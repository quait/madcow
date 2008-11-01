#!/usr/bin/env python
"""Universal feed parser

Handles RSS 0.9x, RSS 1.0, RSS 2.0, CDF, Atom 0.3, and Atom 1.0 feeds

Visit http://feedparser.org/ for the latest version
Visit http://feedparser.org/docs/ for the latest documentation

Required: Python 2.1 or later
Recommended: Python 2.3 or later
Recommended: CJKCodecs and iconv_codec <http://cjkpython.i18n.org/>
"""

__version__ = u"4.1"# + u"$Revision: 1.92 $"[11:15] + u"-cvs"
__license__ = """Copyright (c) 2002-2006, Mark Pilgrim, All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice,
  this list of conditions and the following disclaimer.
* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS 'AS IS'
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE."""
__author__ = u"Mark Pilgrim <http://diveintomark.org/>"
__contributors__ = [u"Jason Diamond <http://injektilo.org/>",
                    u"John Beimler <http://john.beimler.org/>",
                    u"Fazal Majid <http://www.majid.info/mylos/weblog/>",
                    u"Aaron Swartz <http://aaronsw.com/>",
                    u"Kevin Marks <http://epeus.blogspot.com/>"]
_debug = 0

# HTTP u"User-Agent" header to send to servers when downloading feeds.
# If you are embedding feedparser in a larger application, you should
# change this to your application name and URL.
USER_AGENT = u"UniversalFeedParser/%s +http://feedparser.org/" % __version__

# HTTP u"Accept" header to send to servers when downloading feeds.  If you don't
# want to send an Accept header, set this to None.
ACCEPT_HEADER = u"application/atom+xml,application/rdf+xml,application/rss+xml,application/x-netcdf,application/xml;q=0.9,text/xml;q=0.2,*/*;q=0.1"

# List of preferred XML parsers, by SAX driver name.  These will be tried first,
# but if they're not installed, Python will keep searching through its own list
# of pre-installed parsers until it finds one that supports everything we need.
PREFERRED_XML_PARSERS = [u"drv_libxml2"]

# If you want feedparser to automatically run HTML markup through HTML Tidy, set
# this to 1.  Requires mxTidy <http://www.egenix.com/files/python/mxTidy.html>
# or utidylib <http://utidylib.berlios.de/>.
TIDY_MARKUP = 0

# List of Python interfaces for HTML Tidy, in order of preference.  Only useful
# if TIDY_MARKUP = 1
PREFERRED_TIDY_INTERFACES = [u"uTidy", u"mxTidy"]

# ---------- required modules (should come with any Python distribution) ----------
import sgmllib, re, sys, copy, urlparse, time, rfc822, types, cgi, urllib, urllib2
try:
    from cStringIO import StringIO as _StringIO
except:
    from StringIO import StringIO as _StringIO

# ---------- optional modules (feedparser will work without these, but with reduced functionality) ----------

# gzip is included with most Python distributions, but may not be available if you compiled your own
try:
    import gzip
except:
    gzip = None
try:
    import zlib
except:
    zlib = None

# If a real XML parser is available, feedparser will attempt to use it.  feedparser has
# been tested with the built-in SAX parser, PyXML, and libxml2.  On platforms where the
# Python distribution does not come with an XML parser (such as Mac OS X 10.2 and some
# versions of FreeBSD), feedparser will quietly fall back on regex-based parsing.
try:
    import xml.sax
    xml.sax.make_parser(PREFERRED_XML_PARSERS) # test for valid parsers
    from xml.sax.saxutils import escape as _xmlescape
    _XML_AVAILABLE = 1
except:
    _XML_AVAILABLE = 0
    def _xmlescape(data):
        data = data.replace(u'&', u'&amp;')
        data = data.replace(u'>', u'&gt;')
        data = data.replace(u'<', u'&lt;')
        return data

# base64 support for Atom feeds that contain embedded binary data
try:
    import base64, binascii
except:
    base64 = binascii = None

# cjkcodecs and iconv_codec provide support for more character encodings.
# Both are available from http://cjkpython.i18n.org/
try:
    import cjkcodecs.aliases
except:
    pass
try:
    import iconv_codec
except:
    pass

# chardet library auto-detects character encodings
# Download from http://chardet.feedparser.org/
try:
    import chardet
    if _debug:
        import chardet.constants
        chardet.constants._debug = 1
except:
    chardet = None

# ---------- don't touch these ----------
class ThingsNobodyCaresAboutButMe(Exception): pass
class CharacterEncodingOverride(ThingsNobodyCaresAboutButMe): pass
class CharacterEncodingUnknown(ThingsNobodyCaresAboutButMe): pass
class NonXMLContentType(ThingsNobodyCaresAboutButMe): pass
class UndeclaredNamespace(Exception): pass

sgmllib.tagfind = re.compile(u'[a-zA-Z][-_.:a-zA-Z0-9]*')
sgmllib.special = re.compile(u'<!')
sgmllib.charref = re.compile(u'&#(x?[0-9A-Fa-f]+)[^0-9A-Fa-f]')

SUPPORTED_VERSIONS = {u'': u'unknown',
                      u'rss090': u'RSS 0.90',
                      u'rss091n': u'RSS 0.91 (Netscape)',
                      u'rss091u': u'RSS 0.91 (Userland)',
                      u'rss092': u'RSS 0.92',
                      u'rss093': u'RSS 0.93',
                      u'rss094': u'RSS 0.94',
                      u'rss20': u'RSS 2.0',
                      u'rss10': u'RSS 1.0',
                      u'rss': u'RSS (unknown version)',
                      u'atom01': u'Atom 0.1',
                      u'atom02': u'Atom 0.2',
                      u'atom03': u'Atom 0.3',
                      u'atom10': u'Atom 1.0',
                      u'atom': u'Atom (unknown version)',
                      u'cdf': u'CDF',
                      u'hotrss': u'Hot RSS'
                      }

try:
    UserDict = dict
except NameError:
    # Python 2.1 does not have dict
    from UserDict import UserDict
    def dict(aList):
        rc = {}
        for k, v in aList:
            rc[k] = v
        return rc

class FeedParserDict(UserDict):
    keymap = {u'channel': u'feed',
              u'items': u'entries',
              u'guid': u'id',
              u'date': u'updated',
              u'date_parsed': u'updated_parsed',
              u'description': [u'subtitle', u'summary'],
              u'url': [u'href'],
              u'modified': u'updated',
              u'modified_parsed': u'updated_parsed',
              u'issued': u'published',
              u'issued_parsed': u'published_parsed',
              u'copyright': u'rights',
              u'copyright_detail': u'rights_detail',
              u'tagline': u'subtitle',
              u'tagline_detail': u'subtitle_detail'}
    def __getitem__(self, key):
        if key == u'category':
            return UserDict.__getitem__(self, u'tags')[0][u'term']
        if key == u'categories':
            return [(tag[u'scheme'], tag[u'term']) for tag in UserDict.__getitem__(self, u'tags')]
        realkey = self.keymap.get(key, key)
        if type(realkey) == types.ListType:
            for k in realkey:
                if UserDict.has_key(self, k):
                    return UserDict.__getitem__(self, k)
        if UserDict.has_key(self, key):
            return UserDict.__getitem__(self, key)
        return UserDict.__getitem__(self, realkey)

    def __setitem__(self, key, value):
        for k in self.keymap.keys():
            if key == k:
                key = self.keymap[k]
                if type(key) == types.ListType:
                    key = key[0]
        return UserDict.__setitem__(self, key, value)

    def get(self, key, default=None):
        if self.has_key(key):
            return self[key]
        else:
            return default

    def setdefault(self, key, value):
        if not self.has_key(key):
            self[key] = value
        return self[key]

    def has_key(self, key):
        try:
            return hasattr(self, key) or UserDict.has_key(self, key)
        except AttributeError:
            return False

    def __getattr__(self, key):
        try:
            return self.__dict__[key]
        except KeyError:
            pass
        try:
            assert not key.startswith(u'_')
            return self.__getitem__(key)
        except:
            raise AttributeError, u"object has no attribute '%s'" % key

    def __setattr__(self, key, value):
        if key.startswith(u'_') or key == u'data':
            self.__dict__[key] = value
        else:
            return self.__setitem__(key, value)

    def __contains__(self, key):
        return self.has_key(key)

def zopeCompatibilityHack():
    global FeedParserDict
    del FeedParserDict
    def FeedParserDict(aDict=None):
        rc = {}
        if aDict:
            rc.update(aDict)
        return rc

_ebcdic_to_ascii_map = None
def _ebcdic_to_ascii(s):
    global _ebcdic_to_ascii_map
    if not _ebcdic_to_ascii_map:
        emap = (
            0,1,2,3,156,9,134,127,151,141,142,11,12,13,14,15,
            16,17,18,19,157,133,8,135,24,25,146,143,28,29,30,31,
            128,129,130,131,132,10,23,27,136,137,138,139,140,5,6,7,
            144,145,22,147,148,149,150,4,152,153,154,155,20,21,158,26,
            32,160,161,162,163,164,165,166,167,168,91,46,60,40,43,33,
            38,169,170,171,172,173,174,175,176,177,93,36,42,41,59,94,
            45,47,178,179,180,181,182,183,184,185,124,44,37,95,62,63,
            186,187,188,189,190,191,192,193,194,96,58,35,64,39,61,34,
            195,97,98,99,100,101,102,103,104,105,196,197,198,199,200,201,
            202,106,107,108,109,110,111,112,113,114,203,204,205,206,207,208,
            209,126,115,116,117,118,119,120,121,122,210,211,212,213,214,215,
            216,217,218,219,220,221,222,223,224,225,226,227,228,229,230,231,
            123,65,66,67,68,69,70,71,72,73,232,233,234,235,236,237,
            125,74,75,76,77,78,79,80,81,82,238,239,240,241,242,243,
            92,159,83,84,85,86,87,88,89,90,244,245,246,247,248,249,
            48,49,50,51,52,53,54,55,56,57,250,251,252,253,254,255
            )
        import string
        _ebcdic_to_ascii_map = string.maketrans( \
            u''.join(map(chr, range(256))), u''.join(map(chr, emap)))
    return s.translate(_ebcdic_to_ascii_map)

_urifixer = re.compile(u'^([A-Za-z][A-Za-z0-9+-.]*://)(/*)(.*?)')
def _urljoin(base, uri):
    uri = _urifixer.sub(r'\1\3', uri)
    return urlparse.urljoin(base, uri)

