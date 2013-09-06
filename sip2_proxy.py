#!/usr/bin/env python2

import logging
import asyncore
import socket
import traceback
from asyncore_delay import CallLater, loop

PROXY_PORT = 6001

logger = None

sip2_server_list = [
    ("10.35.24.43", 6001),
    ("10.35.24.43", 6003),
    ("10.35.24.43", 6005),
    ("10.35.24.43", 6007),
    ("10.35.24.43", 6009),
]

sip2_server_socks = list()


def config_logger():
    global logger
    """
    Set the log level and choose the destination for log output.
    """
    logger = logging.getLogger(__name__)

    handler = logging.StreamHandler()

    logger.setLevel(logging.INFO)
    fmt = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    handler.setFormatter(fmt)
    logger.addHandler(handler)


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
        logger.debug(' [-] %i -> %i (closed)' %
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
        CallLater(5, self.check_status)
        self.connect(self.host)

    def __init__(self, host):
        asyncore.dispatcher.__init__(self)
        self.host = host
        self.setup_socket()

    def handle_close(self):
        self.close()
        if self.other:
            self.other.close()
            self.other = None
        self.avaiable = False
        self.check_event = CallLater(1, self.setup_socket)
        logger.warning("Server %s:%s close" % self.host)

    def handle_connect(self):
        self.avaiable = True
        self.in_use = False
        logger.info("Server %s:%s connected" % self.host)

    def handle_error(self):
        nil, t, v, tbinfo = asyncore.compact_traceback()
        logger.error("Server %s (%s:%s" % (self.host, t, v))
        self.handle_close()


class Sip2Client(Sip2Sock):
    def set_server(self, server):
        self.other = server
        server.other = self
        server.in_use = True
        logger.debug("server %s in use by %s" % (server.host,
                                                 self.getpeername()[1]))

    def handle_close(self):
        if self.other:
            self.other.in_use = False
            logger.debug("server %s release by %s" % (self.other.host,
                                                      self.getpeername()[1]))
            self.other = None
        Sip2Sock.handle_close(self)


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
            logger.debug('Incoming connection from %s' % repr(addr))
            client_sock = Sip2Client(sock)
            server = get_avaible_server()
            if server:
                client_sock.set_server(server)
            else:
                client_sock.close()


def setup_server_socks():
    global sip2_server_socks

    for host in sip2_server_list:
        sip2_server = Sip2Server(host)
        sip2_server_socks.append(sip2_server)


def get_avaible_server():
    avaiable_servers = filter(lambda server: (server.avaiable and not
                                              server.in_use),
                              sip2_server_socks)

    if avaiable_servers:
        return avaiable_servers[0]
    else:
        return None


if __name__ == "__main__":
    config_logger()
    setup_server_socks()
    proxy_server = Sip2ProxyServer('0.0.0.0', PROXY_PORT)
    loop()
