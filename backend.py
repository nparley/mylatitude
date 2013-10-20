import endpoints
from protorpc import messages
from protorpc import message_types
from protorpc import remote
from google.appengine.api import urlfetch
from functools import wraps
import os
import auth_util
import datetime
import logging
import calendar
import json
logging.getLogger().setLevel(logging.DEBUG)

from latMain import Users, Location, TimeZones

import oauth2client.clientsecrets
clientObj = oauth2client.clientsecrets.loadfile(os.path.join(os.path.dirname(__file__), 'client_secrets.json'))
ALLOWED_CLIENT_IDS = [clientObj[1]['client_id'], endpoints.API_EXPLORER_CLIENT_ID]

def userRequired(userFunc):
  def userRequiredWrap(func):
      @wraps(func)
      def checkUserToken(*args, **kwargs):
        userID = auth_util.get_google_plus_user_id()
        if userFunc(userID):
          return func(*args, **kwargs)
        else:
          raise endpoints.UnauthorizedException('User does not have access to this endpoint')
      return checkUserToken
  return userRequiredWrap

def anyUser(userID):
  if userID:
    userCheck = Users.get_by_id(userID)
    if userCheck:
      return True
  return False
 
def ownerUser(userID):
  if userID:
    userCheck = Users.get_by_id(userID)
    if userCheck:
      if userCheck.owner:
        return True
  return False

MILLIS_PER_12HOURS = 43200000
MILLIS_PER_24HOURS = 86400000

class UserMessage(messages.Message):
  userid = messages.StringField(1)
  owner = messages.BooleanField(2)
  name = messages.StringField(3)
  picture = messages.StringField(4)

class LocationMessage(messages.Message):
  timestampMs = messages.IntegerField(1,variant=messages.Variant.INT64)
  latitude = messages.FloatField(2)
  longitude = messages.FloatField(3)
  accuracy = messages.IntegerField(4,variant=messages.Variant.INT32)
  velocity = messages.IntegerField(5,variant=messages.Variant.INT32)
  heading = messages.IntegerField(6,variant=messages.Variant.INT32)
  altitude = messages.IntegerField(7,variant=messages.Variant.INT32)
  verticalAccuracy = messages.IntegerField(8,variant=messages.Variant.INT32)

class TimeZoneMessage(messages.Message):
  dstOffset = messages.IntegerField(1,variant=messages.Variant.INT32)
  rawOffset = messages.IntegerField(2,variant=messages.Variant.INT32)
  timeZoneId = messages.StringField(3)
  timeZoneName = messages.StringField(4)

class DayMessage(messages.Message):
  year = messages.IntegerField(1,variant=messages.Variant.INT32)
  month = messages.IntegerField(2,variant=messages.Variant.INT32)
  day = messages.IntegerField(3,variant=messages.Variant.INT32)

class SingleLocationMessage(messages.Message):
  location = messages.MessageField(LocationMessage, 1, repeated=False)

class DayLocationsMessage(messages.Message):
  locations = messages.MessageField(LocationMessage, 1, repeated=True)
  timeZone = messages.MessageField(TimeZoneMessage,2,repeated=False)
  day = messages.MessageField(DayMessage,3,repeated=False)
  totalLocations = messages.IntegerField(4,variant=messages.Variant.INT32)

DAY_RESOURCE_CONTAINER = endpoints.ResourceContainer(
  message_types.VoidMessage,
  year=messages.IntegerField(2, variant=messages.Variant.INT32,required=True),
  month=messages.IntegerField(3, variant=messages.Variant.INT32,required=True),
  day=messages.IntegerField(4, variant=messages.Variant.INT32,required=True))

myLatAPI = endpoints.api(name='mylatitude', version='v1', description='Rest API to your location data',
               allowed_client_ids=ALLOWED_CLIENT_IDS)

