# Copyright (C) 2007, 2008 Christopher Jones and Bryan Burns
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
#
#  tweetprinter.py
#  madcow
#  
#  Created by toast on 2008-04-21.
# 
# Periodically checks for fresh 'tweets' from friends and prints them to the channel
#

"""Prints tweets to the channel."""

from include.utils import stripHTML
from include import twitter
import time
import logging as log

class Main:

  def __init__(self, madcow):
    self.madcow = madcow
    self.enabled = madcow.config.twitter.enabled
    self.frequency = madcow.config.twitter.updatefreq
    self.output = madcow.config.twitter.channel
    self.api = twitter.Api()
    self.api.SetCache(None) # this fills up /tmp :(
    self.api.SetUserAgent('Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 6.0)')
    self.api.SetCredentials(self.madcow.config.twitter.username,
        self.madcow.config.twitter.password)
    self.__updatelast()
  
  def __updatelast(self):
    """Updates timestamp of last update."""
    self.lastupdate = time.gmtime()

  def __get_update_str(self):
    return time.strftime("%a, %d %b %Y %X GMT", self.lastupdate)

  def response(self, *args):
    """This is called by madcow, should return a string or None"""
    try:
      log.debug('getting tweets...')
      tweets = self.api.GetFriendsTimeline(since=self.__get_update_str())
    except Exception as e:
      try:
        if e.code == 304:
          log.debug('no new tweets')
          return
      except:
        pass
      log.warn('error in %s: %s' % (self.__module__, e))
      log.exception(e)
      return
    
    log.debug('found %s tweets, parsing')
    lines = []
    
    for t in reversed(tweets):
      if time.localtime(t.GetCreatedAtInSeconds()) < self.lastupdate: # twitter fails sometimes, so we do our own filter..
        print("ignoring old tweet with timestamp %s (TWITTER SUCKS)" % t.created_at)
        continue
      
      line = ">> tweet from %s: %s <<" % (t.user.screen_name, stripHTML(t.text))
      lines.append(line)
    
    self.__updatelast()
    
    if lines:
      return "\n".join(lines)
    else:
      return None