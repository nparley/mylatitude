from google.appengine.ext import endpoints
from google.appengine.ext import ndb
from protorpc import remote

import os
import sys
import auth_util

ENDPOINTS_PROJECT_DIR = os.path.join(os.path.dirname(__file__),
                                     'endpoints-proto-datastore')
sys.path.append(ENDPOINTS_PROJECT_DIR)

from endpoints_proto_datastore.ndb import EndpointsModel

def checkUser(userID):
  if userID:
    userCheck = Users.get_by_id(userID)
    if userCheck:
      return True
    else:
      return False
  else:
    return False
 
def checkOwnerUser(userID):
  if userID:
    userCheck = Users.get_by_id(userID)
    if userCheck:
      if userCheck.owner == True:
        return True
      else:
        return False
    else:
      return False
  else:
    return False 

class Users(ndb.Model):
    userid = ndb.StringProperty()
    owner = ndb.BooleanProperty()
    name = ndb.StringProperty()
    picture = ndb.StringProperty()

class Location(EndpointsModel):
    timestampMs = ndb.IntegerProperty()
    latitudeE7 = ndb.IntegerProperty()
    longitudeE7 = ndb.IntegerProperty()
    accuracy = ndb.IntegerProperty()
    velocity = ndb.IntegerProperty()
    heading = ndb.IntegerProperty()
    altitude = ndb.IntegerProperty()
    verticalAccuracy = ndb.IntegerProperty()

@endpoints.api(name='mylatitude', version='v1', description='Rest API to the location data')
class myLatAPI(remote.Service):
  @Location.query_method(user_required=True,
                        path='lastLocation', name='location.last',limit_default=1,limit_max=1)
  def lastLocation(self, query):
    userID = auth_util.get_google_plus_user_id()
    if checkUser(userID):
      return query.order(-Location.timestampMs)
    else:
      message = 'User does not have access to this endpoint'
      raise endpoints.UnauthorizedException(message)
  
application = endpoints.api_server([myLatAPI], restricted=False)

