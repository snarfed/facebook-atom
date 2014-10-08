"""An App Engine app that provides "private" Atom feeds for your Facebook news
feed, ie posts from your friends.
"""

__author__ = 'Ryan Barrett <facebook-atom@ryanb.org>'

import json
import logging
import os
import urllib2

from activitystreams import appengine_config
from activitystreams import atom
from activitystreams import facebook
from activitystreams.oauth_dropins import facebook as oauth_facebook
from activitystreams.oauth_dropins.webutil import handlers
from activitystreams.oauth_dropins.webutil import util
import webapp2

from google.appengine.ext.webapp import template


class CallbackHandler(oauth_facebook.CallbackHandler):
  def finish(self, auth_entity, state=None):
    """Gets an access token based on an auth code."""
    atom_url = '%s/atom?user_id=%s&access_token=%s' % (
      self.request.host_url, auth_entity.key.id(), auth_entity.access_token())
    logging.info('generated feed URL: %s', atom_url)
    self.response.out.write(template.render(
        os.path.join(os.path.dirname(__file__), 'templates', 'generated.html'),
        {'atom_url': atom_url}))


def actor_name(actor):
  return actor.get('displayName') or actor.get('username') or 'you'


class AtomHandler(webapp2.RequestHandler):
  """Proxies the Atom feed for a Facebook user's stream.

  Authenticates to the Facebook API with the user's stored OAuth credentials.
  """
  handle_exception = handlers.handle_exception

  def get(self):
    host_url = self.request.host_url + "/"
    fb = facebook.Facebook(access_token=util.get_required_param(self, 'access_token'))

    try:
      activities = fb.get_activities()
    except urllib2.HTTPError, e:
      # Facebook API error details:
      # https://developers.facebook.com/docs/graph-api/using-graph-api/#receiving-errorcodes
      # https://developers.facebook.com/docs/reference/api/errors/
      body = e.read()
      try:
        error = json.loads(body).get('error', {})
      except:
        # response isn't JSON
        error = {}

      user_id = self.request.get('user_id')
      if (user_id and
          # bad access token, oauth error
          error.get('code') in (102, 190) and
          # revoked, expired, changed password
          error.get('error_subcode') in (458, 463, 460)):
        fb.create_notification(
          user_id,
          "Your Facebook Atom feed's access has expired. Click here to renew it!",
          host_url)
        self.response.set_status(403)
        self.response.write(
          'Your Facebook access has expired. Go to %s to renew it!' % host_url)
      else:
        self.response.set_status(e.code)
        self.response.write(body)
      return

    # massage data
    for a in activities:
      obj = a.setdefault('object', {})
      who = a.get('actor', {})
      if 'content' not in obj and obj['objectType'] == 'image':
        obj['content'] = '%s added a new photo.' % actor_name(who)

    self.response.headers['Content-Type'] = 'application/atom+xml'
    self.response.out.write(atom.activities_to_atom(
        activities, fb.get_actor(), host_url=host_url,
        request_url=self.request.path_url))


application = webapp2.WSGIApplication(
  [('/generate', oauth_facebook.StartHandler.to('/got_auth_code',
        # https://developers.facebook.com/docs/reference/login/
        facebook.OAUTH_SCOPES + ',offline_access')),
   ('/got_auth_code', CallbackHandler),
   ('/atom', AtomHandler),
   ], debug=appengine_config.DEBUG)
