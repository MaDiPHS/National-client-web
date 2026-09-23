from django.urls import path
from . import views

app_name = 'forecasts'

urlpatterns = [
    path('temperature/', views.ForecastingTemperatureView.as_view(), name='forecasting_temperature'),
    path('rainfall/', views.ForecastingRainfallView.as_view(), name='forecasting_rainfall'),
]