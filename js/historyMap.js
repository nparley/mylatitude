/**
 * Created by Neil on 29/09/13.
 */

/**
 * @fileoverview
 * Provides the Javascript for the history page on the myLatitude code
 * Uses the myLatitude endpoints API
 *
 * @author Neil Parley
 */
/**
 * Adds getBounds method to the google maps Polyline class
 * @return google.maps.LatLngBounds
 */
google.maps.Polyline.prototype.getBounds = function() {
  var bounds = new google.maps.LatLngBounds();
  this.getPath().forEach(function(e) {
    bounds.extend(e);
  });
  return bounds;
};
/** Adds padding to the numbers if needed
 *  @return String
 */
Number.prototype.pad = function (size) {
    if (typeof(size) !== "number") {
        size = 2;
    }
    var s = String(this);
    while (s.length < size) s = "0" + s;
    return s;
};
/** myLatitude namespace for Javascript */
var myLatitude = myLatitude || {};
/** myLatitude.history namespace for history page code */
myLatitude.history = {};
(function() {
/**
 *   Global variables for the myLatitude.history namespace.
 *   Reference to objects such as the Google Map and markers
 */
    this.map = null;
    this.infoWindow = new google.maps.InfoWindow({content: ''});
    this.calObject = null;
    this.currentDate = new Date();
    this.locationData = null;
    this.locationSize = null;
    this.polyline = null;
    this.markers = null;
    this.accuracyCircle = null;
    this.timezone = null;
    // Change the style of the line drawn here
    var polyOptions = {
        strokeColor: '#CC0000',
        strokeOpacity: 1.0,
        strokeWeight: 3,
        clickable: false
    };

/**
 *   Called when the myLatitude.history.currentDate value is changed
 *   Starts the ajax loading animation and starts the data loading function
 */
    this.updateDate = function(){
        $('#noLocationData').hide();
        myLatitude.imageLoader.startAnimation();
        $('#loading').fadeIn();
        $( "#currentDate").text(this.currentDate.toDateString());
        this.getData();
    };
/**
 *   Updates the calendar to reflect the currentDate
 *   Selects the currentDate and sets the calendar to the correct month
 */
    this.updateCal = function(){
        var firstDay = new Date(this.currentDate.getFullYear(), this.currentDate.getMonth(), 1);
        $.extend(this.calObject.options,
        {
            selectedDate:this.currentDate,
            firstDate:firstDay
        });
        this.calObject.render();
    };
/**
 *   Increases the date by 1 day
 *   Calls updateDate and updateCal to get the history and update the calendar
 */
    this.next = function () {
        this.currentDate.setDate(this.currentDate.getDate() - 1);
        this.updateDate();
        this.updateCal();
    };
/**
 *   Decrease the date by 1 day
 *   Calls updateDate and updateCal to get the history and update the calendar
 */
    this.previous = function() {
        this.currentDate.setDate(this.currentDate.getDate() + 1);
        this.updateDate();
        this.updateCal();
    };
/**
 *   Calls the API to get the location data for the currentDate
 *   Start AJAX call and runs function(resp) when complete.
 *   If HTML code is OK, get the data from the location and timeZone object and add the data to the map with addPolyline
 *   If HTML code is 404 show a no data message
 *   If HTML code is 401 try and refresh our access token once
 *   else show a no API access error
 */
    this.getData = function (){
        var year = myLatitude.history.currentDate.getFullYear();
        var month = myLatitude.history.currentDate.getMonth()+1;
        var day = myLatitude.history.currentDate.getDate();

        var payload = {'year':year,'month':month,'day':day};
        gapi.client.mylatitude.locations.history(payload).execute(function (resp) {
            if (!resp.code) {
                myLatitude.endpoints.refreshToken = true;
                myLatitude.history.locationData = resp.locations;
                myLatitude.history.locationSize = resp.totalLocations;
                myLatitude.history.timezone = resp.timeZone;
                myLatitude.history.addPolyline();
                $('#loading').fadeOut();
                myLatitude.imageLoader.stopAnimation();

            } else {
                if (resp.code === 404) {
                    myLatitude.endpoints.refreshToken = true;
                    myLatitude.history.cleanMap();
                    $('#noLocationData').text("No location data for date").show();
                    $('#loading').fadeOut();
                    myLatitude.imageLoader.stopAnimation();
                }
                else if (resp.code === 401 && myLatitude.endpoints.refreshToken ) {
                    myLatitude.endpoints.refreshToken = false;
                    myLatitude.endpoints.signin(true, myLatitude.history.getData);
                }
                else {
                    myLatitude.endpoints.refreshToken = true;
                    myLatitude.history.cleanMap();
                    $('#noLocationData').text("API Access Error ").show();
                    $('#loading').fadeOut();
                    myLatitude.imageLoader.stopAnimation();
                }
            }
        });

    };
/**
 *   Add the polyline and markers to the map
 *   Creates a polyline and adds it to the Google Map, also add circles at each Lat / Long point
 */
    this.addPolyline = function () {
        // To change the style of the circles for each location update change this code
        function getCircle(center,map){
            return new google.maps.Circle({
                center: center,
                radius: 10,
                strokeColor: "#CC0000",
                strokeOpacity: 0.8,
                strokeWeight: 2,
                fillColor: "#CC0000",
                fillOpacity: 0.8,
                map: map
            });
        }
        this.cleanMap(true);
        this.polyline = new google.maps.Polyline(polyOptions);
        this.markers = [];
        var path = this.polyline.getPath();
        if (this.locationData){
            for (var i=0;i<this.locationSize;i++){
                var location = this.locationData[i];
                var latLong = new google.maps.LatLng(location.latitude,location.longitude);
                path.push(latLong);
                this.markers[i]=getCircle(latLong,this.map);
                this.markers[i].info = location;
                this.markers[i].latLong = latLong;
                google.maps.event.addListener(this.markers[i], 'click',function (){
                    myLatitude.history.infoWindow.setContent(myLatitude.history.locationInfo(this.info));
                    myLatitude.history.infoWindow.setPosition(this.latLong);
                    myLatitude.history.addAccuracyCircle(this.info.accuracy,this.latLong);
                    myLatitude.history.infoWindow.open(myLatitude.history.map);
                });
            }
            this.polyline.setMap(this.map);
            this.map.fitBounds(this.polyline.getBounds());
        }
    };
/**
 *   Returns the location information text for a location
 *   Returns the text which appears in the information windows for each location update. The local time is
 *   calculated by using the timezone object returned with the location data.
 *   Note: A javascript date object has the browser's time zone encoded in it, but we are ignoring it and using it as a
 *   UTC date and doing our own conversion. Therefore if we did getHours we would not get the correct local time result,
 *   but we would get localtime + browser time zone offset. Once we have added our timestamp offsets think of "getUTC"
 *   as getLocalTime.
 */
    this.locationInfo = function(location) {
        var use24Hours = 0; // use 24 format, set to 0 for am / pm
        var infoText = "Latitude: " + location.latitude + "<br/>";
        infoText += "Longitude: " + location.longitude + "<br/>";
        infoText += "Accuracy: " + location.accuracy + "m<br/><br/>";
        var timestamp = parseInt(location.timestampMs) + this.timezone.dstOffset * 1000 + this.timezone.rawOffset * 1000;
        var d = new Date(timestamp);
        if (use24Hours) {
            infoText += "At: " + d.getUTCHours().pad() + ":" + d.getUTCMinutes().pad() +
                ":" + d.getUTCSeconds().pad() + " local time<br/>";
        } else {
            var amPm = "AM";
            if (d.getUTCHours() > 11) amPm = "PM";
            var hour = d.getUTCHours();
            if (hour != 12) hour %= 12;
            infoText += "At: " + hour + ":" + d.getUTCMinutes().pad() +
                ":" + d.getUTCSeconds().pad() + " " + amPm + " local time<br/>";
        }
        infoText += this.timezone.timeZoneId +  "<br/>";
        infoText += this.timezone.timeZoneName +  "<br/>";
        return infoText;
    };
/**
 *   Removes all the markers from the map and clears their listeners
 */
    this.removeMarkers = function () {
        if (this.markers){
            for (var i = 0; i < this.markers.length; i++) {
                google.maps.event.clearInstanceListeners(this.markers[i]);
                this.markers[i].setMap(null);
            }
            this.markers = null;
        }
    };
/**
 *   Adds the accuracyCircle to the current selected location point
 *   To change the appearance of the accuracyCircle change this code
 */
    this.addAccuracyCircle = function (accuracy,center) {
        if (this.accuracyCircle) this.accuracyCircle.setMap(null);
        this.accuracyCircle = new google.maps.Circle({
            center: center,
            radius: accuracy,
            strokeColor: "#66CCFF",
            strokeOpacity: 0.8,
            strokeWeight: 2,
            fillColor: "#66CCFF",
            fillOpacity: 0.35,
            map: this.map,
            zIndex:10
        });
    };
/**
 *   Cleans the map of all the objects
 *   If keepLocation is true then don't set the location data objects to null
 *   else clean these as well.
 */
    this.cleanMap = function (keepLocation) {
        if (!keepLocation) {
            this.locationData = null;
            this.locationSize = null;
            this.timezone = null;
        }
        if (this.polyline) this.polyline.setMap(null);
        if (this.accuracyCircle) this.accuracyCircle.setMap(null);
        this.accuracyCircle = null;
        this.polyline = null;
        this.removeMarkers();
        this.infoWindow.close();

    }

}).apply(myLatitude.history);

