"""
Jobs Views
Handles job listing and filtering
"""
from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.http import require_http_methods
from apps.dashboard.services.bigquery_service import get_bigquery_service
import logging

logger = logging.getLogger(__name__)


def index(request):
    """Jobs listing page with filters"""
    return render(request, 'jobs/index.html')


@require_http_methods(["GET"])
def api_list(request):
    """API endpoint for job listings with filters"""
    limit = min(
        int(request.GET.get('limit', settings.DASHBOARD['RESULTS_LIMIT'])),
        settings.DASHBOARD['MAX_RESULTS_LIMIT']
    )
    
    # Collect filters
    filters = {}
    for key in ['source', 'country', 'company_type', 'solution_domain', 'tech_stack', 'keyword', 'posted_within', 'sort_by']:
        value = request.GET.get(key, '').strip()
        if value:
            filters[key] = value
    
    try:
        bq_service = get_bigquery_service()
        
        # Get jobs with or without filters
        if filters:
            jobs = bq_service.get_jobs_with_filters(filters, limit)
        else:
            jobs = bq_service.get_jobs(limit)
        
        return JsonResponse({
            'success': True,
            'jobs': jobs
        })
        
    except Exception as e:
        logger.error(f"Failed to load jobs: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Unable to fetch jobs: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def filter_options(request):
    """API endpoint for filter options"""
    try:
        bq_service = get_bigquery_service()
        
        countries = bq_service.get_unique_countries()
        tech_stacks = bq_service.get_unique_tech_stacks()
        
        return JsonResponse({
            'success': True,
            'countries': countries,
            'tech_stacks': tech_stacks
        })
        
    except Exception as e:
        logger.error(f"Failed to load filter options: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Unable to fetch filter options: {str(e)}'
        }, status=500)
