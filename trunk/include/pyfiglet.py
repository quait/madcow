#!/usr/bin/env python

"""
Python FIGlet adaption
"""

import sys
from optparse import OptionParser
import os
import re
from zipfile import ZipFile

__version__ = '0.3'

__copyright__ = """
Copyright (C) 2007 Christopher Jones <cjones@insub.org>

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA
"""

class FigletError(Exception):
    def __init__(self, error):
        self.error = error

    def __str__(self):
        return self.error

class FontNotFound(FigletError):
    """
    Raised when a font can't be located
    """

class FontError(FigletError):
    """
    Raised when there is a problem parsing a font file
    """


"""
This class represents the currently loaded font, including
meta-data about how it should be displayed by default
"""
class FigletFont(object):
    def __init__(self, dir='.', font='standard'):
        self.dir = dir
        self.font = font

        self.comment = ''
        self.chars = {}
        self.width = {}
        self.data = None

        self.reMagicNumber = re.compile(r'^flf2.')
        self.reEndMarker = re.compile(r'(.)\s*$')

        self.readFontFile()
        self.loadFont()

    """
    Load font file into memory. This can be overriden with
    a superclass to create different font sources.
    """
    def readFontFile(self):
        fontPath = '%s/%s.flf' % (self.dir, self.font)
        if os.path.exists(fontPath) is False:
            raise FontNotFound, "%s doesn't exist" % fontPath

        try:
            fo = open(fontPath, 'rb')
        except Exception, e:
            raise FontError, "couldn't open %s: %s" % (fontPath, e)

        try: self.data = fo.read()
        finally: fo.close()

    def getFonts(self):
        return [font[:-4] for font in os.walk(self.dir).next()[2] if font.endswith('.flf')]
        




    """
    Parse loaded font data for the rendering engine to consume
    """
    def loadFont(self):
        try:
            """
            Parse first line of file, the header
            """
            data = self.data.splitlines()

            header = data.pop(0)
            if self.reMagicNumber.search(header) is None:
                raise FontError, '%s is not a valid figlet font' % fontPath

            header = self.reMagicNumber.sub('', header)
            header = header.split()
            
            if len(header) < 6:
                raise FontError, 'malformed header for %s' % fontPath

            hardBlank = header[0]
            height, baseLine, maxLength, oldLayout, commentLines = map(int, header[1:6])
            printDirection = fullLayout = codeTagCount = None

            # these are all optional for backwards compat
            if len(header) > 6: printDirection = int(header[6])
            if len(header) > 7: fullLayout = int(header[7])
            if len(header) > 8: codeTagCount = int(header[8])

            """
            if the new layout style isn't available,
            convert old layout style. backwards compatability
            """
            if fullLayout is None:
                if oldLayout == 0:
                    fullLayout = 64
                elif oldLayout < 0:
                    fullLayout = 0
                else:
                    fullLayout = (oldLayout & 31) | 128



            """
            Some header information is stored for later, the rendering
            engine needs to know this stuff.
            """
            self.height = height
            self.hardBlank = hardBlank
            self.printDirection = printDirection
            self.smushMode = fullLayout

            """
            Strip out comment lines
            """
            for i in range(0, commentLines):
                self.comment += data.pop(0)

            """
            Load characters
            """
            for i in range(32, 127):
                end = None
                width = 0
                for j in range(0, height):
                    line = data.pop(0)
                    if end is None:
                        end = self.reEndMarker.search(line).group(1)
                        end = re.compile(re.escape(end) + r'{1,2}$')

                    line = end.sub('', line)

                    if len(line) > width:
                        width = len(line)

                    if self.chars.has_key(i) is False:
                        self.chars[i] = []

                    self.chars[i].append(line)

                self.width[i] = width


        except Exception, e:
            raise FontError, 'problem parsing %s font: %s' % (self.font, e)


    def __str__(self):
        return '<FigletFont object: %s>' % self.font


