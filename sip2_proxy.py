import io
import traceback
import socket

sip2_server_list = [
    ("10.35.24.43", 6001),
    ("192.168.64.52", 6011),
]


class Sipe2Router(object):
    def lookup(self):
#        return sip2_server_list[0]

        for server in sip2_server_list:
            print(server)
            avaiable = True
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            try:
                s.connect(server)
            except socket.error as msg:
                print(msg)
                avaiable = False
            s.close()
            print(avaiable)
            if avaiable:
                return server

        return sip2_server_list[-1]

router = Sipe2Router()

# Perform content-aware routing based on the stream data. Here, the
# Host header information from the HTTP protocol is parsed to find the
# username and a lookup routine is run on the name to find the correct
# couchdb node. If no match can be made yet, do nothing with the
# connection. (make your own couchone server...)


def proxy(data):
    traceback.print_stack()
    host = router.lookup()
    return {"remote": host}


def rewrite_request(req):
    while True:
        data = req.read(io.DEFAULT_BUFFER_SIZE)
        print("SEND: %s" % data)
        if not data:
            break
        req.writeall(data)


def rewrite_response(resp):
    while True:
        data = resp.read(io.DEFAULT_BUFFER_SIZE)
        print("GET: %s" % data)
        if not data:
            break
        resp.writeall(data)
