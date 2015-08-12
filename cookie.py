"""Fetch m.facebook.com with a cookie and convert it.
"""

import datetime
import logging
import re
import urllib
import urllib2
import urlparse

from activitystreams.oauth_dropins.webutil import handlers
from activitystreams.oauth_dropins.webutil import util
from bs4 import BeautifulSoup
import webapp2

HEADER = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xml:lang="en-US" xmlns="http://www.w3.org/2005/Atom">
<id>https://facebook-atom.appspot.com/cookie</id>
<title>facebook-atom cookie feed</title>
<logo>https://static.xx.fbcdn.net/rsrc.php/v2/yp/r/eZuLK-TGwK1.png</logo>
<updated>%(updated)s</updated>

<link href="https://m.facebook.com/" rel="alternate" type="text/html" />
<link href="https://facebook-atom.appspot.com/cookie"
      rel="self" type="application/atom+xml" />
"""
FOOTER = """
</feed>
"""
ENTRY = u"""
<entry>
  <id>%(id)s</id>
  <title>%(title)s</title>
  <content type="xhtml">
  <div xmlns="http://www.w3.org/1999/xhtml">
    %(content)s
  </div>
  </content>
</entry>
"""
OMIT_URL_PARAMS = {'bacr', '_ft_', 'refid'}


class CookieHandler(webapp2.RequestHandler):
  handle_exception = handlers.handle_exception

  def get(self):
    cookie = urllib.unquote_plus(util.get_required_param(self, 'cookie'))
    logging.info('Cookie: %s', cookie)

    resp = urllib2.urlopen(urllib2.Request(
      'https://m.facebook.com/',
      headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.10; rv:39.0) Gecko/20100101 Firefox/39.0',
        'DNT': '1',
        'Cookie': cookie,
      }))
    body = resp.read()
    logging.info('Response: %s', resp.getcode())
    assert resp.getcode() == 200

    parts = [HEADER % {'updated': datetime.datetime.now().isoformat('T')}]
    for post in BeautifulSoup(body).find_all(id=re.compile('u_0_.')):
      link = post.find(text='Full Story')
      if link:
        parsed = urlparse.urlparse(link.parent['href'])
        params = [(name, val) for name, val in urlparse.parse_qsl(parsed.query)
                  if name not in OMIT_URL_PARAMS]
        url = urlparse.urlunparse(('https', 'm.facebook.com', parsed.path,
                                   '', urllib.urlencode(params), ''))
        content = post.prettify().replace('href="/', 'href="https://m.facebook.com/')
        entry = ENTRY % {
          'id': url,
          'title': unicode(post.div.get_text(' '))[:100],
          'content': content,
        }
        parts.append(entry.encode('utf-8'))

    parts += [FOOTER]

    self.response.headers['Content-Type'] = 'application/atom+xml'
    self.response.out.write(''.join(parts))


application = webapp2.WSGIApplication(
  [('/cookie', CookieHandler),
   ], debug=False)
