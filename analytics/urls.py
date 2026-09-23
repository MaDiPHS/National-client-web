# analytics/urls.py
from django.urls import path
from . import views

app_name = "analytics"

urlpatterns = [
    path('dashboard/', views.AnalyticsDashboardView.as_view(), name='analytics_dashboard'),
    path('crop-analytics/', views.CropAnalyticsView.as_view(), name='crop_analytics'),
    path('time-series/', views.TimeSeriesAnalyticsView.as_view(), name='time_series_analytics'),
    path('ai-diseases/', views.AIDiseaseListView.as_view(), name='ai_disease_list'),
    path('other-crops/', views.HumanDetectedDiseaseListView.as_view(), name='other_crop_list'),
    path('farms/', views.FarmListView.as_view(), name='farm_list'),

    path('visualizations/', views.visualizations_view, name='visualizations'),
    path('api/analytics/visualization-data/', views.visualization_data_api, name='visualization_data_api'),

    path('disease-dashboard/', views.disease_dashboard, name='disease_dashboard'),
    path('compare/', views.compare_dashboards, name='compare_dashboards'),
    path('map/', views.disease_map, name='disease_map'),
    path('forecast/', views.forecasting_dashboard, name='forecasting'),
]