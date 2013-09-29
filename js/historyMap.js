/**
 * Created by Neil on 29/09/13.
 */
function initialize() {
    var mapOptions = {
        zoom: 16,
        center: new google.maps.LatLng(55.948346, -3.198119),
        mapTypeId: google.maps.MapTypeId.ROADMAP
    }
    var map = new google.maps.Map(document.getElementById('map_canvas'),
        mapOptions);

    var locationCircle = null;
    var locationAccuracy = null;
    var infoWindow = new google.maps.InfoWindow({
        content: "test"
    });

}

google.maps.event.addDomListener(window, 'load', initialize);