from django.contrib import admin
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    
    path('', views.Index.as_view(), name='index'),
    path('viamo/', views.Viamo_Getting_Started.as_view(), name = 'viamo'),
    path('about-us/', views.About_Page.as_view(), name = 'about'),
    
    path("news/", views.news_list, name="news_list"),
path("news/<slug:slug>/", views.news_detail, name="news_detail"),
]