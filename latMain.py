import os
import urllib
import sys

from google.appengine.api import users
from google.appengine.ext import ndb

import jinja2
import webapp2
import json
import random
import string

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'])

def randomKey(N=15):
  return ''.join(random.choice(string.ascii_uppercase + string.digits + string.ascii_lowercase) for x in range(N))

def noAccess(user,output,forwardURL='/'):
  template = JINJA_ENVIRONMENT.get_template('default.html')
  greeting = ('Sorry, %s you do not have access! (<a href="%s">sign out</a>)' %
                (user.nickname(), users.create_logout_url(forwardURL)))
  template_values = {'content':greeting}
  output.write(template.render(template_values))

def signIn(user,output,forwardURL='/'):
  template = JINJA_ENVIRONMENT.get_template('default.html')
  greeting = ('<a href="%s">Please Sign in</a>.' % users.create_login_url(forwardURL))
  template_values = {'content':greeting}
  output.write(template.render(template_values))

def checkUser(user,output,allowAccess=False,forwardURL='/'):
  if user:
    userCheck = Users.get_by_id(user.user_id())
    if userCheck:
      return True
    else:
      if not allowAccess: 
        noAccess(user,output,forwardURL)
        return False
      else:
        return True
  else:
    signIn(user,output,forwardURL)
    return False  
  
def checkOwnerUser(user,output,forwardURL='/'):
  if user:
    userCheck = Users.get_by_id(user.user_id())
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
    signIn(user,output,forwardURL)
    return False 
  
  
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

class Keys(ndb.Model):
    keyid = ndb.StringProperty()  

class FriendUrls(ndb.Model):
  keyid = ndb.StringProperty()
  
class MainPage(webapp2.RequestHandler):
  def get(self):
    user = users.get_current_user()
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
      template_values = {'locations': locationArray, 'userName': owner.name, 'key':str(gKey.keyid),'owner':Users.get_by_id(user.user_id()).owner}
      self.response.write(template.render(template_values))


class setupOwner(webapp2.RequestHandler):
  def get(self):
    numberOfUsers = Users.query().count()
    if numberOfUsers > 0:
      template_values = {'content':'Already setup'}
      template = JINJA_ENVIRONMENT.get_template('default.html')
      self.response.write(template.render(template_values))
      return
    user = users.get_current_user()
    if user:
      template = JINJA_ENVIRONMENT.get_template('userSetup.html')
      self.response.write(template.render())
    else:
      greeting = ('<a href="%s">Please Sign in</a>.' %
                        users.create_login_url('/setup'))
      template_values = {'content':greeting}
      template = JINJA_ENVIRONMENT.get_template('default.html')
      self.response.write(template.render(template_values))  
      
      
  def post(self):
    numberOfUsers = Users.query().count()
    if numberOfUsers > 0:
      template_values = {'content':'Already setup'}
      template = JINJA_ENVIRONMENT.get_template('defaultadmin.html')
      self.response.write(template.render(template_values))
      return
    user = users.get_current_user()
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
      adminUser = Users(id=user.user_id())
      adminUser.userid = user.user_id()
      adminUser.owner = True
      adminUser.name = userName
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
      greeting = ('<a href="%s">Please Sign in</a>.' %
                        users.create_login_url('/setup'))
      template_values = {'content':greeting}
      template = JINJA_ENVIRONMENT.get_template('default.html')
      self.response.write(template.render(template_values))
      
class newFriendUrl(webapp2.RequestHandler):
  def get(self):
    user = users.get_current_user()
    if checkOwnerUser(user,self.response,forwardURL='/newfriend'):
      key = randomKey(15)
      newURL = FriendUrls(id=key)
      newURL.keyid = key
      newURL.put()
      url = "%s/addviewer/%s" % (self.request.host_url,key)
      greeting = 'Send your friend this url: %s' % url
      template_values = {'content':greeting,'userName': Users.get_by_id(user.user_id()).name}
      template = JINJA_ENVIRONMENT.get_template('defaultadmin.html')
      self.response.write(template.render(template_values))
   
