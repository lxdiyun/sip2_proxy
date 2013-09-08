#!/usr/bin/env python2
from daemon import runner
from sip2_proxy import start_sip2_proxy_server


class App(object):
    def __init__(self):
        self.stdin_path = '/dev/null'
        self.stdout_path = '/home/adli/sip2_proxy/log/stdout'
        self.stderr_path = '/home/adli/sip2_proxy/log/stderr'
        self.pidfile_path = '/var/run/sip2_proxy/sip2_proxy.pid'
        self.pidfile_timeout = 5

    def run(self):
        start_sip2_proxy_server()


app = App()

daemon_runner = runner.DaemonRunner(app)
daemon_runner.do_action()
