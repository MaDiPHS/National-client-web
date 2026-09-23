from django.shortcuts import render
from django.views.generic import TemplateView
from django.conf import settings
from national_client.utils import get_template_name
from core.apps import CoreConfig



APP_NAME = CoreConfig.name
# Create your views here.

class Index(TemplateView):
    template_name = get_template_name("index.html", APP_NAME)

class Viamo_Getting_Started(TemplateView):
    template_name = get_template_name("viamo_getting_started.html", APP_NAME)

class About_Page(TemplateView):
    template_name = get_template_name("about.html", APP_NAME)