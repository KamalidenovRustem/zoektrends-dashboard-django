"""
Columbus Chat Views
Conversational AI interface for prospect discovery
"""
from django.shortcuts import render
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
import logging

logger = logging.getLogger(__name__)


def columbus_chat_index(request):
    """Columbus Chat interface page"""
    import os
    ai_provider = os.getenv('AI_PROVIDER', 'vertex')
    return render(request, 'columbus_chat/index.html', {
        'ai_provider': ai_provider,
        'ai_model': 'Gemini 2.5 Pro' if ai_provider == 'vertex' else 'GPT-4o'
    })


@csrf_exempt
@require_http_methods(["POST"])
def chat_message(request):
    """
    Handle chat message from user
    Returns AI response with prospect recommendations
    """
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return JsonResponse({
                'success': False,
                'error': 'Message cannot be empty'
            }, status=400)
        
        # Import services
        from apps.dashboard.services.columbus_chat_service import get_columbus_chat
        from apps.dashboard.services.bigquery_service import get_bigquery_service
        from apps.dashboard.services.prospect_scoring_service import get_prospect_scoring_service
        
        # Get services
        chat_ai = get_columbus_chat()
        bq_service = get_bigquery_service()
        scoring_service = get_prospect_scoring_service()
        
        # Get company context for AI
        # Fetch recent companies (limit for performance)
        companies = bq_service.get_companies_with_filters(filters={'relevant': 'to_review'}, limit=100)
        
        # Score companies
        scored_companies = scoring_service.score_companies_batch(companies)
        
        # Prepare context for AI
        context = {
            'companies': scored_companies,
            'total_companies': len(companies)
        }
        
        # Get AI response
        result = chat_ai.chat(user_message, context=context)
        
        return JsonResponse({
            'success': True,
            'response': result['response'],
            'function_calls': result.get('function_calls', []),
            'data': result.get('data')
        })
        
    except Exception as e:
        logger.error(f"Chat message error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def reset_chat(request):
    """Reset chat conversation history"""
    try:
        from apps.dashboard.services.columbus_chat_service import get_columbus_chat
        
        chat_ai = get_columbus_chat()
        chat_ai.reset_conversation()
        
        return JsonResponse({
            'success': True,
            'message': 'Conversation reset successfully'
        })
        
    except Exception as e:
        logger.error(f"Reset chat error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def get_suggestions(request):
    """Get suggested queries"""
    try:
        from apps.dashboard.services.columbus_chat_service import get_columbus_chat
        
        chat_ai = get_columbus_chat()
        suggestions = chat_ai.get_suggestions()
        
        return JsonResponse({
            'success': True,
            'suggestions': suggestions
        })
        
    except Exception as e:
        logger.error(f"Get suggestions error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def quick_insights(request):
    """
    Get quick insights for dashboard
    - Top 5 hot prospects
    - New companies this week
    - Most active hirers
    """
    try:
        from apps.dashboard.services.bigquery_service import get_bigquery_service
        from apps.dashboard.services.prospect_scoring_service import get_prospect_scoring_service
        
        bq_service = get_bigquery_service()
        scoring_service = get_prospect_scoring_service()
        
        # Get recent companies
        companies = bq_service.get_companies_with_filters(filters={'relevant': 'to_review'}, limit=200)
        
        # Score all companies
        scored = scoring_service.score_companies_batch(companies)
        
        # Get top prospects
        top_prospects = [c for c in scored if c['prospect_score'] >= 70][:5]
        
        # Get new companies (last 7 days)
        from datetime import datetime, timedelta
        week_ago = datetime.utcnow() - timedelta(days=7)
        new_companies = [c for c in scored 
                        if c.get('created_at') and 
                        datetime.fromisoformat(c['created_at'].replace(' UTC', '')) >= week_ago][:5]
        
        # Get most active (by job count)
        most_active = sorted([c for c in scored if c.get('job_count', 0) > 0], 
                           key=lambda x: x.get('job_count', 0), 
                           reverse=True)[:5]
        
        return JsonResponse({
            'success': True,
            'insights': {
                'top_prospects': top_prospects,
                'new_companies': new_companies,
                'most_active': most_active
            }
        })
        
    except Exception as e:
        logger.error(f"Quick insights error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
