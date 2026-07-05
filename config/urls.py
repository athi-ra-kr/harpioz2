from django.urls import path, include
from django.shortcuts import redirect

def home_redirect(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('admin_dashboard')
    return redirect('admin_login')

urlpatterns = [
    path('', home_redirect),
    path('', include('classes.urls')),
]
