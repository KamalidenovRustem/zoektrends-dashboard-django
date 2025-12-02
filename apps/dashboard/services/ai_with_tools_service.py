"""
AI Agent with Web Browsing Tools
This is the CORRECT implementation - AI controls the research process
"""
import logging
from typing import Dict, Any, Optional, List
import json
from openai import OpenAI
from django.conf import settings

logger = logging.getLogger(__name__)


class AIAgentWithTools:
    """
    AI Agent that can use tools (web browsing) to research companies
    This is how ChatGPT works - AI decides what tools to use
    """
    
    def __init__(self):
        api_key = getattr(settings, 'OPENAI_API_KEY', None)
        if not api_key:
            raise ValueError("OpenAI API key required")
        
        self.client = OpenAI(api_key=api_key)
        
        # Import services
        from apps.dashboard.services.web_browser_service import get_web_browser_service
        self.web_browser = get_web_browser_service()
        
        logger.info("AI Agent with Tools initialized")
    
    def research_company_contacts(
        self,
        company_data: Dict[str, Any],
        rag_context: Optional[str] = None,
        linkedin_job_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Research company contacts using AI + Tools
        
        The AI will:
        1. Analyze the company data and RAG context
        2. Decide if it needs to browse the website
        3. Call the browse_website tool if needed
        4. Synthesize all information
        5. Return structured contact details
        
        Args:
            company_data: Company information
            rag_context: Context from RAG (job postings)
            linkedin_job_url: LinkedIn job URL for reference
        
        Returns:
            Dict with results and metadata
        """
        # Store company_data so tools can access it
        self.company_data = company_data
        
        company_name = company_data.get('company_name', 'Unknown')
        
        logger.info(f"AI Agent researching: {company_name}")
        
        # Build initial prompt with RAG context
        initial_prompt = self._build_initial_prompt(
            company_data,
            rag_context,
            linkedin_job_url
        )
        
        # Define tools the AI can use
        tools = self._define_tools()
        
        messages = [
            {
                "role": "system",
                "content": self._get_system_prompt()
            },
            {
                "role": "user",
                "content": initial_prompt
            }
        ]
        
        max_iterations = 10  # Allow thorough exploration (AI stops when done)
        iteration = 0
        tool_calls_made = []
        
        while iteration < max_iterations:
            iteration += 1
            
            logger.info(f"AI Agent iteration {iteration}/{max_iterations}")
            
            # Call AI with tools
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=tools,
                tool_choice="auto",  # Let AI decide
                temperature=0.1
            )
            
            response_message = response.choices[0].message
            
            # Check if AI wants to call tools
            if response_message.tool_calls:
                logger.info(f"AI wants to call {len(response_message.tool_calls)} tools")
                
                # Add AI's message to conversation
                messages.append(response_message)
                
                # Execute each tool call
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    logger.info(f"Executing tool: {function_name} with args: {function_args}")
                    
                    # Execute the tool
                    if function_name == "browse_website":
                        tool_result = self._execute_browse_website(function_args)
                    elif function_name == "search_company_website":
                        tool_result = self._execute_search_website(function_args)
                    else:
                        tool_result = {"error": f"Unknown tool: {function_name}"}
                    
                    tool_calls_made.append({
                        "tool": function_name,
                        "args": function_args,
                        "result": tool_result
                    })
                    
                    # Add tool result to conversation
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": json.dumps(tool_result)
                    })
                
                # Continue to next iteration (AI will process tool results)
                continue
            
            else:
                # AI has finished - no more tool calls
                logger.info("AI has finished research")
                
                final_response = response_message.content
                
                return {
                    "success": True,
                    "company_name": company_name,
                    "contact_details": final_response,
                    "tool_calls": tool_calls_made,
                    "iterations": iteration,
                    "provider": "OpenAI GPT-4o with Tools"
                }
        
        # Max iterations reached - but we still might have useful info
        logger.warning(f"Max iterations reached for {company_name} - returning partial results")
        
        # Try to get the last response from messages
        last_ai_message = None
        for msg in reversed(messages):
            if msg.get('role') == 'assistant' and not msg.get('tool_calls'):
                last_ai_message = msg.get('content')
                break
        
        if last_ai_message:
            return {
                "success": True,
                "company_name": company_name,
                "contact_details": last_ai_message,
                "tool_calls": tool_calls_made,
                "iterations": iteration,
                "provider": "OpenAI GPT-4o with Tools",
                "warning": "Max iterations reached - results may be incomplete"
            }
        
        return {
            "success": False,
            "error": "Max iterations reached without final response",
            "company_name": company_name,
            "tool_calls": tool_calls_made,
            "iterations": iteration
        }
    
    def _get_system_prompt(self) -> str:
        """System prompt that explains the AI's role and capabilities"""
        return """You are an expert business intelligence researcher for Agiliz, a data consultancy specializing in Google Cloud Platform, BigQuery, and Looker.

YOUR MISSION:
Find the best contacts at target companies for potential partnerships and business opportunities.

YOUR TOOLS:
- browse_website: Browse a company's website to find contact information, team members, and details
- search_company_website: Search for a company's website URL if you don't have it

RESEARCH PROCESS:
1. Analyze the company information and job posting data provided
2. If LinkedIn job URL is provided, browse it FIRST:
   - Extract the company LinkedIn profile URL (e.g., linkedin.com/company/pm-group_165501)
   - Browse the company LinkedIn page to find "Visit website" or "Learn more" button
   - This gives you the official company website URL
3. If no LinkedIn URL or website not found, use search_company_website
   - Try domain variations like company-global.com, companygroup.com, etc.
4. CHECK THESE PAGES on company website (contacts are often here):
   - /locations, /offices (IMPORTANT - often lists regional contacts with names)
   - /team, /our-team, /leadership, /management
   - /about, /about-us, /company, /people
   - /contact, /contact-us
5. Look for NAME + TITLE patterns like:
   - "John Smith - CEO"
   - "Jane Doe, Chief Technology Officer"  
   - "Business Development: Bob Johnson"
   - Location pages often show: "Brussels Office: Wouter Celen, Business Development"
6. Synthesize all information into a structured JSON response

IMPORTANT RULES:
- EXPLORE multiple pages - don't stop at homepage or contact page
- Companies often list leadership on /locations, /offices, or regional pages
- Look for Business Development, Sales Directors, CTOs, CDOs, Managing Directors
- Extract LinkedIn URLs when found next to names
- Focus on C-level executives, VPs, Directors in data/analytics/technology
- Only include information you're confident about
- Mark confidence levels (high/medium/low) for each contact
- If you can't find real contacts after checking multiple pages, say so - don't make up placeholder data

RESPONSE FORMAT:
Always return a valid JSON object with this structure:
{
  "company": {
    "name": "Company Name",
    "website": "https://...",
    "linkedin_company": "https://linkedin.com/company/...",
    "headquarters": "City, Country",
    "description": "Brief description"
  },
  "general_contact": {
    "email": "info@company.com",
    "phone": "+1234567890",
    "contact_form": "https://..."
  },
  "decision_makers": [
    {
      "name": "Full Name",
      "title": "Job Title",
      "department": "Department",
      "linkedin_url": "https://linkedin.com/in/...",
      "email": "email@company.com",
      "confidence": "high/medium/low"
    }
  ],
  "notes": "Your insights and recommendations for Agiliz"
}"""
    
    def _build_initial_prompt(
        self,
        company_data: Dict[str, Any],
        rag_context: Optional[str],
        linkedin_job_url: Optional[str]
    ) -> str:
        """Build the initial research prompt"""
        
        company_name = company_data.get('company_name', 'Unknown')
        
        prompt_parts = [
            f"RESEARCH TARGET: {company_name}",
            f"Industry: {company_data.get('company_industry', 'Unknown')}",
            f"Size: {company_data.get('company_size', 'Unknown')}",
            f"Type: {company_data.get('company_type', 'Unknown')}"
        ]
        
        if linkedin_job_url:
            prompt_parts.append(f"\nLinkedIn Job Posting: {linkedin_job_url}")
        
        if rag_context:
            prompt_parts.append(f"\n{'-'*60}\nJOB POSTINGS DATA FROM OUR DATABASE:\n{'-'*60}")
            prompt_parts.append(rag_context)
            prompt_parts.append("-"*60)
        
        prompt_parts.append("""
YOUR TASK:
Research this company and find the best contacts for Agiliz to reach out to.

STEPS:
1. Analyze the job posting data above (if provided)
2. If you need more information, use the browse_website tool to check their website
3. Find decision-makers in data/analytics/technology
4. Return structured contact information in JSON format

Start your research now. Use tools if you need more information.""")
        
        return "\n".join(prompt_parts)
    
    def _define_tools(self) -> List[Dict]:
        """Define tools the AI can use"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "browse_website",
                    "description": "Browse any webpage to extract information. Can browse: company websites (check /locations, /offices, /team pages for contacts), LinkedIn job postings (to find company links), or any URL. Extracts: emails, phones, names with titles, LinkedIn profile URLs.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "The full URL to browse (company website, LinkedIn job posting, or any page)"
                            },
                            "focus": {
                                "type": "string",
                                "description": "What to focus on: 'contacts' for contact info, 'team' for people/leadership, 'about' for company info, 'all' for everything",
                                "enum": ["contacts", "team", "about", "all"]
                            }
                        },
                        "required": ["url"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_company_website",
                    "description": "Find a company's website URL if you don't have it. Use this before browse_website if you need to find the URL.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "company_name": {
                                "type": "string",
                                "description": "The company name to search for"
                            }
                        },
                        "required": ["company_name"]
                    }
                }
            }
        ]
    
    def _execute_browse_website(self, args: Dict) -> Dict:
        """Execute the browse_website tool"""
        url = args.get('url')
        focus = args.get('focus', 'all')
        
        logger.info(f"Browsing website: {url} (focus: {focus})")
        
        try:
            page_data = self.web_browser._browse_page(url)
            
            if not page_data:
                return {"error": f"Could not browse {url}"}
            
            result = {
                "url": url,
                "success": True,
                "emails": page_data.get('emails', [])[:5],
                "phones": page_data.get('phones', [])[:3],
                "names": page_data.get('names', [])[:10],
                "description": page_data.get('description')
            }
            
            # Find key pages
            key_pages = self.web_browser._find_key_pages(url, page_data.get('soup'))
            if key_pages:
                result['key_pages'] = key_pages
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to browse {url}: {str(e)}")
            return {"error": str(e), "url": url}
    
    def _execute_search_website(self, args: Dict) -> Dict:
        """Execute the search_company_website tool"""
        company_name = args.get('company_name')
        
        # Extract location from company_data if available
        location = self.company_data.get('location') if hasattr(self, 'company_data') else None
        
        if location:
            logger.info(f"Searching for website: {company_name} (Location: {location})")
        else:
            logger.info(f"Searching for website: {company_name}")
        
        try:
            # Use the improved web search service with location filtering
            from apps.dashboard.services.web_search_service import get_web_search_service
            search_service = get_web_search_service()
            website = search_service.search_company_website(company_name, location)
            
            if website:
                return {
                    "success": True,
                    "company_name": company_name,
                    "website": website,
                    "message": f"Found official website: {website}"
                }
            else:
                return {
                    "success": False,
                    "company_name": company_name,
                    "error": "Could not find website via web search. Try different search terms or check if the company has an online presence."
                }
        
        except Exception as e:
            logger.error(f"Failed to search for {company_name}: {str(e)}")
            return {"error": str(e), "company_name": company_name}


# Singleton
_ai_agent = None

def get_ai_agent_with_tools() -> AIAgentWithTools:
    """Get or create AI agent singleton"""
    global _ai_agent
    if _ai_agent is None:
        _ai_agent = AIAgentWithTools()
    return _ai_agent
