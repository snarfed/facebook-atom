"""Fetch m.facebook.com with a cookie and convert it.
"""

import logging
import re
import urllib
import urllib2

from activitystreams.oauth_dropins.webutil import handlers
from activitystreams.oauth_dropins.webutil import util
from bs4 import BeautifulSoup
import webapp2

ATOM_HEADER = """
<?xml version="1.0" encoding="UTF-8"?>
<feed xml:lang="en-US" xmlns="http://www.w3.org/2005/Atom">
<id>https://facebook-atom.appspot.com/cookie</id>
<title>facebook-atom cookie feed</title>
<logo>https://static.xx.fbcdn.net/rsrc.php/v2/yp/r/eZuLK-TGwK1.png</logo>

<link href="https://m.facebook.com/" rel="alternate" type="text/html" />
<link href="https://facebook-atom.appspot.com/cookie"
      rel="self" type="application/atom+xml" />
"""
  # <id>{{ activity.url }}</id>
  # <title>{{ activity.title|safe }}</title>
ATOM_ENTRY = """
<entry>
  <content type="xhtml">
  <div xmlns="http://www.w3.org/1999/xhtml">
    %s
  </div>
  </content>
</entry>
"""
# <link rel="alternate" type="text/html" href="{{ activity.url }}" />
# <link rel="self" type="application/atom+xml" href="{{ activity.url }}" />


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

    soup = BeautifulSoup(body)
    posts = [p.prettify().encode('utf-8')
             for p in soup.find_all(id=re.compile('u_0_.'))]

    self.response.headers['Content-Type'] = 'application/atom+xml'
    self.response.out.write(''.join(
      [ATOM_HEADER] + [ATOM_ENTRY % p for p in posts] + ['</feed>']))


application = webapp2.WSGIApplication(
  [('/cookie', CookieHandler),
   ], debug=False)
