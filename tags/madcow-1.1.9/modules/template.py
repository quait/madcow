#!/usr/bin/env python

"""Module stub"""

from include.utils import Module
import sys
import re
#from include.useragent import geturl   # mimic browser
#from include.utils import stripHTML    # strip HTML/unescape entities

__version__ = '0.1'
__author__ = ''
__license__ = 'GPL'
__copyright__ = 'Copyright (C) 2008'
__all__ = []

class Main(Module):
    pattern = re.compile(r'^\s*keyword\s+(\S+)\s*', re.I)
    #pattern = Module._any      # this will match anything (read NOTE below!)

    # DEFAULTS
    #enabled = True             # this can be set to false to disable addon
    #require_addressing = True  # whether you need to address bot directly
    #help = None                # one-line help string for this module
    #priority = 50              # what order to run in (lower=first)
    #terminate = True           # whether to stop if this modules matches
    #allow_threading = True     # whether to launch a thread for this module

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

    def response(self, nick, args, **kwargs):
        # this function should return a response or None
        # - args is a list that matches the matched parts of the pattern
        # - kwargs give you access to the details of the request from the bot

        try:
            return 'not impemented'
        except Exception, e:
            print >> sys.stderr, 'error in %s: %s' % (self.__module__, e)
            # return a friendlier error message
            return '%s: problem with query: %s' % (nick, e)


def main():
    try:
        main = Main()
        args = main.pattern.search(' '.join(sys.argv[1:])).groups()
        print main.response(nick=os.environ['USER'], args=args)
    except Exception, e:
        print 'no match: %s' % e

if __name__ == '__main__':
    import os
    sys.exit(main())