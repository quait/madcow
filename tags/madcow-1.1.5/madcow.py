#!/usr/bin/env python

import sys
import os
from ConfigParser import ConfigParser
from optparse import OptionParser
import re
import threading
import time
import logging as log
from include.authlib import AuthLib
from include.utils import Base
import SocketServer
import select

__version__ = '1.1.5'
__author__ = 'Christopher Jones <cjones@gruntle.org>'
__copyright__ = 'Copyright (C) 2007-2008 Christopher Jones'
__license__ = 'GPL'
__all__ = ['Request', 'User', 'Admin', 'ServiceHandler', 'PeriodicEvents',
        'Madcow', 'Config']
_logformat = '[%(asctime)s] %(levelname)s: %(message)s'
_loglevel = log.INFO

class Request(Base):
    """Generic object passed in from protocol handlers for processing"""

    def __init__(self, message=None):
        self.message = message

        # required attributes get a default
        self.nick = None
        self.addressed = False
        self.correction = False
        self.channel = None
        self.args = []

    def __getattr__(self, attr):
        return None


class User(Base):
    """This class represents a logged in user"""

    def __init__(self, user, flags):
        self.user = user
        self.flags = flags
        self.loggedIn = int(time.time())

    def isAdmin(self):
        return 'a' in self.flags

    def isRegistered(self):
        if 'a' in self.flags or 'r' in self.flags:
            return True
        else:
            return False


class Admin(Base):
    """Class to handle admin interface"""

    _reRegister = re.compile('^\s*register\s+(\S+)\s*$', re.I)
    _reAuth = re.compile('^\s*(?:log[io]n|auth)\s+(\S+)\s*$', re.I)
    _reFist = re.compile('^\s*fist\s+(\S+)\s+(.+)$', re.I)
    _reHelp = re.compile('^\s*admin\s+help\s*$', re.I)
    _reLogout = re.compile('^\s*log(?:out|off)\s*$', re.I)

    _usage =  'admin help - this screen\n'
    _usage += 'register <pass> - register with bot\n'
    _usage += 'login <pass> - login to bot\n'
    _usage += 'fist <chan> <msg> - make bot say something in channel\n'
    _usage += 'logout - log out of bot'

    def __init__(self, bot):
        self.bot = bot
        self.authlib = AuthLib('%s/data/db-%s-passwd' % (bot.dir, bot.ns))
        self.users = {}
        self.modules = {}
        self.usageLines = Admin._usage.splitlines()

    def parse(self, req):
        if self.bot.config.admin.enabled is not True:
            return

        nick = req.nick
        command = req.message
        response = None

        # register
        try:
            passwd = Admin._reRegister.search(command).group(1)
            return self.registerUser(nick, passwd)
        except:
            pass

        # log in
        try:
            passwd = Admin._reAuth.search(command).group(1)
            return self.authenticateUser(nick, passwd)
        except:
            pass

        # don't pass this point unless we are logged in
        try:
            user = self.users[nick]
        except:
            return

        # logout
        if Admin._reLogout.search(command):
            del self.users[nick]
            return 'You are now logged out.'

        # help
        if Admin._reHelp.search(command):
            return '\n'.join(self.usageLines)

        # admin functions
        if user.isAdmin():

            # be the puppetmaster
            try:
                channel, message = Admin._reFist.search(command).groups()
                req.sendTo = channel
                return message
            except:
                pass

    def registerUser(self, user, passwd):
        if self.bot.config.admin.allowRegistration is True:
            flags = self.bot.config.admin.defaultFlags
            if flags is None:
                flags = 'r'

            self.authlib.add_user(user, passwd, flags)
            return "You are now registered, try logging in: login <pass>"
        else:
            return "Registration is disabled."

    def authenticateUser(self, user, passwd):
        status = self.authlib.verify_user(user, passwd)

        if status is False:
            return 'Nice try.. notifying FBI'
        else:
            self.users[user] = User(user, self.authlib.get_user_data(user))
            return 'You are now logged in. Message me "admin help" for help'


