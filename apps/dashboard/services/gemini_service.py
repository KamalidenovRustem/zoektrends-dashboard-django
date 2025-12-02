"""
Gemini AI Service
Handles interactions with Google's Gemini AI via Vertex AI
For analytics chat and contact details extraction
"""
import logging
from typing import List, Dict, Any, Optional
from google.cloud import aiplatform
from google.oauth2 import service_account
from django.conf import settings
import os
import vertexai
from vertexai.generative_models import GenerativeModel, ChatSession

logger = logging.getLogger(__name__)

# Import RAG service (lazy to avoid circular imports)
def get_rag_service():
    from apps.dashboard.services.contact_rag_service import get_rag_service as _get_rag
    return _get_rag()


class GeminiService:
    """Service for interacting with Gemini AI"""
    
    def __init__(self):
        self.project_id = settings.GOOGLE_CLOUD['PROJECT_ID']
        # Use europe-west1 which supports gemini-2.5-pro (GA)
        self.location = 'europe-west1'
        self.credentials_path = settings.GOOGLE_CLOUD['CREDENTIALS_PATH']
        
        # Initialize Vertex AI
        self._initialize_vertex_ai()
    
    def _initialize_vertex_ai(self):
        """Initialize Vertex AI with credentials"""
        try:
            if not self.credentials_path or not os.path.exists(self.credentials_path):
                logger.error(f"Credentials file not found: {self.credentials_path}")
                return
            
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path
            )
            
            vertexai.init(
                project=self.project_id,
                location=self.location,
                credentials=credentials
            )
            
            logger.info("Vertex AI initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Vertex AI: {str(e)}")
    
    def generate_content(
        self,
        prompt: str,
        model_name: str = "gemini-1.5-pro",
        temperature: float = 0.7,
        max_tokens: int = 2048
    ) -> str:
        """
        Generate content using Gemini
        
        Args:
            prompt: The prompt to send to Gemini
            model_name: Model to use (gemini-1.5-pro, gemini-1.5-flash, etc.)
            temperature: Creativity level (0-1)
            max_tokens: Maximum tokens in response
        
        Returns:
            Generated text response
        """
        try:
            model = GenerativeModel(model_name)
            
            generation_config = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            }
            
            response = model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            return response.text
            
        except Exception as e:
            logger.error(f"Gemini content generation failed with model {model_name}: {str(e)}")
            
            # Try fallback: gemini-2.5-pro -> gemini-1.5-pro -> gemini-1.5-flash
            if "2.5" in model_name or "3" in model_name:
                logger.warning("Trying fallback to gemini-1.5-pro...")
                try:
                    model = GenerativeModel("gemini-1.5-pro")
                    response = model.generate_content(
                        prompt,
                        generation_config=generation_config
                    )
                    logger.info("Fallback to gemini-1.5-pro succeeded")
                    return response.text
                except Exception as e2:
                    logger.warning(f"gemini-1.5-pro also failed: {str(e2)}, trying gemini-1.5-flash...")
                    try:
                        model = GenerativeModel("gemini-1.5-flash")
                        response = model.generate_content(
                            prompt,
                            generation_config=generation_config
                        )
                        logger.info("Fallback to gemini-1.5-flash succeeded")
                        return response.text
                    except Exception as e3:
                        logger.error(f"All fallbacks failed: {str(e3)}")
            
            raise
    
    def chat(
        self,
        message: str,
        chat_history: List[Dict[str, str]] = None,
        model_name: str = "gemini-1.5-pro"
    ) -> str:
        """
        Send a chat message to Gemini with history
        
        Args:
            message: User's message
            chat_history: Previous chat history
            model_name: Model to use
        
        Returns:
            AI response
        """
        try:
            model = GenerativeModel(model_name)
            chat = model.start_chat()
            
            # Load chat history if provided
            if chat_history:
                for msg in chat_history:
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    # Note: Vertex AI chat history format may differ
                    # This is simplified
            
            # Send message
            response = chat.send_message(message)
            
            return response.text
            
        except Exception as e:
            logger.error(f"Gemini chat failed: {str(e)}")
            raise
    
    def get_contact_details(
        self,
        company_data: Dict[str, Any],
        linkedin_job_url: Optional[str] = None,
        additional_context: Optional[str] = None
    ) -> str:
        """
        Get company contact details using Gemini with full company context
        
        Args:
            company_data: Full company information dict with keys:
                - company_name: str
                - company_type: str (e.g., 'Consulting (Business)')
                - company_industry: str (e.g., 'IT Services and IT Consulting')
                - company_size: str (e.g., '1000+')
                - job_count: int
            linkedin_job_url: Optional LinkedIn job posting URL for context
        
        Returns:
            JSON formatted contact details
        """
        # Validate company_data is a dict
        if not isinstance(company_data, dict):
            raise ValueError(f"company_data must be a dict, got {type(company_data)}: {company_data}")
        
        prompt = self._build_contact_details_prompt(company_data, linkedin_job_url, additional_context)
        
        try:
            # Use Gemini 2.5 Pro - GA release, most advanced reasoning model
            logger.info(f"Using Gemini 2.5 Pro for contact extraction: {company_data.get('company_name', 'Unknown')}")
            response = self.generate_content(
                prompt,
                model_name="gemini-2.5-pro",
                temperature=0.2,  # Very low temperature for factual accuracy
                max_tokens=8192  # Increased to ensure complete JSON responses
            )
            
            logger.info(f"Gemini 2.5 Pro response received ({len(response)} characters)")
            return response
            
        except Exception as e:
            logger.error(f"Failed to get contact details for {company_data.get('company_name', 'Unknown')}: {str(e)}")
            raise
    
    def _build_contact_details_prompt(
        self,
        company_data: Dict[str, Any],
        linkedin_job_url: Optional[str] = None,
        additional_context: Optional[str] = None
    ) -> str:
        """Build engineered prompt for contact details extraction with RAG-enhanced context"""
        
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
        
        prompt = f"""You are a data extraction assistant that processes company information from provided sources.

CRITICAL RULES - READ CAREFULLY:
⛔ NEVER HALLUCINATE NAMES - This is the #1 most important rule
⛔ NEVER make up or infer contact names, emails, or LinkedIn profiles
⛔ NEVER use your training data or general knowledge about companies
⛔ NEVER create fake names like "John Smith" or "Jane Doe"
⛔ NEVER guess names based on job titles
⛔ ONLY extract REAL names that appear explicitly in the provided data sources below
- If NO REAL NAMES are found in the data, return empty decision_makers array []
- Use null for ANY data not found in the provided sources
- If you see "About Us" or "Team" page content, extract ONLY the real names shown there

PRIORITY LOCATION INSTRUCTIONS:
- This company operates in BENELUX (Belgium, Netherlands, Luxembourg)
- PRIORITIZE finding contact information for the NETHERLANDS office/headquarters
- If multiple locations exist, prefer Dutch office contacts over other regions
- Look for addresses in Netherlands (postal codes like 1234 AB format)
- Look for Dutch phone numbers (format: +31 or starting with 0)
- The job postings we found are from NETHERLANDS, so focus on that office

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
   - REAL contact names (from "About", "Team", "Our Story", "Leadership" pages)
   - Email addresses (from website scraping or job postings)
   - Phone numbers (prioritize +31 numbers for Netherlands)
   - Physical addresses (prioritize Netherlands addresses with Dutch postal codes)
   - LinkedIn profile URLs (personal profiles like linkedin.com/in/name)
   - LinkedIn company page URLs (like linkedin.com/company/name)
   
2. For finding REAL names and LinkedIn profiles on websites:
   - Check "About Us" / "About" / "Over Ons" pages
   - Check "Team" / "Our Team" / "Our Story" pages
   - Check "Leadership" / "Management" pages
   - Check "Contact" pages
   - Extract names with their titles (e.g., "Matthijs Brouns - CTO")
   - ONLY include names that are explicitly shown on these pages
   - If a name has a LinkedIn link next to it, extract that LinkedIn URL
   - LinkedIn URLs look like: linkedin.com/in/firstname-lastname or /company/companyname
   
3. If NO REAL NAMES found in the data:
   - Return decision_makers: []
   - Set general_contact fields to null
   - In notes field, state: "No contact names found in provided data sources"
   - NEVER fill in fake names

4. If REAL NAMES found:
   - Include ONLY names that were explicitly shown in About/Team pages
   - Include their exact titles as shown on the website
   - If a LinkedIn profile URL appears next to their name, include it in the linkedin_url field
   - Mark confidence as "high" for directly extracted data from About pages
   - Prioritize data/analytics decision-makers if found
   - Include FULL physical address if found (street, postal code, city, country)

5. ⛔ ABSOLUTE PROHIBITIONS:
   - DO NOT make up names like "John Doe", "Jane Smith", etc.
   - DO NOT infer names from job titles ("Head of Sales" ≠ create fake name)
   - DO NOT use your training data or general knowledge
   - DO NOT construct LinkedIn URLs unless they appear in the data
   - DO NOT fill in "typical" or "likely" contact information
   - DO NOT hallucinate - if uncertain, return empty array []

Return ONLY this JSON structure (no markdown, no explanations):
{{
  "company": {{
    "name": "{company_name}",
    "website": null,
    "linkedin_company": null,
    "headquarters": null,
    "description": null
  }},
  "general_contact": {{
    "email": null,
    "phone": null,
    "contact_form": null
  }},
  "decision_makers": [],
  "social_media": {{
    "twitter": null,
    "facebook": null,
    "youtube": null
  }},
  "notes": "No contact information found in provided data sources"
}}

Focus on C-level, VP/Director of Sales/Marketing/IT, and Business Development contacts. Return ONLY the JSON object, nothing else.
"""
        
        return prompt
    
    def analyze_data(
        self,
        data_summary: str,
        user_question: str
    ) -> str:
        """
        Analyze data and answer questions about it
        
        Args:
            data_summary: Summary of the data
            user_question: User's question
        
        Returns:
            AI analysis and answer
        """
        prompt = f"""You are a data analyst for a job market analytics platform.

Current data summary:
{data_summary}

User's question: {user_question}

Provide a clear, professional answer based on the data. Include insights and trends where relevant.
"""
        
        try:
            response = self.generate_content(
                prompt,
                temperature=0.5,  # Balanced creativity
                max_tokens=1024
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Data analysis failed: {str(e)}")
            raise

    def generate_analytics_response(
        self,
        user_message: str,
        context_data: Dict[str, Any] = None
    ) -> str:
        """
        Generate analytics chat response using Gemini
        
        Args:
            user_message: User's question or message
            context_data: Dictionary with job market statistics
        
        Returns:
            AI-generated response
        """
        # Build context from data
        context = ""
        if context_data:
            context = f"""
Current Job Market Statistics:
- Total Jobs: {context_data.get('total_jobs', 'N/A')}
- Total Companies: {context_data.get('total_companies', 'N/A')}
- Data Sources: {context_data.get('total_sources', 'N/A')}
"""
        
        prompt = f"""You are Columbus AI, an expert analytics assistant for job market intelligence.

{context}

User Question: {user_message}

Provide a helpful, professional response. If the question is about job trends, companies, or technologies:
- Analyze the data thoughtfully
- Provide actionable insights
- Suggest follow-up actions if relevant
- Use bullet points for clarity where appropriate

If the question is outside your scope, politely guide the user to relevant topics.

Keep responses concise (2-3 paragraphs maximum) and friendly.
"""
        
        try:
            response = self.generate_content(
                prompt,
                model_name="gemini-2.0-flash-exp",  # Fast model for chat
                temperature=0.7,
                max_tokens=512
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Analytics chat generation failed: {str(e)}")
            return "I apologize, but I'm having trouble processing your request right now. Please try again in a moment."



# Singleton instance
_gemini_service = None

def get_gemini_service() -> GeminiService:
    """Get or create GeminiService singleton"""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service
