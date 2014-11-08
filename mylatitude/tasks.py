import io
import csv
import zipfile
import json

import logging
logging.getLogger().setLevel(logging.DEBUG)

from google.appengine.ext import deferred
from google.appengine.ext import ndb
from google.appengine.ext import blobstore

import webapp2

from google.appengine.ext.webapp import blobstore_handlers

import mylatitude.datastore
import mylatitude.auth
import mylatitude.tools
from mylatitude import JINJA_ENVIRONMENT


class ExportLocations(webapp2.RequestHandler):
    """
    Export the locations database

    """

    @staticmethod
    def locations_to_dict(start_stamp=None, end_stamp=None):
        """
        Output the location database as a json like dictionary

        @param start_stamp: Int timestampMs of the start date for export (inclusive) or None
        @param end_stamp:  Int timestampMs of the end date for export (inclusive) or None
        @return: dict(locations:[{"timestampMs":1245...,"latitudeE7":1452...,...},{}...])
        """
        location_class = mylatitude.datastore.Location
        if start_stamp and end_stamp:
            locations_query = location_class.query(location_class.timestampMs >= start_stamp,
                                                   location_class.timestampMs <= end_stamp)\
                .order(-location_class.timestampMs).fetch()
        elif start_stamp:
            locations_query = location_class.query(location_class.timestampMs >= start_stamp)\
                .order(-location_class.timestampMs).fetch()
        elif end_stamp:
            locations_query = location_class.query(location_class.timestampMs <= end_stamp)\
                .order(-location_class.timestampMs).fetch()
        else:
            locations_query = location_class.query().order(-location_class.timestampMs).fetch()
        locations = []
        for location in locations_query:
            locations.append(dict(timestampMs=location.timestampMs,
                                  latitudeE7=location.latitudeE7,
                                  longitudeE7=location.longitudeE7,
                                  accuracy=location.accuracy,
                                  velocity=location.velocity,
                                  heading=location.heading,
                                  altitude=location.altitude,
                                  verticalAccuracy=location.verticalAccuracy))
        return dict(locations=locations)

    @staticmethod
    def locations_to_csv(start_stamp=None, end_stamp=None):
        """
        Output the location database as a CSV file similar to the output from bulkloader

        @param start_stamp: Int timestampMs of the start date for export (inclusive) or None
        @param end_stamp: Int timestampMs of the end date for export (inclusive) or None
        @return: CSV file bytes
        """
        location_class = mylatitude.datastore.Location
        if start_stamp and end_stamp:
            locations_query = location_class.query(location_class.timestampMs >= start_stamp,
                                                   location_class.timestampMs <= end_stamp)\
                .order(-location_class.timestampMs).fetch()
        elif start_stamp:
            locations_query = location_class.query(location_class.timestampMs >= start_stamp)\
                .order(-location_class.timestampMs).fetch()
        elif end_stamp:
            locations_query = location_class.query(location_class.timestampMs <= end_stamp)\
                .order(-location_class.timestampMs).fetch()
        else:
            locations_query = location_class.query().order(-location_class.timestampMs).fetch()

        with io.BytesIO() as output:
            writer = csv.writer(output)
            writer.writerow(['timestampMs', 'latitudeE7', 'longitudeE7', 'accuracy', 'velocity', 'heading',
                             'altitude', 'verticalAccuracy'])

            for location in locations_query:
                writer.writerow([location.timestampMs, location.latitudeE7, location.longitudeE7, location.accuracy,
                                 location.velocity, location.heading, location.altitude, location.verticalAccuracy])

            return output.getvalue()

    @mylatitude.auth.decorator.oauth_required
    @mylatitude.auth.check_owner_user_dec('/admin/importExport')
    def post(self, user_data):
        """
        Post method to kick off the export task
        """
        content = 'Task started, you will be emailed with an an attachment when finished'
        header = 'Export task started'
        template_values = {'content': content, 'header': header, 'userName': user_data.name}
        template = JINJA_ENVIRONMENT.get_template('defaultadmin.html')
        deferred.defer(export_locations_task, user_data.auth, self.request.POST['format'])
        self.response.write(template.render(template_values))


