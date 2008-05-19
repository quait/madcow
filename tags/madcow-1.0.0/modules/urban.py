#!/usr/bin/env python

"""
$Id: urban.py,v 1.1.1.1 2007/06/25 23:09:20 cjones Exp $

Look up a definition in the Urban Dictionary
"""

import sys
import re
import SOAPpy

# class for this module
class match(object):
	def __init__(self):
		self.enabled = True				# True/False - enabled?
		self.pattern = re.compile('urban\s+(.+)')	# regular expression that needs to be matched
		self.requireAddressing = True			# True/False - require addressing?
		self.thread = True				# True/False - should bot spawn thread?
		self.wrap = True				# True/False - wrap output?
		self.help = 'urban <phrase> - look up a word/phrase on urban dictionary'

		self.key = 'a979884b386f8b7ea781754892f08d12'
		self.server = SOAPpy.SOAPProxy("http://api.urbandictionary.com/soap")

	# function to generate a response
	def response(self, nick, args):
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
				return "%s: So obscure even urban dictionary doesn't know what it means" % nick

			if i > max:
				return '%s: CRITICAL BUFFER OVERFLOW ERROR' % nick

			item = items[i - 1]
			response = '%s: [%s/%s] %s - Example: %s' % (nick, i, max, item.definition, item.example)
			return response.encode("utf-8")
		except Exception, e:
			print >> sys.stderr, 'error in %s: %s' % (self.__module__, e)
			return "%s: Serious problems: %s" % (nick, e)


# this is just here so we can test the module from the commandline
def main(argv = None):
	if argv is None: argv = sys.argv[1:]
	obj = match()
	print obj.response('testUser', argv)

	return 0

if __name__ == '__main__': sys.exit(main())