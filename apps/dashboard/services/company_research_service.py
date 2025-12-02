"""
Company Contact Research Service
Orchestrates the complete research pipeline:
1. Fetch company data from BigQuery by ID
2. Get RAG context (job postings)
3. Run Enhanced Contact Service (uses Gemini + SerpAPI)
4. Return complete results
"""
import logging
from typing import Dict, Any, Optional
from apps.dashboard.services.bigquery_service import get_bigquery_service
from apps.dashboard.services.contact_rag_service import get_rag_service
from apps.dashboard.services.enhanced_contact_service import get_enhanced_gemini_service

logger = logging.getLogger(__name__)


class CompanyContactResearchService:
    """
    Complete research pipeline for a company
    Just provide company_id - everything else is automatic!
    Uses Gemini 2.5 Pro + SerpAPI for contact extraction
    """
    
    def __init__(self):
        self.bigquery = get_bigquery_service()
        self.rag_service = get_rag_service()
        self.enhanced_contact_service = get_enhanced_gemini_service()
        logger.info("Company Contact Research Service initialized (using Gemini 2.5 Pro)")
    
    def research_company(self, company_id: str) -> Dict[str, Any]:
        """
        Complete research pipeline for a company
        
        Args:
            company_id: UUID of the company in BigQuery
        
        Returns:
            Dict with complete results including company data, contacts, metadata
        """
        try:
            # Step 1: Fetch company from BigQuery
            logger.info(f"Fetching company data for ID: {company_id}")
            company_data = self._fetch_company_data(company_id)
            
            if not company_data:
                return {
                    'success': False,
                    'error': f'Company not found: {company_id}'
                }
            
            company_name = company_data.get('company_name')
            logger.info(f"Found company: {company_name}")
            
            # Step 2: Get RAG context (job postings)
            logger.info(f"Fetching job postings for: {company_name}")
            rag_data = self.rag_service.get_company_context(company_name)
            
            rag_context = None
            jobs_found = 0
            location = None
            if rag_data and rag_data.get('jobs_found', 0) > 0:
                rag_context = rag_data.get('context', '')
                jobs_found = rag_data.get('jobs_found', 0)
                location = rag_data.get('country')  # Extract country from job postings
                if location:
                    logger.info(f"Found {jobs_found} job postings in {location}")
                else:
                    logger.info(f"Found {jobs_found} job postings")
            else:
                logger.info("No job postings found - AI will rely on web research")
            
            # Step 3: Get LinkedIn job URL (first job if available)
            linkedin_job_url = None
            if rag_data and rag_data.get('jobs'):
                first_job = rag_data['jobs'][0]
                linkedin_job_url = first_job.get('url')  # Changed from job_url to url
                if linkedin_job_url:
                    logger.info(f"Using LinkedIn job URL: {linkedin_job_url}")
            
            # Add location to company_data for enhanced contact service
            if location:
                company_data['location'] = location
            
            # Step 4: Run Enhanced Contact Service (Gemini + SerpAPI + Web Browsing)
            # Use exact same call as Columbus Chat - just pass company_data
            logger.info(f"Starting enhanced contact search for: {company_name}")
            research_result = self.enhanced_contact_service.find_contacts(
                company_data=company_data,
                use_web_browser=True
            )
            
            # Step 5: Combine everything
            result = {
                'success': not research_result.get('error'),
                'company_id': company_id,
                'company_data': company_data,
                'jobs_found': jobs_found,
                'research_result': research_result
            }
            
            if result.get('success'):
                logger.info(f"Research completed successfully for: {company_name}")
                # Extract contact count for logging
                ai_response = research_result.get('ai_response', {})
                if isinstance(ai_response, dict):
                    contact_count = len(ai_response.get('decision_makers', []))
                    logger.info(f"Found {contact_count} decision makers")
            else:
                logger.warning(f"Research failed for {company_name}: {research_result.get('error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Research failed for company {company_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'company_id': company_id
            }
    
    def _fetch_company_data(self, company_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch company data from BigQuery by ID
        """
        try:
            query = """
                SELECT 
                    company_id,
                    company_name,
                    status,
                    company_type,
                    description,
                    company_size,
                    tech_stack,
                    company_industry,
                    solution_domain
                FROM `agiliz-sales-tool.zoektrends_job_data.companies`
                WHERE company_id = @company_id
                LIMIT 1
            """
            
            from google.cloud.bigquery import QueryJobConfig, ScalarQueryParameter
            
            job_config = QueryJobConfig(
                query_parameters=[
                    ScalarQueryParameter('company_id', 'STRING', company_id)
                ]
            )
            
            results = list(self.bigquery.client.query(query, job_config=job_config).result())
            
            if not results:
                logger.warning(f"Company not found: {company_id}")
                return None
            
            row = results[0]
            
            # Convert to dict
            company_data = {
                'company_id': row.company_id,
                'company_name': row.company_name,
                'status': row.status,
                'company_type': row.company_type,
                'company_industry': row.company_industry,
                'company_size': row.company_size,
                'description': row.description,
                'tech_stack': row.tech_stack,
                'solution_domain': row.solution_domain
            }
            
            return company_data
            
        except Exception as e:
            logger.error(f"Failed to fetch company {company_id}: {str(e)}")
            return None


# Singleton
_research_service = None


def get_company_research_service() -> CompanyContactResearchService:
    """Get or create research service singleton"""
    global _research_service
    if _research_service is None:
        _research_service = CompanyContactResearchService()
    return _research_service
