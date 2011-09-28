"""RSS generation"""

import datetime

from django.conf import settings
from django.core.urlresolvers import reverse
from django.contrib.sites.models import Site

from gruntle.memebot.rss.generator import RSSItem, RSS2, Image
from gruntle.memebot.models import SerializedData, Link
from gruntle.memebot.decorators import logged, locked
from gruntle.memebot.utils import first, local_to_gmt, plural

DEFAULT_MAX_LINKS = 100

current_site = Site.objects.get_current()

class LinkItem(RSSItem):

    """A single Link feed item"""

    def __init__(self, link):
        # TODO i think description should get set to the rendered page? somehow..
        super(LinkItem, self).__init__(
                title=first(link.title, link.resolved_url, link.url, 'n/a'),
                link=first(link.resolved_url, link.url),
                guid=link.guid,
                pubDate=local_to_gmt(link.created))


class LinkFeed(RSS2):

    """A feed generator for Link objects"""

    def __init__(self, links, feed):
        now = local_to_gmt(datetime.datetime.now())

        if feed.image is None:
            image = None
        else:
            image_url, image_title, image_link = feed.iamge
            image = Image(url=image_url, title=image_title, link=image_link)

        super(LinkFeed, self).__init__(
                title=feed.title,
                link=reverse('index'),
                description=feed.description,
                language=settings.LANGUAGE_CODE,
                copyright=feed.copyright,
                pubDate=now,
                lastBuildDate=now,
                image=image,
                items=[LinkItem(link) for link in links])


class Feed(object):

    """Base Feed class"""

    title = None
    description = None
    max_links = None
    image = None
    encoding = u'UTF-8'
    copyright = u'Copyright (c) %d %s %s' % (datetime.date.today().year, current_site.domain, current_site.name)

    def generate(self, published_links, max_links=None, log=None, name=None):
        if max_links is None:
            max_links = self.max_links
            if max_links is None:
                max_links = DEFAULT_MAX_LINKS

        links = self.filter(published_links)[:max_links]
        if not links.count():
            log.warn('No links left to publish after filtering')
            return

        last_publish_id = SerializedData.data[name]
        if last_publish_id is None:
            last_publish_id = 0
        log.info('Last publish ID: %d', last_publish_id)

        latest_link = links[0]
        log.info('Latest publish ID: %d', latest_link.publish_id)

        if last_publish_id >= latest_link.publish_id:
            log.warn('No new links posted, not rebuilding')
            return

        log.info('Generating RSS ...')
        link_feed = LinkFeed(links, self)
        xml = link_feed.to_xml()
        log.info('Finished: %s, type=%s', plural(len(xml), 'byte'), type(xml).__name__)

    def filter(self, published_links):
        raise NotImplementedError


def get_feeds(names):
    """Import configured feeds"""
    func_name = 'feed'
    global_context = globals()
    local_context = locals()
    feeds = []
    for name in names:
        mod = __import__(name, global_context, local_context, [func_name])
        feed = getattr(mod, func_name, None)
        if feed is not None:
            feeds.append((name, feed))
    return feeds


@logged('build-rss', append=True)
@locked('build-rss', 0)
def rebuild_rss(logger, max_links=None):
    """Rebuild all RSS feeds"""
    feeds = get_feeds(settings.FEEDS)
    logger.info('Rebuilding %s', plural(len(feeds), 'RSS feed'))

    published_links = Link.objects.filter(state='published').order_by('-published')
    new_links = Link.objects.filter(state='new')
    invalid_links = Link.objects.filter(state='invalid')

    logger.info('%s, %s, %s',
                plural(published_links.count(), 'published link'),
                plural(new_links.count(), 'new link'),
                plural(invalid_links.count(), 'invalid link'))

    for feed_name, feed in feeds:
        log = logger.get_named_logger(feed_name)
        log.info('Rebuilding: %s', first(feed.title, feed.description, feed_name))
        feed.generate(published_links, max_links=max_links, log=log, name=feed_name)