/**
 *   Functions to display the loading animation
 *   Code adapted from original code from http://preloaders.net/
 */
myLatitude.imageLoader = {};
(function() {
	var cSpeed=9;
	var cWidth=128;
	var cHeight=128;
	var cTotalFrames=22;
	var cFrameWidth=128;
	var cImageSrc='images/spriteLoader.gif';

	var cImageTimeout=null;
	var cIndex=0;
	var cXpos=0;
	var cPreloaderTimeout=null;
	var SECONDS_BETWEEN_FRAMES=0;

	this.startAnimation = function (){

		document.getElementById('loaderImage').style.backgroundImage='url('+cImageSrc+')';
		document.getElementById('loaderImage').style.width=cWidth+'px';
		document.getElementById('loaderImage').style.height=cHeight+'px';

		//FPS = Math.round(100/(maxSpeed+2-speed));
		var FPS = Math.round(100/cSpeed);
		SECONDS_BETWEEN_FRAMES = 1 / FPS;

		cPreloaderTimeout=setTimeout('myLatitude.imageLoader.continueAnimation()', SECONDS_BETWEEN_FRAMES/1000);

	};

	this.continueAnimation = function () {

        cXpos += cFrameWidth;
        //increase the index so we know which frame of our animation we are currently on
        cIndex += 1;

        //if our cIndex is higher than our total number of frames, we're at the end and should restart
        if (cIndex >= cTotalFrames) {
            cXpos = 0;
            cIndex = 0;
        }

        if (document.getElementById('loaderImage'))
            document.getElementById('loaderImage').style.backgroundPosition = (-cXpos) + 'px 0';

        cPreloaderTimeout = setTimeout('myLatitude.imageLoader.continueAnimation()', SECONDS_BETWEEN_FRAMES * 1000);
    };

	this.stopAnimation = function (){//stops animation
		clearTimeout(cPreloaderTimeout);
		cPreloaderTimeout=false;
	};

	this.imageLoader = function(s, fun)//Pre-loads the sprites image
	{
		clearTimeout(cImageTimeout);
		cImageTimeout=0;
        var genImage = new Image();
		genImage.onload=function (){cImageTimeout=setTimeout(fun, 0)};
		genImage.onerror=new Function('alert(\'Could not load the image\')');
		genImage.src=s;
	};

	//The following code starts the animation
	new this.imageLoader(cImageSrc, 'myLatitude.imageLoader.startAnimation()');

}).apply(myLatitude.imageLoader);

