"""
OpenAI Service for Contact Details Extraction
Uses GPT-4o with structured prompting for high-quality business research
"""
import logging
from typing import Dict, Any, Optional
from openai import OpenAI
from django.conf import settings

logger = logging.getLogger(__name__)

# Import RAG service (lazy to avoid circular imports)
def get_rag_service():
    from apps.dashboard.services.contact_rag_service import get_rag_service as _get_rag
    return _get_rag()


class OpenAIService:
    """Service for OpenAI API interactions - focused on contact research"""
    
    def __init__(self):
        """Initialize OpenAI client"""
        # For now, hardcode the API key (will move to settings later)
        api_key = getattr(settings, 'OPENAI_API_KEY', None) or "YOUR_OPENAI_API_KEY_HERE"
        
        if not api_key or api_key == "YOUR_OPENAI_API_KEY_HERE":
            raise ValueError(
                "OpenAI API key not configured. "
                "Please set OPENAI_API_KEY in your .env file or settings.py"
            )
        
        self.client = OpenAI(api_key=api_key)
        logger.info("OpenAI client initialized successfully")
    
    def get_contact_details(
        self,
        company_data: Dict[str, Any],
        linkedin_job_url: Optional[str] = None,
        additional_context: Optional[str] = None
    ) -> str:
        """
        Get contact details for a company using GPT-4o
        
        Args:
            company_data: Dict with company_name, company_type, company_industry, company_size, job_count
            linkedin_job_url: Optional LinkedIn job posting URL
            additional_context: Optional enhanced context from web browser/RAG services
        
        Returns:
            JSON string with contact details
        """
        if not isinstance(company_data, dict):
            raise ValueError(f"company_data must be a dict, got {type(company_data)}: {company_data}")
        
        company_name = company_data.get('company_name', 'Unknown Company')
        
        try:
            prompt = self._build_contact_details_prompt(company_data, linkedin_job_url, additional_context)
            
            # Use GPT-4o with structured system prompt
            response = self.client.chat.completions.create(
                model="gpt-4o",  # Latest and best model
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.0,  # Low temperature for factual, consistent responses
                max_tokens=4096
            )
            
            result = response.choices[0].message.content
            
            logger.info(f"OpenAI contact details retrieved for {company_name}")
            logger.debug(f"Tokens used: {response.usage.total_tokens} (prompt: {response.usage.prompt_tokens}, completion: {response.usage.completion_tokens})")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get contact details for {company_name}: {str(e)}")
            raise
    
    def _get_system_prompt(self) -> str:
        """
        System prompt that instructs GPT-4o to behave like a professional business research assistant
        Following ChatGPT's recommendations for structured, factual responses
        """
        return """You are a data extraction assistant that processes company information from provided sources.

CRITICAL RULES - READ CAREFULLY:
🚫 NEVER use your training data or general knowledge about companies
🚫 NEVER make up or infer contact names, emails, or LinkedIn profiles
🚫 NEVER hallucinate information not explicitly provided in the context
✅ ONLY extract information that appears in the provided data sources
✅ Use null for ANY data not found in the provided sources
✅ If no contacts are found in the data, return empty decision_makers array

YOUR CAPABILITIES:
- Extract contact information from provided website data and job postings
- Parse email addresses, phone numbers, and names from HTML/text content
- Identify LinkedIn URLs that appear in the source data
- Organize found information into structured JSON format

WHAT YOU CANNOT DO:
- Look up or recall information about companies from your training
- Guess or infer people's names based on typical company structures
- Construct LinkedIn URLs unless they appear in the provided data
- Make assumptions about who works at the company

OUTPUT STRUCTURE:
Always return a valid JSON object with this exact structure:
{
  "company": {
    "name": "Company Name",
    "website": "https://example.com or null",
    "linkedin_company": "https://linkedin.com/company/xxx or null",
    "headquarters": "City, Country or null",
    "description": "Brief factual description or null"
  },
  "general_contact": {
    "email": "info@example.com or null",
    "phone": "+1234567890 or null",
    "contact_form": "https://example.com/contact or null"
  },
  "decision_makers": [
    {
      "name": "Full Name",
      "title": "Job Title",
      "department": "Department",
      "linkedin_url": "https://linkedin.com/in/profile or null",
      "email": "email@company.com or null",
      "confidence": "high/medium/low"
    }
  ],
  "social_media": {
    "twitter": "@handle or null",
    "facebook": "URL or null",
    "youtube": "URL or null"
  },
  "notes": "Any verification notes or additional context"
}

EXTRACTION RULES:
⚠️ Return ONLY the JSON object - no explanations, no markdown formatting, no preamble
⚠️ Use null for ANY field where data is not found in provided sources
⚠️ Empty decision_makers array [] if NO contacts found in data
⚠️ Only include LinkedIn URLs if they EXPLICITLY appear in the provided data
⚠️ Only include emails/phones that were FOUND in web scraping results
⚠️ Mark confidence as "low" for any inferred data, "high" only for explicitly found data

DATA SOURCE PRIORITY:
1. Website scraping results (emails, phones, contact pages found by web browser)
2. Job posting descriptions and contact information
3. If NEITHER source has contact info → return null/empty arrays

FORBIDDEN ACTIONS:
❌ Do NOT use company name to guess executive names
❌ Do NOT construct LinkedIn URLs from assumed name patterns
❌ Do NOT fill in "typical" contact information
❌ Do NOT use your knowledge of real people at real companies
❌ Do NOT provide placeholder or example data

REQUIRED BEHAVIOR:
✅ If web scraping found 0 emails → general_contact.email = null
✅ If no names found in data → decision_makers = []
✅ Be honest in notes field: "No contacts found in provided data sources"
"""
    
    def _build_contact_details_prompt(
        self,
        company_data: Dict[str, Any],
        linkedin_job_url: Optional[str] = None,
        additional_context: Optional[str] = None
    ) -> str:
        """Build user prompt with RAG-enhanced company context"""
        
        company_name = company_data.get('company_name', 'Unknown Company')
        company_type = company_data.get('company_type', 'Not specified')
        company_industry = company_data.get('company_industry', 'Not specified')
        company_size = company_data.get('company_size', 'Not specified')
        job_count = company_data.get('job_count', 0)
        
        linkedin_context = f"\n- LinkedIn Job Posting: {linkedin_job_url}" if linkedin_job_url else ""
        
        # Get RAG-enhanced context from job postings database (only if no additional context provided)
        rag_context = ""
        if not additional_context:
            try:
                rag_service = get_rag_service()
                rag_data = rag_service.get_company_context(company_name)
                if rag_data.get('context'):
                    rag_context = f"\n\n{'='*60}\nDATA FROM JOB POSTINGS DATABASE:\n{'='*60}\n{rag_data['context']}\n{'='*60}\n"
            except Exception as e:
                logger.warning(f"Could not get RAG context: {str(e)}")
        else:
            # Use the enhanced context from web browser service
            rag_context = f"\n\n{'='*60}\nDATA FROM RESEARCH:\n{'='*60}\n{additional_context}\n{'='*60}\n"
        
        return f"""TASK: Extract contact information from the provided data sources below.

⚠️ CRITICAL: Use ONLY the data provided below. Do NOT use your training knowledge about this company.

COMPANY INFORMATION:
- Name: {company_name}
- Type: {company_type}
- Industry: {company_industry}
- Company Size: {company_size}
- Active Job Openings: {job_count}{linkedin_context}

DATA SOURCES PROVIDED BELOW:
{rag_context}

EXTRACTION INSTRUCTIONS:
1. Look ONLY in the data sources above for:
   - Email addresses (from website scraping or job postings)
   - Phone numbers (from website scraping)
   - Contact names (from website scraping or job postings)
   - LinkedIn URLs (ONLY if they appear in the data above)
   
2. If NO contacts found in the data:
   - Return decision_makers: []
   - Set general_contact fields to null
   - In notes field, state: "No contact information found in provided data sources"

3. If SOME contacts found:
   - Only include what was explicitly found in the data
   - Mark confidence as "high" for directly extracted data
   - Prioritize data/analytics decision-makers if found in job postings

4. DO NOT:
   - Look up or recall information about this company from your training data
   - Make up or infer names, emails, or LinkedIn profiles
   - Construct LinkedIn URLs based on name patterns
   - Fill in "typical" or "likely" contact information

Return ONLY the JSON object (no markdown, no explanations)."""


# Singleton instance
_openai_service = None


def get_openai_service() -> OpenAIService:
    """Get or create OpenAI service singleton"""
    global _openai_service
    if _openai_service is None:
        _openai_service = OpenAIService()
    return _openai_service
