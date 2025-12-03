"""
Companies Views
"""
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.conf import settings
from apps.dashboard.services.bigquery_service import get_bigquery_service
from apps.dashboard.services.gemini_service import get_gemini_service
from apps.dashboard.services.openai_service import get_openai_service
import logging
import json

logger = logging.getLogger(__name__)


@require_http_methods(["GET"])
def api_get_company(request):
    """Get a single company by name from BigQuery"""
    try:
        company_name = request.GET.get('name', '').strip()
        
        if not company_name:
            return JsonResponse({
                'success': False,
                'error': 'Company name is required'
            }, status=400)
        
        bq_service = get_bigquery_service()
        
        # Use keyword filter to find exact company
        filters = {'keyword': company_name}
        companies = bq_service.get_companies_with_filters(filters, limit=1)
        
        if not companies:
            return JsonResponse({
                'success': False,
                'error': 'Company not found'
            }, status=404)
        
        company = companies[0]
        
        logger.info(f"API GET COMPANY - Found: {company.get('company')}")
        
        return JsonResponse({
            'success': True,
            'company': company
        })
        
    except Exception as e:
        logger.error(f"Failed to get company: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def index(request):
    """Companies listing page"""
    limit = min(
        int(request.GET.get('limit', settings.DASHBOARD['RESULTS_LIMIT'])),
        settings.DASHBOARD['MAX_RESULTS_LIMIT']
    )
    
    logger.info("=" * 80)
    logger.info(f"COMPANIES INDEX - Requested limit: {request.GET.get('limit', 'NOT SET')}")
    logger.info(f"COMPANIES INDEX - Settings RESULTS_LIMIT: {settings.DASHBOARD['RESULTS_LIMIT']}")
    logger.info(f"COMPANIES INDEX - Final limit: {limit}")
    logger.info("=" * 80)
    
    # Collect filters
    filters = {}
    for key in ['keyword', 'country', 'tech_stack', 'min_jobs', 'sort_by', 'relevant', 'status']:
        value = request.GET.get(key, '').strip()
        if value:
            filters[key] = value
    
    # Default to "To Review" if not specified
    if 'relevant' not in filters:
        filters['relevant'] = 'to_review'
    
    try:
        bq_service = get_bigquery_service()
        companies = bq_service.get_companies_with_filters(filters, limit)
        
        logger.info(f"COMPANIES INDEX - Fetched {len(companies)} companies from BigQuery")
        logger.info(f"COMPANIES INDEX - Filters used: {filters}")
        
        # Get filter options
        filter_options = bq_service.get_company_filter_options()
        
        # Build template context - only include limit if explicitly set in URL
        template_filters = {
            'keyword': filters.get('keyword', ''),
            'country': filters.get('country', ''),
            'tech_stack': filters.get('tech_stack', ''),
            'min_jobs': filters.get('min_jobs', '1'),
            'sort_by': filters.get('sort_by', 'company_name'),
            'relevant': filters.get('relevant', 'to_review'),
            'status': filters.get('status', ''),
        }
        
        # Only add limit to template if it was explicitly provided in URL
        if 'limit' in request.GET:
            template_filters['limit'] = str(limit)
        
        return render(request, 'companies/index.html', {
            'companies': json.dumps(companies),  # Serialize for JavaScript
            'filter_options': filter_options,
            'limit': limit,
            'filters': template_filters
        })
        
    except Exception as e:
        logger.error(f"Failed to load companies: {str(e)}")
        return render(request, 'companies/index.html', {
            'error': f'Unable to fetch companies: {str(e)}',
            'companies': json.dumps([]),
            'filter_options': {'countries': [], 'tech_stacks': []},
            'limit': limit,
            'filters': {
                'keyword': '',
                'country': '',
                'tech_stack': '',
                'min_jobs': '1',
                'sort_by': 'company_name',
                'limit': str(limit),
            }
        })


@require_http_methods(["POST"])
def get_contact_details(request):
    """Get contact details for a company using Gemini AI with full company context"""
    try:
        import json
        data = json.loads(request.body)
        
        # Extract company data
        company_data = {
            'company_name': data.get('company_name', ''),
            'company_type': data.get('company_type'),
            'company_industry': data.get('company_industry'),
            'company_size': data.get('company_size'),
            'job_count': data.get('job_count', 0)
        }
        
        linkedin_job_url = data.get('linkedin_job_url')
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    
    if not company_data['company_name']:
        return JsonResponse({
            'success': False,
            'error': 'Company name is required'
        }, status=400)
    
    try:
        # Get AI provider from settings (default to Gemini)
        ai_provider = getattr(settings, 'AI_CONTACT_PROVIDER', 'gemini').lower()
        
        # Check if enhanced mode is enabled (RAG + Web Browsing + AI)
        use_enhanced_mode = request.GET.get('enhanced') == 'true'
        
        # Log for debugging
        logger.info(f"Getting contact details for: {company_data} using {ai_provider}")
        if use_enhanced_mode:
            logger.info("Enhanced mode enabled: RAG + Web Browsing + AI")
        
        # Enhanced mode - the impressive full package
        if use_enhanced_mode:
            from apps.dashboard.services.enhanced_contact_service import EnhancedContactService
            
            enhanced_service = EnhancedContactService(ai_provider=ai_provider)
            result = enhanced_service.find_contacts(
                company_data=company_data,
                linkedin_job_url=linkedin_job_url,
                use_web_browser=True
            )
            
            return JsonResponse({
                'success': True,
                'company_name': company_data['company_name'],
                'contact_details': result['ai_response'],
                'provider': f"{ai_provider.upper()} (Enhanced)",
                'data_sources': result['data_sources'],
                'processing_time': result['processing_time'],
                'enhanced_mode': True,
                'web_data': {
                    'website': result['web_data'].get('website') if result.get('web_data') else None,
                    'emails_found': len(result['web_data'].get('emails', [])) if result.get('web_data') else 0,
                    'names_found': len(result['web_data'].get('contact_names', [])) if result.get('web_data') else 0,
                },
                'rag_data': {
                    'jobs_found': result['rag_data'].get('jobs_found', 0) if result.get('rag_data') else 0
                }
            })
        
        # Option to get both responses for comparison
        use_dual_mode = request.GET.get('dual_mode') == 'true'
        
        if use_dual_mode:
            # Get responses from both AIs for comparison
            logger.info("Dual mode: Getting responses from both Gemini and OpenAI")
            
            try:
                gemini_service = get_gemini_service()
                gemini_response = gemini_service.get_contact_details(company_data, linkedin_job_url)
            except Exception as e:
                logger.error(f"Gemini failed: {str(e)}")
                gemini_response = f"Error: {str(e)}"
            
            try:
                openai_service = get_openai_service()
                openai_response = openai_service.get_contact_details(company_data, linkedin_job_url)
            except Exception as e:
                logger.error(f"OpenAI failed: {str(e)}")
                openai_response = f"Error: {str(e)}"
            
            return JsonResponse({
                'success': True,
                'company_name': company_data['company_name'],
                'dual_mode': True,
                'gemini_response': gemini_response,
                'openai_response': openai_response
            })
        
        # Single provider mode (default)
        if ai_provider == 'openai':
            ai_service = get_openai_service()
            provider_name = 'OpenAI GPT-4o'
        else:
            ai_service = get_gemini_service()
            provider_name = 'Gemini 2.5 Pro'
        
        contact_details = ai_service.get_contact_details(company_data, linkedin_job_url)
        
        return JsonResponse({
            'success': True,
            'company_name': company_data['company_name'],
            'contact_details': contact_details,
            'provider': provider_name
        })
        
    except Exception as e:
        logger.error(f"Failed to get contact details: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Failed to fetch contact details: {str(e)}'
        }, status=500)


