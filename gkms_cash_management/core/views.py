from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Sum, Avg
from django.http import HttpResponse, JsonResponse
from .models import (
    AgentProfile, Location, LocationLimit, CashDelivery, 
    CashRequest, EODReport, TellerBalance, Adjustment, DailyAgentData, DenominationBreakdown, TellerVariance, EmergencyAccessRequest, SystemSettings
)
from .forms import CashRequestForm, EODReportForm, CashVerificationForm, SignupForm, EmergencyAccessRequestForm
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
import logging
from django.db import transaction
from django.db import connection
from django.db import reset_queries
import json
from django.contrib.auth.views import LoginView
from datetime import datetime, timedelta
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from decimal import Decimal
import pytz

logger = logging.getLogger(__name__)

def landing_page(request):
    if request.user.is_authenticated:
        return redirect('home')
    return render(request, 'core/landing_page.html')

def home(request):
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('admin_dashboard')
        try:
            # Check if user has an agent profile
            agent = AgentProfile.objects.get(user=request.user)
            return redirect('agent_dashboard')
        except AgentProfile.DoesNotExist:
            messages.warning(request, "Your account has not been assigned to a location yet. Please contact an administrator.")
            return render(request, 'core/waiting_assignment.html')
    return redirect('login')

@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_dashboard(request):
    # Get pending cash requests
    pending_requests = CashRequest.objects.filter(status='pending')
    
    # Get locations data for the dashboard
    locations = Location.objects.all()
    
    # Get daily data for all locations
    today = timezone.now().date()
    daily_data = DailyAgentData.objects.filter(date=today)
    
    # Additional data for dashboard stats
    locations_count = locations.count()
    pending_requests_count = pending_requests.count()
    
    # Prepare warnings based on thresholds and update the flags
    warnings = []
    for data in daily_data:
        # Get location limits (if they exist)
        try:
            limits = LocationLimit.objects.get(location=data.location)
            
            # Check if any limits are exceeded and update flags
            data.exceeds_insurance_limit = data.closing_balance > limits.insurance_limit
            data.exceeds_eod_limit = data.closing_balance > limits.eod_vault_limit
            data.exceeds_working_day_limit = data.closing_balance > limits.working_day_limit
            data.save(update_fields=['exceeds_insurance_limit', 'exceeds_eod_limit', 'exceeds_working_day_limit'])
            
            # Add to warnings list if any limit is exceeded
            if data.exceeds_insurance_limit:
                warnings.append({
                    'location': data.location,
                    'type': 'Insurance Limit Exceeded',
                    'amount': data.closing_balance,
                    'limit': limits.insurance_limit
                })
            
            if data.exceeds_eod_limit:
                warnings.append({
                    'location': data.location,
                    'type': 'EOD Vault Limit Exceeded',
                    'amount': data.closing_balance,
                    'limit': limits.eod_vault_limit
                })
                
            if data.exceeds_working_day_limit:
                warnings.append({
                    'location': data.location,
                    'type': 'Working Day Limit Exceeded',
                    'amount': data.closing_balance,
                    'limit': limits.working_day_limit
                })
        except LocationLimit.DoesNotExist:
            # Skip if no limits defined
            pass
    
    # For compatibility with both old and new code, we'll also try to query based on flags
    try:
        # This will only work after migration is applied
        warnings_from_flags = DailyAgentData.objects.filter(
            Q(exceeds_insurance_limit=True) | 
            Q(exceeds_eod_limit=True) | 
            Q(exceeds_working_day_limit=True)
        ).distinct()
        
        # Add any warnings not already in the list
        for data in warnings_from_flags:
            existing = any(w['location'] == data.location for w in warnings)
            if not existing:
                warnings.append({
                    'location': data.location,
                    'type': 'Limit Exceeded',
                    'amount': data.closing_balance,
                    'limit': 'Unknown'
                })
    except:
        # If the fields don't exist yet, this will silently fail
        pass
    
    context = {
        'pending_requests': pending_requests,
        'warnings': warnings,
        'locations_count': locations_count,
        'pending_requests_count': pending_requests_count,
        'warnings_count': len(warnings),
    }
    
    return render(request, 'core/admin_dashboard.html', context)

