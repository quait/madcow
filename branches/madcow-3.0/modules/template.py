#!/usr/bin/env python

# XXX You should update this Copyright, but you must use a GPLv3 compatible
# license if you redistribute this with your modifications.


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

"""Module stub"""

from include.utils import Module
import logging as log
import re
#from include.useragent import geturl   # mimic browser
#from include.utils import stripHTML    # strip HTML/unescape entities

__version__ = '0.1'
__author__ = ''
__all__ = []

class Main(Module):
    pattern = None
    # example regexes
    #pattern = re.compile(r'^\s*trigger\s*$, re.I)               # no params
    #pattern = re.compile(r'^\s*trigger\s+(\S+)\s*', re.I)       # with params
    #pattern = re.compile(r'^\s*trigger(?:\s+(.+?))?\s*$', re.I) # opt params
    #pattern = Module._any      # this will match anything (read NOTE below!)

    # DEFAULTS
    #enabled = True             # this can be set to false to disable addon
    #require_addressing = True  # whether you need to address bot directly
    #help = None                # one-line help string for this module
    #priority = 50              # what order to run in (lower=first)
    #terminate = True           # whether to stop if this modules matches
    #allow_threading = True     # whether to launch a thread for this module
    #error = None               # error that's returned to user, if any

    # NOTE: if you use Module._any, you should NOT terminate, or set this
    # as a high enough priority to be called after other modules. currently
    # most modules are priority 50, and grufti/factoids is 100.
    #
    # you may also set it to terminate and change this after the fact
    # by updating the kwargs['req'].matched object to False, based on logic
    # in the module code. WARNING -- IF YOU DO THIS, you MUST disable
    # threading (allow_threading=False)!!! Otherwise it will
    # already have terminated before you get a chance to update the request
    # object, and also introduce many thread safety issues.
    #
    # if this doesn't make sense, take a look at some of the existing modules
    # which match anything (i.e. are ALWAYS called no matter what a user types)
    # such as: delicious, factoids, grufti, karma, memebot, seen

    def __init__(self, madcow=None):
        self.madcow = madcow # this gives user access to the internal bot

    def response(self, nick, args, kwargs):
        # this function should return a response or None
        # - args is a list that matches the matched parts of the pattern
        # - kwargs give you access to the details of the request from the bot

        try:
            return 'not impemented'
        except Exception as e:
            log.warn('error in %s: %s' % (self.__module__, e))
            log.exception(e)
            return '%s: %s' % (nick, self.error)


if __name__ == '__main__':
    from include.utils import test_module
    test_module(Main)
