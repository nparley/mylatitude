import io
import csv
import os
import datetime
from functools import wraps
import json
import base64
import zipfile

import logging
logging.getLogger().setLevel(logging.DEBUG)

from google.appengine.api import users
from google.appengine.ext import ndb
from apiclient.discovery import build
from google.appengine.ext import blobstore
from google.appengine.ext import deferred
from google.appengine.api import mail
from google.appengine.api import app_identity

import jinja2
import webapp2

from oauth2client.appengine import OAuth2DecoratorFromClientSecrets
from google.appengine.ext.webapp import blobstore_handlers
import oauth2client.clientsecrets

decorator = OAuth2DecoratorFromClientSecrets(
    os.path.join(os.path.dirname(__file__), 'client_secrets.json'),
    ['https://www.googleapis.com/auth/userinfo.profile', 'https://www.googleapis.com/auth/userinfo.email'])

service = build("oauth2", "v2")

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'])


def random_key(n=15):
    """
    Generate a random key
    @rtype : str
    @param n: int, length of string
    """
    return base64.urlsafe_b64encode(os.urandom(n))


def no_access(user, output, forward_url='/'):
    """
    Display no access HTML message

    Creates the no access HTML message to the user and enables them to log out in case
    they have access under a different username.
    @param user: dict of user info
    @param output: webapp2 response object
    @param forward_url: url to send user to after logout
    @return: None
    """
    template = JINJA_ENVIRONMENT.get_template('/templates/default.html')
    content = ('Sorry, %s you do not have access to this app! (<a href="%s">sign out</a>)' %
               (user['name'], users.create_logout_url(forward_url)))
    template_values = {'content': content, 'header': 'No Access'}
    output.write(template.render(template_values))

# def signIn(user,output,forward_url='/'):
#   template = JINJA_ENVIRONMENT.get_template('/templates/default.html')
#   greeting = ('<a href="%s">Please Sign in</a>.' % users.create_login_url(forward_url))
#   template_values = {'content':greeting}
#   output.write(template.render(template_values))


