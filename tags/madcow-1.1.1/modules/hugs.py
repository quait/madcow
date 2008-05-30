#!/usr/bin/env python

"""
Get a random confession from grouphug.us
"""

import sys
import re
import urllib
from include import utils
import os


class MatchObject(object):

    def __init__(self, config=None, ns='madcow', dir=None):
        self.enabled = True
        self.pattern = re.compile('^\s*hugs(?:\s+(\d+))?')
        self.requireAddressing = True
        self.thread = True
        self.wrap = True
        self.help = 'hugs - random confession'

        self.confs = re.compile('<p>(.*?)</p>', re.I + re.DOTALL)

    def response(self, **kwargs):
        nick = kwargs['nick']
        args = kwargs['args']

        try:
            if args[0] is not None:
                url = 'http://grouphug.us/confessions/' + args[0]
            else:
                url = 'http://grouphug.us/random'

            doc = urllib.urlopen(url).read()

            conf = self.confs.findall(doc)[0]
            conf = utils.stripHTML(conf)
            conf = conf.strip()

            return conf

        except Exception, e:
            print >> sys.stderr, 'error in %s: %s' % (self.__module__, e)
            return '%s: I had some issues with that..' % nick


if __name__ == '__main__':
    print MatchObject().response(nick=os.environ['USER'], args=[' '.join(sys.argv[1:])])
    sys.exit(0)