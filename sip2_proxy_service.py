#!/usr/bin/env python2
from sip2_proxy import start_sip2_proxy_server
import daemon


with daemon.DaemonContext():
    start_sip2_proxy_server()
