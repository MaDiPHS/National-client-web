# admin.py
import csv
import io
import json
from django.contrib import admin, messages
from django.shortcuts import render, redirect
from django.urls import path
from django.db import transaction
from django.utils import timezone
from datetime import datetime, time
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display
from unfold.forms import AdminPasswordChangeForm, UserCreationForm, UserChangeForm
from .models import Farm, AIDisease, HumanDetectedDisease
from .forms import CSVUploadForm
from django.utils.html import format_html

# admin.py - Update FarmAdmin class

@admin.register(Farm)
class FarmAdmin(ModelAdmin):
    list_display = [
        'display_farm_id',
        'display_farm_name',
        'display_coordinates',
        'display_created_date',
        'display_actions',
    ]
    
    search_fields = ('farm_name', 'farm_id')
    list_filter = ('created_date',)
    readonly_fields = ('id', 'created_date', 'updated_date')
    list_per_page = 50
    
    # Add this line to use the custom template
    change_list_template = 'admin/analytics/farm/change_list.html'
    
    actions = ['export_as_csv_action']
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-csv/', self.admin_site.admin_view(self.upload_csv), name='analytics_farm_upload_csv'),
        ]
        return custom_urls + urls
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_upload_button'] = True
        extra_context['upload_csv_url'] = 'analytics_farm_upload_csv'
        return super().changelist_view(request, extra_context=extra_context)
    
    @display(description='Farm ID', ordering='farm_id')
    def display_farm_id(self, obj):
        return f"#{obj.farm_id}"
    
    @display(description='Farm Name', ordering='farm_name')
    def display_farm_name(self, obj):
        return obj.farm_name
    
    @display(description='Coordinates')
    def display_coordinates(self, obj):
        if obj.lat and obj.lng:
            return f"({obj.lat}, {obj.lng})"
        return "No coordinates"
    
    @display(description='Created Date', ordering='created_date')
    def display_created_date(self, obj):
        return obj.created_date.strftime("%Y-%m-%d")
    
    @display(description='Actions')
    def display_actions(self, obj):
        # Use proper HTML with Unfold classes
        from django.utils.html import format_html
        from django.urls import reverse
        
        edit_url = reverse('admin:analytics_farm_change', args=[obj.id])
        delete_url = reverse('admin:analytics_farm_delete', args=[obj.id])
        
        return format_html(
            '''
            <div class="flex gap-2">
                <a href="{}" class="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md bg-blue-100 text-blue-800 hover:bg-blue-200">
                    <svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                    </svg>
                    Edit
                </a>
                <a href="{}" class="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md bg-red-100 text-red-800 hover:bg-red-200">
                    <svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                    </svg>
                    Delete
                </a>
            </div>
            ''',
            edit_url,
            delete_url
        )
    

    def upload_csv(self, request):
        """Custom view for CSV upload"""
        if request.method == 'POST':
            form = CSVUploadForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = request.FILES['csv_file']
                
                # Try to decode the CSV file
                try:
                    data_set = csv_file.read().decode('UTF-8')
                except UnicodeDecodeError:
                    data_set = csv_file.read().decode('ISO-8859-1')
                
                io_string = io.StringIO(data_set)
                reader = csv.DictReader(io_string)
                
                farms_created = 0
                farms_updated = 0
                errors = []
                
                with transaction.atomic():
                    for row_num, row in enumerate(reader, start=2):
                        try:
                            # Clean and parse farm_id
                            farm_id_str = str(row.get('farm_id', '')).strip()
                            if not farm_id_str:
                                errors.append(f"Row {row_num}: farm_id is required")
                                continue
                            
                            try:
                                farm_id = int(float(farm_id_str))
                            except ValueError:
                                errors.append(f"Row {row_num}: Invalid farm_id '{farm_id_str}' - must be a number")
                                continue
                            
                            farm_name = row.get('farm_name', '').strip()
                            if not farm_name:
                                errors.append(f"Row {row_num}: farm_name is required")
                                continue
                            
                            # Parse coordinates
                            lat_str = row.get('lat', '').strip()
                            lng_str = row.get('lng', '').strip()
                            
                            lat = None
                            lng = None
                            
                            if lat_str:
                                try:
                                    lat = float(lat_str)
                                except ValueError:
                                    errors.append(f"Row {row_num}: Invalid latitude '{lat_str}'")
                                    continue
                            
                            if lng_str:
                                try:
                                    lng = float(lng_str)
                                except ValueError:
                                    errors.append(f"Row {row_num}: Invalid longitude '{lng_str}'")
                                    continue
                            
                            # Improved datetime parsing with timezone awareness
                            def parse_datetime_with_timezone(dt_str):
                                """Parse datetime and make it timezone-aware"""
                                if not dt_str or str(dt_str).strip().lower() in ['', 'null', 'none', 'nan']:
                                    return None
                                
                                dt_str = str(dt_str).strip()
                                
                                # Handle formats like "25:31.2" or "32:28.2"
                                if ':' in dt_str and '-' not in dt_str:
                                    # Time-only format like "25:31.2"
                                    parts = dt_str.split(':')
                                    try:
                                        if len(parts) == 2:
                                            # Format: "25:31.2"
                                            hours = int(parts[0])
                                            minutes_seconds = parts[1].split('.')
                                            minutes = int(minutes_seconds[0]) if minutes_seconds[0] else 0
                                            seconds = 0
                                            
                                            if len(minutes_seconds) > 1 and minutes_seconds[1]:
                                                # Convert decimal part to seconds
                                                decimal_part = minutes_seconds[1]
                                                if len(decimal_part) > 2:
                                                    decimal_part = decimal_part[:2]
                                                seconds = int((int(decimal_part) / 100) * 60)
                                            
                                            # Create a naive datetime
                                            naive_dt = datetime(2000, 1, 1, hours, minutes, seconds)
                                            # Make it timezone-aware
                                            return timezone.make_aware(naive_dt, timezone.get_current_timezone())
                                        
                                        elif len(parts) == 3:
                                            # Format: "25:31:20" or "25:31:20.5"
                                            hours = int(parts[0])
                                            minutes = int(parts[1])
                                            seconds_part = parts[2]
                                            
                                            if '.' in seconds_part:
                                                seconds = int(float(seconds_part))
                                            else:
                                                seconds = int(seconds_part)
                                            
                                            naive_dt = datetime(2000, 1, 1, hours, minutes, seconds)
                                            return timezone.make_aware(naive_dt, timezone.get_current_timezone())
                                    
                                    except (ValueError, IndexError) as e:
                                        print(f"Error parsing time '{dt_str}': {e}")
                                        return None
                                
                                else:
                                    # Try to parse full datetime formats
                                    formats_to_try = [
                                        '%Y-%m-%d %H:%M:%S.%f',
                                        '%Y-%m-%d %H:%M:%S',
                                        '%Y/%m/%d %H:%M:%S.%f',
                                        '%Y/%m/%d %H:%M:%S',
                                        '%d-%m-%Y %H:%M:%S.%f',
                                        '%d-%m-%Y %H:%M:%S',
                                        '%d/%m/%Y %H:%M:%S.%f',
                                        '%d/%m/%Y %H:%M:%S',
                                    ]
                                    
                                    for fmt in formats_to_try:
                                        try:
                                            naive_dt = datetime.strptime(dt_str, fmt)
                                            return timezone.make_aware(naive_dt, timezone.get_current_timezone())
                                        except ValueError:
                                            continue
                                
                                return None
                            
                            # Parse the datetime fields
                            created_at = parse_datetime_with_timezone(row.get('created_at'))
                            updated_at = parse_datetime_with_timezone(row.get('updated_at'))
                            deleted_at = parse_datetime_with_timezone(row.get('deleted_at'))
                            
                            # Update or create farm
                            farm, created = Farm.objects.update_or_create(
                                farm_id=farm_id,
                                defaults={
                                    'farm_name': farm_name,
                                    'lat': lat,
                                    'lng': lng,
                                    'created_at': created_at,
                                    'updated_at': updated_at,
                                    'deleted_at': deleted_at,
                                    'created_date': timezone.now().date(),
                                }
                            )
                            
                            if created:
                                farms_created += 1
                            else:
                                farms_updated += 1
                                
                        except Exception as e:
                            errors.append(f"Row {row_num}: {str(e)}")
                
                # Clear any previous errors
                if 'csv_upload_errors' in request.session:
                    del request.session['csv_upload_errors']
                
                # Prepare success message
                success_parts = []
                if farms_created:
                    success_parts.append(f'{farms_created} farms created')
                if farms_updated:
                    success_parts.append(f'{farms_updated} farms updated')
                
                if success_parts:
                    self.message_user(
                        request,
                        f'✅ Successfully processed CSV file. {", ".join(success_parts)}.',
                        messages.SUCCESS
                    )
                
                if errors:
                    self.message_user(
                        request,
                        f'⚠️ Completed with {len(errors)} errors.',
                        messages.WARNING
                    )
                    # Store only first 10 errors in session
                    request.session['csv_upload_errors'] = errors[:10]
                
                return redirect('admin:analytics_farm_changelist')
        else:
            form = CSVUploadForm()
        
        context = {
            **self.admin_site.each_context(request),
            'form': form,
            'opts': self.model._meta,
            'title': 'Upload Farm CSV',
            'subtitle': 'National Client - Farm Data Import',
        }
        return render(request, 'admin/csv_upload_form.html', context)

