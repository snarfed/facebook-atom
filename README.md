facebook-atom
=============

A webapp that generates and serves an Atom feed of your Facebook news feed, ie posts from your friends.

https://facebook-atom.appspot.com/

License: This project is placed in the public domain.


Development
---
You'll need the [Google Cloud SDK](https://cloud.google.com/sdk/gcloud/) (aka `gcloud`) with the `gcloud-appengine-python`, `gcloud-appengine-python-extras` and `google-cloud-sdk-datastore-emulator` [components](https://cloud.google.com/sdk/docs/components#additional_components). Then, create a Python 3 virtualenv and install the dependencies with:

```sh
python3 -m venv local
source local/bin/activate
pip install -r requirements.txt
```

Then, to run the app locally:

```sh
dev_appserver.py --log_level debug --enable_host_checking false \
  --support_datastore_emulator --datastore_emulator_port=8089 \
  --application=facebook-atom ./app.yaml
```

Open [localhost:8080](http://localhost:8080/) in your browser, and you should see it!