@login_required
def agent_dashboard(request):
    """Dashboard view for agent users."""
    try:
        # Get the agent profile
        agent = AgentProfile.objects.get(user=request.user)
        
        # Get today's date and current time in EST (Eastern Standard Time)
        today = timezone.now().date()
        
        # Get system settings
        system_settings = SystemSettings.get_settings()
        
        # Define cutoff times based on system settings
        current_time = timezone.now()
        
        # Define business hours from system settings
        opening_time = current_time.replace(
            hour=system_settings.business_hours_start,
            minute=system_settings.business_hours_start_minute,
            second=0,
            microsecond=0
        )
        cutoff_time = current_time.replace(
            hour=system_settings.cutoff_hour,
            minute=system_settings.cutoff_minute,
            second=0,
            microsecond=0
        )
        
        # Check if cutoff window is enabled and if current time is within business hours
        is_business_hours = True
        if system_settings.cutoff_window_enabled:
            is_business_hours = opening_time <= current_time <= cutoff_time
        
        # Calculate time until cutoff
        if current_time < cutoff_time:
            time_to_cutoff = cutoff_time - current_time
            hours_to_cutoff = time_to_cutoff.seconds // 3600
            minutes_to_cutoff = (time_to_cutoff.seconds % 3600) // 60
        else:
            hours_to_cutoff = 0
            minutes_to_cutoff = 0
        
        # Check for active emergency access
        has_emergency_access = False
        active_emergency_request = EmergencyAccessRequest.objects.filter(
            agent=request.user,
            status='approved',
            access_granted_until__gt=current_time
        ).first()
        
        if active_emergency_request:
            has_emergency_access = True
            emergency_access_remaining = active_emergency_request.access_granted_until - current_time
            emergency_minutes_remaining = emergency_access_remaining.seconds // 60
        else:
            emergency_minutes_remaining = 0
        
        # Handle emergency access request
        if request.method == 'POST' and 'request_emergency_access' in request.POST:
            form = EmergencyAccessRequestForm(request.POST)
            if form.is_valid():
                emergency_request = form.save(commit=False)
                emergency_request.agent = request.user
                emergency_request.location = agent.location
                emergency_request.save()
                messages.success(request, "Emergency access request submitted. An administrator will review your request shortly.")
                return redirect('agent_dashboard')
        else:
            form = EmergencyAccessRequestForm()
        
        # Override time restriction if user has emergency access
        if has_emergency_access:
            is_business_hours = True
        
        # Get or create daily data
        daily_data, created = DailyAgentData.objects.get_or_create(
            location=agent.location,
            date=today,
            defaults={
                'previous_day_balance': 0,
                'cash_delivered_today': 0,
                'payout_at_3pm': 0,
                'cash_position_at_3pm': 0,
                'projected_ending_position': 0,
                'projected_next_day_amount': 0
            }
        )
        
        # Check if EOD report exists for today
        has_eod_report = False
        eod_report = None
        
        try:
            eod_report = EODReport.objects.get(
                location=agent.location,
                processing_date=today
            )
            has_eod_report = True
        except EODReport.DoesNotExist:
            pass
        
        # Get recent EOD reports
        recent_reports = EODReport.objects.filter(
            location=agent.location
        ).order_by('-processing_date')[:5]  # Last 5 reports
        
        # Get notifications (placeholder - to be implemented)
        notifications = []

        # Get pending emergency requests
        pending_emergency_request = EmergencyAccessRequest.objects.filter(
            agent=request.user,
            status='pending'
        ).exists()
        
        context = {
            'agent': agent,
            'today': today,
            'current_time': current_time,
            'is_business_hours': is_business_hours,
            'opening_time': opening_time,
            'cutoff_time': cutoff_time,
            'hours_to_cutoff': hours_to_cutoff,
            'minutes_to_cutoff': minutes_to_cutoff,
            'daily_data': daily_data,
            'has_eod_report': has_eod_report,
            'eod_report': eod_report,
            'recent_reports': recent_reports,
            'notifications': notifications,
            'has_emergency_access': has_emergency_access,
            'emergency_minutes_remaining': emergency_minutes_remaining,
            'emergency_access_form': form,
            'pending_emergency_request': pending_emergency_request,
        }
        
        return render(request, 'core/agent_dashboard.html', context)
        
    except AgentProfile.DoesNotExist:
        messages.error(request, "You don't have an agent profile. Please contact an administrator.")
        return redirect('home')

@login_required
def request_cash(request):
    try:
        agent = AgentProfile.objects.get(user=request.user)
        
        if request.method == 'POST':
            form = CashRequestForm(request.POST)
            if form.is_valid():
                cash_request = form.save(commit=False)
                cash_request.location = agent.location
                cash_request.save()
                messages.success(request, "Cash request submitted successfully")
                return redirect('agent_dashboard')
            else:
                # Handle invalid form case
                return render(request, 'core/request_cash.html', {'form': form})
        else:
            form = CashRequestForm()
            return render(request, 'core/request_cash.html', {'form': form})
            
    except AgentProfile.DoesNotExist:
        messages.error(request, "You don't have an agent profile. Please contact an administrator.")
        return redirect('home')

