facebook-atom
=============

_This service is now closed. So long, and thanks for all the fish!️_

A webapp that generates and serves an Atom feed of your Facebook news feed, ie posts from your friends.

https://facebook-atom.appspot.com/

License: This project is placed in the public domain.


Development
---
1. Fork and clone this repo.
1. `pip install -r requirements.txt`, optionally in a virtualenv.
1. Install the [Google Cloud SDK](https://cloud.google.com/sdk/) with the `gcloud-appengine-python` and `gcloud-appengine-python-extras` [components](https://cloud.google.com/sdk/docs/components#additional_components).
1. `GAE_ENV=localdev FLASK_ENV=development FLASK_APP=main.py flask run -p 8080`
