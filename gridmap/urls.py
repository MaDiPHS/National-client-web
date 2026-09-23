from django.urls import path
from . import views

app_name = 'gridmap'

urlpatterns = [
    path('example/', views.gridmap_example, name='gridmap_example'),
    path('example2/', views.gridmap_example2, name='gridmap_example2'),
    path('example4/', views.gridmap_example4, name='gridmap_example4'),
    path('example5/', views.gridmap_example5, name='gridmap_example5'),
    path('settings.js', views.settings_js, name="views.settings_js"),
]