class viewURLs(webapp2.RequestHandler):
  def get(self):
    user = users.get_current_user()
    if checkOwnerUser(user,self.response,forwardURL='/viewurls'):
      currentURLs = FriendUrls.query().fetch(10)
      greeting = "These URLs are active to enable friends to view your location: <br/>"
      for url in currentURLs:
        greeting += "%s/addviewer/%s <br/>" % (self.request.host_url,url.keyid)
      template_values = {'content':greeting,'userName': Users.get_by_id(user.user_id()).name}
      template = JINJA_ENVIRONMENT.get_template('defaultadmin.html')
      self.response.write(template.render(template_values))

class addViewer(webapp2.RequestHandler):
  def get(self,key):
    dbKey = FriendUrls.get_by_id(key)
    if dbKey:
      user = users.get_current_user()
      if checkUser(user,self.response,allowAccess=True,forwardURL=self.request.url):
        if Users.get_by_id(user.user_id()) == None:
          newUser = Users(id=user.user_id())
          newUser.userid = user.user_id()
          newUser.owner = False
          newUser.name = user.nickname()
          newUser.put()
          dbKey.key.delete()
        return self.redirect('/')
    else:
      self.abort(403)
      
class viewKey (webapp2.RequestHandler):
  def get(self):
    user = users.get_current_user()
    if checkOwnerUser(user,self.response,forwardURL='/viewkey'):
      currentKeys = Keys.query().fetch(1)
      key = currentKeys[0].keyid
      greeting = 'Your key is: %s' % key
      template_values = {'content':greeting,'userName': Users.get_by_id(user.user_id()).name} 
      template = JINJA_ENVIRONMENT.get_template('defaultadmin.html')
      self.response.write(template.render(template_values))
    
        
class insertLocation(webapp2.RequestHandler): 
  def post(self):
    self.response.headers['Content-Type'] = 'application/json'
    try:
      key = self.request.GET['key']
    except KeyError:
      self.abort(403)
    if not Keys.get_by_id(key):
      self.abort(403)
    postBody = json.loads(self.request.body)   
    newLocation = Location.get_by_id(postBody['timestampMs'])
    if newLocation:
      self.response.out.write("Time stamp error")
      self.abort(200)
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
      self.response.out.write("Unexpected error")
      self.abort(400)
      
    response = {'data': newLocation.to_dict()}
    self.response.set_status(200)
    self.response.out.write(json.dumps(response))


class insertBack(webapp2.RequestHandler):
  def post(self):
    try:
      key = self.request.POST['key']
      if not Keys.get_by_id(key):
        self.abort(403)
      latitude = int(float(self.request.POST['latitude']) * 1E7)
      longitude = int(float(self.request.POST['longitude']) * 1E7)
      accuracy = int(float(self.request.POST['accuracy']))
      speed = int(float(self.request.POST['speed']))
      altitude = int(float(self.request.POST['altitude']))
      timestamp = int(self.request.POST['timestamp'])
      timezone = self.request.POST['timezone']
    except KeyError:
      self.response.out.write("Unexpected error")
      self.abort(400)
      
    newLocation = Location.get_by_id(id=str(timestamp))
    if newLocation:
      self.response.out.write("Time stamp error")
      self.response.set_status(200)
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
      self.response.out.write("Unexpected error")
      self.abort(400)
      
    response = {'data': newLocation.to_dict()}
    self.response.set_status(200)
    self.response.out.write(json.dumps(response))

application = webapp2.WSGIApplication([('/', MainPage),('/insert',insertLocation),('/backitude',insertBack),('/setup',setupOwner),
                                       ('/viewkey',viewKey),('/newfriend',newFriendUrl),('/viewurls',viewURLs),webapp2.Route('/addviewer/<key>',handler=addViewer,name='addviewer')], debug=True)

     