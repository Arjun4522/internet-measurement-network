#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    ping a host via tcp protocol
"""

import socket
import time
import asyncio

from six.moves import zip_longest
from timeit import default_timer as timer
from icmplib import Host


def avg(x):
    return sum(x) / float(len(x))


class Socket(object):
    def __init__(self, family, type_, timeout):
        s = socket.socket(family, type_)
        s.settimeout(timeout)
        self._s = s

    def connect(self, host, port=80):
        self._s.connect((host, int(port)))

    def shutdown(self):
        self._s.shutdown(socket.SHUT_RD)

    def close(self):
        self._s.close()


class Timer(object):
    def __init__(self):
        self._start = 0
        self._stop = 0

    def start(self):
        self._start = timer()

    def stop(self):
        self._stop = timer()

    def cost(self, funcs, args):
        self.start()
        for func, arg in zip_longest(funcs, args):
            if arg:
                func(*arg)
            else:
                func()

        self.stop()
        return self._stop - self._start


class TCPing(object):
    def __init__(self, host, port, count=3, timeout=1):
        self.timer = Timer()
        self.successed = 0
        self.failed = 0
        self.rtts = []
        self.host = host
        self.port = port
        self.count = count
        self.timeout = timeout

    async def create_socket(self, family, type_):
        return Socket(family, type_, self.timeout)

    async def ping(self):
        for n in range(1, self.count + 1):
            s = await self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                time.sleep(1)
                cost_time = self.timer.cost((s.connect, s.shutdown), ((self.host, self.port), None))
                s_runtime = 1000 * (cost_time)

                self.rtts.append(s_runtime)

            except socket.timeout:
                self.failed += 1

            else:
                self.successed += 1

            finally:
                s.close()

        return Host(self.host, self.count, self.rtts)