class _FeedParserMixin:
    namespaces = {u'': u'',
                  u'http://backend.userland.com/rss': u'',
                  u'http://blogs.law.harvard.edu/tech/rss': u'',
                  u'http://purl.org/rss/1.0/': u'',
                  u'http://my.netscape.com/rdf/simple/0.9/': u'',
                  u'http://example.com/newformat#': u'',
                  u'http://example.com/necho': u'',
                  u'http://purl.org/echo/': u'',
                  u'uri/of/echo/namespace#': u'',
                  u'http://purl.org/pie/': u'',
                  u'http://purl.org/atom/ns#': u'',
                  u'http://www.w3.org/2005/Atom': u'',
                  u'http://purl.org/rss/1.0/modules/rss091#': u'',

                  u'http://webns.net/mvcb/':                               u'admin',
                  u'http://purl.org/rss/1.0/modules/aggregation/':         u'ag',
                  u'http://purl.org/rss/1.0/modules/annotate/':            u'annotate',
                  u'http://media.tangent.org/rss/1.0/':                    u'audio',
                  u'http://backend.userland.com/blogChannelModule':        u'blogChannel',
                  u'http://web.resource.org/cc/':                          u'cc',
                  u'http://backend.userland.com/creativeCommonsRssModule': u'creativeCommons',
                  u'http://purl.org/rss/1.0/modules/company':              u'co',
                  u'http://purl.org/rss/1.0/modules/content/':             u'content',
                  u'http://my.theinfo.org/changed/1.0/rss/':               u'cp',
                  u'http://purl.org/dc/elements/1.1/':                     u'dc',
                  u'http://purl.org/dc/terms/':                            u'dcterms',
                  u'http://purl.org/rss/1.0/modules/email/':               u'email',
                  u'http://purl.org/rss/1.0/modules/event/':               u'ev',
                  u'http://rssnamespace.org/feedburner/ext/1.0':           u'feedburner',
                  u'http://freshmeat.net/rss/fm/':                         u'fm',
                  u'http://xmlns.com/foaf/0.1/':                           u'foaf',
                  u'http://www.w3.org/2003/01/geo/wgs84_pos#':             u'geo',
                  u'http://postneo.com/icbm/':                             u'icbm',
                  u'http://purl.org/rss/1.0/modules/image/':               u'image',
                  u'http://www.itunes.com/DTDs/PodCast-1.0.dtd':           u'itunes',
                  u'http://example.com/DTDs/PodCast-1.0.dtd':              u'itunes',
                  u'http://purl.org/rss/1.0/modules/link/':                u'l',
                  u'http://search.yahoo.com/mrss':                         u'media',
                  u'http://madskills.com/public/xml/rss/module/pingback/': u'pingback',
                  u'http://prismstandard.org/namespaces/1.2/basic/':       u'prism',
                  u'http://www.w3.org/1999/02/22-rdf-syntax-ns#':          u'rdf',
                  u'http://www.w3.org/2000/01/rdf-schema#':                u'rdfs',
                  u'http://purl.org/rss/1.0/modules/reference/':           u'ref',
                  u'http://purl.org/rss/1.0/modules/richequiv/':           u'reqv',
                  u'http://purl.org/rss/1.0/modules/search/':              u'search',
                  u'http://purl.org/rss/1.0/modules/slash/':               u'slash',
                  u'http://schemas.xmlsoap.org/soap/envelope/':            u'soap',
                  u'http://purl.org/rss/1.0/modules/servicestatus/':       u'ss',
                  u'http://hacks.benhammersley.com/rss/streaming/':        u'str',
                  u'http://purl.org/rss/1.0/modules/subscription/':        u'sub',
                  u'http://purl.org/rss/1.0/modules/syndication/':         u'sy',
                  u'http://purl.org/rss/1.0/modules/taxonomy/':            u'taxo',
                  u'http://purl.org/rss/1.0/modules/threading/':           u'thr',
                  u'http://purl.org/rss/1.0/modules/textinput/':           u'ti',
                  u'http://madskills.com/public/xml/rss/module/trackback/':u'trackback',
                  u'http://wellformedweb.org/commentAPI/':                 u'wfw',
                  u'http://purl.org/rss/1.0/modules/wiki/':                u'wiki',
                  u'http://www.w3.org/1999/xhtml':                         u'xhtml',
                  u'http://www.w3.org/XML/1998/namespace':                 u'xml',
                  u'http://schemas.pocketsoap.com/rss/myDescModule/':      u'szf'
}
    _matchnamespaces = {}

    can_be_relative_uri = [u'link', u'id', u'wfw_comment', u'wfw_commentrss', u'docs', u'url', u'href', u'comments', u'license', u'icon', u'logo']
    can_contain_relative_uris = [u'content', u'title', u'summary', u'info', u'tagline', u'subtitle', u'copyright', u'rights', u'description']
    can_contain_dangerous_markup = [u'content', u'title', u'summary', u'info', u'tagline', u'subtitle', u'copyright', u'rights', u'description']
    html_types = [u'text/html', u'application/xhtml+xml']

    def __init__(self, baseuri=None, baselang=None, encoding=u'utf-8'):
        if _debug: sys.stderr.write(u'initializing FeedParser\n')
        if not self._matchnamespaces:
            for k, v in self.namespaces.items():
                self._matchnamespaces[k.lower()] = v
        self.feeddata = FeedParserDict() # feed-level data
        self.encoding = encoding # character encoding
        self.entries = [] # list of entry-level data
        self.version = u'' # feed type/version, see SUPPORTED_VERSIONS
        self.namespacesInUse = {} # dictionary of namespaces defined by the feed

        # the following are used internally to track state;
        # this is really out of control and should be refactored
        self.infeed = 0
        self.inentry = 0
        self.incontent = 0
        self.intextinput = 0
        self.inimage = 0
        self.inauthor = 0
        self.incontributor = 0
        self.inpublisher = 0
        self.insource = 0
        self.sourcedata = FeedParserDict()
        self.contentparams = FeedParserDict()
        self._summaryKey = None
        self.namespacemap = {}
        self.elementstack = []
        self.basestack = []
        self.langstack = []
        self.baseuri = baseuri or u''
        self.lang = baselang or None
        if baselang:
            self.feeddata[u'language'] = baselang

    def unknown_starttag(self, tag, attrs):
        if _debug: sys.stderr.write(u'start %s with %s\n' % (tag, attrs))
        # normalize attrs
        attrs = [(k.lower(), v) for k, v in attrs]
        attrs = [(k, k in (u'rel', u'type') and v.lower() or v) for k, v in attrs]

        # track xml:base and xml:lang
        attrsD = dict(attrs)
        baseuri = attrsD.get(u'xml:base', attrsD.get(u'base')) or self.baseuri
        self.baseuri = _urljoin(self.baseuri, baseuri)
        lang = attrsD.get(u'xml:lang', attrsD.get(u'lang'))
        if lang == u'':
            # xml:lang could be explicitly set to u'', we need to capture that
            lang = None
        elif lang is None:
            # if no xml:lang is specified, use parent lang
            lang = self.lang
        if lang:
            if tag in (u'feed', u'rss', u'rdf:RDF'):
                self.feeddata[u'language'] = lang
        self.lang = lang
        self.basestack.append(self.baseuri)
        self.langstack.append(lang)

        # track namespaces
        for prefix, uri in attrs:
            if prefix.startswith(u'xmlns:'):
                self.trackNamespace(prefix[6:], uri)
            elif prefix == u'xmlns':
                self.trackNamespace(None, uri)

        # track inline content
        if self.incontent and self.contentparams.has_key(u'type') and not self.contentparams.get(u'type', u'xml').endswith(u'xml'):
            # element declared itself as escaped markup, but it isn't really
            self.contentparams[u'type'] = u'application/xhtml+xml'
        if self.incontent and self.contentparams.get(u'type') == u'application/xhtml+xml':
            # Note: probably shouldn't simply recreate localname here, but
            # our namespace handling isn't actually 100% correct in cases where
            # the feed redefines the default namespace (which is actually
            # the usual case for inline content, thanks Sam), so here we
            # cheat and just reconstruct the element based on localname
            # because that compensates for the bugs in our namespace handling.
            # This will horribly munge inline content with non-empty qnames,
            # but nobody actually does that, so I'm not fixing it.
            tag = tag.split(u':')[-1]
            return self.handle_data(u'<%s%s>' % (tag, u''.join([u' %s="%s"' % t for t in attrs])), escape=0)

        # match namespaces
        if tag.find(u':') <> -1:
            prefix, suffix = tag.split(u':', 1)
        else:
            prefix, suffix = u'', tag
        prefix = self.namespacemap.get(prefix, prefix)
        if prefix:
            prefix = prefix + u'_'

        # special hack for better tracking of empty textinput/image elements in illformed feeds
        if (not prefix) and tag not in (u'title', u'link', u'description', u'name'):
            self.intextinput = 0
        if (not prefix) and tag not in (u'title', u'link', u'description', u'url', u'href', u'width', u'height'):
            self.inimage = 0

        # call special handler (if defined) or default handler
        methodname = u'_start_' + prefix + suffix
        try:
            method = getattr(self, methodname)
            return method(attrsD)
        except AttributeError:
            return self.push(prefix + suffix, 1)

    def unknown_endtag(self, tag):
        if _debug: sys.stderr.write(u'end %s\n' % tag)
        # match namespaces
        if tag.find(u':') <> -1:
            prefix, suffix = tag.split(u':', 1)
        else:
            prefix, suffix = u'', tag
        prefix = self.namespacemap.get(prefix, prefix)
        if prefix:
            prefix = prefix + u'_'

        # call special handler (if defined) or default handler
        methodname = u'_end_' + prefix + suffix
        try:
            method = getattr(self, methodname)
            method()
        except AttributeError:
            self.pop(prefix + suffix)

        # track inline content
        if self.incontent and self.contentparams.has_key(u'type') and not self.contentparams.get(u'type', u'xml').endswith(u'xml'):
            # element declared itself as escaped markup, but it isn't really
            self.contentparams[u'type'] = u'application/xhtml+xml'
        if self.incontent and self.contentparams.get(u'type') == u'application/xhtml+xml':
            tag = tag.split(u':')[-1]
            self.handle_data(u'</%s>' % tag, escape=0)

        # track xml:base and xml:lang going out of scope
        if self.basestack:
            self.basestack.pop()
            if self.basestack and self.basestack[-1]:
                self.baseuri = self.basestack[-1]
        if self.langstack:
            self.langstack.pop()
            if self.langstack: # and (self.langstack[-1] is not None):
                self.lang = self.langstack[-1]

    def handle_charref(self, ref):
        # called for each character reference, e.g. for u'&#160;', ref will be u'160'
        if not self.elementstack: return
        ref = ref.lower()
        if ref in (u'34', u'38', u'39', u'60', u'62', u'x22', u'x26', u'x27', u'x3c', u'x3e'):
            text = u'&#%s;' % ref
        else:
            if ref[0] == u'x':
                c = int(ref[1:], 16)
            else:
                c = int(ref)
            text = unichr(c).encode(u'utf-8')
        self.elementstack[-1][2].append(text)

    def handle_entityref(self, ref):
        # called for each entity reference, e.g. for u'&copy;', ref will be u'copy'
        if not self.elementstack: return
        if _debug: sys.stderr.write(u'entering handle_entityref with %s\n' % ref)
        if ref in (u'lt', u'gt', u'quot', u'amp', u'apos'):
            text = u'&%s;' % ref
        else:
            # entity resolution graciously donated by Aaron Swartz
            def name2cp(k):
                import htmlentitydefs
                if hasattr(htmlentitydefs, u'name2codepoint'): # requires Python 2.3
                    return htmlentitydefs.name2codepoint[k]
                k = htmlentitydefs.entitydefs[k]
                if k.startswith(u'&#') and k.endswith(u';'):
                    return int(k[2:-1]) # not in latin-1
                return ord(k)
            try: name2cp(ref)
            except KeyError: text = u'&%s;' % ref
            else: text = unichr(name2cp(ref)).encode(u'utf-8')
        self.elementstack[-1][2].append(text)

    def handle_data(self, text, escape=1):
        # called for each block of plain text, i.e. outside of any tag and
        # not containing any character or entity references
        if not self.elementstack: return
        if escape and self.contentparams.get(u'type') == u'application/xhtml+xml':
            text = _xmlescape(text)
        self.elementstack[-1][2].append(text)

    def handle_comment(self, text):
        # called for each comment, e.g. <!-- insert message here -->
        pass

    def handle_pi(self, text):
        # called for each processing instruction, e.g. <?instruction>
        pass

    def handle_decl(self, text):
        pass

    def parse_declaration(self, i):
        # override internal declaration handler to handle CDATA blocks
        if _debug: sys.stderr.write(u'entering parse_declaration\n')
        if self.rawdata[i:i+9] == u'<![CDATA[':
            k = self.rawdata.find(u']]>', i)
            if k == -1: k = len(self.rawdata)
            self.handle_data(_xmlescape(self.rawdata[i+9:k]), 0)
            return k+3
        else:
            k = self.rawdata.find(u'>', i)
            return k+1

    def mapContentType(self, contentType):
        contentType = contentType.lower()
        if contentType == u'text':
            contentType = u'text/plain'
        elif contentType == u'html':
            contentType = u'text/html'
        elif contentType == u'xhtml':
            contentType = u'application/xhtml+xml'
        return contentType

    def trackNamespace(self, prefix, uri):
        loweruri = uri.lower()
        if (prefix, loweruri) == (None, u'http://my.netscape.com/rdf/simple/0.9/') and not self.version:
            self.version = u'rss090'
        if loweruri == u'http://purl.org/rss/1.0/' and not self.version:
            self.version = u'rss10'
        if loweruri == u'http://www.w3.org/2005/atom' and not self.version:
            self.version = u'atom10'
        if loweruri.find(u'backend.userland.com/rss') <> -1:
            # match any backend.userland.com namespace
            uri = u'http://backend.userland.com/rss'
            loweruri = uri
        if self._matchnamespaces.has_key(loweruri):
            self.namespacemap[prefix] = self._matchnamespaces[loweruri]
            self.namespacesInUse[self._matchnamespaces[loweruri]] = uri
        else:
            self.namespacesInUse[prefix or u''] = uri

    def resolveURI(self, uri):
        return _urljoin(self.baseuri or u'', uri)

    def decodeEntities(self, element, data):
        return data

    def push(self, element, expectingText):
        self.elementstack.append([element, expectingText, []])

    def pop(self, element, stripWhitespace=1):
        if not self.elementstack: return
        if self.elementstack[-1][0] != element: return

        element, expectingText, pieces = self.elementstack.pop()
        output = u''.join(pieces)
        if stripWhitespace:
            output = output.strip()
        if not expectingText: return output

        # decode base64 content
        if base64 and self.contentparams.get(u'base64', 0):
            try:
                output = base64.decodestring(output)
            except binascii.Error:
                pass
            except binascii.Incomplete:
                pass

        # resolve relative URIs
        if (element in self.can_be_relative_uri) and output:
            output = self.resolveURI(output)

        # decode entities within embedded markup
        if not self.contentparams.get(u'base64', 0):
            output = self.decodeEntities(element, output)

        # remove temporary cruft from contentparams
        try:
            del self.contentparams[u'mode']
        except KeyError:
            pass
        try:
            del self.contentparams[u'base64']
        except KeyError:
            pass

        # resolve relative URIs within embedded markup
        if self.mapContentType(self.contentparams.get(u'type', u'text/html')) in self.html_types:
            if element in self.can_contain_relative_uris:
                output = _resolveRelativeURIs(output, self.baseuri, self.encoding)

        # sanitize embedded markup
        if self.mapContentType(self.contentparams.get(u'type', u'text/html')) in self.html_types:
            if element in self.can_contain_dangerous_markup:
                output = _sanitizeHTML(output, self.encoding)

        if self.encoding and type(output) != type(u''):
            try:
                output = unicode(output, self.encoding)
            except:
                pass

        # categories/tags/keywords/whatever are handled in _end_category
        if element == u'category':
            return output

        # store output in appropriate place(s)
        if self.inentry and not self.insource:
            if element == u'content':
                self.entries[-1].setdefault(element, [])
                contentparams = copy.deepcopy(self.contentparams)
                contentparams[u'value'] = output
                self.entries[-1][element].append(contentparams)
            elif element == u'link':
                self.entries[-1][element] = output
                if output:
                    self.entries[-1][u'links'][-1][u'href'] = output
            else:
                if element == u'description':
                    element = u'summary'
                self.entries[-1][element] = output
                if self.incontent:
                    contentparams = copy.deepcopy(self.contentparams)
                    contentparams[u'value'] = output
                    self.entries[-1][element + u'_detail'] = contentparams
        elif (self.infeed or self.insource) and (not self.intextinput) and (not self.inimage):
            context = self._getContext()
            if element == u'description':
                element = u'subtitle'
            context[element] = output
            if element == u'link':
                context[u'links'][-1][u'href'] = output
            elif self.incontent:
                contentparams = copy.deepcopy(self.contentparams)
                contentparams[u'value'] = output
                context[element + u'_detail'] = contentparams
        return output

    def pushContent(self, tag, attrsD, defaultContentType, expectingText):
        self.incontent += 1
        self.contentparams = FeedParserDict({
            u'type': self.mapContentType(attrsD.get(u'type', defaultContentType)),
            u'language': self.lang,
            u'base': self.baseuri})
        self.contentparams[u'base64'] = self._isBase64(attrsD, self.contentparams)
        self.push(tag, expectingText)

    def popContent(self, tag):
        value = self.pop(tag)
        self.incontent -= 1
        self.contentparams.clear()
        return value

    def _mapToStandardPrefix(self, name):
        colonpos = name.find(u':')
        if colonpos <> -1:
            prefix = name[:colonpos]
            suffix = name[colonpos+1:]
            prefix = self.namespacemap.get(prefix, prefix)
            name = prefix + u':' + suffix
        return name

    def _getAttribute(self, attrsD, name):
        return attrsD.get(self._mapToStandardPrefix(name))

    def _isBase64(self, attrsD, contentparams):
        if attrsD.get(u'mode', u'') == u'base64':
            return 1
        if self.contentparams[u'type'].startswith(u'text/'):
            return 0
        if self.contentparams[u'type'].endswith(u'+xml'):
            return 0
        if self.contentparams[u'type'].endswith(u'/xml'):
            return 0
        return 1

    def _itsAnHrefDamnIt(self, attrsD):
        href = attrsD.get(u'url', attrsD.get(u'uri', attrsD.get(u'href', None)))
        if href:
            try:
                del attrsD[u'url']
            except KeyError:
                pass
            try:
                del attrsD[u'uri']
            except KeyError:
                pass
            attrsD[u'href'] = href
        return attrsD

    def _save(self, key, value):
        context = self._getContext()
        context.setdefault(key, value)

    def _start_rss(self, attrsD):
        versionmap = {u'0.91': u'rss091u',
                      u'0.92': u'rss092',
                      u'0.93': u'rss093',
                      u'0.94': u'rss094'}
        if not self.version:
            attr_version = attrsD.get(u'version', u'')
            version = versionmap.get(attr_version)
            if version:
                self.version = version
            elif attr_version.startswith(u'2.'):
                self.version = u'rss20'
            else:
                self.version = u'rss'

    def _start_dlhottitles(self, attrsD):
        self.version = u'hotrss'

    def _start_channel(self, attrsD):
        self.infeed = 1
        self._cdf_common(attrsD)
    _start_feedinfo = _start_channel

    def _cdf_common(self, attrsD):
        if attrsD.has_key(u'lastmod'):
            self._start_modified({})
            self.elementstack[-1][-1] = attrsD[u'lastmod']
            self._end_modified()
        if attrsD.has_key(u'href'):
            self._start_link({})
            self.elementstack[-1][-1] = attrsD[u'href']
            self._end_link()

    def _start_feed(self, attrsD):
        self.infeed = 1
        versionmap = {u'0.1': u'atom01',
                      u'0.2': u'atom02',
                      u'0.3': u'atom03'}
        if not self.version:
            attr_version = attrsD.get(u'version')
            version = versionmap.get(attr_version)
            if version:
                self.version = version
            else:
                self.version = u'atom'

    def _end_channel(self):
        self.infeed = 0
    _end_feed = _end_channel

    def _start_image(self, attrsD):
        self.inimage = 1
        self.push(u'image', 0)
        context = self._getContext()
        context.setdefault(u'image', FeedParserDict())

    def _end_image(self):
        self.pop(u'image')
        self.inimage = 0

    def _start_textinput(self, attrsD):
        self.intextinput = 1
        self.push(u'textinput', 0)
        context = self._getContext()
        context.setdefault(u'textinput', FeedParserDict())
    _start_textInput = _start_textinput

    def _end_textinput(self):
        self.pop(u'textinput')
        self.intextinput = 0
    _end_textInput = _end_textinput

    def _start_author(self, attrsD):
        self.inauthor = 1
        self.push(u'author', 1)
    _start_managingeditor = _start_author
    _start_dc_author = _start_author
    _start_dc_creator = _start_author
    _start_itunes_author = _start_author

    def _end_author(self):
        self.pop(u'author')
        self.inauthor = 0
        self._sync_author_detail()
    _end_managingeditor = _end_author
    _end_dc_author = _end_author
    _end_dc_creator = _end_author
    _end_itunes_author = _end_author

    def _start_itunes_owner(self, attrsD):
        self.inpublisher = 1
        self.push(u'publisher', 0)

    def _end_itunes_owner(self):
        self.pop(u'publisher')
        self.inpublisher = 0
        self._sync_author_detail(u'publisher')

    def _start_contributor(self, attrsD):
        self.incontributor = 1
        context = self._getContext()
        context.setdefault(u'contributors', [])
        context[u'contributors'].append(FeedParserDict())
        self.push(u'contributor', 0)

    def _end_contributor(self):
        self.pop(u'contributor')
        self.incontributor = 0

    def _start_dc_contributor(self, attrsD):
        self.incontributor = 1
        context = self._getContext()
        context.setdefault(u'contributors', [])
        context[u'contributors'].append(FeedParserDict())
        self.push(u'name', 0)

    def _end_dc_contributor(self):
        self._end_name()
        self.incontributor = 0

    def _start_name(self, attrsD):
        self.push(u'name', 0)
    _start_itunes_name = _start_name

    def _end_name(self):
        value = self.pop(u'name')
        if self.inpublisher:
            self._save_author(u'name', value, u'publisher')
        elif self.inauthor:
            self._save_author(u'name', value)
        elif self.incontributor:
            self._save_contributor(u'name', value)
        elif self.intextinput:
            context = self._getContext()
            context[u'textinput'][u'name'] = value
    _end_itunes_name = _end_name

    def _start_width(self, attrsD):
        self.push(u'width', 0)

    def _end_width(self):
        value = self.pop(u'width')
        try:
            value = int(value)
        except:
            value = 0
        if self.inimage:
            context = self._getContext()
            context[u'image'][u'width'] = value

    def _start_height(self, attrsD):
        self.push(u'height', 0)

    def _end_height(self):
        value = self.pop(u'height')
        try:
            value = int(value)
        except:
            value = 0
        if self.inimage:
            context = self._getContext()
            context[u'image'][u'height'] = value

    def _start_url(self, attrsD):
        self.push(u'href', 1)
    _start_homepage = _start_url
    _start_uri = _start_url

    def _end_url(self):
        value = self.pop(u'href')
        if self.inauthor:
            self._save_author(u'href', value)
        elif self.incontributor:
            self._save_contributor(u'href', value)
        elif self.inimage:
            context = self._getContext()
            context[u'image'][u'href'] = value
        elif self.intextinput:
            context = self._getContext()
            context[u'textinput'][u'link'] = value
    _end_homepage = _end_url
    _end_uri = _end_url

    def _start_email(self, attrsD):
        self.push(u'email', 0)
    _start_itunes_email = _start_email

    def _end_email(self):
        value = self.pop(u'email')
        if self.inpublisher:
            self._save_author(u'email', value, u'publisher')
        elif self.inauthor:
            self._save_author(u'email', value)
        elif self.incontributor:
            self._save_contributor(u'email', value)
    _end_itunes_email = _end_email

    def _getContext(self):
        if self.insource:
            context = self.sourcedata
        elif self.inentry:
            context = self.entries[-1]
        else:
            context = self.feeddata
        return context

    def _save_author(self, key, value, prefix=u'author'):
        context = self._getContext()
        context.setdefault(prefix + u'_detail', FeedParserDict())
        context[prefix + u'_detail'][key] = value
        self._sync_author_detail()

    def _save_contributor(self, key, value):
        context = self._getContext()
        context.setdefault(u'contributors', [FeedParserDict()])
        context[u'contributors'][-1][key] = value

    def _sync_author_detail(self, key=u'author'):
        context = self._getContext()
        detail = context.get(u'%s_detail' % key)
        if detail:
            name = detail.get(u'name')
            email = detail.get(u'email')
            if name and email:
                context[key] = u'%s (%s)' % (name, email)
            elif name:
                context[key] = name
            elif email:
                context[key] = email
        else:
            author = context.get(key)
            if not author: return
            emailmatch = re.search(r'''(([a-zA-Z0-9\_\-\.\+]+)@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.)|(([a-zA-Z0-9\-]+\.)+))([a-zA-Z]{2,4}|[0-9]{1,3})(\]?))''', author)
            if not emailmatch: return
            email = emailmatch.group(0)
            # probably a better way to do the following, but it passes all the tests
            author = author.replace(email, u'')
            author = author.replace(u'()', u'')
            author = author.strip()
            if author and (author[0] == u'('):
                author = author[1:]
            if author and (author[-1] == u')'):
                author = author[:-1]
            author = author.strip()
            context.setdefault(u'%s_detail' % key, FeedParserDict())
            context[u'%s_detail' % key][u'name'] = author
            context[u'%s_detail' % key][u'email'] = email

    def _start_subtitle(self, attrsD):
        self.pushContent(u'subtitle', attrsD, u'text/plain', 1)
    _start_tagline = _start_subtitle
    _start_itunes_subtitle = _start_subtitle

    def _end_subtitle(self):
        self.popContent(u'subtitle')
    _end_tagline = _end_subtitle
    _end_itunes_subtitle = _end_subtitle

    def _start_rights(self, attrsD):
        self.pushContent(u'rights', attrsD, u'text/plain', 1)
    _start_dc_rights = _start_rights
    _start_copyright = _start_rights

    def _end_rights(self):
        self.popContent(u'rights')
    _end_dc_rights = _end_rights
    _end_copyright = _end_rights

    def _start_item(self, attrsD):
        self.entries.append(FeedParserDict())
        self.push(u'item', 0)
        self.inentry = 1
        self.guidislink = 0
        id = self._getAttribute(attrsD, u'rdf:about')
        if id:
            context = self._getContext()
            context[u'id'] = id
        self._cdf_common(attrsD)
    _start_entry = _start_item
    _start_product = _start_item

    def _end_item(self):
        self.pop(u'item')
        self.inentry = 0
    _end_entry = _end_item

    def _start_dc_language(self, attrsD):
        self.push(u'language', 1)
    _start_language = _start_dc_language

    def _end_dc_language(self):
        self.lang = self.pop(u'language')
    _end_language = _end_dc_language

    def _start_dc_publisher(self, attrsD):
        self.push(u'publisher', 1)
    _start_webmaster = _start_dc_publisher

    def _end_dc_publisher(self):
        self.pop(u'publisher')
        self._sync_author_detail(u'publisher')
    _end_webmaster = _end_dc_publisher

    def _start_published(self, attrsD):
        self.push(u'published', 1)
    _start_dcterms_issued = _start_published
    _start_issued = _start_published

    def _end_published(self):
        value = self.pop(u'published')
        self._save(u'published_parsed', _parse_date(value))
    _end_dcterms_issued = _end_published
    _end_issued = _end_published

    def _start_updated(self, attrsD):
        self.push(u'updated', 1)
    _start_modified = _start_updated
    _start_dcterms_modified = _start_updated
    _start_pubdate = _start_updated
    _start_dc_date = _start_updated

    def _end_updated(self):
        value = self.pop(u'updated')
        parsed_value = _parse_date(value)
        self._save(u'updated_parsed', parsed_value)
    _end_modified = _end_updated
    _end_dcterms_modified = _end_updated
    _end_pubdate = _end_updated
    _end_dc_date = _end_updated

    def _start_created(self, attrsD):
        self.push(u'created', 1)
    _start_dcterms_created = _start_created

    def _end_created(self):
        value = self.pop(u'created')
        self._save(u'created_parsed', _parse_date(value))
    _end_dcterms_created = _end_created

    def _start_expirationdate(self, attrsD):
        self.push(u'expired', 1)

    def _end_expirationdate(self):
        self._save(u'expired_parsed', _parse_date(self.pop(u'expired')))

    def _start_cc_license(self, attrsD):
        self.push(u'license', 1)
        value = self._getAttribute(attrsD, u'rdf:resource')
        if value:
            self.elementstack[-1][2].append(value)
        self.pop(u'license')

    def _start_creativecommons_license(self, attrsD):
        self.push(u'license', 1)

    def _end_creativecommons_license(self):
        self.pop(u'license')

    def _addTag(self, term, scheme, label):
        context = self._getContext()
        tags = context.setdefault(u'tags', [])
        if (not term) and (not scheme) and (not label): return
        value = FeedParserDict({u'term': term, u'scheme': scheme, u'label': label})
        if value not in tags:
            tags.append(FeedParserDict({u'term': term, u'scheme': scheme, u'label': label}))

    def _start_category(self, attrsD):
        if _debug: sys.stderr.write(u'entering _start_category with %s\n' % repr(attrsD))
        term = attrsD.get(u'term')
        scheme = attrsD.get(u'scheme', attrsD.get(u'domain'))
        label = attrsD.get(u'label')
        self._addTag(term, scheme, label)
        self.push(u'category', 1)
    _start_dc_subject = _start_category
    _start_keywords = _start_category

    def _end_itunes_keywords(self):
        for term in self.pop(u'itunes_keywords').split():
            self._addTag(term, u'http://www.itunes.com/', None)

    def _start_itunes_category(self, attrsD):
        self._addTag(attrsD.get(u'text'), u'http://www.itunes.com/', None)
        self.push(u'category', 1)

    def _end_category(self):
        value = self.pop(u'category')
        if not value: return
        context = self._getContext()
        tags = context[u'tags']
        if value and len(tags) and not tags[-1][u'term']:
            tags[-1][u'term'] = value
        else:
            self._addTag(value, None, None)
    _end_dc_subject = _end_category
    _end_keywords = _end_category
    _end_itunes_category = _end_category

    def _start_cloud(self, attrsD):
        self._getContext()[u'cloud'] = FeedParserDict(attrsD)

    def _start_link(self, attrsD):
        attrsD.setdefault(u'rel', u'alternate')
        attrsD.setdefault(u'type', u'text/html')
        attrsD = self._itsAnHrefDamnIt(attrsD)
        if attrsD.has_key(u'href'):
            attrsD[u'href'] = self.resolveURI(attrsD[u'href'])
        expectingText = self.infeed or self.inentry or self.insource
        context = self._getContext()
        context.setdefault(u'links', [])
        context[u'links'].append(FeedParserDict(attrsD))
        if attrsD[u'rel'] == u'enclosure':
            self._start_enclosure(attrsD)
        if attrsD.has_key(u'href'):
            expectingText = 0
            if (attrsD.get(u'rel') == u'alternate') and (self.mapContentType(attrsD.get(u'type')) in self.html_types):
                context[u'link'] = attrsD[u'href']
        else:
            self.push(u'link', expectingText)
    _start_producturl = _start_link

    def _end_link(self):
        value = self.pop(u'link')
        context = self._getContext()
        if self.intextinput:
            context[u'textinput'][u'link'] = value
        if self.inimage:
            context[u'image'][u'link'] = value
    _end_producturl = _end_link

    def _start_guid(self, attrsD):
        self.guidislink = (attrsD.get(u'ispermalink', u'true') == u'true')
        self.push(u'id', 1)

    def _end_guid(self):
        value = self.pop(u'id')
        self._save(u'guidislink', self.guidislink and not self._getContext().has_key(u'link'))
        if self.guidislink:
            # guid acts as link, but only if u'ispermalink' is not present or is u'true',
            # and only if the item doesn't already have a link element
            self._save(u'link', value)

    def _start_title(self, attrsD):
        self.pushContent(u'title', attrsD, u'text/plain', self.infeed or self.inentry or self.insource)
    _start_dc_title = _start_title
    _start_media_title = _start_title

    def _end_title(self):
        value = self.popContent(u'title')
        context = self._getContext()
        if self.intextinput:
            context[u'textinput'][u'title'] = value
        elif self.inimage:
            context[u'image'][u'title'] = value
    _end_dc_title = _end_title
    _end_media_title = _end_title

    def _start_description(self, attrsD):
        context = self._getContext()
        if context.has_key(u'summary'):
            self._summaryKey = u'content'
            self._start_content(attrsD)
        else:
            self.pushContent(u'description', attrsD, u'text/html', self.infeed or self.inentry or self.insource)

    def _start_abstract(self, attrsD):
        self.pushContent(u'description', attrsD, u'text/plain', self.infeed or self.inentry or self.insource)

    def _end_description(self):
        if self._summaryKey == u'content':
            self._end_content()
        else:
            value = self.popContent(u'description')
            context = self._getContext()
            if self.intextinput:
                context[u'textinput'][u'description'] = value
            elif self.inimage:
                context[u'image'][u'description'] = value
        self._summaryKey = None
    _end_abstract = _end_description

    def _start_info(self, attrsD):
        self.pushContent(u'info', attrsD, u'text/plain', 1)
    _start_feedburner_browserfriendly = _start_info

    def _end_info(self):
        self.popContent(u'info')
    _end_feedburner_browserfriendly = _end_info

    def _start_generator(self, attrsD):
        if attrsD:
            attrsD = self._itsAnHrefDamnIt(attrsD)
            if attrsD.has_key(u'href'):
                attrsD[u'href'] = self.resolveURI(attrsD[u'href'])
        self._getContext()[u'generator_detail'] = FeedParserDict(attrsD)
        self.push(u'generator', 1)

    def _end_generator(self):
        value = self.pop(u'generator')
        context = self._getContext()
        if context.has_key(u'generator_detail'):
            context[u'generator_detail'][u'name'] = value

    def _start_admin_generatoragent(self, attrsD):
        self.push(u'generator', 1)
        value = self._getAttribute(attrsD, u'rdf:resource')
        if value:
            self.elementstack[-1][2].append(value)
        self.pop(u'generator')
        self._getContext()[u'generator_detail'] = FeedParserDict({u'href': value})

    def _start_admin_errorreportsto(self, attrsD):
        self.push(u'errorreportsto', 1)
        value = self._getAttribute(attrsD, u'rdf:resource')
        if value:
            self.elementstack[-1][2].append(value)
        self.pop(u'errorreportsto')

    def _start_summary(self, attrsD):
        context = self._getContext()
        if context.has_key(u'summary'):
            self._summaryKey = u'content'
            self._start_content(attrsD)
        else:
            self._summaryKey = u'summary'
            self.pushContent(self._summaryKey, attrsD, u'text/plain', 1)
    _start_itunes_summary = _start_summary

    def _end_summary(self):
        if self._summaryKey == u'content':
            self._end_content()
        else:
            self.popContent(self._summaryKey or u'summary')
        self._summaryKey = None
    _end_itunes_summary = _end_summary

    def _start_enclosure(self, attrsD):
        attrsD = self._itsAnHrefDamnIt(attrsD)
        self._getContext().setdefault(u'enclosures', []).append(FeedParserDict(attrsD))
        href = attrsD.get(u'href')
        if href:
            context = self._getContext()
            if not context.get(u'id'):
                context[u'id'] = href

    def _start_source(self, attrsD):
        self.insource = 1

    def _end_source(self):
        self.insource = 0
        self._getContext()[u'source'] = copy.deepcopy(self.sourcedata)
        self.sourcedata.clear()

    def _start_content(self, attrsD):
        self.pushContent(u'content', attrsD, u'text/plain', 1)
        src = attrsD.get(u'src')
        if src:
            self.contentparams[u'src'] = src
        self.push(u'content', 1)

    def _start_prodlink(self, attrsD):
        self.pushContent(u'content', attrsD, u'text/html', 1)

    def _start_body(self, attrsD):
        self.pushContent(u'content', attrsD, u'application/xhtml+xml', 1)
    _start_xhtml_body = _start_body

    def _start_content_encoded(self, attrsD):
        self.pushContent(u'content', attrsD, u'text/html', 1)
    _start_fullitem = _start_content_encoded

    def _end_content(self):
        copyToDescription = self.mapContentType(self.contentparams.get(u'type')) in ([u'text/plain'] + self.html_types)
        value = self.popContent(u'content')
        if copyToDescription:
            self._save(u'description', value)
    _end_body = _end_content
    _end_xhtml_body = _end_content
    _end_content_encoded = _end_content
    _end_fullitem = _end_content
    _end_prodlink = _end_content

    def _start_itunes_image(self, attrsD):
        self.push(u'itunes_image', 0)
        self._getContext()[u'image'] = FeedParserDict({u'href': attrsD.get(u'href')})
    _start_itunes_link = _start_itunes_image

    def _end_itunes_block(self):
        value = self.pop(u'itunes_block', 0)
        self._getContext()[u'itunes_block'] = (value == u'yes') and 1 or 0

    def _end_itunes_explicit(self):
        value = self.pop(u'itunes_explicit', 0)
        self._getContext()[u'itunes_explicit'] = (value == u'yes') and 1 or 0

