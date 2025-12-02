"""
Configuration Views
Handles scraper configuration management
"""
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from apps.dashboard.services.cloudrun_service import get_cloudrun_service
import logging

logger = logging.getLogger(__name__)


def index(request):
    """Configuration management page"""
    return render(request, 'configuration/index.html')


@require_http_methods(["POST"])
def run_job(request):
    """Trigger a Cloud Run job"""
    job_type = request.POST.get('job_type', 'exhaustive')
    
    try:
        cloudrun_service = get_cloudrun_service()
        
        if job_type == 'daily':
            result = cloudrun_service.trigger_daily_scraper()
        else:
            result = cloudrun_service.trigger_exhaustive_scraper()
        
        if result.get('success'):
            return JsonResponse({
                'success': True,
                'message': f'Job triggered successfully: {result.get("execution")}',
                'result': result
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Unknown error')
            }, status=500)
            
    except Exception as e:
        logger.error(f"Failed to trigger job: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def status(request):
    """Get job status"""
    # Placeholder - would need Cloud Run API to get actual status
    return JsonResponse({
        'success': True,
        'status': 'No jobs running',
        'message': 'Job status tracking not yet implemented'
    })
