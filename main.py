"""An App Engine app that provides "private" Atom feeds for your Facebook news
feed, ie posts from your friends.
"""

__author__ = 'Ryan Barrett <facebook-atom@ryanb.org>'

import json
import logging
import os
import urllib
import urllib2

from activitystreams import appengine_config
from activitystreams import atom
from activitystreams import facebook
from activitystreams.oauth_dropins import appengine_config as oauth_config
from activitystreams.oauth_dropins import facebook as oauth_facebook
from activitystreams.oauth_dropins.webutil import handlers
from activitystreams.oauth_dropins.webutil import util
import webapp2

from google.appengine.ext.webapp import template

UPGRADE_MESSAGE = """
<entry>
<id>tag:facebook-atom.appspot.com,2013:1</id>
<title>Please update your Facebook Atom feed</title>
<content type="xhtml">
<div xmlns="http://www.w3.org/1999/xhtml" style="color: red; font-style: italic;">
<p><b>Hi! Thanks for using Facebook Atom feeds. Facebook is changing their API,
which means we need to change too. Please
<a href="https://facebook-atom.appspot.com/">click here to generate a new feed</a>.
Your old feed stops working on April 30, 2015.</b></p>

<p>Feel free to <a href="https://snarfed.org/about">ping me</a> if you have any
questions. Thanks again!</p>
</div>
</content>
<published>2013-07-08T20:00:00</published>
</entry>
"""


class GenerateHandler(webapp2.RequestHandler):
  """Custom OAuth start handler so we can include app id/secret in the callback.
  """
  def post(self):
    app_id = util.get_required_param(self, 'app_id')
    app_secret = util.get_required_param(self, 'app_secret')

    # monkey patch app id so that oauth-dropins uses it instead of the files
    oauth_config.FACEBOOK_APP_ID = app_id
    oauth_config.FACEBOOK_APP_SECRET = app_secret

    url = '/got_auth_code?%s' % urllib.urlencode({'app_id': app_id,
                                                  'app_secret': app_secret})
    # self.request.params['scope'] = 'read_stream'
    # class StartHandler(oauth_facebook.StartHandler):
    #   scope = 'read_stream'
    # the scope param is set to 'read_stream' in the form in index.html
    handler = oauth_facebook.StartHandler.to(url)(self.request, self.response)
    return handler.post()


class CallbackHandler(oauth_facebook.CallbackHandler):
  """The OAuth callback. Generates a new feed URL."""

  def get(self):
    # monkey patch app id so that oauth-dropins uses it instead of the files
    oauth_config.FACEBOOK_APP_ID = util.get_required_param(self, 'app_id')
    oauth_config.FACEBOOK_APP_SECRET = util.get_required_param(self, 'app_secret')
    super(CallbackHandler, self).get()

  def request_url_with_state(self):
    """Used as redirect_uri. Override to add app_id and app_secret."""
    return '%s?%s' % (self.request.path_url, urllib.urlencode({
      'app_id': self.request.get('app_id'),
      'app_secret': self.request.get('app_secret'),
    }))

  def finish(self, auth_entity, state=None):
    if not auth_entity:
      logging.info('User declined Facebook auth prompt')
      self.response.set_status(400)
      self.response.out.write("You need to approve the Facebook prompt. "
                              "<a href='/'>Click here to try again.</a>")
      return

    atom_url = '%s/atom?%s' % (self.request.host_url, urllib.urlencode({
        'app_id': util.get_required_param(self, 'app_id'),
        'app_secret': util.get_required_param(self, 'app_secret'),
        'user_id': auth_entity.key.id(),
        'access_token': auth_entity.access_token(),
      }))
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
      activities = fb.get_activities(count=50)
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
    actor = fb.get_actor()
    title = 'facebook-atom feed for %s' % fb.actor_name(actor)

    # render atom, including upgrade message
    output = atom.activities_to_atom(
        activities, fb.get_actor(), title=title,
        host_url=host_url, request_url=self.request.path_url).rstrip()
    closing_tag = '</feed>'
    assert output.endswith(closing_tag)
    output = output[:-len(closing_tag)] + UPGRADE_MESSAGE + closing_tag

    self.response.headers['Content-Type'] = 'application/atom+xml'
    self.response.out.write(output)


application = webapp2.WSGIApplication(
  [('/generate', GenerateHandler),
   ('/got_auth_code', CallbackHandler),
   ('/atom', AtomHandler),
   ], debug=appengine_config.DEBUG)