if _XML_AVAILABLE:
    class _StrictFeedParser(_FeedParserMixin, xml.sax.handler.ContentHandler):
        def __init__(self, baseuri, baselang, encoding):
            if _debug: sys.stderr.write(u'trying StrictFeedParser\n')
            xml.sax.handler.ContentHandler.__init__(self)
            _FeedParserMixin.__init__(self, baseuri, baselang, encoding)
            self.bozo = 0
            self.exc = None

        def startPrefixMapping(self, prefix, uri):
            self.trackNamespace(prefix, uri)

        def startElementNS(self, name, qname, attrs):
            namespace, localname = name
            lowernamespace = unicode(namespace or u'').lower()
            if lowernamespace.find(u'backend.userland.com/rss') <> -1:
                # match any backend.userland.com namespace
                namespace = u'http://backend.userland.com/rss'
                lowernamespace = namespace
            if qname and qname.find(u':') > 0:
                givenprefix = qname.split(u':')[0]
            else:
                givenprefix = None
            prefix = self._matchnamespaces.get(lowernamespace, givenprefix)
            if givenprefix and (prefix == None or (prefix == u'' and lowernamespace == u'')) and not self.namespacesInUse.has_key(givenprefix):
                    raise UndeclaredNamespace, u"'%s' is not associated with a namespace" % givenprefix
            if prefix:
                localname = prefix + u':' + localname
            localname = unicode(localname).lower()
            if _debug: sys.stderr.write(u'startElementNS: qname = %s, namespace = %s, givenprefix = %s, prefix = %s, attrs = %s, localname = %s\n' % (qname, namespace, givenprefix, prefix, attrs.items(), localname))

            # qname implementation is horribly broken in Python 2.1 (it
            # doesn't report any), and slightly broken in Python 2.2 (it
            # doesn't report the xml: namespace). So we match up namespaces
            # with a known list first, and then possibly override them with
            # the qnames the SAX parser gives us (if indeed it gives us any
            # at all).  Thanks to MatejC for helping me test this and
            # tirelessly telling me that it didn't work yet.
            attrsD = {}
            for (namespace, attrlocalname), attrvalue in attrs._attrs.items():
                lowernamespace = (namespace or u'').lower()
                prefix = self._matchnamespaces.get(lowernamespace, u'')
                if prefix:
                    attrlocalname = prefix + u':' + attrlocalname
                attrsD[unicode(attrlocalname).lower()] = attrvalue
            for qname in attrs.getQNames():
                attrsD[unicode(qname).lower()] = attrs.getValueByQName(qname)
            self.unknown_starttag(localname, attrsD.items())

        def characters(self, text):
            self.handle_data(text)

        def endElementNS(self, name, qname):
            namespace, localname = name
            lowernamespace = unicode(namespace or u'').lower()
            if qname and qname.find(u':') > 0:
                givenprefix = qname.split(u':')[0]
            else:
                givenprefix = u''
            prefix = self._matchnamespaces.get(lowernamespace, givenprefix)
            if prefix:
                localname = prefix + u':' + localname
            localname = unicode(localname).lower()
            self.unknown_endtag(localname)

        def error(self, exc):
            self.bozo = 1
            self.exc = exc

        def fatalError(self, exc):
            self.error(exc)
            raise exc

