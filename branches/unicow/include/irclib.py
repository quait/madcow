# Copyright (C) 1999--2002  Joel Rosdahl
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307  USA
#
# keltus <keltus@users.sourceforge.net>
#
# $Id: irclib.py,v 1.43 2005/12/24 22:12:40 keltus Exp $

"""irclib -- Internet Relay Chat (IRC) protocol client library.

This library is intended to encapsulate the IRC protocol at a quite
low level.  It provides an event-driven IRC client framework.  It has
a fairly thorough support for the basic IRC protocol, CTCP, DCC chat,
but DCC file transfers is not yet supported.

In order to understand how to make an IRC client, I'm afraid you more
or less must understand the IRC specifications.  They are available
here: [IRC specifications].

The main features of the IRC client framework are:

  * Abstraction of the IRC protocol.
  * Handles multiple simultaneous IRC server connections.
  * Handles server PONGing transparently.
  * Messages to the IRC server are done by calling methods on an IRC
    connection object.
  * Messages from an IRC server triggers events, which can be caught
    by event handlers.
  * Reading from and writing to IRC server sockets are normally done
    by an internal select() loop, but the select()ing may be done by
    an external main loop.
  * Functions can be registered to execute at specified times by the
    event-loop.
  * Decodes CTCP tagging correctly (hopefully); I haven't seen any
    other IRC client implementation that handles the CTCP
    specification subtilties.
  * A kind of simple, single-server, object-oriented IRC client class
    that dispatches events to instance methods is included.

Current limitations:

  * The IRC protocol shines through the abstraction a bit too much.
  * Data is not written asynchronously to the server, i.e. the write()
    may block if the TCP buffers are stuffed.
  * There are no support for DCC file transfers.
  * The author haven't even read RFC 2810, 2811, 2812 and 2813.
  * Like most projects, documentation is lacking...

.. [IRC specifications] http://www.irchelp.org/irchelp/rfc/
"""

import bisect
import re
import select
import socket
import string
import sys
import time
import types

VERSION = 0, 4, 6
DEBUG = 0

# TODO
# ----
# (maybe) thread safety
# (maybe) color parser convenience functions
# documentation (including all event types)
# (maybe) add awareness of different types of ircds
# send data asynchronously to the server (and DCC connections)
# (maybe) automatically close unused, passive DCC connections after a while

# NOTES
# -----
# connection.quit() only sends QUIT to the server.
# ERROR from the server triggers the error event and the disconnect event.
# dropping of the connection triggers the disconnect event.

class IRCError(Exception):
    """Represents an IRC exception."""
    pass


