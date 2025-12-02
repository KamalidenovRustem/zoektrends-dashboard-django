"""
Simple Authentication Views
Matches the Laravel SimpleAuthController functionality
"""
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
import logging

logger = logging.getLogger(__name__)


def show_login(request):
    """Display login page"""
    # If already authenticated, redirect to dashboard
    if request.session.get('authenticated'):
        return redirect('dashboard:index')
    
    return render(request, 'auth/simple-login.html')


@csrf_protect
@require_http_methods(["POST"])
def login(request):
    """
    Handle login - username/password authentication
    Matches Laravel simple auth system
    """
    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')
    
    if not username or not password:
        messages.error(request, 'Username and password are required')
        return redirect('login')
    
    # Simple authentication - matching Laravel's env vars
    valid_username = settings.DASHBOARD_USERNAME
    valid_password = settings.DASHBOARD_PASSWORD
    
    if username == valid_username and password == valid_password:
        # Set session
        request.session['authenticated'] = True
        request.session['username'] = username
        request.session.set_expiry(settings.SESSION_COOKIE_AGE)
        
        logger.info(f'User logged in: {username}')
        messages.success(request, 'Welcome back!')
        
        return redirect('dashboard:index')
    else:
        logger.warning(f'Failed login attempt: {username}')
        messages.error(request, 'Invalid credentials.')
        return redirect('login')


@require_http_methods(["POST"])
def logout(request):
    """Handle logout"""
    username = request.session.get('username', 'Unknown')
    request.session.flush()
    
    logger.info(f'User logged out: {username}')
    messages.success(request, 'You have been logged out.')
    
    return redirect('login')
