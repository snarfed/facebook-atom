facebook-atom
=============

A webapp that generates and serves an Atom feed of your Facebook news feed, ie
posts from your friends.

Deployed on App Engine at https://facebook-atom.appspot.com/

License: This project is placed in the public domain.


Development
---
You'll need the
[App Engine Python SDK](https://cloud.google.com/appengine/downloads#Google_App_Engine_SDK_for_Python)
version 1.9.15 or later (for
[`vendor`](https://cloud.google.com/appengine/docs/python/tools/libraries27#vendoring)
support). Add it to your `$PYTHONPATH`, e.g.
`export PYTHONPATH=$PYTHONPATH:/usr/local/google_appengine`, and then run:

```
virtualenv local
source local/bin/activate
pip install -r requirements.txt
```

Now run `/usr/local/google_appengine/dev_appserver.py .` and open
[localhost:8080](http://localhost:8080/) in your browser!
