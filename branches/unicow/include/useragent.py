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

"""Closely mimic a browser"""

import sys
import urllib2
import urlparse
import urllib
import logging as log
import encoding

AGENT = 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 6.0)'
VERSION = sys.version_info[0] * 10 + sys.version_info[1]
UA = None

class UserAgent(object):

    """Closely mimic a browser"""

    def __init__(self, handlers=None, cookies=True, agent=AGENT, timeout=None):
        self.timeout = timeout
        if handlers is None:
            handlers = []
        if cookies:
            handlers.append(urllib2.HTTPCookieProcessor)
        self.opener = urllib2.build_opener(*handlers)
        if agent:
            self.opener.addheaders = [('User-Agent', agent)]

    def open(self, url, opts=None, data=None, referer=None, size=-1,
             timeout=-1):
        """Open URL and return unicode content"""
        log.debug('fetching url: %s' % url)
        url = list(urlparse.urlparse(url))
        if opts:
            query = [urllib.urlencode(opts)]
            if url[4]:
                query.append(url[4])
            url[4] = '&'.join(query)
        request = urllib2.Request(urlparse.urlunparse(url), data)
        if referer:
            request.add_header('Referer', referer)
        if timeout == -1:
            timeout = self.timeout
        args = [request]
        if VERSION < 26:
            self.settimeout(timeout)
        else:
            args.append(timeout)
        response = self.opener.open(*args)
        data = response.read(size)
        return encoding.convert(data, response.headers)

    @staticmethod
    def settimeout(timeout):
        """Monkey-patch socket timeout if older urllib2"""

        def connect(self):
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(timeout)
                self.sock.connect((self.host, self.port))
            except socket.error, error:
                if self.sock:
                    self.sock.close()
                self.sock = None
                raise error

        import httplib
        httplib.HTTPConnection.connect = connect


def getua():
    """Returns global user agent instance"""
    global UA
    if UA is None:
        UA = UserAgent()
    return UA


def setup(handlers=None, cookies=True, agent=AGENT, timeout=None):
    """Create global user agent instance"""
    global UA
    UA = UserAgent(handlers, cookies, agent, timeout)


def geturl(url, opts=None, data=None, referer=None, size=-1, timeout=-1):
    return getua().open(url, opts, data, referer, size, timeout)

geturl.__doc__ = UserAgent.open.__doc__

