#!/usr/bin/env python
#
# Copyright (C) 2007, 2008 Christopher Jones And Bryan Burns
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
#  jinx.py
#  madcow
#  
#  Created by Bryan Burns on 2007-07-17.
# 

# Handle coke allocation

import re
import time
from include.utils import Module
import logging as log

class ChatLine:
  """Records a single line of IRC chat"""
  def __init__(self, nick, text):
    self.nick = nick
    self.text = text
    self.timestamp = time.time()
  
  def __str__(self):
    return "%s: <%s> %s\n" % (str(self.timestamp), self.nick, self.text)

class ChatLog:
  """Holds chat lines for a preconfigured duration of time"""
  def __init__(self, timeout=5):
    self.timeout = timeout
    self.lines = []
  
  def cull(self):
    """removes any lines that are beyond the timeout."""
    now = time.time()
    self.lines = [line for line in self.lines if line.timestamp + self.timeout > now]
  
  def getMatchingLine(self, line):
    """If a line exists in the log that matches the line passed in, returns that line object, 
    otherwise returns None.  A line 'matches' if the text is the same, case insensitive and
    ignoring whitespace."""
    tokens = list(map(str.lower, line.text.split())) # easy way to ignore case and whitespace
    for l in self.lines:
      if list(map(str.lower, l.text.split())) == tokens:
        return l # found a match
    
    return None # no matches found
  
  def add(self, line):
    """adds a line to the log and culls any stale lines."""
    self.cull()
    self.lines.append(line)
  
  def __str__(self):
    s = ""
    for line in self.lines: 
      s += str(line)
    return s

# class for this module
class Main(Module):
  priority = 0
  terminate = False
  allow_threading = False
  def __init__(self, madcow=None):
    self.enabled = True       # True/False - enabled?
    self.pattern = Module._any
    self.require_addressing = False     # True/False - require addressing?
    
    self.log = ChatLog()
    
  # function to generate a response
  def response(self, nick, args, kwargs):
    try:
      line = args[0]
      
      cl = ChatLine(nick, line)
      self.log.add(cl)
      
      oldline = self.log.getMatchingLine(cl)
      if oldline and oldline.nick != nick:
        return "Jinx! %s owes %s a coke!" % (nick, oldline.nick)
    except Exception as e:
      log.warn('error in %s: %s' % (self.__module__, e))
      log.exception(e)
