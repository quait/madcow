#!/usr/bin/env python

# JESUS!

import sys
import re
import urllib
from include import utils

# class for this module
class match(object):
	def __init__(self, config=None, ns='default', dir=None):
		self.enabled = True				# True/False - enabled?
		self.pattern = re.compile('bible\s+(\S+\s+\d+:[0-9-]+)')
		self.requireAddressing = True			# True/False - require addressing?
		self.thread = True				# True/False - should bot spawn thread?
		self.wrap = True				# True/False - wrap output?
		self.help = 'bible <book> <chp>:<verse>[-<verse>] - spam jesus stuff'

		self.baseURL = 'http://www.biblegateway.com/passage/'
		self.verse = re.compile('<div class="result-text-style-normal">(.*?)</div>', re.DOTALL)
		self.footnotes = re.compile('<strong>Footnotes:</strong>.*$', re.DOTALL)
		self.junkHTML = re.compile(r'<(h4|h5|span|sup|strong|ol|a).*?</\1>', re.I)
		self.max = 800

	# function to generate a response
	def response(self, *args, **kwargs):
		nick = kwargs['nick']
		args = kwargs['args']

		try:
			url = self.baseURL + '?' + urllib.urlencode(
					{	'search'	: args[0],
						'version'	: 31,	}
					)
			doc = urllib.urlopen(url).read()

			response = self.verse.search(doc).group(1)
			response = self.footnotes.sub('', response)
			response = self.junkHTML.sub('', response)
			response = utils.stripHTML(response)
			response = response.strip()

			return response[:self.max]
		except Exception, e:
			print >> sys.stderr, 'error in %s: %s' % (self.__module__, e)
			return "%s: God didn't like that." % nick


# this is just here so we can test the module from the commandline
def main(argv = None):
	if argv is None: argv = sys.argv[1:]
	obj = match()
	print obj.response(nick='testUser', args=argv)

	return 0

if __name__ == '__main__': sys.exit(main())