def export_locations_task(user_obj, output_format):
    """
    Export location task

    @param user_obj: User dict of the user who started the task for email and to check owner
    @param output_format: Str "JSON" or "CSV" to define what format is exported
    @return: None
    """
    user_check = mylatitude.datastore.Users.get_by_id(user_obj['id'])
    if not user_check.owner:
        message = "Export Location called by non owner user"
        logging.error(message)
        mylatitude.tools.email_after_task(user_obj['email'], "Export Location", message)
        return
    with io.BytesIO() as output:
        z = zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED)
        if output_format == "JSON":
            z.writestr("locations.json", json.dumps(ExportLocations.locations_to_dict()))
        else:
            z.writestr("locations.csv", ExportLocations.locations_to_csv())
        z.close()
        message = "Please find locationsExport.zip attached to this email"
        mylatitude.tools.email_after_task(user_obj['email'], "Export Location", message,
                                          ("locationsExport.zip", output.getvalue()))
    logging.info("Finished Export task")
    return


class ImportLocation(blobstore_handlers.BlobstoreUploadHandler):
    """
    Import locations into the database
    """

    #noinspection PyPep8Naming
    @staticmethod
    @ndb.toplevel
    def import_locations_json(zipfile_obj, filename):
        """
        Imports JSON data from the uploaded Zip file

        @param zipfile_obj: Opened zip file object
        @param filename: Filename of the JSON file in the zip file
        @return: new = number of values added, existing = number of values already in the database
        @raise deferred.PermanentTaskFailure: Raises if there is a problem with the file
        """
        json_obj = json.loads(zipfile_obj.read(filename))
        existing = 0
        new = 0
        try:
            for location in json_obj['locations']:
                new_location = mylatitude.datastore.Location.get_by_id(id=str(location["timestampMs"]))
                if new_location:
                    existing += 1
                    continue
                new_location = mylatitude.datastore.Location(id=str(location["timestampMs"]))
                new_location.timestampMs = location["timestampMs"]
                new_location.latitudeE7 = location["latitudeE7"]
                new_location.longitudeE7 = location["longitudeE7"]
                new_location.accuracy = location["accuracy"]
                new_location.velocity = location["velocity"]
                new_location.heading = location["heading"]
                new_location.altitude = location["altitude"]
                new_location.verticalAccuracy = location["verticalAccuracy"]
                #logging.info(new_location)
                new_location.put_async()
                new += 1
        except (KeyError, IndexError):
            raise deferred.PermanentTaskFailure("Format of input file is incorrect")
        return new, existing

    #noinspection PyPep8Naming
    @staticmethod
    @ndb.toplevel
    def import_locations_csv(zipfile_obj, filename):
        """
        Imports CSV data

        Imports CSV data from the uploaded zip file. The function works out the mapping from
        the headers in the first line of the file

        @param zipfile_obj: Opened zip file object
        @param filename: Filename of the CSV file
        @return: new = number of values added, existing = number of values already in the database
        @raise deferred.PermanentTaskFailure: Raises if there is a problem with the file
        """
        first_line = True
        existing = 0
        new = 0
        lookup = {}
        with zipfile_obj.open(filename) as z:
            for locationLine in z:
                try:
                    if first_line:
                        i = 0
                        for location_values in locationLine.rstrip().split(","):
                            lookup[location_values.strip()] = i
                            i += 1
                        first_line = False
                        continue
                    location_values = map(int, locationLine.rstrip().split(","))
                    new_location = \
                        mylatitude.datastore.Location.get_by_id(id=str(location_values[lookup["timestampMs"]]))
                    if new_location:
                        existing += 1
                        continue
                    new_location = mylatitude.datastore.Location(id=str(location_values[lookup["timestampMs"]]))
                    new_location.timestampMs = location_values[lookup["timestampMs"]]
                    new_location.latitudeE7 = location_values[lookup["latitudeE7"]]
                    new_location.longitudeE7 = location_values[lookup["longitudeE7"]]
                    new_location.accuracy = location_values[lookup["accuracy"]]
                    new_location.velocity = location_values[lookup["velocity"]]
                    new_location.heading = location_values[lookup["heading"]]
                    new_location.altitude = location_values[lookup["altitude"]]
                    new_location.verticalAccuracy = location_values[lookup["verticalAccuracy"]]
                    #logging.info(new_location)
                    new_location.put_async()
                    new += 1
                except (KeyError, IndexError):
                    raise deferred.PermanentTaskFailure("Format of input file is incorrect")
        return new, existing

    @mylatitude.auth.decorator.oauth_required
    @mylatitude.auth.check_owner_user_dec('/admin/importExport')
    def post(self, user_data):
        """
        Post method to kick off the import task

        This method will fail if the upload to the blobstore failed
        """
        #noinspection PyBroadException
        try:
            upload = self.get_uploads()[0]
            content = 'File uploaded, you will be sent an email when processing is finish'
            header = 'File uploaded'
            template_values = {'content': content, 'header': header, 'userName': user_data.name}
            template = JINJA_ENVIRONMENT.get_template('defaultadmin.html')
            deferred.defer(import_locations_task, user_data.auth, upload.key())
            self.response.write(template.render(template_values))
        except:
            content = 'Error uploading location File'
            header = 'Error'
            template_values = {'content': content, 'header': header, 'userName': user_data.name}
            template = JINJA_ENVIRONMENT.get_template('defaultadmin.html')
            self.response.write(template.render(template_values))