class _BaseHTMLProcessor(sgmllib.SGMLParser):
    elements_no_end_tag = [u'area', u'base', u'basefont', u'br', u'col', u'frame', u'hr',
      u'img', u'input', u'isindex', u'link', u'meta', u'param']

    def __init__(self, encoding):
        self.encoding = encoding
        if _debug: sys.stderr.write(u'entering BaseHTMLProcessor, encoding=%s\n' % self.encoding)
        sgmllib.SGMLParser.__init__(self)

    def reset(self):
        self.pieces = []
        sgmllib.SGMLParser.reset(self)

    def _shorttag_replace(self, match):
        tag = match.group(1)
        if tag in self.elements_no_end_tag:
            return u'<' + tag + u' />'
        else:
            return u'<' + tag + u'></' + tag + u'>'

    def feed(self, data):
        data = re.compile(r'<!((?!DOCTYPE|--|\[))', re.IGNORECASE).sub(r'&lt;!\1', data)
        #data = re.sub(r'<(\S+?)\s*?/>', self._shorttag_replace, data) # bug [ 1399464 ] Bad regexp for _shorttag_replace
        data = re.sub(r'<([^<\s]+?)\s*/>', self._shorttag_replace, data)
        data = data.replace(u'&#39;', u"'")
        data = data.replace(u'&#34;', u'"')
        if self.encoding and type(data) == type(u''):
            data = data.encode(self.encoding)
        sgmllib.SGMLParser.feed(self, data)

    def normalize_attrs(self, attrs):
        # utility method to be called by descendants
        attrs = [(k.lower(), v) for k, v in attrs]
        attrs = [(k, k in (u'rel', u'type') and v.lower() or v) for k, v in attrs]
        return attrs

    def unknown_starttag(self, tag, attrs):
        # called for each start tag
        # attrs is a list of (attr, value) tuples
        # e.g. for <pre class=u'screen'>, tag=u'pre', attrs=[(u'class', u'screen')]
        if _debug: sys.stderr.write(u'_BaseHTMLProcessor, unknown_starttag, tag=%s\n' % tag)
        uattrs = []
        # thanks to Kevin Marks for this breathtaking hack to deal with (valid) high-bit attribute values in UTF-8 feeds
        for key, value in attrs:
            if type(value) != type(u''):
                value = unicode(value, self.encoding)
            uattrs.append((unicode(key, self.encoding), value))
        strattrs = u''.join([u' %s="%s"' % (key, value) for key, value in uattrs]).encode(self.encoding)
        if tag in self.elements_no_end_tag:
            self.pieces.append(u'<%(tag)s%(strattrs)s />' % locals())
        else:
            self.pieces.append(u'<%(tag)s%(strattrs)s>' % locals())

    def unknown_endtag(self, tag):
        # called for each end tag, e.g. for </pre>, tag will be u'pre'
        # Reconstruct the original end tag.
        if tag not in self.elements_no_end_tag:
            self.pieces.append(u"</%(tag)s>" % locals())

    def handle_charref(self, ref):
        # called for each character reference, e.g. for u'&#160;', ref will be u'160'
        # Reconstruct the original character reference.
        self.pieces.append(u'&#%(ref)s;' % locals())

    def handle_entityref(self, ref):
        # called for each entity reference, e.g. for u'&copy;', ref will be u'copy'
        # Reconstruct the original entity reference.
        self.pieces.append(u'&%(ref)s;' % locals())

    def handle_data(self, text):
        # called for each block of plain text, i.e. outside of any tag and
        # not containing any character or entity references
        # Store the original text verbatim.
        if _debug: sys.stderr.write(u'_BaseHTMLProcessor, handle_text, text=%s\n' % text)
        self.pieces.append(text)

    def handle_comment(self, text):
        # called for each HTML comment, e.g. <!-- insert Javascript code here -->
        # Reconstruct the original comment.
        self.pieces.append(u'<!--%(text)s-->' % locals())

    def handle_pi(self, text):
        # called for each processing instruction, e.g. <?instruction>
        # Reconstruct original processing instruction.
        self.pieces.append(u'<?%(text)s>' % locals())

    def handle_decl(self, text):
        # called for the DOCTYPE, if present, e.g.
        # <!DOCTYPE html PUBLIC u"-//W3C//DTD HTML 4.01 Transitional//EN"
        #     u"http://www.w3.org/TR/html4/loose.dtd">
        # Reconstruct original DOCTYPE
        self.pieces.append(u'<!%(text)s>' % locals())

    _new_declname_match = re.compile(r'[a-zA-Z][-_.a-zA-Z0-9:]*\s*').match
    def _scan_name(self, i, declstartpos):
        rawdata = self.rawdata
        n = len(rawdata)
        if i == n:
            return None, -1
        m = self._new_declname_match(rawdata, i)
        if m:
            s = m.group()
            name = s.strip()
            if (i + len(s)) == n:
                return None, -1  # end of buffer
            return name.lower(), m.end()
        else:
            self.handle_data(rawdata)
#            self.updatepos(declstartpos, i)
            return None, -1

    def output(self):
        '''Return processed HTML as a single string'''
        return u''.join([unicode(p) for p in self.pieces])

class _LooseFeedParser(_FeedParserMixin, _BaseHTMLProcessor):
    def __init__(self, baseuri, baselang, encoding):
        sgmllib.SGMLParser.__init__(self)
        _FeedParserMixin.__init__(self, baseuri, baselang, encoding)

    def decodeEntities(self, element, data):
        data = data.replace(u'&#60;', u'&lt;')
        data = data.replace(u'&#x3c;', u'&lt;')
        data = data.replace(u'&#62;', u'&gt;')
        data = data.replace(u'&#x3e;', u'&gt;')
        data = data.replace(u'&#38;', u'&amp;')
        data = data.replace(u'&#x26;', u'&amp;')
        data = data.replace(u'&#34;', u'&quot;')
        data = data.replace(u'&#x22;', u'&quot;')
        data = data.replace(u'&#39;', u'&apos;')
        data = data.replace(u'&#x27;', u'&apos;')
        if self.contentparams.has_key(u'type') and not self.contentparams.get(u'type', u'xml').endswith(u'xml'):
            data = data.replace(u'&lt;', u'<')
            data = data.replace(u'&gt;', u'>')
            data = data.replace(u'&amp;', u'&')
            data = data.replace(u'&quot;', u'"')
            data = data.replace(u'&apos;', u"'")
        return data

class _RelativeURIResolver(_BaseHTMLProcessor):
    relative_uris = [(u'a', u'href'),
                     (u'applet', u'codebase'),
                     (u'area', u'href'),
                     (u'blockquote', u'cite'),
                     (u'body', u'background'),
                     (u'del', u'cite'),
                     (u'form', u'action'),
                     (u'frame', u'longdesc'),
                     (u'frame', u'src'),
                     (u'iframe', u'longdesc'),
                     (u'iframe', u'src'),
                     (u'head', u'profile'),
                     (u'img', u'longdesc'),
                     (u'img', u'src'),
                     (u'img', u'usemap'),
                     (u'input', u'src'),
                     (u'input', u'usemap'),
                     (u'ins', u'cite'),
                     (u'link', u'href'),
                     (u'object', u'classid'),
                     (u'object', u'codebase'),
                     (u'object', u'data'),
                     (u'object', u'usemap'),
                     (u'q', u'cite'),
                     (u'script', u'src')]

    def __init__(self, baseuri, encoding):
        _BaseHTMLProcessor.__init__(self, encoding)
        self.baseuri = baseuri

    def resolveURI(self, uri):
        return _urljoin(self.baseuri, uri)

    def unknown_starttag(self, tag, attrs):
        attrs = self.normalize_attrs(attrs)
        attrs = [(key, ((tag, key) in self.relative_uris) and self.resolveURI(value) or value) for key, value in attrs]
        _BaseHTMLProcessor.unknown_starttag(self, tag, attrs)

def _resolveRelativeURIs(htmlSource, baseURI, encoding):
    if _debug: sys.stderr.write(u'entering _resolveRelativeURIs\n')
    p = _RelativeURIResolver(baseURI, encoding)
    p.feed(htmlSource)
    return p.output()