@admin.register(AIDisease)
class AIDiseaseAdmin(ModelAdmin):
    list_display = [
        'display_disease_id',
        'display_crop_name',
        'display_farm',
        'display_record_date',
        'display_actions',
    ]
    
    search_fields = ('crop_name','record_date', 'original_disease', 'ai_disease_id')
    list_filter = ('record_date', 'crop_name', 'country_code')
    list_per_page = 50
    raw_id_fields = ('farm',)
    
    # Add custom templates
    change_list_template = 'admin/analytics/aidisease/change_list.html'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-csv/', self.admin_site.admin_view(self.upload_csv), name='analytics_aidisease_upload_csv'),
            path('delete-by-date/', self.admin_site.admin_view(self.delete_by_date), name='analytics_aidisease_delete_by_date'),
        ]
        return custom_urls + urls
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_upload_button'] = True
        extra_context['upload_csv_url'] = 'analytics_aidisease_upload_csv'
        extra_context['delete_by_date_url'] = 'analytics_aidisease_delete_by_date'
        return super().changelist_view(request, extra_context=extra_context)
    
    @display(description='Disease ID', ordering='ai_disease_id')
    def display_disease_id(self, obj):
        return f"#{obj.ai_disease_id}"
    
    @display(description='Crop Name')
    def display_crop_name(self, obj):
        return obj.crop_name
    
    @display(description='Farm', ordering='farm__farm_name')
    def display_farm(self, obj):
        if obj.farm:
            return obj.farm.farm_name
        return "No farm"
    
    @display(description='Record Date', ordering='record_date')
    def display_record_date(self, obj):
        return obj.record_date.strftime("%Y-%m-%d")
    
    @display(description='Actions')
    def display_actions(self, obj):
        from django.urls import reverse
        edit_url = reverse('admin:analytics_aidisease_change', args=[obj.id])
        delete_url = reverse('admin:analytics_aidisease_delete', args=[obj.id])
        
        return format_html(
            '''
            <div class="flex gap-2">
                <a href="{}" class="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md bg-blue-100 text-blue-800 hover:bg-blue-200">
                    Edit
                </a>
                <a href="{}" class="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md bg-red-100 text-red-800 hover:bg-red-200">
                    Delete
                </a>
            </div>
            ''',
            edit_url,
            delete_url
        )
    
    def upload_csv(self, request):
        """Custom view for CSV upload - skips duplicates and continues processing"""
        from analytics.forms import AIDiseaseCSVUploadForm
        import traceback
        
        if request.method == 'POST':
            form = AIDiseaseCSVUploadForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = request.FILES['csv_file']
                
                # Try to decode the CSV file
                raw = csv_file.read()

                try:
                    data_set = raw.decode('utf-8')
                except UnicodeDecodeError:
                    data_set = raw.decode('ISO-8859-1')
                
                io_string = io.StringIO(data_set)

                try:
                    sample = data_set[:1000]
                    dialect = csv.Sniffer().sniff(sample)
                except:
                    dialect = 'excel'

                io_string.seek(0)
                reader = csv.DictReader(io_string, dialect=dialect)
                
                diseases_created = 0
                errors = []
                duplicates_skipped = 0
                date_counts = {}
                duplicate_ids = []  # Track duplicate IDs for reporting
                
                with transaction.atomic():
                    for row_num, row in enumerate(reader, start=2):
                        try:
                            # Clean and parse ai_disease_id
                            disease_id_str = str(row.get('ai_disease_id', '')).strip()
                            if not disease_id_str:
                                errors.append(f"Row {row_num}: ai_disease_id is required")
                                continue
                            
                            try:
                                ai_disease_id = int(float(disease_id_str))
                            except ValueError:
                                errors.append(f"Row {row_num}: Invalid ai_disease_id '{disease_id_str}'")
                                continue
                            
                            # Parse user_id
                            user_id_str = str(row.get('user_id', '')).strip()
                            if not user_id_str:
                                errors.append(f"Row {row_num}: user_id is required")
                                continue
                            
                            try:
                                user_id = int(float(user_id_str))
                            except ValueError:
                                errors.append(f"Row {row_num}: Invalid user_id '{user_id_str}'")
                                continue
                            
                            # Parse coordinates
                            lat = None
                            lng = None
                            lat_str = row.get('lat', '').strip()
                            lng_str = row.get('lng', '').strip()
                            
                            if lat_str:
                                try:
                                    lat = float(lat_str)
                                except ValueError:
                                    errors.append(f"Row {row_num}: Invalid latitude '{lat_str}'")
                                    continue
                            
                            if lng_str:
                                try:
                                    lng = float(lng_str)
                                except ValueError:
                                    errors.append(f"Row {row_num}: Invalid longitude '{lng_str}'")
                                    continue
                            
                            # Parse farm_id if provided
                            farm = None
                            farm_id_str = row.get('farm_id', '').strip()
                            if farm_id_str:
                                try:
                                    farm_id = int(float(farm_id_str))
                                    from analytics.models import Farm
                                    try:
                                        farm = Farm.objects.get(farm_id=farm_id)
                                    except Farm.DoesNotExist:
                                        errors.append(f"Row {row_num}: Farm with ID {farm_id} does not exist")
                                        continue
                                except ValueError:
                                    errors.append(f"Row {row_num}: Invalid farm_id '{farm_id_str}'")
                                    continue
                            
                            # Parse crop_name (required)
                            crop_name = row.get('crop_name', '').strip()
                            if not crop_name:
                                errors.append(f"Row {row_num}: crop_name is required")
                                continue
                            
                            # ===== FIXED: Parse created_at field to extract both date and time =====
                            created_at_value = row.get('created_at', '')
                            record_date = None
                            created_time = None
                            
                            if created_at_value and str(created_at_value).lower() not in ['', 'null', 'none', 'nan']:
                                raw_val = str(created_at_value).strip()
                                
                                # Try common datetime formats including those with microseconds
                                datetime_formats = [
                                    # ISO format with microseconds (your case)
                                    '%Y-%m-%d %H:%M:%S.%f',     # 2023-01-31 16:16:04.638972
                                    
                                    # ISO formats
                                    '%Y-%m-%d %H:%M:%S',        # 2023-01-31 16:16:04
                                    '%Y-%m-%d %H:%M',           # 2023-01-31 16:16
                                    '%Y-%m-%dT%H:%M:%S.%f',     # 2023-01-31T16:16:04.638972
                                    '%Y-%m-%dT%H:%M:%S',        # 2023-01-31T16:16:04
                                    
                                    # US formats (month/day/year)
                                    '%m/%d/%Y %I:%M:%S %p',     # 2/15/2023 7:36:56 AM
                                    '%m/%d/%Y %H:%M:%S',        # 2/15/2023 07:36:56
                                    '%m/%d/%Y %I:%M %p',        # 2/15/2023 7:36 AM
                                    '%m/%d/%Y %H:%M',           # 2/15/2023 07:36
                                    
                                    # European formats (day/month/year)
                                    '%d/%m/%Y %H:%M:%S',        # 15/2/2023 07:36:56
                                    '%d/%m/%Y %I:%M:%S %p',     # 15/2/2023 7:36:56 AM
                                    
                                    # With commas
                                    '%m/%d/%Y, %I:%M:%S %p',    # 2/15/2023, 7:36:56 AM
                                ]
                                
                                for fmt in datetime_formats:
                                    try:
                                        dt = datetime.strptime(raw_val, fmt)
                                        record_date = dt.date()
                                        created_time = dt.time()
                                        print(f"Matched format '{fmt}': date={record_date}, time={created_time}")
                                        break
                                    except ValueError:
                                        continue
                                
                                # If no datetime format matched, try Excel serial number
                                if not record_date:
                                    import re
                                    if re.match(r'^\d+(\.\d+)?$', raw_val):
                                        try:
                                            excel_serial = float(raw_val)
                                            if excel_serial > 60:
                                                excel_serial -= 1
                                            excel_epoch = datetime(1899, 12, 31)
                                            dt = excel_epoch + timedelta(days=excel_serial)
                                            record_date = dt.date()
                                            created_time = dt.time()
                                            print(f"Parsed Excel serial to: date={record_date}, time={created_time}")
                                        except ValueError:
                                            pass
                                
                                # If still no date, try time-only formats
                                if not created_time:
                                    time_formats = [
                                        '%H:%M:%S.%f',    # 16:16:04.638972
                                        '%H:%M:%S',       # 16:16:04
                                        '%H:%M',          # 16:16
                                        '%I:%M:%S %p',    # 7:36:56 AM
                                        '%I:%M %p',       # 7:36 AM
                                        '%M:%S.%f',       # 05:14.0
                                    ]
                                    
                                    for fmt in time_formats:
                                        try:
                                            time_obj = datetime.strptime(raw_val, fmt).time()
                                            created_time = time_obj
                                            print(f"Matched time format '{fmt}': time={created_time}")
                                            break
                                        except ValueError:
                                            continue
                            
                            # If we have a date but no time, set time to midnight
                            if record_date and not created_time:
                                created_time = time(0, 0)
                                print(f"Have date but no time, using midnight: {created_time}")
                            
                            # If we have time but no date, this shouldn't happen with proper parsing
                            if created_time and not record_date:
                                # This case should be rare now with proper datetime parsing
                                record_date = timezone.now().date()
                                errors.append(f"Row {row_num}: Could not extract date from '{raw_val}', using today's date")
                                print(f"WARNING: No date extracted, using today: {record_date}")
                            
                            # If we have neither, something went wrong
                            if not record_date or not created_time:
                                errors.append(f"Row {row_num}: Could not parse created_at value '{raw_val}'")
                                continue
                            
                            # Get other fields
                            language = row.get('language', '').strip() or None
                            original_disease = row.get('original_disease', '').strip() or None
                            changed_disease = row.get('changed_disease', '').strip() or None
                            other_diseases = row.get('other_diseases', '').strip() or None
                            country_code = row.get('country_code', '').strip() or None
                            county = row.get('county', '').strip() or None
                            state = row.get('state', '').strip() or None
                            region = row.get('region', '').strip() or None
                            location_name = row.get('location_name', '').strip() or None
                            
                            # ===== MODIFIED: Check for duplicate based on UniqueConstraint fields =====
                            # The UniqueConstraint ensures uniqueness on (record_date, farm, ai_disease_id)
                            
                            # Check if record with same record_date, farm, and ai_disease_id exists
                            duplicate_query = AIDisease.objects.filter(
                                record_date=record_date,
                                ai_disease_id=ai_disease_id
                            )
                            
                            # Add farm to filter if farm exists (if farm is None, filter for NULL farm)
                            if farm:
                                duplicate_query = duplicate_query.filter(farm=farm)
                            else:
                                duplicate_query = duplicate_query.filter(farm__isnull=True)
                            
                            if duplicate_query.exists():
                                # This is a duplicate - skip it and continue
                                duplicates_skipped += 1
                                duplicate_ids.append(ai_disease_id)
                                continue  # Skip this record and continue to next row
                            
                            # Check if disease with this ID already exists (additional check by ai_disease_id only)
                            # Note: This is a broader check than the unique constraint
                            if AIDisease.objects.filter(ai_disease_id=ai_disease_id).exists():
                                duplicates_skipped += 1
                                duplicate_ids.append(ai_disease_id)
                                continue  # Skip this record and continue to next row
                            
                            # Create the disease record (no duplicate found)
                            AIDisease.objects.create(
                                ai_disease_id=ai_disease_id,
                                user_id=user_id,
                                lat=lat,
                                lng=lng,
                                farm=farm,
                                crop_name=crop_name,
                                created_at=created_time,
                                language=language,
                                original_disease=original_disease,
                                changed_disease=changed_disease,
                                other_diseases=other_diseases,
                                country_code=country_code,
                                county=county,
                                state=state,
                                region=region,
                                location_name=location_name,
                                record_date=record_date,
                                created_date=timezone.now().date()
                            )
                            
                            diseases_created += 1
                            
                            # Track date for reporting
                            date_str = record_date.strftime('%Y-%m-%d')
                            date_counts[date_str] = date_counts.get(date_str, 0) + 1
                            
                        except Exception as e:
                            errors.append(f"Row {row_num}: {str(e)} - {traceback.format_exc()}")
                
                # Show results with enhanced reporting
                if errors:
                    error_message = "Errors encountered:\n" + "\n".join(errors[:5])
                    if len(errors) > 5:
                        error_message += f"\n... and {len(errors) - 5} more errors"
                    self.message_user(
                        request,
                        error_message,
                        messages.ERROR
                    )
                
                # Show duplicate information if any
                if duplicates_skipped > 0:
                    duplicate_preview = ", ".join(str(id) for id in duplicate_ids[:10])
                    duplicate_message = f'⚠️ Skipped {duplicates_skipped} duplicate records'
                    if duplicate_ids:
                        duplicate_message += f" (IDs: {duplicate_preview}"
                        if len(duplicate_ids) > 10:
                            duplicate_message += f" and {len(duplicate_ids) - 10} more"
                        duplicate_message += ")"
                    
                    self.message_user(
                        request,
                        duplicate_message,
                        messages.WARNING
                    )
                
                if diseases_created:
                    date_summary = ", ".join([f"{date}: {count}" for date, count in date_counts.items()])
                    self.message_user(
                        request,
                        f'✅ Successfully uploaded {diseases_created} new AI Disease records.',
                        messages.SUCCESS
                    )
                elif diseases_created == 0 and duplicates_skipped > 0:
                    self.message_user(
                        request,
                        f'No new records created. All {duplicates_skipped} records were duplicates.',
                        messages.WARNING
                    )
                
                return redirect('admin:analytics_aidisease_changelist')
            else:
                # Form is invalid
                for field, errors in form.errors.items():
                    for error in errors:
                        self.message_user(
                            request,
                            f'{field}: {error}',
                            messages.ERROR
                        )
        else:
            form = AIDiseaseCSVUploadForm()
        
        context = {
            **self.admin_site.each_context(request),
            'form': form,
            'opts': self.model._meta,
            'title': 'Upload AI Disease CSV',
            'subtitle': 'National Client - AI Disease Data Import (Date auto-extracted from created_at)',
            'back_url': 'admin:analytics_aidisease_changelist',
        }
        return render(request, 'admin/csv_upload_form_with_date.html', context)

    def delete_by_date(self, request):
        """Custom view to delete records by date"""
        from django.http import JsonResponse
        from django.views.decorators.csrf import csrf_exempt
        
        if request.method == 'POST':
            date_str = request.POST.get('date')
            try:
                record_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                
                # Check if records exist for this date
                count = AIDisease.objects.filter(record_date=record_date).count()
                if count == 0:
                    return JsonResponse({
                        'success': False,
                        'error': f'No records found for date {record_date}'
                    })
                
                # Delete records
                deleted_count, _ = AIDisease.objects.filter(record_date=record_date).delete()
                
                return JsonResponse({
                    'success': True,
                    'message': f'Successfully deleted {deleted_count} records for {record_date}',
                    'deleted_count': deleted_count
                })
                
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid date format. Use YYYY-MM-DD'
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                })
        
        # GET request - show confirmation page
        context = {
        **self.admin_site.each_context(request),
        'opts': self.model._meta,
        'title': 'Delete Records by Date',
        'subtitle': f'Select a date to delete all {self.model._meta.verbose_name_plural}',
        'back_url': f'admin:analytics_{self.model._meta.model_name}_changelist',
        }
        return render(request, 'admin/delete_by_date.html', context)