class IRC:
    """Class that handles one or several IRC server connections.

    When an IRC object has been instantiated, it can be used to create
    Connection objects that represent the IRC connections.  The
    responsibility of the IRC object is to provide an event-driven
    framework for the connections and to keep the connections alive.
    It runs a select loop to poll each connection's TCP socket and
    hands over the sockets with incoming data for processing by the
    corresponding connection.

    The methods of most interest for an IRC client writer are server,
    add_global_handler, remove_global_handler, execute_at,
    execute_delayed, process_once and process_forever.

    Here is an example:

        irc = irclib.IRC()
        server = irc.server()
        server.connect(\"irc.some.where\", 6667, \"my_nickname\")
        server.privmsg(\"a_nickname\", \"Hi there!\")
        irc.process_forever()

    This will connect to the IRC server irc.some.where on port 6667
    using the nickname my_nickname and send the message \"Hi there!\"
    to the nickname a_nickname.
    """

    def __init__(self, fn_to_add_socket=None,
                 fn_to_remove_socket=None,
                 fn_to_add_timeout=None):
        """Constructor for IRC objects.

        Optional arguments are fn_to_add_socket, fn_to_remove_socket
        and fn_to_add_timeout.  The first two specify functions that
        will be called with a socket object as argument when the IRC
        object wants to be notified (or stop being notified) of data
        coming on a new socket.  When new data arrives, the method
        process_data should be called.  Similarly, fn_to_add_timeout
        is called with a number of seconds (a floating point number)
        as first argument when the IRC object wants to receive a
        notification (by calling the process_timeout method).  So, if
        e.g. the argument is 42.17, the object wants the
        process_timeout method to be called after 42 seconds and 170
        milliseconds.

        The three arguments mainly exist to be able to use an external
        main loop (for example Tkinter's or PyGTK's main app loop)
        instead of calling the process_forever method.

        An alternative is to just call ServerConnection.process_once()
        once in a while.
        """

        if fn_to_add_socket and fn_to_remove_socket:
            self.fn_to_add_socket = fn_to_add_socket
            self.fn_to_remove_socket = fn_to_remove_socket
        else:
            self.fn_to_add_socket = None
            self.fn_to_remove_socket = None

        self.fn_to_add_timeout = fn_to_add_timeout
        self.connections = []
        self.handlers = {}
        self.delayed_commands = [] # list of tuples in the format (time, function, arguments)

        self.add_global_handler(u"ping", _ping_ponger, -42)

    def server(self):
        """Creates and returns a ServerConnection object."""

        c = ServerConnection(self)
        self.connections.append(c)
        return c

    def process_data(self, sockets):
        """Called when there is more data to read on connection sockets.

        Arguments:

            sockets -- A list of socket objects.

        See documentation for IRC.__init__.
        """
        for s in sockets:
            for c in self.connections:
                if s == c._get_socket():
                    c.process_data()

    def process_timeout(self):
        """Called when a timeout notification is due.

        See documentation for IRC.__init__.
        """
        t = time.time()
        while self.delayed_commands:
            if t >= self.delayed_commands[0][0]:
                self.delayed_commands[0][1](*self.delayed_commands[0][2])
                del self.delayed_commands[0]
            else:
                break

    def process_once(self, timeout=0):
        """Process data from connections once.

        Arguments:

            timeout -- How long the select() call should wait if no
                       data is available.

        This method should be called periodically to check and process
        incoming data, if there are any.  If that seems boring, look
        at the process_forever method.
        """
        sockets = map(lambda x: x._get_socket(), self.connections)
        sockets = filter(lambda x: x != None, sockets)
        if sockets:
            (i, o, e) = select.select(sockets, [], [], timeout)
            self.process_data(i)
        else:
            time.sleep(timeout)
        self.process_timeout()

    def process_forever(self, timeout=0.2):
        """Run an infinite loop, processing data from connections.

        This method repeatedly calls process_once.

        Arguments:

            timeout -- Parameter to pass to process_once.
        """
        while 1:
            self.process_once(timeout)

    def disconnect_all(self, message=u""):
        """Disconnects all connections."""
        for c in self.connections:
            c.disconnect(message)

    def add_global_handler(self, event, handler, priority=0):
        """Adds a global handler function for a specific event type.

        Arguments:

            event -- Event type (a string).  Check the values of the
            numeric_events dictionary in irclib.py for possible event
            types.

            handler -- Callback function.

            priority -- A number (the lower number, the higher priority).

        The handler function is called whenever the specified event is
        triggered in any of the connections.  See documentation for
        the Event class.

        The handler functions are called in priority order (lowest
        number is highest priority).  If a handler function returns
        \"NO MORE\", no more handlers will be called.
        """

        if not event in self.handlers:
            self.handlers[event] = []
        bisect.insort(self.handlers[event], ((priority, handler)))

    def remove_global_handler(self, event, handler):
        """Removes a global handler function.

        Arguments:

            event -- Event type (a string).

            handler -- Callback function.

        Returns 1 on success, otherwise 0.
        """
        if not event in self.handlers:
            return 0
        for h in self.handlers[event]:
            if handler == h[1]:
                self.handlers[event].remove(h)
        return 1

    def execute_at(self, at, function, arguments=()):
        """Execute a function at a specified time.

        Arguments:

            at -- Execute at this time (standard \"time_t\" time).

            function -- Function to call.

            arguments -- Arguments to give the function.
        """
        self.execute_delayed(at-time.time(), function, arguments)

    def execute_delayed(self, delay, function, arguments=()):
        """Execute a function after a specified time.

        Arguments:

            delay -- How many seconds to wait.

            function -- Function to call.

            arguments -- Arguments to give the function.
        """
        bisect.insort(self.delayed_commands, (delay+time.time(), function, arguments))
        if self.fn_to_add_timeout:
            self.fn_to_add_timeout(delay)

    def dcc(self, dcctype=u"chat"):
        """Creates and returns a DCCConnection object.

        Arguments:

            dcctype -- "chat" for DCC CHAT connections or "raw" for
                       DCC SEND (or other DCC types). If "chat",
                       incoming data will be split in newline-separated
                       chunks. If "raw", incoming data is not touched.
        """
        c = DCCConnection(self, dcctype)
        self.connections.append(c)
        return c

    def _handle_event(self, connection, event):
        """[Internal]"""
        h = self.handlers
        for handler in h.get(u"all_events", []) + h.get(event.eventtype(), []):
            if handler[1](connection, event) == u"NO MORE":
                return

    def _remove_connection(self, connection):
        """[Internal]"""
        self.connections.remove(connection)
        if self.fn_to_remove_socket:
            self.fn_to_remove_socket(connection._get_socket())

_rfc_1459_command_regexp = re.compile(u"^(:(?P<prefix>[^ ]+) +)?(?P<command>[^ ]+)( *(?P<argument> .+))?")


class Connection:
    """Base class for IRC connections.

    Must be overridden.
    """
    def __init__(self, irclibobj):
        self.irclibobj = irclibobj

    def _get_socket():
        raise IRCError, u"Not overridden"

    ##############################
    ### Convenience wrappers.

    def execute_at(self, at, function, arguments=()):
        self.irclibobj.execute_at(at, function, arguments)

    def execute_delayed(self, delay, function, arguments=()):
        self.irclibobj.execute_delayed(delay, function, arguments)


class ServerConnectionError(IRCError):
    pass

class ServerNotConnectedError(ServerConnectionError):
    pass


# Huh!?  Crrrrazy EFNet doesn't follow the RFC: their ircd seems to
# use \n as message separator!  :P
_linesep_regexp = re.compile(u"\r?\n")