class _HTMLSanitizer(_BaseHTMLProcessor):
    acceptable_elements = [u'a', u'abbr', u'acronym', u'address', u'area', u'b', u'big',
      u'blockquote', u'br', u'button', u'caption', u'center', u'cite', u'code', u'col',
      u'colgroup', u'dd', u'del', u'dfn', u'dir', u'div', u'dl', u'dt', u'em', u'fieldset',
      u'font', u'form', u'h1', u'h2', u'h3', u'h4', u'h5', u'h6', u'hr', u'i', u'img', u'input',
      u'ins', u'kbd', u'label', u'legend', u'li', u'map', u'menu', u'ol', u'optgroup',
      u'option', u'p', u'pre', u'q', u's', u'samp', u'select', u'small', u'span', u'strike',
      u'strong', u'sub', u'sup', u'table', u'tbody', u'td', u'textarea', u'tfoot', u'th',
      u'thead', u'tr', u'tt', u'u', u'ul', u'var']

    acceptable_attributes = [u'abbr', u'accept', u'accept-charset', u'accesskey',
      u'action', u'align', u'alt', u'axis', u'border', u'cellpadding', u'cellspacing',
      u'char', u'charoff', u'charset', u'checked', u'cite', u'class', u'clear', u'cols',
      u'colspan', u'color', u'compact', u'coords', u'datetime', u'dir', u'disabled',
      u'enctype', u'for', u'frame', u'headers', u'height', u'href', u'hreflang', u'hspace',
      u'id', u'ismap', u'label', u'lang', u'longdesc', u'maxlength', u'media', u'method',
      u'multiple', u'name', u'nohref', u'noshade', u'nowrap', u'prompt', u'readonly',
      u'rel', u'rev', u'rows', u'rowspan', u'rules', u'scope', u'selected', u'shape', u'size',
      u'span', u'src', u'start', u'summary', u'tabindex', u'target', u'title', u'type',
      u'usemap', u'valign', u'value', u'vspace', u'width']

    unacceptable_elements_with_end_tag = [u'script', u'applet']

    def reset(self):
        _BaseHTMLProcessor.reset(self)
        self.unacceptablestack = 0

    def unknown_starttag(self, tag, attrs):
        if not tag in self.acceptable_elements:
            if tag in self.unacceptable_elements_with_end_tag:
                self.unacceptablestack += 1
            return
        attrs = self.normalize_attrs(attrs)
        attrs = [(key, value) for key, value in attrs if key in self.acceptable_attributes]
        _BaseHTMLProcessor.unknown_starttag(self, tag, attrs)

    def unknown_endtag(self, tag):
        if not tag in self.acceptable_elements:
            if tag in self.unacceptable_elements_with_end_tag:
                self.unacceptablestack -= 1
            return
        _BaseHTMLProcessor.unknown_endtag(self, tag)

    def handle_pi(self, text):
        pass

    def handle_decl(self, text):
        pass

    def handle_data(self, text):
        if not self.unacceptablestack:
            _BaseHTMLProcessor.handle_data(self, text)

def _sanitizeHTML(htmlSource, encoding):
    p = _HTMLSanitizer(encoding)
    p.feed(htmlSource)
    data = p.output()
    if TIDY_MARKUP:
        # loop through list of preferred Tidy interfaces looking for one that's installed,
        # then set up a common _tidy function to wrap the interface-specific API.
        _tidy = None
        for tidy_interface in PREFERRED_TIDY_INTERFACES:
            try:
                if tidy_interface == u"uTidy":
                    from tidy import parseString as _utidy
                    def _tidy(data, **kwargs):
                        return unicode(_utidy(data, **kwargs))
                    break
                elif tidy_interface == u"mxTidy":
                    from mx.Tidy import Tidy as _mxtidy
                    def _tidy(data, **kwargs):
                        nerrors, nwarnings, data, errordata = _mxtidy.tidy(data, **kwargs)
                        return data
                    break
            except:
                pass
        if _tidy:
            utf8 = type(data) == type(u'')
            if utf8:
                data = data.encode(u'utf-8')
            data = _tidy(data, output_xhtml=1, numeric_entities=1, wrap=0, char_encoding=u"utf8")
            if utf8:
                data = unicode(data, u'utf-8')
            if data.count(u'<body'):
                data = data.split(u'<body', 1)[1]
                if data.count(u'>'):
                    data = data.split(u'>', 1)[1]
            if data.count(u'</body'):
                data = data.split(u'</body', 1)[0]
    data = data.strip().replace(u'\r\n', u'\n')
    return data

class _FeedURLHandler(urllib2.HTTPDigestAuthHandler, urllib2.HTTPRedirectHandler, urllib2.HTTPDefaultErrorHandler):
    def http_error_default(self, req, fp, code, msg, headers):
        if ((code / 100) == 3) and (code != 304):
            return self.http_error_302(req, fp, code, msg, headers)
        infourl = urllib.addinfourl(fp, headers, req.get_full_url())
        infourl.status = code
        return infourl

    def http_error_302(self, req, fp, code, msg, headers):
        if headers.dict.has_key(u'location'):
            infourl = urllib2.HTTPRedirectHandler.http_error_302(self, req, fp, code, msg, headers)
        else:
            infourl = urllib.addinfourl(fp, headers, req.get_full_url())
        if not hasattr(infourl, u'status'):
            infourl.status = code
        return infourl

    def http_error_301(self, req, fp, code, msg, headers):
        if headers.dict.has_key(u'location'):
            infourl = urllib2.HTTPRedirectHandler.http_error_301(self, req, fp, code, msg, headers)
        else:
            infourl = urllib.addinfourl(fp, headers, req.get_full_url())
        if not hasattr(infourl, u'status'):
            infourl.status = code
        return infourl

    http_error_300 = http_error_302
    http_error_303 = http_error_302
    http_error_307 = http_error_302

    def http_error_401(self, req, fp, code, msg, headers):
        # Check if
        # - server requires digest auth, AND
        # - we tried (unsuccessfully) with basic auth, AND
        # - we're using Python 2.3.3 or later (digest auth is irreparably broken in earlier versions)
        # If all conditions hold, parse authentication information
        # out of the Authorization header we sent the first time
        # (for the username and password) and the WWW-Authenticate
        # header the server sent back (for the realm) and retry
        # the request with the appropriate digest auth headers instead.
        # This evil genius hack has been brought to you by Aaron Swartz.
        host = urlparse.urlparse(req.get_full_url())[1]
        try:
            assert sys.version.split()[0] >= u'2.3.3'
            assert base64 != None
            user, passw = base64.decodestring(req.headers[u'Authorization'].split(u' ')[1]).split(u':')
            realm = re.findall(u'realm="([^"]*)"', headers[u'WWW-Authenticate'])[0]
            self.add_password(realm, host, user, passw)
            retry = self.http_error_auth_reqed(u'www-authenticate', host, req, headers)
            self.reset_retry_count()
            return retry
        except:
            return self.http_error_default(req, fp, code, msg, headers)

def _open_resource(url_file_stream_or_string, etag, modified, agent, referrer, handlers):
    """URL, filename, or string --> stream

    This function lets you define parsers that take any input source
    (URL, pathname to local or network file, or actual data as a string)
    and deal with it in a uniform manner.  Returned object is guaranteed
    to have all the basic stdio read methods (read, readline, readlines).
    Just .close() the object when you're done with it.

    If the etag argument is supplied, it will be used as the value of an
    If-None-Match request header.

    If the modified argument is supplied, it must be a tuple of 9 integers
    as returned by gmtime() in the standard Python time module. This MUST
    be in GMT (Greenwich Mean Time). The formatted date/time will be used
    as the value of an If-Modified-Since request header.

    If the agent argument is supplied, it will be used as the value of a
    User-Agent request header.

    If the referrer argument is supplied, it will be used as the value of a
    Referer[sic] request header.

    If handlers is supplied, it is a list of handlers used to build a
    urllib2 opener.
    """

    if hasattr(url_file_stream_or_string, u'read'):
        return url_file_stream_or_string

    if url_file_stream_or_string == u'-':
        return sys.stdin

    if urlparse.urlparse(url_file_stream_or_string)[0] in (u'http', u'https', u'ftp'):
        if not agent:
            agent = USER_AGENT
        # test for inline user:password for basic auth
        auth = None
        if base64:
            urltype, rest = urllib.splittype(url_file_stream_or_string)
            realhost, rest = urllib.splithost(rest)
            if realhost:
                user_passwd, realhost = urllib.splituser(realhost)
                if user_passwd:
                    url_file_stream_or_string = u'%s://%s%s' % (urltype, realhost, rest)
                    auth = base64.encodestring(user_passwd).strip()
        # try to open with urllib2 (to use optional headers)
        request = urllib2.Request(url_file_stream_or_string)
        request.add_header(u'User-Agent', agent)
        if etag:
            request.add_header(u'If-None-Match', etag)
        if modified:
            # format into an RFC 1123-compliant timestamp. We can't use
            # time.strftime() since the %a and %b directives can be affected
            # by the current locale, but RFC 2616 states that dates must be
            # in English.
            short_weekdays = [u'Mon', u'Tue', u'Wed', u'Thu', u'Fri', u'Sat', u'Sun']
            months = [u'Jan', u'Feb', u'Mar', u'Apr', u'May', u'Jun', u'Jul', u'Aug', u'Sep', u'Oct', u'Nov', u'Dec']
            request.add_header(u'If-Modified-Since', u'%s, %02d %s %04d %02d:%02d:%02d GMT' % (short_weekdays[modified[6]], modified[2], months[modified[1] - 1], modified[0], modified[3], modified[4], modified[5]))
        if referrer:
            request.add_header(u'Referer', referrer)
        if gzip and zlib:
            request.add_header(u'Accept-encoding', u'gzip, deflate')
        elif gzip:
            request.add_header(u'Accept-encoding', u'gzip')
        elif zlib:
            request.add_header(u'Accept-encoding', u'deflate')
        else:
            request.add_header(u'Accept-encoding', u'')
        if auth:
            request.add_header(u'Authorization', u'Basic %s' % auth)
        if ACCEPT_HEADER:
            request.add_header(u'Accept', ACCEPT_HEADER)
        request.add_header(u'A-IM', u'feed') # RFC 3229 support
        opener = apply(urllib2.build_opener, tuple([_FeedURLHandler()] + handlers))
        opener.addheaders = [] # RMK - must clear so we only send our custom User-Agent
        try:
            return opener.open(request)
        finally:
            opener.close() # JohnD

    # try to open with native open function (if url_file_stream_or_string is a filename)
    try:
        return open(url_file_stream_or_string)
    except:
        pass

    # treat url_file_stream_or_string as string
    return _StringIO(unicode(url_file_stream_or_string))

_date_handlers = []
def registerDateHandler(func):
    '''Register a date handler function (takes string, returns 9-tuple date in GMT)'''
    _date_handlers.insert(0, func)

# ISO-8601 date parsing routines written by Fazal Majid.
# The ISO 8601 standard is very convoluted and irregular - a full ISO 8601
# parser is beyond the scope of feedparser and would be a worthwhile addition
# to the Python library.
# A single regular expression cannot parse ISO 8601 date formats into groups
# as the standard is highly irregular (for instance is 030104 2003-01-04 or
# 0301-04-01), so we use templates instead.
# Please note the order in templates is significant because we need a
# greedy match.
_iso8601_tmpl = [u'YYYY-?MM-?DD', u'YYYY-MM', u'YYYY-?OOO',
                u'YY-?MM-?DD', u'YY-?OOO', u'YYYY',
                u'-YY-?MM', u'-OOO', u'-YY',
                u'--MM-?DD', u'--MM',
                u'---DD',
                u'CC', u'']
_iso8601_re = [
    tmpl.replace(
    u'YYYY', r'(?P<year>\d{4})').replace(
    u'YY', r'(?P<year>\d\d)').replace(
    u'MM', r'(?P<month>[01]\d)').replace(
    u'DD', r'(?P<day>[0123]\d)').replace(
    u'OOO', r'(?P<ordinal>[0123]\d\d)').replace(
    u'CC', r'(?P<century>\d\d$)')
    + r'(T?(?P<hour>\d{2}):(?P<minute>\d{2})'
    + r'(:(?P<second>\d{2}))?'
    + r'(?P<tz>[+-](?P<tzhour>\d{2})(:(?P<tzmin>\d{2}))?|Z)?)?'
    for tmpl in _iso8601_tmpl]
del tmpl
_iso8601_matches = [re.compile(regex).match for regex in _iso8601_re]
del regex
def _parse_date_iso8601(dateString):
    '''Parse a variety of ISO-8601-compatible formats like 20040105'''
    m = None
    for _iso8601_match in _iso8601_matches:
        m = _iso8601_match(dateString)
        if m: break
    if not m: return
    if m.span() == (0, 0): return
    params = m.groupdict()
    ordinal = params.get(u'ordinal', 0)
    if ordinal:
        ordinal = int(ordinal)
    else:
        ordinal = 0
    year = params.get(u'year', u'--')
    if not year or year == u'--':
        year = time.gmtime()[0]
    elif len(year) == 2:
        # ISO 8601 assumes current century, i.e. 93 -> 2093, NOT 1993
        year = 100 * int(time.gmtime()[0] / 100) + int(year)
    else:
        year = int(year)
    month = params.get(u'month', u'-')
    if not month or month == u'-':
        # ordinals are NOT normalized by mktime, we simulate them
        # by setting month=1, day=ordinal
        if ordinal:
            month = 1
        else:
            month = time.gmtime()[1]
    month = int(month)
    day = params.get(u'day', 0)
    if not day:
        # see above
        if ordinal:
            day = ordinal
        elif params.get(u'century', 0) or \
                 params.get(u'year', 0) or params.get(u'month', 0):
            day = 1
        else:
            day = time.gmtime()[2]
    else:
        day = int(day)
    # special case of the century - is the first year of the 21st century
    # 2000 or 2001 ? The debate goes on...
    if u'century' in params.keys():
        year = (int(params[u'century']) - 1) * 100 + 1
    # in ISO 8601 most fields are optional
    for field in [u'hour', u'minute', u'second', u'tzhour', u'tzmin']:
        if not params.get(field, None):
            params[field] = 0
    hour = int(params.get(u'hour', 0))
    minute = int(params.get(u'minute', 0))
    second = int(params.get(u'second', 0))
    # weekday is normalized by mktime(), we can ignore it
    weekday = 0
    # daylight savings is complex, but not needed for feedparser's purposes
    # as time zones, if specified, include mention of whether it is active
    # (e.g. PST vs. PDT, CET). Using -1 is implementation-dependent and
    # and most implementations have DST bugs
    daylight_savings_flag = 0
    tm = [year, month, day, hour, minute, second, weekday,
          ordinal, daylight_savings_flag]
    # ISO 8601 time zone adjustments
    tz = params.get(u'tz')
    if tz and tz != u'Z':
        if tz[0] == u'-':
            tm[3] += int(params.get(u'tzhour', 0))
            tm[4] += int(params.get(u'tzmin', 0))
        elif tz[0] == u'+':
            tm[3] -= int(params.get(u'tzhour', 0))
            tm[4] -= int(params.get(u'tzmin', 0))
        else:
            return None
    # Python's time.mktime() is a wrapper around the ANSI C mktime(3c)
    # which is guaranteed to normalize d/m/y/h/m/s.
    # Many implementations have bugs, but weu'll pretend they don't.
    return time.localtime(time.mktime(tm))
registerDateHandler(_parse_date_iso8601)

# 8-bit date handling routines written by ytrewq1.
_korean_year  = u'\ub144' # b3e2 in euc-kr
_korean_month = u'\uc6d4' # bff9 in euc-kr
_korean_day   = u'\uc77c' # c0cf in euc-kr
_korean_am    = u'\uc624\uc804' # bfc0 c0fc in euc-kr
_korean_pm    = u'\uc624\ud6c4' # bfc0 c8c4 in euc-kr

_korean_onblog_date_re = \
    re.compile(u'(\d{4})%s\s+(\d{2})%s\s+(\d{2})%s\s+(\d{2}):(\d{2}):(\d{2})' % \
               (_korean_year, _korean_month, _korean_day))
_korean_nate_date_re = \
    re.compile(u'(\d{4})-(\d{2})-(\d{2})\s+(%s|%s)\s+(\d{,2}):(\d{,2}):(\d{,2})' % \
               (_korean_am, _korean_pm))
