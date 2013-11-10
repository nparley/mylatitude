"""
Datastore classes for data stored by the myLatitude app
"""
from google.appengine.ext import ndb


class Location(ndb.Model):
    """
    Database Location Class: for storing location data
    """
    timestampMs = ndb.IntegerProperty(required=True)
    latitudeE7 = ndb.IntegerProperty(required=True)
    longitudeE7 = ndb.IntegerProperty(required=True)
    accuracy = ndb.IntegerProperty(required=True)
    velocity = ndb.IntegerProperty()
    heading = ndb.IntegerProperty()
    altitude = ndb.IntegerProperty()
    verticalAccuracy = ndb.IntegerProperty()


class Maps(ndb.Model):
    """
    Database Maps Class: for storing Google Maps API key
    """
    keyid = ndb.StringProperty(required=True)


class Users(ndb.Model):
    """
    Database Users Class: for storing allowed users
    """
    userid = ndb.StringProperty(required=True)
    owner = ndb.BooleanProperty(required=True)
    name = ndb.StringProperty(required=True)
    picture = ndb.StringProperty(default="/images/blank.jpg")
    email = ndb.StringProperty(required=True)
    clientid = ndb.StringProperty(default="")
    appURL = ndb.StringProperty(default="")
    allowApp = ndb.BooleanProperty(default=False)
    expires = ndb.IntegerProperty(default=0)


class TimeZones(ndb.Model):
    """
    Database TimeZone Class: for storing the Timezone for a day
    """
    day = ndb.DateProperty(required=True)
    dstOffset = ndb.IntegerProperty(required=True)
    rawOffset = ndb.IntegerProperty(required=True)
    timeZoneId = ndb.StringProperty(required=True)
    timeZoneName = ndb.StringProperty(required=True)


class Keys(ndb.Model):
    """
    Database Keys Class: holds the backitude access key
    """
    keyid = ndb.StringProperty(required=True)


class FriendUrls(ndb.Model):
    """
    Database Friends URL Class: holds the random keys to allow friends access
    """
    keyid = ndb.StringProperty(required=True)
    expires = ndb.IntegerProperty(default=0)


class SetupFormKey(ndb.Model):
    """
    Holds the setup form key
    """
    keyid = ndb.StringProperty(required=True)
