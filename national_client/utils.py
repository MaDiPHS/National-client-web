import os
import datetime
import mimetypes
import random
import string
from random import randint
from django.http import HttpResponse, Http404
from django.core.validators import MaxValueValidator
from django.conf import settings
from django.shortcuts import render

def get_task_feedback():
    return "Process initiated. You will be notified when completed."


def get_template_name(template_path, app_name=None):
    if app_name is None:
        return template_path
    else:
        return f"{app_name}/{template_path}"


def random_number(length):
    return str(randint(0, 10**length-1)).zfill(length)


def random_string(length):
    # Get all the ASCII letters in lowercase and uppercase
    letters = string.ascii_uppercase
    # Randomly choose characters from letters for the given length of the string
    random_string = ''.join(random.choice(letters) for i in range(length))
    return random_string
 

def current_year():
    return datetime.date.today().year


def next_year():
    return datetime.date.today().year+1


def previous_year():
    return datetime.date.today().year-1


def current_month():
    return datetime.date.today().month


def max_value_current_year(value):
    return MaxValueValidator(current_year())(value)


def year_choices(min_value = None):
    if not min_value:
        min_value = 1920
    return [(r, r) for r in range(min_value, datetime.date.today().year+1)]


def get_file_path(file_name, app_name=None):
    if app_name is None:
        return file_name
    else:
        return f"{app_name}/{file_name}"
    

def download(path):
    file_path = os.path.join(settings.MEDIA_ROOT, path)
    if os.path.exists(file_path):
        mime_type, _ = mimetypes.guess_type(file_path)
        file_name = os.path.basename(file_path)
        with open(file_path, 'rb') as fh:
            content = fh.read()
            response = HttpResponse(content, content_type=mime_type)
            response['Content-Disposition'] = 'inline; filename=' + file_name
            return response
    raise Http404


def show_feedback(request, message, redirect_url=None, success=True):
    template = "feedback.html"
    context = {
        'message': str(message),
        'success': success,
        'redirect_url': redirect_url
    }
    return render(request, template, context)


def show_success(request, message, redirect_url=None):
    return show_feedback(request=request, message=message, redirect_url=redirect_url)


def show_error(request, message, redirect_url=None):
    return show_feedback(request=request, message=message, redirect_url=redirect_url, success=False)

