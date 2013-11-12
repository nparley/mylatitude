import datetime
import logging
import calendar
import json

logging.getLogger().setLevel(logging.DEBUG)

import endpoints
from protorpc import message_types
from protorpc import remote
from google.appengine.api import urlfetch

import mylatitude.datastore
import mylatitude.auth
import mylatitude.messages

# Constants for milliseconds to units of time
MILLIS_PER_12HOURS = 43200000
MILLIS_PER_24HOURS = 86400000


# myLatitude API backend
myLatAPI = endpoints.api(name='mylatitude', version='v1', description='Rest API to your location data',
                         allowed_client_ids=mylatitude.auth.ALLOWED_CLIENT_IDS)


@myLatAPI.api_class(resource_name='locations', path='locations')
class LocationsEndPoint(remote.Service):
    """ Endpoints for location services of the API """

    @staticmethod
    def create_location_message(location_obj):
        """ Create a location message from a location database object

        @rtype : LocationMessage
        @param location_obj: ndb Location Class object
        @return: LocationMessage Class object
        """
        return mylatitude.messages.LocationMessage(timestampMs=location_obj.timestampMs,
                                                   latitude=location_obj.latitudeE7 / 1E7,
                                                   longitude=location_obj.longitudeE7 / 1E7,
                                                   accuracy=location_obj.accuracy,
                                                   velocity=location_obj.velocity,
                                                   heading=location_obj.heading,
                                                   altitude=location_obj.altitude,
                                                   verticalAccuracy=location_obj.verticalAccuracy)

    @staticmethod
    def create_date_message(year, month, day):
        """ Retunrs a DateMessage from year, month and day ints

        @rtype : DateMessage
        @param year: year as an int (2013)
        @param month: month as an int (11)
        @param day: day as an int (23)
        @return: DateMessage Class object
        """
        return mylatitude.messages.DateMessage(year=year, month=month, day=day)

    @staticmethod
    def create_timezone_message(tz_obj):
        """ Create a TimeZoneMessage from a TimeZone database object

        @rtype : TimeZoneMessage
        @param tz_obj: ndb TimeZones Class object
        @return: TimeZoneMessage Class object
        """
        return mylatitude.messages.TimeZoneMessage(
            dstOffset=tz_obj.dstOffset, rawOffset=tz_obj.rawOffset,
            timeZoneId=tz_obj.timeZoneId, timeZoneName=tz_obj.timeZoneName)

    #noinspection PyPep8Naming
    @staticmethod
    def get_time_zone(day, day_ts_ms):
        """ Get the timezone for the locations on supplied day

        Returns the timezone from lookup table or from using the Google TimeZone API
        @rtype : TimeZones
        @param day: datetime.datetime day for the timezone
        @param day_ts_ms: timestamp for midday on the day in milliseconds
        @return: ndb TimeZones class object
        @raise endpoints.NotFoundException: If no locations are found for the day
        """
        new_timezone_obj = mylatitude.datastore.TimeZones.get_by_id(str(day_ts_ms))
        if new_timezone_obj:
            return new_timezone_obj
        # + order = smallest first, - order = largest first
        before_midday_qry = mylatitude.datastore.Location.query(
            mylatitude.datastore.Location.timestampMs >= day_ts_ms - MILLIS_PER_24HOURS,
            mylatitude.datastore.Location.timestampMs <= day_ts_ms)\
            .order(-mylatitude.datastore.Location.timestampMs)
        before_midday_fut = before_midday_qry.fetch_async(1)

        after_midday_qry = mylatitude.datastore.Location.query(
            mylatitude.datastore.Location.timestampMs > day_ts_ms,
            mylatitude.datastore.Location.timestampMs <= day_ts_ms + MILLIS_PER_24HOURS)\
            .order(mylatitude.datastore.Location.timestampMs)
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
            new_timezone_obj = mylatitude.datastore.TimeZones(id=str(day_ts_ms))
            new_timezone_obj.day = day.date()
            tz_json = json.loads(timezone_result.content)
            new_timezone_obj.dstOffset = tz_json["dstOffset"]
            new_timezone_obj.rawOffset = tz_json["rawOffset"]
            new_timezone_obj.timeZoneId = tz_json["timeZoneId"]
            new_timezone_obj.timeZoneName = tz_json["timeZoneName"]
            new_timezone_obj.put()
            return new_timezone_obj
        else:
            new_timezone_obj = mylatitude.datastore.TimeZones(id=str(day_ts_ms))
            new_timezone_obj.day = day.date()
            new_timezone_obj.dstOffset = 0
            new_timezone_obj.rawOffset = 0
            new_timezone_obj.timeZoneId = "UTC"
            new_timezone_obj.timeZoneName = "Coordinated Universal Time"
            return new_timezone_obj

    #noinspection PyUnusedLocal
    @endpoints.method(message_types.VoidMessage, mylatitude.messages.SingleLocationMessage,
                      name='latest', path='latest', http_method='GET',
                      scopes=mylatitude.auth.SCOPES)
    @mylatitude.auth.user_required(mylatitude.auth.any_user)
    def get_latest_location(self, not_used_request):
        """ Endpoint method which returns the latest location from the database

        @rtype : SingleLocationMessage
        @param not_used_request: Request variable is not used
        @return: SingleLocationMessage message with latest location data
        @raise endpoints.NotFoundException: If no locations are in the database
        """
        last_location = mylatitude.datastore.Location.query().order(-mylatitude.datastore.Location.timestampMs).fetch(1)
        location = self.create_location_message(last_location[0])
        if not last_location:
            raise endpoints.NotFoundException('No locations in database')
        return mylatitude.messages.SingleLocationMessage(location=location)

    @endpoints.method(mylatitude.messages.DATE_RESOURCE_CONTAINER, mylatitude.messages.DateLocationsMessage,
                      name='history', path='history/{year}/{month}/{day}',
                      http_method='GET', scopes=mylatitude.auth.SCOPES)
    @mylatitude.auth.user_required(mylatitude.auth.owner_user)
    def get_dates_locations(self, request):
        """ Endpoint method which returns the locations for a date supplied, along with timezone

        @rtype : DateLocationsMessage
        @param request: DATE_RESOURCE_CONTAINER object containing year, month and day of the date
        @return: DateLocationsMessage class object with locations and timezone
        @raise endpoints.NotFoundException: If no locations exist for the supplied date
        """
        try:
            # history_date = Mid day UTC on the requested day
            # history_date_ts_ms = Timestamp MS mid day on the requested day
            history_date = datetime.datetime(request.year, request.month, request.day, hour=12, minute=0,
                                             second=0, microsecond=0, tzinfo=None)
            history_date_ts_ms = calendar.timegm(history_date.utctimetuple()) * 1000
        except ValueError:
            raise endpoints.BadRequestException('Not a correct date')

        timezone = self.get_time_zone(history_date, history_date_ts_ms)
        history_date_ts_ms -= (timezone.dstOffset * 1000)
        history_date_ts_ms -= (timezone.rawOffset * 1000)
        qry = mylatitude.datastore.Location.query(
            mylatitude.datastore.Location.timestampMs >= history_date_ts_ms - MILLIS_PER_12HOURS,
            mylatitude.datastore.Location.timestampMs <= history_date_ts_ms + MILLIS_PER_12HOURS)\
            .order(-mylatitude.datastore.Location.timestampMs)
        days_locations_fut = qry.fetch_async()

        day_message = self.create_date_message(request.year, request.month, request.day)
        tz_message = self.create_timezone_message(timezone)

        location_entries = days_locations_fut.get_result()
        if not location_entries:
            raise endpoints.NotFoundException('No locations for %s' % history_date.date().isoformat())

        locations_message = [self.create_location_message(loc) for loc in location_entries]
        total_locations = len(locations_message)
        return mylatitude.messages.DateLocationsMessage(
            locations=locations_message, date=day_message,
            timeZone=tz_message, totalLocations=total_locations)


application = endpoints.api_server([myLatAPI], restricted=False)