def _parse_date_onblog(dateString):
    '''Parse a string according to the OnBlog 8-bit date format'''
    m = _korean_onblog_date_re.match(dateString)
    if not m: return
    w3dtfdate = u'%(year)s-%(month)s-%(day)sT%(hour)s:%(minute)s:%(second)s%(zonediff)s' % \
                {u'year': m.group(1), u'month': m.group(2), u'day': m.group(3),\
                 u'hour': m.group(4), u'minute': m.group(5), u'second': m.group(6),\
                 u'zonediff': u'+09:00'}
    if _debug: sys.stderr.write(u'OnBlog date parsed as: %s\n' % w3dtfdate)
    return _parse_date_w3dtf(w3dtfdate)
registerDateHandler(_parse_date_onblog)

def _parse_date_nate(dateString):
    '''Parse a string according to the Nate 8-bit date format'''
    m = _korean_nate_date_re.match(dateString)
    if not m: return
    hour = int(m.group(5))
    ampm = m.group(4)
    if (ampm == _korean_pm):
        hour += 12
    hour = unicode(hour)
    if len(hour) == 1:
        hour = u'0' + hour
    w3dtfdate = u'%(year)s-%(month)s-%(day)sT%(hour)s:%(minute)s:%(second)s%(zonediff)s' % \
                {u'year': m.group(1), u'month': m.group(2), u'day': m.group(3),\
                 u'hour': hour, u'minute': m.group(6), u'second': m.group(7),\
                 u'zonediff': u'+09:00'}
    if _debug: sys.stderr.write(u'Nate date parsed as: %s\n' % w3dtfdate)
    return _parse_date_w3dtf(w3dtfdate)
registerDateHandler(_parse_date_nate)

_mssql_date_re = \
    re.compile(u'(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})(\.\d+)?')
def _parse_date_mssql(dateString):
    '''Parse a string according to the MS SQL date format'''
    m = _mssql_date_re.match(dateString)
    if not m: return
    w3dtfdate = u'%(year)s-%(month)s-%(day)sT%(hour)s:%(minute)s:%(second)s%(zonediff)s' % \
                {u'year': m.group(1), u'month': m.group(2), u'day': m.group(3),\
                 u'hour': m.group(4), u'minute': m.group(5), u'second': m.group(6),\
                 u'zonediff': u'+09:00'}
    if _debug: sys.stderr.write(u'MS SQL date parsed as: %s\n' % w3dtfdate)
    return _parse_date_w3dtf(w3dtfdate)
registerDateHandler(_parse_date_mssql)

# Unicode strings for Greek date strings
_greek_months = \
  { \
   u'\u0399\u03b1\u03bd': u'Jan',       # c9e1ed in iso-8859-7
   u'\u03a6\u03b5\u03b2': u'Feb',       # d6e5e2 in iso-8859-7
   u'\u039c\u03ac\u03ce': u'Mar',       # ccdcfe in iso-8859-7
   u'\u039c\u03b1\u03ce': u'Mar',       # cce1fe in iso-8859-7
   u'\u0391\u03c0\u03c1': u'Apr',       # c1f0f1 in iso-8859-7
   u'\u039c\u03ac\u03b9': u'May',       # ccdce9 in iso-8859-7
   u'\u039c\u03b1\u03ca': u'May',       # cce1fa in iso-8859-7
   u'\u039c\u03b1\u03b9': u'May',       # cce1e9 in iso-8859-7
   u'\u0399\u03bf\u03cd\u03bd': u'Jun', # c9effded in iso-8859-7
   u'\u0399\u03bf\u03bd': u'Jun',       # c9efed in iso-8859-7
   u'\u0399\u03bf\u03cd\u03bb': u'Jul', # c9effdeb in iso-8859-7
   u'\u0399\u03bf\u03bb': u'Jul',       # c9f9eb in iso-8859-7
   u'\u0391\u03cd\u03b3': u'Aug',       # c1fde3 in iso-8859-7
   u'\u0391\u03c5\u03b3': u'Aug',       # c1f5e3 in iso-8859-7
   u'\u03a3\u03b5\u03c0': u'Sep',       # d3e5f0 in iso-8859-7
   u'\u039f\u03ba\u03c4': u'Oct',       # cfeaf4 in iso-8859-7
   u'\u039d\u03bf\u03ad': u'Nov',       # cdefdd in iso-8859-7
   u'\u039d\u03bf\u03b5': u'Nov',       # cdefe5 in iso-8859-7
   u'\u0394\u03b5\u03ba': u'Dec',       # c4e5ea in iso-8859-7
  }

_greek_wdays = \
  { \
   u'\u039a\u03c5\u03c1': u'Sun', # caf5f1 in iso-8859-7
   u'\u0394\u03b5\u03c5': u'Mon', # c4e5f5 in iso-8859-7
   u'\u03a4\u03c1\u03b9': u'Tue', # d4f1e9 in iso-8859-7
   u'\u03a4\u03b5\u03c4': u'Wed', # d4e5f4 in iso-8859-7
   u'\u03a0\u03b5\u03bc': u'Thu', # d0e5ec in iso-8859-7
   u'\u03a0\u03b1\u03c1': u'Fri', # d0e1f1 in iso-8859-7
   u'\u03a3\u03b1\u03b2': u'Sat', # d3e1e2 in iso-8859-7
  }

_greek_date_format_re = \
    re.compile(u'([^,]+),\s+(\d{2})\s+([^\s]+)\s+(\d{4})\s+(\d{2}):(\d{2}):(\d{2})\s+([^\s]+)')

def _parse_date_greek(dateString):
    '''Parse a string according to a Greek 8-bit date format.'''
    m = _greek_date_format_re.match(dateString)
    if not m: return
    try:
        wday = _greek_wdays[m.group(1)]
        month = _greek_months[m.group(3)]
    except:
        return
    rfc822date = u'%(wday)s, %(day)s %(month)s %(year)s %(hour)s:%(minute)s:%(second)s %(zonediff)s' % \
                 {u'wday': wday, u'day': m.group(2), u'month': month, u'year': m.group(4),\
                  u'hour': m.group(5), u'minute': m.group(6), u'second': m.group(7),\
                  u'zonediff': m.group(8)}
    if _debug: sys.stderr.write(u'Greek date parsed as: %s\n' % rfc822date)
    return _parse_date_rfc822(rfc822date)
registerDateHandler(_parse_date_greek)

# Unicode strings for Hungarian date strings
_hungarian_months = \
  { \
    u'janu\u00e1r':   u'01',  # e1 in iso-8859-2
    u'febru\u00e1ri': u'02',  # e1 in iso-8859-2
    u'm\u00e1rcius':  u'03',  # e1 in iso-8859-2
    u'\u00e1prilis':  u'04',  # e1 in iso-8859-2
    u'm\u00e1ujus':   u'05',  # e1 in iso-8859-2
    u'j\u00fanius':   u'06',  # fa in iso-8859-2
    u'j\u00falius':   u'07',  # fa in iso-8859-2
    u'augusztus':     u'08',
    u'szeptember':    u'09',
    u'okt\u00f3ber':  u'10',  # f3 in iso-8859-2
    u'november':      u'11',
    u'december':      u'12',
  }

_hungarian_date_format_re = \
  re.compile(u'(\d{4})-([^-]+)-(\d{,2})T(\d{,2}):(\d{2})((\+|-)(\d{,2}:\d{2}))')

def _parse_date_hungarian(dateString):
    '''Parse a string according to a Hungarian 8-bit date format.'''
    m = _hungarian_date_format_re.match(dateString)
    if not m: return
    try:
        month = _hungarian_months[m.group(2)]
        day = m.group(3)
        if len(day) == 1:
            day = u'0' + day
        hour = m.group(4)
        if len(hour) == 1:
            hour = u'0' + hour
    except:
        return
    w3dtfdate = u'%(year)s-%(month)s-%(day)sT%(hour)s:%(minute)s%(zonediff)s' % \
                {u'year': m.group(1), u'month': month, u'day': day,\
                 u'hour': hour, u'minute': m.group(5),\
                 u'zonediff': m.group(6)}
    if _debug: sys.stderr.write(u'Hungarian date parsed as: %s\n' % w3dtfdate)
    return _parse_date_w3dtf(w3dtfdate)
registerDateHandler(_parse_date_hungarian)

# W3DTF-style date parsing adapted from PyXML xml.utils.iso8601, written by
# Drake and licensed under the Python license.  Removed all range checking
# for month, day, hour, minute, and second, since mktime will normalize
# these later
def _parse_date_w3dtf(dateString):
    def __extract_date(m):
        year = int(m.group(u'year'))
        if year < 100:
            year = 100 * int(time.gmtime()[0] / 100) + int(year)
        if year < 1000:
            return 0, 0, 0
        julian = m.group(u'julian')
        if julian:
            julian = int(julian)
            month = julian / 30 + 1
            day = julian % 30 + 1
            jday = None
            while jday != julian:
                t = time.mktime((year, month, day, 0, 0, 0, 0, 0, 0))
                jday = time.gmtime(t)[-2]
                diff = abs(jday - julian)
                if jday > julian:
                    if diff < day:
                        day = day - diff
                    else:
                        month = month - 1
                        day = 31
                elif jday < julian:
                    if day + diff < 28:
                       day = day + diff
                    else:
                        month = month + 1
            return year, month, day
        month = m.group(u'month')
        day = 1
        if month is None:
            month = 1
        else:
            month = int(month)
            day = m.group(u'day')
            if day:
                day = int(day)
            else:
                day = 1
        return year, month, day

    def __extract_time(m):
        if not m:
            return 0, 0, 0
        hours = m.group(u'hours')
        if not hours:
            return 0, 0, 0
        hours = int(hours)
        minutes = int(m.group(u'minutes'))
        seconds = m.group(u'seconds')
        if seconds:
            seconds = int(seconds)
        else:
            seconds = 0
        return hours, minutes, seconds

    def __extract_tzd(m):
        '''Return the Time Zone Designator as an offset in seconds from UTC.'''
        if not m:
            return 0
        tzd = m.group(u'tzd')
        if not tzd:
            return 0
        if tzd == u'Z':
            return 0
        hours = int(m.group(u'tzdhours'))
        minutes = m.group(u'tzdminutes')
        if minutes:
            minutes = int(minutes)
        else:
            minutes = 0
        offset = (hours*60 + minutes) * 60
        if tzd[0] == u'+':
            return -offset
        return offset

    __date_re = (u'(?P<year>\d\d\d\d)'
                 u'(?:(?P<dsep>-|)'
                 u'(?:(?P<julian>\d\d\d)'
                 u'|(?P<month>\d\d)(?:(?P=dsep)(?P<day>\d\d))?))?')
    __tzd_re = u'(?P<tzd>[-+](?P<tzdhours>\d\d)(?::?(?P<tzdminutes>\d\d))|Z)'
    __tzd_rx = re.compile(__tzd_re)
    __time_re = (u'(?P<hours>\d\d)(?P<tsep>:|)(?P<minutes>\d\d)'
                 u'(?:(?P=tsep)(?P<seconds>\d\d(?:[.,]\d+)?))?'
                 + __tzd_re)
    __datetime_re = u'%s(?:T%s)?' % (__date_re, __time_re)
    __datetime_rx = re.compile(__datetime_re)
    m = __datetime_rx.match(dateString)
    if (m is None) or (m.group() != dateString): return
    gmt = __extract_date(m) + __extract_time(m) + (0, 0, 0)
    if gmt[0] == 0: return
    return time.gmtime(time.mktime(gmt) + __extract_tzd(m) - time.timezone)
registerDateHandler(_parse_date_w3dtf)

def _parse_date_rfc822(dateString):
    '''Parse an RFC822, RFC1123, RFC2822, or asctime-style date'''
    data = dateString.split()
    if data[0][-1] in (u',', u'.') or data[0].lower() in rfc822._daynames:
        del data[0]
    if len(data) == 4:
        s = data[3]
        i = s.find(u'+')
        if i > 0:
            data[3:] = [s[:i], s[i+1:]]
        else:
            data.append(u'')
        dateString = u" ".join(data)
    if len(data) < 5:
        dateString += u' 00:00:00 GMT'
    tm = rfc822.parsedate_tz(dateString)
    if tm:
        return time.gmtime(rfc822.mktime_tz(tm))
# rfc822.py defines several time zones, but we define some extra ones.
# u'ET' is equivalent to u'EST', etc.
_additional_timezones = {u'AT': -400, u'ET': -500, u'CT': -600, u'MT': -700, u'PT': -800}
rfc822._timezones.update(_additional_timezones)
registerDateHandler(_parse_date_rfc822)

def _parse_date(dateString):
    '''Parses a variety of date formats into a 9-tuple in GMT'''
    for handler in _date_handlers:
        try:
            date9tuple = handler(dateString)
            if not date9tuple: continue
            if len(date9tuple) != 9:
                if _debug: sys.stderr.write(u'date handler function must return 9-tuple\n')
                raise ValueError
            map(int, date9tuple)
            return date9tuple
        except Exception, e:
            if _debug: sys.stderr.write(u'%s raised %s\n' % (handler.__name__, repr(e)))
            pass
    return None

