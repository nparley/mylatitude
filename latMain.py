import os
#import urllib
#import sys
import datetime

import logging
logging.getLogger().setLevel(logging.DEBUG)

from google.appengine.api import users
from google.appengine.ext import ndb
from apiclient.discovery import build
from google.appengine.ext import deferred

import jinja2
import webapp2
import json
import base64

from oauth2client.appengine import OAuth2DecoratorFromClientSecrets
#from oauth2client.client import AccessTokenRefreshError
import oauth2client.clientsecrets

decorator = OAuth2DecoratorFromClientSecrets(
  os.path.join(os.path.dirname(__file__), 'client_secrets.json'),
  ['https://www.googleapis.com/auth/userinfo.profile','https://www.googleapis.com/auth/userinfo.email'])

service = build("oauth2", "v2")

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'])

def randomKey(N=15):
  """
  Generate a random key
  @rtype : str
  @param N: int, length of string
  """
  return base64.urlsafe_b64encode(os.urandom(N))

def noAccess(user,output,forwardURL='/'):
  """
  Display no access HTML message

  Creates the no access HTML message to the user and enables them to log out in case
  they have access under a different username.
  @param user: dict of user info
  @param output: webapp2 response object
  @param forwardURL: url to send user to after logout
  @return: None
  """
  template = JINJA_ENVIRONMENT.get_template('default.html')
  content = ('Sorry, %s you do not have access to this app! (<a href="%s">sign out</a>)' %
                (user['name'], users.create_logout_url(forwardURL)))
  template_values = {'content':content,'header':'No Access'}
  output.write(template.render(template_values))

# def signIn(user,output,forwardURL='/'):
#   template = JINJA_ENVIRONMENT.get_template('default.html')
#   greeting = ('<a href="%s">Please Sign in</a>.' % users.create_login_url(forwardURL))
#   template_values = {'content':greeting}
#   output.write(template.render(template_values))

def checkUser(user,output,allowAccess=False,forwardURL='/'):
  """
  Check if the user can view

  Checks the google profile id is in the database of allowed users. Can be used to check that the user dict is set
  i.e. by setting allowAcess == true this function will only fail when user is None
  @param user: dict from user info
  @param output: webapp2 response object
  @param allowAccess: True to allow users not in the database (i.e. for adding users)
  @param forwardURL: URL to forward user to if sign out needs to be generated
  @return: True for allow, False for no access
  """
  if user:
    userCheck = Users.get_by_id(user['id'])
    if userCheck:
      return True
    else:
      if not allowAccess: 
        noAccess(user,output,forwardURL)
        return False
      else:
        return True
  else:
    noAccess(user,output,forwardURL)
    return False  
  
def checkOwnerUser(user,output,forwardURL='/'):
  """
  Check if the user is the owner

  Checks to see if the users google profile id is in the allowed user database with owner set to True.
  @param user: dict from user info
  @param output: webapp2 response object
  @param forwardURL: URL to forward user to if sign out needs to be generated
  @return: True for owner access, False for no access
  """
  if user:
    userCheck = Users.get_by_id(user['id'])
    if userCheck:
      if userCheck.owner:
        return True
      else:
        noAccess(user,output,forwardURL)
        return False
    else:
      noAccess(user,output,forwardURL)
      return False
  else:
    noAccess(user,output,forwardURL)
    return False 
  
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
  userid = ndb.StringProperty()
  owner = ndb.BooleanProperty()
  name = ndb.StringProperty()
  picture = ndb.StringProperty()

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
    if checkUser(user,self.response):
      #noinspection PyBroadException
      try:
        owner = Users.query(Users.owner==True).fetch(1)[0]
      except IndexError:
        greeting =  'Run /setup first'
        template = JINJA_ENVIRONMENT.get_template('default.html')
        template_values = {'content':greeting}
        self.response.write(template.render(template_values))
        return
      gKey = Maps.query().fetch(1)[0]
      locations = Location.query().order(-Location.timestampMs).fetch(2)
      locationArray = []
      latestUpdate = None
      for location in locations:
        timeStamp = location.timestampMs
        if latestUpdate is None:
          latestUpdate = timeStamp
        if timeStamp - latestUpdate > 900000: # Only send other points within 15minutes of latest update
          break
        latitude = location.latitudeE7 / 1E7
        longitude = location.longitudeE7 / 1E7
        accuracy = location.accuracy
        locationArray.append(
          {'latitude': latitude, 'longitude': longitude, 'accuracy': accuracy, 'timeStamp': float(timeStamp)})
      
      if len(locationArray) == 0: # Default to Edinburgh Castle
        locationArray.append({'latitude':55.948346,'longitude':-3.198119,'accuracy':0,'timeStamp':0}) 
      
      clientObj = oauth2client.clientsecrets.loadfile(os.path.join(os.path.dirname(__file__), 'client_secrets.json'))
      apiRoot = "%s/_ah/api" % self.request.host_url  
      template = JINJA_ENVIRONMENT.get_template('index.html')
      template_values = {'locations': locationArray, 'userName': owner.name, 'key': str(gKey.keyid),
                         'owner': Users.get_by_id(user['id']).owner, 'ownerPic': owner.picture, 'apiRoot': apiRoot,
                         'clientID': clientObj[1]['client_id']}
      self.response.write(template.render(template_values))


