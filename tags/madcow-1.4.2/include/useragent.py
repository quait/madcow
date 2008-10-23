#!/usr/bin/env python
#
# Copyright (C) 2007, 2008 Christopher Jones
#
# This file is part of Madcow.
#
# Madcow is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Madcow is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Madcow.  If not, see <http://www.gnu.org/licenses/>.

"""Library to mimic a browser"""

from urllib2 import HTTPCookieProcessor, build_opener, Request, httplib
from cookielib import CookieJar
from urlparse import urlparse, urlunparse
from urllib import urlencode
import socket
import logging as log

__version__ = '2.0'
__author__ = 'cj_ <cjones@gruntle.org>'
__all__ = ['UserAgent', 'geturl', 'posturl']

# user agent is shared across instances
_ua = None

class UserAgent(object):
    """This is the class to mimic a browser"""
    _msie = 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 6.0)'
    blocksize = 512

    def __init__(self, agent=_msie, cookies=True, handlers=[]):
        self.agent = agent
        if cookies:
            handlers.append(HTTPCookieProcessor(CookieJar()))
        self.opener = build_opener(*handlers)

    def openurl(self, url, data=None, opts={}, referer=None, fo=None, size=-1,
            method='GET'):
        """Open a URL and return output"""

        # parse options and generate proper query string
        url = list(urlparse(url))
        method = method.lower()
        query = [urlencode(opts), data]
        if method == 'get':
            query.append(url[4])
        query = '&'.join([i for i in query if i])
        query = query.replace(' ', '%20')
        if method == 'get':
            url[4] = query
            data = None
        else:
            data = query
        url = urlunparse(url)

        log.debug('fetching url: ' + url)

        # issue the request
        request = Request(url, data=data)
        request.add_header('User-Agent', self.agent)
        if referer:
            request.add_header('Referer', referer)
        response = self.opener.open(request)

        # return output from request
        if fo is None:
            return response.read(size)

        # write output to provided fileobj
        blocksize = self.blocksize
        count = 0
        while True:
            if size > 0:
                if count >= size:
                    break
                if (count + blocksize) >= size:
                    blocksize = size - count
            block = response.read(blocksize)
            if not len(block):
                break
            fo.write(block)
            count += len(block)

    def __str__(self):
        return '<%s %s>' % (self.__class__.__name__, self.__dict__)

    __repr__ = __str__


def settimeout(timeout):
    """Set socket timeout for all requests"""

    def connect(self):
        msg = 'unknown socket error'
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(timeout)
            self.sock.connect((self.host, self.port))
        except socket.error, msg:
            if self.sock:
                self.sock.close()
            self.sock = None
        if not self.sock:
            raise socket.error, msg

    httplib.HTTPConnection.connect = connect

def get_agent():
    global _ua
    if _ua is None:
        _ua = UserAgent()
    return _ua

def setup(agent=UserAgent._msie, cookies=True, handlers=[], timeout=None):
    global _ua
    _ua = UserAgent(agent, cookies, handlers)
    settimeout(timeout)

def geturl(url, data=None, opts={}, referer=None, fo=None, size=-1):
    """Issue GET request"""
    return get_agent().openurl(url, data, opts, referer, fo, size, 'get')

def posturl(url, data=None, opts={}, referer=None, fo=None, size=-1):
    """Issue POST request"""
    return get_agent().openurl(url, data, opts, referer, fo, size, 'post')

def main():
    """When called from the commandline, act as a limited wget"""
    op = OptionParser(version=__version__, usage=__usage__)
    op.add_option('-o', '--output', metavar='<file>', default=None,
            help='output to this file instead of STDOUT')
    op.add_option('-p', '--post', dest='method', action='store_const',
            default='GET', const='POST', help='issue POST instead of GET')
    op.add_option('-d', '--data', metavar='<data>',
            help='send this data in post request (implies -p)')
    op.add_option('-s', '--size', metavar='<bytes>', type='int',
            default=-1, help='limit read to these bytes, default is read all')
    op.add_option('-r', '--referer', metavar='<url>', help='use this referer')
    op.add_option('-a', '--agent', metavar='<agent>', default=UserAgent._msie,
            help='default: %default')
    op.add_option('-t', '--timeout', type='int', metavar='<secs>',
            help='set request timeout (default: %default)')
    opts, args = op.parse_args()

    setup(agent=opts.timeout, cookies=True, handlers=[], timeout=opts.timeout)
    ua = get_agent()

    if len(args) != 1:
        sys.stderr.write('Error: missing URL\n')
        op.print_help()
        return 1
    url = args[0]

    if opts.data is not None:
        opts.method = 'POST'

    if opts.output is None:
        fo = sys.stdout
    else:
        fo = open(opts.output, 'wb')
    try:
        ua.openurl(url, opts.data, {}, opts.referer, fo, opts.size, opts.method)
    finally:
        fo.close()

    return 0

if __name__ == '__main__':
    import sys
    from optparse import OptionParser
    __usage__ = '%prog [options] <url>'
    sys.exit(main())