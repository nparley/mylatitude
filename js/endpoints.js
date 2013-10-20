/**
 * Created by Neil on 29/09/13.
 */
function signin(mode, callback, clientID) { // clientID filled in by template, immediate = true because we should not need to ask permission again
    gapi.auth.authorize({client_id: clientID,
            scope: ["https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"], immediate: true,
            response_type: 'token'}, // Can't use id tokens as we can't get the user if from an id token
        callback);
}

function userAuthed() {

    var request =
        gapi.client.oauth2.userinfo.get().execute(function (resp) { // Check the token by calling userinfo, if it's ok call our end point
            if (!resp.code) {
                var token = gapi.auth.getToken();
                gapi.client.mylatitude.locations.latest().execute(function (resp) { // this does not do anything yet it's just a test.
//                    console.log(resp);
                });
            }
        });
}
