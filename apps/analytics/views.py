"""
Analytics Views
Handles AI-powered analytics chat
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from apps.dashboard.services.bigquery_service import get_bigquery_service
from apps.dashboard.services.gemini_service import get_gemini_service
import logging
import json

logger = logging.getLogger(__name__)


@require_http_methods(["POST"])
@csrf_exempt  # For AJAX calls - consider using CSRF token in production
def chat(request):
    """
    Handle analytics chat messages with Gemini AI
    """
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        
        if not user_message or len(user_message) > 1000:
            return JsonResponse({
                'success': False,
                'error': 'Message is required and must be less than 1000 characters'
            }, status=400)
        
        # Get analytics context
        context = _get_analytics_context()
        
        # Build prompt
        prompt = _build_analytics_prompt(user_message, context)
        
        # Call Gemini
        gemini_service = get_gemini_service()
        response = gemini_service.generate_content(prompt, temperature=0.7)
        
        return JsonResponse({
            'success': True,
            'message': response
        })
        
    except Exception as e:
        logger.error(f"Analytics chat error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Sorry, I encountered an error. Please try again.',
            'message': "I apologize, but I'm having trouble processing your request right now. Please try again in a moment."
        }, status=500)


def _get_analytics_context():
    """Get current analytics context from dashboard"""
    try:
        bq_service = get_bigquery_service()
        
        stats = bq_service.get_stats()
        top_companies = bq_service.get_companies_with_filters({'sort_by': 'job_count_desc'}, 10)
        top_locations = bq_service.get_top_locations(10)
        countries = bq_service.get_unique_countries()
        tech_stacks = bq_service.get_unique_tech_stacks()
        
        return {
            'total_jobs': stats.get('total_jobs', 0),
            'total_companies': stats.get('total_companies', 0),
            'jobs_today': stats.get('jobs_today', 0),
            'countries_count': len(countries),
            'countries': countries[:10],
            'top_companies': [
                {
                    'name': c.get('company'),
                    'job_count': c.get('job_count'),
                    'type': c.get('company_type', 'Unknown')
                }
                for c in top_companies
            ],
            'top_locations': top_locations,
            'top_tech_stacks': tech_stacks[:20]
        }
        
    except Exception as e:
        logger.error(f"Error getting analytics context: {str(e)}")
        return {}


def _build_analytics_prompt(user_message, context):
    """Build prompt for analytics chat"""
    return f"""You are an AI assistant for a job market analytics dashboard.

Current data snapshot:
- Total jobs: {context.get('total_jobs', 'N/A')}
- Total companies: {context.get('total_companies', 'N/A')}
- Jobs posted today: {context.get('jobs_today', 'N/A')}
- Countries covered: {context.get('countries_count', 'N/A')}

Top companies by job count:
{chr(10).join([f"- {c['name']}: {c['job_count']} jobs" for c in context.get('top_companies', [])[:5]])}

Top locations:
{chr(10).join([f"- {loc.get('location', 'Unknown')}, {loc.get('country', '')}: {loc.get('job_count', 0)} jobs" for loc in context.get('top_locations', [])[:5]])}

User's question: {user_message}

Provide a helpful, professional response based on the data. If the data doesn't contain the answer, suggest what information would be needed.
"""