@login_required
@user_passes_test(lambda u: u.is_staff)
def approve_cash_request(request, request_id):
    # Get the cash request
    cash_request = get_object_or_404(CashRequest, id=request_id)
    
    # Prepare statistics for the template
    location_stats = {
        'current_balance': getattr(cash_request.location, 'current_balance', 0),
        'working_day_limit': getattr(cash_request.location, 'daily_limit', 0),
        'position_percentage': 0,
        'requests_this_month': 0,
        'total_delivered_this_month': 0,
        'average_request_amount': 0,
        'last_request_date': None
    }
    
    # Calculate percentage if both values exist
    if hasattr(cash_request.location, 'current_balance') and hasattr(cash_request.location, 'daily_limit'):
        if cash_request.location.daily_limit > 0:
            percentage = (cash_request.location.current_balance / cash_request.location.daily_limit) * 100
            location_stats['position_percentage'] = min(int(percentage), 100)
    
    # Get request counts if the fields exist
    if hasattr(CashRequest, 'request_date'):
        # Count requests this month
        location_stats['requests_this_month'] = CashRequest.objects.filter(
            location=cash_request.location,
            request_date__month=datetime.now().month,
            request_date__year=datetime.now().year
        ).count()
        
        # Get last request date
        last_request = CashRequest.objects.filter(
            location=cash_request.location
        ).exclude(id=request_id).order_by('-request_date').first()
        
        if last_request:
            location_stats['last_request_date'] = last_request.request_date
    
    # Handle form submission
    if request.method == 'POST':
        # Log all POST data for debugging
        print(f"POST data: {request.POST}")
        
        # Get the decision from the form
        decision = request.POST.get('decision', '')
        action = request.POST.get('action', decision)  # Fallback to decision if action is not present
        
        print(f"Decision: {decision}, Action: {action}")
        
        if action == 'approve' or decision == 'approve':
            try:
                print("Processing approval...")
                
                # Get form data
                approved_jmd = request.POST.get('approved_jmd_amount', '0') or '0'
                approved_usd = request.POST.get('approved_usd_amount', '0') or '0'
                delivery_date_str = request.POST.get('delivery_date')
                notes = request.POST.get('approval_notes', '')
                
                # Parse delivery date
                try:
                    if delivery_date_str:
                        delivery_date = datetime.strptime(delivery_date_str, '%Y-%m-%d').date()
                    else:
                        delivery_date = datetime.now().date()
                except ValueError:
                    print(f"Invalid date format: {delivery_date_str}")
                    delivery_date = datetime.now().date()
                
                print(f"Data for approval: JMD={approved_jmd}, USD={approved_usd}, date={delivery_date}")
                
                # Update cash request
                cash_request.status = 'approved'
                cash_request.delivery_date = delivery_date
                
                if hasattr(cash_request, 'notes'):
                    cash_request.notes = notes
                
                if hasattr(cash_request, 'approved_by'):
                    cash_request.approved_by = request.user
                
                if hasattr(cash_request, 'approved_at'):
                    cash_request.approved_at = timezone.now()
                
                cash_request.save()
                print(f"Cash request saved: {cash_request.id}, status={cash_request.status}")
                
                # Create delivery record
                try:
                    jmd_amount = float(approved_jmd)
                    usd_amount = float(approved_usd)
                    
                    delivery = CashDelivery.objects.create(
                        location=cash_request.location,
                        cash_request=cash_request,
                        date=delivery_date,
                        jmd_amount=jmd_amount,
                        usd_amount=usd_amount
                    )
                    
                    print(f"Created delivery: {delivery}")
                    messages.success(request, f"Cash request #{cash_request.id} has been approved and delivery has been scheduled.")
                
                except Exception as e:
                    print(f"Error creating delivery: {e}")
                    import traceback
                    traceback.print_exc()
                    messages.warning(request, f"Request approved but error creating delivery: {e}")
                
                return redirect('admin_dashboard')
                
            except Exception as e:
                print(f"Error in approval process: {e}")
                import traceback
                traceback.print_exc()
                messages.error(request, f"Error approving request: {e}")
                return redirect('admin_dashboard')
        
        elif action == 'reject' or decision == 'reject':
            try:
                print("Processing rejection...")
                
                # Get rejection reason
                rejection_reason = request.POST.get('rejection_reason', '')
                
                # Update request
                cash_request.status = 'rejected'
                
                # Add rejection reason
                if hasattr(cash_request, 'rejection_reason'):
                    cash_request.rejection_reason = rejection_reason
                elif hasattr(cash_request, 'notes'):
                    cash_request.notes = f"REJECTED: {rejection_reason}"
                
                # Set rejection metadata
                if hasattr(cash_request, 'rejected_by'):
                    cash_request.rejected_by = request.user
                if hasattr(cash_request, 'rejected_at'):
                    cash_request.rejected_at = timezone.now()
                
                cash_request.save()
                print(f"Cash request rejected: {cash_request.id}")
                messages.success(request, f"Cash request #{cash_request.id} has been rejected.")
                
                return redirect('admin_dashboard')
                
            except Exception as e:
                print(f"Error in rejection process: {e}")
                import traceback
                traceback.print_exc()
                messages.error(request, f"Error rejecting request: {e}")
                return redirect('admin_dashboard')
        
        else:
            print(f"Unknown action or decision: action={action}, decision={decision}")
            messages.warning(request, "No clear action specified. Please try again.")
            return redirect('admin_dashboard')
    
    # Render the template
    context = {
        'cash_request': cash_request,
        'location_stats': location_stats,
    }
    
    return render(request, 'core/approve_cash_request.html', context)

@login_required
def verify_cash_delivery(request, delivery_id):
    delivery = get_object_or_404(CashDelivery, id=delivery_id)
    
    # Verify user belongs to the correct location
    try:
        agent = AgentProfile.objects.get(user=request.user)
        if agent.location != delivery.location:
            messages.error(request, "You can only verify deliveries for your location")
            return redirect('agent_dashboard')
    except AgentProfile.DoesNotExist:
        messages.error(request, "You don't have an agent profile")
        return redirect('home')
    
    if request.method == 'POST':
        form = CashVerificationForm(request.POST, instance=delivery)
        if form.is_valid():
            form.save(user=request.user)
            messages.success(request, "Cash delivery verified successfully")
            return redirect('agent_dashboard')
    else:
        form = CashVerificationForm(instance=delivery)
    
    return render(request, 'core/verify_cash_delivery.html', {
        'form': form,
        'delivery': delivery
    })

