from django.contrib import admin
from .models import (
    AgentProfile, Location, LocationLimit, CashDelivery, 
    CashRequest, EODReport, TellerBalance, Adjustment, DailyAgentData,
    TellerVariance, DenominationBreakdown
)

@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'created_at')
    search_fields = ('name', 'address')

@admin.register(AgentProfile)
class AgentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'location', 'phone_number')
    list_filter = ('location',)
    search_fields = ('user__username', 'user__email', 'phone_number')

@admin.register(LocationLimit)
class LocationLimitAdmin(admin.ModelAdmin):
    list_display = ('location', 'insurance_limit', 'eod_vault_limit', 'working_day_limit')

admin.site.register(CashDelivery)
admin.site.register(CashRequest)

@admin.register(DailyAgentData)
class DailyAgentDataAdmin(admin.ModelAdmin):
    list_display = ('location', 'date', 'previous_day_balance', 'cash_delivered_today', 
                   'payout_at_3pm', 'projected_ending_position', 'closing_balance', 'variance')
    list_filter = ('location', 'date')
    search_fields = ('location__name',)
    date_hierarchy = 'date'

class AdjustmentInline(admin.TabularInline):
    model = Adjustment
    extra = 0

class TellerBalanceInline(admin.TabularInline):
    model = TellerBalance
    extra = 0

class TellerVarianceInline(admin.TabularInline):
    model = TellerVariance
    extra = 0

class DenominationBreakdownInline(admin.TabularInline):
    model = DenominationBreakdown
    extra = 0

@admin.register(EODReport)
class EODReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'processing_date', 'closing_balance', 'funds_from_bxp_webex', 
                   'total_variance', 'submitted', 'agent')
    list_filter = ('processing_date', 'location', 'submitted')
    search_fields = ('agent__username', 'location__name')
    inlines = [TellerBalanceInline, TellerVarianceInline, DenominationBreakdownInline, AdjustmentInline]
    readonly_fields = ('created_at', 'updated_at')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('agent', 'location')

@admin.register(Adjustment)
class AdjustmentAdmin(admin.ModelAdmin):
    list_display = ('eod_report', 'type', 'description', 'count', 'amount', 'currency')
    list_filter = ('type', 'currency', 'eod_report__location')
    search_fields = ('description', 'eod_report__location__name')

@admin.register(TellerBalance)
class TellerBalanceAdmin(admin.ModelAdmin):
    list_display = ('eod_report', 'teller_name', 'jmd_amount', 'usd_amount')
    search_fields = ('teller_name', 'eod_report__location__name')