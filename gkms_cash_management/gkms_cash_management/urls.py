from django.contrib import admin
from django.urls import path, include
from core.views import landing_page, home, CustomLoginView  # Adjust based on your views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('accounts/login/', CustomLoginView.as_view(), name='login'),
]