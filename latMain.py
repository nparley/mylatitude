import os
import urllib
import sys
import datetime

import logging
logging.getLogger().setLevel(logging.DEBUG)

from google.appengine.api import users
from google.appengine.ext import ndb
from apiclient.discovery import build

import jinja2
import webapp2
import json
import base64

from oauth2client.appengine import OAuth2DecoratorFromClientSecrets
from oauth2client.client import AccessTokenRefreshError

decorator = OAuth2DecoratorFromClientSecrets(
  os.path.join(os.path.dirname(__file__), 'client_secrets.json'),
  ['https://www.googleapis.com/auth/userinfo.profile','https://www.googleapis.com/auth/userinfo.email'])

service = build("oauth2", "v2")

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'])

def randomKey(N=15):
  return base64.urlsafe_b64encode(os.urandom(N))

def noAccess(user,output,forwardURL='/'):
  template = JINJA_ENVIRONMENT.get_template('default.html')
  greeting = ('Sorry, %s you do not have access! (<a href="%s">sign out</a>)' %
                (user['name'], users.create_logout_url(forwardURL)))
  template_values = {'content':greeting}
  output.write(template.render(template_values))

# def signIn(user,output,forwardURL='/'):
#   template = JINJA_ENVIRONMENT.get_template('default.html')
#   greeting = ('<a href="%s">Please Sign in</a>.' % users.create_login_url(forwardURL))
#   template_values = {'content':greeting}
#   output.write(template.render(template_values))

def checkUser(user,output,allowAccess=False,forwardURL='/'):
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
  if user:
    userCheck = Users.get_by_id(user['id'])
    if userCheck:
      if userCheck.owner == True:
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
  response.headers.add_header('Content-Type', 'application/json')
  response.set_status(code)
  result = {
      'status': 'error',
      'status_code': code,
      'error_message': message,
    }
  response.write(json.dumps(result))

  
class Location(ndb.Model):
    timestampMs = ndb.IntegerProperty()
    latitudeE7 = ndb.IntegerProperty()
    longitudeE7 = ndb.IntegerProperty()
    accuracy = ndb.IntegerProperty()
    velocity = ndb.IntegerProperty()
    heading = ndb.IntegerProperty()
    altitude = ndb.IntegerProperty()
    verticalAccuracy = ndb.IntegerProperty()

class Maps(ndb.Model):
    keyid = ndb.StringProperty()

class Users(ndb.Model):
    userid = ndb.StringProperty()
    owner = ndb.BooleanProperty()
    name = ndb.StringProperty()
    picture = ndb.StringProperty()

class Keys(ndb.Model):
    keyid = ndb.StringProperty()  

class FriendUrls(ndb.Model):
  keyid = ndb.StringProperty()

class oauthTest(webapp2.RequestHandler):
  @decorator.oauth_required
  def get(self):
    if decorator.has_credentials():
      http = decorator.http()
      me = service.userinfo().get().execute(http=http)
      #info = {"name":me['displayName'],"id":me['userID']}
      self.response.write(me)

      
  
class MainPage(webapp2.RequestHandler):
  @decorator.oauth_required
  def get(self):
    http = decorator.http()
    user = service.userinfo().get().execute(http=http)
    if checkUser(user,self.response):
      try:
        owner = Users.query(Users.owner==True).fetch(1)[0]
      except:
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
        if latestUpdate == None:
          latestUpdate = timeStamp
        if timeStamp - latestUpdate > 900000: # Only send other points within 15minutes of latest update
          break
        latitude = location.latitudeE7 / 1E7
        longitude = location.longitudeE7 / 1E7
        accuracy = location.accuracy
        locationArray.append({'latitude':latitude,'longitude':longitude,'accuracy':accuracy,'timeStamp':float(timeStamp)})
      
      if len(locationArray) == 0: # Default to Edinburgh Castle
        locationArray.append({'latitude':55.948346,'longitude':-3.198119,'accuracy':0,'timeStamp':0}) 
        
      template = JINJA_ENVIRONMENT.get_template('index.html')
      template_values = {'locations': locationArray, 'userName': owner.name, 'key':str(gKey.keyid),'owner':Users.get_by_id(user['id']).owner, 'ownerPic':owner.picture}
      self.response.write(template.render(template_values))


