from google.appengine.ext import blobstore

import webapp2

import mylatitude.datastore
import mylatitude.auth
import mylatitude.tools
from mylatitude import JINJA_ENVIRONMENT


class NewFriendUrl(webapp2.RequestHandler):
    """
    Creates a new random URL to allow a friend access
    """

    @mylatitude.auth.decorator.oauth_required
    @mylatitude.auth.check_owner_user_dec('/admin/newfriend')
    def get(self, user_data):
        key = mylatitude.tools.random_key(15)
        new_url = mylatitude.datastore.FriendUrls(id=key)
        new_url.keyid = key
        new_url.put()
        url = "%s/admin/addviewer/%s" % (self.request.host_url, key)
        content = 'Send your friend this url:<br/><br/> %s' % url
        template_values = {'content': content, 'header': 'New Friend URL', 'userName': user_data.name}
        template = JINJA_ENVIRONMENT.get_template('defaultadmin.html')
        self.response.write(template.render(template_values))


class ViewURLs(webapp2.RequestHandler):
    """
    Displays the unused friend URLs
    """

    @mylatitude.auth.decorator.oauth_required
    @mylatitude.auth.check_owner_user_dec('/admin/viewurls')
    def get(self, user_data):
        current_urls = mylatitude.datastore.FriendUrls.query().fetch(10)
        content = "These URLs are active to enable friends to view your location: <br/>"
        for url in current_urls:
            content += "<br/>%s/admin/addviewer/%s <br/>" % (self.request.host_url, url.keyid)
        template_values = {'content': content, 'header': 'Friend URLs', 'userName': user_data.name}
        template = JINJA_ENVIRONMENT.get_template('defaultadmin.html')
        self.response.write(template.render(template_values))


class AddViewer(webapp2.RequestHandler):
    """
    Add a new user to the allowed views

    Gets the key from the URL and check it's in the database of friend URL keys, if it is add the user
    and delete the key from the database as it has now been used.
    """
    @mylatitude.auth.decorator.oauth_required
    def get(self, key):
        dbkey = mylatitude.datastore.FriendUrls.get_by_id(key)
        if dbkey:
            http = mylatitude.auth.decorator.http()
            user = mylatitude.auth.service.userinfo().get().execute(http=http)
            if mylatitude.auth.check_user(user, self.response, allow_access=True, forward_url=self.request.url):
                if mylatitude.datastore.Users.get_by_id(user['id']) is None:
                    new_user = mylatitude.datastore.Users(id=user['id'])
                    new_user.userid = user['id']
                    new_user.owner = False
                    new_user.name = user['given_name']
                    new_user.email = user['email']
                    try:  # Not all users have pictures so sent the picture to blank if it is missing
                        new_user.picture = user['picture']
                    except KeyError:
                        new_user.picture = '/images/blank.jpg'
                    new_user.put()
                    dbkey.key.delete()
                return self.redirect('/')
        else:
            self.abort(403)


class ViewKey(webapp2.RequestHandler):
    """
    Display the backitude key to the user
    """

    @mylatitude.auth.decorator.oauth_required
    @mylatitude.auth.check_owner_user_dec('/admin/viewkey')
    def get(self, user_data):
        try:
            currentkeys = mylatitude.datastore.Keys.query().fetch(1)
            key = currentkeys[0].keyid
        except IndexError:
            content = 'You have no backitude error (Please create a new key)'
            template_values = {'content': content, 'userName': user_data.name, 'header': 'Missing Key'}
            template = JINJA_ENVIRONMENT.get_template('defaultadmin.html')
            self.response.write(template.render(template_values))
            return
        content = '%s' % key
        header = 'Your key is:'
        template_values = {'content': content, 'header': header, 'userName': user_data.name}
        template = JINJA_ENVIRONMENT.get_template('defaultadmin.html')
        self.response.write(template.render(template_values))


class NewKey(webapp2.RequestHandler):
    """
    Create a new backitude key and delete the old one
    """
    @mylatitude.auth.decorator.oauth_required
    @mylatitude.auth.check_owner_user_dec('/admin/newkey')
    def get(self, user_data):
        try:
            current_key = mylatitude.datastore.Keys.query().fetch(1)[0]
            current_key.key.delete()
        except IndexError:
            pass  # for some reason the key already got deleted
        new_random_key = mylatitude.tools.random_key(15)
        new_key_obj = mylatitude.datastore.Keys(id=new_random_key)
        new_key_obj.keyid = new_random_key
        new_key_obj.put()
        content = '%s' % new_random_key
        header = 'Your new key is:'
        template_values = {'content': content, 'header': header, 'userName': user_data.name}
        template = JINJA_ENVIRONMENT.get_template('defaultadmin.html')
        self.response.write(template.render(template_values))


class ImportExport(webapp2.RequestHandler):
    """
    Import / Export page

    Get: creates a import / export web page with a link to import and exporting the location data
    """

    @mylatitude.auth.decorator.oauth_required
    @mylatitude.auth.check_owner_user_dec('/admin/importExport')
    def get(self, user_data):
        upload_url = blobstore.create_upload_url('/tasks/importlocations')
        template_values = {'url': upload_url, 'userName': user_data.name}
        template = JINJA_ENVIRONMENT.get_template('import_export.html')
        self.response.write(template.render(template_values))

application = webapp2.WSGIApplication(
    [('/admin/viewkey', ViewKey), ('/admin/newfriend', NewFriendUrl), ('/admin/viewurls', ViewURLs),
     ('/admin/newkey', NewKey), ('/admin/importexport', ImportExport),
     webapp2.Route('/admin/addviewer/<key>', handler=AddViewer, name='addviewer')],debug=True)