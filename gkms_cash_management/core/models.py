from django.db import models
from django.contrib.auth.models import User
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone

def yesterday():
    return datetime.now().date() - timedelta(days=1)

def today():
    return datetime.now().date()

def tomorrow():
    return datetime.now().date() + timedelta(days=1)

class Location(models.Model):
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class AgentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=20, blank=True, null=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.location.name}"

    class Meta:
        verbose_name = "Agent Profile"
        verbose_name_plural = "Agent Profiles"

class LocationLimit(models.Model):
    location = models.OneToOneField(Location, on_delete=models.CASCADE)
    insurance_limit = models.DecimalField(max_digits=15, decimal_places=2, default=5000000.00)
    eod_vault_limit = models.DecimalField(max_digits=15, decimal_places=2, default=3000000.00)
    working_day_limit = models.DecimalField(max_digits=15, decimal_places=2, default=2000000.00)

    def __str__(self):
        return f"Limits for {self.location.name}"

class CashDelivery(models.Model):
    location = models.ForeignKey(Location, on_delete=models.CASCADE, null=True, blank=True)
    cash_request = models.OneToOneField('CashRequest', on_delete=models.SET_NULL, null=True, blank=True, related_name='delivery')
    date = models.DateField(default=today)
    jmd_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    usd_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    verification_date = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Delivery to {self.location.name if self.location else 'Unknown'} on {self.date}"

class CashRequest(models.Model):
    REQUEST_TYPES = (
        ('regular', 'Regular'),
        ('urgent', 'Urgent')
    )

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('delivered', 'Delivered'),
        ('rejected', 'Rejected')
    )

    location = models.ForeignKey(Location, on_delete=models.CASCADE, null=True, blank=True)
    request_date = models.DateTimeField(auto_now_add=True)
    delivery_date = models.DateField(default=tomorrow)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    request_type = models.CharField(max_length=10, choices=REQUEST_TYPES, default='regular')
    
    # JMD Denominations
    jmd_5000 = models.IntegerField(default=0)
    jmd_2000 = models.IntegerField(default=0)  
    jmd_1000 = models.IntegerField(default=0)
    jmd_500 = models.IntegerField(default=0)
    jmd_100 = models.IntegerField(default=0)
    jmd_50 = models.IntegerField(default=0)
    
    # USD Denominations
    usd_100 = models.IntegerField(default=0)
    usd_50 = models.IntegerField(default=0)
    usd_20 = models.IntegerField(default=0)
    usd_10 = models.IntegerField(default=0)
    usd_1 = models.IntegerField(default=0)
    
    # Calculated fields
    total_jmd = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    total_usd = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    
    # Approval fields
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_requests')
    approved_date = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Cash Request #{self.id} for {self.location.name if self.location else 'Unknown'}"
    
    def save(self, *args, **kwargs):
        # Calculate totals before saving
        self.total_jmd = (
            self.jmd_5000 * 5000 +
            self.jmd_2000 * 2000 +
            self.jmd_1000 * 1000 +
            self.jmd_500 * 500 +
            self.jmd_100 * 100 +
            self.jmd_50 * 50
        )
        
        self.total_usd = (
            self.usd_100 * 100 +
            self.usd_50 * 50 +
            self.usd_20 * 20 +
            self.usd_10 * 10 +
            self.usd_1 * 1
        )
        
        super().save(*args, **kwargs)

class EODReport(models.Model):
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='eod_reports')
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='eod_reports')
    processing_date = models.DateField(default=yesterday)
    closing_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    funds_from_bxp_webex = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    
    # Courier Fields
    cash_sent_to_courier = models.BooleanField(default=False)
    courier_usd_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, default=0.00)
    courier_usd_receipt = models.CharField(max_length=50, null=True, blank=True, default='')
    courier_jmd_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, default=0.00)
    courier_jmd_receipt = models.CharField(max_length=50, null=True, blank=True, default='')
    
    # Teller Balance Fields
    all_tellers_balanced = models.BooleanField(default=True)
    total_variance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    
    notes = models.TextField(blank=True, default='')
    confirmation = models.BooleanField(default=False)
    submitted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['agent', 'location', 'processing_date']
        ordering = ['-processing_date']

    def __str__(self):
        return f"EOD Report {self.location.name} - {self.processing_date}"

class TellerBalance(models.Model):
    eod_report = models.ForeignKey(EODReport, on_delete=models.CASCADE, related_name='teller_balances')
    teller_name = models.CharField(max_length=255, default='')
    jmd_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    usd_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.eod_report} - {self.teller_name}"

class Adjustment(models.Model):
    TYPE_CHOICES = (
        ('denomination', 'Denomination'),
        ('overage', 'Overage'),
        ('shortage', 'Shortage'),
    )
    
    CURRENCY_CHOICES = (
        ('JMD', 'Jamaican Dollar'),
        ('USD', 'US Dollar'),
    )
    
    eod_report = models.ForeignKey(EODReport, on_delete=models.CASCADE, related_name='adjustments')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='denomination')
    description = models.CharField(max_length=255, default='')
    count = models.IntegerField(default=1)
    amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='JMD')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.eod_report} - {self.type} - {self.amount} {self.currency}"

