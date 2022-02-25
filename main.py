"""Fetch mbasic.facebook.com with a cookie and convert it to Atom.
"""
import datetime
import logging
import operator
import re

from flask import Flask, render_template, request
from flask.views import View
from flask_caching import Cache
import flask_gae_static
from granary import atom, facebook, microformats2
from oauth_dropins.webutil import appengine_config, appengine_info, flask_util, util

CACHE_EXPIRATION = datetime.timedelta(minutes=15)

# See https://www.cloudimage.io/
IMAGE_PROXY_URL_BASE = 'https://aujtzahimq.cloudimg.io/v7/'
# https://dash.cloudflare.com/dcc4dadb279e9e9e69e9e84ec82d9303/workers/view/caching-proxy
VIDEO_PROXY_URL_BASE = 'https://caching-proxy.snarfed.workers.dev/'

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

# Flask app
app = Flask('facebook-atom')
app.template_folder = './templates'
app.config.from_mapping(
    ENV='development' if appengine_info.DEBUG else 'production',
    CACHE_TYPE='SimpleCache',
    SECRET_KEY=util.read('flask_secret_key'),
)
app.after_request(flask_util.default_modern_headers)
app.register_error_handler(Exception, flask_util.handle_exception)
flask_gae_static.init_app(app)
app.wsgi_app = flask_util.ndb_context_middleware(
    app.wsgi_app, client=appengine_config.ndb_client)

cache = Cache(app)


def blocklisted(string):
  logging.info('Examining %r', string)
  for regex in BLOCKLIST:
    if regex.search(string):
      logging.info('Ignoring due to %r', regex.pattern)
      return True


@app.route('/cookie')
@flask_util.cached(cache, CACHE_EXPIRATION)
def feed():
  c_user = flask_util.get_required_param('c_user')
  xs = flask_util.get_required_param('xs')
  fb = facebook.Facebook(scrape=True, cookie_c_user=c_user, cookie_xs=xs)
  activities = fb.get_activities(log_html=(c_user == '212038'))  # me, for debugging
  logging.info(f'Got {len(activities)} activities')

  all = request.values.get('all', '').lower() == 'true'
  if all:
    logging.info('Ignoring blocklist and returning all items due to all=true!')
  else:
    activities = [a for a in activities if not blocklisted(a.get('content', ''))]

  # Pass images and videos through caching proxy to cache them
  for a in activities:
    microformats2.prefix_image_urls(a, IMAGE_PROXY_URL_BASE)
    microformats2.prefix_video_urls(a, VIDEO_PROXY_URL_BASE)

  # Generate output
  return atom.activities_to_atom(
    activities, {}, title='facebook-atom feed',
    host_url=request.host_url,
    request_url=request.url,
    xml_base=facebook.M_HTML_BASE_URL,
  ), {'Content-Type': 'application/atom+xml'}