@require_http_methods(["POST"])
def update_company(request):
    """Update company information in BigQuery"""
    logger.info("=" * 80)
    logger.info("UPDATE COMPANY ENDPOINT CALLED")
    logger.info("=" * 80)
    
    try:
        data = json.loads(request.body)
        logger.info(f"Request data: {data}")
        
        company_id = data.get('company_id')
        company_name = data.get('company_name')
        updates = data.get('updates', {})
        
        if not company_id and not company_name:
            logger.error("Missing company_id and company_name")
            return JsonResponse({
                'success': False,
                'error': 'Either company_id or company_name is required'
            }, status=400)
        
        if not updates:
            logger.error("No updates provided")
            return JsonResponse({
                'success': False,
                'error': 'No updates provided'
            }, status=400)
        
        logger.info(f"Updating company: {company_name or company_id}")
        logger.info(f"Updates: {updates}")
        
        # Get BigQuery service
        bq_service = get_bigquery_service()
        
        # Build UPDATE query
        set_clauses = []
        for field, value in updates.items():
            if field in ['status', 'company_name', 'domain', 'company_type', 'company_industry', 'company_size', 'solution_domain']:
                set_clauses.append(f"{field} = '{value}'")
                logger.info(f"  - Setting {field} = '{value}'")
        
        if not set_clauses:
            logger.error("No valid fields to update")
            return JsonResponse({
                'success': False,
                'error': 'No valid fields to update'
            }, status=400)
        
        # Build WHERE clause
        if company_id:
            where_clause = f"company_id = '{company_id}'"
        else:
            where_clause = f"company_name = '{company_name}'"
        
        # Execute UPDATE
        update_query = f"""
            UPDATE `{bq_service.project_id}.{bq_service.dataset}.{bq_service.companies_table}`
            SET {', '.join(set_clauses)}
            WHERE {where_clause}
        """
        
        logger.info("Executing BigQuery UPDATE:")
        logger.info(update_query)
        
        query_job = bq_service.client.query(update_query)
        result = query_job.result()
        
        logger.info(f"UPDATE completed. Rows affected: {query_job.num_dml_affected_rows}")
        logger.info("=" * 80)
        
        return JsonResponse({
            'success': True,
            'rows_affected': query_job.num_dml_affected_rows,
            'message': f'Successfully updated {query_job.num_dml_affected_rows} row(s)'
        })
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Failed to update company: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Failed to update company: {str(e)}'
        }, status=500)
