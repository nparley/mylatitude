# myLatitude

This is a Google App Engine project for creating a personal latitude server replacement making use of the backitude app for updates from an Android phone. (Endpoints for other apps could be add if requested). To set up this code you need to do the following.

## Create a Google App Engine App ##

Go to https://appengine.google.com/ and create a new Google App Engine app. The name of the app will be used in the URL. For example myapp will have the url myapp.appspot.com. Once you have created the app you can view the dashboard etc for your app, by visiting the link above. 

## Create Google API access for the App ##

The code uses Google Maps and Google's sign in to authenticate users. To set this up go to https://code.google.com/apis/console/ and make sure that the name of your app is selected in the drop down box on the left. Then link on services and select:

* Google Maps API v3
* Google Maps Geolocation API
* Google+ API

then click on API Access on the left. We need a Client ID for web applications and we a key for browser apps (with referers).

If there is already a "Client ID for web applications" edit it or if not create a new one, the import information you need to fill in is (you might need to click on more options):

* Redirect URIs: https://yourapp.appspot.com/oauth2callback, http://localhost:8080/oauth2callback
* JavaScript origins: https://yourapp.appspot.com, http://localhost:8080

Once you have set that up click Download JSON, you will need this client.secret file later.

Click create new browser key. In the accept requests from these server IP address box add: https://yourapp.appspot.com/* and http://localhost. Then click create. The string of letters next to API key will be needed later.

## Download the Google App Engine SDK ##

You need this to uplaod the app to the google app engine servers. You need to download the python version for your OS from here: https://developers.google.com/appengine/downloads#Google_App_Engine_SDK_for_Python

## Get a copy of the myLatitude App Code ##

Download the latest zip, or clone the git repo into a directory. In this directory copy your client.secret file you downloaded earlier.

Edit the app.yaml file and replace neillatitude with the name of your app under application

For Mac OsX and Windows: load the google app engine launcher. Click on create new application and then fill in the application name and the parent directory. Making sure that Python 2.7 is selected as the runtime. Once created you can test the app by clicking on the run button. Once it is running you can visit http://localhost:8080/ and once you sign in with you google id and give the app permission it should tell you that you don't have permission to access the page. Which is correct as we have not done the setup. But we might as well do that on the remote server so stop the app and click deploy. This will upload the code to the google app engine servers.

For linux: to test the code will run use: `google_appengine/dev_appserver.py app_folder_path/` and then to upload the code type: `google_appengine/appcfg.py --oauth2 update app_folder_path/`

## Set up the myLatitude app ##

Vist https://yourapp.appspot.com/setup and here you need to type in your name (normally already filled in) and your maps api. This is the new browser key you created earlier. Copy and past it into the box and sudmit the form. You could be told your app is setup and it will give you a key. This is your random key which you use in backitude as your password to upload your location to the app. 

If you now go to https://yourapp.appspot.com/ you should see a google map centred on Edinburgh castle. (As you have no location points yet).

## Set up Backitude ##

The backitude custom server settings to work with this app are:

* Server URL: https://yourapp.appspot.com/backitude
* Auth Options: Credentials in POST
* User Name: <leave blank>
* Password: your random key created during setup (or click view key)
* Device ID: <does not need changing>

The field names are:

* User Name: username
* Password: key
* Latitude: latitude
* Longitude: longitude
* Accuracy: accuracy
* Speed: speed
* Altitude: altitude
* Direction Bearing: (No Value)
* Location Timestamp: utc_timestamp
* Requestion Timestamp: req_timestamp
* Device Id: (No Value)

I prefer location rollback being off and then utc_timestamp will be updated with the latest location. If you like location rollback you might prefer using req_timestamp to show you are still updating. This needs a code change at the moment. 
				
				timestamp = int(self.request.POST['utc_timestamp']) -> timestamp = int(self.request.POST['req_timestamp'])

Once you have setup backitude you should be able to fire an update and then going to: https://yourapp.appspot.com/ should show you your location on a map.

## Let friends View ##

To add a friend click on Add friend. This creates a random url which you can send to a friend. When they visit your page using that url there Google account gets linked and then they have access to view your location. (but not your key etc.). Once they have visited the url gets used up and you will have to create another url for your next friend.

## To Do ##

Lots !

* Add history
* Enable Apps to talk to each other etc.


