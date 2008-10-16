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

"""Look up a definition in the Urban Dictionary"""

import re
import SOAPpy
from include.utils import Module, stripHTML
import logging as log

class Main(Module):
    pattern = re.compile('^\s*urban\s+(.+)')
    require_addressing = True
    help = 'urban <phrase> - look up a word/phrase on urban dictionary'
    key = 'a979884b386f8b7ea781754892f08d12'
    error = "%s: So obscure even urban dictionary doesn't know what it means"

    def __init__(self, madcow=None):
        self.server = SOAPpy.SOAPProxy("http://api.urbandictionary.com/soap")

    def response(self, nick, args, kwargs):
        try:
            words = args[0].split()
            if words[-1].isdigit():
                i = int(words[-1])
                term = ' '.join(words[:-1])
            else:
                i = 1
                term = ' '.join(words)


            items = self.server.lookup(self.key, term)

            max = len(items)
            if max == 0:
                return self.error % nick

            if i > max:
                return '%s: CRITICAL BUFFER OVERFLOW ERROR' % nick

            item = items[i - 1]
            response = '%s: [%s/%s] %s - Example: %s' % (nick, i, max,
                    item.definition, item.example)
            response = stripHTML(response)
            return response.encode("utf-8")

        except Exception as e:
            log.warn('error in %s: %s' % (self.__module__, e))
            log.exception(e)
            return "%s: Serious problems: %s" % (nick, e)


if __name__ == '__main__':
    from include.utils import test_module
    test_module(Main)