/**
 *   Loads the Google Map on Page Load and sets up references to the objects
 */
$(window).load(function () {

    var mapOptions = {
        zoom: 16,
        center: new google.maps.LatLng(55.948346, -3.198119),
        mapTypeId: google.maps.MapTypeId.ROADMAP
    };

    myLatitude.history.map = new google.maps.Map(document.getElementById('map_canvas'), mapOptions);

});

/**
 *   Function call when the API first loads
 *   Sets up handlers for user clicks etc
 *   Only works if we can get the user's info from the token
 */
function apiLoad(){
    gapi.client.oauth2.userinfo.get().execute(function (resp){
        if (!resp.code) {
             myLatitude.history.calObject = $("#histDate").glDatePicker({
                showAlways: false,
                cssName: 'flatwhite',
                onShow: function (calendar) {
                    calendar.fadeIn();
                },
                onHide: function (calendar) {
                    calendar.fadeOut("fast");
                    $(".historyCalMin").show()
                },
                onClick: (function (el, cell, date) {
                    el.val(date.toLocaleDateString());
                    myLatitude.history.currentDate = date;
                    myLatitude.history.updateDate();
                })
            }).glDatePicker(true);

            myLatitude.history.updateDate();

            $(".historyCalMin").click(function () {
                myLatitude.history.calObject.show();
                $(this).hide();
            });

            $("#currentDate").click(function () {
                if ($('#histCal').is(':hidden')) {
                    myLatitude.history.calObject.show();
                    $(".historyCalMin").hide();
                } else {
                    myLatitude.history.calObject.hide();
                    $(".historyCalMin").show();
                }
            });

            $("#previous").click(function () {
                myLatitude.history.next();
            });
            $("#next").click(function () {
                myLatitude.history.previous()
            });
        } else if (resp.code === 401){
            console.log(resp);
            $('#noLocationData').text("No API Access").show();
            $('#loading').fadeOut();
            myLatitude.imageLoader.stopAnimation();
            $('#apiAccess').click(function(){
                $('#noLocationData').hide();
                myLatitude.imageLoader.startAnimation();
                $('#loading').fadeIn();
                $('#apiAccess').hide();
                myLatitude.endpoints.signin(false, apiLoad);
            }).fadeIn();
        } else {
            console.log(resp);
            $('#noLocationData').text("API Access Error ").show();
            $('#loading').fadeOut();
            myLatitude.imageLoader.stopAnimation();
        }
    });
}