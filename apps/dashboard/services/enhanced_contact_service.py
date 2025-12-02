"""
Enhanced AI Contact Service
Combines RAG (job postings data) + Web Browsing + AI Analysis
This is the impressive "full package" solution
"""
import logging
from typing import Dict, Any, Optional
import json

logger = logging.getLogger(__name__)


class EnhancedContactService:
    """
    Premium contact finding service that combines:
    1. RAG - Your existing job postings data
    2. Web Browsing - Real-time company website scraping
    3. AI Analysis - Smart synthesis of all data
    """
    
    def __init__(self, ai_provider: str = 'gemini'):
        """
        Initialize with AI provider choice
        
        Args:
            ai_provider: 'gemini' or 'openai'
        """
        self.ai_provider = ai_provider
        
        # Lazy imports to avoid circular dependencies
        from apps.dashboard.services.contact_rag_service import get_rag_service
        from apps.dashboard.services.web_browser_service import get_web_browser_service
        
        self.rag_service = get_rag_service()
        self.web_browser = get_web_browser_service()
        
        # Import AI service based on provider
        # Accept both 'gemini' and 'vertex' for Gemini AI
        if ai_provider in ['gemini', 'vertex']:
            from apps.dashboard.services.gemini_service import GeminiService
            self.ai_service = GeminiService()
            logger.info(f"Enhanced Contact Service initialized with Gemini (provider: {ai_provider})")
        else:
            from apps.dashboard.services.openai_service import OpenAIService
            self.ai_service = OpenAIService()
            logger.info(f"Enhanced Contact Service initialized with OpenAI (provider: {ai_provider})")
    
    def find_contacts(
        self,
        company_data: Dict[str, Any],
        linkedin_job_url: Optional[str] = None,
        use_web_browser: bool = True
    ) -> Dict[str, Any]:
        """
        Find contacts using the complete enhanced pipeline
        
        Args:
            company_data: Dict with company info
            linkedin_job_url: Optional LinkedIn job URL (for reference only)
            use_web_browser: Whether to browse company website (recommended: True)
        
        Returns:
            Dict with:
                - ai_response: JSON string from AI
                - data_sources: List of data sources used
                - rag_data: RAG context (job postings)
                - web_data: Web browsing results
                - processing_time: Time taken
                - provider: AI provider used
        """
        import time
        start_time = time.time()
        
        company_name = company_data.get('company_name', 'Unknown')
        
        logger.info(f"Enhanced contact search for: {company_name}")
        
        result = {
            'company_name': company_name,
            'data_sources': [],
            'rag_data': None,
            'web_data': None,
            'ai_response': None,
            'provider': self.ai_provider,
            'processing_time': 0,
            'error': None
        }
        
        try:
            # Step 1: Get RAG data (job postings)
            logger.info(f"Step 1/3: Getting RAG data from job postings...")
            rag_data = self.rag_service.get_company_context(company_name)
            if rag_data and rag_data.get('jobs_found', 0) > 0:
                result['rag_data'] = rag_data
                result['data_sources'].append(f"job_postings ({rag_data['jobs_found']} jobs)")
                logger.info(f"[OK] RAG: Found {rag_data['jobs_found']} job postings")
            else:
                logger.info(f"✗ RAG: No job postings found")
            
            # Step 2: Browse company website
            if use_web_browser:
                logger.info(f"Step 2/3: Browsing company website...")
                
                # Check if we already have the website from company data
                known_website = company_data.get('website')
                if known_website:
                    logger.info(f"Using known website from company data: {known_website}")
                    # Browse the known website directly
                    web_data = self.web_browser.browse_website(known_website)
                else:
                    # Extract location from job postings to help search
                    location = None
                    if rag_data and rag_data.get('jobs_found', 0) > 0:
                        # Try to get headquarters from job data
                        jobs = rag_data.get('jobs', [])
                        if jobs:
                            # Use location from first job
                            location = jobs[0].get('company_location') or jobs[0].get('location')
                            if location:
                                logger.info(f"Using location from job postings: {location}")
                    
                    # Search for website if not known
                    web_data = self.web_browser.search_company_info(company_name, location=location)
                if web_data and web_data.get('website'):
                    result['web_data'] = web_data
                    result['data_sources'].append(f"website ({web_data['website']})")
                    logger.info(f"[OK] Web: Found {len(web_data.get('emails', []))} emails, {len(web_data.get('contact_names', []))} names")
                else:
                    logger.info(f"✗ Web: No website found")
            else:
                logger.info(f"Step 2/3: Web browsing disabled")
            
            # Step 3: AI Analysis
            logger.info(f"Step 3/3: AI analysis with {self.ai_provider}...")
            
            # Log what data we're passing to AI
            if result.get('web_data'):
                web_summary = {
                    'website': result['web_data'].get('website'),
                    'emails': len(result['web_data'].get('emails', [])),
                    'phones': len(result['web_data'].get('phones', [])),
                    'addresses': len(result['web_data'].get('addresses', [])),
                    'contact_names': len(result['web_data'].get('contact_names', []))
                }
                logger.info(f"Passing to AI: {web_summary}")
            
            # Build enhanced prompt with all collected data
            enhanced_prompt = self._build_enhanced_prompt(
                company_data,
                rag_data=result.get('rag_data'),
                web_data=result.get('web_data'),
                linkedin_job_url=linkedin_job_url
            )
            
            # Get AI response with enhanced context
            ai_response = self.ai_service.get_contact_details(
                company_data={'company_name': company_name, **company_data},
                linkedin_job_url=linkedin_job_url,
                additional_context=enhanced_prompt  # Pass the enhanced prompt!
            )
            
            logger.info(f"AI response received: {type(ai_response)}")
            
            # Parse JSON if it's a string
            if isinstance(ai_response, str):
                try:
                    import json
                    # Try to extract JSON from markdown code blocks if present
                    ai_response_clean = ai_response.strip()
                    if ai_response_clean.startswith('```json'):
                        # Extract JSON from ```json ... ``` block
                        start_idx = ai_response_clean.find('{')
                        end_idx = ai_response_clean.rfind('}')
                        if start_idx != -1 and end_idx != -1:
                            ai_response_clean = ai_response_clean[start_idx:end_idx+1]
                    elif ai_response_clean.startswith('```'):
                        # Extract JSON from ``` ... ``` block
                        start_idx = ai_response_clean.find('{')
                        end_idx = ai_response_clean.rfind('}')
                        if start_idx != -1 and end_idx != -1:
                            ai_response_clean = ai_response_clean[start_idx:end_idx+1]
                    
                    ai_response = json.loads(ai_response_clean)
                    logger.info("Parsed AI response from JSON string")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse AI response as JSON: {str(e)}")
                    logger.error(f"AI response text: {ai_response[:500]}")  # Log first 500 chars
                    # Return empty contact structure
                    ai_response = {
                        "company": {"name": company_name},
                        "general_contact": {},
                        "decision_makers": [],
                        "notes": "AI returned non-JSON response - no contact information found"
                    }
                except Exception as e:
                    logger.error(f"Failed to parse AI response: {str(e)}")
                    ai_response = {
                        "company": {"name": company_name},
                        "general_contact": {},
                        "decision_makers": [],
                        "notes": "Error parsing AI response"
                    }
            
            # If AI service returns JSON string, we'll enhance it with our web data
            result['ai_response'] = self._enhance_ai_response(
                ai_response,
                web_data=result.get('web_data'),
                rag_data=result.get('rag_data')
            )
            
            contact_count = len(result['ai_response'].get('decision_makers', []))
            logger.info(f"Final result has {contact_count} contacts")
            
            # If no contacts found but we have a website, add helpful message
            if contact_count == 0 and result.get('web_data', {}).get('website'):
                website = result['web_data']['website']
                if 'notes' not in result['ai_response']:
                    result['ai_response']['notes'] = ""
                result['ai_response']['notes'] += f"\n\nNo contact details found on website. Please visit the company website manually: {website}"
                
                # Add common contact page suggestions
                result['ai_response']['suggested_contact_pages'] = [
                    f"{website}/contact",
                    f"{website}/contact-us",
                    f"{website}/about/contact",
                    f"{website}/get-in-touch"
                ]
            
            result['processing_time'] = time.time() - start_time
            
            logger.info(f"[OK] Enhanced contact search complete in {result['processing_time']:.2f}s")
            logger.info(f"  Data sources: {', '.join(result['data_sources'])}")
            
        except Exception as e:
            logger.error(f"Enhanced contact search failed: {str(e)}")
            result['error'] = str(e)
            result['processing_time'] = time.time() - start_time
        
        return result
    
    def _build_enhanced_prompt(
        self,
        company_data: Dict[str, Any],
        rag_data: Optional[Dict],
        web_data: Optional[Dict],
        linkedin_job_url: Optional[str]
    ) -> str:
        """
        Build a super-enhanced prompt with all available data
        This is what makes the AI response so much better
        """
        company_name = company_data.get('company_name', 'Unknown')
        
        sections = []
        
        # Base company info
        sections.append(f"COMPANY: {company_name}")
        
        # RAG Data
        if rag_data and rag_data.get('context'):
            sections.append(f"\n{'='*60}\nJOB POSTINGS DATA (from our database):")
            sections.append(rag_data['context'])
        
        # Web Browsing Data
        if web_data:
            sections.append(f"\n{'='*60}\nWEB RESEARCH (live data):")
            
            if web_data.get('website'):
                sections.append(f"[OK] Website: {web_data['website']}")
            
            if web_data.get('emails'):
                sections.append(f"[OK] Found Emails: {', '.join(web_data['emails'][:5])}")
            
            if web_data.get('phones'):
                sections.append(f"[OK] Found Phones: {', '.join(web_data['phones'][:3])}")
            
            if web_data.get('contact_names'):
                # contact_names should be a list of strings
                names = web_data['contact_names']
                if names and isinstance(names[0], str):
                    sections.append(f"[OK] Found Names: {', '.join(names[:10])}")
                else:
                    sections.append(f"[OK] Found {len(names)} Names")
            
            if web_data.get('linkedin_urls'):
                # linkedin_urls is now a list of dicts with name, title, linkedin_url, confidence
                linkedin_data = web_data['linkedin_urls']
                if linkedin_data:
                    sections.append(f"[OK] Found LinkedIn Profiles:")
                    for i, profile in enumerate(linkedin_data[:10], 1):
                        if isinstance(profile, dict):
                            name = profile.get('name', 'Unknown')
                            title = profile.get('title', '')
                            url = profile.get('linkedin_url', '')
                            if title:
                                sections.append(f"    {i}. {name} - {title}: {url}")
                            else:
                                sections.append(f"    {i}. {name}: {url}")
                        else:
                            # Fallback for string format
                            sections.append(f"    {i}. {profile}")
            
            if web_data.get('description'):
                sections.append(f"[OK] Description: {web_data['description']}")
            
            if web_data.get('contact_page'):
                sections.append(f"[OK] Contact Page: {web_data['contact_page']}")
            
            if web_data.get('team_page'):
                sections.append(f"[OK] Team Page: {web_data['team_page']}")
        
        # LinkedIn Job Reference
        if linkedin_job_url:
            sections.append(f"\n[OK] LinkedIn Job: {linkedin_job_url}")
        
        return "\n".join(sections)
    
    def _enhance_ai_response(
        self,
        ai_response,  # Can be str or dict
        web_data: Optional[Dict],
        rag_data: Optional[Dict]
    ) -> Dict:
        """
        Enhance AI response by injecting real data we found
        This ensures we include actual emails/phones found via web browsing
        """
        try:
            # Parse AI response if it's a string
            if isinstance(ai_response, str):
                response_json = json.loads(ai_response)
            else:
                response_json = ai_response
            
            # Inject web-found emails into general_contact
            if web_data and web_data.get('emails'):
                if 'general_contact' not in response_json:
                    response_json['general_contact'] = {}
                
                # Use first email found as primary
                if not response_json['general_contact'].get('email'):
                    response_json['general_contact']['email'] = web_data['emails'][0]
            
            # Inject web-found phone
            if web_data and web_data.get('phones'):
                if 'general_contact' not in response_json:
                    response_json['general_contact'] = {}
                
                if not response_json['general_contact'].get('phone'):
                    response_json['general_contact']['phone'] = web_data['phones'][0]
            
            # Inject web-found address
            if web_data and web_data.get('addresses'):
                if 'general_contact' not in response_json:
                    response_json['general_contact'] = {}
                
                if not response_json['general_contact'].get('address'):
                    response_json['general_contact']['address'] = web_data['addresses'][0]
            
            # Inject website
            if web_data and web_data.get('website'):
                if 'company' not in response_json:
                    response_json['company'] = {}
                response_json['company']['website'] = web_data['website']
            
            # Add metadata about data sources
            response_json['_metadata'] = {
                'data_sources': [],
                'web_browsing_enabled': bool(web_data),
                'job_postings_found': rag_data.get('jobs_found', 0) if rag_data else 0
            }
            
            if web_data:
                response_json['_metadata']['data_sources'].append('web_browser')
                response_json['_metadata']['web_data'] = {
                    'emails_found': len(web_data.get('emails', [])),
                    'phones_found': len(web_data.get('phones', [])),
                    'addresses_found': len(web_data.get('addresses', [])),
                    'names_found': len(web_data.get('contact_names', [])),
                    'website': web_data.get('website'),
                    # Include actual data for AI to format
                    'all_emails': web_data.get('emails', []),
                    'all_phones': web_data.get('phones', []),
                    'all_addresses': web_data.get('addresses', [])
                }
            
            if rag_data and rag_data.get('jobs_found', 0) > 0:
                response_json['_metadata']['data_sources'].append('job_postings_rag')
            
            return response_json  # Return dict, not JSON string
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI response in _enhance_ai_response: {str(e)}")
            # Return empty contact structure as dict
            return {
                "company": {"name": "Unknown"},
                "general_contact": {},
                "decision_makers": [],
                "notes": "Failed to parse AI response"
            }


# Service getter functions for different AI providers
def get_enhanced_gemini_service() -> EnhancedContactService:
    """Get enhanced service with Gemini AI"""
    return EnhancedContactService(ai_provider='gemini')


def get_enhanced_openai_service() -> EnhancedContactService:
    """Get enhanced service with OpenAI"""
    return EnhancedContactService(ai_provider='openai')
