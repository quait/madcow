#!/usr/bin/env py3
#
# Copyright (C) 2007-2008 Chris Jones
#
# This file is part of Madcow.
#
# Madcow is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# Madcow is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License
# along with Madcow.  If not, see <http://www.gnu.org/licenses/>.

"""Library to mimic a browser"""

import urllib.request
import urllib.parse
from io import StringIO

_ua = None

class UserAgent:

    """Mimics a browser"""

    _agent = 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 6.0)'
    _blocksize = 1024

    def __init__(self, handlers=None, cookies=True, agent=_agent, timeout=None):
        self.timeout = timeout
        if handlers is None:
            handlers = []
        if cookies:
            handlers.append(urllib.request.HTTPCookieProcessor)
        self.opener = urllib.request.build_opener(*handlers)
        self.opener.addheaders = [('User-Agent', agent)]

    def open(self, url, referer=None, opts=None, data=None, file=None, size=0):
        """Open URL"""
        if opts:
            uri = list(urllib.parse.urlparse(url))
            uri[4] = '&'.join([uri[4], urllib.parse.urlencode(opts)])
            url = urllib.parse.urlunparse(uri)
        request = urllib.request.Request(url, data, self.timeout)
        if referer:
            request.add_header('Referer', referer)
        response = self.opener.open(request)
        if not file:
            file = StringIO()
        blocksize = self._blocksize
        read = 0
        while not response.fp.closed:
            if size and read + blocksize > size:
                blocksize = size - read
            block = response.read(blocksize).decode('utf8')
            read += len(block)
            if not block:
                break
            file.write(block)
            if size and read >= size:
                break
        if isinstance(file, StringIO):
            return file.getvalue()


def setup(*args, **kwargs):
    global _ua
    _ua = UserAgent(*args, **kwargs)


def getua():
    global _ua
    if _ua is None:
        _ua = UserAgent()
    return _ua


def geturl(*args, **kwargs):
    return getua().open(*args, **kwargs)