class ServerConnection(Connection):
    """This class represents an IRC server connection.

    ServerConnection objects are instantiated by calling the server
    method on an IRC object.
    """

    def __init__(self, irclibobj):
        Connection.__init__(self, irclibobj)
        self.connected = 0  # Not connected yet.
        self.socket = None

    def connect(self, server, port, nickname, password=None, username=None,
                ircname=None, localaddress=u"", localport=0, ssl=False):
        """Connect/reconnect to a server.

        Arguments:

            server -- Server name.

            port -- Port number.

            nickname -- The nickname.

            password -- Password (if any).

            username -- The username.

            ircname -- The IRC name ("realname").

            localaddress -- Bind the connection to a specific local IP address.

            localport -- Bind the connection to a specific local port.

        This function can be called to reconnect a closed connection.

        Returns the ServerConnection object.
        """
        if self.connected:
            self.disconnect(u"Changing servers")

        self.previous_buffer = u""
        self.handlers = {}
        self.real_server_name = u""
        self.real_nickname = nickname
        self.server = server
        self.port = port
        self.nickname = nickname
        self.username = username or nickname
        self.ircname = ircname or nickname
        self.password = password
        self.localaddress = localaddress
        self.localport = localport
        self.localhost = socket.gethostname()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.bind((self.localaddress, self.localport))
            self.socket.connect((self.server, self.port))
        except socket.error, x:
            self.socket.close()
            self.socket = None
            raise ServerConnectionError, u"Couldn't connect to socket: %s" % x
        if ssl:
            self.transport = socket.ssl(self.socket)
            self.sock_read = self.transport.read
            self.sock_write = self.transport.write
        else:
            self.transport = self.socket
            self.sock_read = self.transport.recv
            self.sock_write = self.transport.send
        self.connected = 1
        if self.irclibobj.fn_to_add_socket:
            self.irclibobj.fn_to_add_socket(self.socket)

        # Log on...
        if self.password:
            self.pass_(self.password)
        self.nick(self.nickname)
        self.user(self.username, self.ircname)
        return self

    def close(self):
        """Close the connection.

        This method closes the connection permanently; after it has
        been called, the object is unusable.
        """

        self.disconnect(u"Closing object")
        self.irclibobj._remove_connection(self)

    def _get_socket(self):
        """[Internal]"""
        return self.socket

    def get_server_name(self):
        """Get the (real) server name.

        This method returns the (real) server name, or, more
        specifically, what the server calls itself.
        """

        if self.real_server_name:
            return self.real_server_name
        else:
            return u""

    def get_nickname(self):
        """Get the (real) nick name.

        This method returns the (real) nickname.  The library keeps
        track of nick changes, so it might not be the nick name that
        was passed to the connect() method.  """

        return self.real_nickname

    def process_data(self):
        """[Internal]"""

        try:
            new_data = self.sock_read(2**14)
        except socket.error, x:
            # The server hung up.
            self.disconnect(u"Connection reset by peer")
            return
        if not new_data:
            # Read nothing: connection must be down.
            self.disconnect(u"Connection reset by peer")
            return

        lines = _linesep_regexp.split(self.previous_buffer + new_data)

        # Save the last, unfinished line.
        self.previous_buffer = lines[-1]
        lines = lines[:-1]

        for line in lines:
            if DEBUG:
                print u"FROM SERVER:", line

            if not line:
                continue

            prefix = None
            command = None
            arguments = None
            self._handle_event(Event(u"all_raw_messages",
                                     self.get_server_name(),
                                     None,
                                     [line]))

            m = _rfc_1459_command_regexp.match(line)
            if m.group(u"prefix"):
                prefix = m.group(u"prefix")
                if not self.real_server_name:
                    self.real_server_name = prefix

            if m.group(u"command"):
                command = m.group(u"command").lower()

            if m.group(u"argument"):
                a = m.group(u"argument").split(u" :", 1)
                arguments = a[0].split()
                if len(a) == 2:
                    arguments.append(a[1])

            # Translate numerics into more readable strings.
            if command in numeric_events:
                command = numeric_events[command]

            if command == u"nick":
                if nm_to_n(prefix) == self.real_nickname:
                    self.real_nickname = arguments[0]
            elif command == u"welcome":
                # Record the nickname in case the client changed nick
                # in a nicknameinuse callback.
                self.real_nickname = arguments[0]

            if command in [u"privmsg", u"notice"]:
                target, message = arguments[0], arguments[1]
                messages = _ctcp_dequote(message)

                if command == u"privmsg":
                    if is_channel(target):
                        command = u"pubmsg"
                else:
                    if is_channel(target):
                        command = u"pubnotice"
                    else:
                        command = u"privnotice"

                for m in messages:
                    if type(m) is types.TupleType:
                        if command in [u"privmsg", u"pubmsg"]:
                            command = u"ctcp"
                        else:
                            command = u"ctcpreply"

                        m = list(m)
                        if DEBUG:
                            print u"command: %s, source: %s, target: %s, arguments: %s" % (
                                command, prefix, target, m)
                        self._handle_event(Event(command, prefix, target, m))
                        if command == u"ctcp" and m[0] == u"ACTION":
                            self._handle_event(Event(u"action", prefix, target, m[1:]))
                    else:
                        if DEBUG:
                            print u"command: %s, source: %s, target: %s, arguments: %s" % (
                                command, prefix, target, [m])
                        self._handle_event(Event(command, prefix, target, [m]))
            else:
                target = None

                if command == u"quit":
                    arguments = [arguments[0]]
                elif command == u"ping":
                    target = arguments[0]
                else:
                    target = arguments[0]
                    arguments = arguments[1:]

                if command == u"mode":
                    if not is_channel(target):
                        command = u"umode"

                if DEBUG:
                    print u"command: %s, source: %s, target: %s, arguments: %s" % (
                        command, prefix, target, arguments)
                self._handle_event(Event(command, prefix, target, arguments))

    def _handle_event(self, event):
        """[Internal]"""
        self.irclibobj._handle_event(self, event)
        if event.eventtype() in self.handlers:
            for fn in self.handlers[event.eventtype()]:
                fn(self, event)

    def is_connected(self):
        """Return connection status.

        Returns true if connected, otherwise false.
        """
        return self.connected

    def add_global_handler(self, *args):
        """Add global handler.

        See documentation for IRC.add_global_handler.
        """
        self.irclibobj.add_global_handler(*args)

    def remove_global_handler(self, *args):
        """Remove global handler.

        See documentation for IRC.remove_global_handler.
        """
        self.irclibobj.remove_global_handler(*args)

    def action(self, target, action):
        """Send a CTCP ACTION command."""
        self.ctcp(u"ACTION", target, action)

    def admin(self, server=u""):
        """Send an ADMIN command."""
        self.send_raw(u" ".join([u"ADMIN", server]).strip())

    def ctcp(self, ctcptype, target, parameter=u""):
        """Send a CTCP command."""
        ctcptype = ctcptype.upper()
        self.privmsg(target, u"\001%s%s\001" % (ctcptype, parameter and (u" " + parameter) or u""))

    def ctcp_reply(self, target, parameter):
        """Send a CTCP REPLY command."""
        self.notice(target, u"\001%s\001" % parameter)

    def disconnect(self, message=u""):
        """Hang up the connection.

        Arguments:

            message -- Quit message.
        """
        if not self.connected:
            return

        self.connected = 0

        self.quit(message)

        try:
            self.socket.close()
        except socket.error, x:
            pass
        self.socket = None
        self._handle_event(Event(u"disconnect", self.server, u"", [message]))

    def globops(self, text):
        """Send a GLOBOPS command."""
        self.send_raw(u"GLOBOPS :" + text)

    def info(self, server=u""):
        """Send an INFO command."""
        self.send_raw(u" ".join([u"INFO", server]).strip())

    def invite(self, nick, channel):
        """Send an INVITE command."""
        self.send_raw(u" ".join([u"INVITE", nick, channel]).strip())

    def ison(self, nicks):
        """Send an ISON command.

        Arguments:

            nicks -- List of nicks.
        """
        self.send_raw(u"ISON " + u" ".join(nicks))

    def join(self, channel, key=u""):
        """Send a JOIN command."""
        self.send_raw(u"JOIN %s%s" % (channel, (key and (u" " + key))))

    def kick(self, channel, nick, comment=u""):
        """Send a KICK command."""
        self.send_raw(u"KICK %s %s%s" % (channel, nick, (comment and (u" :" + comment))))

    def links(self, remote_server=u"", server_mask=u""):
        """Send a LINKS command."""
        command = u"LINKS"
        if remote_server:
            command = command + u" " + remote_server
        if server_mask:
            command = command + u" " + server_mask
        self.send_raw(command)

    def list(self, channels=None, server=u""):
        """Send a LIST command."""
        command = u"LIST"
        if channels:
            command = command + u" " + u",".join(channels)
        if server:
            command = command + u" " + server
        self.send_raw(command)

    def lusers(self, server=u""):
        """Send a LUSERS command."""
        self.send_raw(u"LUSERS" + (server and (u" " + server)))

    def mode(self, target, command):
        """Send a MODE command."""
        self.send_raw(u"MODE %s %s" % (target, command))

    def motd(self, server=u""):
        """Send an MOTD command."""
        self.send_raw(u"MOTD" + (server and (u" " + server)))

    def names(self, channels=None):
        """Send a NAMES command."""
        self.send_raw(u"NAMES" + (channels and (u" " + u",".join(channels)) or u""))

    def nick(self, newnick):
        """Send a NICK command."""
        self.send_raw(u"NICK " + newnick)

    def notice(self, target, text):
        """Send a NOTICE command."""
        # Should limit len(text) here!
        self.send_raw(u"NOTICE %s :%s" % (target, text))

    def oper(self, nick, password):
        """Send an OPER command."""
        self.send_raw(u"OPER %s %s" % (nick, password))

    def part(self, channels, message=u""):
        """Send a PART command."""
        if type(channels) == types.StringType:
            self.send_raw(u"PART " + channels + (message and (u" " + message)))
        else:
            self.send_raw(u"PART " + u",".join(channels) + (message and (u" " + message)))

    def pass_(self, password):
        """Send a PASS command."""
        self.send_raw(u"PASS " + password)

    def ping(self, target, target2=u""):
        """Send a PING command."""
        self.send_raw(u"PING %s%s" % (target, target2 and (u" " + target2)))

    def pong(self, target, target2=u""):
        """Send a PONG command."""
        self.send_raw(u"PONG %s%s" % (target, target2 and (u" " + target2)))

    def privmsg(self, target, text):
        """Send a PRIVMSG command."""
        # Should limit len(text) here!
        self.send_raw(u"PRIVMSG %s :%s" % (target, text))

    def privmsg_many(self, targets, text):
        """Send a PRIVMSG command to multiple targets."""
        # Should limit len(text) here!
        self.send_raw(u"PRIVMSG %s :%s" % (u",".join(targets), text))

    def quit(self, message=u""):
        """Send a QUIT command."""
        # Note that many IRC servers don't use your QUIT message
        # unless you've been connected for at least 5 minutes!
        self.send_raw(u"QUIT" + (message and (u" :" + message)))

    def sconnect(self, target, port=u"", server=u""):
        """Send an SCONNECT command."""
        self.send_raw(u"CONNECT %s%s%s" % (target,
                                          port and (u" " + port),
                                          server and (u" " + server)))

    def send_raw(self, string):
        """Send raw string to the server.

        The string will be padded with appropriate CR LF.
        """
        if self.socket is None:
            raise ServerNotConnectedError, u"Not connected."
        try:
            self.sock_write(string + u"\r\n")
            if DEBUG:
                print u"TO SERVER:", string
        except socket.error, x:
            # Ouch!
            self.disconnect(u"Connection reset by peer.")

    def squit(self, server, comment=u""):
        """Send an SQUIT command."""
        self.send_raw(u"SQUIT %s%s" % (server, comment and (u" :" + comment)))

    def stats(self, statstype, server=u""):
        """Send a STATS command."""
        self.send_raw(u"STATS %s%s" % (statstype, server and (u" " + server)))

    def time(self, server=u""):
        """Send a TIME command."""
        self.send_raw(u"TIME" + (server and (u" " + server)))

    def topic(self, channel, new_topic=None):
        """Send a TOPIC command."""
        if new_topic is None:
            self.send_raw(u"TOPIC " + channel)
        else:
            self.send_raw(u"TOPIC %s :%s" % (channel, new_topic))

    def trace(self, target=u""):
        """Send a TRACE command."""
        self.send_raw(u"TRACE" + (target and (u" " + target)))

    def user(self, username, realname):
        """Send a USER command."""
        self.send_raw(u"USER %s 0 * :%s" % (username, realname))

    def userhost(self, nicks):
        """Send a USERHOST command."""
        self.send_raw(u"USERHOST " + u",".join(nicks))

    def users(self, server=u""):
        """Send a USERS command."""
        self.send_raw(u"USERS" + (server and (u" " + server)))

    def version(self, server=u""):
        """Send a VERSION command."""
        self.send_raw(u"VERSION" + (server and (u" " + server)))

    def wallops(self, text):
        """Send a WALLOPS command."""
        self.send_raw(u"WALLOPS :" + text)

    def who(self, target=u"", op=u""):
        """Send a WHO command."""
        self.send_raw(u"WHO%s%s" % (target and (u" " + target), op and (u" o")))

    def whois(self, targets):
        """Send a WHOIS command."""
        self.send_raw(u"WHOIS " + u",".join(targets))

    def whowas(self, nick, max=u"", server=u""):
        """Send a WHOWAS command."""
        self.send_raw(u"WHOWAS %s%s%s" % (nick,
                                         max and (u" " + max),
                                         server and (u" " + server)))


