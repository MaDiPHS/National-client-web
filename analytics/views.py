
from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone
from django.views.generic import TemplateView, ListView
from django.db.models import Count, Avg, Q, Sum
from django.db.models.functions import ExtractMonth, ExtractYear, TruncMonth
import folium
from folium.plugins import HeatMap
import plotly.graph_objs as go
import plotly.offline as opy
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import make_pipeline
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict
from .models import Farm, AIDisease, HumanDetectedDisease
from .filters import AIDiseaseFilter, HumanDetectedDiseaseFilter, FarmFilter
from .forms import DiseaseFilterForm
from django.core.serializers.json import DjangoJSONEncoder
from django_filters.views import FilterView

class AnalyticsDashboardView(TemplateView):
    template_name = 'analytics/dashboard.html'

    # Passed to every opy.plot(...) call so Plotly actually resizes to fit
    # its container div instead of rendering at a fixed intrinsic size and
    # letting CSS overflow:hidden crop whatever doesn't fit.
    PLOTLY_CONFIG = {
        'responsive': True,
        'displayModeBar': False,  # optional: hide the floating toolbar so it doesn't overlap card headers
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Date filters from URL
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        # Apply date filters if provided
        ai_diseases = AIDisease.objects.all()
        other_crops = HumanDetectedDisease.objects.all()
        
        if start_date:
            ai_diseases = ai_diseases.filter(record_date__gte=start_date)
            other_crops = other_crops.filter(record_date__gte=start_date)
        if end_date:
            ai_diseases = ai_diseases.filter(record_date__lte=end_date)
            other_crops = other_crops.filter(record_date__lte=end_date)
        
        # Statistics
        context.update({
            'total_farms': Farm.objects.count(),
            'total_ai_diseases': ai_diseases.count(),
            'total_other_crops': other_crops.count(),
            'total_infected_crops': other_crops.filter(
                infection_percentage__gt=0
            ).count(),
            'avg_infection_rate': other_crops.filter(
                infection_percentage__gt=0
            ).aggregate(Avg('infection_percentage'))['infection_percentage__avg'] or 0,
        })
        
        # Generate charts
        context['disease_trend_chart'] = self.create_disease_trend_chart(ai_diseases)
        context['infection_distribution_chart'] = self.create_infection_distribution_chart(other_crops)
        context['top_crops_chart'] = self.create_top_crops_chart(ai_diseases)
        context['geographical_distribution_chart'] = self.create_geographical_distribution_chart()
        
        return context

    def _base_layout(self, **overrides):
        """
        Common layout kwargs shared by every chart.
        autosize=True (with no explicit width/height) tells Plotly to size
        itself to whatever container div it's rendered into, so it stays
        in sync with the .chart-container CSS instead of overriding it.
        """
        defaults = dict(
            autosize=True,
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(l=50, r=30, t=50, b=50),
        )
        defaults.update(overrides)
        return defaults

    def create_disease_trend_chart(self, queryset):
        # Monthly trend
        monthly_data = queryset.annotate(
            month=ExtractMonth('record_date'),
            year=ExtractYear('record_date')
        ).values('year', 'month').annotate(
            count=Count('id')
        ).order_by('year', 'month')
        
        if not monthly_data:
            return None
        
        months = [f"{item['year']}-{item['month']:02d}" for item in monthly_data]
        counts = [item['count'] for item in monthly_data]
        
        fig = go.Figure(data=go.Scatter(
            x=months,
            y=counts,
            mode='lines+markers',
            line=dict(color='#2E86AB', width=3),
            marker=dict(size=8),
            fill='tozeroy',
            fillcolor='rgba(46, 134, 171, 0.1)'
        ))
        
        fig.update_layout(self._base_layout(
            title='Disease Detection Trend',
            xaxis_title='Month',
            yaxis_title='Number of Cases',
            font=dict(family='Arial, sans-serif'),
        ))
        
        return opy.plot(fig, auto_open=False, output_type='div', config=self.PLOTLY_CONFIG)
    
    def create_infection_distribution_chart(self, queryset):
        # Infection percentage distribution
        bins = [0, 20, 40, 60, 80, 100]
        labels = ['0-20%', '21-40%', '41-60%', '61-80%', '81-100%']
        
        distribution = []
        for i in range(len(bins)-1):
            lower = bins[i]
            upper = bins[i+1] if i < len(bins)-1 else 100
            count = queryset.filter(
                infection_percentage__gte=lower,
                infection_percentage__lt=upper
            ).count()
            distribution.append(count)
        
        fig = go.Figure(data=go.Bar(
            x=labels,
            y=distribution,
            marker_color=['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#6B2737'],
            text=distribution,
            textposition='auto',
        ))
        
        fig.update_layout(self._base_layout(
            title='Infection Percentage Distribution',
            xaxis_title='Infection Range',
            yaxis_title='Number of Crops',
        ))
        
        return opy.plot(fig, auto_open=False, output_type='div', config=self.PLOTLY_CONFIG)
    
    def create_top_crops_chart(self, queryset):
        # Top 10 crops with most diseases
        top_crops = queryset.values('crop_name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        if not top_crops:
            return None
        
        crops = [item['crop_name'] for item in top_crops]
        counts = [item['count'] for item in top_crops]
        
        fig = go.Figure(data=go.Bar(
            x=counts,
            y=crops,
            orientation='h',
            marker_color='#2E86AB'
        ))
        
        # NOTE: the previous fixed height=400 here is what was clipping this
        # specific chart -- it forced the plot taller than the 320px
        # .chart-container, and overflow:hidden cropped the rest. Removed
        # in favor of autosize (from _base_layout) so it fits the container.
        fig.update_layout(self._base_layout(
            title='Top Crops by Disease Incidence',
            xaxis_title='Number of Cases',
            yaxis_title='Crop',
        ))
        
        return opy.plot(fig, auto_open=False, output_type='div', config=self.PLOTLY_CONFIG)
    
    def create_geographical_distribution_chart(self):
        # Get region distribution from AIDisease model (since Farm doesn't have region)
        # Combine data from both AIDisease and HumanDetectedDisease models for regions
        from django.db.models import Count, Q
        
        # Get regions from AIDisease
        ai_regions = AIDisease.objects.exclude(
            Q(region__isnull=True) | Q(region='')
        ).values('region').annotate(
            count=Count('id')
        )
        
        # Get regions from HumanDetectedDisease
        other_regions = HumanDetectedDisease.objects.exclude(
            Q(region__isnull=True) | Q(region='')
        ).values('region').annotate(
            count=Count('id')
        )
        
        # Combine the data
        region_data = {}
        
        # Process AI Disease regions
        for item in ai_regions:
            region = item['region']
            count = item['count']
            if region in region_data:
                region_data[region] += count
            else:
                region_data[region] = count
        
        # Process HumanDetectedDisease regions
        for item in other_regions:
            region = item['region']
            count = item['count']
            if region in region_data:
                region_data[region] += count
            else:
                region_data[region] = count
        
        if not region_data:
            # Fallback: Use county if no regions
            return self.create_county_distribution_chart()
        
        # Sort regions by count
        sorted_regions = sorted(region_data.items(), key=lambda x: x[1], reverse=True)
        regions = [item[0] for item in sorted_regions[:10]]  # Top 10 regions
        counts = [item[1] for item in sorted_regions[:10]]
        
        fig = go.Figure(data=go.Pie(
            labels=regions,
            values=counts,
            hole=0.4,
            marker=dict(colors=['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#6B2737',
                                '#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#6B2737'])
        ))
        
        fig.update_layout(self._base_layout(
            title='Data Distribution by Region',
        ))
        
        return opy.plot(fig, auto_open=False, output_type='div', config=self.PLOTLY_CONFIG)

    def create_county_distribution_chart(self):
        """Fallback chart using county data"""
        from django.db.models import Count, Q
        
        # Get counties from AIDisease
        ai_counties = AIDisease.objects.exclude(
            Q(county__isnull=True) | Q(county='')
        ).values('county').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        if not ai_counties:
            # Try HumanDetectedDisease counties
            other_counties = HumanDetectedDisease.objects.exclude(
                Q(county__isnull=True) | Q(county='')
            ).values('county').annotate(
                count=Count('id')
            ).order_by('-count')[:10]
            
            if not other_counties:
                return None
            
            counties = [item['county'] for item in other_counties]
            counts = [item['count'] for item in other_counties]
        else:
            counties = [item['county'] for item in ai_counties]
            counts = [item['count'] for item in ai_counties]
        
        fig = go.Figure(data=go.Bar(
            x=counties,
            y=counts,
            marker_color='#2E86AB'
        ))
        
        fig.update_layout(self._base_layout(
            title='Data Distribution by County',
            xaxis_title='County',
            yaxis_title='Number of Records',
        ))
        
        return opy.plot(fig, auto_open=False, output_type='div', config=self.PLOTLY_CONFIG)
    
class CropAnalyticsView(TemplateView):
    template_name = 'analytics/crop_analytics.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        crop_name = self.request.GET.get('crop_name')
        
        if not crop_name:
            # Get all unique crops
            ai_crops = AIDisease.objects.values_list('crop_name', flat=True).distinct()
            other_crops = HumanDetectedDisease.objects.values_list('crop_name', flat=True).distinct()
            all_crops = sorted(set(list(ai_crops) + list(other_crops)))
            context['all_crops'] = all_crops
            return context
        
        # Filter data for specific crop
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        ai_diseases = AIDisease.objects.filter(crop_name=crop_name)
        other_crops = HumanDetectedDisease.objects.filter(crop_name=crop_name)
        
        if start_date:
            ai_diseases = ai_diseases.filter(record_date__gte=start_date)
            other_crops = other_crops.filter(record_date__gte=start_date)
        if end_date:
            ai_diseases = ai_diseases.filter(record_date__lte=end_date)
            other_crops = other_crops.filter(record_date__lte=end_date)
        
        # Statistics for this crop
        context.update({
            'selected_crop': crop_name,
            'total_ai_cases': ai_diseases.count(),
            'total_other_cases': other_crops.count(),
            'avg_infection_rate': other_crops.aggregate(
                Avg('infection_percentage')
            )['infection_percentage__avg'] or 0,
            'most_common_farm': ai_diseases.values('farm__farm_name').annotate(
                count=Count('id')
            ).order_by('-count').first(),
            'top_diseases': ai_diseases.values('original_disease').annotate(
                count=Count('id')
            ).order_by('-count')[:5],
        })
        
        # Generate crop-specific charts
        context['crop_trend_chart'] = self.create_crop_trend_chart(ai_diseases, other_crops)
        context['crop_diseases_chart'] = self.create_crop_diseases_chart(ai_diseases)
        context['crop_infection_chart'] = self.create_crop_infection_chart(other_crops)
        context['crop_geographic_chart'] = self.create_crop_geographic_chart(ai_diseases)
        
        return context
    
    def create_crop_trend_chart(self, ai_diseases, other_crops):
        # Combine data from both models
        ai_monthly = ai_diseases.annotate(
            month=ExtractMonth('record_date'),
            year=ExtractYear('record_date')
        ).values('year', 'month').annotate(
            count=Count('id')
        ).order_by('year', 'month')
        
        other_monthly = other_crops.annotate(
            month=ExtractMonth('record_date'),
            year=ExtractYear('record_date')
        ).values('year', 'month').annotate(
            count=Count('id')
        ).order_by('year', 'month')
        
        fig = go.Figure()
        
        # Add AI Disease trace
        if ai_monthly:
            ai_months = [f"{item['year']}-{item['month']:02d}" for item in ai_monthly]
            ai_counts = [item['count'] for item in ai_monthly]
            fig.add_trace(go.Scatter(
                x=ai_months,
                y=ai_counts,
                mode='lines+markers',
                name='AI Detected Diseases',
                line=dict(color='#2E86AB', width=3)
            ))
        
        # Add Other Crops trace
        if other_monthly:
            other_months = [f"{item['year']}-{item['month']:02d}" for item in other_monthly]
            other_counts = [item['count'] for item in other_monthly]
            fig.add_trace(go.Scatter(
                x=other_months,
                y=other_counts,
                mode='lines+markers',
                name='Other Crops Reports',
                line=dict(color='#A23B72', width=3)
            ))
        
        fig.update_layout(
            title='Monthly Trend for Selected Crop',
            xaxis_title='Month',
            yaxis_title='Number of Records',
            plot_bgcolor='white',
            paper_bgcolor='white',
            hovermode='x unified'
        )
        
        return opy.plot(fig, auto_open=False, output_type='div')
    
    def create_crop_diseases_chart(self, queryset):
        diseases = queryset.exclude(
            Q(original_disease__isnull=True) | Q(original_disease='')
        ).values('original_disease').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        if not diseases:
            return None
        
        disease_names = [item['original_disease'] for item in diseases]
        counts = [item['count'] for item in diseases]
        
        fig = go.Figure(data=go.Bar(
            x=disease_names,
            y=counts,
            marker_color='#2E86AB'
        ))
        
        fig.update_layout(
            title='Top Diseases for This Crop',
            xaxis_title='Disease',
            yaxis_title='Number of Cases',
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        
        return opy.plot(fig, auto_open=False, output_type='div')
    
    def create_crop_infection_chart(self, queryset):
        # Infection rate over time
        monthly_infection = queryset.filter(
            infection_percentage__gt=0
        ).annotate(
            month=ExtractMonth('record_date'),
            year=ExtractYear('record_date')
        ).values('year', 'month').annotate(
            avg_infection=Avg('infection_percentage')
        ).order_by('year', 'month')
        
        if not monthly_infection:
            return None
        
        months = [f"{item['year']}-{item['month']:02d}" for item in monthly_infection]
        infections = [item['avg_infection'] for item in monthly_infection]
        
        fig = go.Figure(data=go.Scatter(
            x=months,
            y=infections,
            mode='lines+markers',
            line=dict(color='#C73E1D', width=3),
            fill='tozeroy',
            fillcolor='rgba(199, 62, 29, 0.1)'
        ))
        
        fig.update_layout(
            title='Average Infection Rate Over Time',
            xaxis_title='Month',
            yaxis_title='Infection Percentage',
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        
        return opy.plot(fig, auto_open=False, output_type='div')
    
    def create_crop_geographic_chart(self, queryset):
        # Geographic distribution
        regions = queryset.exclude(
            Q(region__isnull=True) | Q(region='')
        ).values('region').annotate(
            count=Count('id')
        ).order_by('-count')
        
        if not regions:
            return None
        
        region_names = [item['region'] for item in regions]
        counts = [item['count'] for item in regions]
        
        fig = go.Figure(data=go.Bar(
            x=region_names,
            y=counts,
            marker_color='#6B2737'
        ))
        
        fig.update_layout(
            title='Geographic Distribution',
            xaxis_title='Region',
            yaxis_title='Number of Cases',
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        
        return opy.plot(fig, auto_open=False, output_type='div')


class AIDiseaseListView(FilterView):
    model = AIDisease
    template_name = 'analytics/ai_disease_list.html'
    filterset_class = AIDiseaseFilter
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # Apply additional filters if needed
        return queryset.select_related('farm').order_by('-record_date')


# Update your HumanDetectedDiseaseListView in views.py
class HumanDetectedDiseaseListView(FilterView):
    model = HumanDetectedDisease
    template_name = 'analytics/other_crop_list.html'
    filterset_class = HumanDetectedDiseaseFilter
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.select_related('farm').order_by('-record_date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        
        # Get unique crops count
        unique_crops = queryset.values('crop_name').distinct().count()
        
        # Get unique farms count
        unique_farms = queryset.values('farm').distinct().count()
        
        # Calculate average infection rate
        avg_infection = queryset.filter(
            infection_percentage__isnull=False
        ).aggregate(Avg('infection_percentage'))['infection_percentage__avg'] or 0
        
        # Get top crops for sidebar
        top_crops = queryset.values('crop_name').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        context.update({
            'unique_crops_count': unique_crops,
            'unique_farms_count': unique_farms,
            'avg_infection_rate': avg_infection,
            'top_crops': top_crops,
        })
        
        return context


# Update FarmListView in views.py
class FarmListView(FilterView):
    model = Farm
    template_name = 'analytics/farm_list.html'
    filterset_class = FarmFilter
    paginate_by = 20
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.order_by('farm_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = self.get_queryset()
        
        # Calculate active farms count
        active_farms_count = queryset.filter(deleted_at__isnull=True).count()
        
        # Calculate average reports per farm
        total_farms = queryset.count()
        total_reports = 0
        for farm in queryset:
            total_reports += farm.aidisease_set.count() + farm.HumanDetectedDisease_set.count()
        
        avg_reports_per_farm = total_reports / total_farms if total_farms > 0 else 0
        
        # Get recent farms (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_farms_count = queryset.filter(
            created_date__gte=thirty_days_ago
        ).count()
        
        # Get top active farms
        from django.db.models import Count
        top_active_farms = Farm.objects.annotate(
            total_reports=Count('aidisease') + Count('othercrop')
        ).filter(
            total_reports__gt=0
        ).order_by('-total_reports')[:5]
        
        context.update({
            'active_farms_count': active_farms_count,
            'avg_reports_per_farm': avg_reports_per_farm,
            'recent_farms_count': recent_farms_count,
            'top_active_farms': top_active_farms,
        })
        
        return context

class TimeSeriesAnalyticsView(TemplateView):
    template_name = 'analytics/time_series.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get time period from URL
        period = self.request.GET.get('period', 'monthly')  # daily, weekly, monthly, yearly
        crop_name = self.request.GET.get('crop_name')
        
        # Filter querysets
        ai_diseases = AIDisease.objects.all()
        other_crops = HumanDetectedDisease.objects.all()
        
        if crop_name:
            ai_diseases = ai_diseases.filter(crop_name=crop_name)
            other_crops = other_crops.filter(crop_name=crop_name)
        
        # Generate time series data
        context['ai_time_series_chart'] = self.create_time_series_chart(
            ai_diseases, period, 'AI Disease Detections', '#2E86AB'
        )
        context['other_time_series_chart'] = self.create_time_series_chart(
            other_crops, period, 'Other Crops Reports', '#A23B72'
        )
        context['combined_time_series_chart'] = self.create_combined_time_series_chart(
            ai_diseases, other_crops, period
        )
        
        return context
    
    def create_time_series_chart(self, queryset, period, title, color):
        if period == 'daily':
            data = queryset.values('record_date').annotate(
                count=Count('id')
            ).order_by('record_date')
            x = [item['record_date'].strftime('%Y-%m-%d') for item in data]
        elif period == 'monthly':
            data = queryset.annotate(
                month=ExtractMonth('record_date'),
                year=ExtractYear('record_date')
            ).values('year', 'month').annotate(
                count=Count('id')
            ).order_by('year', 'month')
            x = [f"{item['year']}-{item['month']:02d}" for item in data]
        elif period == 'yearly':
            data = queryset.annotate(
                year=ExtractYear('record_date')
            ).values('year').annotate(
                count=Count('id')
            ).order_by('year')
            x = [str(item['year']) for item in data]
        else:  # weekly
            # Simplified weekly grouping
            data = queryset.extra({
                'week': "EXTRACT(WEEK FROM record_date)",
                'year': "EXTRACT(YEAR FROM record_date)"
            }).values('year', 'week').annotate(
                count=Count('id')
            ).order_by('year', 'week')
            x = [f"{item['year']}-W{item['week']:02d}" for item in data]
        
        y = [item['count'] for item in data]
        
        fig = go.Figure(data=go.Scatter(
            x=x,
            y=y,
            mode='lines+markers',
            line=dict(color=color, width=3),
            marker=dict(size=6),
            fill='tozeroy',
            fillcolor=f'rgba{self.hex_to_rgb(color) + (0.1,)}'
        ))
        
        fig.update_layout(
            title=f'{title} - {period.capitalize()}',
            xaxis_title='Time',
            yaxis_title='Count',
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        
        return opy.plot(fig, auto_open=False, output_type='div')
    
    def create_combined_time_series_chart(self, ai_queryset, other_queryset, period):
        fig = go.Figure()
        
        # Add AI Diseases trace
        if period == 'monthly':
            ai_data = ai_queryset.annotate(
                month=ExtractMonth('record_date'),
                year=ExtractYear('record_date')
            ).values('year', 'month').annotate(
                count=Count('id')
            ).order_by('year', 'month')
            x = [f"{item['year']}-{item['month']:02d}" for item in ai_data]
            ai_y = [item['count'] for item in ai_data]
            
            other_data = other_queryset.annotate(
                month=ExtractMonth('record_date'),
                year=ExtractYear('record_date')
            ).values('year', 'month').annotate(
                count=Count('id')
            ).order_by('year', 'month')
            other_y = [item['count'] for item in other_data]
        
        fig.add_trace(go.Scatter(
            x=x,
            y=ai_y,
            mode='lines+markers',
            name='AI Diseases',
            line=dict(color='#2E86AB', width=3)
        ))
        
        fig.add_trace(go.Scatter(
            x=x,
            y=other_y,
            mode='lines+markers',
            name='Other Crops Reports',
            line=dict(color='#A23B72', width=3)
        ))
        
        fig.update_layout(
            title=f'Combined Time Series - {period.capitalize()}',
            xaxis_title='Time',
            yaxis_title='Count',
            plot_bgcolor='white',
            paper_bgcolor='white',
            hovermode='x unified'
        )
        
        return opy.plot(fig, auto_open=False, output_type='div')
    
    @staticmethod
    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    

def visualizations_view(request):
    """Main view for the visualizations page"""
    
    try:
        # Get summary statistics for the cards
        summary_stats = get_summary_statistics()
        
        # Get initial chart data
        chart_data = get_chart_data(aggregation='daily')
        
        # Get regional and category data
        regional_data = get_regional_data()
        category_data = get_category_distribution()
        
        context = {
            'summary_stats': summary_stats,
            'chart_data': json.dumps(chart_data),
            'regional_data': json.dumps(regional_data),
            'category_data': json.dumps(category_data),
        }
        
        return render(request, 'analytics/visualizations.html', context)
    
    except Exception as e:
        print(f"Error in visualizations_view: {e}")
        # Return with empty data if there's an error
        context = {
            'summary_stats': {
                'total': 0,
                'total_ai_diseases': 0,
                'total_other_crops': 0,
                'total_farms': Farm.objects.count(),
                'average': 0,
                'max': 0,
                'min': 0,
                'date_range_days': 0,
            },
            'chart_data': json.dumps({
                'labels': [],
                'datasets': [
                    {
                        'label': 'AI Diseases',
                        'data': [],
                        'borderColor': 'rgba(54, 162, 235, 1)',
                        'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                    },
                    {
                        'label': 'Other Crops',
                        'data': [],
                        'borderColor': 'rgba(255, 99, 132, 1)',
                        'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                    }
                ]
            }),
            'regional_data': json.dumps({'labels': [], 'data': []}),
            'category_data': json.dumps({'labels': [], 'data': []}),
        }
        return render(request, 'analytics/visualizations.html', context)
    
def visualization_data_api(request):
    """API endpoint to fetch visualization data based on filters"""
    try:
        aggregation = request.GET.get('aggregation', 'daily')
        data_type = request.GET.get('data_type', 'all')
        chart_type = request.GET.get('type', 'main')
        
        print(f"API called with: aggregation={aggregation}, data_type={data_type}, chart_type={chart_type}")
        
        if chart_type == 'regional':
            data = get_regional_data()
            print(f"Regional data: {data}")  # Debug
            return JsonResponse(data)
        elif chart_type == 'category':
            data = get_category_distribution()
            print(f"Category data: {data}")  # Debug
            return JsonResponse(data)
        
        # For main chart
        chart_data = get_chart_data(aggregation)
        print(f"Main chart data - labels: {len(chart_data['labels'])}, datasets: {len(chart_data['datasets'])}")  # Debug
        
        # Filter based on data_type if needed
        if data_type == 'ai_diseases' and len(chart_data['datasets']) > 0:
            chart_data['datasets'] = [chart_data['datasets'][0]]
        elif data_type == 'other_crops' and len(chart_data['datasets']) > 1:
            chart_data['datasets'] = [chart_data['datasets'][1]]
        
        return JsonResponse(chart_data)
    
    except Exception as e:
        print(f"Error in API: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'error': str(e),
            'labels': [],
            'datasets': []
        }, status=500)

def get_summary_statistics():
    """Calculate summary statistics for the dashboard cards"""
    
    # Total records across all models
    total_ai_diseases = AIDisease.objects.count()
    total_other_crops = HumanDetectedDisease.objects.count()
    total_farms = Farm.objects.count()
    
    # Get date range
    earliest_date = AIDisease.objects.order_by('record_date').first()
    latest_date = AIDisease.objects.order_by('-record_date').first()
    
    if earliest_date and latest_date:
        date_range = (latest_date.record_date - earliest_date.record_date).days
    else:
        date_range = 0
    
    # Calculate average infections from HumanDetectedDisease model
    avg_infection = HumanDetectedDisease.objects.filter(
        infection_percentage__isnull=False
    ).aggregate(Avg('infection_percentage'))['infection_percentage__avg'] or 0
    
    # Get top disease counts
    top_diseases = AIDisease.objects.values('changed_disease')\
        .annotate(count=Count('id'))\
        .order_by('-count')[:5]
    
    return {
        'total': total_ai_diseases + total_other_crops,
        'total_ai_diseases': total_ai_diseases,
        'total_other_crops': total_other_crops,
        'total_farms': total_farms,
        'average': avg_infection,
        'max': HumanDetectedDisease.objects.aggregate(Max('infection_percentage'))['infection_percentage__max'] or 0,
        'min': HumanDetectedDisease.objects.aggregate(Min('infection_percentage'))['infection_percentage__min'] or 0,
        'date_range_days': date_range,
        'top_diseases': list(top_diseases),
    }

def get_chart_data(aggregation='daily'):
    """Generate chart data based on aggregation period"""
    
    # Get date range (last 30 days by default)
    end_date = timezone.now().date()
    
    if aggregation == 'daily':
        start_date = end_date - timedelta(days=30)
    elif aggregation == 'weekly':
        start_date = end_date - timedelta(weeks=12)
    elif aggregation == 'monthly':
        start_date = end_date - timedelta(days=365)
    elif aggregation == 'quarterly':
        start_date = end_date - timedelta(days=730)
    else:
        start_date = end_date - timedelta(days=30)
    
    # Query data from both models
    ai_diseases_data = get_ai_diseases_timeline(start_date, end_date, aggregation)
    other_crops_data = get_other_crops_timeline(start_date, end_date, aggregation)
    
    # Get all unique dates/periods and sort them
    all_periods = sorted(set(list(ai_diseases_data.keys()) + list(other_crops_data.keys())))
    
    # If no data at all, create some sample data for the last 30 days
    if not all_periods:
        if aggregation == 'daily':
            all_periods = [(end_date - timedelta(days=x)).strftime('%Y-%m-%d') for x in range(30, -1, -1)]
        elif aggregation == 'weekly':
            all_periods = [(end_date - timedelta(weeks=x)).strftime('%Y-W%W') for x in range(12, -1, -1)]
        elif aggregation == 'monthly':
            all_periods = [(end_date - timedelta(days=30*x)).strftime('%Y-%m') for x in range(12, -1, -1)]
        else:
            all_periods = ['No Data']
    
    # Prepare chart data structure for Chart.js
    chart_data = {
        'labels': all_periods,
        'datasets': [
            {
                'label': 'AI Diseases',
                'data': [ai_diseases_data.get(period, 0) for period in all_periods],
                'borderColor': 'rgba(54, 162, 235, 1)',
                'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                'tension': 0.1,
                'fill': True,
            },
            {
                'label': 'Other Crops',
                'data': [other_crops_data.get(period, 0) for period in all_periods],
                'borderColor': 'rgba(255, 99, 132, 1)',
                'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                'tension': 0.1,
                'fill': True,
            }
        ]
    }
    
    return chart_data

def get_ai_diseases_timeline(start_date, end_date, aggregation):
    """Get timeline data for AI Diseases"""
    
    try:
        diseases = AIDisease.objects.filter(
            record_date__gte=start_date,
            record_date__lte=end_date
        ).order_by('record_date')
        
        if not diseases.exists():
            return {}
        
        if aggregation == 'daily':
            result = diseases.values('record_date')\
                .annotate(count=Count('id'))\
                .order_by('record_date')
            
            return {item['record_date'].strftime('%Y-%m-%d'): item['count'] for item in result}
        
        elif aggregation == 'weekly':
            result = defaultdict(int)
            for disease in diseases:
                week = disease.record_date.strftime('%Y-W%W')
                result[week] += 1
            return dict(sorted(result.items()))
        
        elif aggregation == 'monthly':
            result = defaultdict(int)
            for disease in diseases:
                month = disease.record_date.strftime('%Y-%m')
                result[month] += 1
            return dict(sorted(result.items()))
        
        elif aggregation == 'quarterly':
            result = defaultdict(int)
            for disease in diseases:
                quarter = f"{disease.record_date.year}-Q{(disease.record_date.month-1)//3 + 1}"
                result[quarter] += 1
            return dict(sorted(result.items()))
        
        return {}
    
    except Exception as e:
        print(f"Error in get_ai_diseases_timeline: {e}")
        return {}

def get_other_crops_timeline(start_date, end_date, aggregation):
    """Get timeline data for Other Crops"""
    
    try:
        crops = HumanDetectedDisease.objects.filter(
            record_date__gte=start_date,
            record_date__lte=end_date
        ).order_by('record_date')
        
        if not crops.exists():
            return {}
        
        if aggregation == 'daily':
            result = crops.values('record_date')\
                .annotate(count=Count('id'))\
                .order_by('record_date')
            
            return {item['record_date'].strftime('%Y-%m-%d'): item['count'] for item in result}
        
        elif aggregation == 'weekly':
            result = defaultdict(int)
            for crop in crops:
                week = crop.record_date.strftime('%Y-W%W')
                result[week] += 1
            return dict(sorted(result.items()))
        
        elif aggregation == 'monthly':
            result = defaultdict(int)
            for crop in crops:
                month = crop.record_date.strftime('%Y-%m')
                result[month] += 1
            return dict(sorted(result.items()))
        
        elif aggregation == 'quarterly':
            result = defaultdict(int)
            for crop in crops:
                quarter = f"{crop.record_date.year}-Q{(crop.record_date.month-1)//3 + 1}"
                result[quarter] += 1
            return dict(sorted(result.items()))
        
        return {}
    
    except Exception as e:
        print(f"Error in get_other_crops_timeline: {e}")
        return {}
    
def get_other_crops_timeline(start_date, end_date, aggregation):
    """Get timeline data for Other Crops"""
    
    crops = HumanDetectedDisease.objects.filter(
        record_date__gte=start_date,
        record_date__lte=end_date
    ).order_by('record_date')
    
    if aggregation == 'daily':
        result = crops.values('record_date')\
            .annotate(count=Count('id'))\
            .order_by('record_date')
        
        return {item['record_date'].strftime('%Y-%m-%d'): item['count'] for item in result}
    
    elif aggregation == 'weekly':
        result = defaultdict(int)
        for crop in crops:
            week = crop.record_date.strftime('%Y-W%W')
            result[week] += 1
        return dict(sorted(result.items()))
    
    elif aggregation == 'monthly':
        result = defaultdict(int)
        for crop in crops:
            month = crop.record_date.strftime('%Y-%m')
            result[month] += 1
        return dict(sorted(result.items()))
    
    elif aggregation == 'quarterly':
        result = defaultdict(int)
        for crop in crops:
            quarter = f"{crop.record_date.year}-Q{(crop.record_date.month-1)//3 + 1}"
            result[quarter] += 1
        return dict(sorted(result.items()))
    
    return {}


def get_regional_data():
    """Get regional comparison data"""
    
    try:
        # Group by state/region from AIDisease
        ai_disease_regions = AIDisease.objects.exclude(
            state__isnull=True
        ).exclude(
            state=''
        ).values('state').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Group by state/region from HumanDetectedDisease
        other_crops_regions = HumanDetectedDisease.objects.exclude(
            state__isnull=True
        ).exclude(
            state=''
        ).values('state').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Combine region data
        regions = {}
        for item in ai_disease_regions:
            if item['state']:
                regions[item['state']] = regions.get(item['state'], 0) + item['count']
        
        for item in other_crops_regions:
            if item['state']:
                regions[item['state']] = regions.get(item['state'], 0) + item['count']
        
        # If no regions found, use county as fallback
        if not regions:
            # Try with county
            ai_counties = AIDisease.objects.exclude(
                county__isnull=True
            ).exclude(
                county=''
            ).values('county').annotate(
                count=Count('id')
            ).order_by('-count')[:5]
            
            for item in ai_counties:
                if item['county']:
                    regions[item['county']] = regions.get(item['county'], 0) + item['count']
        
        # Sort and take top 5
        if regions:
            top_regions = dict(sorted(regions.items(), key=lambda x: x[1], reverse=True)[:5])
        else:
            # Return empty data if no regions found
            return {
                'labels': [],
                'data': []
            }
        
        return {
            'labels': list(top_regions.keys()),
            'data': list(top_regions.values())
        }
    
    except Exception as e:
        print(f"Error in get_regional_data: {e}")
        return {
            'labels': [],
            'data': []
        }

def get_category_distribution():
    """Get category distribution data"""
    
    try:
        # Get crop name distribution from AI Diseases
        ai_crops = AIDisease.objects.exclude(
            crop_name__isnull=True
        ).exclude(
            crop_name=''
        ).values('crop_name').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        # Get crop name distribution from Other Crops
        other_crops = HumanDetectedDisease.objects.exclude(
            crop_name__isnull=True
        ).exclude(
            crop_name=''
        ).values('crop_name').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        # Combine crop data
        crops = {}
        for item in ai_crops:
            if item['crop_name']:
                crops[item['crop_name']] = crops.get(item['crop_name'], 0) + item['count']
        
        for item in other_crops:
            if item['crop_name']:
                crops[item['crop_name']] = crops.get(item['crop_name'], 0) + item['count']
        
        # Sort and take top 5
        if crops:
            top_crops = dict(sorted(crops.items(), key=lambda x: x[1], reverse=True)[:5])
        else:
            # Return empty data if no crops found
            return {
                'labels': [],
                'data': []
            }
        
        return {
            'labels': list(top_crops.keys()),
            'data': list(top_crops.values())
        }
    
    except Exception as e:
        print(f"Error in get_category_distribution: {e}")
        return {
            'labels': [],
            'data': []
        }
    
from django.db.models import Max, Min

def disease_dashboard(request):
    form = DiseaseFilterForm(request.GET or None)
    context = {
        'form': form,
        'chart_data': None,
        'summary_stats': None
    }
    
    if form.is_valid():
        try:
            district = form.cleaned_data['district']
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            selected_disease = form.cleaned_data.get('disease')
             
            # Filter AIDisease records by state
            ai_records = AIDisease.objects.filter(
                state=district,  # State is in AIDisease model
                record_date__range=[start_date, end_date]
            )
            
            # Filter HumanDetectedDisease records by state
            other_records = HumanDetectedDisease.objects.filter(
                state=district,  # State is in HumanDetectedDisease model
                record_date__range=[start_date, end_date]
            )
            
            # Get farms in this district (optional, for reference)
            farms_in_district = Farm.objects.filter(
                id__in=list(ai_records.values_list('farm_id', flat=True)) + 
                        list(other_records.values_list('farm_id', flat=True))
            ).distinct()
            
            # Apply disease filter if selected
            if selected_disease and selected_disease != '':
                ai_records = ai_records.filter(
                    Q(original_disease=selected_disease) |
                    Q(changed_disease=selected_disease) |
                    Q(other_diseases__icontains=selected_disease)
                )
                other_records = other_records.filter(
                    threats__contains=[selected_disease]
                )
            
            # Check if any records found
            if not ai_records.exists() and not other_records.exists():
                context['error'] = f"No records found for {district} in the selected date range"
                return render(request, 'analytics/disease_dashboard.html', context)
            
            # Generate summary statistics
            summary_stats = {
                'total_records': ai_records.count() + other_records.count(),
                'ai_records': ai_records.count(),
                'other_records': other_records.count(),
                'unique_diseases': ai_records.exclude(original_disease__isnull=True).values('original_disease').distinct().count(),
                'unique_crops': AIDisease.objects.filter(id__in=ai_records).values('crop_name').distinct().count() +
                               HumanDetectedDisease.objects.filter(id__in=other_records).values('crop_name').distinct().count(),
                'affected_farms': farms_in_district.count(),
                'locations': list(ai_records.values('location_name').distinct()) + 
                            list(other_records.values('location_name').distinct()),
            }
            
            # Generate chart data
            chart_data = generate_chart_data(ai_records, other_records, start_date, end_date, district)
            
            context.update({
                'chart_data': json.dumps(chart_data),
                'summary_stats': summary_stats,
                'district': district,
                'start_date': start_date,
                'end_date': end_date,
                'selected_disease': selected_disease
            })
            
        except Exception as e:
            context['error'] = f"Error processing data: {str(e)}"
    
    return render(request, 'analytics/disease_dashboard.html', context)

def generate_chart_data(ai_records, other_records, start_date, end_date, district):
    """Generate properly formatted chart data for Chart.js"""
    
    # 1. Monthly Trends Chart Data
    ai_monthly = ai_records.annotate(
        month=TruncMonth('record_date')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')
    
    other_monthly = other_records.annotate(
        month=TruncMonth('record_date')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')
    
    # Create a dictionary of monthly counts
    monthly_data = defaultdict(lambda: {'ai': 0, 'other': 0, 'total': 0})
    
    # Process AI records
    for item in ai_monthly:
        if item['month']:  # Check if month exists
            month_str = item['month'].strftime('%Y-%m')
            monthly_data[month_str]['ai'] = item['count']
            monthly_data[month_str]['total'] += item['count']
    
    # Process Other records
    for item in other_monthly:
        if item['month']:  # Check if month exists
            month_str = item['month'].strftime('%Y-%m')
            monthly_data[month_str]['other'] = item['count']
            monthly_data[month_str]['total'] += item['count']
    
    # Sort months chronologically
    sorted_months = sorted(monthly_data.keys())
    
    # 2. Disease Distribution Chart Data
    disease_distribution = list(ai_records.exclude(
        original_disease__isnull=True
    ).exclude(
        original_disease=''
    ).values('original_disease').annotate(
        count=Count('id')
    ).order_by('-count')[:10])  # Top 10 diseases
    
    # Process threats from HumanDetectedDisease for additional distribution
    threat_counts = defaultdict(int)
    for record in other_records.exclude(threats__isnull=True):
        if record.threats and isinstance(record.threats, list):
            for threat in record.threats:
                threat_counts[threat] += 1
    
    # Combine with disease distribution
    all_threats = []
    for disease in disease_distribution:
        all_threats.append({
            'name': disease['original_disease'],
            'count': disease['count'],
            'type': 'disease'
        })
    
    for threat, count in threat_counts.items():
        all_threats.append({
            'name': threat,
            'count': count,
            'type': 'threat'
        })
    
    # Sort by count and take top 10
    all_threats.sort(key=lambda x: x['count'], reverse=True)
    top_threats = all_threats[:10]
    
    # 3. Crop Distribution Chart Data
    ai_crops = list(ai_records.values('crop_name').annotate(
        count=Count('id')
    ).exclude(
        crop_name__isnull=True
    ).exclude(
        crop_name=''
    ).order_by('-count'))
    
    # Add crops from HumanDetectedDisease
    other_crops = list(other_records.values('crop_name').annotate(
        count=Count('id')
    ).exclude(
        crop_name__isnull=True
    ).exclude(
        crop_name=''
    ).order_by('-count'))
    
    # Combine crop data
    crop_dict = defaultdict(int)
    for crop in ai_crops:
        if crop['crop_name']:
            crop_dict[crop['crop_name']] += crop['count']
    for crop in other_crops:
        if crop['crop_name']:
            crop_dict[crop['crop_name']] += crop['count']
    
    # Format for chart
    crop_data = [{'crop': k, 'count': v} for k, v in crop_dict.items()]
    crop_data.sort(key=lambda x: x['count'], reverse=True)
    top_crops = crop_data[:10]
    
    # 4. Location-based distribution (county/region level)
    location_distribution = list(ai_records.values('county').annotate(
        count=Count('id')
    ).exclude(
        county__isnull=True
    ).exclude(
        county=''
    ).order_by('-count'))
    
    # 5. Severity/Infection Rate Data (if available)
    severity_data = []
    if other_records.filter(infection_percentage__isnull=False).exists():
        severity_ranges = [
            {'range': '0-25%', 'min': 0, 'max': 25},
            {'range': '26-50%', 'min': 26, 'max': 50},
            {'range': '51-75%', 'min': 51, 'max': 75},
            {'range': '76-100%', 'min': 76, 'max': 100},
        ]
        
        for range_item in severity_ranges:
            count = other_records.filter(
                infection_percentage__gte=range_item['min'],
                infection_percentage__lte=range_item['max']
            ).count()
            if count > 0:
                severity_data.append({
                    'range': range_item['range'],
                    'count': count
                })
    
    return {
        # Monthly trends data
        'month_labels': sorted_months,
        'ai_trends': [monthly_data[month]['ai'] for month in sorted_months],
        'other_trends': [monthly_data[month]['other'] for month in sorted_months],
        'total_trends': [monthly_data[month]['total'] for month in sorted_months],
        
        # Disease/Threat distribution data
        'threat_labels': [t['name'] for t in top_threats],
        'threat_counts': [t['count'] for t in top_threats],
        'threat_types': [t['type'] for t in top_threats],
        
        # Crop distribution data
        'crop_labels': [c['crop'] for c in top_crops],
        'crop_counts': [c['count'] for c in top_crops],
        
        # Location distribution data
        'location_labels': [l['county'] for l in location_distribution[:10]],
        'location_counts': [l['count'] for l in location_distribution[:10]],
        
        # Severity data
        'severity_labels': [s['range'] for s in severity_data],
        'severity_counts': [s['count'] for s in severity_data],
        
        # Raw data for additional processing
        'raw_data': {
            'total_ai': ai_records.count(),
            'total_other': other_records.count(),
            'unique_diseases': len(disease_distribution),
            'unique_threats': len(threat_counts),
            'district': district,
            'date_range': f"{start_date} to {end_date}"
        }
    }



def compare_dashboards(request):
    """Show two side-by-side dashboards for comparison"""
    form1 = DiseaseFilterForm(request.GET or None, prefix='period1')
    form2 = DiseaseFilterForm(request.GET or None, prefix='period2')

    if request.GET:
        print("GET data:", request.GET)
        print("Form1 valid:", form1.is_valid())
        print("Form2 valid:", form2.is_valid())
        if not form1.is_valid():
            print("Form1 errors:", form1.errors)
        if not form2.is_valid():
            print("Form2 errors:", form2.errors)
    
    context = {
        'form1': form1,
        'form2': form2,
        'period1_data': None,
        'period2_data': None,
        'comparison_stats': None
    }
    
    if form1.is_valid() and form2.is_valid():
        # Get filter values for period 1
        district1 = form1.cleaned_data['district']
        start_date1 = form1.cleaned_data['start_date']
        end_date1 = form1.cleaned_data['end_date']
        disease1 = form1.cleaned_data.get('disease')
        
        # Get filter values for period 2
        district2 = form2.cleaned_data['district']
        start_date2 = form2.cleaned_data['start_date']
        end_date2 = form2.cleaned_data['end_date']
        disease2 = form2.cleaned_data.get('disease')
        
        # Process Period 1 Data
        period1_data = process_period_data(district1, start_date1, end_date1, disease1)
        
        # Process Period 2 Data
        period2_data = process_period_data(district2, start_date2, end_date2, disease2)
        
        # Calculate comparison statistics
        comparison_stats = calculate_comparison_stats(period1_data, period2_data)
        
        context.update({
             
            'period1_data': json.dumps(period1_data, cls=DjangoJSONEncoder),
            'period2_data': json.dumps(period2_data, cls=DjangoJSONEncoder),
            'comparison_stats': comparison_stats
        })
    
    return render(request, 'analytics/compare_dashboards.html', context)

def process_period_data(district, start_date, end_date, selected_disease=None):
    """Helper function to process data for a single period"""
    
    # Get farms in district
    ai_records = AIDisease.objects.filter(
    state=district,
    record_date__range=[start_date, end_date]
    )

    other_records = HumanDetectedDisease.objects.filter(
        state=district,
        record_date__range=[start_date, end_date]
    )
    
    # Apply disease filter if selected
    if selected_disease:
        ai_records = ai_records.filter(
            Q(original_disease=selected_disease) |
            Q(changed_disease=selected_disease) |
            Q(other_diseases__icontains=selected_disease)
        )
        other_records = other_records.filter(
            Q(threats__contains=[selected_disease])
        )
    
    # Monthly trends
    monthly_trends = list(ai_records.annotate(
        month=TruncMonth('record_date')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month'))
    
    # Disease distribution
    disease_distribution = list(ai_records.values('original_disease').annotate(
        count=Count('id')
    ).order_by('-count')[:10])
    
    # Crop distribution
    crop_distribution = list(ai_records.values('crop_name').annotate(
        count=Count('id')
    ).order_by('-count'))
    
    # Summary statistics
    summary = {
        'total_ai_records': ai_records.count(),
        'total_other_records': other_records.count(),
        'total_records': ai_records.count() + other_records.count(),
        'unique_diseases': ai_records.values('original_disease').distinct().count(),
        'unique_crops': ai_records.values('crop_name').distinct().count(),
    }
    
    return {
        'monthly_trends': monthly_trends,
        'disease_distribution': disease_distribution,
        'crop_distribution': crop_distribution,
        'summary': summary,
        'district': district,
        'start_date': str(start_date),
        'end_date': str(end_date)
    }

def calculate_comparison_stats(period1_data, period2_data):
    """Calculate comparison statistics between two periods"""
    
    stats = {
        'record_difference': period2_data['summary']['total_records'] - period1_data['summary']['total_records'],
        'record_percent_change': 0,
        'disease_difference': period2_data['summary']['unique_diseases'] - period1_data['summary']['unique_diseases'],
        'most_changed_disease': None
    }
    
    # Calculate percent change
    if period1_data['summary']['total_records'] > 0:
        stats['record_percent_change'] = (
            (period2_data['summary']['total_records'] - period1_data['summary']['total_records']) / 
            period1_data['summary']['total_records'] * 100
        )
    
    # Find most changed disease
    disease_changes = {}
    for d1 in period1_data['disease_distribution']:
        disease_changes[d1['original_disease']] = -d1['count']
    
    for d2 in period2_data['disease_distribution']:
        if d2['original_disease'] in disease_changes:
            disease_changes[d2['original_disease']] += d2['count']
        else:
            disease_changes[d2['original_disease']] = d2['count']
    
    if disease_changes:
        stats['most_changed_disease'] = max(disease_changes, key=disease_changes.get)
        stats['most_changed_value'] = disease_changes[stats['most_changed_disease']]
    
    return stats

def disease_map(request):
    form = DiseaseFilterForm(request.GET or None)
    context = {
        'form': form,
        'map': None,
        'stats': None
    }
    
    if form.is_valid():
        try:
            district = form.cleaned_data['district']
            start_date = form.cleaned_data['start_date']
            end_date = form.cleaned_data['end_date']
            selected_disease = form.cleaned_data.get('disease')
            
            # CORRECTED: Filter records directly by state (not through Farm)
            # Get AI Disease records with coordinates
            ai_records = AIDisease.objects.filter(
                state=district,
                record_date__range=[start_date, end_date],
                lat__isnull=False,
                lng__isnull=False
            )
            
            # Get Other Crop records with coordinates
            other_records = HumanDetectedDisease.objects.filter(
                state=district,
                record_date__range=[start_date, end_date],
                lat__isnull=False,
                lng__isnull=False
            )
            
            # Apply disease filter if selected
            if selected_disease and selected_disease != '':
                ai_records = ai_records.filter(
                    Q(original_disease=selected_disease) |
                    Q(changed_disease=selected_disease) |
                    Q(other_diseases__icontains=selected_disease)
                )
                other_records = other_records.filter(
                    threats__contains=[selected_disease]
                )
            
            # Check if any records found
            total_records = ai_records.count() + other_records.count()
            if total_records == 0:
                context['error'] = f"No records with coordinates found for {district} in the selected date range"
                return render(request, 'analytics/disease_map.html', context)
            
            # Create base map centered on Malawi
            m = folium.Map(
                location=[-13.9669, 33.7873],  # Malawi center
                zoom_start=7,
                tiles='OpenStreetMap'
            )
            
            # Add fullscreen button
            folium.plugins.Fullscreen().add_to(m)
             
            from django.contrib.staticfiles import finders
            geo_json_path = finders.find('assets/geoBoundaries-MWI-ADM0_simplified.geojson')
            
            if geo_json_path:
                with open(geo_json_path, 'r', encoding='utf-8') as f:
                    malawi_geojson = json.load(f)
                
                # Add GeoJSON layer
                folium.GeoJson(
                    malawi_geojson,
                    name='Malawi Boundary',
                    style_function=lambda x: {
                        'fillColor': 'transparent',
                        'color': 'blue',
                        'weight': 2,
                        'dashArray': '5, 5'
                    }
                ).add_to(m)
            
            # Prepare heatmap data
            heat_data = []
            
            # Create feature groups for different layers
            ai_group = folium.FeatureGroup(name='AI Diseases')
            other_group = folium.FeatureGroup(name='Other Crop Threats')
            
            # Process AI Disease records
            for record in ai_records:
                if record.lat and record.lng:
                    lat = float(record.lat)
                    lng = float(record.lng)
                    
                    # Add to heatmap (weighted by occurrence)
                    heat_data.append([lat, lng, 1])
                    
                    # Create popup content
                    popup_content = f"""
                    <div style="min-width: 200px;">
                        <h6 style="color: #dc3545;">AI Disease Record</h6>
                        <b>Disease:</b> {record.original_disease or 'Unknown'}<br>
                        <b>Crop:</b> {record.crop_name}<br>
                        <b>Date:</b> {record.record_date}<br>
                        <b>Location:</b> {record.location_name or 'Unknown'}<br>
                        <b>County:</b> {record.county or 'Unknown'}<br>
                        <b>Changed Disease:</b> {record.changed_disease or 'None'}<br>
                        <b>Other Diseases:</b> {record.other_diseases or 'None'}<br>
                        <b>User ID:</b> {record.user_id}
                    </div>
                    """
                    
                    # Add marker
                    folium.Marker(
                        [lat, lng],
                        popup=folium.Popup(popup_content, max_width=300),
                        tooltip=f"AI Disease: {record.original_disease or 'Unknown'}",
                        icon=folium.Icon(color='red', icon='info-sign', prefix='glyphicon')
                    ).add_to(ai_group)
            
            # Process Other Crop records
            for record in other_records:
                if record.lat and record.lng:
                    lat = float(record.lat)
                    lng = float(record.lng)
                    
                    # Add to heatmap (weighted by occurrence)
                    heat_data.append([lat, lng, 1])
                    
                    # Format threats for display
                    threats_display = ', '.join(record.threats) if record.threats else 'None'
                    
                    # Create popup content
                    popup_content = f"""
                    <div style="min-width: 200px;">
                        <h6 style="color: #ffc107;">Other Crop Threat</h6>
                        <b>Crop:</b> {record.crop_name}<br>
                        <b>Threats:</b> {threats_display}<br>
                        <b>Infection:</b> {record.infection_percentage or 'Unknown'}%<br>
                        <b>Date:</b> {record.record_date}<br>
                        <b>Location:</b> {record.location_name or 'Unknown'}<br>
                        <b>County:</b> {record.county or 'Unknown'}<br>
                        <b>Comment:</b> {record.comment or 'None'}<br>
                        <b>User ID:</b> {record.user_id}
                    </div>
                    """
                    
                    # Add marker
                    folium.Marker(
                        [lat, lng],
                        popup=folium.Popup(popup_content, max_width=300),
                        tooltip=f"Threat: {threats_display[:50]}...",
                        icon=folium.Icon(color='orange', icon='leaf', prefix='glyphicon')
                    ).add_to(other_group)
            
            # Add heatmap layer
            if heat_data:
                HeatMap(
                    heat_data,
                    name='Heat Map',
                    min_opacity=0.3,
                    max_zoom=10,
                    radius=15,
                    blur=10
                ).add_to(m)
            
            # Add feature groups to map
            ai_group.add_to(m)
            other_group.add_to(m)
            
            # Add layer control
            folium.LayerControl().add_to(m)
            
            # Add click functionality to show coordinates
            m.add_child(folium.LatLngPopup())
            
            # Calculate statistics
            context['stats'] = {
                'total_points': len(heat_data),
                'ai_count': ai_records.count(),
                'other_count': other_records.count(),
                'district': district,
                'start_date': start_date,
                'end_date': end_date,
                'unique_diseases': ai_records.values('original_disease').distinct().count(),
                'unique_threats': other_records.exclude(threats__isnull=True).count()
            }
            
            # Save map as HTML
            context['map'] = m._repr_html_()
            
        except Exception as e:
            context['error'] = f"Error generating map: {str(e)}"
    
    return render(request, 'analytics/disease_map.html', context)


def forecast_disease_trends(disease_name, district, years=2, forecast_months=12):
    """Forecast disease trends for next year based on past data"""
    
    try:
        # Calculate date range
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=365*years)
        
        # CORRECTED: Filter records directly by state, not through Farm
        # Get AI Disease records
        ai_records = AIDisease.objects.filter(
            state=district,  # Direct filter on state
            record_date__range=[start_date, end_date]
        ).filter(
            Q(original_disease__icontains=disease_name) |
            Q(changed_disease__icontains=disease_name) |
            Q(other_diseases__icontains=disease_name)
        )

        # Get HumanDetectedDisease records (threats)
        other_records = HumanDetectedDisease.objects.filter(
            state=district,
            record_date__range=[start_date, end_date]
        )
        
        # Combine both data sources
        all_records = []
        
        # Process AI records
        for record in ai_records:
            all_records.append({
                'date': record.record_date,
                'type': 'disease',
                'name': record.original_disease or disease_name
            })
         
        # Process Other records with JSON filtering
        for record in other_records:
            if record.threats and disease_name in record.threats:
                all_records.append({
                    'date': record.record_date,
                    'type': 'threat',
                    'name': disease_name
                })
        
        if not all_records:
            return {
                'error': f"No data found for '{disease_name}' in {district} for the past {years} years"
            }
        
        # Convert to DataFrame
        df = pd.DataFrame(all_records)
        df['date'] = pd.to_datetime(df['date'])
        df['month'] = df['date'].dt.to_period('M')
        
        # Monthly aggregation
        monthly_counts = df.groupby('month').size().reset_index(name='count')
        monthly_counts['month_str'] = monthly_counts['month'].astype(str)
        monthly_counts = monthly_counts.sort_values('month')
        
        # Prepare data for forecasting
        dates = monthly_counts['month_str'].tolist()
        counts = monthly_counts['count'].tolist()
        
        if len(counts) < 4:  # Need at least 4 data points
            return {
                'error': f"Insufficient data points ({len(counts)}). Need at least 4 months of data."
            }
        
        # Create time series features
        X = np.array(range(len(counts))).reshape(-1, 1)
        y = np.array(counts)
        
        # Try different models and pick the best
        models = {
            'linear': LinearRegression(),
            'polynomial_2': make_pipeline(PolynomialFeatures(2), LinearRegression()),
            'polynomial_3': make_pipeline(PolynomialFeatures(3), LinearRegression())
        }
        
        best_model = None
        best_score = -np.inf
        best_model_name = None
        
        for name, model in models.items():
            try:
                model.fit(X, y)
                score = model.score(X, y)
                if score > best_score:
                    best_score = score
                    best_model = model
                    best_model_name = name
            except:
                continue
        
        if best_model is None:
            # Fallback to simple linear regression
            best_model = LinearRegression()
            best_model.fit(X, y)
            best_model_name = 'linear'
            best_score = best_model.score(X, y)
        
        # Forecast future months
        last_idx = len(counts) - 1
        future_indices = np.array(range(last_idx + 1, last_idx + forecast_months + 1)).reshape(-1, 1)
        predictions = best_model.predict(future_indices)
        
        # Ensure predictions aren't negative
        predictions = np.maximum(predictions, 0)
        
        # Generate future dates
        last_date = pd.to_datetime(dates[-1])
        future_dates = []
        for i in range(1, forecast_months + 1):
            # Add month safely handling year rollover
            if last_date.month == 12:
                future_date = last_date.replace(year=last_date.year + 1, month=1)
            else:
                future_date = last_date.replace(month=last_date.month + 1)
            future_dates.append(future_date.strftime('%Y-%m'))
            last_date = future_date
        
        # Calculate seasonal patterns if enough data
        seasonal_pattern = None
        if len(counts) >= 12:
            # Simple seasonal index (average by month)
            df['month_num'] = df['date'].dt.month
            seasonal_avg = df.groupby('month_num')['count'].mean().to_dict()
            seasonal_pattern = seasonal_avg
        
        # Calculate trend statistics
        trend_coefficient = best_model.named_steps['linearregression'].coef_[0] if best_model_name.startswith('polynomial') else best_model.coef_[0]
        
        # Calculate confidence intervals (simplified)
        residuals = y - best_model.predict(X)
        std_residuals = np.std(residuals)
        
        forecast_data = {
            'metadata': {
                'disease': disease_name,
                'district': district,
                'data_points': len(counts),
                'model_used': best_model_name,
                'model_accuracy': round(best_score * 100, 2),
                'trend_direction': 'increasing' if trend_coefficient > 0 else 'decreasing',
                'trend_strength': abs(round(trend_coefficient, 3))
            },
            'historical': {
                'dates': dates,
                'counts': counts,
                'total_cases': sum(counts),
                'avg_monthly': round(np.mean(counts), 1),
                'max_monthly': max(counts),
                'min_monthly': min(counts)
            },
            'forecast': {
                'dates': future_dates,
                'counts': [max(0, round(p, 1)) for p in predictions],
                'total_predicted': round(sum(predictions), 1),
                'avg_predicted': round(np.mean(predictions), 1),
                'confidence_intervals': {
                    'lower': [max(0, round(p - 2*std_residuals, 1)) for p in predictions],
                    'upper': [round(p + 2*std_residuals, 1) for p in predictions]
                }
            },
            'seasonal_pattern': seasonal_pattern,
            'recommendations': generate_recommendations(trend_coefficient, best_score, counts, predictions)
        }
        
        return forecast_data
        
    except Exception as e:
        return {'error': f"Forecasting error: {str(e)}"}

def generate_recommendations(trend_coefficient, model_accuracy, historical_counts, predictions):
    """Generate recommendations based on forecast"""
    recommendations = []
    
    # Trend-based recommendations
    if trend_coefficient > 0.5:
        recommendations.append("⚠️ **ALERT**: Strong increasing trend detected. Increase monitoring and prepare intervention measures.")
    elif trend_coefficient > 0.1:
        recommendations.append("📈 Moderate increasing trend. Maintain regular monitoring.")
    elif trend_coefficient < -0.5:
        recommendations.append("✅ Strong decreasing trend. Current control measures seem effective.")
    elif trend_coefficient < -0.1:
        recommendations.append("📉 Slight decreasing trend. Continue current practices.")
    else:
        recommendations.append("➡️ Stable trend. Maintain standard monitoring procedures.")
    
    # Peak prediction
    if len(predictions) > 0 and np.max(predictions) > max(historical_counts) * 1.5:
        recommendations.append("⚠️ Forecast suggests potential outbreak peak higher than historical maximum. Prepare for increased cases.")
    
    # Model confidence
    if model_accuracy < 50:
        recommendations.append("📊 Low model confidence due to limited or erratic data. Consider collecting more data points.")
    elif model_accuracy > 80:
        recommendations.append("📊 High confidence in forecast. Use for planning purposes.")
    
    # Seasonal recommendations
    if len(predictions) >= 3 and np.max(predictions[-3:]) > np.mean(predictions) * 1.3:
        recommendations.append("📅 Upward trend in coming months. Prepare for seasonal increase.")
    
    return recommendations

def forecasting_dashboard(request):
    """View for disease forecasting"""
    form = DiseaseFilterForm(request.GET or None)
    context = {
        'form': form,
        'forecast_data': None,
        'error': None
    }
    
    if form.is_valid():
        district = form.cleaned_data['district']
        selected_disease = form.cleaned_data.get('disease')
        
        if selected_disease and selected_disease != '':
            forecast_data = forecast_disease_trends(selected_disease, district)
            
            if forecast_data and 'error' in forecast_data:
                context['error'] = forecast_data['error']
            else:
                context['forecast_data'] = json.dumps(forecast_data, cls=DjangoJSONEncoder)
                context['forecast_data_dict'] = forecast_data
        else:
            context['error'] = "Please select a disease to forecast"
    
    return render(request, 'analytics/forecasting.html', context)