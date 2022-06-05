#!/usr/bin/env python3
import ipaddress
import os
import random
import re
import socket
import sys

import dns.message
import dns.rdatatype


class DecoyQuery(object):
    '''Generate and send noise domain to primary resolver.'''
    def __init__(self, resolver_ip, sensitive_path):
        self._resolver_ip = resolver_ip
        if ipaddress.ip_address(resolver_ip).version == 6:
            self._family = socket.AF_INET6
        else:
            self._family = socket.AF_INET

        with open(sensitive_path, 'r') as f:
            self._list = f.read().splitlines()

    def send_query(self, qname, qtype=dns.rdatatype.A):
        '''Send a query to primary resolver.'''
        query = dns.message.make_query(qname, rdtype=qtype)
        wire = query.to_wire()

        with socket.socket(self._family, socket.SOCK_DGRAM, 0) as s:
            s.connect((self._resolver_ip, 53))
            s.send(wire)

    def get_random_qname(self, qname):
        '''Generate a noise domain.'''
        while True:
            rand_name = random.choice(self._list)
            if rand_name != qname:
                return rand_name

    def __call__(self, qname, qtype_str='A'):
        '''rewrite __call__() function'''
        qtype = getattr(dns.rdatatype, qtype_str, dns.rdatatype.A)
        qname = self.get_random_qname(qname)
        self.send_query(qname, qtype)


def main():
    '''Start a noisy stub resolver.'''

    PAT = re.compile(r'Packet from \S+ for (?P<qname>\S+) (?P<qtype>\S+) with id \S+')
    RESOLVER = os.environ['PRIMARY_RESOLVER']
    SENSITIVE_PATH = os.environ['SENSITIVE_PATH']
    decoy_query = DecoyQuery(RESOLVER, SENSITIVE_PATH)
    while True:
        for line in sys.stdin:
            matched = PAT.match(line)
            if matched:
                info = matched.groupdict()
                decoy_query(info['qname'], info['qtype'])
            else:
                print(line.rstrip('\n'))

main()