class DCCConnectionError(IRCError):
    pass


class DCCConnection(Connection):
    """This class represents a DCC connection.

    DCCConnection objects are instantiated by calling the dcc
    method on an IRC object.
    """
    def __init__(self, irclibobj, dcctype):
        Connection.__init__(self, irclibobj)
        self.connected = 0
        self.passive = 0
        self.dcctype = dcctype
        self.peeraddress = None
        self.peerport = None

    def connect(self, address, port):
        """Connect/reconnect to a DCC peer.

        Arguments:
            address -- Host/IP address of the peer.

            port -- The port number to connect to.

        Returns the DCCConnection object.
        """
        self.peeraddress = socket.gethostbyname(address)
        self.peerport = port
        self.socket = None
        self.previous_buffer = u""
        self.handlers = {}
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.passive = 0
        try:
            self.socket.connect((self.peeraddress, self.peerport))
        except socket.error, x:
            raise DCCConnectionError, u"Couldn't connect to socket: %s" % x
        self.connected = 1
        if self.irclibobj.fn_to_add_socket:
            self.irclibobj.fn_to_add_socket(self.socket)
        return self

    def listen(self):
        """Wait for a connection/reconnection from a DCC peer.

        Returns the DCCConnection object.

        The local IP address and port are available as
        self.localaddress and self.localport.  After connection from a
        peer, the peer address and port are available as
        self.peeraddress and self.peerport.
        """
        self.previous_buffer = u""
        self.handlers = {}
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.passive = 1
        try:
            self.socket.bind((socket.gethostbyname(socket.gethostname()), 0))
            self.localaddress, self.localport = self.socket.getsockname()
            self.socket.listen(10)
        except socket.error, x:
            raise DCCConnectionError, u"Couldn't bind socket: %s" % x
        return self

    def disconnect(self, message=u""):
        """Hang up the connection and close the object.

        Arguments:

            message -- Quit message.
        """
        if not self.connected:
            return

        self.connected = 0
        try:
            self.socket.close()
        except socket.error, x:
            pass
        self.socket = None
        self.irclibobj._handle_event(
            self,
            Event(u"dcc_disconnect", self.peeraddress, u"", [message]))
        self.irclibobj._remove_connection(self)

    def process_data(self):
        """[Internal]"""

        if self.passive and not self.connected:
            conn, (self.peeraddress, self.peerport) = self.socket.accept()
            self.socket.close()
            self.socket = conn
            self.connected = 1
            if DEBUG:
                print u"DCC connection from %s:%d" % (
                    self.peeraddress, self.peerport)
            self.irclibobj._handle_event(
                self,
                Event(u"dcc_connect", self.peeraddress, None, None))
            return

        try:
            new_data = self.sock_read(2**14)
        except socket.error, x:
            # The server hung up.
            self.disconnect(u"Connection reset by peer")
            return
        if not new_data:
            # Read nothing: connection must be down.
            self.disconnect(u"Connection reset by peer")
            return

        if self.dcctype == u"chat":
            # The specification says lines are terminated with LF, but
            # it seems safer to handle CR LF terminations too.
            chunks = _linesep_regexp.split(self.previous_buffer + new_data)

            # Save the last, unfinished line.
            self.previous_buffer = chunks[-1]
            if len(self.previous_buffer) > 2**14:
                # Bad peer! Naughty peer!
                self.disconnect()
                return
            chunks = chunks[:-1]
        else:
            chunks = [new_data]

        command = u"dccmsg"
        prefix = self.peeraddress
        target = None
        for chunk in chunks:
            if DEBUG:
                print u"FROM PEER:", chunk
            arguments = [chunk]
            if DEBUG:
                print u"command: %s, source: %s, target: %s, arguments: %s" % (
                    command, prefix, target, arguments)
            self.irclibobj._handle_event(
                self,
                Event(command, prefix, target, arguments))

    def _get_socket(self):
        """[Internal]"""
        return self.socket

    def privmsg(self, string):
        """Send data to DCC peer.

        The string will be padded with appropriate LF if it's a DCC
        CHAT session.
        """
        try:
            self.sock_write(string)
            if self.dcctype == u"chat":
                self.sock_write(u"\n")
            if DEBUG:
                print u"TO PEER: %s\n" % string
        except socket.error, x:
            # Ouch!
            self.disconnect(u"Connection reset by peer.")