class ServiceHandler(SocketServer.BaseRequestHandler):
    """This class handles the listener service for message injection"""

    # pre-compiled regex
    re_from = re.compile(r'^from:\s*(.+?)\s*$', re.I)
    re_to = re.compile(r'^to:\s*(#\S+)\s*$', re.I)
    re_message = re.compile(r'^message:\s*(.+?)\s*$', re.I)

    def setup(self):
        log.info('connection from %s' % repr(self.client_address))

    def handle(self):
        data = ''
        while True:
            read = self.request.recv(1024)
            if len(read) == 0:
                break
            data += read
        log.info('got payload: %s' % repr(data))

        sent_from = send_to = message = None
        for line in data.splitlines():
            try:
                sent_from = ServiceHandler.re_from.search(line).group(1)
            except:
                pass

            try:
                send_to = ServiceHandler.re_to.search(line).group(1)
            except:
                pass

            try:
                message = ServiceHandler.re_message.search(line).group(1)
            except:
                pass

        if sent_from is None or send_to is None or message is None:
            log.warn('invalid payload')
            return

        # see if we can reverse lookup sender
        db = self.server.madcow.modules['learn'].get_db('email')
        for user, email in db.items():
            if sent_from == email:
                sent_from = user
                break

        req = Request()
        req.colorize = False
        req.wrap = False
        req.sendTo = send_to
        output = 'message from %s: %s' % (sent_from, message)
        self.server.madcow.output(output, req)

    def finish(self):
        log.info('connection closed by %s' % repr(self.client_address))


class PeriodicEvents(Base):
    """Class to manage modules which are periodically executed"""
    _re_delim = re.compile(r'\s*[,;]\s*')
    _ignore_modules = ['__init__', 'template']
    _process_frequency = 0.50

    def __init__(self, madcow):
        self.madcow = madcow
        self.dir = os.path.join(madcow.dir, 'periodic')
        self.modules = {}
        self.load_modules()

    def load_modules(self):
        """Load modules to be periodically executed"""
        filenames = os.walk(self.dir).next()[2]
        log.info('[MOD] * Reading periodic modules from %s' % self.dir)

        for filename in filenames:
            if not filename.endswith('.py'):
                continue
            mod_name = filename[:-3]
            if mod_name in PeriodicEvents._ignore_modules:
                continue
            try:
                module = __import__('periodic.' + mod_name, globals(),
                        locals(), ['PeriodicEvent'])
                PeriodicEvent = getattr(module, 'PeriodicEvent')
                obj = PeriodicEvent(madcow=self.madcow)
                if not obj.enabled:
                    raise Exception, 'disabled'
                log.info('[MOD] Loaded periodic module %s' % mod_name)
                self.modules[mod_name] = {'last_run': time.time(), 'obj': obj}
            except Exception, e:
                log.warn("[MOD] Couldn't load %s: %s" % (mod_name, e))

    def start(self):
        while True:
            self.process_queue()
            time.sleep(self._process_frequency)

    def process_queue(self):
        now = time.time()
        for mod_name, mod_data in self.modules.items():
            obj = mod_data['obj']
            if (now - mod_data['last_run']) < obj.frequency:
                continue
            self.modules[mod_name]['last_run'] = now
            kwargs = {'mod_name': mod_name, 'obj': obj}
            threading.Thread(target=self.process_thread, kwargs=kwargs).start()

    def process_thread(self, **kwargs):
        try:
            obj = kwargs['obj']
            response = obj.process()
            if response is not None and len(response):
                req = Request()
                req.colorize = False
                req.wrap = False
                req.sendTo = obj.output
                self.madcow.outputLock.acquire()
                self.madcow.output(response, req)
                self.madcow.outputLock.release()
        except Exception, e:
            log.warn('UNCAUGHT EXCEPTION IN %s' % kwargs['mod_name'])
            log.exception(e)