def _getCharacterEncoding(http_headers, xml_data):
    '''Get the character encoding of the XML document

    http_headers is a dictionary
    xml_data is a raw string (not Unicode)

    This is so much trickier than it sounds, it's not even funny.
    According to RFC 3023 ('XML Media Types'), if the HTTP Content-Type
    is application/xml, application/*+xml,
    application/xml-external-parsed-entity, or application/xml-dtd,
    the encoding given in the charset parameter of the HTTP Content-Type
    takes precedence over the encoding given in the XML prefix within the
    document, and defaults to 'utf-8' if neither are specified.  But, if
    the HTTP Content-Type is text/xml, text/*+xml, or
    text/xml-external-parsed-entity, the encoding given in the XML prefix
    within the document is ALWAYS IGNORED and only the encoding given in
    the charset parameter of the HTTP Content-Type header should be
    respected, and it defaults to 'us-ascii' if not specified.

    Furthermore, discussion on the atom-syntax mailing list with the
    author of RFC 3023 leads me to the conclusion that any document
    served with a Content-Type of text/* and no charset parameter
    must be treated as us-ascii.  (We now do this.)  And also that it
    must always be flagged as non-well-formed.  (We now do this too.)

    If Content-Type is unspecified (input was local file or non-HTTP source)
    or unrecognized (server just got it totally wrong), then go by the
    encoding given in the XML prefix of the document and default to
    'iso-8859-1' as per the HTTP specification (RFC 2616).

    Then, assuming we didn't find a character encoding in the HTTP headers
    (and the HTTP Content-type allowed us to look in the body), we need
    to sniff the first few bytes of the XML data and try to determine
    whether the encoding is ASCII-compatible.  Section F of the XML
    specification shows the way here:
    http://www.w3.org/TR/REC-xml/#sec-guessing-no-ext-info

    If the sniffed encoding is not ASCII-compatible, we need to make it
    ASCII compatible so that we can sniff further into the XML declaration
    to find the encoding attribute, which will tell us the true encoding.

    Of course, none of this guarantees that we will be able to parse the
    feed in the declared character encoding (assuming it was declared
    correctly, which many are not).  CJKCodecs and iconv_codec help a lot;
    you should definitely install them if you can.
    http://cjkpython.i18n.org/
    '''

    def _parseHTTPContentType(content_type):
        '''takes HTTP Content-Type header and returns (content type, charset)

        If no charset is specified, returns (content type, '')
        If no content type is specified, returns ('', '')
        Both return parameters are guaranteed to be lowercase strings
        '''
        content_type = content_type or u''
        content_type, params = cgi.parse_header(content_type)
        return content_type, params.get(u'charset', u'').replace(u"'", u'')

    sniffed_xml_encoding = u''
    xml_encoding = u''
    true_encoding = u''
    http_content_type, http_encoding = _parseHTTPContentType(http_headers.get(u'content-type'))
    # Must sniff for non-ASCII-compatible character encodings before
    # searching for XML declaration.  This heuristic is defined in
    # section F of the XML specification:
    # http://www.w3.org/TR/REC-xml/#sec-guessing-no-ext-info
    try:
        if xml_data[:4] == u'\x4c\x6f\xa7\x94':
            # EBCDIC
            xml_data = _ebcdic_to_ascii(xml_data)
        elif xml_data[:4] == u'\x00\x3c\x00\x3f':
            # UTF-16BE
            sniffed_xml_encoding = u'utf-16be'
            xml_data = unicode(xml_data, u'utf-16be').encode(u'utf-8')
        elif (len(xml_data) >= 4) and (xml_data[:2] == u'\xfe\xff') and (xml_data[2:4] != u'\x00\x00'):
            # UTF-16BE with BOM
            sniffed_xml_encoding = u'utf-16be'
            xml_data = unicode(xml_data[2:], u'utf-16be').encode(u'utf-8')
        elif xml_data[:4] == u'\x3c\x00\x3f\x00':
            # UTF-16LE
            sniffed_xml_encoding = u'utf-16le'
            xml_data = unicode(xml_data, u'utf-16le').encode(u'utf-8')
        elif (len(xml_data) >= 4) and (xml_data[:2] == u'\xff\xfe') and (xml_data[2:4] != u'\x00\x00'):
            # UTF-16LE with BOM
            sniffed_xml_encoding = u'utf-16le'
            xml_data = unicode(xml_data[2:], u'utf-16le').encode(u'utf-8')
        elif xml_data[:4] == u'\x00\x00\x00\x3c':
            # UTF-32BE
            sniffed_xml_encoding = u'utf-32be'
            xml_data = unicode(xml_data, u'utf-32be').encode(u'utf-8')
        elif xml_data[:4] == u'\x3c\x00\x00\x00':
            # UTF-32LE
            sniffed_xml_encoding = u'utf-32le'
            xml_data = unicode(xml_data, u'utf-32le').encode(u'utf-8')
        elif xml_data[:4] == u'\x00\x00\xfe\xff':
            # UTF-32BE with BOM
            sniffed_xml_encoding = u'utf-32be'
            xml_data = unicode(xml_data[4:], u'utf-32be').encode(u'utf-8')
        elif xml_data[:4] == u'\xff\xfe\x00\x00':
            # UTF-32LE with BOM
            sniffed_xml_encoding = u'utf-32le'
            xml_data = unicode(xml_data[4:], u'utf-32le').encode(u'utf-8')
        elif xml_data[:3] == u'\xef\xbb\xbf':
            # UTF-8 with BOM
            sniffed_xml_encoding = u'utf-8'
            xml_data = unicode(xml_data[3:], u'utf-8').encode(u'utf-8')
        else:
            # ASCII-compatible
            pass
        xml_encoding_match = re.compile(u'^<\?.*encoding=[\'"](.*?)[\'"].*\?>').match(xml_data)
    except:
        xml_encoding_match = None
    if xml_encoding_match:
        xml_encoding = xml_encoding_match.groups()[0].lower()
        if sniffed_xml_encoding and (xml_encoding in (u'iso-10646-ucs-2', u'ucs-2', u'csunicode', u'iso-10646-ucs-4', u'ucs-4', u'csucs4', u'utf-16', u'utf-32', u'utf_16', u'utf_32', u'utf16', u'u16')):
            xml_encoding = sniffed_xml_encoding
    acceptable_content_type = 0
    application_content_types = (u'application/xml', u'application/xml-dtd', u'application/xml-external-parsed-entity')
    text_content_types = (u'text/xml', u'text/xml-external-parsed-entity')
    if (http_content_type in application_content_types) or \
       (http_content_type.startswith(u'application/') and http_content_type.endswith(u'+xml')):
        acceptable_content_type = 1
        true_encoding = http_encoding or xml_encoding or u'utf-8'
    elif (http_content_type in text_content_types) or \
         (http_content_type.startswith(u'text/')) and http_content_type.endswith(u'+xml'):
        acceptable_content_type = 1
        true_encoding = http_encoding or u'us-ascii'
    elif http_content_type.startswith(u'text/'):
        true_encoding = http_encoding or u'us-ascii'
    elif http_headers and (not http_headers.has_key(u'content-type')):
        true_encoding = xml_encoding or u'iso-8859-1'
    else:
        true_encoding = xml_encoding or u'utf-8'
    return true_encoding, http_encoding, xml_encoding, sniffed_xml_encoding, acceptable_content_type

def _toUTF8(data, encoding):
    '''Changes an XML data stream on the fly to specify a new encoding

    data is a raw sequence of bytes (not Unicode) that is presumed to be in %encoding already
    encoding is a string recognized by encodings.aliases
    '''
    if _debug: sys.stderr.write(u'entering _toUTF8, trying encoding %s\n' % encoding)
    # strip Byte Order Mark (if present)
    if (len(data) >= 4) and (data[:2] == u'\xfe\xff') and (data[2:4] != u'\x00\x00'):
        if _debug:
            sys.stderr.write(u'stripping BOM\n')
            if encoding != u'utf-16be':
                sys.stderr.write(u'trying utf-16be instead\n')
        encoding = u'utf-16be'
        data = data[2:]
    elif (len(data) >= 4) and (data[:2] == u'\xff\xfe') and (data[2:4] != u'\x00\x00'):
        if _debug:
            sys.stderr.write(u'stripping BOM\n')
            if encoding != u'utf-16le':
                sys.stderr.write(u'trying utf-16le instead\n')
        encoding = u'utf-16le'
        data = data[2:]
    elif data[:3] == u'\xef\xbb\xbf':
        if _debug:
            sys.stderr.write(u'stripping BOM\n')
            if encoding != u'utf-8':
                sys.stderr.write(u'trying utf-8 instead\n')
        encoding = u'utf-8'
        data = data[3:]
    elif data[:4] == u'\x00\x00\xfe\xff':
        if _debug:
            sys.stderr.write(u'stripping BOM\n')
            if encoding != u'utf-32be':
                sys.stderr.write(u'trying utf-32be instead\n')
        encoding = u'utf-32be'
        data = data[4:]
    elif data[:4] == u'\xff\xfe\x00\x00':
        if _debug:
            sys.stderr.write(u'stripping BOM\n')
            if encoding != u'utf-32le':
                sys.stderr.write(u'trying utf-32le instead\n')
        encoding = u'utf-32le'
        data = data[4:]
    newdata = unicode(data, encoding)
    if _debug: sys.stderr.write(u'successfully converted %s data to unicode\n' % encoding)
    declmatch = re.compile(u'^<\?xml[^>]*?>')
    newdecl = '''<?xml version='1.0' encoding='utf-8'?>'''
    if declmatch.search(newdata):
        newdata = declmatch.sub(newdecl, newdata)
    else:
        newdata = newdecl + u'\n' + newdata
    return newdata.encode(u'utf-8')

def _stripDoctype(data):
    '''Strips DOCTYPE from XML document, returns (rss_version, stripped_data)

    rss_version may be 'rss091n' or None
    stripped_data is the same XML document, minus the DOCTYPE
    '''
    entity_pattern = re.compile(r'<!ENTITY([^>]*?)>', re.MULTILINE)
    data = entity_pattern.sub(u'', data)
    doctype_pattern = re.compile(r'<!DOCTYPE([^>]*?)>', re.MULTILINE)
    doctype_results = doctype_pattern.findall(data)
    doctype = doctype_results and doctype_results[0] or u''
    if doctype.lower().count(u'netscape'):
        version = u'rss091n'
    else:
        version = None
    data = doctype_pattern.sub(u'', data)
    return version, data

def parse(url_file_stream_or_string, etag=None, modified=None, agent=None, referrer=None, handlers=[]):
    '''Parse a feed from a URL, file, stream, or string'''
    result = FeedParserDict()
    result[u'feed'] = FeedParserDict()
    result[u'entries'] = []
    if _XML_AVAILABLE:
        result[u'bozo'] = 0
    if type(handlers) == types.InstanceType:
        handlers = [handlers]
    try:
        f = _open_resource(url_file_stream_or_string, etag, modified, agent, referrer, handlers)
        data = f.read()
    except Exception, e:
        result[u'bozo'] = 1
        result[u'bozo_exception'] = e
        data = u''
        f = None

    # if feed is gzip-compressed, decompress it
    if f and data and hasattr(f, u'headers'):
        if gzip and f.headers.get(u'content-encoding', u'') == u'gzip':
            try:
                data = gzip.GzipFile(fileobj=_StringIO(data)).read()
            except Exception, e:
                # Some feeds claim to be gzipped but they're not, so
                # we get garbage.  Ideally, we should re-request the
                # feed without the u'Accept-encoding: gzip' header,
                # but we don't.
                result[u'bozo'] = 1
                result[u'bozo_exception'] = e
                data = u''
        elif zlib and f.headers.get(u'content-encoding', u'') == u'deflate':
            try:
                data = zlib.decompress(data, -zlib.MAX_WBITS)
            except Exception, e:
                result[u'bozo'] = 1
                result[u'bozo_exception'] = e
                data = u''

    # save HTTP headers
    if hasattr(f, u'info'):
        info = f.info()
        result[u'etag'] = info.getheader(u'ETag')
        last_modified = info.getheader(u'Last-Modified')
        if last_modified:
            result[u'modified'] = _parse_date(last_modified)
    if hasattr(f, u'url'):
        result[u'href'] = f.url
        result[u'status'] = 200
    if hasattr(f, u'status'):
        result[u'status'] = f.status
    if hasattr(f, u'headers'):
        result[u'headers'] = f.headers.dict
    if hasattr(f, u'close'):
        f.close()

    # there are four encodings to keep track of:
    # - http_encoding is the encoding declared in the Content-Type HTTP header
    # - xml_encoding is the encoding declared in the <?xml declaration
    # - sniffed_encoding is the encoding sniffed from the first 4 bytes of the XML data
    # - result[u'encoding'] is the actual encoding, as per RFC 3023 and a variety of other conflicting specifications
    http_headers = result.get(u'headers', {})
    result[u'encoding'], http_encoding, xml_encoding, sniffed_xml_encoding, acceptable_content_type = \
        _getCharacterEncoding(http_headers, data)
    if http_headers and (not acceptable_content_type):
        if http_headers.has_key(u'content-type'):
            bozo_message = u'%s is not an XML media type' % http_headers[u'content-type']
        else:
            bozo_message = u'no Content-type specified'
        result[u'bozo'] = 1
        result[u'bozo_exception'] = NonXMLContentType(bozo_message)

    result[u'version'], data = _stripDoctype(data)

    baseuri = http_headers.get(u'content-location', result.get(u'href'))
    baselang = http_headers.get(u'content-language', None)

    # if server sent 304, we're done
    if result.get(u'status', 0) == 304:
        result[u'version'] = u''
        result[u'debug_message'] = u'The feed has not changed since you last checked, ' + \
            u'so the server sent no data.  This is a feature, not a bug!'
        return result

    # if there was a problem downloading, we're done
    if not data:
        return result

    # determine character encoding
    use_strict_parser = 0
    known_encoding = 0
    tried_encodings = []
    # try: HTTP encoding, declared XML encoding, encoding sniffed from BOM
    for proposed_encoding in (result[u'encoding'], xml_encoding, sniffed_xml_encoding):
        if not proposed_encoding: continue
        if proposed_encoding in tried_encodings: continue
        tried_encodings.append(proposed_encoding)
        try:
            data = _toUTF8(data, proposed_encoding)
            known_encoding = use_strict_parser = 1
            break
        except:
            pass
    # if no luck and we have auto-detection library, try that
    if (not known_encoding) and chardet:
        try:
            proposed_encoding = chardet.detect(data)[u'encoding']
            if proposed_encoding and (proposed_encoding not in tried_encodings):
                tried_encodings.append(proposed_encoding)
                data = _toUTF8(data, proposed_encoding)
                known_encoding = use_strict_parser = 1
        except:
            pass
    # if still no luck and we haven't tried utf-8 yet, try that
    if (not known_encoding) and (u'utf-8' not in tried_encodings):
        try:
            proposed_encoding = u'utf-8'
            tried_encodings.append(proposed_encoding)
            data = _toUTF8(data, proposed_encoding)
            known_encoding = use_strict_parser = 1
        except:
            pass
    # if still no luck and we haven't tried windows-1252 yet, try that
    if (not known_encoding) and (u'windows-1252' not in tried_encodings):
        try:
            proposed_encoding = u'windows-1252'
            tried_encodings.append(proposed_encoding)
            data = _toUTF8(data, proposed_encoding)
            known_encoding = use_strict_parser = 1
        except:
            pass
    # if still no luck, give up
    if not known_encoding:
        result[u'bozo'] = 1
        result[u'bozo_exception'] = CharacterEncodingUnknown( \
            u'document encoding unknown, I tried ' + \
            u'%s, %s, utf-8, and windows-1252 but nothing worked' % \
            (result[u'encoding'], xml_encoding))
        result[u'encoding'] = u''
    elif proposed_encoding != result[u'encoding']:
        result[u'bozo'] = 1
        result[u'bozo_exception'] = CharacterEncodingOverride( \
            u'documented declared as %s, but parsed as %s' % \
            (result[u'encoding'], proposed_encoding))
        result[u'encoding'] = proposed_encoding

    if not _XML_AVAILABLE:
        use_strict_parser = 0
    if use_strict_parser:
        # initialize the SAX parser
        feedparser = _StrictFeedParser(baseuri, baselang, u'utf-8')
        saxparser = xml.sax.make_parser(PREFERRED_XML_PARSERS)
        saxparser.setFeature(xml.sax.handler.feature_namespaces, 1)
        saxparser.setContentHandler(feedparser)
        saxparser.setErrorHandler(feedparser)
        source = xml.sax.xmlreader.InputSource()
        source.setByteStream(_StringIO(data))
        if hasattr(saxparser, u'_ns_stack'):
            # work around bug in built-in SAX parser (doesn't recognize xml: namespace)
            # PyXML doesnu't have this problem, and it doesn't have _ns_stack either
            saxparser._ns_stack.append({u'http://www.w3.org/XML/1998/namespace':u'xml'})
        try:
            saxparser.parse(source)
        except Exception, e:
            if _debug:
                import traceback
                traceback.print_stack()
                traceback.print_exc()
                sys.stderr.write(u'xml parsing failed\n')
            result[u'bozo'] = 1
            result[u'bozo_exception'] = feedparser.exc or e
            use_strict_parser = 0
    if not use_strict_parser:
        feedparser = _LooseFeedParser(baseuri, baselang, known_encoding and u'utf-8' or u'')
        feedparser.feed(data)
    result[u'feed'] = feedparser.feeddata
    result[u'entries'] = feedparser.entries
    result[u'version'] = result[u'version'] or feedparser.version
    result[u'namespaces'] = feedparser.namespacesInUse
    return result

