"""
Dashboard Views
Main dashboard views matching Laravel DashboardController
"""
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .services.bigquery_service import get_bigquery_service
from .services.looker_service import get_looker_service
from .services.gemini_service import get_gemini_service
import logging
import json

logger = logging.getLogger(__name__)


def index(request):
    """
    Main dashboard view
    Loads dashboard instantly with skeleton UI
    Data will be fetched via AJAX
    """
    context = {
        'GOOGLE_CLOUD_PROJECT_ID': settings.GOOGLE_CLOUD.get('PROJECT_ID', ''),
        'GOOGLE_CLOUD_REGION': settings.GOOGLE_CLOUD.get('REGION', ''),
        'BIGQUERY_DATASET': settings.BIGQUERY.get('DATASET', ''),
    }
    return render(request, 'dashboard/index.html', context)


@require_http_methods(["GET"])
def get_stats(request):
    """
    AJAX endpoint to fetch dashboard statistics
    """
    try:
        bq_service = get_bigquery_service()
        stats = bq_service.get_stats()
        recent_jobs = bq_service.get_recent_jobs(5)
        
        return JsonResponse({
            'success': True,
            'stats': stats,
            'recentJobs': recent_jobs
        })
    except Exception as e:
        logger.error(f"Failed to get stats: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Unable to connect to BigQuery: {str(e)}'
        }, status=500)


def analytics(request):
    """
    Analytics page with Looker dashboard
    """
    return render(request, 'analytics/index.html')


def api_management(request):
    """API management page"""
    return render(request, 'dashboard/api.html')


