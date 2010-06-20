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

"""Interface for getting really stupid IRC quotes"""

import re
import random
from include.utils import Module, stripHTML
from include.useragent import geturl
import logging as log

class Bash(object):

    random = u'http://www.bash.org/?random'
    bynum = u'http://www.bash.org/?num'
    search = u'http://www.bash.org/'
    query = 'search'
    opts = dict(show=100)
    entries = re.compile(u'<p class="qt">(.*?)</p>', re.DOTALL)


class QDB(object):

    random = u'http://qdb.us/random'
    bynum = u'http://qdb.us/num'
    search = u'http://qdb.us/'
    query = 'search'
    opts = dict(limit=100, approved=1)
    entries = re.compile(u'<td[^>]+><p>(.*?)</p>', re.DOTALL)


class Limerick(object):

    random = u'http://www.limerickdb.com/?random'
    bynum = u'http://www.limerickdb.com/?num'
    search = u'http://www.limerickdb.com/'
    query = 'search'
    opts = dict(number=100)
    entries = re.compile(u'<div class="quote_output">\s*(.*?)\s*</div>',
                         re.DOTALL)


class Main(Module):

    pattern = re.compile(u'^\s*(bash|qdb|limerick)(?:\s+(\S+))?', re.I)
    require_addressing = True
    help = u'<bash|qdb|limerick> [#|query] - get stupid IRC quotes'
    sources = {u'bash': Bash(),
               u'qdb': QDB(),
               u'limerick': Limerick()}
    _error = u'Having some issues, make some stupid quotes yourself'

    def response(self, nick, args, kwargs):
        try:
            source = self.sources[args[0]]
            try:
                query = args[1]
            except:
                query = None
            try:
                num = int(query)
                query = None
            except:
                num = None
            if num:
                url = source.bynum.replace(u'num', unicode(num))
                opts = None
            elif query:
                url = source.search
                opts = dict(source.opts)
                opts[source.query] = query
            else:
                url = source.random
                opts = None
            doc = geturl(url, opts=opts)
            entries = source.entries.findall(doc)
            if query:
                entries = filter(None, entries)
            entry = random.choice(entries)
            entry = stripHTML(entry).strip()
            return entry
        except Exception, error:
            log.warn(u'error in module %s' % self.__module__)
            log.exception(error)
            return u'%s: %s' % (nick, self._error)


if __name__ == u'__main__':
    from include.utils import test_module
    test_module(Main)