"""
Rendered figlet font
"""
class RenderedOutput(str):
    def __init__(self, *args, **kwargs):
        str.__init__(self, *args, **kwargs)

        # translation map for reversing ascii art / -> \, etc.
        self.__reverse_map__ = '\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f !"#$%&\')(*+,-.\\0123456789:;>=<?@ABCDEFGHIJKLMNOPQRSTUVWXYZ]/[^_`abcdefghijklmnopqrstuvwxyz}|{~\x7f\x80\x81\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d\x9e\x9f\xa0\xa1\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xab\xac\xad\xae\xaf\xb0\xb1\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xbb\xbc\xbd\xbe\xbf\xc0\xc1\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xcb\xcc\xcd\xce\xcf\xd0\xd1\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xdb\xdc\xdd\xde\xdf\xe0\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xeb\xec\xed\xee\xef\xf0\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xfb\xfc\xfd\xfe\xff'

        # translation map for flipping ascii art ^ -> v, etc.
        self.__flip_map__ = '\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\x0c\r\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f !"#$%&\'()*+,-.\\0123456789:;<=>?@VBCDEFGHIJKLWNObQbSTUAMXYZ[/]v-`aPcdefghijklwnopqrstu^mxyz{|}~\x7f\x80\x81\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x8b\x8c\x8d\x8e\x8f\x90\x91\x92\x93\x94\x95\x96\x97\x98\x99\x9a\x9b\x9c\x9d\x9e\x9f\xa0\xa1\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xab\xac\xad\xae\xaf\xb0\xb1\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xbb\xbc\xbd\xbe\xbf\xc0\xc1\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xcb\xcc\xcd\xce\xcf\xd0\xd1\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xdb\xdc\xdd\xde\xdf\xe0\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xeb\xec\xed\xee\xef\xf0\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xfb\xfc\xfd\xfe\xff'

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
        return RenderedOutput('\n'.join(list) + '\n')





"""
Use this Font class if it exists inside of a zipfile.
"""
class ZippedFigletFont(FigletFont):
    def __init__(self, dir='.', font='standard', zipfile='fonts.zip'):
        self.zipfile = zipfile
        FigletFont.__init__(self, dir=dir, font=font)

    def readFontFile(self):
        if os.path.exists(self.zipfile) is False:
            raise FontNotFound, "%s doesn't exist" % self.zipfile

        fontPath = 'fonts/%s.flf' % self.font

        try:
            z = ZipFile(self.zipfile, 'r')
            files = z.namelist()
            if fontPath not in files:
                raise FontNotFound, '%s not found in %s' % (self.font, self.zipfile)

            self.data = z.read(fontPath)

        except Exception, e:
            raise FontError, "couldn't open %s: %s" % (fontPath, e)

    def getFonts(self):
        if os.path.exists(self.zipfile) is False:
            raise FontNotFound, "%s doesn't exist" % self.zipfile

        z = ZipFile(self.zipfile, 'r')
        return [font[6:-4] for font in z.namelist() if font.endswith('.flf')]



