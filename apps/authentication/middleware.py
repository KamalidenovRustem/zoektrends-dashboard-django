"""
Authentication Middleware
Protects routes that require authentication
"""
from django.shortcuts import redirect
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)


class SimpleAuthMiddleware:
    """
    Middleware to check if user is authenticated for protected routes
    Similar to Laravel's 'simple.auth' middleware
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Routes that don't require authentication
        self.public_routes = [
            '/login',
            '/logout',
            '/admin/',
            '/static/',
            '/media/',
        ]
    
    def __call__(self, request):
        # Check if this is a public route
        path = request.path
        is_public = any(path.startswith(route) for route in self.public_routes)
        
        # If not public and not authenticated, redirect to login
        if not is_public and not request.session.get('authenticated'):
            logger.debug(f'Unauthenticated access attempt to: {path}')
            return redirect('login_page')
        
        response = self.get_response(request)
        return response
