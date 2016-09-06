"""Fetch m.facebook.com with a cookie and convert it to Atom.
"""

import datetime
import logging
import re
import urllib
import urllib2
import urlparse
import xml.sax.saxutils

import appengine_config
from bs4 import BeautifulSoup
from oauth_dropins.webutil import handlers
import webapp2

HEADER = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xml:lang="en-US"
      xmlns="http://www.w3.org/2005/Atom"
      xml:base="https://m.facebook.com/">
<id>https://facebook-atom.appspot.com/</id>
<title>facebook-atom feed</title>
<logo>https://static.xx.fbcdn.net/rsrc.php/v2/yp/r/eZuLK-TGwK1.png</logo>
<updated>%(updated)s</updated>

<link href="https://m.facebook.com/?sk=h_chr" rel="alternate" type="text/html" />
<link href="https://facebook-atom.appspot.com/"
      rel="self" type="application/atom+xml" />
"""
FOOTER = """
</feed>
"""
ENTRY = u"""
<entry>
  <id>%(url)s</id>
  <link rel="alternate" type="text/html" href="%(url)s" />
  <title>%(title)s</title>
  <content type="xhtml">
  <div xmlns="http://www.w3.org/1999/xhtml">
    %(content)s
  </div>
  </content>
</entry>
"""
OMIT_URL_PARAMS = {'bacr', 'ext', '_ft_', 'hash', 'refid'}

# don't show stories with titles or headers that contain one of these regexps.
#
# the double spaces are intentional. it's how FB renders these stories. should
# help prevent false positives.
BLACKLIST = frozenset([
  re.compile(r'  (are now friends|is now friends with|(also )?commented on|like[ds]|replied to|followed)(  | this| a)'),
  re.compile(r'  ((was|were) (mentioned|tagged) in( a)?|>)  '),
  re.compile(r"  (wrote on|shared a  .+  to)  .+ 's (wall|timeline)", re.I),
  re.compile(r' Add Friend$', re.I),
  re.compile(r'Suggested Post', re.I),
])


def blacklisted(string):
  logging.info('Examining %r', string)
  for regex in BLACKLIST:
    if regex.search(string):
      logging.info('Ignoring due to %r', regex.pattern)
      return True


def clean_url(url):
  parsed = urlparse.urlparse(url)
  if parsed.netloc not in ('', 'm.facebook.com'):
    return url

  params = [(name, val.encode('utf-8'))
            for name, val in urlparse.parse_qsl(parsed.query)
            if name not in OMIT_URL_PARAMS]
  return urlparse.urlunparse(('https', 'm.facebook.com', parsed.path,
                              '', urllib.urlencode(params), ''))


class CookieHandler(handlers.ModernHandler):
  handle_exception = handlers.handle_exception

  def get(self):
    try:
      cookie = 'c_user=%(c_user)s; xs=%(xs)s' % self.request.params
    except KeyError:
      return self.abort(400, 'Query parameters c_user and xs are required')

    logging.info('Fetching with Cookie: %s', cookie)
    resp = urllib2.urlopen(urllib2.Request(
      # ?sk=hcr uses the Most Recent news feed option (instead of Top Stories)
      'https://m.facebook.com/?sk=h_chr',
      headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.10; rv:39.0) Gecko/20100101 Firefox/39.0',
        'Cookie': cookie,
      }))
    body = resp.read()
    logging.info('Response: %s', resp.getcode())
    assert resp.getcode() == 200

    soup = BeautifulSoup(body, 'html.parser')
    # logging.debug(soup.prettify().encode('utf-8'))
    if not soup.find('a', href=re.compile('^/logout.php')):
      return self.abort(401, "Couldn't log into Facebook with cookie %s" % cookie)

    home_link = soup.find('a', href=re.compile(
      r'/[^?]+\?ref_component=mbasic_home_bookmark.*'))
    if home_link:
      href = home_link['href']
      logging.info('Logged in for user %s', href[1:href.find('?')])
    else:
      logging.warning("Couldn't determine username or id!")

    posts = soup.find_all('div', id=re.compile('u_0_.'))
    logging.info('Found %d posts', len(posts))

    atom_parts = [HEADER % {'updated': datetime.datetime.now().isoformat('T') + 'Z'}]
    for post in posts:
      # look for Full Story link; it's the first a element before Save or More.
      # (can't use text labels because we don't know language.)
      save_or_more = post.find(href=re.compile(
        '/(save/story|nfx/basic/direct_actions)/.+'))
      if not save_or_more:
        logging.info('Skipping one due to missing Save and More links')
        continue

      link = save_or_more.find_previous_sibling('a')
      if not link:
        logging.info('Skipping one due to missing Full Story link')
        continue

      story = unicode(post.div.get_text(' '))
      if blacklisted(story):
        continue

      header_div = post.find_previous_sibling('div')
      if header_div:
        header = header_div.find('h3')
        if header and blacklisted(header.get_text(' ')):
          continue

      # strip footer with like count, comment count, etc., and also footer
      # section with relative publish time (e.g. '1 hr'). they change over time,
      # which we think triggers readers to show stories again even when you've
      # already read them. https://github.com/snarfed/facebook-atom/issues/11
      if save_or_more.parent.previous_sibling:
        save_or_more.parent.previous_sibling.extract()
      save_or_more.parent.extract()

      for a in post.find_all('a'):
        if a.get('href'):
          a['href'] = clean_url(a['href'])

      entry = ENTRY % {
        'url': xml.sax.saxutils.escape(clean_url(link['href'])),
        'title': story[:100],
        'content': post.prettify(),
      }
      atom_parts.append(entry.encode('utf-8'))

    atom_parts += [FOOTER]

    self.response.headers['Content-Type'] = 'application/atom+xml'
    self.response.out.write(''.join(atom_parts))


application = webapp2.WSGIApplication(
  [('/cookie', CookieHandler),
   ], debug=False)
