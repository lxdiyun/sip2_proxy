#!/usr/bin/env python2

import logging
import asyncore
import socket
from datetime import datetime
from random import randrange
import traceback
from asyncore_delay import CallLater, loop

# setting
PROXY_PORT = 6001
# recommend longer than 2
SERVER_CONNECT_TIMEOUT = 5
SERVER_CONNECT_RETRY_TIME = 5

# log setting
LOG_TO_FILE = False
LOG_FILE_DIR = "/home/sip2_proxy/log/"
LOG_LEVEL = logging.DEBUG


# server list
sip2_server_list = [
    ("192.168.64.52", 6001),
#    ("192.168.64.52", 6005),
    ("192.168.64.52", 6009),
    ("192.168.64.52", 6011),
    ("192.168.64.53", 6001),
    ("192.168.64.53", 6003),
    ("192.168.64.53", 6005),
    ("192.168.64.53", 6007),
    ("192.168.64.53", 6009),
]

sip2_server_socks = list()
logger = None


def config_logger():
    global logger
    """
    Set the log level and choose the destination for log output.
    """
    logger = logging.getLogger(__name__)
    handler = None

    if LOG_TO_FILE:
        file_name = LOG_FILE_DIR + datetime.now().strftime('%Y-%m-%d') + ".log"
        handler = logging.FileHandler(file_name)
    else:
        handler = logging.StreamHandler()

    logger.setLevel(LOG_LEVEL)
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
        self.close()


class Sip2Server(Sip2Sock):
    def setup_socket(self):
        logger.info("Try connect to %s:%s" % self.host)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect(self.host)

    def __init__(self, host):
        asyncore.dispatcher.__init__(self)
        self.host = host
        self.setup_socket()

    def handle_close(self):
        self.close()
        if self.other:
            logger.warning("Server %s force release %s" % (self.host,
                                                           self.other.addr))
            self.other.close()
            self.other = None
        self.check_event = CallLater(SERVER_CONNECT_RETRY_TIME,
                                     self.setup_socket)
        logger.warning("Server %s:%s close" % self.host)
        show_server_info()

    def handle_connect(self):
        self.in_use = False
        logger.info("Server %s:%s connected" % self.host)

    def handle_error(self):
        nil, t, v, tbinfo = asyncore.compact_traceback()
        logger.warning("Server %s (%s:%s" % (self.host, t, v))
        self.handle_close()


class Sip2Client(Sip2Sock):
    def __init__(self, sock, addr):
        Sip2Sock.__init__(self, sock)
        self.addr = addr

    def set_server(self, server):
        self.other = server
        server.other = self
        server.in_use = True
        logger.debug("server %s in use by %s" % (server.host,
                                                 self.addr))

    def handle_close(self):
        if self.other:
            self.other.in_use = False
            logger.debug("server %s released by %s" % (self.other.host,
                                                       self.addr))
            self.other = None
        Sip2Sock.handle_close(self)
        show_server_info()


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
            client_sock = Sip2Client(sock, addr)
            server = get_avaible_server()
            if server:
                client_sock.set_server(server)
            else:
                client_sock.close()

        show_server_info()


def setup_server_socks():
    global sip2_server_socks

    for host in sip2_server_list:
        sip2_server = Sip2Server(host)
        sip2_server_socks.append(sip2_server)


def get_avaible_server():
    avaiable_servers = filter(lambda server: (server.connected and not
                                              server.in_use),
                              sip2_server_socks)

    if avaiable_servers:
        return avaiable_servers[randrange(len(avaiable_servers))]
    else:
        return None


def show_server_info():
    connected_server = filter(lambda server: server.connect, sip2_server_socks)
    in_use_servers = filter(lambda server: server.in_use, connected_server)

    logger.info("Server Info Total: %d connected: %d used:%d" %
                (len(sip2_server_socks),
                 len(connected_server),
                 len(in_use_servers)))


def start_sip2_proxy_server():
    try:
        config_logger()
        setup_server_socks()
        Sip2ProxyServer('0.0.0.0', PROXY_PORT)
        loop()
    except Exception as e:
        logger.error(e)

if __name__ == "__main__":
    start_sip2_proxy_server()
