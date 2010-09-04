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

"""Python FIGlet adaption"""

from __future__ import with_statement
import sys
import os
import re
from zipfile import ZipFile
from optparse import OptionParser

__version__ = u'0.5'
__author__ = u'cj_<cjones@gruntle.org>'

class FigletError(Exception):

    """Base figlet error"""


class FontNotFound(FigletError):

    """Raised when a font can't be located"""


class FontError(FigletError):

    """Raised when there is a problem parsing a font file"""


class FigletFont(object):

    """
    This class represents the currently loaded font, including
    meta-data about how it should be displayed by default
    """

    def __init__(self, prefix=u'.', font=u'standard'):
        self.prefix = prefix
        self.font = font
        self.comment = u''
        self.chars = {}
        self.width = {}
        self.data = None
        self.reMagicNumber = re.compile(r'^flf2.')
        self.reEndMarker = re.compile(r'(.)\s*$')
        self.readFontFile()
        self.loadFont()

    def readFontFile(self):
        """
        Load font file into memory. This can be overriden with
        a superclass to create different font sources.
        """
        fontPath = u'%s/%s.flf' % (self.prefix, self.font)
        if os.path.exists(fontPath) is False:
            raise FontNotFound, u"%s doesn't exist" % fontPath

        try:
            fo = open(fontPath, u'rb')
        except Exception, error:
            raise FontError(u"couldn't open %s: %s" % (fontPath, error))

        try: self.data = fo.read()
        finally: fo.close()

    def getFonts(self):
        return [font[:-4] for font in os.walk(self.prefix).next()[2] if font.endswith(u'.flf')]

    def loadFont(self):
        """
        Parse loaded font data for the rendering engine to consume
        """
        try:
            # Parse first line of file, the header
            data = self.data.splitlines()

            header = data.pop(0)
            if self.reMagicNumber.search(header) is None:
                raise FontError('not a valid figlet font')

            header = self.reMagicNumber.sub(u'', header)
            header = header.split()

            if len(header) < 6:
                raise FontError('malformed header')

            hardBlank = header[0]
            height, baseLine, maxLength, oldLayout, commentLines = map(int, header[1:6])
            printDirection = fullLayout = codeTagCount = None

            # these are all optional for backwards compat
            if len(header) > 6: printDirection = int(header[6])
            if len(header) > 7: fullLayout = int(header[7])
            if len(header) > 8: codeTagCount = int(header[8])

            # if the new layout style isn't available,
            # convert old layout style. backwards compatability
            if fullLayout is None:
                if oldLayout == 0:
                    fullLayout = 64
                elif oldLayout < 0:
                    fullLayout = 0
                else:
                    fullLayout = (oldLayout & 31) | 128

            # Some header information is stored for later, the rendering
            # engine needs to know this stuff.
            self.height = height
            self.hardBlank = hardBlank
            self.printDirection = printDirection
            self.smushMode = fullLayout

            # Strip out comment lines
            for i in range(0, commentLines):
                self.comment += data.pop(0)

            # Load characters
            for i in range(32, 127):
                end = None
                width = 0
                chars = []
                for j in range(0, height):
                    line = data.pop(0)
                    if end is None:
                        end = self.reEndMarker.search(line).group(1)
                        end = re.compile(re.escape(end) + r'{1,2}$')

                    line = end.sub(u'', line)

                    if len(line) > width: width = len(line)
                    chars.append(line)

                if u''.join(chars) != u'':
                    self.chars[i] = chars
                    self.width[i] = width

        except Exception, error:
            raise FontError(u'problem parsing %s font: %s' % (self.font, error))

    def __str__(self):
        return u'<FigletFont object: %s>' % self.font