"""
This class handles the rendering of a FigletFont,
including smushing/kerning/justification/direction
"""
class FigletRenderingEngine(object):
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


    """
    Given 2 characters which represent the edges rendered figlet
    fonts where they would touch, see if they can be smushed together.
    Returns None if this cannot or should not be done.
    """
    def smushChars(self, left='', right=''):
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

            """
            Ensures that the dominant (foreground)
            fig-character for overlapping is the latter in the
            user's text, not necessarily the rightmost character.
            """
            if self.base.direction == 'right-to-left': return left
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
            if (left  == '_') and (right in r'|/\[]{}()<>'): return right
            if (right == '_') and (left  in r'|/\[]{}()<>'): return left

        if self.base.Font.smushMode & self.SM_HIERARCHY:
            if (left  == '|')   and (right in r'|/\[]{}()<>'): return right
            if (right == '|')   and (left  in r'|/\[]{}()<>'): return left
            if (left  in r'\/') and (right in '[]{}()<>'): return right
            if (right in r'\/') and (left  in '[]{}()<>'): return left
            if (left  in '[]')  and (right in '{}()<>'): return right
            if (right in '[]')  and (left  in '{}()<>'): return left
            if (left  in '{}')  and (right in '()<>'): return right
            if (right in '{}')  and (left  in '()<>'): return left
            if (left  in '()')  and (right in '<>'): return right
            if (right in '()')  and (left  in '<>'): return left

        if self.base.Font.smushMode & self.SM_PAIR:
            for pair in [left+right, right+left]:
                if pair in ['[]', '{}', '()']: return '|'

        if self.base.Font.smushMode & self.SM_BIGX:
            if (left == '/') and (right == '\\'): return '|'
            if (right == '/') and (left == '\\'): return 'Y'
            if (left == '>') and (right == '<'): return 'X'

        return



    """
    Render an ASCII text string in figlet
    """
    def render(self, text):
        self.curCharWidth = 0
        buffer = ['' for i in range(0, self.base.Font.height)]

        for c in map(ord, list(text)):
            curChar = self.base.Font.chars[c]
            self.prevCharWidth = self.curCharWidth
            self.curCharWidth = self.base.Font.width[c]


            """
            Calculate the amount of smushing we can do between this char and the last
            If this is the first char it will throw a series of exceptions which
            are caught and cause appropriate values to be set for later.

            This differs from C figlet which will just get bogus values from
            memory and then discard them after.
            """
            maxSmush = self.curCharWidth
            for row in range(0, self.base.Font.height):
                if self.base.direction == 'left-to-right':
                    try:
                        linebd = len(buffer[row].rstrip()) - 1
                        if linebd < 0: linebd = 0
                        ch1 = buffer[row][linebd]
                    except:
                        linebd = 0
                        ch1 = ''

                    try:
                        charbd = len(curChar[row]) - len(curChar[row].lstrip())
                        ch2 = curChar[row][charbd]
                    except:
                        charbd = len(curChar[row])
                        ch2 = ''
                        

                    try: curLength = len(buffer[row])
                    except: curLength = 0

                    amt = charbd + curLength - 1 - linebd

                elif self.base.direction == 'right-to-left':
                    try:
                        charbd = len(curChar[row].rstrip()) - 1
                        if charbd < 0: charbd = 0
                        ch1 = curChar[row][charbd]
                    except:
                        charbd = 0
                        ch1 = ''

                    try:
                        linebd = len(buffer[row]) - len(buffer[row].lstrip())
                        ch2 = buffer[row][linebd]
                    except:
                        linebd = len(buffer[row])
                        ch2 = ''

                    amt = linebd + self.curCharWidth - 1 - charbd


                if ch1 == '' or ch1 == ' ':
                    amt += 1
                elif ch2 != '':
                    if self.smushChars(left=ch1, right=ch2) is not None:
                        amt += 1


                if amt < maxSmush:
                    maxSmush = amt

            if (self.base.Font.smushMode & (self.SM_SMUSH | self.SM_KERN)) == 0:
                maxSmush = 0


            """
            Add a character to the buffer

            Smushing/Kerning loop. Exceptions in this loop
            are caused by index out of range errors which
            indicate smushing should be skipped.
            """
            templine = ''
            for row in range(0, self.base.Font.height):

                wBuffer = buffer[row] # row of previously added characters
                wChar = curChar[row]  # row of character to add

                if self.base.direction == 'left-to-right':
                    for i in range(0, maxSmush):

                        try: left = wBuffer[len(wBuffer) - maxSmush + i]
                        except: left = ''

                        right = wChar[i]

                        smushed = self.smushChars(left=left, right=right)

                        try:
                            if smushed is not None:
                                l = list(wBuffer)
                                l[len(l)-maxSmush+i] = smushed
                                wBuffer = ''.join(l)
                        except: pass

                    buffer[row] = wBuffer + wChar[maxSmush:]

                elif self.base.direction == 'right-to-left':
                    templine = wChar
                    for i in range(0, maxSmush):
                        try: left = templine[self.curCharWidth - maxSmush + i]
                        except: left = ''

                        right = wBuffer[i]

                        smushed = self.smushChars(left=left, right=right)

                        try:
                            l = list(templine)
                            l[self.curCharWidth - maxSmush +i] = smushed
                            templine = ''.join(l)
                        except:
                            pass

                    templine = templine + wBuffer[maxSmush:]
                    buffer[row] = templine

        # justify text
        if self.base.justify == 'right':
            for row in range(0, self.base.Font.height):
                buffer[row] = (' ' * (self.base.width - len(buffer[row]) - 1)) + buffer[row]

        elif self.base.justify == 'center':
            for row in range(0, self.base.Font.height):
                buffer[row] = (' ' * int((self.base.width - len(buffer[row])) / 2)) + buffer[row]


        # return rendered ASCII with hardblanks replaced
        buffer = '\n'.join(buffer) + '\n'
        buffer = buffer.replace(self.base.Font.hardBlank, ' ')
        return RenderedOutput(buffer)