class SimpleIRCClient:
    """A simple single-server IRC client class.

    This is an example of an object-oriented wrapper of the IRC
    framework.  A real IRC client can be made by subclassing this
    class and adding appropriate methods.

    The method on_join will be called when a "join" event is created
    (which is done when the server sends a JOIN messsage/command),
    on_privmsg will be called for "privmsg" events, and so on.  The
    handler methods get two arguments: the connection object (same as
    self.connection) and the event object.

    Instance attributes that can be used by sub classes:

        ircobj -- The IRC instance.

        connection -- The ServerConnection instance.

        dcc_connections -- A list of DCCConnection instances.
    """
    def __init__(self):
        self.ircobj = IRC()
        self.connection = self.ircobj.server()
        self.dcc_connections = []
        self.ircobj.add_global_handler(u"all_events", self._dispatcher, -10)
        self.ircobj.add_global_handler(u"dcc_disconnect", self._dcc_disconnect, -10)

    def _dispatcher(self, c, e):
        """[Internal]"""
        m = u"on_" + e.eventtype()
        if hasattr(self, m):
            getattr(self, m)(c, e)

    def _dcc_disconnect(self, c, e):
        self.dcc_connections.remove(c)

    def connect(self, server, port, nickname, password=None, username=None,
                ircname=None, localaddress=u"", localport=0):
        """Connect/reconnect to a server.

        Arguments:

            server -- Server name.

            port -- Port number.

            nickname -- The nickname.

            password -- Password (if any).

            username -- The username.

            ircname -- The IRC name.

            localaddress -- Bind the connection to a specific local IP address.

            localport -- Bind the connection to a specific local port.

        This function can be called to reconnect a closed connection.
        """
        self.connection.connect(server, port, nickname,
                                password, username, ircname,
                                localaddress, localport)

    def dcc_connect(self, address, port, dcctype=u"chat"):
        """Connect to a DCC peer.

        Arguments:

            address -- IP address of the peer.

            port -- Port to connect to.

        Returns a DCCConnection instance.
        """
        dcc = self.ircobj.dcc(dcctype)
        self.dcc_connections.append(dcc)
        dcc.connect(address, port)
        return dcc

    def dcc_listen(self, dcctype=u"chat"):
        """Listen for connections from a DCC peer.

        Returns a DCCConnection instance.
        """
        dcc = self.ircobj.dcc(dcctype)
        self.dcc_connections.append(dcc)
        dcc.listen()
        return dcc

    def start(self):
        """Start the IRC client."""
        self.ircobj.process_forever()