#noinspection PyUnusedLocal
@myLatAPI.api_class(resource_name='locations',path='locations')
class LocationsEndPoint(remote.Service):
  @staticmethod
  def create_location_message(locationObj):
    return LocationMessage(timestampMs = locationObj.timestampMs,
                         latitude = locationObj.latitudeE7 / 1E7,
                         longitude = locationObj.longitudeE7 / 1E7,
                         accuracy = locationObj.accuracy,
                         velocity = locationObj.velocity,
                         heading = locationObj.heading,
                         altitude = locationObj.altitude,
                         verticalAccuracy = locationObj.verticalAccuracy)

  @staticmethod
  def create_day_message(year,month,day):
    return DayMessage(year=year,month=month,day=day)

  @staticmethod
  def create_timezone_message(tzObjc):
    return TimeZoneMessage(dstOffset = tzObjc.dstOffset, rawOffset = tzObjc.rawOffset,
                           timeZoneId = tzObjc.timeZoneId, timeZoneName = tzObjc.timeZoneName)
  @staticmethod
  def get_TimeZone(day,dayTSMs):
    newTimeZone = TimeZones.get_by_id(str(dayTSMs))
    if newTimeZone:
      return newTimeZone

    qryBeforeMidday = Location.query(Location.timestampMs >= dayTSMs - MILLIS_PER_12HOURS,
                         Location.timestampMs <= dayTSMs).order(-Location.timestampMs) # + order = smallest
    futBeforeMidday = qryBeforeMidday.fetch_async(1)

    qryAfterMidday = Location.query(Location.timestampMs > dayTSMs,
                         Location.timestampMs <= dayTSMs + MILLIS_PER_12HOURS).order(Location.timestampMs)
    futAfterMidday = qryAfterMidday.fetch_async(1)

    try:
      beforeMidday = futBeforeMidday.get_result()[0]
      beforeMiddayMs = dayTSMs - beforeMidday.timestampMs
    except IndexError:
      beforeMiddayMs = MILLIS_PER_24HOURS
      beforeMidday = None

    try:
      afterMidday = futAfterMidday.get_result()[0]
      afterMiddayMs = afterMidday.timestampMs - dayTSMs
    except IndexError:
      afterMiddayMs = MILLIS_PER_24HOURS
      afterMidday = None

    if not any((beforeMidday,afterMidday)):
      raise endpoints.NotFoundException('No locations for %s' % day.date().isoformat())

    if beforeMiddayMs < afterMiddayMs:
      queryParams = (beforeMidday.latitudeE7 / 1E7, beforeMidday.longitudeE7 / 1E7, beforeMidday.timestampMs / 1000)
    else:
      queryParams = (afterMidday.latitudeE7 / 1E7, afterMidday.longitudeE7 / 1E7, afterMidday.timestampMs / 1000)

    timeZoneApiURL = "https://maps.googleapis.com/maps/api/timezone/json?location=%.2f,%.2f&timestamp=%d&sensor=false" \
                     % queryParams

    timeZoneResult = urlfetch.fetch(url=timeZoneApiURL,method=urlfetch.GET,validate_certificate=True)
    if timeZoneResult.status_code == 200:
      newTimeZone = TimeZones(id=str(dayTSMs))
      newTimeZone.day = day.date()
      tz_json = json.loads(timeZoneResult.content)
      newTimeZone.dstOffset = tz_json["dstOffset"]
      newTimeZone.rawOffset = tz_json["rawOffset"]
      newTimeZone.timeZoneId = tz_json["timeZoneId"]
      newTimeZone.timeZoneName = tz_json["timeZoneName"]
      newTimeZone.put()
      return newTimeZone
    else:
      newTimeZone = TimeZones(id=str(dayTSMs))
      newTimeZone.day = day.date()
      newTimeZone.dstOffset = 0
      newTimeZone.rawOffset = 0
      newTimeZone.timeZoneId = "UTC"
      newTimeZone.timeZoneName = "Coordinated Universal Time"
      return newTimeZone

  @endpoints.method(message_types.VoidMessage,SingleLocationMessage,name='latest',path='latest',http_method='GET')
  @userRequired(anyUser)
  def get_latest_location(self,request):
    lastLocation = Location.query().order(-Location.timestampMs).fetch(1)
    location = self.create_location_message(lastLocation[0])
    if not lastLocation:
      raise endpoints.NotFoundException('No locations in database')
    return SingleLocationMessage(location=location)

  @endpoints.method(DAY_RESOURCE_CONTAINER,DayLocationsMessage,name='history',path='history/{year}/{month}/{day}',
                    http_method='GET')
  @userRequired(ownerUser)
  def get_days_locations(self,request):
    try:
      historyDay = datetime.datetime(request.year,request.month,request.day,hour=12,minute=0,second=0,microsecond=0,
                                     tzinfo=None) # Mid day UTC on the requested day
      historyDayTsMs = calendar.timegm(historyDay.utctimetuple()) * 1000 # Timestamp MS mid day on the requested day
    except ValueError:
      raise endpoints.BadRequestException('Not a correct date')

    timeZone = self.get_TimeZone(historyDay,historyDayTsMs)
    historyDayTsMs += (timeZone.dstOffset * 1000)
    historyDayTsMs += (timeZone.rawOffset * 1000)

    qry = Location.query(Location.timestampMs >= historyDayTsMs - MILLIS_PER_12HOURS,
                         Location.timestampMs <= historyDayTsMs + MILLIS_PER_12HOURS).order(-Location.timestampMs)
    daysLocationsFut = qry.fetch_async()

    dayMessage = self.create_day_message(request.year,request.month,request.day)
    tzMessage = self.create_timezone_message(timeZone)

    location_entries = daysLocationsFut.get_result()
    if not location_entries:
      raise endpoints.NotFoundException('No locations for %s' % historyDay.date().isoformat())

    locationsMessage = [self.create_location_message(loc) for loc in location_entries]
    totalLocations = len(locationsMessage)
    return DayLocationsMessage(locations=locationsMessage,day=dayMessage,
                               timeZone=tzMessage,totalLocations=totalLocations)

application = endpoints.api_server([myLatAPI],restricted=False)

