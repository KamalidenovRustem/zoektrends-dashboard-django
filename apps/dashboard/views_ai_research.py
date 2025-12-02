"""
AI Research Views with Status Streaming
Provides real-time status updates for company contact research
"""

import json
import time
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import logging

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def research_company_streaming(request):
    """
    Stream status updates while researching company contacts
    Uses Server-Sent Events (SSE) for real-time progress
    """
    try:
        data = json.loads(request.body)
        company_id = data.get('company_id')
        
        if not company_id:
            return JsonResponse({'error': 'company_id required'}, status=400)
        
        def event_stream():
            """Generator that yields status updates"""
            try:
                # Initialize services
                from apps.dashboard.services.company_research_service import get_company_research_service
                research_service = get_company_research_service()
                
                # Status 1: Columbus AI Thinking
                yield f"data: {json.dumps({'status': 'thinking', 'message': 'ColumbusAI is analyzing your request...', 'icon': '🧠', 'progress': 10})}\n\n"
                time.sleep(0.5)
                
                # Status 2: Fetching from BigQuery
                yield f"data: {json.dumps({'status': 'fetching', 'message': 'Connecting to BigQuery database...', 'icon': '📊', 'progress': 20})}\n\n"
                
                # Fetch company data
                company_data = research_service._fetch_company_data(company_id)
                if not company_data:
                    yield f"data: {json.dumps({'status': 'error', 'message': f'Company not found: {company_id}'})}\n\n"
                    return
                
                company_name = company_data.get('company_name')
                
                # Status 3: RAG pulling information
                yield f"data: {json.dumps({'status': 'rag', 'message': f'RAG analyzing job postings for {company_name}...', 'icon': '📚', 'progress': 35})}\n\n"
                
                # Get RAG context
                rag_data = research_service.rag_service.get_company_context(company_name)
                jobs_found = rag_data.get('jobs_found', 0) if rag_data else 0
                location = rag_data.get('country') if rag_data else None
                
                if location:
                    company_data['location'] = location
                    yield f"data: {json.dumps({'status': 'rag', 'message': f'Found {jobs_found} job postings in {location}', 'icon': '✓', 'progress': 45})}\n\n"
                else:
                    yield f"data: {json.dumps({'status': 'rag', 'message': f'Found {jobs_found} job postings', 'icon': '✓', 'progress': 45})}\n\n"
                
                time.sleep(0.3)
                
                # Status 4: AI Agent browsing
                yield f"data: {json.dumps({'status': 'browsing', 'message': 'AI Agent searching the web...', 'icon': '🌐', 'progress': 50})}\n\n"
                
                # Get LinkedIn job URL
                linkedin_job_url = None
                if rag_data and rag_data.get('jobs'):
                    first_job = rag_data['jobs'][0]
                    linkedin_job_url = first_job.get('url')
                
                rag_context = rag_data.get('context', '') if rag_data else None
                
                # Run Enhanced Contact Service (Gemini + SerpAPI) with progress updates
                yield f"data: {json.dumps({'status': 'browsing', 'message': 'Gemini AI exploring company website...', 'icon': '🔍', 'progress': 60})}\n\n"
                
                # Use exact same call as Columbus Chat
                research_result = research_service.enhanced_contact_service.find_contacts(
                    company_data=company_data,
                    use_web_browser=True
                )
                
                yield f"data: {json.dumps({'status': 'browsing', 'message': 'Gemini AI extracting contact information...', 'icon': '📇', 'progress': 75})}\n\n"
                time.sleep(0.3)
                
                # Status 5: AI Summarizing
                yield f"data: {json.dumps({'status': 'summarizing', 'message': 'AI organizing and validating contacts...', 'icon': '🎯', 'progress': 85})}\n\n"
                time.sleep(0.5)
                
                # Status 6: Complete
                yield f"data: {json.dumps({'status': 'complete', 'message': 'Research complete!', 'icon': '✅', 'progress': 100})}\n\n"
                
                # Format the contact information for display
                contacts_data = research_result.get('ai_response', {})
                if isinstance(contacts_data, str):
                    import json as json_lib
                    contacts_data = json_lib.loads(contacts_data)
                
                # Build formatted message
                message_parts = [f"**Contact Information for {company_name}**\n"]
                
                # Add company info
                if 'company' in contacts_data and contacts_data['company']:
                    company_info = contacts_data['company']
                    if company_info.get('website'):
                        message_parts.append(f"🌐 **Website:** {company_info['website']}")
                    if company_info.get('address'):
                        message_parts.append(f"📍 **Address:** {company_info['address']}")
                
                # Add general contact
                if 'general_contact' in contacts_data and contacts_data['general_contact']:
                    general = contacts_data['general_contact']
                    if general.get('email') or general.get('phone'):
                        message_parts.append(f"\n**General Contact:**")
                        if general.get('email'):
                            message_parts.append(f"📧 {general['email']}")
                        if general.get('phone'):
                            message_parts.append(f"📞 {general['phone']}")
                
                # Add decision makers
                if 'decision_makers' in contacts_data and contacts_data['decision_makers']:
                    message_parts.append(f"\n**Decision Makers ({len(contacts_data['decision_makers'])} contacts):**\n")
                    for dm in contacts_data['decision_makers']:
                        name = dm.get('name', 'Unknown')
                        title = dm.get('title', '')
                        email = dm.get('email', '')
                        linkedin = dm.get('linkedin_url', '')
                        
                        contact_line = f"• **{name}**"
                        if title:
                            contact_line += f" - _{title}_"
                        message_parts.append(contact_line)
                        
                        if email:
                            message_parts.append(f"  📧 {email}")
                        if linkedin:
                            message_parts.append(f"  🔗 [LinkedIn]({linkedin})")
                        message_parts.append("")  # Empty line between contacts
                else:
                    # No contacts found
                    message_parts.append(f"\n⚠️ **No contact details found**")
                    if contacts_data.get('company', {}).get('website'):
                        message_parts.append(f"\nPlease visit the website manually to find contact information.")
                
                # Add notes if available
                if contacts_data.get('notes'):
                    message_parts.append(f"\n📝 **Notes:** {contacts_data['notes']}")
                
                # Add data sources
                data_sources = research_result.get('data_sources', [])
                if data_sources:
                    message_parts.append(f"\n📊 **Data Sources:** {', '.join(data_sources)}")
                
                formatted_message = '\n'.join(message_parts)
                
                # Send final result with formatted message
                result = {
                    'success': True,
                    'company_id': company_id,
                    'company_data': company_data,
                    'jobs_found': jobs_found,
                    'message': formatted_message,
                    'contacts': contacts_data
                }
                
                yield f"data: {json.dumps({'status': 'result', 'data': result})}\n\n"
                
            except Exception as e:
                logger.error(f"Error in research stream: {str(e)}", exc_info=True)
                yield f"data: {json.dumps({'status': 'error', 'message': str(e)})}\n\n"
        
        response = StreamingHttpResponse(
            event_stream(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response
        
    except Exception as e:
        logger.error(f"Failed to start research stream: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