@admin.register(HumanDetectedDisease)
class HumanDetectedDiseaseAdmin(ModelAdmin):
    list_display = [
        'display_crop_name',
        'display_user_id',
        'display_farm',
        'display_record_date',
        'display_infection_percentage',
        'display_actions',
    ]
    
    search_fields = ('crop_name','record_date','other_crops_id', 'description', 'comment')
    list_filter = ('record_date', 'crop_name', 'country_code')
    list_per_page = 50
    raw_id_fields = ('farm',)
    
    # Add custom templates
    change_list_template = 'admin/analytics/othercrop/change_list.html'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('upload-csv/', self.admin_site.admin_view(self.upload_csv), name='analytics_humandetecteddisease_upload_csv'),
            path('delete-by-date/', self.admin_site.admin_view(self.delete_by_date), name='analytics_humandetecteddisease_delete_by_date'),
        ]
        return custom_urls + urls
    
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_upload_button'] = True
        extra_context['upload_csv_url'] = 'admin:analytics_humandetecteddisease_upload_csv'
        extra_context['delete_by_date_url'] = 'admin:analytics_humandetecteddisease_delete_by_date'
        return super().changelist_view(request, extra_context=extra_context)
    
    @display(description='Crop Name')
    def display_crop_name(self, obj):
        return obj.crop_name
    
    @display(description='User ID', ordering='user_id')
    def display_user_id(self, obj):
        return f"#{obj.user_id}"
    
    @display(description='Farm', ordering='farm__farm_name')
    def display_farm(self, obj):
        if obj.farm:
            return obj.farm.farm_name
        return "No farm"
    
    @display(description='Record Date', ordering='record_date')
    def display_record_date(self, obj):
        return obj.record_date.strftime("%Y-%m-%d")
    
    @display(description='Infection %', ordering='infection_percentage')
    def display_infection_percentage(self, obj):
        if obj.infection_percentage:
            return f"{obj.infection_percentage}%"
        return "N/A"
    
    @display(description='Actions')
    def display_actions(self, obj):
        from django.urls import reverse
        edit_url = reverse('admin:analytics_humandetecteddisease_change', args=[obj.id])
        delete_url = reverse('admin:analytics_humandetecteddisease_delete', args=[obj.id])
        
        return format_html(
            '''
            <div class="flex gap-2">
                <a href="{}" class="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md bg-blue-100 text-blue-800 hover:bg-blue-200">
                    Edit
                </a>
                <a href="{}" class="inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-md bg-red-100 text-red-800 hover:bg-red-200">
                    Delete
                </a>
            </div>
            ''',
            edit_url,
            delete_url
        )
    
    def parse_datetime_field(self, value):
        """Parse a datetime field that might contain date, time, or both"""
        if not value or str(value).lower() in ['', 'null', 'none', 'nan']:
            return None, None
        
        raw_val = str(value).strip()
        record_date = None
        record_time = None
        
        # Try common datetime formats including those with microseconds
        datetime_formats = [
            # ISO format with microseconds
            '%Y-%m-%d %H:%M:%S.%f',     # 2023-01-31 16:16:04.638972
            
            # ISO formats
            '%Y-%m-%d %H:%M:%S',        # 2023-01-31 16:16:04
            '%Y-%m-%d %H:%M',           # 2023-01-31 16:16
            '%Y-%m-%dT%H:%M:%S.%f',     # 2023-01-31T16:16:04.638972
            '%Y-%m-%dT%H:%M:%S',        # 2023-01-31T16:16:04
            
            # US formats (month/day/year)
            '%m/%d/%Y %I:%M:%S %p',     # 2/15/2023 7:36:56 AM
            '%m/%d/%Y %H:%M:%S',        # 2/15/2023 07:36:56
            '%m/%d/%Y %I:%M %p',        # 2/15/2023 7:36 AM
            '%m/%d/%Y %H:%M',           # 2/15/2023 07:36
            '%m/%d/%y %I:%M:%S %p',     # 2/15/23 7:36:56 AM
            
            # European formats (day/month/year)
            '%d/%m/%Y %H:%M:%S',        # 15/2/2023 07:36:56
            '%d/%m/%Y %I:%M:%S %p',     # 15/2/2023 7:36:56 AM
            
            # With commas
            '%m/%d/%Y, %I:%M:%S %p',    # 2/15/2023, 7:36:56 AM
        ]
        
        for fmt in datetime_formats:
            try:
                dt = datetime.strptime(raw_val, fmt)
                return dt.date(), dt.time()
            except ValueError:
                continue
        
        # If no datetime format matched, try Excel serial number
        import re
        if re.match(r'^\d+(\.\d+)?$', raw_val):
            try:
                excel_serial = float(raw_val)
                if excel_serial > 60:
                    excel_serial -= 1
                excel_epoch = datetime(1899, 12, 31)
                dt = excel_epoch + timedelta(days=excel_serial)
                return dt.date(), dt.time()
            except ValueError:
                pass
        
        # Try time-only formats
        time_formats = [
            '%H:%M:%S.%f',    # 16:16:04.638972
            '%H:%M:%S',       # 16:16:04
            '%H:%M',          # 16:16
            '%I:%M:%S %p',    # 7:36:56 AM
            '%I:%M %p',       # 7:36 AM
            '%M:%S.%f',       # 05:14.0 (minutes:seconds.microseconds)
            '%M:%S',          # 05:14 (minutes:seconds)
        ]
        
        for fmt in time_formats:
            try:
                time_obj = datetime.strptime(raw_val, fmt).time()
                return None, time_obj
            except ValueError:
                continue
        
        return None, None
    
    def upload_csv(self, request):
        """Custom view for CSV upload - skips duplicates and continues processing"""
        from analytics.forms import HumanDetectedDiseaseCSVUploadForm
        import traceback
        
        if request.method == 'POST':
            form = HumanDetectedDiseaseCSVUploadForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = request.FILES['csv_file']
                
                # Try to decode the CSV file
                raw = csv_file.read()

                try:
                    data_set = raw.decode('utf-8')
                except UnicodeDecodeError:
                    data_set = raw.decode('ISO-8859-1')
                
                io_string = io.StringIO(data_set)

                try:
                    sample = data_set[:1000]
                    dialect = csv.Sniffer().sniff(sample)
                except:
                    dialect = 'excel'

                io_string.seek(0)
                reader = csv.DictReader(io_string, dialect=dialect)
                
                crops_created = 0
                errors = []
                duplicates_skipped = 0
                date_counts = {}
                duplicate_keys = []  # Track duplicate keys for reporting
                
                with transaction.atomic():
                    for row_num, row in enumerate(reader, start=2):
                        try:
                            # ===== CHECK FOR other_crops_id FIRST (required for unique constraint) =====
                            other_crops_id_str = str(row.get('other_crops_id', '')).strip()
                            if not other_crops_id_str:
                                errors.append(f"Row {row_num}: other_crops_id is required")
                                continue
                            
                            try:
                                other_crops_id = int(float(other_crops_id_str))
                            except ValueError:
                                errors.append(f"Row {row_num}: Invalid other_crops_id '{other_crops_id_str}'")
                                continue
                            
                            # Parse user_id (required)
                            user_id_str = str(row.get('user_id', '')).strip()
                            if not user_id_str:
                                errors.append(f"Row {row_num}: user_id is required")
                                continue
                            
                            try:
                                user_id = int(float(user_id_str))
                            except ValueError:
                                errors.append(f"Row {row_num}: Invalid user_id '{user_id_str}'")
                                continue
                            
                            # Parse crop_name (required)
                            crop_name = row.get('crop_name', '').strip()
                            if not crop_name:
                                errors.append(f"Row {row_num}: crop_name is required")
                                continue
                            
                            # Parse coordinates
                            lat = None
                            lng = None
                            lat_str = row.get('lat', '').strip()
                            lng_str = row.get('lng', '').strip()
                            
                            if lat_str:
                                try:
                                    lat = float(lat_str)
                                except ValueError:
                                    errors.append(f"Row {row_num}: Invalid latitude '{lat_str}'")
                                    continue
                            
                            if lng_str:
                                try:
                                    lng = float(lng_str)
                                except ValueError:
                                    errors.append(f"Row {row_num}: Invalid longitude '{lng_str}'")
                                    continue
                            
                            # Parse farm_id if provided
                            farm = None
                            farm_id_str = row.get('farm_id', '').strip()
                            if farm_id_str:
                                try:
                                    farm_id = int(float(farm_id_str))
                                    from analytics.models import Farm
                                    try:
                                        farm = Farm.objects.get(farm_id=farm_id)
                                    except Farm.DoesNotExist:
                                        errors.append(f"Row {row_num}: Farm with ID {farm_id} does not exist")
                                        continue
                                except ValueError:
                                    errors.append(f"Row {row_num}: Invalid farm_id '{farm_id_str}'")
                                    continue
                            
                            # Parse date/time fields
                            # Priority: collected_at -> created_at -> updated_at for record_date
                            record_date = None
                            collected_time = None
                            created_time = None
                            updated_time = None
                            
                            # Try collected_at first
                            collected_date, collected_time = self.parse_datetime_field(row.get('collected_at', ''))
                            if collected_date:
                                record_date = collected_date
                            
                            # Try created_at next if no date found
                            created_date, created_time = self.parse_datetime_field(row.get('created_at', ''))
                            if not record_date and created_date:
                                record_date = created_date
                            
                            # Try updated_at last if still no date
                            updated_date, updated_time = self.parse_datetime_field(row.get('updated_at', ''))
                            if not record_date and updated_date:
                                record_date = updated_date
                            
                            # If still no date found, use current date
                            if not record_date:
                                record_date = timezone.now().date()
                                errors.append(f"Row {row_num}: No valid date found in any date field, using today's date")
                            
                            # Parse threats (JSON list)
                            threats = None
                            threats_str = row.get('threats', '').strip()
                            if threats_str and threats_str not in ['', '[]']:
                                try:
                                    # Clean the string and parse as JSON
                                    threats_str = threats_str.replace("'", '"')
                                    threats = json.loads(threats_str)
                                except json.JSONDecodeError:
                                    # Try to handle malformed JSON
                                    threats_str = threats_str.strip('[]').replace("'", "").strip()
                                    if threats_str:
                                        threats = [threat.strip() for threat in threats_str.split(',')]
                            
                            # Parse infection percentage
                            infection_percentage = None
                            infection_str = row.get('infection_percentage', '').strip()
                            if infection_str:
                                try:
                                    infection_percentage = float(infection_str)
                                except ValueError:
                                    errors.append(f"Row {row_num}: Invalid infection_percentage '{infection_str}'")
                                    continue
                            
                            # Get other fields
                            description = row.get('description', '').strip() or None
                            comment = row.get('comment', '').strip() or None
                            country_code = row.get('country_code', '').strip() or None
                            county = row.get('county', '').strip() or None
                            state = row.get('state', '').strip() or None
                            region = row.get('region', '').strip() or None
                            location_name = row.get('location_name', '').strip() or None
                            
                            # ===== CHECK FOR DUPLICATES BASED ON UNIQUE CONSTRAINT =====
                            # The UniqueConstraint is: fields=['record_date', 'farm', 'other_crops_id']
                            
                            # Build the duplicate check query
                            duplicate_query = HumanDetectedDisease.objects.filter(
                                record_date=record_date,
                                other_crops_id=other_crops_id  # Note: field name is other_crops_id, not other_crops_id
                            )
                            
                            # Add farm to filter if farm exists (if farm is None, filter for NULL farm)
                            if farm:
                                duplicate_query = duplicate_query.filter(farm=farm)
                            else:
                                duplicate_query = duplicate_query.filter(farm__isnull=True)
                            
                            if duplicate_query.exists():
                                # This is a duplicate - skip it and continue
                                duplicates_skipped += 1
                                duplicate_keys.append({
                                    'record_date': record_date.strftime('%Y-%m-%d'),
                                    'farm_id': farm.farm_id if farm else 'None',
                                    'other_crops_id': other_crops_id
                                })
                                continue  # Skip this record and continue to next row
                            
                            # Also check by other_crops_id alone as additional safety
                            if HumanDetectedDisease.objects.filter(other_crops_id=other_crops_id).exists():
                                duplicates_skipped += 1
                                duplicate_keys.append({
                                    'record_date': 'N/A',
                                    'farm_id': 'N/A',
                                    'other_crops_id': other_crops_id
                                })
                                continue  # Skip this record and continue to next row
                            
                            # Create the other crop record (no duplicate found)
                            HumanDetectedDisease.objects.create(
                                other_crops_id=other_crops_id,
                                user_id=user_id,
                                crop_name=crop_name,
                                description=description,
                                collected_at=collected_time,
                                created_at=created_time,
                                updated_at=updated_time,
                                lat=lat,
                                lng=lng,
                                farm=farm,
                                threats=threats,
                                comment=comment,
                                infection_percentage=infection_percentage,
                                country_code=country_code,
                                county=county,
                                state=state,
                                region=region,
                                location_name=location_name,
                                record_date=record_date,
                                collected_date=record_date if collected_time else None,
                                created_date=timezone.now().date()
                            )
                            
                            crops_created += 1
                            
                            # Track date for reporting
                            date_str = record_date.strftime('%Y-%m-%d')
                            date_counts[date_str] = date_counts.get(date_str, 0) + 1
                            
                        except Exception as e:
                            errors.append(f"Row {row_num}: {str(e)} - {traceback.format_exc()}")
                
                # Show results with enhanced reporting
                if errors:
                    error_message = "Errors encountered:\n" + "\n".join(errors[:5])
                    if len(errors) > 5:
                        error_message += f"\n... and {len(errors) - 5} more errors"
                    self.message_user(
                        request,
                        error_message,
                        messages.ERROR
                    )
                
                # Show duplicate information if any
                if duplicates_skipped > 0:
                    duplicate_preview = ", ".join([f"ID:{k['other_crops_id']}" for k in duplicate_keys[:10]])
                    duplicate_message = f'⚠️ Skipped {duplicates_skipped} duplicate records'
                    if duplicate_keys:
                        duplicate_message += f" (HumanDetectedDisease IDs: {duplicate_preview}"
                        if len(duplicate_keys) > 10:
                            duplicate_message += f" and {len(duplicate_keys) - 10} more"
                        duplicate_message += ")"
                    
                    self.message_user(
                        request,
                        duplicate_message,
                        messages.WARNING
                    )
                
                if crops_created:
                    date_summary = ", ".join([f"{date}: {count}" for date, count in date_counts.items()])
                    self.message_user(
                        request,
                        f'✅ Successfully uploaded {crops_created} new Other Crop records.',
                        messages.SUCCESS
                    )
                elif crops_created == 0 and duplicates_skipped > 0:
                    self.message_user(
                        request,
                        f'No new records created. All {duplicates_skipped} records were duplicates.',
                        messages.WARNING
                    )
                
                return redirect('admin:analytics_humandetecteddisease_changelist')
            else:
                # Form is invalid
                for field, errors in form.errors.items():
                    for error in errors:
                        self.message_user(
                            request,
                            f'{field}: {error}',
                            messages.ERROR
                        )
        else:
            form = HumanDetectedDiseaseCSVUploadForm()
        
        context = {
            **self.admin_site.each_context(request),
            'form': form,
            'opts': self.model._meta,
            'title': 'Upload Other Crop CSV',
            'subtitle': 'National Client - Other Crop Data Import (Date auto-extracted from date fields)',
            'back_url': 'admin:analytics_humandetecteddisease_changelist',
        }
        return render(request, 'admin/csv_upload_form_with_date.html', context)

    def delete_by_date(self, request):
        """Custom view to delete records by date"""
        from django.http import JsonResponse
        
        if request.method == 'POST':
            date_str = request.POST.get('date')
            try:
                record_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                
                # Check if records exist for this date
                count = HumanDetectedDisease.objects.filter(record_date=record_date).count()
                if count == 0:
                    return JsonResponse({
                        'success': False,
                        'error': f'No records found for date {record_date}'
                    })
                
                # Delete records
                deleted_count, _ = HumanDetectedDisease.objects.filter(record_date=record_date).delete()
                
                return JsonResponse({
                    'success': True,
                    'message': f'Successfully deleted {deleted_count} records for {record_date}',
                    'deleted_count': deleted_count
                })
                
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid date format. Use YYYY-MM-DD'
                })
            except Exception as e:
                return JsonResponse({
                    'success': False,
                    'error': str(e)
                })
        
        # GET request - show confirmation page
        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'title': 'Delete Records by Date',
            'subtitle': f'Select a date to delete all {self.model._meta.verbose_name_plural}',
            'back_url': f'admin:analytics_{self.model._meta.model_name}_changelist',
        }
        return render(request, 'admin/delete_by_date.html', context)