class setupOwner(webapp2.RequestHandler):
  """
  Creates the user setup process

  GET: Creates the form asking for name and Google Maps API key
  POST: Creates the new owner user and displays the backitude access key
  """
  @decorator.oauth_required
  def get(self):
    http = decorator.http()
    numberOfUsers = Users.query().count()
    if numberOfUsers > 0:
      template_values = {'content':'This app already has an owning user, nothing to do here','header':'Already setup'}
      template = JINJA_ENVIRONMENT.get_template('default.html')
      self.response.write(template.render(template_values))
      return
    user = service.userinfo().get().execute(http=http)
    if user:
      try:
        currentSetupKey = SetupFormKey.query().fetch(1)[0]
        currentSetupKey.key.delete()
      except IndexError:
        pass # No setup key
      newRandomKey = randomKey(15)
      newSetupKey = SetupFormKey(id=newRandomKey)
      newSetupKey.keyid = newRandomKey
      newSetupKey.put()
      template_values = {'userName':user['given_name'],'key':newRandomKey}
      template = JINJA_ENVIRONMENT.get_template('userSetup.html')
      self.response.write(template.render(template_values))
    else:
      noAccess(user,self.response,"/setup")
      
  @decorator.oauth_required    
  def post(self):
    try:
      formKeyCheck = SetupFormKey.get_by_id(self.request.POST['form_key'])
      if not formKeyCheck:
        raise KeyError
    except KeyError:
      self.abort(401)
    numberOfUsers = Users.query().count()
    if numberOfUsers > 0:
      template_values = {'content':'This app already has an owning user, nothing to do here','header':'Already setup'}
      template = JINJA_ENVIRONMENT.get_template('default.html')
      self.response.write(template.render(template_values))
      return
    http = decorator.http()
    user = service.userinfo().get().execute(http=http)
    if user:
      try:
        mapKey = self.request.POST['mapKey']
        userName = self.request.POST['userName']
      except KeyError:
        content = 'Map Key or User Name not set'
        template_values = {'content':content,'header':'Setup Error'}
        template = JINJA_ENVIRONMENT.get_template('default.html')
        self.response.write(template.render(template_values))
        return
      adminUser = Users(id=user['id'])
      adminUser.userid = user['id']
      adminUser.owner = True
      adminUser.name = userName
      try:
        adminUser.picture = user['picture']
      except KeyError:
        adminUser.picture = '/images/blank.jpg'
      adminUser.put()
      gmaps = Maps()
      gmaps.keyid = mapKey
      gmaps.put()
      key = randomKey(15)
      newKeyObj = Keys(id=key)
      newKeyObj.keyid = key
      newKeyObj.put()
      content = ('All setup, %s you have access!' % userName)
      content += '<br/> Your Backitude key is: %s' % key
      template_values = {'content':content,'userName': userName,'header':'Setup Complete'}
      template = JINJA_ENVIRONMENT.get_template('defaultadmin.html')
      self.response.write(template.render(template_values))
    else:
      noAccess(user,self.response,"/setup")
      
class newFriendUrl(webapp2.RequestHandler):
  """
  Creates a new random URL to allow a friend access
  """
  @decorator.oauth_required
  def get(self):
    http = decorator.http()
    user = service.userinfo().get().execute(http=http)
    if checkOwnerUser(user,self.response,forwardURL='/newfriend'):
      key = randomKey(15)
      newURL = FriendUrls(id=key)
      newURL.keyid = key
      newURL.put()
      url = "%s/addviewer/%s" % (self.request.host_url,key)
      content = 'Send your friend this url:<br/><br/> %s' % url
      template_values = {'content':content,'header':'New Friend URL','userName': Users.get_by_id(user['id']).name}
      template = JINJA_ENVIRONMENT.get_template('defaultadmin.html')
      self.response.write(template.render(template_values))
   
class viewURLs(webapp2.RequestHandler):
  """
  Displays the unused friend URLs
  """
  @decorator.oauth_required
  def get(self):
    http = decorator.http()
    user = service.userinfo().get().execute(http=http)
    if checkOwnerUser(user,self.response,forwardURL='/viewurls'):
      currentURLs = FriendUrls.query().fetch(10)
      content = "These URLs are active to enable friends to view your location: <br/>"
      for url in currentURLs:
        content += "<br/>%s/addviewer/%s <br/>" % (self.request.host_url,url.keyid)
      template_values = {'content':content,'header':'Friend URLs','userName': Users.get_by_id(user['id']).name}
      template = JINJA_ENVIRONMENT.get_template('defaultadmin.html')
      self.response.write(template.render(template_values))

