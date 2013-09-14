from google.appengine.ext import endpoints
from google.appengine.ext import ndb
from protorpc import remote

import os
import sys

ENDPOINTS_PROJECT_DIR = os.path.join(os.path.dirname(__file__),
                                     'endpoints-proto-datastore')
sys.path.append(ENDPOINTS_PROJECT_DIR)

from endpoints_proto_datastore.ndb import EndpointsModel

class Location(EndpointsModel):
    timestampMs = ndb.IntegerProperty()
    latitudeE7 = ndb.IntegerProperty()
    longitudeE7 = ndb.IntegerProperty()
    accuracy = ndb.IntegerProperty()
    velocity = ndb.IntegerProperty()
    heading = ndb.IntegerProperty()
    altitude = ndb.IntegerProperty()
    verticalAccuracy = ndb.IntegerProperty()

@endpoints.api(name='mylatapi', version='v1', description='Rest API to the location data')
class myLatAPI(remote.Service):
  @Location.query_method(user_required=True,
                        path='lastLocation', name='location.last',limit_default=1,limit_max=1)
  def lastLocation(self, query):
    #need to check user
    return query.order(-Location.timestampMs)
  
application = endpoints.api_server([myLatAPI], restricted=False)

