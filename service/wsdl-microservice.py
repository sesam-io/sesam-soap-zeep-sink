#! /usr/bin/env python

import requests
from flask import Flask, request, Response
from requests.auth import HTTPBasicAuth  # or HTTPDigestAuth, or OAuth1, etc.
from zeep import Client
from zeep.transports import Transport
import logger
import typetransformer
import os
import jwt
import hashlib
import datetime
from lxml import etree
from zeep import Plugin

rootlogger=logger.Logger()

app = Flask(__name__)

requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += os.environ.get('cipher', ':ECDHE-RSA-AES128-SHA')
timeout=int(os.environ.get('timeout', '30'))
url=os.environ.get('url')

class JWTPlugin(Plugin):

    def ingress(self, envelope, http_headers, operation):
        return envelope, http_headers

    def egress(self, envelope, http_headers, operation, binding_options):
        sha256 = hashlib.sha256(etree.tostring(envelope, pretty_print=True))
        expDate = int(datetime.datetime.timestamp(datetime.datetime.now() + datetime.timedelta(seconds=int(os.environ.get('jwt_expiry')))))
        issuer = os.environ.get('jwt_issuer')

        auth =jwt.encode({'sha256': sha256.hexdigest(), 'iss': issuer, 'exp': expDate }, os.environ.get('jwt_secret'), algorithm='HS256').decode("utf-8")
        http_headers['Authorization'] = 'Bearer ' +  auth

        return envelope, http_headers

auth = os.environ.get('authentication', "")
if auth.lower() == "basic":
    rootlogger.info("Using authentication")
    transport = Transport(http_auth=HTTPBasicAuth(os.environ.get('username'), os.environ.get('password')), timeout=timeout)
else:
    rootlogger.info("Skipping authentication")
    transport = Transport(timeout=timeout)

if os.environ.get('jwt_secret') is not None:
    rootlogger.info("Using JWT")
    client = Client(url, transport=transport, plugins=[JWTPlugin()])
else:
    client = Client(url, transport=transport)
##Receiving soap-object
@app.route('/', methods=['POST'])
def push():

    entity = request.get_json()

    if isinstance(entity, list):
        return Response("Multiple entities is not supported",status=400, mimetype='text/plain')

    if os.environ.get('transit_decode', 'false').lower() == "true":
        rootlogger.info("transit_decode is set to True.")
        entity = typetransformer.transit_decode(entity)

    rootlogger.info("Finished creating request: " + str(entity))

    response=do_soap(entity,client)
    rootlogger.info("SOAPResponse : \n" + str(response) + "\n----End-Response----")
    return Response("Thanks", mimetype='text/plain')

def do_soap(entity, client):

    headers = entity['_soapheaders']
    filtered_entity = {i:entity[i] for i in entity if not i.startswith('_') }
    filtered_entity['_soapheaders']=headers

    response = getattr(client.service, os.environ.get('method'))(**filtered_entity)
    return response

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=os.environ.get('port',5001))