class addViewer(webapp2.RequestHandler):
  """
  Add a new user to the allowed views

  Gets the key from the URL and check it's in the database of friend URL keys, if it is add the user
  and delete the key from the database as it has now been used.
  """
  @decorator.oauth_required
  def get(self,key):
    dbKey = FriendUrls.get_by_id(key)
    if dbKey:
      http = decorator.http()
      user = service.userinfo().get().execute(http=http)
      if checkUser(user,self.response,allowAccess=True,forwardURL=self.request.url):
        if Users.get_by_id(user['id']) is None:
          newUser = Users(id=user['id'])
          newUser.userid = user['id']
          newUser.owner = False
          newUser.name = user['given_name']
          try: # Not all users have pictures so sent the picture to blank if it is missing
            newUser.picture = user['picture']
          except KeyError:
            newUser.picture = '/images/blank.jpg'
          newUser.put()
          dbKey.key.delete()
        return self.redirect('/')
    else:
      self.abort(403)

class viewAdmin (webapp2.RequestHandler):
  """
  View the admin settings page for the app
  """
  @decorator.oauth_required
  def get(self):
    http = decorator.http()
    user = service.userinfo().get().execute(http=http)
    if checkOwnerUser(user,self.response,forwardURL='/viewkey'):
      template_values = {'userName': Users.get_by_id(user['id']).name} 
      template = JINJA_ENVIRONMENT.get_template('admin.html')
      self.response.write(template.render(template_values))
    else:
      self.abort(403)
      
class viewKey (webapp2.RequestHandler):
  """
  Display the backitude key to the user
  """
  @decorator.oauth_required
  def get(self):
    http = decorator.http()
    user = service.userinfo().get().execute(http=http)
    if checkOwnerUser(user,self.response,forwardURL='/viewkey'):
      try:
        currentKeys = Keys.query().fetch(1)
        key = currentKeys[0].keyid
      except IndexError:
        content = 'You have no backitude error (Please create a new key'
        template_values = {'content':content,'userName': Users.get_by_id(user['id']).name,'header':'Missing Key'}
        template = JINJA_ENVIRONMENT.get_template('defaultadmin.html')
        self.response.write(template.render(template_values))
        return
      content = '%s' % key
      header = 'Your key is:'
      template_values = {'content':content,'header':header,'userName': Users.get_by_id(user['id']).name} 
      template = JINJA_ENVIRONMENT.get_template('defaultadmin.html')
      self.response.write(template.render(template_values))
    else:
      self.abort(403)
    
class newKey (webapp2.RequestHandler):
  """
  Create a new backitude key and delete the old one
  """
  @decorator.oauth_required
  def get(self):
    http = decorator.http()
    user = service.userinfo().get().execute(http=http)
    if checkOwnerUser(user,self.response,forwardURL='/newkey'):
      try:
        currentKey = Keys.query().fetch(1)[0]
        currentKey.key.delete()
      except IndexError:
        pass #for some reason the key already got deleted
      newRandomKey = randomKey(15)
      newKeyObj = Keys(id=newRandomKey)
      newKeyObj.keyid = newRandomKey
      newKeyObj.put()
      content = '%s' % newRandomKey
      header = 'Your new key is:'      
      template_values = {'content':content,'header':header,'userName': Users.get_by_id(user['id']).name} 
      template = JINJA_ENVIRONMENT.get_template('defaultadmin.html')
      self.response.write(template.render(template_values))
        
class insertLocation(webapp2.RequestHandler):
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
      json_error(self.response,401,"No Access")
      return
    if not Keys.get_by_id(key):
      json_error(self.response,401,"No Access")
      return
    postBody = json.loads(self.request.body)   
    newLocation = Location.get_by_id(postBody['timestampMs'])
    if newLocation:
      json_error(self.response,200,"Time stamp error")
      return
    try:
      newLocation = Location(id=postBody['timestampMs'])
      newLocation.timestampMs = int(postBody['timestampMs'])
      newLocation.latitudeE7 = int(postBody['latitudeE7'])
      newLocation.longitudeE7 = int(postBody['longitudeE7'])
      newLocation.accuracy = int(postBody['accuracy'])
      newLocation.velocity = int(postBody['velocity'])
      newLocation.heading = int(postBody['heading'])
      newLocation.altitude = int(postBody['altitude'])
      newLocation.verticalAccuracy = int(postBody['verticalAccuracy'])
      newLocation.put()
    except (KeyError,ValueError):
      json_error(self.response,400,"Unexpected error")
      return
                
    response = {'data': newLocation.to_dict()}
    self.response.set_status(200)
    self.response.out.write(json.dumps(response))


