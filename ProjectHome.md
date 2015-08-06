# Notice #

This is now hosted at [github](https://github.com/cjones/madcow)


# Overview #

Madcow is an extensible python IRC bot with support for SILC and AIM. It is fully customizable and has a simple API for creating modules that extend its functionality. Madcow ships with modules that emulate classic Infobot behavior and many other fun or useful utilities.

# Requirements #

  * Python 2.5 or higher
  * If you wish to use Madcow with the SILC protocol, you will need to install the silc-toolkit and pysilc libraries.
  * The memebot module requires SQLObject and a backend (MySQLdb or pysqlite3)

# Features #

In addition to the modules listed in the next section, madcow has support for the following features:

  * IRC auto-op administration via authentication
  * 2-way SMS to IRC message relay
  * Twitter to IRC message relay
  * URL tracking software (delicious or saved in a local database)
  * Capture images sent from phones, save locally, and display links in channel.

# Modules #

Madcow ships with the following modules, which can be enabled/disabled in config, as well as a template for easily creating your own in Python:

## Basic Functionality ##

  * **alias**: user-created aliases for custom interfacing with the bot
  * **area**: look up area codes
  * **babel**: language translations using google translation (generally requires utf-8 client support)
  * **bbcnews**: bbc news headlines and search article summaries
  * **calc**: google calculator results
  * **clock**: get the time in any place in the world (powered by google search)
  * **chp**: california real-time traffic reports
  * **cnn**: look up headlines from cnn.com
  * **delicious**: post all urls from channel to delicious account
  * **dictionary**: m-w definition of words
  * **google**: i'm feeling lucky query
  * **learn**: used for various modules to cache per-user data
  * **movie**: rate movie on imdb, rotten tomatoes and/or metacritic
  * **nslookup**: look up ip of hostnames
  * **seen**: keep track of last thing everyone in channel said
  * **spellcheck**: spellcheck a word/phrase using google
  * **stockquote**: get yahoo stock quotes
  * **summon**: summon users (send email/sms)
  * **traffic**: real-time traffic driving times (north. california only)
  * **urban**: look up word/phrase on urban dictionary
  * **weather**: look up weather from wunderground
  * **wikipedia**: look up summary from wikipedia
  * **wikiquotes**: look up quotes from wikiquotes
  * **yelp**: look up restaraunt reviews from yelp.com

## For Fun ##

  * **artfart**: random ascii art
  * **bash**: bash/qdb (irc/im) quotes and limericks
  * **bible**: get a quote from the bible by book chapter:verse
  * **care**: generate a high-precision care-o-meter
  * **conservapedia**: look up really inaccurate "conservative information"
  * **election**: keep track of senate seat predictions, or predicted electoral votes during Presidential elections
  * **factoids**: makes madcow remember stuff from chatter
  * **figlet**: generate ascii fonts
  * **fmylife**: random stories from fmylife.com or by ID
  * **grufti**: random response triggeres, like grufti bot
  * **hugs**: random group hug confession
  * **jinx**: someone owes you a coke for being unoriginal
  * **joke**: random joke
  * **karma**: keep track of karma (nick++, nick--)
  * **livejournal**: get livejournal entries (random or by nick)
  * **lyrics**: look up song lyrics (spammy!)
  * **megahal**: A 5th order Markov bot using MegaHAL for Eliza like "learning bot"
  * **memebot**: track urls and lay smackdown on old memes
  * **obama**: count of days since we've been free of Bush (formerly countdown to inaugaration)
  * **roll**: roll ad&d dice
  * **slut**: how slutty is the phrase? (safesearch vs. regular)
  * **steam**: Track a Steam player community to see what games people are playing currently.
  * **war**: current war status
  * **wardb**: look up item stats for Warhammer Online
  * **webtender**: how to make drinks!
  * **woot**: latest woot offer

# Protocols #

Madcow is written in a way that is agnostic to the underlying protocol transport.  As long as it has a send method and a receive method, Madcow can easily be extended to use this protocol.  It ships with protocol support for IRC, SILC, AIM and UNIX commandline.  To use SILC, you will need to install the silc-toolkit C library on your system, whereas IRC and AIM are implemented in pure Python.

A template is included in the protocol directory for creating your own.