class Madcow(Base):
    """Core bot handler"""
    reDelim = re.compile(r'\s*[,;]\s*')

    def __init__(self, config=None, dir=None):
        self.config = config
        self.dir = dir

        self.ns = self.config.modules.dbnamespace
        self.ignoreModules = [ '__init__', 'template' ]
        self.moduleDir = os.path.join(self.dir, 'modules')
        self.outputLock = threading.RLock()

        if self.config.main.ignorelist is not None:
            self.ignoreList = self.config.main.ignorelist
            self.ignoreList = self.reDelim.split(self.ignoreList)
            self.ignoreList = [nick.lower() for nick in self.ignoreList]
            log.info('Ignoring nicks: %s' % ', '.join(self.ignoreList))
        else:
            self.ignoreList = []

        self.admin = Admin(self)

        # dynamically generated content
        self.usageLines = []
        self.modules = {}
        self.loadModules()

        # start local service for handling email gateway
        if self.config.gateway.enabled:
            log.info('launching gateway service')
            threading.Thread(target=self.startService).start()

        # start thread to handle periodic events
        threading.Thread(target=self.startPeriodicService).start()

    def startService(self, *args, **kwargs):
        addr = (self.config.gateway.bind, self.config.gateway.port)
        server = SocketServer.ThreadingTCPServer(addr, ServiceHandler)
        server.daemon_threads = True
        server.madcow = self
        while True:
            if select.select([server.socket], [], [], 0.25)[0]:
                server.handle_request()

    def startPeriodicService(self, *args, **kwargs):
        PeriodicEvents(madcow=self).start()

    def start(self):
        pass

    def output(self, message, req):
        pass

    def botName(self):
        return 'madcow'

    def loadModules(self):
        """
        Dynamic loading of module extensions. This looks for .py files in
        The module directory. They must be well-formed (based on template.py).
        If there are any problems loading, it will skip them.
        """
        disabled = []
        for mod_name, enabled in self.config.modules.__dict__.items():
            if mod_name == 'dbNamespace':
                continue
            if not enabled:
                disabled.append(mod_name)

        files = os.walk(self.moduleDir).next()[2]
        log.info('[MOD] * Reading modules from %s' % self.moduleDir)

        for file in files:
            if file.endswith('.py') is False:
                continue

            modName = file[:-3]
            if modName in self.ignoreModules:
                continue

            if modName in disabled:
                log.warn('[MOD] %s is disabled in config' % modName)
                continue

            try:
                module = __import__('modules.' + modName, globals(), locals(),
                        ['MatchObject'])
                MatchObject = getattr(module, 'MatchObject')
                obj = MatchObject(config=self.config, ns=self.ns, dir=self.dir)

                if obj.enabled is False:
                    raise Exception, 'disabled'

                if hasattr(obj, 'help') and obj.help is not None:
                    self.usageLines += obj.help.splitlines()

                log.info('[MOD] Loaded module %s' % modName)
                self.modules[modName] = obj

                try:
                    Admin = getattr(module, 'Admin')
                    obj = Admin()
                    log.info('[MOD] Registering Admin: %s' % modName)
                    self.admin.modules[modName] = obj
                except:
                    pass

            except Exception, e:
                log.warn("[MOD] Couldn't load module %s: %s" % (modName, e))

    def checkAddressing(self, req):
        """Is bot being addressed?"""
        nick = self.botName()

        # compile regex based on current nick
        self.reCorrection = re.compile('^\s*no,?\s*%s\s*[,:> -]+\s*(.+)' % 
                re.escape(nick), re.I)
        self.reAddressed = re.compile('^\s*%s\s*[,:> -]+\s*(.+)' %
                re.escape(nick), re.I)
        self.reFeedback = re.compile('^\s*%s\s*\?+$' % re.escape(nick), re.I)

        # correction: "no, bot, foo is bar"
        try:
            req.message = self.reCorrection.search(req.message).group(1)
            req.correction = True
            req.addressed = True
        except:
            pass

        # bot ping: "bot?"
        if self.reFeedback.search(req.message):
            req.feedback = True

        # addressed
        try:
            req.message = self.reAddressed.search(req.message).group(1)
            req.addressed = True
        except:
            pass

    def logpublic(self, req):
        """Logs public chatter"""
        line = '%s <%s> %s\n' % (time.strftime('%T'), req.nick, req.message)
        path = os.path.join(self.dir, 'logs', '%s-irc-%s-%s' % (self.ns,
            req.channel, time.strftime('%F')))

        fo = open(path, 'a')
        try:
            fo.write(line)
        finally:
            fo.close()

    def usage(self):
        """Returns help data as a string"""
        return '\n'.join(self.usageLines)

    def processMessage(self, req):
        """Process requests"""
        if self.config.main.logpublic and not req.private:
            self.logpublic(req)

        if req.nick.lower() in self.ignoreList:
            log.info('Ignored "%s" from %s' % (req.message, req.nick))
            return

        if req.feedback is True:
            self.output('yes?', req)
            return

        if req.addressed is True and req.message.lower() == 'help':
            self.output(self.usage(), req)
            return

        # pass through admin
        if req.private is True:
            response = self.admin.parse(req)
            if response is not None:
                self.output(response, req)
                return

        for module in self.modules.values():
            if module.requireAddressing and not req.addressed:
                continue

            try:
                args = module.pattern.search(req.message).groups()
            except:
                continue

            # make new dict explictly for thread safety
            kwargs = dict(req.__dict__.items() + [('args', args),
                ('module', module), ('req', req)])

            if self.allowThreading and module.thread:
                threading.Thread(target=self.processThread,
                        kwargs=kwargs).start()
            else:
                try:
                    response = module.response(**kwargs)
                except Exception, e:
                    log.warn('UNCAUGHT EXCEPTION')
                    log.exception(e)
                    response = None
                if response is not None and len(response) > 0:
                    self.output(response, req)

    def processThread(self, **kwargs):
        try:
            response = kwargs['module'].response(**kwargs)
        except Exception, e:
            log.warn('UNCAUGHT EXCEPTION')
            log.exception(e)
            response = None
        if response is not None and len(response) > 0:
            self.outputLock.acquire()
            self.output(response, kwargs['req'])
            self.outputLock.release()


