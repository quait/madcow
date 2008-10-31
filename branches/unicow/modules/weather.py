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

"""Get weather report"""

import re
from include.utils import stripHTML, Module
from include.useragent import geturl
from urlparse import urljoin
from include.BeautifulSoup import BeautifulSoup
from include import feedparser
from learn import Main as Learn
import logging as log
from include.colorlib import ColorLib
from include import encoding

__version__ = '0.2'
__author__ = 'cj_ <cjones@gruntle.org>'
__all__ = ['Weather', 'Main']

USAGE = 'set location <nick> <location>'

class Weather(object):

    baseurl = 'http://www.wunderground.com/'
    search = urljoin(baseurl, '/cgi-bin/findweather/getForecast')
    _rss_link = {'type': 'application/rss+xml'}
    _tempF = re.compile('(-?[0-9.]+)\s*\xb0\s*F', re.I)
    _bar = re.compile(r'\s*\|\s*')
    _keyval = re.compile(r'^\s*(.*?)\s*:\s*(.*?)\s*$')

    def __init__(self, colorlib):
        self.colorlib = colorlib

    def forecast(self, location):
        page = geturl(url=self.search, opts={'query': location},
                      referer=self.baseurl)
        soup = BeautifulSoup(page)

        # disambiguation page
        if 'Search Results' in unicode(soup):
            table = soup.find('table', attrs={'class': 'dataTable'})
            tbody = soup.find('tbody')
            results = [row.findAll('td')[0].find('a')
                       for row in tbody.findAll('tr')]
            results = [(normalize(unicode(result.contents[0])),
                        urljoin(Weather.baseurl, unicode(result['href'])))
                       for result in results]

            match = None
            for result in results:
                if result[0] == normalize(location):
                    match = result[1]
                    break
            if match is None:
                match = results[0][1]
            page = geturl(url=match, referer=self.search)
            soup = BeautifulSoup(page)

        title = soup.find('h1').string.strip()
        rss_url = soup.find('link', attrs=self._rss_link)['href']
        rss = feedparser.parse(rss_url)
        conditions = rss.entries[0].description

        # XXX ok, here's the deal. this page has raw utf-8 bytes encoded
        # as html entities, and in some cases latin1.  this demonstrates a
        # total misunderstanding of how unicode works on the part of the
        # authors, so we need to jump through some hoops to make it work
        conditions = conditions.encode('raw-unicode-escape')
        conditions = stripHTML(conditions)
        conditions = encoding.convert(conditions)
        fields = self._bar.split(conditions)
        data = {}
        for field in fields:
            try:
                key, val = self._keyval.search(field).groups()
                data[key] = val
            except:
                pass

        try:
            temp = float(self._tempF.search(data['Temperature']).group(1))
            blink = False
            if temp < 0:
                color = 'magenta'
            elif temp >=0 and temp < 40:
                color = 'blue'
            elif temp >= 40 and temp < 60:
                color = 'cyan'
            elif temp >= 60 and temp < 80:
                color = 'green'
            elif temp >= 80 and temp < 90:
                color = 'yellow'
            elif temp >= 90 and temp < 100:
                color = 'red'
            elif temp >= 100:
                color = 'red'
                blink = True
            data['Temperature'] = self.colorlib.get_color(color,
                    text=data['Temperature'])

            # XXX this seems ill-conceived
            if blink:
                data['Temperature'] = '\x1b[5m' + data['Temperature'] + \
                        '\x1b[0m'

        except:
            pass

        output = []
        for key, val in data.items():
            line = u'%s: %s' % (key, val)
            output.append(line)
        output = u' | '.join(output)
        return u'%s: %s' % (title, output)


class Main(Module):

    pattern = re.compile('^\s*(?:fc|forecast|weather)(?:\s+(.*)$)?')
    require_addressing = True
    help = 'fc [location] - look up weather forecast'

    def __init__(self, madcow=None):
        if madcow is not None:
            colorlib = madcow.colorlib
        else:
            colorlib = ColorLib('ansi')
        self.weather = Weather(colorlib)
        try:
            self.learn = Learn(madcow=madcow)
        except:
            self.learn = None

    def response(self, nick, args, kwargs):

        args = args[0] if args else None

        if not args and self.learn:
            query = self.learn.lookup('location', nick)
        elif args.startswith('@') and self.learn:
            query = self.learn.lookup('location', args[1:])
        else:
            query = args

        if not query:
            return u'%s: unknown nick. %s' % (nick, USAGE)

        try:
            return u'%s: %s' % (nick, self.weather.forecast(query))
        except Exception, error:
            log.warn('error in module %s' % self.__module__)
            log.exception(error)
            return u"Couldn't find that place, maybe a bomb dropped on it"


whitespace = re.compile(r'\s+')
year = re.compile(r'\(\d{4}\)\s*$')
badchars = re.compile(r'[^a-z0-9 ]', re.I)

def normalize(name):
    """Normalize city name for easy comparison"""
    name = stripHTML(name)
    name = year.sub('', name)
    name = badchars.sub(' ', name)
    name = name.lower()
    name = name.strip()
    name = whitespace.sub(' ', name)
    return name

if __name__ == '__main__':
    from include.utils import test_module
    test_module(Main)
