/**
 * Created by Neil on 29/09/13.
 */
$(window).load(function () {
    var currentDate = new Date();
    var mapOptions = {
        zoom: 16,
        center: new google.maps.LatLng(55.948346, -3.198119),
        mapTypeId: google.maps.MapTypeId.ROADMAP
    };
    var map = new google.maps.Map(document.getElementById('map_canvas'),
        mapOptions);

    var locationCircle = null;
    var locationAccuracy = null;
    var infoWindow = new google.maps.InfoWindow({
        content: "test"
    });
    var calObject = $("#histDate").glDatePicker({
        showAlways: false,
        cssName: 'flatwhite',
        onShow: function(calendar) { calendar.fadeIn(); },
        onHide: function(calendar) { calendar.fadeOut("fast");$( ".historyCalMin").show() },
        onClick: (function(el, cell, date, data) {
            el.val(date.toLocaleDateString());
            currentDate = date;
            updateDate();
        })
    }).glDatePicker(true);
    $( ".historyCalMin" ).click(function() {
      calObject.show();
      $(this).hide();
    });
    $( "#currentDate" ).click(function() {
        if($('#histCal').is(':hidden')) {
            calObject.show();
            $( ".historyCalMin").hide();
        } else {
            calObject.hide();
            $( ".historyCalMin").show();
        }
    });
    function updateDate(){
        $( "#currentDate").text(currentDate.toDateString())
    }
    updateDate();
    function updateCal(){
        var firstDay = new Date(currentDate.getFullYear(), currentDate.getMonth(), 1);
        $.extend(calObject.options,
        {
            selectedDate:currentDate,
            firstDate:firstDay
        });
        calObject.render();
    }
    $( "#previous").click(function() {
        currentDate.setDate(currentDate.getDate() - 1);
        updateDate();
        updateCal();
    });
    $( "#next").click(function() {
        currentDate.setDate(currentDate.getDate() + 1);
        updateDate();
        updateCal();
    });
});
