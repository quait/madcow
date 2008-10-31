#!/usr/bin/env python

import re
from utils import stripHTML
import codecs
import chardet
import logging as log

DEFAULT = 'ascii'
meta_re = re.compile(r'<meta\s+(.*?)\s*>', re.I | re.DOTALL)
attr_re = re.compile(r'\s*([a-zA-Z_][-.:a-zA-Z_0-9]*)(\s*=\s*(\'[^\']*\'|"[^"'
                     r']*"|[-a-zA-Z0-9./,:;+*%?!&$\(\)_#=~@]*))?')

def convert(data, headers=None):
    """Return unicode object of data"""
    if isinstance(data, str):
        data = data.decode(detect(data, headers), 'replace')
    return data


def detect(data, headers=None):
    """Return charset of data"""

    # try to figure out the encoding first from meta tags
    charset = metacharset(data)
    if charset:
        log.debug('using http meta header encoding: %s' % charset)
        return charset

    # if that doesn't work, see if there's a real http header
    if headers and headers.plist:
        charset = headers.plist[0]
        attrs = parseattrs(charset)
        if 'charset' in attrs:
            charset = lookup(attrs['charset'])
        if charset:
            log.debug('using http header encoding: %s' % charset)
            return charset

    # that didn't work, try chardet library
    charset = lookup(chardet.detect(data)['encoding'])
    if charset:
        log.debug('detected encoding: %s' % repr(charset))
        return charset

    # if that managed to fail, just use ascii
    log.warn("couldn't detect encoding, using ascii")
    return DEFAULT


def lookup(charset):
    """Lookup codec"""
    try:
        return codecs.lookup(charset).name
    except LookupError:
        pass


def metacharset(data):
    """Parse data for HTML meta character encoding"""
    for meta in meta_re.findall(data):
        attrs = parseattrs(meta)
        if ('http-equiv' in attrs and
            attrs['http-equiv'].lower() == 'content-type' and
            'content' in attrs):
            content = attrs['content']
            content = parseattrs(content)
            if 'charset' in content:
                return lookup(content['charset'])


def parseattrs(data):
    """Parse key=val attributes"""
    attrs = {}
    for key, rest, val in attr_re.findall(data):
        if not rest:
            val = None
        elif val[:1] == '\'' == val[-1:] or val[:1] == '"' == val[-1:]:
            val = val[1:-1]
            val = stripHTML(val)
        attrs[key.lower()] = val
    return attrs