@require_http_methods(["GET"])
def test_connection(request):
    """Test BigQuery connection"""
    try:
        bq_service = get_bigquery_service()
        job_count = bq_service.get_job_count()
        
        return JsonResponse({
            'success': True,
            'message': 'Connection successful',
            'job_count': job_count
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def get_company_jobs(request):
    """Get jobs for a specific company"""
    company = request.GET.get('company', '')
    
    if not company:
        return JsonResponse({
            'success': False,
            'error': 'Company name is required'
        }, status=400)
    
    try:
        bq_service = get_bigquery_service()
        # Filter jobs by company using keyword filter
        jobs = bq_service.get_jobs_with_filters({'keyword': company}, limit=50)
        
        return JsonResponse({
            'success': True,
            'jobs': jobs,
            'company': company
        })
    except Exception as e:
        logger.error(f"Failed to get company jobs: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
def analytics_chat(request):
    """
    AI Analytics Chat endpoint using Gemini
    Processes user questions about job market data
    """
    try:
        # Parse JSON body
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        
        if not user_message:
            return JsonResponse({
                'success': False,
                'message': 'Please provide a message'
            }, status=400)
        
        # Initialize Gemini service
        gemini_service = get_gemini_service()
        
        # Get BigQuery context for AI
        try:
            bq_service = get_bigquery_service()
            stats = bq_service.get_stats()
            context_data = {
                'total_jobs': stats.get('total_jobs', 0),
                'total_companies': stats.get('total_companies', 0),
                'total_sources': stats.get('total_sources', 0)
            }
        except:
            context_data = {}
        
        # Generate AI response
        ai_response = gemini_service.generate_analytics_response(
            user_message,
            context_data
        )
        
        return JsonResponse({
            'success': True,
            'message': ai_response
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Analytics chat error: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Sorry, I encountered an error: {str(e)}'
        }, status=500)


@require_http_methods(["POST"])
def get_contact_details(request):
    """
    Get AI-generated contact details for a company
    """
    try:
        data = json.loads(request.body)
        company_name = data.get('company_name') or data.get('company')
        
        if not company_name:
            return JsonResponse({
                'success': False,
                'error': 'Company name is required'
            }, status=400)
        
        # Get company details from BigQuery
        bq_service = get_bigquery_service()
        company_details = bq_service.get_company_details(company_name)
        
        # Build company data dict for AI
        company_data = {
            'company_name': company_name,
            'company_type': company_details.get('company_type'),
            'company_industry': company_details.get('company_industry'),
            'company_size': company_details.get('company_size'),
            'job_count': company_details.get('job_count', 0)
        }
        
        # Find LinkedIn job URL if available
        linkedin_job_url = None
        jobs = company_details.get('jobs', [])
        if jobs:
            for job in jobs:
                if job.get('url') and 'linkedin.com' in job.get('url', '').lower():
                    linkedin_job_url = job.get('url')
                    break
        
        # Generate contact details with AI
        gemini_service = get_gemini_service()
        contact_details = gemini_service.get_contact_details(company_data, linkedin_job_url)
        
        return JsonResponse({
            'success': True,
            'contact_details': contact_details
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Contact details error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def skills_registry(request):
    """Skills Registry management page"""
    return render(request, 'dashboard/skills_registry.html')


@require_http_methods(["GET"])
def skills_registry_list(request):
    """Get all skills from registry"""
    try:
        bq_service = get_bigquery_service()
        skills = bq_service.get_skills_registry()
        
        return JsonResponse({
            'success': True,
            'skills': skills
        })
    except Exception as e:
        logger.error(f"Skills registry list error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
def skills_registry_save(request):
    """Add or update skill in registry"""
    try:
        data = json.loads(request.body)
        bq_service = get_bigquery_service()
        
        # Check if this is an update (skill already exists)
        existing_skills = bq_service.get_skills_registry()
        skill_exists = any(s['skill_id'] == data['skill_id'] for s in existing_skills)
        
        if skill_exists:
            # Update existing skill
            success = bq_service.update_skill(data)
        else:
            # Add new skill
            success = bq_service.add_skill(data)
        
        if success:
            return JsonResponse({
                'success': True,
                'message': 'Skill saved successfully'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to save skill'
            }, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Skills registry save error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
def skills_registry_toggle_active(request):
    """Toggle skill active status"""
    try:
        data = json.loads(request.body)
        skill_id = data.get('skill_id')
        is_active = data.get('is_active')
        
        if not skill_id:
            return JsonResponse({
                'success': False,
                'error': 'Skill ID is required'
            }, status=400)
        
        bq_service = get_bigquery_service()
        success = bq_service.toggle_skill_active(skill_id, is_active)
        
        if success:
            return JsonResponse({
                'success': True,
                'message': 'Skill status updated'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to update skill status'
            }, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Skills toggle error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
def skills_registry_delete(request):
    """Delete skill from registry"""
    try:
        data = json.loads(request.body)
        skill_id = data.get('skill_id')
        
        if not skill_id:
            return JsonResponse({
                'success': False,
                'error': 'Skill ID is required'
            }, status=400)
        
        bq_service = get_bigquery_service()
        success = bq_service.delete_skill(skill_id)
        
        if success:
            return JsonResponse({
                'success': True,
                'message': 'Skill deleted successfully'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to delete skill'
            }, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Skills delete error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# ===== Configuration Views =====

def configuration(request):
    """Configuration page - render template"""
    logger.info("Configuration page requested")
    return render(request, 'configuration/index.html')

def _extract_config_id(payload: dict) -> int | None:
    """Helper to pull a configuration ID from mixed payload formats"""
    if not payload:
        return None

    config_id = payload.get('config_id')

    # Direct int
    if isinstance(config_id, int):
        return config_id

    # Nested dict (maybe already parsed config)
    if isinstance(config_id, dict):
        nested_id = config_id.get('id')
        return int(nested_id) if nested_id is not None else None

    # JSON string carrying dict or numeric ID
    if isinstance(config_id, str) and config_id.strip():
        raw = config_id.strip()
        try:
            # Try direct integer first
            return int(raw)
        except ValueError:
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict) and parsed.get('id') is not None:
                    return int(parsed['id'])
            except json.JSONDecodeError:
                return None

    # Some callers might send full config under `config`
    config_obj = payload.get('config')
    if isinstance(config_obj, dict) and config_obj.get('id') is not None:
        return int(config_obj['id'])
    if isinstance(config_obj, str) and config_obj.strip():
        try:
            parsed = json.loads(config_obj.strip())
            if isinstance(parsed, dict) and parsed.get('id') is not None:
                return int(parsed['id'])
        except json.JSONDecodeError:
            return None

    return None

def configuration_list(request):
    """Get all configurations"""
    try:
        bq_service = get_bigquery_service()
        configs = bq_service.get_all_configurations()
        
        logger.info(f"Loaded {len(configs)} configurations from BigQuery")
        for i, config in enumerate(configs):
            logger.info(f"Config {i}: active={config.get('is_active')}, queries={len(config.get('search_queries', []))}")
        
        return JsonResponse({
            'success': True,
            'configs': configs
        })
        
    except Exception as e:
        logger.error(f"Configuration list error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
def configuration_save(request):
    """Save new or update existing configuration"""
    try:
        data = json.loads(request.body)
        
        # Validate required fields
        required_fields = ['search_queries', 'search_countries', 'enabled_modules', 
                          'daily_max_per_module', 'exhaustive_max_per_module',
                          'enable_bigquery', 'enable_filtering']
        
        for field in required_fields:
            if field not in data:
                return JsonResponse({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }, status=400)
        
        # Check 90-minute lock for existing configurations
        old_timestamp = data.get('updated_at')
        if old_timestamp:
            from datetime import datetime, timedelta, timezone
            try:
                # Parse the timestamp (handle both with and without timezone)
                if old_timestamp.endswith('UTC'):
                    old_timestamp_clean = old_timestamp.replace(' UTC', '')
                    last_updated = datetime.fromisoformat(old_timestamp_clean).replace(tzinfo=timezone.utc)
                else:
                    last_updated = datetime.fromisoformat(old_timestamp)
                    if last_updated.tzinfo is None:
                        last_updated = last_updated.replace(tzinfo=timezone.utc)
                
                # Calculate time difference
                current_time = datetime.now(timezone.utc)
                time_diff = current_time - last_updated
                minutes_passed = time_diff.total_seconds() / 60
                
                # Check if 90 minutes have passed
                if minutes_passed < 90:
                    minutes_remaining = int(90 - minutes_passed)
                    return JsonResponse({
                        'success': False,
                        'error': f'Configuration is locked. Changes can be made after {minutes_remaining} minutes. This lock exists to ensure buffer time for active scraping jobs.',
                        'locked': True,
                        'minutes_remaining': minutes_remaining,
                        'last_updated': old_timestamp
                    }, status=423)  # 423 Locked status code
                    
                logger.info(f"Configuration lock check passed: {minutes_passed:.1f} minutes since last update")
                
            except Exception as e:
                logger.warning(f"Failed to parse timestamp for lock check: {str(e)}")
                # Continue if timestamp parsing fails (backwards compatibility)
        
        updated_by = request.user.username if request.user.is_authenticated else 'admin'

        # Build configuration payload
        config_data = {
            'is_active': data.get('is_active', False),
            'search_queries': data.get('search_queries', []),
            'search_countries': data.get('search_countries', []),
            'enabled_modules': data.get('enabled_modules', []),
            'daily_max_per_module': int(data.get('daily_max_per_module', 100)),
            'exhaustive_max_per_module': int(data.get('exhaustive_max_per_module', 500)),
            'enable_bigquery': bool(data.get('enable_bigquery', True)),
            'enable_filtering': bool(data.get('enable_filtering', True)),
            'notes': data.get('notes', ''),
            'updated_by': updated_by
        }
        
        bq_service = get_bigquery_service()
        if old_timestamp:
            # Update existing configuration
            success = bq_service.update_configuration_by_timestamp(old_timestamp, config_data)
        else:
            # Create new configuration
            success = bq_service.add_configuration(config_data)
        
        if success:
            return JsonResponse({
                'success': True,
                'message': 'Configuration saved successfully'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to save configuration'
            }, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Configuration save error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
def configuration_activate(request):
    """Activate a configuration (deactivates all others)"""
    try:
        data = json.loads(request.body)
        config = data.get('config')
        
        if not config or not config.get('updated_at'):
            return JsonResponse({
                'success': False,
                'error': 'Configuration data with timestamp is required'
            }, status=400)
        updated_by = request.user.username if request.user.is_authenticated else 'admin'
        bq_service = get_bigquery_service()
        success = bq_service.activate_configuration(config['updated_at'], config, updated_by)
        
        if success:
            return JsonResponse({
                'success': True,
                'message': 'Configuration activated successfully'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to activate configuration'
            }, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Configuration activate error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
def configuration_deactivate(request):
    """Deactivate a configuration"""
    try:
        data = json.loads(request.body)
        config = data.get('config')
        
        if not config or not config.get('updated_at'):
            return JsonResponse({
                'success': False,
                'error': 'Configuration data with timestamp is required'
            }, status=400)
        updated_by = request.user.username if request.user.is_authenticated else 'admin'
        bq_service = get_bigquery_service()
        success = bq_service.deactivate_configuration(config['updated_at'], config, updated_by)
        
        if success:
            return JsonResponse({
                'success': True,
                'message': 'Configuration deactivated successfully'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to deactivate configuration'
            }, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Configuration deactivate error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
def configuration_delete(request):
    """Delete a configuration"""
    try:
        data = json.loads(request.body)
        config = data.get('config')
        
        if not config or not config.get('updated_at'):
            return JsonResponse({
                'success': False,
                'error': 'Configuration timestamp is required'
            }, status=400)
        
        bq_service = get_bigquery_service()
        success = bq_service.delete_configuration(config['updated_at'])
        
        if success:
            return JsonResponse({
                'success': True,
                'message': 'Configuration deleted successfully'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Failed to delete configuration'
            }, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        logger.error(f"Configuration delete error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
