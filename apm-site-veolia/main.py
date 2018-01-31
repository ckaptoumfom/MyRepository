# -*- coding: utf-8 -*-
from __future__ import with_statement

import cloudstorage as gcs
import webapp2

import httplib2
from apiclient.discovery import build
from oauth2client.appengine import AppAssertionCredentials
import traceback
import logging
import re

from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.api import users
from google.appengine.ext import ndb


class Bucket(ndb.Model):
    """
    Describe a bucket
    """
    name = ndb.StringProperty()


class Authorization(ndb.Model):
    """
    Describe an authorization
    """
    domains = ndb.StringProperty(repeated=True)

BUCKET = '/apm-site-veolia.appspot.com'
API_KEY = 'AIzaSyD5gSI-WS19bKExI-7h7idXFpDs-CJbk5w'
SPREADHSEET_ID = '1RLU5_u6PsP1TN3CbqNeASUEwHzSGZ_tGN05ufXuOgWI'
TRACKING_CODE = """
<script>
  (function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
  (i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
  m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
  })(window,document,'script','//www.google-analytics.com/analytics.js','ga');

  ga('create', 'UA-53289468-1', 'auto');
  ga('send', 'pageview');

</script>
"""


def getBucket():
    """
    Get the main bucket object
    """
    bucket = ndb.Key(Bucket, 'production').get()

    if not bucket:
        bucket = Bucket(id='production')
        bucket.put()

    return bucket


def getAuthorization():
    """
    Get the main authorization object
    """
    authorization = ndb.Key(Authorization, 'production').get()

    if not authorization:
        authorization = Authorization(id='production')
        authorization.put()

    return authorization


def createDriveService():
    """
    Builds and returns a Drive service object authorized with the
    application's service account.

    Returns:
    Drive service object.
    """
    credentials = AppAssertionCredentials(scope='https://www.googleapis.com/auth/drive')
    http = httplib2.Http()
    http = credentials.authorize(http)

    return build('drive', 'v2', http=http, developerKey=API_KEY)


class ServingHandler(blobstore_handlers.BlobstoreDownloadHandler):

    def get(self):
        email = users.get_current_user().email()

        if email.split('@')[1] in (getAuthorization().domains + ['lumapps.com']):
            path = self.request.url.split('appspot.com/')[1]
            path = path if path else 'index.htm'
            name = '/gs%s/%s/%s' % (BUCKET, getBucket().name, path)
            blob_key = blobstore.create_gs_key(name)

            if not '.htm' in name and not '.html' in name:
                self.send_blob(blob_key)
            else:
                name = '%s/%s/%s' % (BUCKET, getBucket().name, path)
                logging.info('Content for %s' % name)
                content = gcs.open(name, 'r').read()
                match = re.findall('</head>', content, re.IGNORECASE)
                if len(match) > 0:
                    content = content.replace(match[0], '%s</head>' % TRACKING_CODE)
                logging.info(content)
                self.response.write(content)


class UpdateHandler(webapp2.RequestHandler):

    def get(self):
        bucketName = self.request.get('bucket')

        if not bucketName:
            self.response.write('Cliquez sur un dossier pour le passer en production (actuellement : <b>%s</b>) : <br><br>' % getBucket().name)
            for result in gcs.listbucket(BUCKET, delimiter='/'):
                if result.is_dir:
                    filename = result.filename.replace(BUCKET, '').replace('/', '')
                    self.response.write('<a href="/update?bucket=%s">%s</a><br>' % (filename, filename))
        else:
            bucket = getBucket()
            bucket.name = bucketName
            bucket.put()

            self.response.write('Le dossier <b>%s</b> est en production.<br><br><a href="/">Cliquez ici pour y le consulter.</a>' % bucketName)


class ConfigHandler(webapp2.RequestHandler):

    def get(self):
        try:
            service = createDriveService()
            entry = service.files().get(fileId=SPREADHSEET_ID).execute()

            downloadUrl = entry.get('exportLinks')['application/pdf']
            downloadUrl = downloadUrl[:-4] + "=csv&gid=0"

            resp, content = service._http.request(downloadUrl)

            logging.info(content)

            domains = [line.split(',')[0] for line in content.split('\n')[2:] if line.split(',')[0]]
            logging.info(domains)

            if domains:
                authorization = getAuthorization()
                authorization.domains = domains
                authorization.put()
        except:
            logging.error(traceback.print_exc())
        

application = webapp2.WSGIApplication([('/update', UpdateHandler), ('/refreshDomains', ConfigHandler), ('/.*', ServingHandler)],
                                      debug=True)
