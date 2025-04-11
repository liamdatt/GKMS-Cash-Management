from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Landing and Home URLs
    path('', views.landing_page, name='landing_page'),  # Homepage for visitors
    path('home/', views.home, name='home'),  # Redirects to appropriate dashboard based on user type
    
    # Agent URLs
    path('agent-dashboard/', views.agent_dashboard, name='agent_dashboard'),
    path('request-cash/', views.request_cash, name='request_cash'),
    path('verify-cash-delivery/<int:delivery_id>/', views.verify_cash_delivery, name='verify_cash_delivery'),
    path('submit-eod-report/', views.submit_eod_report, name='submit_eod_report'),
    
    # Admin URLs
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('location/<int:location_id>/', views.location_details, name='location_details'),
    path('approve-cash-request/<int:request_id>/', views.approve_cash_request, name='approve_cash_request'),
    path('generate-report/', views.generate_report, name='generate_report'),
    
    # Authentication URLs
    path('signup/', views.signup, name='signup'),
    path('signup/success/', views.signup_success, name='signup_success'),
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('logout/', views.custom_logout, name='logout'),
    path('system-admin/manage-users/', views.manage_users, name='manage_users'),
    path('system-admin/promote-user/<int:user_id>/', views.promote_user, name='promote_user'),
    path('demote-user/<int:user_id>/', views.demote_user, name='demote_user'),
    path('assign-location/<int:user_id>/', views.assign_location, name='assign_location'),
    path('create-user/', views.create_user, name='create_user'),
    path('reset-password/<int:user_id>/', views.reset_password, name='reset_password'),
    path('deactivate-user/<int:user_id>/', views.deactivate_user, name='deactivate_user'),
    path('system-admin/settings/', views.manage_system_settings, name='manage_system_settings'),
    path('debug-profiles/', views.debug_profiles, name='debug_profiles'),
    path('user-profile-debug/<int:user_id>/', views.user_profile_debug, name='user_profile_debug'),
    path('assign-location/', views.assign_location, name='assign_location_no_id'),
    path('direct-assign/<int:user_id>/', views.assign_location_direct, name='direct_assign'),
    path('delete-user/<int:user_id>/', views.delete_user, name='delete_user'),
    path('agent/submit-eod-report/', views.submit_eod_report, name='submit_eod_report'),
    path('admin/view-eod-reports/', views.view_eod_reports, name='view_eod_reports'),
    path('admin/review-eod-report/<int:report_id>/', views.review_eod_report, name='review_eod_report'),
]

# Report views
urlpatterns += [
    path('reports/view/', views.view_eod_reports, name='view_eod_reports'),
    path('reports/review/<int:report_id>/', views.review_eod_report, name='review_eod_report'),
    path('system-admin/eod-reports/', views.admin_view_eod_reports, name='admin_view_eod_reports'),
    path('system-admin/eod-reports/<int:report_id>/', views.admin_view_eod_report_detail, name='admin_view_eod_report_detail'),
]

# Emergency access routes
urlpatterns += [
    path('request-emergency-access/', views.agent_dashboard, name='request_emergency_access'),
    path('system-admin/emergency-requests/', views.review_emergency_requests, name='review_emergency_requests'),
    path('system-admin/emergency-requests/<int:request_id>/', views.handle_emergency_request, name='handle_emergency_request'),
]