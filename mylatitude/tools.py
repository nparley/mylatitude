"""
General functions used by the mylatitude app
"""

import os
import base64
import json
from google.appengine.api import mail
from google.appengine.api import app_identity


def random_key(n=15):
    """
    Generate a random key
    @rtype : str
    @param n: int, length of string
    """
    return base64.urlsafe_b64encode(os.urandom(n))


def json_error(response, code, message):
    """
    Create a JSON error message

    Generate a error message in JSON format for the API parts of the app.
    @param response: webapp2 response object
    @param code: int HTTP status code
    @param message: String error message
    @return: None
    """
    response.headers.add_header('Content-Type', 'application/json')
    response.set_status(code)
    result = {
        'status': 'error',
        'status_code': code,
        'error_message': message,
    }
    response.write(json.dumps(result))


def email_after_task(to_email, task_name, message, attachment=None):
    """
    Call to send an email from admin@app-name.appspot.com that a task has finished

    @param to_email: String to email address, "example@example.com"
    @param task_name: Name of the task that has finished
    @param message: String message to send as the email body
    @param attachment: Tuple of (attachmentFileName,attachmentData) or None for no attachment
    @return: None
    """
    sender = "admin@%s.appspotmail.com" % app_identity.get_application_id()
    if attachment:
        mail.send_mail(sender=sender, to=to_email, subject="Task %s Finished" % task_name, body=message,
                       attachments=[attachment])
    else:
        mail.send_mail(sender=sender, to=to_email, subject="Task %s Finished" % task_name, body=message)