class setupOwner(webapp2.RequestHandler):
  @decorator.oauth_required
  def get(self):
    http = decorator.http()
    numberOfUsers = Users.query().count()
    if numberOfUsers > 0:
      template_values = {'content':'Already setup'}
      template = JINJA_ENVIRONMENT.get_template('default.html')
      self.response.write(template.render(template_values))
      return
    user = service.userinfo().get().execute(http=http)
    if user:
      template_values = {'userName':user['given_name']}
      template = JINJA_ENVIRONMENT.get_template('userSetup.html')
      self.response.write(template.render(template_values))
    else:
      noAccess(user,self.response,"/setup")
      
  @decorator.oauth_required    
  def post(self):
    numberOfUsers = Users.query().count()
    if numberOfUsers > 0:
      template_values = {'content':'Already setup'}
      template = JINJA_ENVIRONMENT.get_template('defaultadmin.html')
      self.response.write(template.render(template_values))
      return
    http = decorator.http()
    user = service.userinfo().get().execute(http=http)
    if user:
      try:
        mapKey = self.request.POST['mapKey']
        userName = self.request.POST['userName']
      except:
        greeting = 'Map Key or User Name not set'
        template_values = {'content':greeting}
        template = JINJA_ENVIRONMENT.get_template('defaultadmin.html')
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
      newKey = Keys(id=key)
      newKey.keyid = key
      newKey.put()
      greeting = ('All setup, %s you have access!' % userName)
      greeting += '<br/> Your Backitude key is: %s' % key
      template_values = {'content':greeting,'userName': userName}
      template = JINJA_ENVIRONMENT.get_template('defaultadmin.html')
      self.response.write(template.render(template_values))
    else:
      noAccess(user,self.response,"/setup")
      
class newFriendUrl(webapp2.RequestHandler):
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
      greeting = 'Send your friend this url: %s' % url
      template_values = {'content':greeting,'userName': Users.get_by_id(user['id']).name}
      template = JINJA_ENVIRONMENT.get_template('defaultadmin.html')
      self.response.write(template.render(template_values))
   
class viewURLs(webapp2.RequestHandler):
  @decorator.oauth_required
  def get(self):
    http = decorator.http()
    user = service.userinfo().get().execute(http=http)
    if checkOwnerUser(user,self.response,forwardURL='/viewurls'):
      currentURLs = FriendUrls.query().fetch(10)
      greeting = "These URLs are active to enable friends to view your location: <br/>"
      for url in currentURLs:
        greeting += "%s/addviewer/%s <br/>" % (self.request.host_url,url.keyid)
      template_values = {'content':greeting,'userName': Users.get_by_id(user['id']).name}
      template = JINJA_ENVIRONMENT.get_template('defaultadmin.html')
      self.response.write(template.render(template_values))

class addViewer(webapp2.RequestHandler):
  @decorator.oauth_required
  def get(self,key):
    dbKey = FriendUrls.get_by_id(key)
    if dbKey:
      http = decorator.http()
      user = service.userinfo().get().execute(http=http)
      if checkUser(user,self.response,allowAccess=True,forwardURL=self.request.url):
        if Users.get_by_id(user['id']) == None:
          newUser = Users(id=user['id'])
          newUser.userid = user['id']
          newUser.owner = False
          newUser.name = user['given_name']
          try:
            newUser.picture = user['picture']
          except KeyError:
            newUser.picture = '/images/blank.jpg'
          newUser.put()
          dbKey.key.delete()
        return self.redirect('/')
    else:
      self.abort(403)
      
class viewKey (webapp2.RequestHandler):
  @decorator.oauth_required
  def get(self):
    http = decorator.http()
    user = service.userinfo().get().execute(http=http)
    if checkOwnerUser(user,self.response,forwardURL='/viewkey'):
      currentKeys = Keys.query().fetch(1)
      key = currentKeys[0].keyid
      greeting = 'Your key is: %s' % key
      template_values = {'content':greeting,'userName': Users.get_by_id(user['id']).name} 
      template = JINJA_ENVIRONMENT.get_template('defaultadmin.html')
      self.response.write(template.render(template_values))
    else:
      self.abort(403)
    
        
class insertLocation(webapp2.RequestHandler): 
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
    except:
      json_error(self.response,400,"Unexpected error")
      return
                
    response = {'data': newLocation.to_dict()}
    self.response.set_status(200)
    self.response.out.write(json.dumps(response))


class insertBack(webapp2.RequestHandler):
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
      except:
        altitude = 0    
      # Backitude has two timestamps due to the fact it can repost old
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
      except:
        speed = 0
  #     direction = int(float(self.request.POST['direction']))
      
      # Check to see if the timestamp is in seconds or milli seconds
      # If the timestamp is in seconds this will pass and we can then
      # convert it to millisecodns. If not the test will fail and everything
      # is ok
      try:
        timestampDate = datetime.datetime.utcfromtimestamp(timestamp)
        timestamp *= 1000
      except:
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
    except:
      logging.debug('DB insert error')
      logging.debug(self.request)
      json_error(self.response,400,"DB insert error" )
      return
      
    response = {'data': newLocation.to_dict()}
    self.response.set_status(200)
    self.response.out.write(json.dumps(response))

application = webapp2.WSGIApplication([('/', MainPage),('/insert',insertLocation),('/backitude',insertBack),('/setup',setupOwner),
                                       ('/viewkey',viewKey),('/newfriend',newFriendUrl),('/viewurls',viewURLs),('/test',oauthTest),
                                       (decorator.callback_path, decorator.callback_handler()),
                                       webapp2.Route('/addviewer/<key>',handler=addViewer,name='addviewer')], debug=True)

