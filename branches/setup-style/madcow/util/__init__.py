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

"""Some helper functions"""

from htmlentitydefs import name2codepoint
from time import time as unix_time
from HTMLParser import HTMLParser
from datetime import datetime
import tempfile
import logging as log
import errno
import re
import sys
import os
from madcow.conf import settings

DEFAULT_UNIQUE_TIMESTAMP_FORMAT = '%Y%m%d'
DEFAULT_UNIQUE_MAX_FILES = 1000
DEFAULT_UNIQUE_DELIM = '.'
TEMPDIR = tempfile.gettempdir()

# translation map to make superscripts
SUPER_MAP = {48: 8304, 49: 8305, 50: 178, 51: 179, 52: 8308, 53: 8309,
             54: 8310, 55: 8311, 56: 8312, 57: 8313, 43: 8314, 45: 8315,
             61: 8316, 40: 8317, 41: 8318, 110: 8319}

# apos is non-standard but used frequently
name2codepoint = dict(name2codepoint)
name2codepoint['apos'] = ord("'")

class HTMLStripper(HTMLParser):

    def __init__(self, data):
        HTMLParser.__init__(self)
        self._stripped = []
        self.feed(data)

    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'br':
            self._stripped.append('\n')

    def handle_charref(self, name):
        try:
            if name.lower().startswith('x'):
                char = int(name[1:], 16)
            else:
                char = int(name)
            self._stripped.append(unichr(char))
        except Exception, error:
            log.warn('invalid entity: %s' % error)

    def handle_entityref(self, name):
        try:
            char = unichr(name2codepoint[name])
        except Exception, error:
            log.warn('unknown entity: %s' % error)
            char = u'&%s;' % name
        self._stripped.append(char)

    def handle_data(self, data):
        self._stripped.append(data)

    @property
    def stripped(self):
        return ''.join(self._stripped)


class Module(object):

    """Base module class"""

    _any = re.compile(r'^(.+)$')
    pattern = re.compile('')
    enabled = True
    require_addressing = True
    help = None
    priority = 50
    terminate = True
    allow_threading = True
    error = None

    def __init__(self, madcow=None):
        self.madcow = madcow

    def response(self, nick, args, **kwargs):
        return u'not implemented'


class Request(object):

    """Generic object passed in from protocol handlers for processing"""

    defaults = {'message': None,
                'sendto': None,
                'private': False,
                'nick': None,
                'matched': False,
                'feedback': False,
                'correction': False,
                'colorize': False,
                'channel': None,
                'addressed': False,
                'action': False}

    def __init__(self, **kwargs):
        self.__dict__.update(self.defaults, **kwargs)


def cache_property(timeout=None):

    """Caching property decorator"""

    cache = {}

    def decorator(method):

        def inner(*args, **kwargs):
            if method in cache:
                if unix_time() - cache[method]['lastrun'] > timeout:
                    del cache[method]
            if method not in cache:
                cache[method] = dict(lastrun=unix_time(),
                                     result=method(*args, **kwargs))
            return cache[method]['result']

        inner.__doc__ = method.__doc__
        inner.__name__ = method.__name__
        return property(inner)
    return decorator


def find_madcow():
    """Find where we are run from and config file location"""
    if __file__.startswith(sys.argv[0]):
        prefix = sys.argv[0]
    else:
        prefix = __file__
    parts = os.path.abspath(os.path.dirname(prefix)).split(os.sep)
    found = False
    prefix = None
    while parts:
        prefix = os.sep.join(parts)
        config = os.path.join(prefix, 'madcow.ini')
        if os.path.exists(config):
            found = True
            break
        parts.pop()
    if not found:
        raise Exception('No config file found')
    return prefix, config


