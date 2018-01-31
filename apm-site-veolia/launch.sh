#!/bin/sh
if test -n "$1"
then
    more="-$1"
else
    more=""
fi
python $APPENGINE/dev_appserver.py --datastore_path="datastore$more" --blobstore_path="blobstore$more" --search_indexes_path=".search_index$more" --port 8888 .