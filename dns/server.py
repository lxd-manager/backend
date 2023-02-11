# -*- coding: utf-8 -*-

"""
    FixedResolver - example resolver which responds with fixed response
                    to all requests
"""

from __future__ import print_function

from dnslib import RR, parse_time, QTYPE, RCODE, A, AAAA
from dnslib.label import DNSLabel
from dnslib.server import DNSServer, DNSHandler, BaseResolver, DNSLogger
from dnslib.dns import DNSRecord

import sys
import os
import json
import ipaddress
from datetime import datetime

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ct_backend.settings")
sys.path.append(os.path.abspath(__file__ + "/../../"))

import django  # noqa: F402
django.setup()

from apps.container.models import Container  # noqa: F402
from apps.dns.models import ZoneExtra, DynamicEntry  # noqa: F402
from django.conf import settings  # noqa: F402
from django.db import connections


class LXDResolver(BaseResolver):

    def __init__(self, origin, ttl):
        self.origin = DNSLabel(origin)
        self.ttl = parse_time(ttl)
        self.routes = {}

    def resolve(self, request, handler):
        reply = request.reply()
        qname = request.q.qname
        qtype = request.q.qtype

        suffix = DNSLabel(self.origin)
        if request.q.qtype == QTYPE.AXFR and settings.DNS_ALLOW_TRANSFER and ipaddress.ip_address(handler.client_address[0]) in ipaddress.ip_network(settings.DNS_ALLOW_TRANSFER):
            rrs = []

            now = datetime.now()
            soatime = now.strftime('%y%j')+"%05d"%(now.hour*3600+now.minute*60+now.second)
            rrs += RR.fromZone(f"{self.origin} 60 IN SOA {settings.DNS_BASE_DOMAIN} non-exist.{settings.DNS_BASE_DOMAIN} {soatime} 900 900 1800 60")

            for extra in ZoneExtra.objects.all():
                rrs += RR.fromZone(extra.entry)
            for dyn in DynamicEntry.objects.all():
                rrs += RR.fromZone(dyn.combined)
            for cts in Container.objects.all():
                for ip in ct.ip_set.all():
                    if ip.is_ipv4:
                        rrs += RR(qname, QTYPE.A, ttl=self.ttl, rdata=A(ip.ip))
                    elif ip.siit_ip.exists():
                        rrs += RR(qname, QTYPE.A, ttl=self.ttl, rdata=A(ip.siit_ip.first().ip))
                    else:
                        rrs += RR(qname, QTYPE.AAAA, ttl=self.ttl, rdata=AAAA(ip.ip))

            rrs += RR.fromZone(f"{self.origin} 60 IN SOA {settings.DNS_BASE_DOMAIN} non-exist.{settings.DNS_BASE_DOMAIN} {soatime} 900 900 1800 60")

            reply.add_answer(*rrs)
        elif str(qname.label[-len(suffix.label):]).lower() == str(suffix.label).lower():
            rem = DNSLabel(qname.label[:-len(suffix.label)])
            print("queries for :", rem, qtype)

            found_rrs = []
            found_glob = []
            rrs = []
            for extra in ZoneExtra.objects.all():
                rrs += RR.fromZone(extra.entry)
            for dyn in DynamicEntry.objects.all():
                rrs += RR.fromZone(dyn.combined)
            for rr in rrs:
                if rem == rr.rname and rr.rtype in [qtype, QTYPE.CNAME]:
                    rr.rname.label += self.origin.label
                    found_rrs.append(rr)
                elif rem.matchGlob(rr.rname) and rr.rtype in [qtype, QTYPE.CNAME]:
                    rr.rname.label += self.origin.label
                    found_glob.append(rr)


            if len(found_rrs):
                reply.add_answer(*found_rrs)
            elif len(found_glob):
                for g in found_glob:
                    g.set_rname(qname)
                reply.add_answer(*found_glob)

            cts = Container.objects.filter(name=str(str(rem)[:-1]).lower())
            if cts.exists():
                ct = cts.first()
                
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
            # try other server
            if len(reply.rr) == 0 and (settings.DNS_MIRROR_SERVER is not None):
                print("checking other server because no rr and env: .%s. "%settings.DNS_MIRROR_SERVER)
                connections.close_all()  # might fail
                apk = request.send(settings.DNS_MIRROR_SERVER, 53, timeout=30)
                reply = DNSRecord.parse(apk)

            if len(reply.rr) == 0:
                reply.header.rcode = RCODE.NOERROR
                now = datetime.now()
                soatime = now.strftime('%y%j')+"%05d"%(now.hour*3600+now.minute*60+now.second)
                reply.add_auth(*RR.fromZone(f"{self.origin} 60 IN SOA {settings.DNS_BASE_DOMAIN} non-exist.{settings.DNS_BASE_DOMAIN} {soatime} 900 900 1800 60"))
            else:
                reply.add_auth(*RR.fromZone(f"{self.origin} 60 IN NS {settings.DNS_BASE_DOMAIN}"))
        else:
            reply.header.rcode = RCODE.NXDOMAIN

        connections.close_all()
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
