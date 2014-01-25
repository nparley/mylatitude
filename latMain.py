import datetime
import json

import logging
logging.getLogger().setLevel(logging.DEBUG)

from google.appengine.api import users

import webapp2

import mylatitude.datastore
import mylatitude.auth
import mylatitude.tools
from mylatitude import JINJA_ENVIRONMENT

# def signIn(user,output,forward_url='/'):
#   template = JINJA_ENVIRONMENT.get_template('default.html')
#   greeting = ('<a href="%s">Please Sign in</a>.' % users.create_login_url(forward_url))
#   template_values = {'content':greeting}
#   output.write(template.render(template_values))

#class oauthTest(webapp2.RequestHandler):
#  @mylatitude.auth.decorator.oauth_required
#  def get(self):
#    if mylatitude.auth.decorator.has_credentials():
#      http = mylatitude.auth.decorator.http()
#      me = mylatitude.auth.mylatitude.auth.service.userinfo().get().execute(http=http)
#      #info = {"name":me['displayName'],"id":me['userID']}
#      self.response.write(me)


class SignOut(webapp2.RequestHandler):
    """
    Sign the user out of their Google account for the app
    """
    def get(self):
        if users.get_current_user():
            sign_out_url = users.create_logout_url('/signout')
            return self.redirect(sign_out_url)
        else:
            template = JINJA_ENVIRONMENT.get_template('default.html')
            content = 'You are no longer signed in'
            template_values = {'content': content, 'header': 'Signed Out'}
            self.response.write(template.render(template_values))


class MainPage(webapp2.RequestHandler):
    """
    Generates the main map page
    """

    @mylatitude.auth.decorator.oauth_required
    def get(self):
        http = mylatitude.auth.decorator.http()
        user = mylatitude.auth.service.userinfo().get().execute(http=http)
        if mylatitude.auth.check_user(user, self.response):
            #noinspection PyBroadException
            try:
                owner = mylatitude.datastore.Users.query(mylatitude.datastore.Users.owner == True).fetch(1)[0]
            except IndexError:
                greeting = 'Run /setup first'
                template = JINJA_ENVIRONMENT.get_template('default.html')
                template_values = {'content': greeting}
                self.response.write(template.render(template_values))
                return
            gkey = mylatitude.datastore.Maps.query().fetch(1)[0]
            locations = mylatitude.datastore.Location.query().order(-mylatitude.datastore.Location.timestampMs).fetch(2)
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

            api_root = "%s/_ah/api" % self.request.host_url
            template = JINJA_ENVIRONMENT.get_template('index.html')
            template_values = {'locations': location_array, 'userName': owner.name, 'key': str(gkey.keyid),
                               'owner': mylatitude.datastore.Users.get_by_id(user['id']).owner,
                               'ownerPic': owner.picture,
                               'apiRoot': api_root,
                               'clientID': mylatitude.auth.CLIENT_ID}
            self.response.write(template.render(template_values))


