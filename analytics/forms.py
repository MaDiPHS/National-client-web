# forms.py
import csv
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from analytics.models import AIDisease, HumanDetectedDisease

class CSVUploadForm(forms.Form):
    csv_file = forms.FileField(
        label=_('CSV File'),
        help_text=_('Upload a CSV file with farm data. Maximum file size is 10MB.'),
        widget=forms.FileInput(attrs={
            'accept': '.csv',
            'class': 'block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100'
        })
    )
    
    def clean_csv_file(self):
        csv_file = self.cleaned_data['csv_file']
        
        # Check file extension
        if not csv_file.name.endswith('.csv'):
            raise ValidationError('Please upload a CSV file with .csv extension.')
        
        # Check file size (10MB max)
        max_size = 100 * 1024 * 1024
        if csv_file.size > max_size:
            raise ValidationError(f'File size should not exceed 10MB. Your file is {csv_file.size / 1024 / 1024:.1f}MB.')
        
        # Check if file is empty
        if csv_file.size == 0:
            raise ValidationError('The uploaded file is empty.')
        
        # Validate CSV structure by checking headers
        try:
            content = csv_file.read().decode('utf-8')
            csv_file.seek(0)  # Reset file pointer
            
            # Check if it has expected headers
            reader = csv.reader(content.splitlines())
            headers = next(reader, [])
            
            expected_headers = ['farm_id', 'farm_name', 'lat', 'lng', 'created_at', 'updated_at', 'deleted_at']
            
            if not headers:
                raise ValidationError('CSV file appears to be empty or has no headers.')
            
            # Check for required headers
            missing_headers = [h for h in expected_headers if h not in headers]
            if missing_headers:
                raise ValidationError(f'Missing required columns: {", ".join(missing_headers)}')
        
        except UnicodeDecodeError:
            raise ValidationError('File encoding is not valid UTF-8. Please save your CSV as UTF-8.')
        except Exception as e:
            raise ValidationError(f'Error reading CSV file: {str(e)}')
        
        return csv_file

class AIDiseaseCSVUploadForm(forms.Form):
    csv_file = forms.FileField(
        label=_('CSV File'),
        help_text=_('Upload a CSV file with AI Disease data. Maximum file size is 100MB.'),
        widget=forms.FileInput(attrs={
            'accept': '.csv',
            'class': 'file-input'
        })
    )
    
    def clean_csv_file(self):
        csv_file = self.cleaned_data['csv_file']
        
        # Check file extension
        if not csv_file.name.endswith('.csv'):
            raise ValidationError('Please upload a CSV file with .csv extension.')
        
        # Check file size (10MB max)
        max_size = 100 * 1024 * 1024  # 10MB
        if csv_file.size > max_size:
            raise ValidationError(f'File size should not exceed 100MB. Your file is {csv_file.size / 1024 / 1024:.1f}MB.')
        
        if csv_file.size == 0:
            raise ValidationError('The uploaded file is empty.')
        
        # Validate CSV structure
        try:
            content = csv_file.read().decode('utf-8')
            csv_file.seek(0)  # Reset file pointer
            
            reader = csv.reader(content.splitlines())
            headers = next(reader, [])
            
            # AIDisease expected headers
            expected_headers = [
                'ai_disease_id', 'user_id', 'lat', 'lng', 'farm_id', 
                'crop_name', 'created_at', 'language', 'original_disease',
                'changed_disease', 'other_diseases', 'country_code', 
                'county', 'state', 'region', 'location_name'
            ]
            
            if not headers:
                raise ValidationError('CSV file appears to be empty or has no headers.')
            
            # Convert headers to lowercase for comparison
            headers_lower = [h.lower().strip() for h in headers]
            expected_lower = [h.lower().strip() for h in expected_headers]
            
            # Check for required headers
            missing_headers = [expected_headers[i] for i, h in enumerate(expected_lower) if h not in headers_lower]
            if missing_headers:
                raise ValidationError(f'Missing required columns: {", ".join(missing_headers)}')
            
            # Also check if created_at exists (we need it for date extraction)
            if 'created_at' not in headers_lower:
                raise ValidationError('CSV must contain a created_at column for date extraction.')
        
        except UnicodeDecodeError:
            raise ValidationError('File encoding is not valid UTF-8. Please save your CSV as UTF-8.')
        except Exception as e:
            raise ValidationError(f'Error reading CSV file: {str(e)}')
        
        return csv_file