class FigletString(str):

    """Rendered figlet font"""

    def __init__(self, *args, **kwargs):
        # XXX this is bad in 3.0..well, more to the point, this whole thing
        # will have to fixed up.
        str.__init__(self, *args, **kwargs)

        # translation map for reversing ascii art / -> \, etc.
        self.__reverse_map__ = u'\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f !"#$%&\')(*+,-.\\0123456789:;>=<?@ABCDEFGHIJKLMNOPQRSTUVWXYZ]/[^_`abcdefghijklmnopqrstuvwxyz}|{~\x7f\x80\x81\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d\x9e\x9f\xa0\xa1\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xab\xac\xad\xae\xaf\xb0\xb1\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xbb\xbc\xbd\xbe\xbf\xc0\xc1\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xcb\xcc\xcd\xce\xcf\xd0\xd1\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xdb\xdc\xdd\xde\xdf\xe0\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xeb\xec\xed\xee\xef\xf0\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xfb\xfc\xfd\xfe\xff'

        # translation map for flipping ascii art ^ -> v, etc.
        self.__flip_map__ = u'\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f !"#$%&\'()*+,-.\\0123456789:;<=>?@VBCDEFGHIJKLWNObQbSTUAMXYZ[/]v-`aPcdefghijklwnopqrstu^mxyz{|}~\x7f\x80\x81\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d\x9e\x9f\xa0\xa1\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xab\xac\xad\xae\xaf\xb0\xb1\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xbb\xbc\xbd\xbe\xbf\xc0\xc1\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xcb\xcc\xcd\xce\xcf\xd0\xd1\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xdb\xdc\xdd\xde\xdf\xe0\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xeb\xec\xed\xee\xef\xf0\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xfb\xfc\xfd\xfe\xff'

    def reverse(self):
        out = []
        for row in self.splitlines():
            out.append(row.translate(self.__reverse_map__)[::-1])

        return self.newFromList(out)

    def flip(self):
        out = []
        for row in self.splitlines()[::-1]:
            out.append(row.translate(self.__flip_map__))

        return self.newFromList(out)

    def newFromList(self, list):
        return FigletString(u'\n'.join(list) + u'\n')


class ZippedFigletFont(FigletFont):
    """
    Use this Font class if it exists inside of a zipfile.
    """

    def __init__(self, prefix=u'.', font=u'standard', zipfile=u'fonts.zip'):
        self.zipfile = zipfile
        FigletFont.__init__(self, prefix=prefix, font=font)

    def readFontFile(self):
        if os.path.exists(self.zipfile) is False:
            raise FontNotFound, u"%s doesn't exist" % self.zipfile

        fontPath = u'fonts/%s.flf' % self.font

        try:
            z = ZipFile(self.zipfile, u'r')
            files = z.namelist()
            if fontPath not in files:
                raise FontNotFound, u'%s not found in %s' % (self.font, self.zipfile)

            self.data = z.read(fontPath)

        except Exception, error:
            raise FontError(u"couldn't open %s: %s" % (fontPath, error))

    def getFonts(self):
        if os.path.exists(self.zipfile) is False:
            raise FontNotFound, u"%s doesn't exist" % self.zipfile

        z = ZipFile(self.zipfile, u'r')
        return [font[6:-4] for font in z.namelist() if font.endswith(u'.flf')]


