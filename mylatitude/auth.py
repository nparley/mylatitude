"""
Module for handling the myLatitude user authentication

ALLOWED_CLIENT_IDS - Allowed client IDs that can connection to
                     backend endpoints
SCOPES             - OAuth scopes that we ask from the user
decorator          - OAuth decorator created by oauth2client
service            - User info from oauth token service
"""

import os
import logging
from functools import wraps

logging.getLogger().setLevel(logging.DEBUG)

from google.appengine.api import users
import oauth2client.clientsecrets
import oauth2client.appengine
import apiclient.discovery
import endpoints

import mylatitude.datastore
from mylatitude import ROOT_DIR
from mylatitude import JINJA_ENVIRONMENT




ALLOWED_CLIENT_IDS = None

__client_secrets_loc__ = os.path.join(ROOT_DIR, 'client_secrets.json')

try:
    __clientObj__ = oauth2client.clientsecrets.loadfile(__client_secrets_loc__)
    ALLOWED_CLIENT_IDS = [__clientObj__[1]['client_id'], endpoints.API_EXPLORER_CLIENT_ID]
except oauth2client.clientsecrets.InvalidClientSecretsError:
    logging.error("Client secret file not found at {}".format(__client_secrets_loc__))
    raise ClientSecretsError(__client_secrets_loc__)

SCOPES = ['https://www.googleapis.com/auth/userinfo.profile', 'https://www.googleapis.com/auth/userinfo.email']

decorator = oauth2client.appengine.OAuth2DecoratorFromClientSecrets(
    os.path.join(ROOT_DIR, 'client_secrets.json'), SCOPES)

service = apiclient.discovery.build("oauth2", "v2")


def user_required(user_test_function):
    """ Decorator to test if there is a valid user for API endpoint function

    returns API if user_test_function passes for user_id if not raises exception
    @param user_test_function: Function to test the Google user_id generated from the access token
    @return: input endpoint function
    @raise endpoints.UnauthorizedException: If user is not allowed
    """
    import auth_util

    def user_required_wrap(func):
        @wraps(func)
        def check_user_token(*args, **kwargs):
            user_id = auth_util.get_google_plus_user_id()
            if user_test_function(user_id):
                return func(*args, **kwargs)
            else:
                raise endpoints.UnauthorizedException('User does not have access to this endpoint')

        return check_user_token

    return user_required_wrap


def any_user(user_id):
    """ Returns True if user_id is in the allowed users database table

    @param user_id: Google User ID
    @return: Boolean True or False
    """
    if user_id:
        user_check = mylatitude.datastore.Users.get_by_id(user_id)
        if user_check:
            return True
    return False


def owner_user(user_id):
    """ Returns True if the user_id is in the allowed users database and owner == True

    @param user_id: Google User ID
    @return: Boolean True or False
    """
    if user_id:
        user_check = mylatitude.datastore.Users.get_by_id(user_id)
        if user_check:
            if user_check.owner:
                return True
    return False


def no_access(user, output, forward_url='/'):
    """
    Display no access HTML message

    Creates the no access HTML message to the user and enables them to log out in case
    they have access under a different username.
    @param user: dict of user info
    @param output: webapp2 response object
    @param forward_url: url to send user to after logout
    @return: None
    """
    template = JINJA_ENVIRONMENT.get_template('default.html')
    content = 'Sorry, {user_name} you do not have access to this app! (<a href="{logout_url}">sign out</a>)'.format(
        user_name=user['name'], logout_url=users.create_logout_url(forward_url))
    template_values = {'content': content, 'header': 'No Access'}
    output.write(template.render(template_values))


def check_owner_user_dec(forward_url='/'):
    """
    Decorator for the checkOwnerUser returns f() if user is the owner if not writes out no access

    @param forward_url: Forwarding URL after sign out
    @return: f() or not access template, user_data which is the result of the datastore get plus user_data.auth which is
    the user dictionary from the oauth profile
    """

    def func_wrapper(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            http = decorator.http()
            user = service.userinfo().get().execute(http=http)
            owner_check, user_data = check_owner_user(user, self.response, forward_url=forward_url)
            if owner_check:
                user_data.auth = user
                kwargs['user_data'] = user_data
                return func(self, *args, **kwargs)

        return wrapper

    return func_wrapper


def check_user(user, output, allow_access=False, forward_url='/'):
    """
    Check if the user can view

    Checks the google profile id is in the database of allowed users. Can be used to check that the user dict is set
    i.e. by setting allowAcess == true this function will only fail when user is None
    @param user: dict from user info
    @param output: webapp2 response object
    @param allow_access: True to allow users not in the database (i.e. for adding users)
    @param forward_url: URL to forward user to if sign out needs to be generated
    @return: True for allow, False for no access
    """
    if user:
        user_check = mylatitude.datastore.Users.get_by_id(user['id'])
        if user_check:
            return True
        else:
            if not allow_access:
                no_access(user, output, forward_url)
                return False
            else:
                return True
    else:
        no_access(user, output, forward_url)
        return False


def check_owner_user(user, output, forward_url='/'):
    """
    Check if the user is the owner

    Checks to see if the users google profile id is in the allowed user database with owner set to True.
    @param user: dict from user info
    @param output: webapp2 response object
    @param forward_url: URL to forward user to if sign out needs to be generated
    @return: True for owner access, False for no access
    """
    if user:
        user_check = mylatitude.datastore.Users.get_by_id(user['id'])
        if user_check:
            if user_check.owner:
                return True, user_check
            else:
                no_access(user, output, forward_url)
                return False, None
        else:
            no_access(user, output, forward_url)
            return False, None
    else:
        no_access(user, output, forward_url)
        return False, None