def check_owner_user_dec(forward_url='/'):
    """
    Decorator for the checkOwnerUser returns f() if user is the owner if not writes out no access

    @param forward_url: Forwarding URL after sign out
    @return: f() or not access template, user_data which is the result of the datastore get plus user_data.auth which is
    the user dictionary from the oauth profile
    """

    def func_wrapper(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            http = decorator.http()
            user = service.userinfo().get().execute(http=http)
            owner_check, user_data = check_owner_user(user, self.response, forward_url=forward_url)
            if owner_check:
                user_data.auth = user
                kwargs['user_data'] = user_data
                return func(self, *args, **kwargs)

        return wrapper

    return func_wrapper


def check_user(user, output, allow_access=False, forward_url='/'):
    """
    Check if the user can view

    Checks the google profile id is in the database of allowed users. Can be used to check that the user dict is set
    i.e. by setting allowAcess == true this function will only fail when user is None
    @param user: dict from user info
    @param output: webapp2 response object
    @param allow_access: True to allow users not in the database (i.e. for adding users)
    @param forward_url: URL to forward user to if sign out needs to be generated
    @return: True for allow, False for no access
    """
    if user:
        user_check = Users.get_by_id(user['id'])
        if user_check:
            return True
        else:
            if not allow_access:
                no_access(user, output, forward_url)
                return False
            else:
                return True
    else:
        no_access(user, output, forward_url)
        return False


def check_owner_user(user, output, forward_url='/'):
    """
    Check if the user is the owner

    Checks to see if the users google profile id is in the allowed user database with owner set to True.
    @param user: dict from user info
    @param output: webapp2 response object
    @param forward_url: URL to forward user to if sign out needs to be generated
    @return: True for owner access, False for no access
    """
    if user:
        user_check = Users.get_by_id(user['id'])
        if user_check:
            if user_check.owner:
                return True, user_check
            else:
                no_access(user, output, forward_url)
                return False, None
        else:
            no_access(user, output, forward_url)
            return False, None
    else:
        no_access(user, output, forward_url)
        return False, None


def json_error(response, code, message):
    """
    Create a JSON error message

    Generate a error message in JSON format for the API parts of the app.
    @param response: webapp2 response object
    @param code: int HTTP status code
    @param message: String error message
    @return: None
    """
    response.headers.add_header('Content-Type', 'application/json')
    response.set_status(code)
    result = {
        'status': 'error',
        'status_code': code,
        'error_message': message,
    }
    response.write(json.dumps(result))


def email_after_task(to_email, task_name, message, attachment=None):
    """
    Call to send an email from admin@app-name.appspot.com that a task has finished

    @param to_email: String to email address, "example@example.com"
    @param task_name: Name of the task that has finished
    @param message: String message to send as the email body
    @param attachment: Tuple of (attachmentFileName,attachmentData) or None for no attachment
    @return: None
    """
    sender = "admin@%s.appspotmail.com" % app_identity.get_application_id()
    if attachment:
        mail.send_mail(sender=sender, to=to_email, subject="Task %s Finished" % task_name, body=message,
                       attachments=[attachment])
    else:
        mail.send_mail(sender=sender, to=to_email, subject="Task %s Finished" % task_name, body=message)


class Location(ndb.Model):
    """
    Database Location Class: for storing location data
    """
    timestampMs = ndb.IntegerProperty()
    latitudeE7 = ndb.IntegerProperty()
    longitudeE7 = ndb.IntegerProperty()
    accuracy = ndb.IntegerProperty()
    velocity = ndb.IntegerProperty()
    heading = ndb.IntegerProperty()
    altitude = ndb.IntegerProperty()
    verticalAccuracy = ndb.IntegerProperty()


class Maps(ndb.Model):
    """
    Database Maps Class: for storing Google Maps API key
    """
    keyid = ndb.StringProperty()


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
    day = ndb.DateProperty()
    dstOffset = ndb.IntegerProperty()
    rawOffset = ndb.IntegerProperty()
    timeZoneId = ndb.StringProperty()
    timeZoneName = ndb.StringProperty()


class Keys(ndb.Model):
    """
    Database Keys Class: holds the backitude access key
    """
    keyid = ndb.StringProperty()


class FriendUrls(ndb.Model):
    """
    Database Friends URL Class: holds the random keys to allow friends access
    """
    keyid = ndb.StringProperty()


class SetupFormKey(ndb.Model):
    """
    Holds the setup form key
    """
    keyid = ndb.StringProperty()

#class oauthTest(webapp2.RequestHandler):
#  @decorator.oauth_required
#  def get(self):
#    if decorator.has_credentials():
#      http = decorator.http()
#      me = service.userinfo().get().execute(http=http)
#      #info = {"name":me['displayName'],"id":me['userID']}
#      self.response.write(me)


class MainPage(webapp2.RequestHandler):
    """
    Generates the main map page
    """

    @decorator.oauth_required
    def get(self):
        http = decorator.http()
        user = service.userinfo().get().execute(http=http)
        if check_user(user, self.response):
            #noinspection PyBroadException
            try:
                owner = Users.query(Users.owner == True).fetch(1)[0]
            except IndexError:
                greeting = 'Run /setup first'
                template = JINJA_ENVIRONMENT.get_template('/templates/default.html')
                template_values = {'content': greeting}
                self.response.write(template.render(template_values))
                return
            gkey = Maps.query().fetch(1)[0]
            locations = Location.query().order(-Location.timestampMs).fetch(2)
            location_array = []
            latest_update = None
            for location in locations:
                time_stamp = location.timestampMs
                if latest_update is None:
                    latest_update = time_stamp
                if time_stamp - latest_update > 900000:  # Only send other points within 15minutes of latest update
                    break
                latitude = location.latitudeE7 / 1E7
                longitude = location.longitudeE7 / 1E7
                accuracy = location.accuracy
                location_array.append(
                    {'latitude': latitude, 'longitude': longitude, 'accuracy': accuracy,
                     'timeStampMs': str(time_stamp)})

            if len(location_array) == 0:  # Default to Edinburgh Castle
                location_array.append(
                    {'latitude': 55.948346, 'longitude': -3.198119, 'accuracy': 0, 'timeStampMs': str(0)})

            client_obj = oauth2client.clientsecrets.loadfile(
                os.path.join(os.path.dirname(__file__), 'client_secrets.json'))
            api_root = "%s/_ah/api" % self.request.host_url
            template = JINJA_ENVIRONMENT.get_template('/templates/index.html')
            template_values = {'locations': location_array, 'userName': owner.name, 'key': str(gkey.keyid),
                               'owner': Users.get_by_id(user['id']).owner, 'ownerPic': owner.picture,
                               'apiRoot': api_root,
                               'clientID': client_obj[1]['client_id']}
            self.response.write(template.render(template_values))


class SetupOwner(webapp2.RequestHandler):
    """
    Creates the user setup process

    GET: Creates the form asking for name and Google Maps API key
    POST: Creates the new owner user and displays the backitude access key
    """

    @decorator.oauth_required
    def get(self):
        http = decorator.http()
        number_of_users = Users.query().count()
        if number_of_users > 0:
            template_values = {'content': 'This app already has an owning user, nothing to do here',
                               'header': 'Already setup'}
            template = JINJA_ENVIRONMENT.get_template('/templates/default.html')
            self.response.write(template.render(template_values))
            return
        user = service.userinfo().get().execute(http=http)
        if user:
            try:
                current_setup_key = SetupFormKey.query().fetch(1)[0]
                current_setup_key.key.delete()
            except IndexError:
                pass  # No setup key
            new_random_key = random_key(15)
            new_setup_key = SetupFormKey(id=new_random_key)
            new_setup_key.keyid = new_random_key
            new_setup_key.put()
            template_values = {'userName': user['given_name'], 'key': new_random_key}
            template = JINJA_ENVIRONMENT.get_template('/templates/userSetup.html')
            self.response.write(template.render(template_values))
        else:
            no_access(user, self.response, "/setup")

    @decorator.oauth_required
    def post(self):
        try:
            form_key_check = SetupFormKey.get_by_id(self.request.POST['form_key'])
            if not form_key_check:
                raise KeyError
            form_key_check.key.delete()
        except KeyError:
            self.abort(401)
        number_of_users = Users.query().count()
        if number_of_users > 0:
            template_values = {'content': 'This app already has an owning user, nothing to do here',
                               'header': 'Already setup'}
            template = JINJA_ENVIRONMENT.get_template('/templates/default.html')
            self.response.write(template.render(template_values))
            return
        http = decorator.http()
        user = service.userinfo().get().execute(http=http)
        if user:
            try:
                map_key = self.request.POST['mapKey']
                user_name = self.request.POST['userName']
            except KeyError:
                content = 'Map Key or User Name not set'
                template_values = {'content': content, 'header': 'Setup Error'}
                template = JINJA_ENVIRONMENT.get_template('/templates/default.html')
                self.response.write(template.render(template_values))
                return
            admin_user = Users(id=user['id'])
            admin_user.userid = user['id']
            admin_user.owner = True
            admin_user.name = user_name
            try:
                admin_user.picture = user['picture']
            except KeyError:
                admin_user.picture = '/images/blank.jpg'
            admin_user.put()
            gmaps = Maps()
            gmaps.keyid = map_key
            gmaps.put()
            key = random_key(15)
            new_key_obj = Keys(id=key)
            new_key_obj.keyid = key
            new_key_obj.put()
            content = ('All setup, %s you have access!' % user_name)
            content += '<br/> Your Backitude key is: %s' % key
            template_values = {'content': content, 'userName': user_name, 'header': 'Setup Complete'}
            template = JINJA_ENVIRONMENT.get_template('/templates/defaultadmin.html')
            self.response.write(template.render(template_values))
        else:
            no_access(user, self.response, "/setup")


class NewFriendUrl(webapp2.RequestHandler):
    """
    Creates a new random URL to allow a friend access
    """

    @decorator.oauth_required
    @check_owner_user_dec('/newfriend')
    def get(self, user_data):
        key = random_key(15)
        new_url = FriendUrls(id=key)
        new_url.keyid = key
        new_url.put()
        url = "%s/addviewer/%s" % (self.request.host_url, key)
        content = 'Send your friend this url:<br/><br/> %s' % url
        template_values = {'content': content, 'header': 'New Friend URL', 'userName': user_data.name}
        template = JINJA_ENVIRONMENT.get_template('/templates/defaultadmin.html')
        self.response.write(template.render(template_values))


class ViewURLs(webapp2.RequestHandler):
    """
    Displays the unused friend URLs
    """

    @decorator.oauth_required
    @check_owner_user_dec('/viewurls')
    def get(self, user_data):
        current_urls = FriendUrls.query().fetch(10)
        content = "These URLs are active to enable friends to view your location: <br/>"
        for url in current_urls:
            content += "<br/>%s/addviewer/%s <br/>" % (self.request.host_url, url.keyid)
        template_values = {'content': content, 'header': 'Friend URLs', 'userName': user_data.name}
        template = JINJA_ENVIRONMENT.get_template('/templates/defaultadmin.html')
        self.response.write(template.render(template_values))


class AddViewer(webapp2.RequestHandler):
    """
    Add a new user to the allowed views

    Gets the key from the URL and check it's in the database of friend URL keys, if it is add the user
    and delete the key from the database as it has now been used.
    """
    @decorator.oauth_required
    def get(self, key):
        dbkey = FriendUrls.get_by_id(key)
        if dbkey:
            http = decorator.http()
            user = service.userinfo().get().execute(http=http)
            if check_user(user, self.response, allow_access=True, forward_url=self.request.url):
                if Users.get_by_id(user['id']) is None:
                    new_user = Users(id=user['id'])
                    new_user.userid = user['id']
                    new_user.owner = False
                    new_user.name = user['given_name']
                    try:  # Not all users have pictures so sent the picture to blank if it is missing
                        new_user.picture = user['picture']
                    except KeyError:
                        new_user.picture = '/images/blank.jpg'
                    new_user.put()
                    dbkey.key.delete()
                return self.redirect('/')
        else:
            self.abort(403)


class ViewHistory(webapp2.RequestHandler):
    """
    View the history page for the app
    """
    @decorator.oauth_required
    @check_owner_user_dec('/history')
    def get(self, user_data):
        client_obj = oauth2client.clientsecrets.loadfile(os.path.join(os.path.dirname(__file__), 'client_secrets.json'))
        api_root = "%s/_ah/api" % self.request.host_url
        template_values = {'userName': user_data.name, 'clientID': client_obj[1]['client_id'],
                           'apiRoot': api_root}
        template = JINJA_ENVIRONMENT.get_template('/templates/history.html')
        self.response.write(template.render(template_values))


class ViewAdmin(webapp2.RequestHandler):
    """
    View the admin settings page for the app
    """

    @decorator.oauth_required
    @check_owner_user_dec('/admin')
    def get(self, user_data):
        template_values = {'userName': user_data.name}
        template = JINJA_ENVIRONMENT.get_template('/templates/admin.html')
        self.response.write(template.render(template_values))


class ViewKey(webapp2.RequestHandler):
    """
    Display the backitude key to the user
    """

    @decorator.oauth_required
    @check_owner_user_dec('/viewkey')
    def get(self, user_data):
        try:
            currentkeys = Keys.query().fetch(1)
            key = currentkeys[0].keyid
        except IndexError:
            content = 'You have no backitude error (Please create a new key)'
            template_values = {'content': content, 'userName': user_data.name, 'header': 'Missing Key'}
            template = JINJA_ENVIRONMENT.get_template('/templates/defaultadmin.html')
            self.response.write(template.render(template_values))
            return
        content = '%s' % key
        header = 'Your key is:'
        template_values = {'content': content, 'header': header, 'userName': user_data.name}
        template = JINJA_ENVIRONMENT.get_template('/templates/defaultadmin.html')
        self.response.write(template.render(template_values))


class NewKey(webapp2.RequestHandler):
    """
    Create a new backitude key and delete the old one
    """
    @decorator.oauth_required
    @check_owner_user_dec('/newkey')
    def get(self, user_data):
        try:
            current_key = Keys.query().fetch(1)[0]
            current_key.key.delete()
        except IndexError:
            pass  # for some reason the key already got deleted
        new_random_key = random_key(15)
        new_key_obj = Keys(id=new_random_key)
        new_key_obj.keyid = new_random_key
        new_key_obj.put()
        content = '%s' % new_random_key
        header = 'Your new key is:'
        template_values = {'content': content, 'header': header, 'userName': user_data.name}
        template = JINJA_ENVIRONMENT.get_template('/templates/defaultadmin.html')
        self.response.write(template.render(template_values))


class InsertLocation(webapp2.RequestHandler):
    """
    Endpoint for the app to insert locations using the Google takeout json format.

    For example:
    {
      "timestampMs" : "1000000000000",
      "latitudeE7" : 000000000,
      "longitudeE7" : -00000000,
      "accuracy" : 10,
      "velocity" : 0,
      "heading" : 0,
      "altitude" : 0,
      "verticalAccuracy" : 0
    }
    """

    def post(self):
        self.response.headers['Content-Type'] = 'application/json'
        try:
            key = self.request.GET['key']
        except KeyError:
            json_error(self.response, 401, "No Access")
            return
        if not Keys.get_by_id(key):
            json_error(self.response, 401, "No Access")
            return
        post_body = json.loads(self.request.body)
        new_location = Location.get_by_id(post_body['timestampMs'])
        if new_location:
            json_error(self.response, 200, "Time stamp error")
            return
        try:
            new_location = Location(id=post_body['timestampMs'])
            new_location.timestampMs = int(post_body['timestampMs'])
            new_location.latitudeE7 = int(post_body['latitudeE7'])
            new_location.longitudeE7 = int(post_body['longitudeE7'])
            new_location.accuracy = int(post_body['accuracy'])
            new_location.velocity = int(post_body['velocity'])
            new_location.heading = int(post_body['heading'])
            new_location.altitude = int(post_body['altitude'])
            new_location.verticalAccuracy = int(post_body['verticalAccuracy'])
            new_location.put()
        except (KeyError, ValueError):
            json_error(self.response, 400, "Unexpected error")
            return

        response = {'data': new_location.to_dict()}
        self.response.set_status(201)
        self.response.out.write(json.dumps(response))


class InsertBack(webapp2.RequestHandler):
    """
    Endpoint for inserting locations from backitude
    """
    #noinspection PyBroadException,PyPep8Naming
    def post(self):
        try:
            key = self.request.POST['key']
            if not Keys.get_by_id(key):
                json_error(self.response, 401, "No Access")
                return
            latitude = int(float(self.request.POST['latitude']) * 1E7)
            longitude = int(float(self.request.POST['longitude']) * 1E7)
            accuracy = int(float(self.request.POST['accuracy']))
            try:
                altitude = int(float(self.request.POST['altitude']))
            except (KeyError, ValueError):
                altitude = 0
                # Backitude has two timestamps due to the fact it can re-post old
                # locations.
            # utc_timestamp = time the location was created by the gps or wifi
            # req_timestamp = time a request was made for the location
            # If you setup backitude to post old locations if the accuracy is better
            # and you have not moved then you might decide that you want to record
            # req_timestamp to show that your location is updating.
            timestamp = int(self.request.POST['utc_timestamp'])
            #     timestamp = int(self.request.POST['req_timestamp'])

            # You can decide to try and record the heading if you would like
            try:
                speed = int(float(self.request.POST['speed']))
            except (KeyError, ValueError):
                speed = 0
                #     direction = int(float(self.request.POST['direction']))

            # Check to see if the timestamp is in seconds or milli seconds
            # If the timestamp is in seconds this will pass and we can then
            # convert it to millisecodns. If not the test will fail and everything
            # is ok
            try:
                #noinspection PyUnusedLocal
                time_stamp_date = datetime.datetime.utcfromtimestamp(timestamp)
                timestamp *= 1000
            except ValueError:
                pass

        except KeyError, e:
            logging.debug('Missing values %s' % str(e))
            logging.debug(self.request)
            json_error(self.response, 400, "Missing values %s" % str(e))
            return

        # Only add the location to the database if the timestamp is unique
        # but send a 200 code so backitude doesn't store the location and
        # keep trying
        new_location = Location.get_by_id(id=str(timestamp))
        if new_location:
            json_error(self.response, 200, "Time stamp error")
            return
            #noinspection PyBroadException
        try:
            new_location = Location(id=str(timestamp))
            new_location.timestampMs = timestamp
            new_location.latitudeE7 = latitude
            new_location.longitudeE7 = longitude
            new_location.accuracy = accuracy
            new_location.velocity = speed
            new_location.heading = 0
            new_location.altitude = altitude
            new_location.verticalAccuracy = 0
            new_location.put()
        except ValueError:
            logging.debug('DB insert error')
            logging.debug(self.request)
            json_error(self.response, 400, "DB insert error")
            return

        response = {'data': new_location.to_dict()}
        self.response.set_status(200)
        self.response.out.write(json.dumps(response))


class ExportLocations(webapp2.RequestHandler):
    """
    Export the locations database

    """

    @staticmethod
    def locations_to_dict(start_stamp=None, end_stamp=None):
        """
        Output the location database as a json like dictionary

        @param start_stamp: Int timestampMs of the start date for export (inclusive) or None
        @param end_stamp:  Int timestampMs of the end date for export (inclusive) or None
        @return: dict(locations:[{"timestampMs":1245...,"latitudeE7":1452...,...},{}...])
        """
        if start_stamp and end_stamp:
            locations_query = Location.query(Location.timestampMs >= start_stamp,
                                             Location.timestampMs <= end_stamp).order(-Location.timestampMs).fetch()
        elif start_stamp:
            locations_query = Location.query(Location.timestampMs >= start_stamp).order(-Location.timestampMs).fetch()
        elif end_stamp:
            locations_query = Location.query(Location.timestampMs <= end_stamp).order(-Location.timestampMs).fetch()
        else:
            locations_query = Location.query().order(-Location.timestampMs).fetch()
        locations = []
        for location in locations_query:
            locations.append(dict(timestampMs=location.timestampMs,
                                  latitudeE7=location.latitudeE7,
                                  longitudeE7=location.longitudeE7,
                                  accuracy=location.accuracy,
                                  velocity=location.velocity,
                                  heading=location.heading,
                                  altitude=location.altitude,
                                  verticalAccuracy=location.verticalAccuracy))
        return dict(locations=locations)

    @staticmethod
    def locations_to_csv(start_stamp=None, end_stamp=None):
        """
        Output the location database as a CSV file similar to the output from bulkloader

        @param start_stamp: Int timestampMs of the start date for export (inclusive) or None
        @param end_stamp: Int timestampMs of the end date for export (inclusive) or None
        @return: CSV file bytes
        """
        if start_stamp and end_stamp:
            locations_query = Location.query(Location.timestampMs >= start_stamp,
                                             Location.timestampMs <= end_stamp).order(-Location.timestampMs).fetch()
        elif start_stamp:
            locations_query = Location.query(Location.timestampMs >= start_stamp).order(-Location.timestampMs).fetch()
        elif end_stamp:
            locations_query = Location.query(Location.timestampMs <= end_stamp).order(-Location.timestampMs).fetch()
        else:
            locations_query = Location.query().order(-Location.timestampMs).fetch()

        with io.BytesIO() as output:
            writer = csv.writer(output)
            writer.writerow(['timestampMs', 'latitudeE7', 'longitudeE7', 'accuracy', 'velocity', 'heading',
                             'altitude', 'verticalAccuracy'])

            for location in locations_query:
                writer.writerow([location.timestampMs, location.latitudeE7, location.longitudeE7, location.accuracy,
                                 location.velocity, location.heading, location.altitude, location.verticalAccuracy])

            return output.getvalue()

    @decorator.oauth_required
    @check_owner_user_dec('/importExport')
    def post(self, user_data):
        """
        Post method to kick off the export task
        """
        content = 'Task started, you will be emailed with an an attachment when finished'
        header = 'Export task started'
        template_values = {'content': content, 'header': header, 'userName': user_data.name}
        template = JINJA_ENVIRONMENT.get_template('/templates/defaultadmin.html')
        deferred.defer(export_locations_task, user_data.auth, self.request.POST['format'])
        self.response.write(template.render(template_values))


def export_locations_task(user_obj, output_format):
    """
    Export location task

    @param user_obj: User dict of the user who started the task for email and to check owner
    @param output_format: Str "JSON" or "CSV" to define what format is exported
    @return: None
    """
    user_check = Users.get_by_id(user_obj['id'])
    if not user_check.owner:
        message = "Export Location called by non owner user"
        logging.error(message)
        email_after_task(user_obj['email'], "Export Location", message)
        return
    with io.BytesIO() as output:
        z = zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED)
        if output_format == "JSON":
            z.writestr("locations.json", json.dumps(ExportLocations.locations_to_dict()))
        else:
            z.writestr("locations.csv", ExportLocations.locations_to_csv())
        z.close()
        message = "Please find locationsExport.zip attached to this email"
        email_after_task(user_obj['email'], "Export Location", message, ("locationsExport.zip", output.getvalue()))
    logging.info("Finished Export task")
    return