class FigletRenderingEngine(object):
    """
    This class handles the rendering of a FigletFont,
    including smushing/kerning/justification/direction
    """

    def __init__(self, base=None):
        self.base = base

        # constants.. lifted from figlet222
        self.SM_EQUAL = 1    # smush equal chars (not hardblanks)
        self.SM_LOWLINE = 2    # smush _ with any char in hierarchy
        self.SM_HIERARCHY = 4    # hierarchy: |, /\, [], {}, (), <>
        self.SM_PAIR = 8    # hierarchy: [ + ] -> |, { + } -> |, ( + ) -> |
        self.SM_BIGX = 16    # / + \ -> X, > + < -> X
        self.SM_HARDBLANK = 32    # hardblank + hardblank -> hardblank
        self.SM_KERN = 64
        self.SM_SMUSH = 128


    def smushChars(self, left=u'', right=u''):
        """
        Given 2 characters which represent the edges rendered figlet
        fonts where they would touch, see if they can be smushed together.
        Returns None if this cannot or should not be done.
        """
        if left.isspace() is True: return right
        if right.isspace() is True: return left

        # Disallows overlapping if previous or current char has a width of 1 or zero
        if (self.prevCharWidth < 2) or (self.curCharWidth < 2): return

        # kerning only
        if (self.base.Font.smushMode & self.SM_SMUSH) == 0: return

        # smushing by universal overlapping
        if (self.base.Font.smushMode & 63) == 0:
            # Ensure preference to visiable characters.
            if left == self.base.Font.hardBlank: return right
            if right == self.base.Font.hardBlank: return left

            # Ensures that the dominant (foreground)
            # fig-character for overlapping is the latter in the
            # user's text, not necessarily the rightmost character.
            if self.base.direction == u'right-to-left': return left
            else: return right

        if self.base.Font.smushMode & self.SM_HARDBLANK:
            if left == self.base.Font.hardBlank and right == self.base.Font.hardBlank:
                return left

        if left == self.base.Font.hardBlank or right == self.base.Font.hardBlank:
            return

        if self.base.Font.smushMode & self.SM_EQUAL:
            if left == right:
                return left

        if self.base.Font.smushMode & self.SM_LOWLINE:
            if (left  == u'_') and (right in r'|/\[]{}()<>'): return right
            if (right == u'_') and (left  in r'|/\[]{}()<>'): return left

        if self.base.Font.smushMode & self.SM_HIERARCHY:
            if (left  == u'|')   and (right in r'|/\[]{}()<>'): return right
            if (right == u'|')   and (left  in r'|/\[]{}()<>'): return left
            if (left  in r'\/') and (right in u'[]{}()<>'): return right
            if (right in r'\/') and (left  in u'[]{}()<>'): return left
            if (left  in u'[]')  and (right in u'{}()<>'): return right
            if (right in u'[]')  and (left  in u'{}()<>'): return left
            if (left  in u'{}')  and (right in u'()<>'): return right
            if (right in u'{}')  and (left  in u'()<>'): return left
            if (left  in u'()')  and (right in u'<>'): return right
            if (right in u'()')  and (left  in u'<>'): return left

        if self.base.Font.smushMode & self.SM_PAIR:
            for pair in [left+right, right+left]:
                if pair in [u'[]', u'{}', u'()']: return u'|'

        if self.base.Font.smushMode & self.SM_BIGX:
            if (left == u'/') and (right == u'\\'): return '|'
            if (right == u'/') and (left == u'\\'): return 'Y'
            if (left == u'>') and (right == u'<'): return u'X'

        return

    def smushAmount(self, left=None, right=None, buffer=[], curChar=[]):
        """
        Calculate the amount of smushing we can do between this char and
        the last.  If this is the first char it will throw a series of
        exceptions which are caught and cause appropriate values to be
        set for later.  This differs from C figlet which will just get
        bogus values from memory and then discard them after.
        """

        if (self.base.Font.smushMode & (self.SM_SMUSH | self.SM_KERN)) == 0:
            return 0

        maxSmush = self.curCharWidth
        for row in range(0, self.base.Font.height):
            lineLeft = buffer[row]
            lineRight = curChar[row]
            if self.base.direction == u'right-to-left':
                lineLeft, lineRight = lineRight, lineLeft

            try:
                linebd = len(lineLeft.rstrip()) - 1
                if linebd < 0: linebd = 0
                ch1 = lineLeft[linebd]
            except:
                linebd = 0
                ch1 = u''

            try:
                charbd = len(lineRight) - len(lineRight.lstrip())
                ch2 = lineRight[charbd]
            except:
                charbd = len(lineRight)
                ch2 = u''

            amt = charbd + len(lineLeft) - 1 - linebd

            if ch1 == u'' or ch1 == u' ':
                amt += 1
            elif ch2 != u'' and self.smushChars(left=ch1, right=ch2) is not None:
                amt += 1

            if amt < maxSmush:
                maxSmush = amt

        return maxSmush

    def render(self, text):
        """
        Render an ASCII text string in figlet
        """
        self.curCharWidth = self.prevCharWidth = 0
        buffer = []

        for c in map(ord, list(text)):
            if c in self.base.Font.chars is False: continue
            curChar = self.base.Font.chars[c]
            self.curCharWidth = self.base.Font.width[c]
            if len(buffer) == 0: buffer = [u'' for i in range(self.base.Font.height)]
            maxSmush = self.smushAmount(buffer=buffer, curChar=curChar)

            # Add a character to the buffer and do smushing/kerning
            for row in range(0, self.base.Font.height):
                addLeft = buffer[row]
                addRight = curChar[row]

                if self.base.direction == u'right-to-left':
                    addLeft, addRight = addRight, addLeft

                for i in range(0, maxSmush):

                    try: left = addLeft[len(addLeft) - maxSmush + i]
                    except: left = u''

                    right = addRight[i]

                    smushed = self.smushChars(left=left, right=right)

                    try:
                        l = list(addLeft)
                        l[len(l)-maxSmush+i] = smushed
                        addLeft = u''.join(l)
                    except:
                        pass

                buffer[row] = addLeft + addRight[maxSmush:]

            self.prevCharWidth = self.curCharWidth


        # Justify text. This does not use str.rjust/str.center
        # specifically because the output would not match FIGlet
        if self.base.justify == u'right':
            for row in range(0, self.base.Font.height):
                buffer[row] = (u' ' * (self.base.width - len(buffer[row]) - 1)) + buffer[row]

        elif self.base.justify == u'center':
            for row in range(0, self.base.Font.height):
                buffer[row] = (u' ' * int((self.base.width - len(buffer[row])) / 2)) + buffer[row]

        # return rendered ASCII with hardblanks replaced
        buffer = u'\n'.join(buffer) + u'\n'
        buffer = buffer.replace(self.base.Font.hardBlank, u' ')

        return FigletString(buffer)