class insertBack(webapp2.RequestHandler):
  """
  Endpoint for inserting locations from backitude
  """
  #noinspection PyBroadException
  def post(self):
    try:
      key = self.request.POST['key']
      if not Keys.get_by_id(key):
        json_error(self.response,401,"No Access")
        return
      latitude = int(float(self.request.POST['latitude']) * 1E7)
      longitude = int(float(self.request.POST['longitude']) * 1E7)
      accuracy = int(float(self.request.POST['accuracy']))
      try:
        altitude = int(float(self.request.POST['altitude']))
      except (KeyError,ValueError):
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
      except (KeyError,ValueError):
        speed = 0
  #     direction = int(float(self.request.POST['direction']))
      
      # Check to see if the timestamp is in seconds or milli seconds
      # If the timestamp is in seconds this will pass and we can then
      # convert it to millisecodns. If not the test will fail and everything
      # is ok
      try:
        #noinspection PyUnusedLocal
        timestampDate = datetime.datetime.utcfromtimestamp(timestamp)
        timestamp *= 1000
      except ValueError:
        pass
      
    except KeyError, e:
      logging.debug('Missing values %s' % str(e) )
      logging.debug(self.request)
      json_error(self.response,400,"Missing values %s" % str(e))
      return
    
    # Only add the location to the database if the timestamp is unique
    # but send a 200 code so backitude doesn't store the location and 
    # keep trying  
    newLocation = Location.get_by_id(id=str(timestamp))
    if newLocation:
      json_error(self.response,200,"Time stamp error")
      return
    #noinspection PyBroadException
    try:
      newLocation = Location(id=str(timestamp))
      newLocation.timestampMs = timestamp
      newLocation.latitudeE7 = latitude
      newLocation.longitudeE7 = longitude
      newLocation.accuracy = accuracy
      newLocation.velocity = speed
      newLocation.heading = 0
      newLocation.altitude = altitude
      newLocation.verticalAccuracy = 0
      newLocation.put()
    except ValueError:
      logging.debug('DB insert error')
      logging.debug(self.request)
      json_error(self.response,400,"DB insert error" )
      return
      
    response = {'data': newLocation.to_dict()}
    self.response.set_status(200)
    self.response.out.write(json.dumps(response))

class exportLocations(webapp2.RequestHandler):
  """Export the locations database"""
  @decorator.oauth_required
  def get(self):
    http = decorator.http()
    user = service.userinfo().get().execute(http=http)
    if checkOwnerUser(user,self.response,forwardURL='/admin'):
      locationsQuery = Location.query().order(-Location.timestampMs).fetch()
      locations = []
      for location in locationsQuery:
        locations.append(dict(timestampMs = location.timestampMs,
                          latitudeE7 = location.latitudeE7,
                          longitudeE7 = location.longitudeE7,
                          accuracy = location.accuracy,
                          velocity = location.velocity,
                          heading = location.heading,
                          altitude = location.altitude,
                          verticalAccuracy = location.verticalAccuracy ))
      self.response.headers['Content-Type'] = 'text/json'
      self.response.headers['Content-Disposition'] = "attachment; filename=locationsExport.json"
      self.response.out.write(json.dumps(dict(locations =locations)))

def importLocationsTask(userObj):
  # Take for importing data but probably don't need this
  logging.info(userObj)
  pass

class importLocations(webapp2.RequestHandler):
  """
  Kicks off the exportLocation task
  """
  @decorator.oauth_required
  def get(self):
    http = decorator.http()
    user = service.userinfo().get().execute(http=http)
    if checkOwnerUser(user,self.response,forwardURL='/importLocations'):
      content = "Started exporting task, you will be emailed when it's finished<br/>"
      template_values = {'content':content,'header':'Export Locations','userName': Users.get_by_id(user['id']).name}
      template = JINJA_ENVIRONMENT.get_template('defaultadmin.html')
      #deferred.defer(importLocationsTask,user)
      self.response.write(template.render(template_values))

application = webapp2.WSGIApplication(
  [('/', MainPage), ('/insert', insertLocation), ('/backitude', insertBack), ('/setup', setupOwner),
   ('/viewkey', viewKey), ('/newfriend', newFriendUrl), ('/viewurls', viewURLs), #('/test',oauthTest),
   ('/admin', viewAdmin), ('/newkey', newKey),('/importLocations', importLocations),
   ('/exportLocations', exportLocations),
   (decorator.callback_path, decorator.callback_handler()),
   webapp2.Route('/addviewer/<key>', handler=addViewer, name='addviewer')], debug=True)