class Event:
    """Class representing an IRC event."""
    def __init__(self, eventtype, source, target, arguments=None):
        """Constructor of Event objects.

        Arguments:

            eventtype -- A string describing the event.

            source -- The originator of the event (a nick mask or a server).

            target -- The target of the event (a nick or a channel).

            arguments -- Any event specific arguments.
        """
        self._eventtype = eventtype
        self._source = source
        self._target = target
        if arguments:
            self._arguments = arguments
        else:
            self._arguments = []

    def eventtype(self):
        """Get the event type."""
        return self._eventtype

    def source(self):
        """Get the event source."""
        return self._source

    def target(self):
        """Get the event target."""
        return self._target

    def arguments(self):
        """Get the event arguments."""
        return self._arguments

_LOW_LEVEL_QUOTE = u"\020"
_CTCP_LEVEL_QUOTE = u"\134"
_CTCP_DELIMITER = u"\001"

_low_level_mapping = {
    u"0": u"\000",
    u"n": u"\n",
    u"r": u"\r",
    _LOW_LEVEL_QUOTE: _LOW_LEVEL_QUOTE
}

_low_level_regexp = re.compile(_LOW_LEVEL_QUOTE + u"(.)")

def mask_matches(nick, mask):
    """Check if a nick matches a mask.

    Returns true if the nick matches, otherwise false.
    """
    nick = irc_lower(nick)
    mask = irc_lower(mask)
    mask = mask.replace(u"\\", "\\\\")
    for ch in u".$|[](){}+":
        mask = mask.replace(ch, "\\" + ch)
    mask = mask.replace(u"?", u".")
    mask = mask.replace(u"*", u".*")
    r = re.compile(mask, re.IGNORECASE)
    return r.match(nick)

_special = u"-[]\\`^{}"
nick_characters = string.ascii_letters + string.digits + _special
_ircstring_translation = string.maketrans(string.ascii_uppercase + u"[]\\^",
                                          string.ascii_lowercase + u"{}|~")

def irc_lower(s):
    """Returns a lowercased string.

    The definition of lowercased comes from the IRC specification (RFC
    1459).
    """
    return s.translate(_ircstring_translation)