class Figlet(object):
    """
    Main figlet class.
    """

    def __init__(self, prefix=None, zipfile=None, font=u'standard', direction=u'auto', justify=u'auto', width=80):
        self.prefix = prefix
        self.font = font
        self._direction = direction
        self._justify = justify
        self.width = width
        self.zipfile = zipfile
        self.setFont()
        self.engine = FigletRenderingEngine(base=self)

    def setFont(self, **kwargs):
        if u'prefix' in kwargs:
            self.dir = kwargs[u'prefix']

        if u'font' in kwargs:
            self.font = kwargs[u'font']

        if u'zipfile' in kwargs:
            self.zipfile = kwargs[u'zipfile']

        Font = None
        if self.zipfile is not None:
            try:
                Font = ZippedFigletFont(
                        prefix=self.prefix,
                        font=self.font,
                        zipfile=self.zipfile)
            except:
                pass

        if Font is None and self.prefix is not None:
            try:
                Font = FigletFont(prefix=self.prefix, font=self.font)
            except:
                pass

        if Font is None:
            raise FontNotFound(u"Couldn't load font %s: Not found" % self.font)

        self.Font = Font

    def getDirection(self):
        if self._direction == u'auto':
            direction = self.Font.printDirection
            if direction == 0:
                return u'left-to-right'
            elif direction == 1:
                return u'right-to-left'
            else:
                return u'left-to-right'

        else:
            return self._direction

    direction = property(getDirection)

    def getJustify(self):
        if self._justify == u'auto':
            if self.direction == u'left-to-right':
                return u'left'
            elif self.direction == u'right-to-left':
                return u'right'

        else:
            return self._justify

    justify = property(getJustify)

    def renderText(self, text):
        # wrapper method to engine
        return self.engine.render(text)

    def getFonts(self):
        return self.Font.getFonts()


def main():
    prefix = os.path.abspath(os.path.dirname(sys.argv[0]))
    parser = OptionParser(version=__version__, usage='%prog [options] text..')
    parser.add_option('-f', '--font', default='standard',
                      help='font to render with (default: %default)',
                      metavar='FONT')
    parser.add_option('-d', '--fontdir', default=None,
                      help='location of font files', metavar='DIR')
    parser.add_option('-z', '--zipfile', default=prefix+'/fonts.zip',
                      help='specify a zipfile to use instead of a directory o'
                      'f fonts')
    parser.add_option('-D', '--direction', type='choice',
                      choices=('auto', 'left-to-right', 'right-to-left'),
                      default='auto', metavar='DIRECTION',
                      help='set direction text will be formatted in (default:'
                      ' %default)')
    parser.add_option('-j', '--justify', type='choice',
                      choices=('auto', 'left', 'center', 'right'),
                      default='auto', metavar='SIDE',
                      help='set justification, defaults to print direction')
    parser.add_option('-w', '--width', type='int', default=80, metavar='COLS',
                      help='set terminal width for wrapping/justification (de'
                      'fault: %default)')
    parser.add_option('-r', '--reverse', action='store_true', default=False,
                      help='shows mirror image of output text')
    parser.add_option('-F', '--flip', action='store_true', default=False,
                      help='flips rendered output text over')
    opts, args = parser.parse_args()

    if not args:
        parser.print_help()
        return 1

    text = u' '.join(args)

    f = Figlet(
        prefix=opts.fontdir, font=opts.font, direction=opts.direction,
        justify=opts.justify, width=opts.width, zipfile=opts.zipfile,
    )

    r = f.renderText(text)
    if opts.reverse is True: r = r.reverse()
    if opts.flip is True: r = r.flip()
    print r

    return 0

if __name__ == u'__main__':
    sys.exit(main())
