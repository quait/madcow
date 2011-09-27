"""Should be called last, if nothing can do a better job with the URL"""

from gruntle.memebot.scanner import Scanner, ScanResult

class DefaultScanner(Scanner):

    rss_template = 'memebot/scanner/rss/default.html'

    def handle(self, response, log):
        return ScanResult(response=response,
                          override_url=None,
                          title=None,
                          content_type=None,
                          content=None,
                          attr=None)


scanner = DefaultScanner()