class Config(Base):
    """
    Class to handle configuration directives. Usage is: config.module.attribute
    module maps to the headers in the configuration file. It automatically
    translates floats and integers to the appropriate type.
    """

    isInt = re.compile('^[0-9]+$')
    isFloat = re.compile('^\d+\.\d+$')
    isTrue = re.compile('^\s*(true|yes|on|1)\s*$')
    isFalse = re.compile('^\s*(false|no|off|0)\s*$')

    def __init__(self, file=None, section=None, opts=None):
        if file is not None:
            cfg = ConfigParser()
            cfg.read(file)

            for section in cfg.sections():
                obj = Config(section=section, opts=cfg.items(section))
                setattr(self, section, obj)

        else:
            for key, val in opts:
                if Config.isInt.search(val):
                    val = int(val)
                elif Config.isFloat.search(val):
                    val = float(val)
                elif Config.isTrue.search(val):
                    val = True
                elif Config.isFalse.search(val):
                    val = False

                setattr(self, key, val)

    def __getattr__(self, attr):
        try:
            return getattr(self, attr)
        except:
            try:
                return getattr(self, attr.lower())
            except:
                return None


def detach():
    """Daemonize on POSIX system"""
    if os.name != 'posix':
        return
    stop_logging('StreamHandler') # kind of pointless if we're daemonized
    if os.fork() != 0:
        sys.exit(0)
    os.setsid()
    if os.fork() != 0:
        sys.exit(0)
    for fd in sys.stdout, sys.stderr:
        fd.flush()
    si = file('/dev/null', 'r')
    so = file('/dev/null', 'a+')
    se = file('/dev/null', 'a+', 0)
    os.dup2(si.fileno(), sys.stdin.fileno())
    os.dup2(so.fileno(), sys.stdout.fileno())
    os.dup2(se.fileno(), sys.stderr.fileno())
    log.info('madcow is launched as a daemon')

def stop_logging(handler_name):
    """
    Stops a specified logging handler by name (e.g. StreamHandler), why
    there's no way to do this in the logging class I do not know.
    """
    logger = log.getLogger('')
    for handler in logger.handlers:
        if handler.__class__.__name__ == handler_name:
            handler.flush()
            handler.close()
            logger.removeHandler(handler)
    log.info('stopped logging to console')

def main():
    """Entry point to set up bot and run it"""

    # where we are being run from
    dir = os.path.abspath(os.path.dirname(sys.argv[0]))
    sys.path.append(dir)

    # parse commandline options
    parser = OptionParser(version=__version__)
    parser.add_option('-c', '--config', default=dir+'/madcow.ini',
            help='default: %default', metavar='FILE')
    parser.add_option('-d', '--detach', action='store_true', default=False,
            help='detach when run')
    parser.add_option('-p', '--protocol',
            help='force the use of this output protocol')
    parser.add_option('-D', '--debug', dest='loglevel', action='store_const',
            const=log.DEBUG, help='turn on debugging output (SPAMMY)')
    parser.add_option('-q', '--quiet', dest='loglevel', action='store_const',
            const=log.WARN, help='only show errors')
    opts, args = parser.parse_args()

    # read config file
    config = Config(file=opts.config)

    # init log facility
    try:
        loglevel = getattr(log, config.main.loglevel)
    except:
        loglevel = _loglevel

    if opts.loglevel is not None:
        loglevel = opts.loglevel

    log.basicConfig(level=loglevel, format=_logformat)

    # if specified, log to file as well
    try:
        logfile = config.main.logfile
        if logfile is not None and len(logfile):
            handler = log.FileHandler(filename=logfile)
            handler.setLevel(opts.loglevel)
            formatter = log.Formatter(_logformat)
            handler.setFormatter(formatter)
            log.getLogger('').addHandler(handler)
    except Exception, e:
        log.warn('unable to log to file: %s' % e)
        log.exception(e)

    # load specified protocol
    if opts.protocol:
        protocol = opts.protocol
        config.main.module = protocol
    else:
        protocol = config.main.module

    # dynamic load protocol handler
    try:
        module = __import__('protocols.' + protocol, globals(), locals(),
                ['ProtocolHandler'])
        ProtocolHandler = getattr(module, 'ProtocolHandler')
    except Exception, e:
        log.exception(e)
        return 1

    # daemonize if requested
    if config.main.detach or opts.detach:
        detach()

    # run bot & shut down threads when done
    try:
        ProtocolHandler(config=config, dir=dir).start()
    finally:
        for thread in threading.enumerate():
            thread._Thread__stop()

    return 0

if __name__ == '__main__':
    sys.exit(main())