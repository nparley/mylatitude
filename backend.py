import os
import datetime
import logging
import calendar
import json
from functools import wraps

logging.getLogger().setLevel(logging.DEBUG)

import endpoints
from protorpc import messages
from protorpc import message_types
from protorpc import remote
from google.appengine.api import urlfetch

import auth_util
from latMain import Users, Location, TimeZones
import oauth2client.clientsecrets

clientObj = oauth2client.clientsecrets.loadfile(os.path.join(os.path.dirname(__file__), 'client_secrets.json'))
ALLOWED_CLIENT_IDS = [clientObj[1]['client_id'], endpoints.API_EXPLORER_CLIENT_ID]


def user_required(user_test_function):
    def user_required_wrap(func):
        @wraps(func)
        def check_user_token(*args, **kwargs):
            user_id = auth_util.get_google_plus_user_id()
            if user_test_function(user_id):
                return func(*args, **kwargs)
            else:
                raise endpoints.UnauthorizedException('User does not have access to this endpoint')

        return check_user_token

    return user_required_wrap


def any_user(user_id):
    if user_id:
        user_check = Users.get_by_id(user_id)
        if user_check:
            return True
    return False


def owner_user(user_id):
    if user_id:
        user_check = Users.get_by_id(user_id)
        if user_check:
            if user_check.owner:
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
    timestampMs = messages.IntegerField(1, variant=messages.Variant.INT64)
    latitude = messages.FloatField(2)
    longitude = messages.FloatField(3)
    accuracy = messages.IntegerField(4, variant=messages.Variant.INT32)
    velocity = messages.IntegerField(5, variant=messages.Variant.INT32)
    heading = messages.IntegerField(6, variant=messages.Variant.INT32)
    altitude = messages.IntegerField(7, variant=messages.Variant.INT32)
    verticalAccuracy = messages.IntegerField(8, variant=messages.Variant.INT32)


class TimeZoneMessage(messages.Message):
    dstOffset = messages.IntegerField(1, variant=messages.Variant.INT32)
    rawOffset = messages.IntegerField(2, variant=messages.Variant.INT32)
    timeZoneId = messages.StringField(3)
    timeZoneName = messages.StringField(4)


class DayMessage(messages.Message):
    year = messages.IntegerField(1, variant=messages.Variant.INT32)
    month = messages.IntegerField(2, variant=messages.Variant.INT32)
    day = messages.IntegerField(3, variant=messages.Variant.INT32)


class SingleLocationMessage(messages.Message):
    location = messages.MessageField(LocationMessage, 1, repeated=False)


class DayLocationsMessage(messages.Message):
    locations = messages.MessageField(LocationMessage, 1, repeated=True)
    timeZone = messages.MessageField(TimeZoneMessage, 2, repeated=False)
    day = messages.MessageField(DayMessage, 3, repeated=False)
    totalLocations = messages.IntegerField(4, variant=messages.Variant.INT32)


DAY_RESOURCE_CONTAINER = endpoints.ResourceContainer(
    message_types.VoidMessage,
    year=messages.IntegerField(2, variant=messages.Variant.INT32, required=True),
    month=messages.IntegerField(3, variant=messages.Variant.INT32, required=True),
    day=messages.IntegerField(4, variant=messages.Variant.INT32, required=True))

myLatAPI = endpoints.api(name='mylatitude', version='v1', description='Rest API to your location data',
                         allowed_client_ids=ALLOWED_CLIENT_IDS)


