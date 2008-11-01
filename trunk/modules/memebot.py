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

"""Watch URLs in channel, punish people for living under a rock"""

import re
import os
import urlparse
import datetime
from sqlobject import *
import random
from include.throttle import Throttle
from include.utils import Module
import logging as log

try:
    class url(SQLObject):
        url = StringCol()
        clean = StringCol()
        author = ForeignKey('author')
        channel = ForeignKey('channel')
        citations = IntCol(default=0)
        posted = DateTimeCol(default = datetime.datetime.now)
        comments = MultipleJoin('comments')

        def truncated_url(self):
            if (len(self.url) > 48):
                return self.url[:48] + ' ... ' + self.url[-4:]
            else:
                return self.url

        turl = property(truncated_url)


    class author(SQLObject):
        name = StringCol(alternateID=True, length=50)
        urls = MultipleJoin('url')
        comments = MultipleJoin('comments')
        pointsNew = IntCol(default=0)
        pointsOld = IntCol(default=0)
        pointsCredit = IntCol(default=0)


    class channel(SQLObject):
        name = StringCol(alternateID=True, length=50)
        urls = MultipleJoin('url')


    class comments(SQLObject):
        text = StringCol()
        author = ForeignKey('author')
        url = ForeignKey('url')
except:
    pass