class DailyAgentData(models.Model):
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    agent = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    date = models.DateField(default=today)
    previous_day_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    cash_delivered_today = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    payout_at_3pm = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    cash_position_at_3pm = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    projected_ending_position = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    projected_next_day_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    closing_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    variance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    # These fields will be used to track limit exceedances
    exceeds_insurance_limit = models.BooleanField(default=False)
    exceeds_eod_limit = models.BooleanField(default=False)
    exceeds_working_day_limit = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('location', 'date')
        
    def __str__(self):
        return f"{self.location.name} - {self.date}"
        
    def expected_closing_balance(self):
        return self.previous_day_balance + self.cash_delivered_today - self.payout_at_3pm

class TellerVariance(models.Model):
    eod_report = models.ForeignKey(EODReport, on_delete=models.CASCADE, related_name='teller_variances')
    teller_number = models.CharField(max_length=2, default='')
    variance = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Teller {self.teller_number} - {self.eod_report.processing_date}"

class DenominationBreakdown(models.Model):
    CURRENCY_CHOICES = (
        ('JMD', 'Jamaican Dollar'),
        ('USD', 'US Dollar'),
    )
    
    eod_report = models.ForeignKey(EODReport, on_delete=models.CASCADE, related_name='denomination_breakdowns')
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='JMD')
    
    # JMD Denominations
    denomination_5000_count = models.IntegerField(default=0)
    denomination_1000_count = models.IntegerField(default=0)
    denomination_500_count = models.IntegerField(default=0)
    denomination_100_count = models.IntegerField(default=0)
    denomination_50_count = models.IntegerField(default=0)
    coins_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    
    # USD Denominations
    denomination_100_count = models.IntegerField(default=0)
    denomination_50_count = models.IntegerField(default=0)
    denomination_20_count = models.IntegerField(default=0)
    denomination_10_count = models.IntegerField(default=0)
    small_bills_coins_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['eod_report', 'currency']
    
    def __str__(self):
        return f"{self.eod_report.location.name} - {self.currency} Breakdown - {self.eod_report.processing_date}"
    
    def get_total(self):
        if self.currency == 'JMD':
            return (
                self.denomination_5000_count * 5000 +
                self.denomination_1000_count * 1000 +
                self.denomination_500_count * 500 +
                self.denomination_100_count * 100 +
                self.denomination_50_count * 50 +
                self.coins_amount
            )
        elif self.currency == 'USD':
            return (
                self.denomination_100_count * 100 +
                self.denomination_50_count * 50 +
                self.denomination_20_count * 20 +
                self.denomination_10_count * 10 +
                self.small_bills_coins_amount
            )
        return 0

class EmergencyAccessRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('denied', 'Denied'),
        ('expired', 'Expired'),
    )
    
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='emergency_access_requests')
    location = models.ForeignKey(Location, on_delete=models.CASCADE)
    requested_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_access_requests')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    access_granted_until = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Emergency Access Request by {self.agent.username} ({self.get_status_display()})"
    
    def is_active(self):
        if self.status == 'approved' and self.access_granted_until:
            return timezone.now() <= self.access_granted_until
        return False
    
    class Meta:
        ordering = ['-requested_at']

class SystemSettings(models.Model):
    """Global system settings"""
    cutoff_window_enabled = models.BooleanField(default=True, help_text="Enable/disable the 3 PM cutoff window")
    cutoff_hour = models.IntegerField(default=15, help_text="Hour of the day for cutoff (24-hour format)")
    cutoff_minute = models.IntegerField(default=0, help_text="Minute of the hour for cutoff")
    business_hours_start = models.IntegerField(default=8, help_text="Start hour of business hours (24-hour format)")
    business_hours_start_minute = models.IntegerField(default=0, help_text="Start minute of business hours")
    emergency_access_duration = models.IntegerField(default=30, help_text="Duration of emergency access in minutes")
    last_updated = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='settings_updates')

    class Meta:
        verbose_name = "System Settings"
        verbose_name_plural = "System Settings"

    def __str__(self):
        return "System Settings"

    @classmethod
    def get_settings(cls):
        """Get or create system settings"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings

from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_agent_profile(sender, instance, created, **kwargs):
    """
    Signal handler to ensure we don't interfere with manual profile creation.
    """
    # Don't do anything in this signal - we handle profile creation manually
    pass

# Patch the User model with additional properties
def get_location_name(self):
    try:
        if hasattr(self, 'agentprofile') and self.agentprofile:
            return self.agentprofile.location.name
        profile = AgentProfile.objects.filter(user=self).first()
        if profile:
            return profile.location.name
        return "Not assigned"
    except Exception:
        return "Not assigned"

User.add_to_class('get_location_name', get_location_name)