def _ctcp_dequote(message):
    """[Internal] Dequote a message according to CTCP specifications.

    The function returns a list where each element can be either a
    string (normal message) or a tuple of one or two strings (tagged
    messages).  If a tuple has only one element (ie is a singleton),
    that element is the tag; otherwise the tuple has two elements: the
    tag and the data.

    Arguments:

        message -- The message to be decoded.
    """

    def _low_level_replace(match_obj):
        ch = match_obj.group(1)

        # If low_level_mapping doesn't have the character as key, we
        # should just return the character.
        return _low_level_mapping.get(ch, ch)

    if _LOW_LEVEL_QUOTE in message:
        # Yup, there was a quote.  Release the dequoter, man!
        message = _low_level_regexp.sub(_low_level_replace, message)

    if _CTCP_DELIMITER not in message:
        return [message]
    else:
        # Split it into parts.  (Does any IRC client actually *use*
        # CTCP stacking like this?)
        chunks = message.split(_CTCP_DELIMITER)

        messages = []
        i = 0
        while i < len(chunks)-1:
            # Add message if it's non-empty.
            if len(chunks[i]) > 0:
                messages.append(chunks[i])

            if i < len(chunks)-2:
                # Aye!  CTCP tagged data ahead!
                messages.append(tuple(chunks[i+1].split(u" ", 1)))

            i = i + 2

        if len(chunks) % 2 == 0:
            # Hey, a lonely _CTCP_DELIMITER at the end!  This means
            # that the last chunk, including the delimiter, is a
            # normal message!  (This is according to the CTCP
            # specification.)
            messages.append(_CTCP_DELIMITER + chunks[-1])

        return messages

def is_channel(string):
    """Check if a string is a channel name.

    Returns true if the argument is a channel name, otherwise false.
    """
    return string and string[0] in u"#&+!"

def ip_numstr_to_quad(num):
    """Convert an IP number as an integer given in ASCII
    representation (e.g. '3232235521') to an IP address string
    (e.g. '192.168.0.1')."""
    n = long(num)
    p = map(str, map(int, [n >> 24 & 0xFF, n >> 16 & 0xFF,
                           n >> 8 & 0xFF, n & 0xFF]))
    return u".".join(p)

def ip_quad_to_numunicode(quad):
    """Convert an IP address string (e.g. '192.168.0.1') to an IP
    number as an integer given in ASCII representation
    (e.g. '3232235521')."""
    p = map(long, quad.split(u"."))
    s = unicode((p[0] << 24) | (p[1] << 16) | (p[2] << 8) | p[3])
    if s[-1] == u"L":
        s = s[:-1]
    return s

def nm_to_n(s):
    """Get the nick part of a nickmask.

    (The source of an Event is a nickmask.)
    """
    return s.split(u"!")[0]

def nm_to_uh(s):
    """Get the userhost part of a nickmask.

    (The source of an Event is a nickmask.)
    """
    return s.split(u"!")[1]

def nm_to_h(s):
    """Get the host part of a nickmask.

    (The source of an Event is a nickmask.)
    """
    return s.split(u"@")[1]

def nm_to_u(s):
    """Get the user part of a nickmask.

    (The source of an Event is a nickmask.)
    """
    s = s.split(u"!")[1]
    return s.split(u"@")[0]

def parse_nick_modes(mode_string):
    """Parse a nick mode string.

    The function returns a list of lists with three members: sign,
    mode and argument.  The sign is \"+\" or \"-\".  The argument is
    always None.

    Example:

    >>> irclib.parse_nick_modes(\"+ab-c\")
    [['+', 'a', None], ['+', 'b', None], ['-', 'c', None]]
    """

    return _parse_modes(mode_string, u"")

def parse_channel_modes(mode_string):
    """Parse a channel mode string.

    The function returns a list of lists with three members: sign,
    mode and argument.  The sign is \"+\" or \"-\".  The argument is
    None if mode isn't one of \"b\", \"k\", \"l\", \"v\" or \"o\".

    Example:

    >>> irclib.parse_channel_modes(\"+ab-c foo\")
    [['+', 'a', None], ['+', 'b', 'foo'], ['-', 'c', None]]
    """

    return _parse_modes(mode_string, u"bklvo")

def _parse_modes(mode_string, unary_modes=u""):
    """[Internal]"""
    modes = []
    arg_count = 0

    # State variable.
    sign = u""

    a = mode_string.split()
    if len(a) == 0:
        return []
    else:
        mode_part, args = a[0], a[1:]

    if mode_part[0] not in u"+-":
        return []
    for ch in mode_part:
        if ch in u"+-":
            sign = ch
        elif ch == u" ":
            collecting_arguments = 1
        elif ch in unary_modes:
            if len(args) >= arg_count + 1:
                modes.append([sign, ch, args[arg_count]])
                arg_count = arg_count + 1
            else:
                modes.append([sign, ch, None])
        else:
            modes.append([sign, ch, None])
    return modes

def _ping_ponger(connection, event):
    """[Internal]"""
    connection.pong(event.target())

