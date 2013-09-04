#!/usr/bin/env python2

import logging
import sys
import asyncore
import socket
import gevent
import os
from gevent.server import StreamServer

PROXY_PORT = 6001

logger = None

sip2_server_list = [
    ("10.35.24.43", 6001),
    ("192.168.64.52", 6011),
]


def config_logger():
    global logger
    """
    Set the log level and choose the destination for log output.
    """
    logger = logging.getLogger(__name__)

    handler = logging.StreamHandler()

    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    handler.setFormatter(fmt)
    logger.addHandler(handler)


def accept_client(socket, address):
    logger.info('New connection from %s:%s' % address)
    fileobj = socket.makefile()

    while True:
        line = fileobj.readline()
        if not line:
            logger.info("client %s:%s disconnected" % address)
            break
        if line.strip().lower() == 'quit':
            logger.info("client %s:%s quit" % address)
            break
        fileobj.write(line)
        fileobj.flush()
        logger.info("echoed %s %r" % (address, line))


def main():
    server = StreamServer(('0.0.0.0', PROXY_PORT), accept_client)
    server.serve_forever()


class Sip2Handler(asyncore.dispatcher_with_send):

    def handle_read(self):
        data = self.recv(8192)
        if data:
            self.send(data)


class Sip2ProxyServer(asyncore.dispatcher):

    def __init__(self, host, port):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((host, port))
        self.listen(5)

    def handle_accept(self):
        pair = self.accept()
        if pair is not None:
            sock, addr = pair
            logger.info('Incoming connection from %s' % repr(addr))
            handler = Sip2Handler(sock)
            logger.debug(handler)


class Sip2Client(asyncore.dispatcher):
    def __init__(self, host):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host = host
        self.avaiable = False
        self.conect(self.host)

    def handle_close(self):
        self.close()
        self.avaiable = False
        self.connect(self.host)

    def handle_connect(self):
        self.avaiable = True


if __name__ == "__main__":
    config_logger()
    server = Sip2ProxyServer('0.0.0.0', PROXY_PORT)
    asyncore.loop()