class SetupOwner(webapp2.RequestHandler):
    """
    Creates the user setup process

    GET: Creates the form asking for name and Google Maps API key
    POST: Creates the new owner user and displays the backitude access key
    """

    @mylatitude.auth.decorator.oauth_required
    def get(self):
        http = mylatitude.auth.decorator.http()
        number_of_users = mylatitude.datastore.Users.query().count()
        if number_of_users > 0:
            template_values = {'content': 'This app already has an owning user, nothing to do here',
                               'header': 'Already setup'}
            template = JINJA_ENVIRONMENT.get_template('default.html')
            self.response.write(template.render(template_values))
            return
        user = mylatitude.auth.service.userinfo().get().execute(http=http)
        if user:
            try:
                current_setup_key = mylatitude.datastore.SetupFormKey.query().fetch(1)[0]
                current_setup_key.key.delete()
            except IndexError:
                pass  # No setup key
            new_random_key = mylatitude.tools.random_key(15)
            new_setup_key = mylatitude.datastore.SetupFormKey(id=new_random_key)
            new_setup_key.keyid = new_random_key
            new_setup_key.put()
            template_values = {'userName': user['given_name'], 'key': new_random_key}
            template = JINJA_ENVIRONMENT.get_template('userSetup.html')
            self.response.write(template.render(template_values))
        else:
            mylatitude.auth.no_access(user, self.response, "/setup")

    @mylatitude.auth.decorator.oauth_required
    def post(self):
        try:
            form_key_check = mylatitude.datastore.SetupFormKey.get_by_id(self.request.POST['form_key'])
            if not form_key_check:
                raise KeyError
            form_key_check.key.delete()
        except KeyError:
            self.abort(401)
        number_of_users = mylatitude.datastore.Users.query().count()
        if number_of_users > 0:
            template_values = {'content': 'This app already has an owning user, nothing to do here',
                               'header': 'Already setup'}
            template = JINJA_ENVIRONMENT.get_template('default.html')
            self.response.write(template.render(template_values))
            return
        http = mylatitude.auth.decorator.http()
        user = mylatitude.auth.service.userinfo().get().execute(http=http)
        if user:
            try:
                map_key = self.request.POST['mapKey']
                user_name = self.request.POST['userName']
            except KeyError:
                content = 'Map Key or User Name not set'
                template_values = {'content': content, 'header': 'Setup Error'}
                template = JINJA_ENVIRONMENT.get_template('default.html')
                self.response.write(template.render(template_values))
                return
            admin_user = mylatitude.datastore.Users(id=user['id'])
            admin_user.userid = user['id']
            admin_user.owner = True
            admin_user.name = user_name
            try:
                admin_user.picture = user['picture']
            except KeyError:
                admin_user.picture = '/images/blank.jpg'
            admin_user.email = user['email']
            admin_user.put()
            gmaps = mylatitude.datastore.Maps()
            gmaps.keyid = map_key
            gmaps.put()
            key = mylatitude.tools.random_key(15)
            new_key_obj = mylatitude.datastore.Keys(id=key)
            new_key_obj.keyid = key
            new_key_obj.put()
            content = ('All setup, %s you have access!' % user_name)
            content += '<br/> Your Backitude key is: %s' % key
            template_values = {'content': content, 'userName': user_name, 'header': 'Setup Complete'}
            template = JINJA_ENVIRONMENT.get_template('defaultadmin.html')
            self.response.write(template.render(template_values))
        else:
            mylatitude.auth.no_access(user, self.response, "/setup")


class ViewHistory(webapp2.RequestHandler):
    """
    View the history page for the app
    """
    @mylatitude.auth.decorator.oauth_required
    @mylatitude.auth.check_owner_user_dec('/history')
    def get(self, user_data):
        api_root = "%s/_ah/api" % self.request.host_url
        template_values = {'userName': user_data.name, 'clientID': mylatitude.auth.CLIENT_ID,
                           'apiRoot': api_root}
        template = JINJA_ENVIRONMENT.get_template('history.html')
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
            mylatitude.tools.json_error(self.response, 401, "No Access")
            return
        if not mylatitude.datastore.Keys.get_by_id(key):
            mylatitude.tools.json_error(self.response, 401, "No Access")
            return
        post_body = json.loads(self.request.body)
        new_location = mylatitude.datastore.Location.get_by_id(post_body['timestampMs'])
        if new_location:
            mylatitude.tools.json_error(self.response, 200, "Time stamp error")
            return
        try:
            new_location = mylatitude.datastore.Location(id=post_body['timestampMs'])
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
            mylatitude.tools.json_error(self.response, 400, "Unexpected error")
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
            if not mylatitude.datastore.Keys.get_by_id(key):
                mylatitude.tools.json_error(self.response, 401, "No Access")
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
            mylatitude.tools.json_error(self.response, 400, "Missing values %s" % str(e))
            return

        # Only add the location to the database if the timestamp is unique
        # but send a 200 code so backitude doesn't store the location and
        # keep trying
        new_location = mylatitude.datastore.Location.get_by_id(id=str(timestamp))
        if new_location:
            mylatitude.tools.json_error(self.response, 200, "Time stamp error")
            return
            #noinspection PyBroadException
        try:
            new_location = mylatitude.datastore.Location(id=str(timestamp))
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
            mylatitude.tools.json_error(self.response, 400, "DB insert error")
            return

        response = {'data': new_location.to_dict()}
        self.response.set_status(200)
        self.response.out.write(json.dumps(response))


class ViewAdmin(webapp2.RequestHandler):
    """
    View the admin settings page for the app
    """

    @mylatitude.auth.decorator.oauth_required
    @mylatitude.auth.check_owner_user_dec('/admin')
    def get(self, user_data):
        template_values = {'userName': user_data.name}
        template = JINJA_ENVIRONMENT.get_template('admin.html')
        self.response.write(template.render(template_values))


application = webapp2.WSGIApplication(
    [('/', MainPage), ('/insert', InsertLocation), ('/backitude', InsertBack), ('/setup', SetupOwner),
     ('/history', ViewHistory), ('/signout', SignOut), ('/admin', ViewAdmin),
     (mylatitude.auth.decorator.callback_path, mylatitude.auth.decorator.callback_handler())], debug=True)
