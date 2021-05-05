"""Fetch mbasic.facebook.com with a cookie and convert it to Atom.
"""
import datetime
import logging
import operator
import re

from granary import atom, facebook
from oauth_dropins.webutil import appengine_config, appengine_info, handlers, util
import webapp2

CACHE_EXPIRATION = datetime.timedelta(minutes=15)

# See https://www.cloudimage.io/
IMAGE_PROXY_URL_BASE = 'https://aujtzahimq.cloudimg.io/v7/'

# don't show stories with titles or headers that contain one of these regexps.
#
# the double spaces are intentional. it's how FB renders these stories. should
# help prevent false positives.
BLOCKLIST = frozenset([
  re.compile(r'  (are now friends|is now friends with|(also )?commented on|added \d+ comments on|[Ll]ike([ds])?|reacted to|replied to|followed|is going to|is interested in|donated to)(  ?| this| an?)'),
  re.compile(r'  ((was|were) (mentioned|tagged)( in( an?| this)?|>)?)'),
  re.compile(r"  (wrote on|shared a  .+  to)  .+ 's (wall|timeline)", re.I),
  re.compile(r' Add Friend$', re.I),
  re.compile(r"A Video You May Like|Popular Across Facebook|Similar to Posts You've Interacted With|Suggested (for You|Post)", re.I),
])


def blocklisted(string):
  logging.info('Examining %r', string)
  for regex in BLOCKLIST:
    if regex.search(string):
      logging.info('Ignoring due to %r', regex.pattern)
      return True


class CookieHandler(handlers.ModernHandler):
  handle_exception = handlers.handle_exception

  @handlers.throttle(CACHE_EXPIRATION)
  def get(self):
    c_user = util.get_required_param(self, 'c_user')
    xs = util.get_required_param(self, 'xs')
    fb = facebook.Facebook(scrape=True, cookie_c_user=c_user, cookie_xs=xs)
    activities = fb.get_activities()
    logging.info(f'Got {len(activities)} activities')

    all = self.request.get('all', '').lower() == 'true'
    if all:
      logging.info('Ignoring blocklist and returning all items due to all=true!')
    else:
      activities = [a for a in activities if not blocklisted(a.get('content', ''))]

    # Pass images through image proxy to cache them
    for a in activities:
      obj = a.get('object')
      for elem in ([obj, obj.get('author'), a.get('actor')] +
                   obj.get('replies', {}).get('items', []) +
                   obj.get('attachments', []) +
                   obj.get('tags', [])):
        if elem:
          for img in util.get_list(elem, 'image'):
            url = img.get('url')
            if url and not url.startswith(IMAGE_PROXY_URL_BASE):
              # Note that url isn't URL-encoded here, that's intentional.
              # cloudimage.io doesn't decode it.
              img['url'] = IMAGE_PROXY_URL_BASE + url

    # Generate output
    self.response.headers['Content-Type'] = 'application/atom+xml'
    self.response.out.write(atom.activities_to_atom(
      activities, {}, title='facebook-atom feed',
      host_url=self.request.host_url + '/',
      request_url=self.request.path_url,
      xml_base=facebook.M_HTML_BASE_URL))


application = webapp2.WSGIApplication([
  ('/cookie', CookieHandler),
], debug=appengine_info.DEBUG)