class ImportExport(webapp2.RequestHandler):
    """
    Import / Export page

    Get: creates a import / export web page with a link to import and exporting the location data
    """

    @decorator.oauth_required
    @check_owner_user_dec('/importExport')
    def get(self, user_data):
        upload_url = blobstore.create_upload_url('/importlocations')
        template_values = {'url': upload_url, 'userName': user_data.name}
        template = JINJA_ENVIRONMENT.get_template('/templates/import_export.html')
        self.response.write(template.render(template_values))


class ImportLocation(blobstore_handlers.BlobstoreUploadHandler):
    """
    Import locations into the database
    """

    #noinspection PyPep8Naming
    @staticmethod
    @ndb.toplevel
    def import_locations_json(zipfile_obj, filename):
        """
        Imports JSON data from the uploaded Zip file

        @param zipfile_obj: Opened zip file object
        @param filename: Filename of the JSON file in the zip file
        @return: new = number of values added, existing = number of values already in the database
        @raise deferred.PermanentTaskFailure: Raises if there is a problem with the file
        """
        json_obj = json.loads(zipfile_obj.read(filename))
        existing = 0
        new = 0
        try:
            for location in json_obj['locations']:
                new_location = Location.get_by_id(id=str(location["timestampMs"]))
                if new_location:
                    existing += 1
                    continue
                new_location = Location(id=str(location["timestampMs"]))
                new_location.timestampMs = location["timestampMs"]
                new_location.latitudeE7 = location["latitudeE7"]
                new_location.longitudeE7 = location["longitudeE7"]
                new_location.accuracy = location["accuracy"]
                new_location.velocity = location["velocity"]
                new_location.heading = location["heading"]
                new_location.altitude = location["altitude"]
                new_location.verticalAccuracy = location["verticalAccuracy"]
                #logging.info(new_location)
                new_location.put_async()
                new += 1
        except (KeyError, IndexError):
            raise deferred.PermanentTaskFailure("Format of input file is incorrect")
        return new, existing

    #noinspection PyPep8Naming
    @staticmethod
    @ndb.toplevel
    def import_locations_csv(zipfile_obj, filename):
        """
        Imports CSV data

        Imports CSV data from the uploaded zip file. The function works out the mapping from
        the headers in the first line of the file

        @param zipfile_obj: Opened zip file object
        @param filename: Filename of the CSV file
        @return: new = number of values added, existing = number of values already in the database
        @raise deferred.PermanentTaskFailure: Raises if there is a problem with the file
        """
        first_line = True
        existing = 0
        new = 0
        lookup = {}
        with zipfile_obj.open(filename) as z:
            for locationLine in z:
                try:
                    if first_line:
                        i = 0
                        for location_values in locationLine.rstrip().split(","):
                            lookup[location_values.strip()] = i
                            i += 1
                        first_line = False
                        continue
                    location_values = map(int, locationLine.rstrip().split(","))
                    new_location = Location.get_by_id(id=str(location_values[lookup["timestampMs"]]))
                    if new_location:
                        existing += 1
                        continue
                    new_location = Location(id=str(location_values[lookup["timestampMs"]]))
                    new_location.timestampMs = location_values[lookup["timestampMs"]]
                    new_location.latitudeE7 = location_values[lookup["latitudeE7"]]
                    new_location.longitudeE7 = location_values[lookup["longitudeE7"]]
                    new_location.accuracy = location_values[lookup["accuracy"]]
                    new_location.velocity = location_values[lookup["velocity"]]
                    new_location.heading = location_values[lookup["heading"]]
                    new_location.altitude = location_values[lookup["altitude"]]
                    new_location.verticalAccuracy = location_values[lookup["verticalAccuracy"]]
                    #logging.info(new_location)
                    new_location.put_async()
                    new += 1
                except (KeyError, IndexError):
                    raise deferred.PermanentTaskFailure("Format of input file is incorrect")
        return new, existing

    @decorator.oauth_required
    @check_owner_user_dec('/importExport')
    def post(self, user_data):
        """
        Post method to kick off the import task

        This method will fail if the upload to the blobstore failed
        """
        #noinspection PyBroadException
        try:
            upload = self.get_uploads()[0]
            content = 'File uploaded, you will be sent an email when processing is finish'
            header = 'File uploaded'
            template_values = {'content': content, 'header': header, 'userName': user_data.name}
            template = JINJA_ENVIRONMENT.get_template('/templates/defaultadmin.html')
            deferred.defer(import_locations_task, user_data.auth, upload.key())
            self.response.write(template.render(template_values))
        except:
            content = 'Error uploading location File'
            header = 'Error'
            template_values = {'content': content, 'header': header, 'userName': user_data.name}
            template = JINJA_ENVIRONMENT.get_template('/templates/defaultadmin.html')
            self.response.write(template.render(template_values))


