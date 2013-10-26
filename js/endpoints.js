/**
 * Created by Neil on 29/09/13.
 */
/**
 * @fileoverview
 * Provides methods to access the google client endpoints including the myLatitude API and handle the logging
 * in etc.
 *
 * @author Neil Parley
 */
/** myLatitude namespace for Javascript */
var myLatitude = myLatitude || {};
/** myLatitude.endpoints namespace for cloud endpoints functions */
myLatitude.endpoints = {};
(function() {
/**
 *   Keep hold of the client id etc so we can get at them again later.
 */
    var client_id = null;
    var api_root = null;
    var scopes = ["https://www.googleapis.com/auth/userinfo.email",
                    "https://www.googleapis.com/auth/userinfo.profile"];
    this.refreshToken = true;
/**
 *   Loads the mylatitude API and the google oauth2 API
 *   once both have loaded call myLatitude.endpoints.signin
 */
    this.loadBackEnd = function (clientID, apiRoot, apiStartFunction) {
        client_id = clientID;
        api_root = apiRoot;
        var apisToLoad;
        var callback = function () {
            if (--apisToLoad == 0) {
                myLatitude.endpoints.signin(true, apiStartFunction);
            }
        };
        apisToLoad = 2;
        gapi.client.load('mylatitude', 'v1', callback, api_root);
        gapi.client.load('oauth2', 'v2', callback);
    };
/**
 *   Authorize the user against the API and set the access tokens
 *   clientID filled in by template, immediate = true because we should not need to ask permission again for the backend
 *   Can't use id tokens as we can't get the user id from an id token, so need bearer token
 */
    this.signin = function (mode, callback) {
        gapi.auth.authorize({client_id: client_id, scope: scopes, immediate: mode}, callback);
    };

/**
 *   Default function to be called after authorize just gets the user information from the token
 */
    this.userAuthed = function() {

        gapi.client.oauth2.userinfo.get().execute(function (resp) {
            if (!resp.code) {
                var token = gapi.auth.getToken();
                gapi.client.mylatitude.locations.latest().execute(function (resp) {
//                    console.log(resp);
                });
            }
        });
    }
}).apply(myLatitude.endpoints);
