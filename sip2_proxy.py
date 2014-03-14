#!/usr/bin/env python2

import logging
from BufferingSMTPHandler import BufferingSMTPHandler
import asyncore
import socket
from datetime import datetime
from random import randrange
import traceback
import re
from asyncore_delay import CallLater, loop

# setting
PROXY_PORT = 6001
# recommend longer than 2
SERVER_CONNECT_TIMEOUT = 5
SERVER_CONNECT_RETRY_TIME = 5

TEST_INTERVAL = 5

# log setting
LOG_TO_FILE = True
LOG_FILE_DIR = "/home/sip2_proxy/log/"
LOG_LEVEL = logging.WARNING

# server list
sip2_server_list = [
    ("192.168.64.52", 6001),
    ("192.168.64.52", 6005),
    ("192.168.64.52", 6009),
    ("192.168.64.52", 6011),
    ("192.168.64.53", 6001),
    ("192.168.64.53", 6003),
    ("192.168.64.53", 6005),
    ("192.168.64.53", 6007),
#    ("192.168.64.53", 6009),
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
    handler.setLevel(LOG_LEVEL)
    fmt = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    mail_handeler = BufferingSMTPHandler(mailhost='smtp.stu.edu.cn',
                                         fromaddr='xdli@stu.edu.cn',
                                         toaddrs=['xdli@stu.edu.cn',
                                                  'qzma@stu.edu.cn'],
                                         subject='The Sip2 Proxy Error log',
                                         credentials=('xdli', 'ad4.stu'),
                                         secure=None,
                                         capacity=64)
    mail_handeler.setLevel(logging.ERROR)
    mail_handeler.setFormatter(fmt)
    logger.addHandler(mail_handeler)


class Sip2Sock(asyncore.dispatcher):
    write_buffer = ''
    other = None

    def readable(self):
        if self.other and self.connected:
            return True
        else:
            return False

    def handle_read(self):
        recv_sip = self.recv(4096*4)
        logger.debug("%s read %s" % (self, recv_sip))

        if self.other:
            self.other.write_buffer += recv_sip

    def writable(self):
        if self.connected:
            return 0 < len(self.write_buffer)
        else:
            return True

    def handle_write(self):
        if self.other and self.write_buffer:
            logger.debug("%s write %s" % (self, self.write_buffer))
            sent = self.send(self.write_buffer)
            self.write_buffer = self.write_buffer[sent:]

    def handle_close(self):
        self.close()


class Sip2Server(Sip2Sock):
    test_sip = "1720130913    095122AO044120|AB5095888|AC|AY4AZF55C\r"
    test_re = re.compile("^18")

    def setup_socket(self):
        logger.info("Try connect to %s:%s" % self.host)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect(self.host)
        self.reset()

    def reset(self):
        self.testing = False
        self.in_use = False
        self.test_result = False

    def __init__(self, host):
        asyncore.dispatcher.__init__(self)
        self.host = host
        self.setup_socket()

    def handle_close(self):
        if self.testing:
            self.end_test()

        if self.other:
            logger.warning("Server %s force release %s" % (self.host,
                                                           self.other.addr))
            self.other.handle_close()
            self.other = None

        self.close()
        logger.warning("Server %s:%s close" % self.host)
        show_servers_info()
        CallLater(SERVER_CONNECT_RETRY_TIME, self.setup_socket)

    def handle_connect(self):
        self.in_use = False
        logger.info("Server %s:%s connected" % self.host)

    def handle_error(self):
        nil, t, v, tbinfo = asyncore.compact_traceback()
        logger.warning("Server %s (%s:%s)\n(%s)" % (self.host, t, v, tbinfo))
        self.handle_close()

    def start_test(self):
        logger.debug("Server %s:%s test start" % self.host)
        if self.connected and not self.in_use:
            self.testing = True
            self.in_use = True
            self.test_result = False
            self.write_buffer += self.test_sip
        else:
            logger.warning("Server %s:%s in use or disconnect, stop testing"
                           % self.host)

        show_servers_info()

    def end_test(self):
        if self.test_result:
            logger.info("Server %s:%s test passed" % self.host)
        else:
            logger.warning("Server %s:%s test failed" % self.host)

        logger.debug("Server %s:%s test end" % self.host)
        self.testing = False
        self.in_use = False

        show_servers_info()

    def handle_write(self):
        if self.testing and self.write_buffer:
            logger.debug("%s send test sip: %s" % (self, self.write_buffer))
            sent = self.send(self.write_buffer)
            self.write_buffer = self.write_buffer[sent:]
        else:
            Sip2Sock.handle_write(self)

    def handle_read(self):
        if self.testing:
            recv_sip = self.recv(4096*4)
            logger.debug("%s receive test sip: %s" % (self, recv_sip))
            if self.test_re.match(recv_sip):
                self.test_result = True
            self.end_test()
        else:
            Sip2Sock.handle_read(self)

    def readable(self):
        if self.testing:
            return True
        else:
            return Sip2Sock.readable(self)

    def writable(self):
        if self.testing:
            return True
        else:
            return Sip2Sock.writable(self)


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
        show_servers_info()


class Sip2ProxyServer(asyncore.dispatcher):
    def __init__(self, host, port):
        asyncore.dispatcher.__init__(self)
        logger.info("Start sip2 proxy server on port: %d", port)
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
                client_sock.handle_close()

        show_servers_info()


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


def show_servers_info():
    connected_server = filter(lambda server: server.connected,
                              sip2_server_socks)
    in_use_servers = filter(lambda server: server.in_use, connected_server)
    total = len(sip2_server_socks)
    avaiable = len(connected_server)

    logger.info("Server Info Total: %d connected: %d used:%d" %
                (total,
                 avaiable,
                 len(in_use_servers)))
    if avaiable <= (total / 2):
        logger.error("[%d / %d] server not avaiable" % (total - avaiable, total))


def test_server():
    server = get_avaible_server()
    if server:
        server.start_test()
    else:
        logger.error("No avaiable servers")

    CallLater(TEST_INTERVAL, test_server)


def start_sip2_proxy_server():
    try:
        config_logger()
        setup_server_socks()
        Sip2ProxyServer('0.0.0.0', PROXY_PORT)
        CallLater(TEST_INTERVAL, test_server)
        loop(timeout=0.1, use_poll=True)
    except Exception as e:
        logger.exception(e)

if __name__ == "__main__":
    start_sip2_proxy_server()
