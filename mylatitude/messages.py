"""
Protorpc message classes for the backend API
"""
import endpoints
from protorpc import messages
from protorpc import message_types


class UserMessage(messages.Message):
    """ API message for user data """
    userid = messages.StringField(1)
    owner = messages.BooleanField(2)
    name = messages.StringField(3)
    picture = messages.StringField(4)


class LocationMessage(messages.Message):
    """ API message for location data """
    timestampMs = messages.IntegerField(1, variant=messages.Variant.INT64)
    latitude = messages.FloatField(2)
    longitude = messages.FloatField(3)
    accuracy = messages.IntegerField(4, variant=messages.Variant.INT32)
    velocity = messages.IntegerField(5, variant=messages.Variant.INT32)
    heading = messages.IntegerField(6, variant=messages.Variant.INT32)
    altitude = messages.IntegerField(7, variant=messages.Variant.INT32)
    verticalAccuracy = messages.IntegerField(8, variant=messages.Variant.INT32)


class TimeZoneMessage(messages.Message):
    """ API message for Timezone data """
    dstOffset = messages.IntegerField(1, variant=messages.Variant.INT32)
    rawOffset = messages.IntegerField(2, variant=messages.Variant.INT32)
    timeZoneId = messages.StringField(3)
    timeZoneName = messages.StringField(4)


class DateMessage(messages.Message):
    """ API message for a date with year, month, day as ints """
    year = messages.IntegerField(1, variant=messages.Variant.INT32)
    month = messages.IntegerField(2, variant=messages.Variant.INT32)
    day = messages.IntegerField(3, variant=messages.Variant.INT32)


class SingleLocationMessage(messages.Message):
    """ Message with a single location """
    location = messages.MessageField(LocationMessage, 1, repeated=False)


class DateLocationsMessage(messages.Message):
    """ Message with many locations, timezone and day data and number of locations variable """
    locations = messages.MessageField(LocationMessage, 1, repeated=True)
    timeZone = messages.MessageField(TimeZoneMessage, 2, repeated=False)
    date = messages.MessageField(DateMessage, 3, repeated=False)
    totalLocations = messages.IntegerField(4, variant=messages.Variant.INT32)

# Resource to hold the GET request information to the history endpoint
DATE_RESOURCE_CONTAINER = endpoints.ResourceContainer(
    message_types.VoidMessage,
    year=messages.IntegerField(2, variant=messages.Variant.INT32, required=True),
    month=messages.IntegerField(3, variant=messages.Variant.INT32, required=True),
    day=messages.IntegerField(4, variant=messages.Variant.INT32, required=True))
