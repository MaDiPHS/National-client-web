import uuid
from django.db import models
from django.utils import timezone

class Farm(models.Model):
    """Model for farms data"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    farm_id = models.IntegerField(unique=True)  # Original farm_id from Excel
    farm_name = models.CharField(max_length=255)
    lat = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    lng = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    
    # Change TimeField to DateTimeField
    created_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    # Date fields for analytics
    created_date = models.DateField(default=timezone.now)
    updated_date = models.DateField(auto_now=True)
 
    def __str__(self):
        return f"{self.farm_name} ({self.farm_id})"
    
    class Meta:
        ordering = ['farm_id']


class AIDisease(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ai_disease_id = models.IntegerField()
    user_id = models.IntegerField(blank=True, null=True)
    lat = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    lng = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    farm = models.ForeignKey('Farm', on_delete=models.CASCADE, to_field='farm_id', null=True, blank=True)
    crop_name = models.CharField(max_length=255)
    created_at = models.TimeField(null=True, blank=True)
    language = models.CharField(max_length=10, null=True, blank=True)
    original_disease = models.CharField(max_length=255, null=True, blank=True)
    changed_disease = models.CharField(max_length=255, null=True, blank=True)
    other_diseases = models.CharField(max_length=255, null=True, blank=True)
    country_code = models.CharField(max_length=5, null=True, blank=True)
    county = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    region = models.CharField(max_length=255, null=True, blank=True)
    location_name = models.CharField(max_length=255, null=True, blank=True)
    record_date = models.DateField()
    created_date = models.DateField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['record_date', 'farm', 'ai_disease_id'],
                name='unique_record_per_farm_date_disease'
            )
        ]

    def __str__(self):
        return f"AIDisease {self.ai_disease_id} - {self.crop_name}"


class HumanDetectedDisease(models.Model):
    """Model for other crops data"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    other_crops_id = models.IntegerField(default=0)
    user_id = models.IntegerField()
    crop_name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    collected_at = models.TimeField(null=True, blank=True)
    created_at = models.TimeField(null=True, blank=True)
    updated_at = models.TimeField(null=True, blank=True)
    lat = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    lng = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, to_field='farm_id', null=True, blank=True)
    threats = models.JSONField(null=True, blank=True)  # Store the list of threats
    comment = models.TextField(null=True, blank=True)
    infection_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    country_code = models.CharField(max_length=5, null=True, blank=True)
    county = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    region = models.CharField(max_length=255, null=True, blank=True)
    location_name = models.CharField(max_length=255, null=True, blank=True)
    
    # Date fields for analytics
    record_date = models.DateField()
    collected_date = models.DateField(null=True, blank=True)
    created_date = models.DateField(default=timezone.now)
    updated_date = models.DateField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['record_date', 'farm', 'other_crops_id'],
                name='unique_other_crops_record_per_farm_date_disease'
            )
        ]

    def __str__(self):
        return f"OtherCrop - {self.crop_name}"