@login_required
def submit_eod_report(request):
    from django.utils import timezone
    from decimal import Decimal
    from datetime import datetime, timedelta
    from .models import (
        AgentProfile, Location, EODReport, TellerBalance, DailyAgentData, 
        DenominationBreakdown, TellerVariance
    )
    
    user = request.user
    
    try:
        agent_profile = AgentProfile.objects.get(user=user)
        location = agent_profile.location
    except AgentProfile.DoesNotExist:
        messages.error(request, "Agent profile not found. Please contact an administrator.")
        return redirect('agent_dashboard')
    
    # Get the daily agent data for today for expected balance calculation
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    
    try:
        # Modified to filter by location only, not by agent
        daily_data = DailyAgentData.objects.get(
            location=location,
            date=today
        )
        expected_balance = daily_data.previous_day_balance + daily_data.cash_delivered_today
    except DailyAgentData.DoesNotExist:
        expected_balance = 0
        daily_data = None
    
    # Check for existing report
    existing_report = None
    teller_balances = []
    teller_variances = []
    
    if request.method == 'GET':
        process_date = request.GET.get('date', yesterday)
        if isinstance(process_date, str):
            try:
                process_date = datetime.strptime(process_date, '%Y-%m-%d').date()
            except ValueError:
                process_date = yesterday
    else:
        process_date = yesterday
    
    try:
        existing_report = EODReport.objects.get(
            agent=user,
            location=location,
            processing_date=process_date
        )
        # Get existing denominations
        jmd_denoms = DenominationBreakdown.objects.filter(
            eod_report=existing_report,
            currency='JMD'
        ).first()
        
        usd_denoms = DenominationBreakdown.objects.filter(
            eod_report=existing_report,
            currency='USD'
        ).first()
        
        # Get existing teller balances
        teller_balances = TellerBalance.objects.filter(eod_report=existing_report)
        
        # Get existing teller variances
        teller_variances = TellerVariance.objects.filter(eod_report=existing_report)
        
        # Pre-populate form with existing data
        initial_data = {
            'processing_date': existing_report.processing_date,
            'closing_balance': existing_report.closing_balance,
            'funds_from_bxp_webex': existing_report.funds_from_bxp_webex,
            'cash_sent_to_courier': existing_report.cash_sent_to_courier,
            'courier_usd_amount': existing_report.courier_usd_amount,
            'courier_usd_receipt': existing_report.courier_usd_receipt,
            'courier_jmd_amount': existing_report.courier_jmd_amount,
            'courier_jmd_receipt': existing_report.courier_jmd_receipt,
            'all_tellers_balanced': existing_report.all_tellers_balanced,
            'notes': existing_report.notes,
            'confirmation': existing_report.confirmation,
        }
        
        # Add denomination data if available
        if jmd_denoms:
            initial_data.update({
                'jmd_5000_count': jmd_denoms.denomination_5000_count,
                'jmd_1000_count': jmd_denoms.denomination_1000_count,
                'jmd_500_count': jmd_denoms.denomination_500_count,
                'jmd_100_count': jmd_denoms.denomination_100_count,
                'jmd_50_count': jmd_denoms.denomination_50_count,
                'jmd_coins_amount': jmd_denoms.coins_amount,
            })
            
        if usd_denoms:
            initial_data.update({
                'usd_100_count': usd_denoms.denomination_100_count,
                'usd_50_count': usd_denoms.denomination_50_count,
                'usd_20_count': usd_denoms.denomination_20_count,
                'usd_10_count': usd_denoms.denomination_10_count,
                'usd_small_amount': usd_denoms.small_bills_coins_amount,
            })
            
        from .forms import EODReportForm
        form = EODReportForm(initial=initial_data)
    except EODReport.DoesNotExist:
        from .forms import EODReportForm
        form = EODReportForm(initial={'processing_date': process_date})
    
    if request.method == 'POST':
        from .forms import EODReportForm
        form = EODReportForm(request.POST)
        
        if form.is_valid():
            processing_date = form.cleaned_data['processing_date']
            
            # Check if report exists for this date
            report, created = EODReport.objects.update_or_create(
                agent=user,
                location=location,
                processing_date=processing_date,
                defaults={
                    'closing_balance': form.cleaned_data['closing_balance'],
                    'funds_from_bxp_webex': form.cleaned_data['funds_from_bxp_webex'] or 0,
                    'cash_sent_to_courier': form.cleaned_data['cash_sent_to_courier'],
                    'courier_usd_amount': form.cleaned_data['courier_usd_amount'] if form.cleaned_data['cash_sent_to_courier'] else None,
                    'courier_usd_receipt': form.cleaned_data['courier_usd_receipt'] if form.cleaned_data['cash_sent_to_courier'] else None,
                    'courier_jmd_amount': form.cleaned_data['courier_jmd_amount'] if form.cleaned_data['cash_sent_to_courier'] else None,
                    'courier_jmd_receipt': form.cleaned_data['courier_jmd_receipt'] if form.cleaned_data['cash_sent_to_courier'] else None,
                    'all_tellers_balanced': form.cleaned_data['all_tellers_balanced'],
                    'notes': form.cleaned_data['notes'],
                    'confirmation': form.cleaned_data['confirmation'],
                    'submitted': True
                }
            )
            
            # Handle JMD Denomination Breakdown
            jmd_denoms, _ = DenominationBreakdown.objects.update_or_create(
                eod_report=report,
                currency='JMD',
                defaults={
                    'denomination_5000_count': form.cleaned_data['jmd_5000_count'] or 0,
                    'denomination_1000_count': form.cleaned_data['jmd_1000_count'] or 0,
                    'denomination_500_count': form.cleaned_data['jmd_500_count'] or 0,
                    'denomination_100_count': form.cleaned_data['jmd_100_count'] or 0,
                    'denomination_50_count': form.cleaned_data['jmd_50_count'] or 0,
                    'coins_amount': form.cleaned_data['jmd_coins_amount'] or 0,
                }
            )
            
            # Handle USD Denomination Breakdown
            usd_denoms, _ = DenominationBreakdown.objects.update_or_create(
                eod_report=report,
                currency='USD',
                defaults={
                    'denomination_100_count': form.cleaned_data['usd_100_count'] or 0,
                    'denomination_50_count': form.cleaned_data['usd_50_count'] or 0,
                    'denomination_20_count': form.cleaned_data['usd_20_count'] or 0,
                    'denomination_10_count': form.cleaned_data['usd_10_count'] or 0,
                    'small_bills_coins_amount': form.cleaned_data['usd_small_amount'] or 0,
                }
            )
            
            # Process teller balances
            teller_names = request.POST.getlist('teller_name[]')
            teller_jmd_amounts = request.POST.getlist('teller_jmd[]')
            teller_usd_amounts = request.POST.getlist('teller_usd[]')
            
            # First delete existing teller balances for this report
            TellerBalance.objects.filter(eod_report=report).delete()
            
            # Then create new teller balances
            for i in range(len(teller_names)):
                if i < len(teller_jmd_amounts) and i < len(teller_usd_amounts) and teller_names[i].strip():
                    TellerBalance.objects.create(
                        eod_report=report,
                        teller_name=teller_names[i],
                        jmd_amount=teller_jmd_amounts[i] or 0,
                        usd_amount=teller_usd_amounts[i] or 0
                    )
            
            # Process teller variances if tellers were not all balanced
            if not form.cleaned_data['all_tellers_balanced']:
                teller_numbers = request.POST.getlist('teller_number[]')
                teller_variances = request.POST.getlist('teller_variance[]')
                
                # Delete existing variances
                TellerVariance.objects.filter(eod_report=report).delete()
                
                # Calculate total variance
                total_variance = Decimal('0.00')
                
                # Create new variances
                for i in range(len(teller_numbers)):
                    if i < len(teller_variances) and teller_numbers[i].strip():
                        variance_amount = Decimal(teller_variances[i] or 0)
                        total_variance += variance_amount
                        
                        TellerVariance.objects.create(
                            eod_report=report,
                            teller_number=teller_numbers[i],
                            variance=variance_amount
                        )
                
                # Update total variance on the report
                report.total_variance = total_variance
                report.save()
            
            # Update daily data if this is today's report
            if processing_date == today and daily_data:
                # Create or update the daily data for today
                # No 'agent' field here since it doesn't exist in the model
                daily_data.closing_balance = form.cleaned_data['closing_balance']
                # Don't set daily_data.eod_report if that field doesn't exist
                daily_data.save()
            
            if created:
                messages.success(request, f"EOD Report for {processing_date.strftime('%d %b, %Y')} submitted successfully.")
            else:
                messages.success(request, f"EOD Report for {processing_date.strftime('%d %b, %Y')} updated successfully.")
            
            return redirect('agent_dashboard')
        else:
            messages.error(request, "Please correct the errors in the form.")
    
    context = {
        'form': form,
        'location': location,
        'expected_balance': expected_balance,
        'daily_data': daily_data,
        'existing_report': existing_report,
        'teller_balances': teller_balances,
        'teller_variances': teller_variances,
    }
    
    return render(request, 'core/submit_eod_report.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def location_details(request, location_id):
    location = get_object_or_404(Location, id=location_id)
    
    # Get location limits
    limits, created = LocationLimit.objects.get_or_create(
        location=location,
        defaults={
            'insurance_limit': 5000000,
            'eod_vault_limit': 3000000,
            'working_day_limit': 2000000
        }
    )
    
    # Get cash requests for this location
    cash_requests = CashRequest.objects.filter(
        location=location
    ).order_by('-request_date')[:10]
    
    # Get EOD reports
    eod_reports = EODReport.objects.filter(
        location=location
    ).order_by('-processing_date')[:10]
    
    # Get cash position data
    today = timezone.now().date()
    daily_data, created = DailyAgentData.objects.get_or_create(
        location=location,
        date=today,
        defaults={
            'previous_day_balance': 0,
            'cash_delivered_today': 0,
            'payout_at_3pm': 0,
            'cash_position_at_3pm': 0,
            'projected_ending_position': 0,
            'projected_next_day_amount': 0
        }
    )
    
    context = {
        'location': location,
        'limits': limits,
        'cash_requests': cash_requests,
        'eod_reports': eod_reports,
        'daily_data': daily_data
    }
    
    return render(request, 'core/location_details.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def manage_users(request):
    # Get all users except the current user
    users_with_locations = User.objects.exclude(id=request.user.id).select_related('agentprofile__location')
    
    # Get all locations for the dropdown
    locations = Location.objects.all().order_by('name')
    
    context = {
        'users': users_with_locations,
        'locations': locations,
    }
    
    return render(request, 'core/manage_users.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def create_user(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        location_id = request.POST.get('location')
        is_admin = request.POST.get('is_admin') == 'on'
        
        try:
            # Create the user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            
            if is_admin:
                user.is_staff = True
                user.save()
            
            # Assign location if provided
            if location_id:
                location = Location.objects.get(id=location_id)
                AgentProfile.objects.create(user=user, location=location)
                
            messages.success(request, f"User '{username}' created successfully.")
            
        except Exception as e:
            messages.error(request, f"Error creating user: {str(e)}")
        
        return redirect('manage_users')
    
    return redirect('manage_users')

@login_required
@user_passes_test(lambda u: u.is_staff)
def promote_user(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        
        # Don't allow promoting superusers
        if not user.is_superuser:
            user.is_staff = True
            user.save()
            messages.success(request, f"{user.username} promoted to admin successfully.")
        
    return redirect('manage_users')

@login_required
@user_passes_test(lambda u: u.is_staff)
def demote_user(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        
        # Don't allow demoting superusers
        if not user.is_superuser:
            user.is_staff = False
            user.save()
            messages.success(request, f"{user.username} demoted to agent successfully.")
        
    return redirect('manage_users')

@login_required
@user_passes_test(lambda u: u.is_staff)
def assign_location(request, user_id=None):
    # Get user_id from URL parameter or POST data
    if user_id is None:
        user_id = request.POST.get('user_id')
    
    # GET request from the URL parameter (direct link case)
    if request.method == 'GET' and 'location' in request.GET:
        location_id = request.GET.get('location')
        try:
            user = get_object_or_404(User, id=user_id)
            location = get_object_or_404(Location, id=location_id)
            
            # Get current timestamp for created_at and updated_at fields
            current_time = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Update the user's location
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM core_agentprofile WHERE user_id = %s", [user_id])
                cursor.execute(
                    "INSERT INTO core_agentprofile (user_id, location_id, created_at, updated_at) VALUES (%s, %s, %s, %s)",
                    [user_id, location_id, current_time, current_time]
                )
            connection.commit()
            
            messages.success(request, f"Assigned {user.username} to {location.name}.")
            return redirect(f'/system-admin/manage-users/?updated_user={user_id}')
        except Exception as e:
            print(f"Error: {str(e)}")
            messages.error(request, f"Error assigning location: {str(e)}")
            return redirect('manage_users')
    
    # Normal POST request case
    if request.method == 'POST':
        try:
            if not user_id:
                raise ValueError("No user ID provided")
            
            user = get_object_or_404(User, id=user_id)
            location_id = request.POST.get('location')
            
            if not location_id:
                raise ValueError("No location selected")
            
            location = get_object_or_404(Location, id=location_id)
            
            # Get current timestamp for created_at and updated_at fields
            current_time = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Simple direct SQL approach
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM core_agentprofile WHERE user_id = %s", [user_id])
                cursor.execute(
                    "INSERT INTO core_agentprofile (user_id, location_id, created_at, updated_at) VALUES (%s, %s, %s, %s)",
                    [user_id, location_id, current_time, current_time]
                )
            
            # Force commit to ensure it's saved
            connection.commit()
            
            # Success message
            messages.success(request, f"Assigned {user.username} to {location.name}.")
            
            # Explicitly return to the manage_users page with a proper path
            return redirect('/system-admin/manage-users/?updated_user=' + str(user_id))
            
        except Exception as e:
            print(f"Assignment Error: {str(e)}")
            import traceback
            traceback.print_exc()
            messages.error(request, f"Error assigning location: {str(e)}")
    
    # Fallback redirect
    return redirect('manage_users')

@login_required
@user_passes_test(lambda u: u.is_staff)
def reset_password(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        
        # Generate a random password
        import string
        import random
        chars = string.ascii_letters + string.digits + string.punctuation
        new_password = ''.join(random.choice(chars) for _ in range(10))
        
        user.set_password(new_password)
        user.save()
        
        messages.success(
            request, 
            f"Password for {user.username} has been reset to: {new_password}"
            f"<br><strong>Please copy this password now - it won't be shown again.</strong>",
            extra_tags='safe'
        )
        
    return redirect('manage_users')

@login_required
@user_passes_test(lambda u: u.is_staff)
def deactivate_user(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        
        # Don't allow deactivating superusers
        if not user.is_superuser:
            user.is_active = False
            user.save()
            messages.success(request, f"User {user.username} has been deactivated.")
        
    return redirect('manage_users')

@login_required
@user_passes_test(lambda u: u.is_staff)
def generate_report(request):
    # Placeholder for report generation logic
    return render(request, 'core/generate_report.html')

def signup(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Note: We don't create an AgentProfile here
            # Administrator will assign users to locations
            return redirect('signup_success')
    else:
        form = SignupForm()
    return render(request, 'core/signup.html', {'form': form})

def signup_success(request):
    return render(request, 'core/signup_success.html')

def custom_logout(request):
    """
    Custom logout view to ensure proper session cleanup and redirect
    """
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect('landing_page')

@login_required
@user_passes_test(lambda u: u.is_staff)
def debug_profiles(request):
    profiles = AgentProfile.objects.select_related('user', 'location').all()
    users = User.objects.select_related('agentprofile__location').all()
    
    return render(request, 'core/debug_profiles.html', {
        'profiles': profiles,
        'users': users
    })

@login_required
@user_passes_test(lambda u: u.is_staff)
def user_profile_debug(request, user_id):
    # Get the user object
    user = get_object_or_404(User, id=user_id)
    
    # Get profile data directly from the database
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT ap.id, ap.user_id, ap.location_id, l.name FROM core_agentprofile ap " +
            "JOIN core_location l ON ap.location_id = l.id " +
            "WHERE ap.user_id = %s",
            [user_id]
        )
        profile_data = cursor.fetchall()
    
    # Get user data through the ORM
    try:
        agent_profile = AgentProfile.objects.get(user=user)
        orm_data = {
            'profile_id': agent_profile.id,
            'user_id': agent_profile.user_id,
            'location_id': agent_profile.location_id,
            'location_name': agent_profile.location.name
        }
    except AgentProfile.DoesNotExist:
        orm_data = "No profile found in ORM"
    
    # Get location name via the property
    location_name = user.get_location_name()
    
    # Create diagnostic data
    debug_data = {
        'user_id': user.id,
        'username': user.username,
        'direct_sql_profile': profile_data,
        'orm_profile': orm_data,
        'get_location_name': location_name
    }
    
    return HttpResponse(
        f"<pre>{json.dumps(debug_data, indent=4)}</pre>", 
        content_type="text/html"
    )

@login_required
@user_passes_test(lambda u: u.is_staff)
def assign_location_direct(request, user_id):
    """Ultra-simplified direct assignment view that works with both GET and POST"""
    print(f"===> assign_location_direct called with user_id={user_id}")
    print(f"===> Request method: {request.method}")
    print(f"===> GET params: {request.GET}")
    print(f"===> POST params: {request.POST}")
    
    try:
        # Get location ID from GET or POST
        location_id = request.GET.get('location') or request.POST.get('location')
        print(f"===> Location ID: {location_id}")
        
        if not location_id:
            raise ValueError("No location ID provided")
        
        # Get the user and location
        user = User.objects.get(id=user_id)
        location = Location.objects.get(id=location_id)
        
        print(f"===> Found user: {user.username} (ID: {user_id})")
        print(f"===> Found location: {location.name} (ID: {location_id})")
        
        # Get current timestamp for created_at and updated_at fields
        current_time = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Execute SQL directly (proven approach)
        with connection.cursor() as cursor:
            # Remove any existing profile
            cursor.execute("DELETE FROM core_agentprofile WHERE user_id = %s", [user_id])
            # Create new profile with timestamps
            cursor.execute(
                "INSERT INTO core_agentprofile (user_id, location_id, created_at, updated_at) VALUES (%s, %s, %s, %s)",
                [user_id, location_id, current_time, current_time]
            )
        
        # Force commit
        connection.commit()
        
        # Show success message
        messages.success(
            request, 
            f"✅ Successfully assigned {user.username} to {location.name}"
        )
        
        print(f"===> SUCCESS: {user.username} assigned to {location.name}")
        
        # Always redirect to the manage users page
        return redirect('/system-admin/manage-users/?updated_user=' + str(user_id))
        
    except Exception as e:
        print(f"===> ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        messages.error(request, f"Error: {str(e)}")
        
        return redirect('/system-admin/manage-users/')

@login_required
@user_passes_test(lambda u: u.is_staff)
def delete_user(request, user_id):
    if request.method == 'POST':
        try:
            user = get_object_or_404(User, id=user_id)
            
            # Don't allow deleting superusers
            if user.is_superuser:
                messages.error(request, "Superusers cannot be deleted.")
                return redirect('manage_users')
                
            # Store username for success message
            username = user.username
            
            # Delete any agent profile first (to avoid foreign key constraints)
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM core_agentprofile WHERE user_id = %s", [user_id])
                connection.commit()
            
            # Delete the user
            user.delete()
            
            messages.success(request, f"User '{username}' has been permanently deleted.")
            
        except Exception as e:
            print(f"Error deleting user: {str(e)}")
            messages.error(request, f"Error deleting user: {str(e)}")
    
    return redirect('manage_users')

class CustomLoginView(LoginView):
    template_name = 'registration/login.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add extra context to verify the view is being used
        context['using_custom_login'] = True
        return context

@login_required
def view_eod_reports(request):
    """View to list all EOD reports for admins."""
    if not request.user.is_staff:
        messages.error(request, "You don't have permission to access this page.")
        return redirect('dashboard')
    
    # Get the selected date from query params, default to today
    selected_date = request.GET.get('date')
    if selected_date:
        try:
            selected_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
        except ValueError:
            selected_date = timezone.now().date()
    else:
        selected_date = timezone.now().date()
    
    # Filter reports by date if specified
    if selected_date:
        reports_list = EODReport.objects.filter(
            processing_date=selected_date
        ).order_by('-created_at')
    else:
        reports_list = EODReport.objects.all().order_by('-processing_date', '-created_at')
    
    # Count metrics
    reports_count = reports_list.count()
    pending_count = reports_list.filter(status='pending').count()
    variance_count = reports_list.exclude(variance=0).count()
    
    # Pagination
    paginator = Paginator(reports_list, 10)  # Show 10 reports per page
    page = request.GET.get('page')
    try:
        reports = paginator.page(page)
    except PageNotAnInteger:
        reports = paginator.page(1)
    except EmptyPage:
        reports = paginator.page(paginator.num_pages)
    
    context = {
        'reports': reports,
        'reports_count': reports_count,
        'pending_count': pending_count,
        'variance_count': variance_count,
        'selected_date': selected_date,
    }
    
    return render(request, 'core/view_eod_reports.html', context)

@login_required
def review_eod_report(request, report_id):
    """View to review a specific EOD report."""
    if not request.user.is_staff:
        messages.error(request, "You don't have permission to access this page.")
        return redirect('view_eod_reports')
    
    try:
        report = EODReport.objects.get(id=report_id)
    except EODReport.DoesNotExist:
        messages.error(request, "Report not found.")
        return redirect('view_eod_reports')
    
    # Calculate expected balance
    expected_balance = report.opening_balance + report.cash_delivered
    
    # Get denominations for JMD and USD
    jmd_denominations = Adjustment.objects.filter(
        eod_report=report,
        type='denomination',
        currency='JMD'
    )
    
    usd_denominations = Adjustment.objects.filter(
        eod_report=report,
        type='denomination',
        currency='USD'
    )
    
    # Calculate totals
    jmd_total = jmd_denominations.aggregate(total=Sum('amount'))['total'] or 0
    usd_total = usd_denominations.aggregate(total=Sum('amount'))['total'] or 0
    
    # Get teller balances
    teller_balances = TellerBalance.objects.filter(eod_report=report)
    teller_jmd_total = teller_balances.aggregate(total=Sum('jmd_amount'))['total'] or 0
    teller_usd_total = teller_balances.aggregate(total=Sum('usd_amount'))['total'] or 0
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'approve':
            report.status = 'approved'
            report.reviewed_by = request.user
            report.review_notes = request.POST.get('review_notes', '')
            report.save()
            
            messages.success(request, "EOD report has been approved.")
            return redirect('view_eod_reports')
        
        elif action == 'reject':
            report.status = 'rejected'
            report.reviewed_by = request.user
            report.review_notes = request.POST.get('review_notes', '')
            report.save()
            
            messages.success(request, "EOD report has been rejected.")
            return redirect('view_eod_reports')
        
        elif action == 'reopen' and request.user.has_perm('core.change_eodreport'):
            report.status = 'pending'
            report.reviewed_by = None
            report.review_notes = ''
            report.save()
            
            messages.success(request, "EOD report has been reopened for review.")
            return redirect('review_eod_report', report_id=report.id)
    
    context = {
        'report': report,
        'expected_balance': expected_balance,
        'jmd_denominations': jmd_denominations,
        'usd_denominations': usd_denominations,
        'jmd_total': jmd_total,
        'usd_total': usd_total,
        'teller_balances': teller_balances,
        'teller_jmd_total': teller_jmd_total,
        'teller_usd_total': teller_usd_total,
    }
    
    return render(request, 'core/review_eod_report.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_view_eod_reports(request):
    """View for admins to see all submitted EOD reports"""
    # Get filter parameters
    location_id = request.GET.get('location')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Base queryset with prefetched related models
    reports = EODReport.objects.select_related('agent', 'location').prefetch_related(
        'denomination_breakdowns', 'teller_balances', 'teller_variances'
    ).order_by('-processing_date')
    
    # Apply filters
    if location_id:
        reports = reports.filter(location_id=location_id)
    
    if start_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            reports = reports.filter(processing_date__gte=start_date)
        except ValueError:
            pass
    
    if end_date:
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            reports = reports.filter(processing_date__lte=end_date)
        except ValueError:
            pass
    
    # Get all locations for the filter dropdown
    locations = Location.objects.all().order_by('name')
    
    # Pagination
    paginator = Paginator(reports, 20)  # Show 20 reports per page
    page = request.GET.get('page')
    try:
        reports_page = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page
        reports_page = paginator.page(1)
    except EmptyPage:
        # If page is out of range, deliver last page
        reports_page = paginator.page(paginator.num_pages)
    
    context = {
        'reports': reports_page,
        'locations': locations,
        'selected_location': location_id,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'core/admin_view_eod_reports.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def admin_view_eod_report_detail(request, report_id):
    """View for admins to see details of a specific EOD report"""
    report = get_object_or_404(
        EODReport.objects.select_related('agent', 'location').prefetch_related(
            'denomination_breakdowns', 'teller_balances', 'teller_variances'
        ),
        id=report_id
    )
    
    # Get denomination breakdowns
    jmd_denomination = report.denomination_breakdowns.filter(currency='JMD').first()
    usd_denomination = report.denomination_breakdowns.filter(currency='USD').first()
    
    # Calculate individual denomination amounts
    denomination_amounts = {}
    
    if jmd_denomination:
        denomination_amounts.update({
            'jmd_5000_amount': jmd_denomination.denomination_5000_count * 5000 if jmd_denomination.denomination_5000_count else 0,
            'jmd_1000_amount': jmd_denomination.denomination_1000_count * 1000 if jmd_denomination.denomination_1000_count else 0,
            'jmd_500_amount': jmd_denomination.denomination_500_count * 500 if jmd_denomination.denomination_500_count else 0,
            'jmd_100_amount': jmd_denomination.denomination_100_count * 100 if jmd_denomination.denomination_100_count else 0,
            'jmd_50_amount': jmd_denomination.denomination_50_count * 50 if jmd_denomination.denomination_50_count else 0,
        })
    
    if usd_denomination:
        denomination_amounts.update({
            'usd_100_amount': usd_denomination.denomination_100_count * 100 if usd_denomination.denomination_100_count else 0,
            'usd_50_amount': usd_denomination.denomination_50_count * 50 if usd_denomination.denomination_50_count else 0,
            'usd_20_amount': usd_denomination.denomination_20_count * 20 if usd_denomination.denomination_20_count else 0,
            'usd_10_amount': usd_denomination.denomination_10_count * 10 if usd_denomination.denomination_10_count else 0,
        })
    
    context = {
        'report': report,
        'jmd_denomination': jmd_denomination,
        'usd_denomination': usd_denomination,
        'teller_balances': report.teller_balances.all(),
        'teller_variances': report.teller_variances.all(),
        'denomination_amounts': denomination_amounts,
    }
    
    return render(request, 'core/admin_view_eod_report_detail.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def review_emergency_requests(request):
    """View for admins to review emergency access requests."""
    # Get all pending emergency access requests
    pending_requests = EmergencyAccessRequest.objects.filter(status='pending')
    
    # Get all recent requests (for history)
    recent_requests = EmergencyAccessRequest.objects.exclude(status='pending').order_by('-requested_at')[:10]
    
    context = {
        'pending_requests': pending_requests,
        'recent_requests': recent_requests,
    }
    
    return render(request, 'core/review_emergency_requests.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def handle_emergency_request(request, request_id):
    """Handle approval or denial of emergency access requests."""
    # Get the emergency request
    emergency_request = get_object_or_404(EmergencyAccessRequest, id=request_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Update the request based on admin action
        if action == 'approve':
            # Grant 30 minutes of emergency access
            emergency_request.status = 'approved'
            emergency_request.reviewed_by = request.user
            emergency_request.reviewed_at = timezone.now()
            emergency_request.access_granted_until = timezone.now() + timedelta(minutes=30)
            emergency_request.save()
            
            messages.success(request, f"Emergency access granted to {emergency_request.agent.username} for 30 minutes.")
        
        elif action == 'deny':
            emergency_request.status = 'denied'
            emergency_request.reviewed_by = request.user
            emergency_request.reviewed_at = timezone.now()
            emergency_request.save()
            
            messages.warning(request, f"Emergency access request from {emergency_request.agent.username} has been denied.")
    
    return redirect('review_emergency_requests')

@login_required
@user_passes_test(lambda u: u.is_staff)
def manage_system_settings(request):
    """View for managing system-wide settings."""
    settings = SystemSettings.get_settings()
    
    if request.method == 'POST':
        # Update settings
        settings.cutoff_window_enabled = request.POST.get('cutoff_window_enabled') == 'on'
        settings.cutoff_hour = int(request.POST.get('cutoff_hour', 15))
        settings.cutoff_minute = int(request.POST.get('cutoff_minute', 0))
        settings.business_hours_start = int(request.POST.get('business_hours_start', 8))
        settings.business_hours_start_minute = int(request.POST.get('business_hours_start_minute', 0))
        settings.emergency_access_duration = int(request.POST.get('emergency_access_duration', 60))
        settings.updated_by = request.user
        settings.save()
        
        messages.success(request, "System settings have been updated successfully.")
        return redirect('manage_system_settings')
    
    context = {
        'settings': settings,
    }
    
    return render(request, 'core/manage_system_settings.html', context)