/**
 * Created by Neil on 29/09/13.
 */
function initialize() {
    var mapOptions = {
        zoom: 16,
        center: new google.maps.LatLng(locations[0].latitude, locations[0].longitude),
        mapTypeId: google.maps.MapTypeId.ROADMAP
    };
    var map = new google.maps.Map(document.getElementById('map_canvas'),
        mapOptions);

    var locationCircle = null;
    var locationAccuracy = null;
    var infoWindow = new google.maps.InfoWindow({
        content: "test"
    });

    function updateLocation(location,userName,userPic) {
        if (location.timeStampMs > 0) {
            var center = new google.maps.LatLng(location.latitude, location.longitude);
            infoWindow.close();
            //noinspection JSValidateTypes
            infoWindow.setPosition(center);
            locationAccuracy = new google.maps.Circle({
                center: center,
                radius: location.accuracy,
                strokeColor: "#66CCFF",
                strokeOpacity: 0.8,
                strokeWeight: 2,
                fillColor: "#66CCFF",
                fillOpacity: 0.35,
                map: map
            });
            locationCircle = new google.maps.Circle({
                center: center,
                radius: 5,
                strokeColor: "#6699FF",
                strokeOpacity: 0.8,
                strokeWeight: 2,
                fillColor: "#6699FF",
                fillOpacity: 0.8,
                map: map
            });
            var d = new Date(parseInt(location.timeStampMs));
            var dNow = new Date();
            var diff = dNow.getTime() - d.getTime();
            diff /= 60000;
            var diffText = "minutes";
            if (diff > 60) {
                diff /= 60;
                diffText = "hours"
            }
            diff = Math.round(diff);
            //noinspection JSValidateTypes
            infoWindow.setPosition(center);
            var updateString = "<img src='" +userPic+"' height='50' width='50' " +
                "style='float:right;border-width:1px;border-style:solid;border-color:#A5A5A5;'> " +
                "<strong>"+userName+"'s location </strong><br/>";
            updateString += "<a href='http://maps.google.com/maps?saddr=&daddr=" + location.latitude + ","
                + location.longitude + "'> Directions Link</a><br/>";
            updateString += "Last updated on:<br/>" + d.toDateString() + "<br/>";
            updateString += "at: " + d.toTimeString() + "<br/>";
            updateString += diff + " " + diffText + " ago <br/><span style=\"font-size:10%\">&nbsp;</span> ";

            var div = document.createElement('div');
            div.className = "infoWin";
            div.innerHTML = updateString;

            infoWindow.setContent(div);

            infoWindow.open(map);
            google.maps.event.addListener(locationAccuracy, 'click', function () {
                infoWindow.open(map);
            });
            google.maps.event.addListener(locationCircle, 'click', function () {
                infoWindow.open(map);
            });


        }
    }

    updateLocation(locations[0],userName,userPic);

}

google.maps.event.addDomListener(window, 'load', initialize);