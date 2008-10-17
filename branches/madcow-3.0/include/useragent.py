#!/home/cjones/local/bin/py3

import sys
from urllib.request import HTTPCookieProcessor, build_opener, Request
from urllib.parse import urlparse, urlencode, urlunparse
import logging as log

_ua = None

class UserAgent:

    _agent = 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 6.0)'
    _blocksize = 8 * 1024

    def __init__(self, handlers=None, timeout=None):
        if handlers is None:
            handlers = []
        handlers.append(HTTPCookieProcessor)
        self.opener = build_opener(*handlers)
        self.opener.addheaders = [('User-Agent', self._agent)]
        self.timeout = timeout

    def open(self, url, opts=None, size=0):
        url = list(urlparse(url))
        if opts:
            url[4] = '&'.join(filter(lambda x: x, [url[4], urlencode(opts)]))
        request = Request(urlunparse(url))
        request.add_header('Referer', '%s://%s/' % (url[0], url[1]))
        log.debug('reading ' + request.get_full_url())
        response = self.opener.open(request, timeout=self.timeout)
        blocksize = self._blocksize
        data = b''
        while not response.fp.closed:
            if size and len(data) + blocksize > size:
                blocksize = size - len(data)
            block = response.read(blocksize)
            if not block:
                break
            data += block
            if size and len(data) >= size:
                break
        return data.decode('raw-unicode-escape')


def get_agent():
    global _ua
    if _ua is None:
        _ua = UserAgent()
    return _ua

def setup(*args, **kwargs):
    global _ua
    _ua = UserAgent(*args, **kwargs)

def geturl(*args, **kwargs):
    return get_agent().open(*args, **kwargs)