if __name__ == u'__main__':
    if not sys.argv[1:]:
        print __doc__
        sys.exit(0)
    else:
        urls = sys.argv[1:]
    zopeCompatibilityHack()
    from pprint import pprint
    for url in urls:
        print url
        print
        result = parse(url)
        pprint(result)
        print

#REVISION HISTORY
#1.0 - 9/27/2002 - MAP - fixed namespace processing on prefixed RSS 2.0 elements,
#  added Simon Fell's test suite
#1.1 - 9/29/2002 - MAP - fixed infinite loop on incomplete CDATA sections
#2.0 - 10/19/2002
#  JD - use inchannel to watch out for image and textinput elements which can
#  also contain title, link, and description elements
#  JD - check for isPermaLink=u'false' attribute on guid elements
#  JD - replaced openAnything with open_resource supporting ETag and
#  If-Modified-Since request headers
#  JD - parse now accepts etag, modified, agent, and referrer optional
#  arguments
#  JD - modified parse to return a dictionary instead of a tuple so that any
#  etag or modified information can be returned and cached by the caller
#2.0.1 - 10/21/2002 - MAP - changed parse() so that if we don't get anything
#  because of etag/modified, return the old etag/modified to the caller to
#  indicate why nothing is being returned
#2.0.2 - 10/21/2002 - JB - added the inchannel to the if statement, otherwise its
#  useless.  Fixes the problem JD was addressing by adding it.
#2.1 - 11/14/2002 - MAP - added gzip support
#2.2 - 1/27/2003 - MAP - added attribute support, admin:generatorAgent.
#  start_admingeneratoragent is an example of how to handle elements with
#  only attributes, no content.
#2.3 - 6/11/2003 - MAP - added USER_AGENT for default (if caller doesn't specify);
#  also, make sure we send the User-Agent even if urllib2 isn't available.
#  Match any variation of backend.userland.com/rss namespace.
#2.3.1 - 6/12/2003 - MAP - if item has both link and guid, return both as-is.
#2.4 - 7/9/2003 - MAP - added preliminary Pie/Atom/Echo support based on Sam Ruby's
#  snapshot of July 1 <http://www.intertwingly.net/blog/1506.html>; changed
#  project name
#2.5 - 7/25/2003 - MAP - changed to Python license (all contributors agree);
#  removed unnecessary urllib code -- urllib2 should always be available anyway;
#  return actual url, status, and full HTTP headers (as result[u'url'],
#  result[u'status'], and result[u'headers']) if parsing a remote feed over HTTP --
#  this should pass all the HTTP tests at <http://diveintomark.org/tests/client/http/>;
#  added the latest namespace-of-the-week for RSS 2.0
#2.5.1 - 7/26/2003 - RMK - clear opener.addheaders so we only send our custom
#  User-Agent (otherwise urllib2 sends two, which confuses some servers)
#2.5.2 - 7/28/2003 - MAP - entity-decode inline xml properly; added support for
#  inline <xhtml:body> and <xhtml:div> as used in some RSS 2.0 feeds
#2.5.3 - 8/6/2003 - TvdV - patch to track whether we're inside an image or
#  textInput, and also to return the character encoding (if specified)
#2.6 - 1/1/2004 - MAP - dc:author support (MarekK); fixed bug tracking
#  nested divs within content (JohnD); fixed missing sys import (JohanS);
#  fixed regular expression to capture XML character encoding (Andrei);
#  added support for Atom 0.3-style links; fixed bug with textInput tracking;
#  added support for cloud (MartijnP); added support for multiple
#  category/dc:subject (MartijnP); normalize content model: u'description' gets
#  description (which can come from description, summary, or full content if no
#  description), u'content' gets dict of base/language/type/value (which can come
#  from content:encoded, xhtml:body, content, or fullitem);
#  fixed bug matching arbitrary Userland namespaces; added xml:base and xml:lang
#  tracking; fixed bug tracking unknown tags; fixed bug tracking content when
#  <content> element is not in default namespace (like Pocketsoap feed);
#  resolve relative URLs in link, guid, docs, url, comments, wfw:comment,
#  wfw:commentRSS; resolve relative URLs within embedded HTML markup in
#  description, xhtml:body, content, content:encoded, title, subtitle,
#  summary, info, tagline, and copyright; added support for pingback and
#  trackback namespaces
#2.7 - 1/5/2004 - MAP - really added support for trackback and pingback
#  namespaces, as opposed to 2.6 when I said I did but didn't really;
#  sanitize HTML markup within some elements; added mxTidy support (if
#  installed) to tidy HTML markup within some elements; fixed indentation
#  bug in _parse_date (FazalM); use socket.setdefaulttimeout if available
#  (FazalM); universal date parsing and normalization (FazalM): u'created', modified',
#  u'issued' are parsed into 9-tuple date format and stored in u'created_parsed',
#  u'modified_parsed', and u'issued_parsed'; u'date' is duplicated in u'modified'
#  and vice-versa; u'date_parsed' is duplicated in u'modified_parsed' and vice-versa
#2.7.1 - 1/9/2004 - MAP - fixed bug handling &quot; and &apos;.  fixed memory
#  leak not closing url opener (JohnD); added dc:publisher support (MarekK);
#  added admin:errorReportsTo support (MarekK); Python 2.1 dict support (MarekK)
#2.7.4 - 1/14/2004 - MAP - added workaround for improperly formed <br/> tags in
#  encoded HTML (skadz); fixed unicode handling in normalize_attrs (ChrisL);
#  fixed relative URI processing for guid (skadz); added ICBM support; added
#  base64 support
#2.7.5 - 1/15/2004 - MAP - added workaround for malformed DOCTYPE (seen on many
#  blogspot.com sites); added _debug variable
#2.7.6 - 1/16/2004 - MAP - fixed bug with StringIO importing
#3.0b3 - 1/23/2004 - MAP - parse entire feed with real XML parser (if available);
#  added several new supported namespaces; fixed bug tracking naked markup in
#  description; added support for enclosure; added support for source; re-added
#  support for cloud which got dropped somehow; added support for expirationDate
#3.0b4 - 1/26/2004 - MAP - fixed xml:lang inheritance; fixed multiple bugs tracking
#  xml:base URI, one for documents that don't define one explicitly and one for
#  documents that define an outer and an inner xml:base that goes out of scope
#  before the end of the document
#3.0b5 - 1/26/2004 - MAP - fixed bug parsing multiple links at feed level
#3.0b6 - 1/27/2004 - MAP - added feed type and version detection, result[u'version']
#  will be one of SUPPORTED_VERSIONS.keys() or empty string if unrecognized;
#  added support for creativeCommons:license and cc:license; added support for
#  full Atom content model in title, tagline, info, copyright, summary; fixed bug
#  with gzip encoding (not always telling server we support it when we do)
#3.0b7 - 1/28/2004 - MAP - support Atom-style author element in author_detail
#  (dictionary of u'name', u'url', u'email'); map author to author_detail if author
#  contains name + email address
#3.0b8 - 1/28/2004 - MAP - added support for contributor
#3.0b9 - 1/29/2004 - MAP - fixed check for presence of dict function; added
#  support for summary
#3.0b10 - 1/31/2004 - MAP - incorporated ISO-8601 date parsing routines from
#  xml.util.iso8601
#3.0b11 - 2/2/2004 - MAP - added u'rights' to list of elements that can contain
#  dangerous markup; fiddled with decodeEntities (not right); liberalized
#  date parsing even further
#3.0b12 - 2/6/2004 - MAP - fiddled with decodeEntities (still not right);
#  added support to Atom 0.2 subtitle; added support for Atom content model
#  in copyright; better sanitizing of dangerous HTML elements with end tags
#  (script, frameset)
#3.0b13 - 2/8/2004 - MAP - better handling of empty HTML tags (br, hr, img,
#  etc.) in embedded markup, in either HTML or XHTML form (<br>, <br/>, <br />)
#3.0b14 - 2/8/2004 - MAP - fixed CDATA handling in non-wellformed feeds under
#  Python 2.1
#3.0b15 - 2/11/2004 - MAP - fixed bug resolving relative links in wfw:commentRSS;
#  fixed bug capturing author and contributor URL; fixed bug resolving relative
#  links in author and contributor URL; fixed bug resolvin relative links in
#  generator URL; added support for recognizing RSS 1.0; passed Simon Fell's
#  namespace tests, and included them permanently in the test suite with his
#  permission; fixed namespace handling under Python 2.1
#3.0b16 - 2/12/2004 - MAP - fixed support for RSS 0.90 (broken in b15)
#3.0b17 - 2/13/2004 - MAP - determine character encoding as per RFC 3023
#3.0b18 - 2/17/2004 - MAP - always map description to summary_detail (Andrei);
#  use libxml2 (if available)
#3.0b19 - 3/15/2004 - MAP - fixed bug exploding author information when author
#  name was in parentheses; removed ultra-problematic mxTidy support; patch to
#  workaround crash in PyXML/expat when encountering invalid entities
#  (MarkMoraes); support for textinput/textInput
#3.0b20 - 4/7/2004 - MAP - added CDF support
#3.0b21 - 4/14/2004 - MAP - added Hot RSS support
#3.0b22 - 4/19/2004 - MAP - changed u'channel' to u'feed', u'item' to u'entries' in
#  results dict; changed results dict to allow getting values with results.key
#  as well as results[key]; work around embedded illformed HTML with half
#  a DOCTYPE; work around malformed Content-Type header; if character encoding
#  is wrong, try several common ones before falling back to regexes (if this
#  works, bozo_exception is set to CharacterEncodingOverride); fixed character
#  encoding issues in BaseHTMLProcessor by tracking encoding and converting
#  from Unicode to raw strings before feeding data to sgmllib.SGMLParser;
#  convert each value in results to Unicode (if possible), even if using
#  regex-based parsing
#3.0b23 - 4/21/2004 - MAP - fixed UnicodeDecodeError for feeds that contain
#  high-bit characters in attributes in embedded HTML in description (thanks
#  Thijs van de Vossen); moved guid, date, and date_parsed to mapped keys in
#  FeedParserDict; tweaked FeedParserDict.has_key to return True if asking
#  about a mapped key
#3.0fc1 - 4/23/2004 - MAP - made results.entries[0].links[0] and
#  results.entries[0].enclosures[0] into FeedParserDict; fixed typo that could
#  cause the same encoding to be tried twice (even if it failed the first time);
#  fixed DOCTYPE stripping when DOCTYPE contained entity declarations;
#  better textinput and image tracking in illformed RSS 1.0 feeds
#3.0fc2 - 5/10/2004 - MAP - added and passed Sam's amp tests; added and passed
#  my blink tag tests
#3.0fc3 - 6/18/2004 - MAP - fixed bug in _changeEncodingDeclaration that
#  failed to parse utf-16 encoded feeds; made source into a FeedParserDict;
#  duplicate admin:generatorAgent/@rdf:resource in generator_detail.url;
#  added support for image; refactored parse() fallback logic to try other
#  encodings if SAX parsing fails (previously it would only try other encodings
#  if re-encoding failed); remove unichr madness in normalize_attrs now that
#  we're properly tracking encoding in and out of BaseHTMLProcessor; set
#  feed.language from root-level xml:lang; set entry.id from rdf:about;
#  send Accept header
#3.0 - 6/21/2004 - MAP - donu't try iso-8859-1 (can't distinguish between
#  iso-8859-1 and windows-1252 anyway, and most incorrectly marked feeds are
#  windows-1252); fixed regression that could cause the same encoding to be
#  tried twice (even if it failed the first time)
#3.0.1 - 6/22/2004 - MAP - default to us-ascii for all text/* content types;
#  recover from malformed content-type header parameter with no equals sign
#  (u'text/xml; charset:iso-8859-1')
#3.1 - 6/28/2004 - MAP - added and passed tests for converting HTML entities
#  to Unicode equivalents in illformed feeds (aaronsw); added and
#  passed tests for converting character entities to Unicode equivalents
#  in illformed feeds (aaronsw); test for valid parsers when setting
#  XML_AVAILABLE; make version and encoding available when server returns
#  a 304; add handlers parameter to pass arbitrary urllib2 handlers (like
#  digest auth or proxy support); add code to parse username/password
#  out of url and send as basic authentication; expose downloading-related
#  exceptions in bozo_exception (aaronsw); added __contains__ method to
#  FeedParserDict (aaronsw); added publisher_detail (aaronsw)
#3.2 - 7/3/2004 - MAP - use cjkcodecs and iconv_codec if available; always
#  convert feed to UTF-8 before passing to XML parser; completely revamped
#  logic for determining character encoding and attempting XML parsing
#  (much faster); increased default timeout to 20 seconds; test for presence
#  of Location header on redirects; added tests for many alternate character
#  encodings; support various EBCDIC encodings; support UTF-16BE and
#  UTF16-LE with or without a BOM; support UTF-8 with a BOM; support
#  UTF-32BE and UTF-32LE with or without a BOM; fixed crashing bug if no
#  XML parsers are available; added support for u'Content-encoding: deflate';
#  send blank u'Accept-encoding: ' header if neither gzip nor zlib modules
#  are available
#3.3 - 7/15/2004 - MAP - optimize EBCDIC to ASCII conversion; fix obscure
#  problem tracking xml:base and xml:lang if element declares it, child
#  doesnu't, first grandchild redeclares it, and second grandchild doesn't;
#  refactored date parsing; defined public registerDateHandler so callers
#  can add support for additional date formats at runtime; added support
#  for OnBlog, Nate, MSSQL, Greek, and Hungarian dates (ytrewq1); added
#  zopeCompatibilityHack() which turns FeedParserDict into a regular
#  dictionary, required for Zope compatibility, and also makes command-
#  line debugging easier because pprint module formats real dictionaries
#  better than dictionary-like objects; added NonXMLContentType exception,
#  which is stored in bozo_exception when a feed is served with a non-XML
#  media type such as u'text/plain'; respect Content-Language as default
#  language if not xml:lang is present; cloud dict is now FeedParserDict;
#  generator dict is now FeedParserDict; better tracking of xml:lang,
#  including support for xml:lang=u'' to unset the current language;
#  recognize RSS 1.0 feeds even when RSS 1.0 namespace is not the default
#  namespace; don't overwrite final status on redirects (scenarios:
#  redirecting to a URL that returns 304, redirecting to a URL that
#  redirects to another URL with a different type of redirect); add
#  support for HTTP 303 redirects
#4.0 - MAP - support for relative URIs in xml:base attribute; fixed
#  encoding issue with mxTidy (phopkins); preliminary support for RFC 3229;
#  support for Atom 1.0; support for iTunes extensions; new u'tags' for
#  categories/keywords/etc. as array of dict
#  {u'term': term, u'scheme': scheme, u'label': label} to match Atom 1.0
#  terminology; parse RFC 822-style dates with no time; lots of other
#  bug fixes
#4.1 - MAP - removed socket timeout; added support for chardet library
