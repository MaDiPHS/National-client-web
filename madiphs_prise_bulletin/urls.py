from django.urls import path
from . import views

app_name = 'madiphs_prise_bulletin'

urlpatterns = [
    path('intro/', views.bulletin_intro, name='bulletin_intro'),
    path('example/', views.bulletin_example, name='bulletin_example'), 
    path("api/prise/<path:path>", views.bulletin_proxy, name="bulletin_proxy",),
]
