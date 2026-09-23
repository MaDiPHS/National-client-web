from django.urls import path
from .views import *


app_name = 'madiphs_ckan'

urlpatterns = [
   
     path('', Ckan.as_view(), name='ckan'),
     path('ckan_getting_started/', CkanGettingStarted.as_view(), name='ckan_getting_started'), 
     path('ckan_getting_started2/', CkanGettingStarted2.as_view(), name='ckan_getting_started2'),
     path('ckan_getting_started3/', CkanGettingStarted3.as_view(), name='ckan_getting_started3'),
     path('advanced_filter/',AdvancedFilter, name="advanced_filter"),
]