# -*- coding: utf-8 -*-

"""
    FixedResolver - example resolver which responds with fixed response
                    to all requests
"""

from __future__ import print_function

from dnslib import RR, parse_time, QTYPE, RCODE, A, AAAA
from dnslib.label import DNSLabel
from dnslib.server import DNSServer, DNSHandler, BaseResolver, DNSLogger

import sys
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ct_backend.settings")
sys.path.append(os.path.abspath(__file__ + "/../../"))

import django  # noqa: F402
django.setup()

from apps.container.models import Container  # noqa: F402
from django.conf import settings  # noqa: F402


class LXDResolver(BaseResolver):

    def __init__(self, origin, ttl):
        self.origin = DNSLabel(origin)
        self.ttl = parse_time(ttl)
        self.routes = {}

    def resolve(self, request, handler):
        reply = request.reply()
        qname = request.q.qname
        if qname.matchSuffix(self.origin):
            rem = qname.stripSuffix(self.origin)
            print(rem)
            cts = Container.objects.filter(name=str(rem)[:-1])
            if cts.exists():
                ct = cts.first()
                reply.add_auth(*RR.fromZone(f"{self.origin} 60 IN NS {settings.DNS_BASE_DOMAIN}"))

                if request.q.qtype == QTYPE.A:
                    for ip in ct.ip_set.all():
                        if ip.is_ipv4:
                            reply.add_answer(RR(qname, QTYPE.A, ttl=self.ttl,
                                                rdata=A(ip.ip)))
                        elif ip.siit_ip.exists():
                            reply.add_answer(RR(qname, QTYPE.A, ttl=self.ttl,
                                                rdata=A(ip.siit_ip.first().ip)))
                if request.q.qtype == QTYPE.AAAA:
                    for ip in ct.ip_set.all():
                        if not ip.is_ipv4:
                            reply.add_answer(RR(qname, QTYPE.AAAA, ttl=self.ttl,
                                                rdata=AAAA(ip.ip)))
        else:
            reply.header.rcode = RCODE.NXDOMAIN
        return reply


if __name__ == '__main__':

    import argparse
    import time

    p = argparse.ArgumentParser(description="Fixed DNS Resolver")
    p.add_argument("--port", "-p", type=int, default=53, metavar="<port>", help="Server port (default:53)")
    p.add_argument("--address", "-a", default="", metavar="<address>", help="Listen address (default:all)")
    p.add_argument("--udplen", "-u", type=int, default=0, metavar="<udplen>", help="Max UDP packet length (default:0)")
    p.add_argument("--tcp", action='store_true', default=False, help="TCP server (default: UDP only)")
    p.add_argument("--log", default="request,reply,truncated,error",
                   help="Log hooks to enable (default: +request,+reply,+truncated,+error,-recv,-send,-data)")
    p.add_argument("--log-prefix", action='store_true', default=False,
                   help="Log prefix (timestamp/handler/resolver) (default: False)")
    args = p.parse_args()

    resolver = LXDResolver(settings.DNS_CONTAINER_DOMAIN, '60s')
    logger = DNSLogger(args.log, args.log_prefix)

    print("Starting Fixed Resolver (%s:%d) [%s]" % (args.address or "*", args.port, "UDP/TCP" if args.tcp else "UDP"))

    # for rr in resolver.rrs:
    #     print("    | ", rr.toZone().strip(), sep="")
    # print()

    if args.udplen:
        DNSHandler.udplen = args.udplen

    udp_server = DNSServer(resolver, port=args.port, address=args.address, logger=logger)
    udp_server.start_thread()

    if args.tcp:
        tcp_server = DNSServer(resolver, port=args.port, address=args.address, tcp=True, logger=logger)
        tcp_server.start_thread()

    while udp_server.isAlive():
        time.sleep(1)