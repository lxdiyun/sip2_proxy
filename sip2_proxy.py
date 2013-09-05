#!/usr/bin/env python2

import logging
import asyncore
import socket
import traceback
from gevent.server import StreamServer
from asyncore_delay import CallLater, loop

PROXY_PORT = 6001

logger = None

sip2_server_list = [
    ("10.35.24.43", 6001),
    ("192.168.64.52", 6011),
]

sip2_server_socks = list()


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


class Sip2Sock(asyncore.dispatcher):
    write_buffer = ''
    other = None

    def readable(self):
        if self.other:
            return not self.other.write_buffer
        else:
            return False

    def handle_read(self):
        if self.other:
            self.other.write_buffer += self.recv(4096*4)

    def handle_write(self):
        if self.other:
            sent = self.send(self.write_buffer)
            self.write_buffer = self.write_buffer[sent:]

    def handle_close(self):
        logger.info(' [-] %i -> %i (closed)' %
                    (self.getsockname()[1], self.getpeername()[1]))
        self.close()


class Sip2Server(Sip2Sock):
    def check_status(self):
        if not self.avaiable:
            logger.error("Server %s:%s connect timeout" % self.host)
            self.handle_close()

    def setup_socket(self):
        logger.info("Try connect to %s:%s" % self.host)
        self.avaiable = False
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        CallLater(1, self.check_status)
        self.connect(self.host)

    def __init__(self, host):
        asyncore.dispatcher.__init__(self)
        self.host = host
        self.setup_socket()

    def handle_close(self):
        logger.warning("Server %s:%s close" % self.host)
        self.close()
        if self.other:
            self.other.close()
            self.other = None
        self.avaiable = False
        CallLater(1, self.setup_socket)

    def handle_connect(self):
        logger.info("Server %s:%s connected" % self.host)
        self.avaiable = True

    def handle_error(self):
        traceback.print_stack()
        nil, t, v, tbinfo = asyncore.compact_traceback()
        logger.error("Server %s (%s:%s" % (self.host, t, v))
        self.handle_close()


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
            client_sock = Sip2Sock(sock)
            client_sock.other = sip2_server_socks[0]
            sip2_server_socks[0].other = client_sock


if __name__ == "__main__":
    config_logger()
    proxy_server = Sip2ProxyServer('0.0.0.0', PROXY_PORT)
    sip2_server = Sip2Server(("10.35.24.43", 6001))
    sip2_server_socks.append(sip2_server)
    loop()