def test_module(mod, argv=None):
    if argv is None:
        argv = sys.argv[1:]
    prefix, configfile = find_madcow()
    sys.path.insert(0, prefix)
    from madcow import Madcow, DEFAULTS
    from config import Config
    log.basicConfig(level=log.ERROR)
    defaults = os.path.join(prefix, DEFAULTS)
    config = Config(configfile, defaults)
    madcow = Madcow(config, prefix, 'ansi')
    main = mod(madcow)
    try:
        args = main.pattern.search(u' '.join(argv)).groups()
    except:
        print 'no match, double-check regex'
        return 1
    print main.response(nick=os.environ[u'USER'], args=args, kwargs={}).encode('utf-8')
    return 0


def superscript(text):
    if isinstance(text, str):
        text = text.decode('utf8', 'replace')
    return text.translate(SUPER_MAP)


def stripHTML(data):
    return HTMLStripper(data).stripped


def get_logger(name=None, dir=None, unique=True, timestamp_format=None, max_unique_files=None, level=None,
               format=None, time_format=None, encoding=None, stream=None, store_errors=False, store_warnings=False):

    # create a logger with defaults from settings, if set
    from madcow.util.logging import Logger
    if level is None:
        level = getattr(settings, 'LOGGING_LEVEL', None)
    if format is None:
        format = getattr(settings, 'LOGGING_FORMAT', None)
    if time_format is None:
        time_format = getattr(settings, 'LOGGING_TIME_FORMAT', None)
    if encoding is None:
        encoding = getattr(settings, 'LOGGING_ENCODING', None)
    logger = Logger(level=level, format=format, time_format=time_format, encoding=encoding, stream=stream,
                    store_errors=store_errors, store_warnings=store_warnings)

    # add a file to central logfile area
    if name is None:
        name = 'madcow'
    if dir is None:
        dir = os.path.join(os.environ['MADCOW_BASE'], 'log')
    if not os.path.exists(dir):
        os.makedirs(dir)
    if unique:
        path, fd = get_unique_file(dir=dir, prefix=name, suffix='log',
                                   timestamp_format=timestamp_format,
                                   max_files=max_unique_files)
        os.close(fd)
    else:
        path = os.path.join(dir, name + '.log')
    logger.add_file(path)
    logger.info('Logfile opened: %s', os.path.basename(path))
    return logger


def unique_opener(create_func, dir=None, prefix=None, suffix=None, timestamp_format=None, max_files=None, delim=None):
    if timestamp_format is None:
        timestamp_format = getattr(settings, 'UNIQUE_TIMESTAMP_FORMAT', DEFAULT_UNIQUE_TIMESTAMP_FORMAT)
    if max_files is None:
        max_files = getattr(settings, 'UNIQUE_MAX_FILES', DEFAULT_UNIQUE_MAX_FILES)
    if delim is None:
        delim = DEFAULT_UNIQUE_DELIM
    if dir is None:
        dir = TEMPDIR
    if not os.path.exists(dir):
        os.makedirs(dir)

    # build the format string
    format = []
    delim = delim.replace('%', '%%')
    if prefix:
        format.append(prefix.replace('%', '%%'))
    format.append(datetime.now().strftime(timestamp_format).replace('%', '%%'))
    format.append('%%0%dd' % len(str(max_files - 1)))
    if suffix:
        format.append(suffix.replace('%', '%%'))
    format = delim.replace('%s', '%%').join(format)

    for i in xrange(max_files):
        filename = format % i
        path = os.path.join(dir, filename)
        try:
            result = create_func(path)
            break
        except OSError, error:
            if error.errno != errno.EEXIST:
                raise
    else:
        raise

    return path, result


def get_unique_dir(dir=None, prefix=None, suffix=None, timestamp_format=None, max_files=None, delim=None, perms=0755):
    create_func = lambda path: os.mkdir(path, perms)
    return unique_opener(create_func, dir, prefix, suffix, timestamp_format, max_files, delim)[0]


def get_unique_file(dir=None, prefix=None, suffix=None, timestamp_format=None, max_files=None, delim=None, perms=0644):
    create_func = lambda path: os.open(path, tempfile._text_openflags, perms)
    return unique_opener(create_func, dir, prefix, suffix, timestamp_format, max_files, delim)