# Numeric table mostly stolen from the Perl IRC module (Net::IRC).
numeric_events = {
    u"001": u"welcome",
    u"002": u"yourhost",
    u"003": u"created",
    u"004": u"myinfo",
    u"005": u"featurelist",  # XXX
    u"200": u"tracelink",
    u"201": u"traceconnecting",
    u"202": u"tracehandshake",
    u"203": u"traceunknown",
    u"204": u"traceoperator",
    u"205": u"traceuser",
    u"206": u"traceserver",
    u"207": u"traceservice",
    u"208": u"tracenewtype",
    u"209": u"traceclass",
    u"210": u"tracereconnect",
    u"211": u"statslinkinfo",
    u"212": u"statscommands",
    u"213": u"statscline",
    u"214": u"statsnline",
    u"215": u"statsiline",
    u"216": u"statskline",
    u"217": u"statsqline",
    u"218": u"statsyline",
    u"219": u"endofstats",
    u"221": u"umodeis",
    u"231": u"serviceinfo",
    u"232": u"endofservices",
    u"233": u"service",
    u"234": u"servlist",
    u"235": u"servlistend",
    u"241": u"statslline",
    u"242": u"statsuptime",
    u"243": u"statsoline",
    u"244": u"statshline",
    u"250": u"luserconns",
    u"251": u"luserclient",
    u"252": u"luserop",
    u"253": u"luserunknown",
    u"254": u"luserchannels",
    u"255": u"luserme",
    u"256": u"adminme",
    u"257": u"adminloc1",
    u"258": u"adminloc2",
    u"259": u"adminemail",
    u"261": u"tracelog",
    u"262": u"endoftrace",
    u"263": u"tryagain",
    u"265": u"n_local",
    u"266": u"n_global",
    u"300": u"none",
    u"301": u"away",
    u"302": u"userhost",
    u"303": u"ison",
    u"305": u"unaway",
    u"306": u"nowaway",
    u"311": u"whoisuser",
    u"312": u"whoisserver",
    u"313": u"whoisoperator",
    u"314": u"whowasuser",
    u"315": u"endofwho",
    u"316": u"whoischanop",
    u"317": u"whoisidle",
    u"318": u"endofwhois",
    u"319": u"whoischannels",
    u"321": u"liststart",
    u"322": u"list",
    u"323": u"listend",
    u"324": u"channelmodeis",
    u"329": u"channelcreate",
    u"331": u"notopic",
    u"332": u"currenttopic",
    u"333": u"topicinfo",
    u"341": u"inviting",
    u"342": u"summoning",
    u"346": u"invitelist",
    u"347": u"endofinvitelist",
    u"348": u"exceptlist",
    u"349": u"endofexceptlist",
    u"351": u"version",
    u"352": u"whoreply",
    u"353": u"namreply",
    u"361": u"killdone",
    u"362": u"closing",
    u"363": u"closeend",
    u"364": u"links",
    u"365": u"endoflinks",
    u"366": u"endofnames",
    u"367": u"banlist",
    u"368": u"endofbanlist",
    u"369": u"endofwhowas",
    u"371": u"info",
    u"372": u"motd",
    u"373": u"infostart",
    u"374": u"endofinfo",
    u"375": u"motdstart",
    u"376": u"endofmotd",
    u"377": u"motd2",        # 1997-10-16 -- tkil
    u"381": u"youreoper",
    u"382": u"rehashing",
    u"384": u"myportis",
    u"391": u"time",
    u"392": u"usersstart",
    u"393": u"users",
    u"394": u"endofusers",
    u"395": u"nousers",
    u"401": u"nosuchnick",
    u"402": u"nosuchserver",
    u"403": u"nosuchchannel",
    u"404": u"cannotsendtochan",
    u"405": u"toomanychannels",
    u"406": u"wasnosuchnick",
    u"407": u"toomanytargets",
    u"409": u"noorigin",
    u"411": u"norecipient",
    u"412": u"notexttosend",
    u"413": u"notoplevel",
    u"414": u"wildtoplevel",
    u"421": u"unknowncommand",
    u"422": u"nomotd",
    u"423": u"noadmininfo",
    u"424": u"fileerror",
    u"431": u"nonicknamegiven",
    u"432": u"erroneusnickname", # Thiss iz how its speld in thee RFC.
    u"433": u"nicknameinuse",
    u"436": u"nickcollision",
    u"437": u"unavailresource",  # u"Nick temporally unavailable"
    u"441": u"usernotinchannel",
    u"442": u"notonchannel",
    u"443": u"useronchannel",
    u"444": u"nologin",
    u"445": u"summondisabled",
    u"446": u"usersdisabled",
    u"451": u"notregistered",
    u"461": u"needmoreparams",
    u"462": u"alreadyregistered",
    u"463": u"nopermforhost",
    u"464": u"passwdmismatch",
    u"465": u"yourebannedcreep", # I love this one...
    u"466": u"youwillbebanned",
    u"467": u"keyset",
    u"471": u"channelisfull",
    u"472": u"unknownmode",
    u"473": u"inviteonlychan",
    u"474": u"bannedfromchan",
    u"475": u"badchannelkey",
    u"476": u"badchanmask",
    u"477": u"nochanmodes",  # u"Channel doesn't support modes"
    u"478": u"banlistfull",
    u"481": u"noprivileges",
    u"482": u"chanoprivsneeded",
    u"483": u"cantkillserver",
    u"484": u"restricted",   # Connection is restricted
    u"485": u"uniqopprivsneeded",
    u"491": u"nooperhost",
    u"492": u"noservicehost",
    u"501": u"umodeunknownflag",
    u"502": u"usersdontmatch",
}

generated_events = [
    # Generated events
    u"dcc_connect",
    u"dcc_disconnect",
    u"dccmsg",
    u"disconnect",
    u"ctcp",
    u"ctcpreply",
]

protocol_events = [
    # IRC protocol events
    u"error",
    u"join",
    u"kick",
    u"mode",
    u"part",
    u"ping",
    u"privmsg",
    u"privnotice",
    u"pubmsg",
    u"pubnotice",
    u"quit",
    u"invite",
    u"pong",
]

all_events = generated_events + protocol_events + numeric_events.values()