"""
Main figlet class.
"""
class Figlet(object):
    def __init__(self, dir=None, zipfile=None, font='standard', direction='auto', justify='auto', width=80):
        self.dir = dir
        self.font = font
        self._direction = direction
        self._justify = justify
        self.width = width
        self.zipfile = zipfile
        self.setFont()
        self.engine = FigletRenderingEngine(base=self)


    def setFont(self, **kwargs):
        if kwargs.has_key('dir'):
            self.dir = kwargs['dir']

        if kwargs.has_key('font'):
            self.font = kwargs['font']

        if kwargs.has_key('zipfile'):
            self.zipfile = kwargs['zipfile']


        Font = None
        if self.zipfile is not None:
            try: Font = ZippedFigletFont(dir=self.dir, font=self.font, zipfile=self.zipfile)
            except: pass

        if Font is None and self.dir is not None:
            try: Font = FigletFont(dir=self.dir, font=self.font)
            except: pass

        if Font is None:
            raise FontNotFound, "Couldn't load font %s: Not found" % self.font

        self.Font = Font


    def getDirection(self):
        if self._direction == 'auto':
            direction = self.Font.printDirection
            if direction == 0:
                return 'left-to-right'
            elif direction == 1:
                return 'right-to-left'
            else:
                return 'left-to-right'

        else:
            return self._direction

    direction = property(getDirection)

    def getJustify(self):
        if self._justify == 'auto':
            if self.direction == 'left-to-right':
                return 'left'
            elif self.direction == 'right-to-left':
                return 'right'

        else:
            return self._justify

    justify = property(getJustify)

    # wrapper method to engine
    def renderText(self, text):
        return self.engine.render(text)

    def getFonts(self):
        return self.Font.getFonts()



def main():
    dir = os.path.abspath(os.path.dirname(sys.argv[0]))

    parser = OptionParser(version=__version__, usage='%prog [options] text..')

    parser.add_option(    '-f', '--font', default='standard',
                help='font to render with (default: %default)', metavar='FONT' )

    parser.add_option(    '-d', '--fontdir', default=None,
                help='location of font files', metavar='DIR' )

    parser.add_option(    '-z', '--zipfile', default=dir+'/fonts.zip',
                help='specify a zipfile to use instead of a directory of fonts' )

    parser.add_option(    '-D', '--direction', type='choice', choices=('auto', 'left-to-right', 'right-to-left'),
                default='auto', metavar='DIRECTION',
                help='set direction text will be formatted in (default: %default)' )

    parser.add_option(    '-j', '--justify', type='choice', choices=('auto', 'left', 'center', 'right'),
                default='auto', metavar='SIDE',
                help='set justification, defaults to print direction' )

    parser.add_option(    '-w', '--width', type='int', default=80, metavar='COLS',
                help='set terminal width for wrapping/justification (default: %default)' )

    parser.add_option(    '-r', '--reverse', action='store_true', default=False,
                help='shows mirror image of output text' )

    parser.add_option(    '-F', '--flip', action='store_true', default=False,
                help='flips rendered output text over' )



    opts, args = parser.parse_args()

    if len(args) == 0:
        parser.print_help()
        return 1

    text = ' '.join(args)

    f = Figlet(
        dir=opts.fontdir, font=opts.font, direction=opts.direction,
        justify=opts.justify, width=opts.width, zipfile=opts.zipfile,
    )

    r = f.renderText(text)
    if opts.reverse is True: r = r.reverse()
    if opts.flip is True: r = r.flip()
    print r


    return 0

if __name__ == '__main__': sys.exit(main())
