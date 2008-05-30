#!/usr/bin/env python

"""
$Id: weather.py,v 1.1.1.1 2007/06/25 23:09:20 cjones Exp $

Get a weather report from wunderground
"""

import sys
import re
import urllib
import learn

# class for this module
class match(object):
	def __init__(self):
		self.enabled = True				# True/False - enabled?
		self.pattern = re.compile('^(?:fc|forecast|weather)(?:\s+(.*)$)?')
		self.requireAddressing = True			# True/False - require addressing?
		self.thread = True				# True/False - should bot spawn thread?
		self.wrap = False				# True/False - wrap output?
		self.help = 'fc <location> - look up forecast for location'
		self.help = self.help + '\nfc @nick - lookup forecast for this nick\'s location'
		self.help = self.help + '\nlearn <nick> <location> - permanently learn a nick\'s location'

		self.lookup = re.compile('^@(\S+)')
		self.resultType = re.compile('(Search Results|Current Conditions|There has been an error)')
		self.multipleResults = re.compile('<td class="sortC"><a href="([^>]+)">([^<]+)')
		self.baseURL = 'http://www.wunderground.com'

		self.tempF = re.compile('<nobr><b>([0-9.]+)</b>&nbsp;&#176;F</nobr>')
		self.tempC = re.compile('<nobr><b>([0-9.]+)</b>&nbsp;&#176;C</nobr>')
		self.skies = re.compile('<div id="b" style="font-size: 14px;">(.*?)</div>')
		self.cityName = re.compile('<h1>(.*?)</h1>')
		self.humidity = re.compile('pwsvariable="humidity".*?><nobr><b>([0-9.]+%)</b></nobr></span></td>')
  		self.windSpeed = re.compile('<nobr><b>([0-9.]+)</b>&nbsp;mph</nobr>')
  		self.windDir = re.compile('[0-9.]+&deg;</span>\s*\(([NSEW]+)\)</td>')

	# function to generate a response
	def response(self, nick, args):
		try:
			if args[0] is None:
				query = learn.match().lookup(nick)
				if not query:
					return '%s: Teach me where you live: learn <nick> <location>' % nick
			else:
				query = ' '.join(args)
				try: lookup = self.lookup.search(query).group(1)
				except: lookup = None

				if lookup:
					query = learn.match().lookup(lookup)
					if not query:
						return '%s: I have no idea where %s lives, try: learn <nick> <location>' % (nick, lookup)


			response = None

			queryString = urllib.urlencode( { 'query' : query } )
			url = '%s/cgi-bin/findweather/getForecast?%s' % (self.baseURL, queryString)

			while True:
				doc = urllib.urlopen(url).read()
				mo = self.resultType.search(doc)
				if mo: type = mo.group(1)
				else: type = 'There has been an error'

				# found multiple items
				if type == 'Search Results':
					results = [(path, city) for path, city in self.multipleResults.findall(doc)]
					if len(results) == 1:
						url = self.basURL + results[0][0]
					elif len(results) > 1:
						response = 'I found multiple results: ' + '; '.join([city for path, city in results])

				# proper page
				elif type == 'Current Conditions':
					try: cityName = self.cityName.search(doc).group(1).strip()
					except: cityName = query

					try: tempF = str(int(round(float(self.tempF.search(doc).group(1))))) + 'F'
					except: tempF = None

					try: tempC = str(int(round(float(self.tempC.search(doc).group(1))))) + 'C'
					except: tempC = None

					try: skies = self.skies.search(doc).group(1)
					except: skies = None

					try: humidity = self.humidity.search(doc).group(1)
					except: humidity = None

					try: windSpeed = self.windSpeed.search(doc).group(1) + 'mph'
					except: windSpeed = None

					try: windDir = self.windDir.search(doc).group(1)
					except: windDir = None

					output = []

					if tempF or tempC:
						temps = []
						if tempF: temps.append(tempF)
						if tempC: temps.append(tempC)
						output.append('/'.join(temps))

					if humidity:
						output.append('humidity: %s' % humidity)

					if windSpeed and windDir:
						output.append('%s at %s' % (windDir, windSpeed))

					if skies:
						output.append(skies)

					response = '%s: %s' % (cityName, ', '.join(output))

				# nothing found
				elif type == 'There has been an error':
					response = "I couldn't find %s" % query

				if response: break
			
			return '%s: %s' % (nick, response)
		except Exception, e:
			print >> sys.stderr, 'error in %s: %s' % (self.__module__, e)
			return '%s: There is no weather there' % nick


# this is just here so we can test the module from the commandline
def main(argv = None):
	if argv is None: argv = sys.argv[1:]
	obj = match()
	print obj.response('testUser', argv)

	return 0

if __name__ == '__main__': sys.exit(main())