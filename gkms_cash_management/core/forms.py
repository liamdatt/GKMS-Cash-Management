from django import forms
from .models import CashRequest, EODReport, CashDelivery, TellerBalance, Adjustment, EmergencyAccessRequest, Location
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

class CashRequestForm(forms.ModelForm):
    # JMD Denomination Values
    jmd_5000_value = forms.DecimalField(
        label='$5,000 Notes Value',
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control denomination-input', 'min': '0', 'step': '5000'})
    )
    jmd_2000_value = forms.DecimalField(
        label='$2,000 Notes Value',
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control denomination-input', 'min': '0', 'step': '2000'})
    )
    jmd_1000_value = forms.DecimalField(
        label='$1,000 Notes Value',
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control denomination-input', 'min': '0', 'step': '1000'})
    )
    jmd_500_value = forms.DecimalField(
        label='$500 Notes Value',
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control denomination-input', 'min': '0', 'step': '500'})
    )
    jmd_100_value = forms.DecimalField(
        label='$100 Notes Value',
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control denomination-input', 'min': '0', 'step': '100'})
    )
    jmd_50_value = forms.DecimalField(
        label='$50 Notes Value',
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control denomination-input', 'min': '0', 'step': '50'})
    )

    # USD Denomination Values
    usd_100_value = forms.DecimalField(
        label='$100 Notes Value',
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control denomination-input', 'min': '0', 'step': '100'})
    )
    usd_50_value = forms.DecimalField(
        label='$50 Notes Value',
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control denomination-input', 'min': '0', 'step': '50'})
    )
    usd_20_value = forms.DecimalField(
        label='$20 Notes Value',
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control denomination-input', 'min': '0', 'step': '20'})
    )
    usd_10_value = forms.DecimalField(
        label='$10 Notes Value',
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control denomination-input', 'min': '0', 'step': '10'})
    )
    usd_1_value = forms.DecimalField(
        label='$1 Notes Value',
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control denomination-input', 'min': '0', 'step': '1'})
    )

    # Total fields for form submission
    total_jmd = forms.DecimalField(required=False)
    total_usd = forms.DecimalField(required=False)
    
    # Make the original fields optional since we're using the value fields instead
    jmd_5000 = forms.IntegerField(required=False, initial=0)
    jmd_2000 = forms.IntegerField(required=False, initial=0)
    jmd_1000 = forms.IntegerField(required=False, initial=0)
    jmd_500 = forms.IntegerField(required=False, initial=0)
    jmd_100 = forms.IntegerField(required=False, initial=0)
    jmd_50 = forms.IntegerField(required=False, initial=0)
    usd_100 = forms.IntegerField(required=False, initial=0)
    usd_50 = forms.IntegerField(required=False, initial=0)
    usd_20 = forms.IntegerField(required=False, initial=0)
    usd_10 = forms.IntegerField(required=False, initial=0)
    usd_1 = forms.IntegerField(required=False, initial=0)

    class Meta:
        model = CashRequest
        fields = [
            'delivery_date', 'request_type',
            'jmd_5000', 'jmd_2000', 'jmd_1000', 'jmd_500', 'jmd_100', 'jmd_50',
            'usd_100', 'usd_50', 'usd_20', 'usd_10', 'usd_1',
            'total_jmd', 'total_usd'
        ]
        widgets = {
            'delivery_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'request_type': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        
        # Convert denomination values to note counts
        denominations = {
            'jmd_5000': 5000,
            'jmd_2000': 2000,
            'jmd_1000': 1000,
            'jmd_500': 500,
            'jmd_100': 100,
            'jmd_50': 50,
            'usd_100': 100,
            'usd_50': 50,
            'usd_20': 20,
            'usd_10': 10,
            'usd_1': 1
        }

        # Get totals from form data if available
        total_jmd = float(cleaned_data.get('total_jmd') or 0)
        total_usd = float(cleaned_data.get('total_usd') or 0)

        # For each denomination, calculate the note count
        for field, value in denominations.items():
            value_field = f"{field}_value"
            amount = float(cleaned_data.get(value_field) or 0)
            
            if amount > 0 and amount % value != 0:
                self.add_error(value_field, f"Value must be a multiple of ${value}")
            else:
                note_count = int(amount / value) if amount > 0 else 0
                cleaned_data[field] = note_count

        # Add calculated totals to cleaned data
        cleaned_data['total_jmd'] = total_jmd
        cleaned_data['total_usd'] = total_usd

        # Form is only valid if at least one denomination is specified
        if total_jmd == 0 and total_usd == 0:
            self.add_error(None, "Please specify at least one denomination")

        return cleaned_data

class CashVerificationForm(forms.ModelForm):
    confirmed = forms.BooleanField(
        label="I confirm that I have verified and counted the received cash.",
        required=True
    )
    
    class Meta:
        model = CashDelivery
        fields = ['verified']
    
    def save(self, user=None, commit=True):
        instance = super().save(commit=False)
        
        # Mark as verified
        instance.verified = True
        
        # Add verification metadata if the fields exist
        if hasattr(instance, 'verified_by') and user:
            instance.verified_by = user
        
        if hasattr(instance, 'verification_date'):
            instance.verification_date = timezone.now()
        
        if commit:
            instance.save()
        
        return instance

class EODReportForm(forms.ModelForm):
    # Processing Date - Default to previous day
    processing_date = forms.DateField(
        label="Processing Date",
        initial=timezone.now().date() - timedelta(days=1),
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    # Cash Position
    closing_balance = forms.DecimalField(
        label="EOD Balance JMD",
        max_digits=15, 
        decimal_places=2,
        help_text="Enter the closing balance in JMD (numeric only, no commas)"
    )
    
    funds_from_bxp_webex = forms.DecimalField(
        label="Funds Received from BXP and Webex Vaults",
        max_digits=15, 
        decimal_places=2,
        required=False,
        initial=0,
        help_text="Enter the amount received from BXP and Webex vaults (numeric only, no commas)"
    )
    
    # Cash Sent to Courier
    cash_sent_to_courier = forms.BooleanField(
        label="Was cash sent to courier today?",
        required=False,
        initial=False
    )
    
    courier_usd_amount = forms.DecimalField(
        label="USD Amount Sent",
        max_digits=15, 
        decimal_places=2,
        required=False,
        help_text="Enter the USD amount sent to courier (numeric only, no commas)"
    )
    
    courier_usd_receipt = forms.CharField(
        label="USD Receipt Number",
        max_length=50,
        required=False,
        help_text="Enter the receipt number for USD cash sent"
    )
    
    courier_jmd_amount = forms.DecimalField(
        label="JMD Amount Sent",
        max_digits=15, 
        decimal_places=2,
        required=False,
        help_text="Enter the JMD amount sent to courier (numeric only, no commas)"
    )
    
    courier_jmd_receipt = forms.CharField(
        label="JMD Receipt Number",
        max_length=50,
        required=False,
        help_text="Enter the receipt number for JMD cash sent"
    )
    
    # Teller Balancing
    all_tellers_balanced = forms.BooleanField(
        label="Were all tellers balanced?",
        required=False,
        initial=True
    )
    
    # Denomination fields for JMD
    jmd_5000_count = forms.IntegerField(
        label="$5,000 Notes",
        required=False,
        initial=0,
        min_value=0
    )
    
    jmd_1000_count = forms.IntegerField(
        label="$1,000 Notes",
        required=False,
        initial=0,
        min_value=0
    )
    
    jmd_500_count = forms.IntegerField(
        label="$500 Notes",
        required=False,
        initial=0,
        min_value=0
    )
    
    jmd_100_count = forms.IntegerField(
        label="$100 Notes",
        required=False,
        initial=0,
        min_value=0
    )
    
    jmd_50_count = forms.IntegerField(
        label="$50 Notes",
        required=False,
        initial=0,
        min_value=0
    )
    
    jmd_coins_amount = forms.DecimalField(
        label="Coins Total",
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=0,
        min_value=0
    )
    
    # Denomination fields for USD
    usd_100_count = forms.IntegerField(
        label="$100 Notes",
        required=False,
        initial=0,
        min_value=0
    )
    
    usd_50_count = forms.IntegerField(
        label="$50 Notes",
        required=False,
        initial=0,
        min_value=0
    )
    
    usd_20_count = forms.IntegerField(
        label="$20 Notes",
        required=False,
        initial=0,
        min_value=0
    )
    
    usd_10_count = forms.IntegerField(
        label="$10 Notes",
        required=False,
        initial=0,
        min_value=0
    )
    
    usd_small_amount = forms.DecimalField(
        label="Small Bills & Coins Total",
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=0,
        min_value=0
    )
    
    notes = forms.CharField(
        label="Additional Notes",
        widget=forms.Textarea(attrs={'rows': 4}),
        required=False
    )
    
    confirmation = forms.BooleanField(
        label="I confirm that the information provided in this report is accurate to the best of my knowledge.",
        required=True
    )
    
    class Meta:
        model = EODReport
        fields = [
            'processing_date', 'closing_balance', 'funds_from_bxp_webex',
            'cash_sent_to_courier', 'courier_usd_amount', 'courier_usd_receipt',
            'courier_jmd_amount', 'courier_jmd_receipt', 'all_tellers_balanced',
            'jmd_5000_count', 'jmd_1000_count', 'jmd_500_count', 'jmd_100_count',
            'jmd_50_count', 'jmd_coins_amount', 'usd_100_count', 'usd_50_count',
            'usd_20_count', 'usd_10_count', 'usd_small_amount', 'notes', 'confirmation'
        ]

class TellerBalanceForm(forms.ModelForm):
    class Meta:
        model = TellerBalance
        fields = ['teller_name', 'jmd_amount', 'usd_amount']
        widgets = {
            'teller_name': forms.TextInput(attrs={'class': 'form-control'}),
            'jmd_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'usd_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }

class AdjustmentForm(forms.ModelForm):
    class Meta:
        model = Adjustment
        fields = ['type', 'description', 'count', 'amount', 'currency']
        widgets = {
            'type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'count': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'currency': forms.Select(attrs={'class': 'form-control'}),
        }

TellerBalanceFormSet = forms.inlineformset_factory(
    EODReport, TellerBalance, form=TellerBalanceForm,
    extra=1, can_delete=True,
    fields=['teller_name', 'jmd_amount', 'usd_amount']
)

AdjustmentFormSet = forms.inlineformset_factory(
    EODReport, Adjustment, form=AdjustmentForm,
    extra=1, can_delete=True,
    fields=['type', 'description', 'count', 'amount', 'currency']
)

class SignupForm(UserCreationForm):
    email = forms.EmailField(max_length=254, required=True, widget=forms.EmailInput(attrs={'class': 'form-control'}))
    
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'password1': forms.PasswordInput(attrs={'class': 'form-control'}),
            'password2': forms.PasswordInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'}) 

class EmergencyAccessRequestForm(forms.ModelForm):
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Please explain why you need emergency access'}),
        required=True
    )
    
    class Meta:
        model = EmergencyAccessRequest
        fields = ['reason'] 

class LocationUpdateForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ['name', 'address', 'eft_system_name', 'remote_services_name', 'insurance_limit_name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'eft_system_name': forms.TextInput(attrs={'class': 'form-control'}),
            'remote_services_name': forms.TextInput(attrs={'class': 'form-control'}),
            'insurance_limit_name': forms.TextInput(attrs={'class': 'form-control'}),
        } 