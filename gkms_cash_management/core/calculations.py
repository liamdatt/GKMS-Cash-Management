from datetime import datetime, timedelta
from decimal import Decimal
from .models import DailyAgentData, LocationLimit
from .services import get_eft_balance, get_payout_at_3pm, get_average_payout

def update_daily_agent_data(location, date=None):
    """
    Calculate and update the daily agent data for a location
    """
    if date is None:
        date = datetime.now().date()
    
    # Get previous day's date
    prev_day = date - timedelta(days=1)
    
    # Get data from external systems
    previous_day_balance = get_eft_balance(location.id, prev_day)
    payout_at_3pm = get_payout_at_3pm(location.id, date)
    
    # Get cash delivered today (from our database)
    from .models import CashDelivery
    try:
        delivery = CashDelivery.objects.get(location=location, date=date, verified=True)
        cash_delivered_today = delivery.verified_jmd_amount
    except CashDelivery.DoesNotExist:
        cash_delivered_today = Decimal('0')
    
    # Calculate cash position at 3 PM
    cash_position_at_3pm = previous_day_balance + cash_delivered_today - payout_at_3pm
    
    # Calculate projected ending position
    avg_payout = get_average_payout(location.id, date)
    projected_ending_position = cash_position_at_3pm - avg_payout
    
    # Calculate amount needed tomorrow
    tomorrow_avg_payout = get_average_payout(location.id, date + timedelta(days=1))
    projected_next_day_amount = projected_ending_position - tomorrow_avg_payout
    
    # Check if limits are exceeded
    try:
        limits = LocationLimit.objects.get(location=location)
        exceeds_insurance_limit = projected_next_day_amount > limits.insurance_limit
        exceeds_eod_limit = projected_next_day_amount > limits.eod_vault_limit
        exceeds_working_day_limit = projected_next_day_amount > limits.working_day_limit
    except LocationLimit.DoesNotExist:
        exceeds_insurance_limit = False
        exceeds_eod_limit = False
        exceeds_working_day_limit = False
    
    # Update or create daily data record
    daily_data, created = DailyAgentData.objects.update_or_create(
        location=location,
        date=date,
        defaults={
            'previous_day_balance': previous_day_balance,
            'cash_delivered_today': cash_delivered_today,
            'payout_at_3pm': payout_at_3pm,
            'cash_position_at_3pm': cash_position_at_3pm,
            'projected_ending_position': projected_ending_position,
            'projected_next_day_amount': projected_next_day_amount,
            'exceeds_insurance_limit': exceeds_insurance_limit,
            'exceeds_eod_limit': exceeds_eod_limit,
            'exceeds_working_day_limit': exceeds_working_day_limit,
        }
    )
    
    return daily_data 