def import_locations_task(user_obj, blob_key):
    """
    Task to import the locations from the uploaded Zip file

    @param user_obj: User Dict for email and to check owner info
    @param blob_key: Key of the uploaded file so we can read it from the blobstore
    """
    user_check = mylatitude.datastore.Users.get_by_id(user_obj['id'])
    if not user_check.owner:
        logging.error("Import Location called by non owner user")
        blobstore.delete(blob_key)
        return
        # check we can read from blobstore
    #noinspection PyBroadException
    try:
        import_file = blobstore.BlobReader(blob_key)
    except:
        message = "Error reading uploading file, this file might not have been deleted"
        logging.error(message)
        mylatitude.tools.email_after_task(user_obj['email'], "Import Location (Failed)", message)
        return
        # Check we have a zip file
    try:
        location_zip_file = zipfile.ZipFile(import_file)
    except zipfile.BadZipfile:
        message = "Uploaded file is not a zip file"
        logging.error(message)
        blobstore.delete(blob_key)
        mylatitude.tools.email_after_task(user_obj['email'], "Import Location (Failed)", message)
        return

    location_file = None
    location_file_type = None
    # Find the first file which is a JSON or CSV file and use that
    for fileName in location_zip_file.namelist():
        if fileName.split(".")[-1] == ("json" or "JSON"):
            location_file = fileName
            location_file_type = "JSON"
            break
        elif fileName.split(".")[-1] == ("csv" or "CSV"):
            location_file = fileName
            location_file_type = "CSV"
            break

    if not location_file_type:  # Have not found a JSON or CSV file
        message = "Zip File does not contain json or csv"
        logging.error(message)
        blobstore.delete(blob_key)
        mylatitude.tools.email_after_task(user_obj['email'], "Import Location (Failed)", message)
        return
    elif location_file_type == "CSV":  # CSV file found
        try:
            new, existing = ImportLocation.import_locations_csv(location_zip_file, location_file)
        except deferred.PermanentTaskFailure, e:
            logging.exception(e)
            blobstore.delete(blob_key)
            mylatitude.tools.email_after_task(user_obj['email'], "Import Location (Failed)", e)
            return
    elif location_file_type == "JSON":  # JSON file found
        try:
            new, existing = ImportLocation.import_locations_json(location_zip_file, location_file)
        except deferred.PermanentTaskFailure, e:
            logging.exception(e)
            blobstore.delete(blob_key)
            mylatitude.tools.email_after_task(user_obj['email'], "Import Location (Failed)", e)
            return
    else:
        # Catch all if we have defined a new file type but not defined an import function
        message = "Undefined File type"
        logging.error(message)
        blobstore.delete(blob_key)
        mylatitude.tools.email_after_task(user_obj['email'], "Import Location (Failed)", message)
        return

    message = "Finished import task and all seems ok\nImported %d new values and found %d existing values" % \
              (new, existing)
    logging.info(message)
    blobstore.delete(blob_key)
    mylatitude.tools.email_after_task(user_obj['email'], "Import Location", message)
    return

application = webapp2.WSGIApplication(
    [('/tasks/exportlocations', ExportLocations), ('/tasks/importlocations', ImportLocation)], debug=True)