# In your forms.py
class HumanDetectedDiseaseCSVUploadForm(forms.Form):
    csv_file = forms.FileField(
        label=_('CSV File'),
        help_text=_('Upload a CSV file with Other Crop data. Maximum file size is 10MB.'),
        widget=forms.FileInput(attrs={
            'accept': '.csv',
            'class': 'file-input'
        })
    )
    
    def clean_csv_file(self):
        csv_file = self.cleaned_data['csv_file']
        
        # Check file extension
        if not csv_file.name.endswith('.csv'):
            raise ValidationError('Please upload a CSV file with .csv extension.')
        
        # Check file size (10MB max)
        max_size = 100 * 1024 * 1024  # 10MB
        if csv_file.size > max_size:
            raise ValidationError(f'File size should not exceed 100MB. Your file is {csv_file.size / 1024 / 1024:.1f}MB.')
        
        if csv_file.size == 0:
            raise ValidationError('The uploaded file is empty.')
        
        # Validate CSV structure
        try:
            content = csv_file.read().decode('utf-8')
            csv_file.seek(0)  # Reset file pointer
            
            reader = csv.reader(content.splitlines())
            headers = next(reader, [])
            
            # HumanDetectedDisease expected headers
            expected_headers = [
                'user_id', 'crop_name', 'description', 'collected_at', 
                'created_at', 'updated_at', 'lat', 'lng', 'farm_id',
                'threats', 'comment', 'infection_percentage', 'country_code',
                'county', 'state', 'region', 'location_name'
            ]
            
            if not headers:
                raise ValidationError('CSV file appears to be empty or has no headers.')
            
            # Convert headers to lowercase for comparison
            headers_lower = [h.lower().strip() for h in headers]
            expected_lower = [h.lower().strip() for h in expected_headers]
            
            # Check for required headers (user_id and crop_name are required)
            required_headers = ['user_id', 'crop_name']
            missing_required = [h for h in required_headers if h not in headers_lower]
            if missing_required:
                raise ValidationError(f'Missing required columns: {", ".join(missing_required)}')
            
            # Check if at least one date field exists for date extraction
            date_fields = ['collected_at', 'created_at', 'updated_at']
            if not any(field in headers_lower for field in date_fields):
                raise ValidationError('CSV must contain at least one of these date fields: collected_at, created_at, or updated_at')
        
        except UnicodeDecodeError:
            raise ValidationError('File encoding is not valid UTF-8. Please save your CSV as UTF-8.')
        except Exception as e:
            raise ValidationError(f'Error reading CSV file: {str(e)}')
        
        return csv_file
    
class DiseaseFilterForm(forms.Form):
    
    DISTRICT_CHOICES = [

    # Northern Region
    ('Chitipa', 'Chitipa'),
    ('Karonga', 'Karonga'),
    ('Likoma', 'Likoma'),
    ('Mzimba', 'Mzimba'),
    ('Nkhata Bay', 'Nkhata Bay'),
    ('Rumphi', 'Rumphi'),

    # Central Region
    ('Dedza', 'Dedza'),
    ('Dowa', 'Dowa'),
    ('Kasungu', 'Kasungu'),
    ('Lilongwe', 'Lilongwe'),
    ('Mchinji', 'Mchinji'),
    ('Nkhotakota', 'Nkhotakota'),
    ('Ntcheu', 'Ntcheu'),
    ('Ntchisi', 'Ntchisi'),
    ('Salima', 'Salima'),

    # Southern Region
    ('Balaka', 'Balaka'),
    ('Blantyre', 'Blantyre'),
    ('Chikwawa', 'Chikwawa'),
    ('Chiradzulu', 'Chiradzulu'),
    ('Machinga', 'Machinga'),
    ('Mangochi', 'Mangochi'),
    ('Mulanje', 'Mulanje'),
    ('Mwanza', 'Mwanza'),
    ('Neno', 'Neno'),
    ('Nsanje', 'Nsanje'),
    ('Phalombe', 'Phalombe'),
    ('Thyolo', 'Thyolo'),
    ('Zomba', 'Zomba'),
]
    
    district = forms.ChoiceField(choices=DISTRICT_CHOICES, required=True,widget=forms.Select(attrs={'class':'form-select'}))
    start_date = forms.DateField(widget=forms.DateInput(attrs={
            'type':'date',
            'class':'form-control'
        }))
    end_date = forms.DateField(widget=forms.DateInput(attrs={
            'type':'date',
            'class':'form-control'
        }))
    
    # Dynamic disease choices based on selected district
    disease = forms.ChoiceField(choices=[], required=False,widget=forms.Select(attrs={'class':'form-select'}))
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Get unique diseases/threats from both models
        ai_diseases = AIDisease.objects.exclude(original_disease__isnull=True).values_list('original_disease', flat=True).distinct()
        other_threats = HumanDetectedDisease.objects.exclude(threats__isnull=True).values_list('threats', flat=True)
        
        # Flatten threats list
        threat_list = []
        for threat in other_threats:
            if threat:
                threat_list.extend(threat)
        
        disease_choices = [('', 'All Diseases/Threats')] + [(d, d) for d in set(list(ai_diseases) + threat_list)]
        self.fields['disease'].choices = disease_choices