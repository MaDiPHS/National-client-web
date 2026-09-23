# analytics/filters.py
import django_filters
from django import forms
from .models import Farm, AIDisease, HumanDetectedDisease
from django.utils import timezone

class DateRangeFilter(django_filters.FilterSet):
    start_date = django_filters.DateFilter(
        field_name='record_date', 
        lookup_expr='gte',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    end_date = django_filters.DateFilter(
        field_name='record_date', 
        lookup_expr='lte',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    class Meta:
        model = None
        fields = []


class AIDiseaseFilter(DateRangeFilter):
    crop_name = django_filters.CharFilter(
        lookup_expr='icontains',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Filter by crop...'})
    )
    farm = django_filters.ModelChoiceFilter(
        queryset=Farm.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = AIDisease
        fields = ['crop_name', 'farm']

# class DateRangeFilter(django_filters.FilterSet):
#     start_date = django_filters.DateFilter(
#         field_name='record_date', 
#         lookup_expr='gte',
#         widget=forms.DateInput(attrs={
#             'type': 'date', 
#             'class': 'form-control',
#             'placeholder': 'Start Date'
#         })
#     )
#     end_date = django_filters.DateFilter(
#         field_name='record_date', 
#         lookup_expr='lte',
#         widget=forms.DateInput(attrs={
#             'type': 'date', 
#             'class': 'form-control',
#             'placeholder': 'End Date'
#         })
#     )
    
#     class Meta:
#         model = None
#         fields = []


class HumanDetectedDiseaseFilter(DateRangeFilter):
    crop_name = django_filters.CharFilter(
        lookup_expr='icontains',
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Crop name...'
        })
    )
    farm = django_filters.ModelChoiceFilter(
        queryset=Farm.objects.all().order_by('farm_name'),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    infection_percentage = django_filters.RangeFilter(
        field_name='infection_percentage',
        widget=django_filters.widgets.RangeWidget(attrs={
            'class': 'form-control', 
            'placeholder': 'Infection %'
        })
    )
    county = django_filters.CharFilter(
        lookup_expr='icontains',
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'County...'
        })
    )
    state = django_filters.CharFilter(
        lookup_expr='icontains',
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'State...'
        })
    )
    region = django_filters.CharFilter(
        lookup_expr='icontains',
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Region...'
        })
    )
    
    class Meta:
        model = HumanDetectedDisease
        fields = ['crop_name', 'farm', 'county', 'state', 'region']


class FarmFilter(django_filters.FilterSet):
    farm_name = django_filters.CharFilter(
        lookup_expr='icontains',
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Farm name...'
        })
    )
    farm_id = django_filters.NumberFilter(
        widget=forms.NumberInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Farm ID...'
        })
    )
    county = django_filters.CharFilter(
        lookup_expr='icontains',
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'County...'
        })
    )
    state = django_filters.CharFilter(
        lookup_expr='icontains',
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'State...'
        })
    )
    region = django_filters.CharFilter(
        lookup_expr='icontains',
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Region...'
        })
    )
    
    class Meta:
        model = Farm
        fields = ['farm_name', 'farm_id', 'county', 'state', 'region']