def import_locations_task(user_obj, blob_key):
    """
    Task to import the locations from the uploaded Zip file

    @param user_obj: User Dict for email and to check owner info
    @param blob_key: Key of the uploaded file so we can read it from the blobstore
    """
    user_check = Users.get_by_id(user_obj['id'])
    if not user_check.owner:
        logging.error("Import Location called by non owner user")
        blobstore.delete(blob_key)
        return
        # check we can read from blobstore
    #noinspection PyBroadException
    try:
        import_file = blobstore.BlobReader(blob_key)
    except:
        message = "Error reading uploading file, this file might not have been deleted"
        logging.error(message)
        email_after_task(user_obj['email'], "Import Location", message)
        return
        # Check we have a zip file
    try:
        location_zip_file = zipfile.ZipFile(import_file)
    except zipfile.BadZipfile:
        message = "Uploaded file is not a zip file"
        logging.error(message)
        blobstore.delete(blob_key)
        email_after_task(user_obj['email'], "Import Location", message)
        return

    location_file = None
    location_file_type = None
    # Find the first file which is a JSON or CSV file and use that
    for fileName in location_zip_file.namelist():
        if fileName.split(".")[-1] == ("json" or "JSON"):
            location_file = fileName
            location_file_type = "JSON"
            break
        elif fileName.split(".")[-1] == ("csv" or "CSV"):
            location_file = fileName
            location_file_type = "CSV"
            break

    if not location_file_type:  # Have not found a JSON or CSV file
        message = "Zip File does not contain json or csv"
        logging.error(message)
        blobstore.delete(blob_key)
        email_after_task(user_obj['email'], "Import Location", message)
        return
    elif location_file_type == "CSV":  # CSV file found
        try:
            new, existing = ImportLocation.import_locations_csv(location_zip_file, location_file)
        except deferred.PermanentTaskFailure, e:
            logging.exception(e)
            blobstore.delete(blob_key)
            email_after_task(user_obj['email'], "Import Location", e)
            return
    elif location_file_type == "JSON":  # JSON file found
        try:
            new, existing = ImportLocation.import_locations_json(location_zip_file, location_file)
        except deferred.PermanentTaskFailure, e:
            logging.exception(e)
            blobstore.delete(blob_key)
            email_after_task(user_obj['email'], "Import Location", e)
            return
    else:
        # Catch all if we have defined a new file type but not defined an import function
        message = "Undefined File type"
        logging.error(message)
        blobstore.delete(blob_key)
        email_after_task(user_obj['email'], "Import Location", message)
        return

    message = "Finished import task and all seems ok\nImported %d new values and found %d existing values" % \
              (new, existing)
    logging.info(message)
    blobstore.delete(blob_key)
    email_after_task(user_obj['email'], "Import Location", message)
    return


application = webapp2.WSGIApplication(
    [('/', MainPage), ('/insert', InsertLocation), ('/backitude', InsertBack), ('/setup', SetupOwner),
     ('/viewkey', ViewKey), ('/newfriend', NewFriendUrl), ('/viewurls', ViewURLs),  # ('/test',oauthTest),
     ('/admin', ViewAdmin), ('/newkey', NewKey), ('/importexport', ImportExport), ('/history', ViewHistory),
     ('/exportlocations', ExportLocations), ('/importlocations', ImportLocation),
     (decorator.callback_path, decorator.callback_handler()),
     webapp2.Route('/addviewer/<key>', handler=AddViewer, name='addviewer')], debug=True)
