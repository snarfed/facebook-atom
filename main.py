"""An App Engine app that provides "private" Atom feeds for your Facebook news
feed, ie posts from your friends.
"""

__author__ = 'Ryan Barrett <facebook-atom@ryanb.org>'

import json
import logging
import os
import urllib2

from activitystreams import appengine_config
from activitystreams import facebook
from activitystreams.oauth_dropins import facebook as oauth_facebook
from activitystreams.oauth_dropins.webutil import handlers
import webapp2

from google.appengine.ext.webapp import template

# https://developers.facebook.com/docs/reference/login/
OAUTH_SCOPES = facebook.OAUTH_SCOPES + ',offline_access'
GENERATED_TEMPLATE_FILE = os.path.join(os.path.dirname(__file__),
                                       'templates', 'generated.html')
ATOM_TEMPLATE_FILE = os.path.join(os.path.dirname(__file__),
                                  'activitystreams', 'templates', 'user_feed.atom')

API_HOME_URL = ('https://graph.facebook.com/me?access_token=%s&fields='
                'home.limit(50),id,username,name,link,updated_time,bio,location')


class CallbackHandler(oauth_facebook.CallbackHandler):
  def finish(self, auth_entity, state=None):
    """Gets an access token based on an auth code."""
    atom_url = '%s/atom?access_token=%s' % (self.request.host_url,
                                            auth_entity.access_token())
    logging.info('generated feed URL: %s', atom_url)
    self.response.out.write(template.render(GENERATED_TEMPLATE_FILE,
                                            {'atom_url': atom_url}))


def actor_name(actor):
  return actor.get('displayName') or actor.get('username') or 'you'


class AtomHandler(webapp2.RequestHandler):
  """Proxies the Atom feed for a Facebook user's stream.

  Authenticates to the Facebook API with the user's stored OAuth credentials.
  """
  handle_exception = handlers.handle_exception

  def get(self):
    access_token = self.request.get('access_token')
    assert access_token
    resp = json.loads(urllib2.urlopen(API_HOME_URL % access_token, timeout=999).read())

    fb = facebook.Facebook(self)
    actor = fb.user_to_actor(resp)
    posts = resp.get('home', {}).get('data', [])
    activities = [fb.post_to_activity(p) for p in posts]

    # massage data
    for a in activities:
      obj = a.setdefault('object', {})
      who = a.get('actor', {})
      if 'content' not in obj and obj['objectType'] == 'image':
        obj['content'] = '%s added a new photo.' % actor_name(who)

    self.response.headers['Content-Type'] = 'text/xml'
    self.response.out.write(template.render(
        ATOM_TEMPLATE_FILE,
        {'title': 'Facebook news feed for %s' % actor_name(actor),
         'updated': activities[0]['object'].get('updated') if activities else '',
         'actor': actor,
         'items': activities,
         'host_url': self.request.host_url + "/",
         'request_url': self.request.url,
         }))


application = webapp2.WSGIApplication(
  [('/generate', oauth_facebook.StartHandler.to('/got_auth_code', OAUTH_SCOPES)),
   ('/got_auth_code', CallbackHandler),
   ('/atom', AtomHandler),
   ], debug=appengine_config.DEBUG)