@myLatAPI.api_class(resource_name='locations', path='locations')
class LocationsEndPoint(remote.Service):
    @staticmethod
    def create_location_message(location_obj):
        return LocationMessage(timestampMs=location_obj.timestampMs,
                               latitude=location_obj.latitudeE7 / 1E7,
                               longitude=location_obj.longitudeE7 / 1E7,
                               accuracy=location_obj.accuracy,
                               velocity=location_obj.velocity,
                               heading=location_obj.heading,
                               altitude=location_obj.altitude,
                               verticalAccuracy=location_obj.verticalAccuracy)

    @staticmethod
    def create_day_message(year, month, day):
        return DayMessage(year=year, month=month, day=day)

    @staticmethod
    def create_timezone_message(tz_obj):
        return TimeZoneMessage(dstOffset=tz_obj.dstOffset, rawOffset=tz_obj.rawOffset,
                               timeZoneId=tz_obj.timeZoneId, timeZoneName=tz_obj.timeZoneName)

    #noinspection PyPep8Naming
    @staticmethod
    def get_time_zone(day, day_ts_ms):
        new_timezone_obj = TimeZones.get_by_id(str(day_ts_ms))
        if new_timezone_obj:
            return new_timezone_obj
        # + order = smallest first, - order = largest first
        before_midday_qry = Location.query(Location.timestampMs >= day_ts_ms - MILLIS_PER_12HOURS,
                                           Location.timestampMs <= day_ts_ms).order(-Location.timestampMs)
        before_midday_fut = before_midday_qry.fetch_async(1)

        after_midday_qry = Location.query(Location.timestampMs > day_ts_ms,
                                          Location.timestampMs <= day_ts_ms +
                                          MILLIS_PER_12HOURS).order(Location.timestampMs)
        after_midday_fut = after_midday_qry.fetch_async(1)

        try:
            before_midday_rec = before_midday_fut.get_result()[0]
            before_midday_ts_ms = day_ts_ms - before_midday_rec.timestampMs
        except IndexError:
            before_midday_ts_ms = MILLIS_PER_24HOURS
            before_midday_rec = None

        try:
            after_midday_rec = after_midday_fut.get_result()[0]
            after_midday_ts_ms = after_midday_rec.timestampMs - day_ts_ms
        except IndexError:
            after_midday_ts_ms = MILLIS_PER_24HOURS
            after_midday_rec = None

        if not any((before_midday_rec, after_midday_rec)):
            raise endpoints.NotFoundException('No locations for %s' % day.date().isoformat())

        if before_midday_ts_ms < after_midday_ts_ms:
            query_params = (before_midday_rec.latitudeE7 / 1E7, before_midday_rec.longitudeE7 / 1E7,
                            before_midday_rec.timestampMs / 1000)
        else:
            query_params = (after_midday_rec.latitudeE7 / 1E7, after_midday_rec.longitudeE7 / 1E7,
                            after_midday_rec.timestampMs / 1000)

        timezone_api_url = \
            "https://maps.googleapis.com/maps/api/timezone/json?location=%.2f,%.2f&timestamp=%d&sensor=false" \
            % query_params

        timezone_result = urlfetch.fetch(url=timezone_api_url, method=urlfetch.GET, validate_certificate=True)
        if timezone_result.status_code == 200:
            new_timezone_obj = TimeZones(id=str(day_ts_ms))
            new_timezone_obj.day = day.date()
            tz_json = json.loads(timezone_result.content)
            new_timezone_obj.dstOffset = tz_json["dstOffset"]
            new_timezone_obj.rawOffset = tz_json["rawOffset"]
            new_timezone_obj.timeZoneId = tz_json["timeZoneId"]
            new_timezone_obj.timeZoneName = tz_json["timeZoneName"]
            new_timezone_obj.put()
            return new_timezone_obj
        else:
            new_timezone_obj = TimeZones(id=str(day_ts_ms))
            new_timezone_obj.day = day.date()
            new_timezone_obj.dstOffset = 0
            new_timezone_obj.rawOffset = 0
            new_timezone_obj.timeZoneId = "UTC"
            new_timezone_obj.timeZoneName = "Coordinated Universal Time"
            return new_timezone_obj

    #noinspection PyUnusedLocal
    @endpoints.method(message_types.VoidMessage, SingleLocationMessage, name='latest', path='latest', http_method='GET')
    @user_required(any_user)
    def get_latest_location(self, not_used_request):
        last_location = Location.query().order(-Location.timestampMs).fetch(1)
        location = self.create_location_message(last_location[0])
        if not last_location:
            raise endpoints.NotFoundException('No locations in database')
        return SingleLocationMessage(location=location)

    @endpoints.method(DAY_RESOURCE_CONTAINER, DayLocationsMessage, name='history', path='history/{year}/{month}/{day}',
                      http_method='GET')
    @user_required(owner_user)
    def get_days_locations(self, request):
        try:
            # history_day = Mid day UTC on the requested day
            # history_day_ts_ms = Timestamp MS mid day on the requested day
            history_day = datetime.datetime(request.year, request.month, request.day, hour=12, minute=0, second=0,
                                            microsecond=0,
                                            tzinfo=None)
            history_day_ts_ms = calendar.timegm(history_day.utctimetuple()) * 1000
        except ValueError:
            raise endpoints.BadRequestException('Not a correct date')

        timezone = self.get_time_zone(history_day, history_day_ts_ms)
        history_day_ts_ms += (timezone.dstOffset * 1000)
        history_day_ts_ms += (timezone.rawOffset * 1000)

        qry = Location.query(Location.timestampMs >= history_day_ts_ms - MILLIS_PER_12HOURS,
                             Location.timestampMs <= history_day_ts_ms
                             + MILLIS_PER_12HOURS).order(-Location.timestampMs)
        days_locations_fut = qry.fetch_async()

        day_message = self.create_day_message(request.year, request.month, request.day)
        tz_message = self.create_timezone_message(timezone)

        location_entries = days_locations_fut.get_result()
        if not location_entries:
            raise endpoints.NotFoundException('No locations for %s' % history_day.date().isoformat())

        locations_message = [self.create_location_message(loc) for loc in location_entries]
        total_locations = len(locations_message)
        return DayLocationsMessage(locations=locations_message, day=day_message,
                                   timeZone=tz_message, totalLocations=total_locations)


application = endpoints.api_server([myLatAPI], restricted=False)