class Main(Module):
    pattern = Module._any
    allow_threading = False
    priority = 10
    terminate = False
    require_addressing = False
    help = 'score [name,range] - get memescore, empty for top10'
    matchURL = re.compile('(http://\S+)', re.I)
    scoreRequest = re.compile(r'^\s*score(?:(?:\s+|[:-]+\s*)(\S+?)(?:\s*-\s*(\S+))?)?\s*$', re.I)
    colonHeader = re.compile(r'^\s*(.*?)\s*:\s*$')
    riffs = [
        'OLD MEME ALERT!',
        'omg, SO OLD!',
        'Welcome to yesterday.',
        'been there, done that.',
        'you missed the mememobile.',
        'oldest. meme. EVAR.',
        'jesus christ you suck.',
        'you need a new memesource, bucko.',
        'that was funny the first time i saw it.',
        'new to the internet?',
        'i think that came installed with the internet',
    ]
    get_frag = re.compile(r'^(.*)#([^;/?:@=&]*)$')

    def __init__(self, madcow):
        self.throttle = Throttle()
        config = madcow.config.memebot
        engine = config.db_engine
        uri = engine + '://'
        if engine == 'sqlite':
            uri += os.path.join(madcow.prefix,
                    'data/db-%s-memes' % madcow.namespace)
        elif engine == 'mysql':
            user = config.db_user
            if len(config.db_pass):
                user += ':' + config.db_pass
            host = config.db_host
            if not len(host):
                host = 'localhost'
            if len(config.db_port):
                host += ':' + config.db_port
            uri += '%s@%s/%s' % (user, host, config.db_name)
        try:
            sqlhub.processConnection = connectionForURI(uri)
        except Exception, error:
            log.warn('invalid uri: %s (%s)' % (uri, error))
            self.enabled = False
            return

        # show raw SQL being dispatched if loglevel is debug
        if log.root.level <= log.DEBUG:
            url._connection.debug = True
            author._connection.debug = True
            channel._connection.debug = True
            comments._connection.debug = True

        url.createTable(ifNotExists=True)
        author.createTable(ifNotExists=True)
        channel.createTable(ifNotExists=True)
        comments.createTable(ifNotExists=True)

    def cleanURL(self, url):
        # stolen from urlparse.urlsplit(), which doesn't handle
        # splitting frags correctly
        netloc = query = fragment = ''
        i = url.find(':')
        scheme = url[:i].lower()
        url = url[i+1:]
        if url[:2] == '//':
            delim = len(url)
            for c in '/?#':
                wdelim = url.find(c, 2)
                if wdelim >= 0:
                    delim = min(delim, wdelim)
            netloc, url = url[2:delim], url[delim:]
        if '#' in url:
            try:
                url, fragment = self.get_frag.search(url).groups()
            except:
                pass
        if '?' in url:
            url, query = url.split('?', 1)

        ### now for memebots normalizing..
        # make hostname lowercase and remove www
        netloc = netloc.lower()
        if netloc.startswith('www.') and len(netloc) > 4:
            netloc = netloc[4:]
        # all urls have trailing slash
        if url == '':
            url = '/'
        # remove empty query settings, these are usually form artifacts
        # and put them in order
        try:
            query = '&'.join(sorted(
                    '='.join(i)
                    for i in [p.split('=', 1) for p in query.split('&')]
                    if len(i) == 2 and i[1]))
        except:
            query = ''

        # ignore fragments
        fragment = ''

        return urlparse.urlunsplit([scheme, netloc, url, query, fragment])

    def getScoreForAuthor(self, a):
        return a.pointsNew + (a.pointsOld  * -2) + (a.pointsCredit * 2)

    def getScores(self):
        scores = [(a.name, self.getScoreForAuthor(a)) for a in author.select()]
        scores = sorted(scores, lambda x, y: cmp(y[1], x[1]))
        return scores

    def response(self, nick, args, kwargs):
        nick = nick.lower()
        chan = kwargs['channel'].lower()
        addressed = kwargs['addressed']
        message = args[0]

        if addressed:
            try:
                x, y = self.scoreRequest.search(message).groups()
                scores = self.getScores()
                size = len(scores)

                if x is None:
                    scores = scores[:10]
                    x = 1
                elif x.isdigit():
                    x = int(x)
                    if x == 0:
                        x = 1
                    if x > size:
                        x = size

                    if y is not None and y.isdigit():
                        y = int(y)
                        if y > size:
                            y = size
                        scores = scores[x-1:y]
                    else:
                        scores = [scores[x-1]]

                else:
                    for i, data in enumerate(scores):
                        name, score = data
                        if name.lower() == x.lower():
                            scores = [scores[i]]
                            x = i+1
                            break

                out = []
                for i, data in enumerate(scores):
                    name, score = data
                    out.append('#%s: %s (%s)' % (i + x, name, score))
                return ', '.join(out)
                
            except:
                pass

        match = self.matchURL.search(message)
        if match is None:
            return

        event = self.throttle.registerEvent(name='memebot', user=nick)
        if event.isThrottled():
            if event.warn():
                return '%s: Stop abusing me plz.' % nick
            else:
                return

        orig = match.group(1)
        clean = self.cleanURL(orig)

        comment1, comment2 = re.split(re.escape(orig), message)
        try:
            comment1 = self.colonHeader.search(comment1).group(1)
        except:
            pass

        comment1 = comment1.strip()
        comment2 = comment2.strip()

        try:
            me = author.byName(nick)
        except SQLObjectNotFound:
            me = author(name=nick)

        try:
            # old meme
            try:
                old = url.select(url.q.clean == clean)[0]
            except:
                raise SQLObjectNotFound

            if len(comment1) > 0:
                comments(url=old, text=comment1, author=me)
            if len(comment2) > 0:
                comments(url=old, text=comment2, author=me)

            # chew them out unless its my own
            if old.author.name.lower() != nick.lower():
                response = 'first posted by %s on %s' % (old.author.name,
                        old.posted)
                riff = random.choice(self.riffs)
                old.author.pointsCredit = old.author.pointsCredit + 1
                me.pointsOld = me.pointsOld + 1
                old.citations = old.citations + 1
                return '%s %s' % (riff, response)


        except SQLObjectNotFound:
            try:
                c = channel.byName(chan)
            except SQLObjectNotFound:
                c = channel(name=chan)

            urlid = url(url=orig, clean=clean, author=me, channel=c)

            if len(comment1) > 0:
                comments(url=urlid, text=comment1, author=me)
            if len(comment2) > 0:
                comments(url=urlid, text=comment2, author=me)

            me.pointsNew = me.pointsNew + 1

        except Exception, error:
            log.warn('error in %s: %s' % (self.__module__, error))
            log.exception(error)
