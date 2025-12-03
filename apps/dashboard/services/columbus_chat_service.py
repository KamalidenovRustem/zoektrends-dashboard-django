"""
Columbus Chat AI Service
Conversational AI for intelligent prospect recommendations
Supports both OpenAI GPT-4o and Google Vertex AI (Gemini 2.5 Pro)
"""
from typing import Dict, List, Any, Optional
import json
import logging
import os

logger = logging.getLogger(__name__)


class ColumbusChatAI:
    """
    Conversational AI assistant for Agiliz prospect discovery
    
    Capabilities:
    - Natural language queries about companies
    - Tech stack-specific searches
    - Top prospect recommendations
    - Industry/size filtering
    - Activity-based sorting
    
    Supports two AI providers:
    - OpenAI (GPT-4o) - Set AI_PROVIDER=openai
    - Vertex AI (Gemini 2.5 Pro) - Set AI_PROVIDER=vertex (default)
    """
    
    def __init__(self):
        # Determine AI provider
        self.provider = os.getenv('AI_PROVIDER', 'vertex').lower()
        self.conversation_history = []
        self.last_company_results = []  # Cache last company results for follow-up questions
        
        if self.provider == 'openai':
            self._init_openai()
        elif self.provider == 'vertex':
            self._init_vertex()
        else:
            raise ValueError(f"Unsupported AI_PROVIDER: {self.provider}. Use 'openai' or 'vertex'")
        
        logger.info(f"Columbus Chat AI initialized with provider: {self.provider}")
    
    def _init_openai(self):
        """Initialize OpenAI client"""
        from openai import OpenAI
        
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o"
        logger.info("Using OpenAI GPT-4o")
    
    def _init_vertex(self):
        """Initialize Vertex AI (Gemini) client"""
        import vertexai
        from vertexai.generative_models import GenerativeModel
        
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT_ID')
        location = os.getenv('GOOGLE_CLOUD_REGION', 'europe-west1')
        
        if not project_id:
            raise ValueError("GOOGLE_CLOUD_PROJECT_ID environment variable not set")
        
        # Use europe-west1 region with Gemini 2.5 Pro (GA release)
        vertexai.init(project=project_id, location='europe-west1')
        self.model = GenerativeModel('gemini-2.5-pro')
        self.client = None  # Vertex doesn't use a client object
        logger.info(f"Using Vertex AI Gemini 2.5 Pro in europe-west1")
        
        # System prompt defining Columbus AI personality and capabilities
        self.system_prompt = """You are Columbus AI, Agiliz's intelligent sales assistant. You help identify and analyze potential partners and prospects based on job posting data.

**About Agiliz:**
- We provide data activation services using GCP stack (BigQuery, Looker, Vertex AI) and MicroStrategy
- We focus on Belgium and Netherlands markets
- We help businesses turn data into actionable insights
- **TARGET CLIENTS**: Retail, Manufacturing, Healthcare, Finance, Logistics, Energy - companies that NEED data services
- **AVOID**: Google, tech giants, consulting firms - they are our partners/competitors, not clients

**Your Capabilities:**
1. Find companies by technology (BigQuery, Looker, GCP, MicroStrategy, etc.)
2. Identify top prospects based on scoring criteria
3. Filter by industry, company size, job activity
4. Recommend new/trending companies
5. Analyze company fit for partnerships
6. Answer follow-up questions about previously shown companies
7. Handle complex multi-criteria searches (e.g., "healthcare companies using Vertex AI")
8. Analyze company data challenges and provide Agiliz strategic recommendations (consulting/staffing opportunities)

**Multi-Criteria Searches:**
- When user requests multiple filters (technology + industry, or other combinations):
  * AUTOMATICALLY apply all filters - DO NOT ask for permission
  * Call the appropriate functions to handle all criteria
  * Examples:
    - "Technology companies in healthcare using Vertex AI" → Search by tech="Vertex AI", industry_filter="healthcare"
    - "Financial services using BigQuery" → Search by tech="BigQuery", industry_filter="financial"
    - "Top 5 retail companies" → Get top prospects, filter by industry="retail", limit=5
- Be autonomous and decisive - users expect you to handle their full request without asking for clarification unless truly ambiguous
- If a multi-criteria search returns NO results:
  * Automatically try broader searches (e.g., search for just the technology without industry filter)
  * Present the broader results with a clear explanation
  * Example: "No healthcare companies using Vertex AI were found. However, here are 5 companies using Vertex AI across all industries..."
  * DO NOT ask permission to broaden - just do it and explain what you did

**Context Awareness:**
- When users ask follow-up questions like:
  * "give me an overview of these companies"
  * "tell me more about them"  
  * "show me details"
  * "get me details of [company name]"
- They are ALWAYS referring to companies from the IMMEDIATELY PREVIOUS response
- The system automatically injects those companies into your context
- You MUST use the actual data from context (company descriptions, tech stacks, job counts, locations)
- DO NOT provide generic descriptions - use the specific data from the database
- The company cards will display automatically with full details
- Your summary should highlight KEY FACTS from the actual data (not general knowledge)

**When User Requests Company Details:**
- When user asks: "company details of [company]" or "tell me about [company]"
- Call get_company_details function
- If a SINGLE company is found, the function returns a 'message' field with:
  1. Company overview
  2. **Data Challenges** section (2-3 biggest data challenges)
  3. **Agiliz Next Steps** section (strategic recommendations)
  4. Suggested next action (fetch contact details)
- You MUST include the complete 'message' content in your response
- Present it clearly with proper formatting, preserving all sections
- Example response: "Here are the details for **Xccelerated**:\n\n[paste the complete message content from function result]"
- The message field contains the full analysis - display it in full, don't summarize

**When User Requests Company AND Contact Details:**
- When user asks: "get me company and contact details for [company]"
- ALWAYS call BOTH functions in the same response:
  1. First call get_company_details (includes strategy analysis automatically)
  2. Then call get_company_contacts to fetch contact information
- Provide a brief summary mentioning company overview, strategy analysis, AND contact search
- Example: "Here are the details for **Genmab** with strategic analysis. I'm also searching for contact information..."

**Formatting Contact Details in Your Response:**
- When get_company_contacts returns data, format it in a clear, readable way
- ALWAYS include these sections if data is found:
  * **Website**: Display the company website URL
  * **Netherlands Office** (prioritize for Benelux companies):
    - **Address**: Full physical address (street, postal code, city, country)
    - **Phone**: Include country code (e.g., +31 30 2 123 123)
  * **General Contact**: Any general email or main contact info
  * **Decision Makers**: List names, titles, emails if found from job postings
- Example format:
  ```
  **Contact Information for Genmab (Netherlands Office):**
  
  📍 **Address**: Uppsalalaan 15, 3584 CT Utrecht, The Netherlands
  
  📞 **Phone**: +31 30 2 123 123
  
  🌐 **Website**: https://www.genmab.com
  ```
- If NO contact details found, explain what was searched and suggest LinkedIn outreach

**Scoring Criteria:**
- **Hot Prospects (70+ score)**: Retail, manufacturing, healthcare, finance companies with GCP stack and moderate hiring (5-20 jobs)
- **Warm Leads (50-69)**: Similar sectors with some tech alignment or less hiring activity
- **Cold Leads (30-49)**: Weak alignment or unsuitable industry
- **Avoid (<30)**: Tech giants (Google, Microsoft), consulting firms, companies with 50+ jobs (too enterprise)

**CRITICAL: Target Company Profile**
- **IDEAL**: Mid-size companies (100-1000 employees) in retail, manufacturing, healthcare, logistics, finance
- **IDEAL HIRING**: 3-15 open positions (indicates growth but not huge enterprise)
- **AVOID**: Technology companies (Google, bol.com etc.) - they build their own solutions
- **AVOID**: Companies with 50+ jobs - these are tech giants who don't need external help
- **AVOID**: Consulting/Staffing firms - these are competitors

**CRITICAL RESPONSE RULES:**
❌ NEVER return raw JSON data in your text response
❌ NEVER list company details like IDs, descriptions, full tech stacks in your message  
❌ NEVER include code blocks with company arrays
❌ NEVER hallucinate contact information (emails, phone numbers, names) - ALWAYS use get_company_contacts function
❌ NEVER call a function more than once per turn - if you get 0 results, accept it and explain to the user
❌ NEVER write Python code like print() or try to call functions in unusual ways - only use the proper function calling mechanism
✅ USE markdown formatting for readability:
  - **Bold** for company names and important terms
  - Bullet points (*) for lists
  - Line breaks for structure
✅ Provide brief summaries mentioning: number of companies, key highlights, main insights
✅ For contact requests: Call get_company_contacts function - don't invent data
✅ For strategy questions: Call analyze_company_strategy function for data challenges and Agiliz recommendations
  - When user asks about data challenges, next steps, or whether to contact/staff a company
  - Examples: "What are Xccelerated's data challenges?", "Should we contact them?", "Analyze Xccelerated for Agiliz"
✅ Company cards will display automatically below your text - keep your summary concise
✅ When a search returns 0 results:
  - Accept the result - do NOT try to call the function again
  - Explain to the user what was searched for
  - Suggest alternative searches or related technologies they could try
  - Be helpful and constructive, not apologetic

**Example GOOD response for "give me overview":**
"Here are **5 top prospects** - all are retail/manufacturing/healthcare companies that could benefit from our data services:

* **Albert Heijn** - Retail chain with **8 jobs**, using BigQuery for analytics 🔥 Hot Prospect
* **Philips Healthcare** - Medical devices with **12 jobs**, expanding data team ⭐ Warm Lead  
* **DSM** - Manufacturing/nutrition with **6 jobs**, GCP migration ⭐ Warm Lead

These mid-size companies are actively hiring data talent and could benefit from our consulting and staffing services."
(Company cards will automatically display below with full details)

**Example BAD response:**
```json
[{"company": "Google", "company_id": "123...", "job_count": 17}]
```
or
"Google: A multinational technology company..." (generic Wikipedia-style description instead of database facts)
or
"Contact: info@company.com, Phone: +31..." (hallucinated data)

**IMPORTANT:** 
- When you return a response after calling a function that found companies, those companies WILL appear as rich cards in the UI
- When answering follow-up questions about cached companies, those companies WILL appear as cards
- Your text response should be BRIEF - the cards show all the details

**Tone:** Professional, concise, actionable"""
        
        # Available functions for the AI
        self.available_functions = {
            'search_companies_by_tech': self._search_by_tech,
            'get_top_prospects': self._get_top_prospects,
            'get_new_companies': self._get_new_companies,
            'filter_by_industry': self._filter_by_industry,
            'get_company_details': self._get_company_details,
            'get_company_contacts': self._get_company_contacts,
            'analyze_company_strategy': self._analyze_company_strategy,
            'filter_by_job_count': self._filter_by_job_count
        }
        
        logger.info("Columbus Chat AI initialized")
    
    def chat(self, user_message: str, context: Dict[str, Any] = None) -> Dict[str, str]:
        """
        Process user message and return AI response
        
        Args:
            user_message: User's question/request
            context: Optional context (e.g., available companies data)
            
        Returns:
            {
                'response': str - AI response text,
                'function_calls': List - Functions called during response,
                'data': Any - Structured data if applicable
            }
        """
        # Detect follow-up questions and use cached companies
        # Only treat as follow-up if it's asking about previously mentioned companies
        # NOT if it's a new search request with different criteria
        follow_up_phrases = [
            'overview of', 'details about', 'tell me about', 'information on',
            'contact details', 'contacts for', 'get me contact',
            'more about', 'details for', 'overview for'
        ]
        
        # Check if message contains any follow-up phrase
        is_follow_up = any(phrase in user_message.lower() for phrase in follow_up_phrases)
        
        # Don't treat as follow-up if it contains new search keywords
        new_search_keywords = ['top', 'find', 'search', 'show me companies', 'list', 'get companies', 'which companies']
        is_new_search = any(keyword in user_message.lower() for keyword in new_search_keywords)
        
        if self.last_company_results and is_follow_up and not is_new_search:
            # This is a follow-up about previously mentioned companies
            logger.info(f"Follow-up question detected. Using {len(self.last_company_results)} cached companies from previous search")
            if not context:
                context = {}
            context['companies'] = self.last_company_results
        
        if self.provider == 'openai':
            return self._chat_openai(user_message, context)
        else:
            return self._chat_vertex(user_message, context)
    
    def _chat_openai(self, user_message: str, context: Dict[str, Any] = None) -> Dict[str, str]:
        """OpenAI chat implementation"""
        try:
            # Add user message to history
            self.conversation_history.append({
                'role': 'user',
                'content': user_message
            })
            
            # Prepare messages for API
            messages = [
                {'role': 'system', 'content': self.system_prompt},
                *self.conversation_history
            ]
            
            # Call OpenAI with function calling
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                functions=self._get_function_definitions(),
                function_call='auto',
                temperature=0.1,
                max_tokens=2000
            )
            
            message = response.choices[0].message
            function_calls_made = []
            function_results = {}
            
            # Handle function calling
            if message.function_call:
                function_name = message.function_call.name
                function_args = json.loads(message.function_call.arguments)
                
                logger.info(f"Columbus AI calling function: {function_name} with args: {function_args}")
                
                # Execute function with context
                if context:
                    function_args['context'] = context
                
                function_result = self.available_functions[function_name](**function_args)
                function_calls_made.append(function_name)
                function_results[function_name] = function_result
                
                # Add function result to conversation
                self.conversation_history.append({
                    'role': 'function',
                    'name': function_name,
                    'content': json.dumps(function_result)
                })
                
                # Get final response with function result
                messages.append({
                    'role': 'function',
                    'name': function_name,
                    'content': json.dumps(function_result)
                })
                
                final_response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.1,
                    max_tokens=2000
                )
                
                response_text = final_response.choices[0].message.content
            else:
                response_text = message.content
            
            # Add assistant response to history
            self.conversation_history.append({
                'role': 'assistant',
                'content': response_text
            })
            
            # Extract companies array from function results for UI display
            # Aggregate companies from ALL function calls (in case multiple functions returned companies)
            companies_data = []
            if function_results:
                logger.info(f"OpenAI function results keys: {function_results.keys()}")
                for func_name, result in function_results.items():
                    logger.info(f"Checking result from {func_name}: type={type(result)}, has 'companies'={isinstance(result, dict) and 'companies' in result}")
                    if isinstance(result, dict) and 'companies' in result and result['companies']:
                        companies_data.extend(result['companies'])
                        logger.info(f"[OK] Added {len(result['companies'])} companies from {func_name}")
                
                if companies_data:
                    # Remove duplicates based on company_id
                    seen_ids = set()
                    unique_companies = []
                    for company in companies_data:
                        company_id = company.get('company_id')
                        if company_id and company_id not in seen_ids:
                            seen_ids.add(company_id)
                            unique_companies.append(company)
                    companies_data = unique_companies
                    self.last_company_results = companies_data  # Cache for follow-up questions
                    logger.info(f"[OK] Total unique companies: {len(companies_data)}")
                else:
                    companies_data = None
            else:
                logger.info("No function results to extract companies from")
            
            return {
                'response': response_text,
                'function_calls': function_calls_made,
                'data': companies_data  # UI expects array of companies
            }
            
        except Exception as e:
            logger.error(f"OpenAI Chat error: {str(e)}", exc_info=True)
            return {
                'response': f"I apologize, but I encountered an error: {str(e)}. Please try rephrasing your question.",
                'function_calls': [],
                'data': None
            }
    
    def _chat_vertex(self, user_message: str, context: Dict[str, Any] = None) -> Dict[str, str]:
        """Vertex AI (Gemini) chat implementation"""
        try:
            from vertexai.generative_models import FunctionDeclaration, Tool, GenerationConfig, GenerativeModel, Content, Part
            
            # Define tools (functions) for Gemini
            # Note: Vertex AI doesn't support 'default' in parameters, so we clean them
            function_declarations = []
            for func_def in self._get_function_definitions():
                # Remove 'default' from parameters as Vertex AI doesn't support it
                clean_params = self._clean_params_for_vertex(func_def['parameters'])
                function_declarations.append(FunctionDeclaration(
                    name=func_def['name'],
                    description=func_def['description'],
                    parameters=clean_params
                ))
            
            tools = [Tool(function_declarations=function_declarations)]
            
            # Build conversation history for Gemini using Content objects
            history_parts = []
            
            # Trim conversation history to last 6 messages (3 exchanges) to avoid "Multiple content parts" error
            # Gemini has limitations on conversation history length
            max_history_messages = 6
            recent_history = self.conversation_history[-max_history_messages:] if len(self.conversation_history) > max_history_messages else self.conversation_history
            
            # Add system prompt as first exchange if conversation is empty
            if not recent_history:
                history_parts.append(Content(role='user', parts=[Part.from_text(self.system_prompt)]))
                history_parts.append(Content(role='model', parts=[Part.from_text('Understood. I am Columbus AI, ready to help you identify and analyze potential partners and prospects. I will use the available functions to search companies, analyze prospects, and provide actionable insights based on job posting data.')]))
            
            # Add recent conversation history (only last few exchanges)
            for msg in recent_history:
                role = 'user' if msg['role'] == 'user' else 'model'
                # Ensure content is a simple string, not a complex object
                content_text = str(msg['content']) if not isinstance(msg['content'], str) else msg['content']
                history_parts.append(Content(role=role, parts=[Part.from_text(content_text)]))
            
            # Start chat with history (disable response validation to prevent false errors)
            chat = self.model.start_chat(history=history_parts, response_validation=False)
            
            # Send message with tools
            response = chat.send_message(
                user_message,
                tools=tools,
                generation_config=GenerationConfig(
                    temperature=0.1, 
                    max_output_tokens=2000
                )
            )
            
            function_calls_made = []
            function_results = {}
            response_text = ""
            
            # Handle function calls - collect ALL function calls first
            function_response_parts = []
            if response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        function_call = part.function_call
                        function_name = function_call.name
                        function_args = dict(function_call.args)
                        
                        logger.info(f"Gemini calling function: {function_name} with args: {function_args}")
                        
                        # Execute function with context
                        if context:
                            function_args['context'] = context
                        
                        function_result = self.available_functions[function_name](**function_args)
                        function_calls_made.append(function_name)
                        function_results[function_name] = function_result
                        
                        # Create function response part
                        from vertexai.generative_models import Part
                        function_response_parts.append(Part.from_function_response(
                            name=function_name,
                            response={'result': function_result}
                        ))
            
            # Send all function responses back at once if any functions were called
            if function_response_parts:
                # Check if any function result has a 'message' field - prioritize contact details
                function_message = None
                
                # Priority 1: get_company_contacts (contact details are most specific to user request)
                if 'get_company_contacts' in function_results:
                    func_result = function_results['get_company_contacts']
                    if isinstance(func_result, dict) and 'message' in func_result and func_result['message']:
                        function_message = func_result['message']
                        logger.info(f"Using message field from get_company_contacts: {len(function_message)} characters")
                
                # Priority 2: Other functions with messages (like get_company_details strategy analysis)
                if not function_message:
                    for func_name, func_result in function_results.items():
                        if isinstance(func_result, dict) and 'message' in func_result and func_result['message']:
                            function_message = func_result['message']
                            logger.info(f"Using message field from {func_name}: {len(function_message)} characters")
                            break
                
                # If we have a pre-built message from function, use it directly
                if function_message:
                    response_text = function_message
                else:
                    # Otherwise, let Gemini generate a response based on function results
                    final_response = chat.send_message(function_response_parts)
                    
                    # Check if response has text
                    try:
                        response_text = final_response.text
                        if not response_text or not response_text.strip():
                            logger.warning("Final response text is empty")
                            response_text = "I've processed your request. Please see the results above."
                    except (ValueError, AttributeError) as e:
                        logger.warning(f"Final response has no text: {str(e)}")
                        logger.warning(f"Response object: {final_response}")
                        logger.warning(f"Candidates: {final_response.candidates if hasattr(final_response, 'candidates') else 'N/A'}")
                        # Generate a summary from function results
                        if function_calls_made:
                            response_text = "I've gathered the information you requested. Please see the results above."
                        else:
                            response_text = "I apologize, but I couldn't generate a response. Please try rephrasing your question."
            else:
                # No function calls, just use the direct response
                try:
                    response_text = response.text
                    if not response_text or not response_text.strip():
                        logger.warning("Response text is empty")
                        response_text = "I apologize, but I couldn't generate a response. Please try rephrasing your question."
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Response has no text: {str(e)}")
                    logger.warning(f"Response object: {response}")
                    response_text = "I apologize, but I couldn't generate a response. Please try rephrasing your question."
            
            # Add to conversation history (only the final text exchange, not function calls)
            # This prevents Vertex AI errors about function response parts mismatch
            # Store only simple text exchanges - no function call details
            self.conversation_history.append({'role': 'user', 'content': user_message})
            self.conversation_history.append({'role': 'assistant', 'content': response_text})
            
            # Auto-trim conversation history to keep it manageable
            # Prevents "Multiple content parts are not supported" errors
            max_total_messages = 20  # Keep last 10 exchanges
            if len(self.conversation_history) > max_total_messages:
                self.conversation_history = self.conversation_history[-max_total_messages:]
            
            # Extract companies array from function results for UI display
            # Aggregate companies from ALL function calls (in case multiple functions returned companies)
            companies_data = []
            if function_results:
                logger.info(f"Vertex AI function results keys: {function_results.keys()}")
                for func_name, result in function_results.items():
                    logger.info(f"Checking result from {func_name}: type={type(result)}, has 'companies'={isinstance(result, dict) and 'companies' in result}")
                    if isinstance(result, dict) and 'companies' in result and result['companies']:
                        companies_data.extend(result['companies'])
                        logger.info(f"[OK] Added {len(result['companies'])} companies from {func_name}")
                
                if companies_data:
                    # Remove duplicates based on company_id
                    seen_ids = set()
                    unique_companies = []
                    for company in companies_data:
                        company_id = company.get('company_id')
                        if company_id and company_id not in seen_ids:
                            seen_ids.add(company_id)
                            unique_companies.append(company)
                    companies_data = unique_companies
                    self.last_company_results = companies_data  # Cache for follow-up questions
                    logger.info(f"[OK] Total unique companies: {len(companies_data)}")
                else:
                    companies_data = None
            else:
                logger.info("No function results to extract companies from")
            
            # If no new companies but we have cached results, return those for follow-up questions
            # Check if companies_data is None or empty list
            if (not companies_data or len(companies_data) == 0) and self.last_company_results and not function_calls_made:
                logger.info(f"Using {len(self.last_company_results)} cached companies for follow-up question (no functions called)")
                companies_data = self.last_company_results
            
            # Convert empty list to None for consistency
            if companies_data and len(companies_data) == 0:
                companies_data = None
            
            return {
                'response': response_text,
                'function_calls': function_calls_made,
                'data': companies_data  # UI expects array of companies
            }
            
        except Exception as e:
            logger.error(f"Vertex AI Chat error: {str(e)}", exc_info=True)
            return {
                'response': f"I apologize, but I encountered an error: {str(e)}. Please try rephrasing your question.",
                'function_calls': [],
                'data': None
            }
    
    def _clean_params_for_vertex(self, params: Dict) -> Dict:
        """Remove 'default' fields from parameters for Vertex AI compatibility"""
        cleaned = params.copy()
        if 'properties' in cleaned:
            cleaned['properties'] = {}
            for prop_name, prop_def in params['properties'].items():
                cleaned_prop = {k: v for k, v in prop_def.items() if k != 'default'}
                cleaned['properties'][prop_name] = cleaned_prop
        return cleaned
    
    def _get_function_definitions(self) -> List[Dict]:
        """Define functions available to the AI"""
        return [
            {
                'name': 'search_companies_by_tech',
                'description': 'Search for companies using specific technology. Can optionally filter by industry at the same time for multi-criteria searches like "healthcare companies using Vertex AI".',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'technology': {
                            'type': 'string',
                            'description': 'Technology to search for (e.g., "BigQuery", "Looker", "Vertex AI")'
                        },
                        'industry_filter': {
                            'type': 'string',
                            'description': 'Optional industry keyword to filter results (e.g., "healthcare", "financial", "retail"). Matches against company_type field (e.g., "Healthcare", "Finance") and company_industry field (e.g., "Hospitals and Health Care").'
                        },
                        'limit': {
                            'type': 'integer',
                            'description': 'Maximum number of results to return',
                            'default': 5
                        }
                    },
                    'required': ['technology']
                }
            },
            {
                'name': 'get_top_prospects',
                'description': 'Get companies ranked by prospect score and hiring activity. Use this to find companies most active in hiring, top prospects, or companies with most open positions. Can exclude industries like consulting. Results are sorted by prospect score which factors in job count, tech stack alignment, company type, and activity level.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'limit': {
                            'type': 'integer',
                            'description': 'Number of top prospects to return',
                            'default': 10
                        },
                        'min_score': {
                            'type': 'integer',
                            'description': 'Minimum prospect score (0-100). Use 0 to see all companies sorted by activity.',
                            'default': 0
                        },
                        'exclude_industry': {
                            'type': 'string',
                            'description': 'Industry keyword to exclude (e.g., "consulting", "recruitment"). Filters out companies whose industry contains this keyword.'
                        }
                    }
                }
            },
            {
                'name': 'get_new_companies',
                'description': 'Get recently discovered companies from latest scraping runs',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'days': {
                            'type': 'integer',
                            'description': 'Number of days to look back',
                            'default': 7
                        },
                        'limit': {
                            'type': 'integer',
                            'description': 'Maximum number of results',
                            'default': 5
                        }
                    }
                }
            },
            {
                'name': 'filter_by_industry',
                'description': 'Filter companies by industry sector',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'industry': {
                            'type': 'string',
                            'description': 'Industry name or keyword (e.g., "Financial Services", "Healthcare", "Technology")'
                        },
                        'limit': {
                            'type': 'integer',
                            'description': 'Maximum number of results',
                            'default': 5
                        }
                    },
                    'required': ['industry']
                }
            },
            {
                'name': 'get_company_details',
                'description': 'Get detailed information about ONE specific company by name. Do NOT use this for follow-up questions like "give me overview of these companies" - those companies are already in the context and will be shown automatically.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'company_name': {
                            'type': 'string',
                            'description': 'Exact name of the specific company to look up'
                        }
                    },
                    'required': ['company_name']
                }
            },
            {
                'name': 'get_company_contacts',
                'description': 'Find contact information (emails, names, roles) for a company using AI-powered analysis of job postings and web browsing',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'company_name': {
                            'type': 'string',
                            'description': 'Name of the company to find contacts for'
                        },
                        'use_web_browser': {
                            'type': 'boolean',
                            'description': 'Whether to browse company website for additional contact info',
                            'default': True
                        }
                    },
                    'required': ['company_name']
                }
            },
            {
                'name': 'analyze_company_strategy',
                'description': 'Analyze a company\'s data challenges and provide strategic recommendations for Agiliz (consulting/staffing opportunities). Use this when asked about data challenges, next steps, or whether we should contact/staff a company.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'company_name': {
                            'type': 'string',
                            'description': 'Name of the company to analyze'
                        }
                    },
                    'required': ['company_name']
                }
            },
            {
                'name': 'filter_by_job_count',
                'description': 'Filter companies by number of open job positions. Use this to find companies with specific hiring activity levels (e.g., "max 4 jobs", "between 5-10 jobs", "at least 8 jobs").',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'min_jobs': {
                            'type': 'integer',
                            'description': 'Minimum number of jobs (inclusive). Use 0 or 1 for companies with any jobs.',
                            'default': 0
                        },
                        'max_jobs': {
                            'type': 'integer',
                            'description': 'Maximum number of jobs (inclusive). Use a specific number to cap results.',
                            'default': 999
                        },
                        'min_score': {
                            'type': 'integer',
                            'description': 'Minimum prospect score filter (0-100). Use to filter by warmth: 70+ for hot, 50+ for warm, 30+ for cold.',
                            'default': 0
                        },
                        'limit': {
                            'type': 'integer',
                            'description': 'Maximum number of results to return',
                            'default': 10
                        }
                    }
                }
            }
        ]
    
    # Function implementations (these will be called by the AI)
    
    def _search_by_tech(self, technology: str, limit: int = 5, industry_filter: str = None, context: Dict = None) -> Dict:
        """Search companies by technology stack, optionally filtered by industry"""
        # Validate technology parameter
        if not technology or not isinstance(technology, str):
            return {
                'companies': [],
                'count': 0,
                'technology': technology,
                'message': 'Please specify a technology to search for (e.g., "Vertex AI", "BigQuery", "Looker")'
            }
        
        tech_lower = technology.lower()
        
        # More flexible tech matching - handle variations
        # For "Vertex AI", also try: "vertexai", "vertex", "google ai", "gemini"
        tech_variations = [tech_lower]
        if 'vertex' in tech_lower:
            tech_variations.extend(['vertexai', 'vertex_ai', 'google ai platform', 'gemini', 'palm', 'gcp', 'google cloud'])
        elif 'bigquery' in tech_lower:
            tech_variations.extend(['big query', 'bq', 'google bigquery', 'gcp', 'google cloud'])
        elif 'looker' in tech_lower:
            tech_variations.extend(['looker studio', 'data studio', 'google looker', 'gcp'])
        elif tech_lower in ['gcp', 'google cloud', 'google cloud platform']:
            tech_variations.extend(['gcp', 'google cloud', 'google cloud platform', 'bigquery', 'vertex', 'vertexai', 'looker'])
        
        # Query BigQuery directly for companies with these technologies
        # This ensures we search the entire database, not just the limited context
        from apps.dashboard.services.bigquery_service import get_bigquery_service
        from apps.dashboard.services.prospect_scoring_service import get_prospect_scoring_service
        
        bq_service = get_bigquery_service()
        scoring_service = get_prospect_scoring_service()
        
        # Build tech_stack filter string for BigQuery (comma-separated variations)
        tech_stack_filter = ','.join(tech_variations)
        
        # Query BigQuery with tech_stack filter
        # Use 'relevant=all' to search ALL companies regardless of status
        all_companies = bq_service.get_companies_with_filters(
            filters={
                'tech_stack': tech_stack_filter,
                'relevant': 'all',  # Search all companies, not just prospects
                'min_jobs': '1'     # At least 1 job posting
            },
            limit=500
        )
        
        # Score the companies for better ranking
        matching = scoring_service.score_companies_batch(all_companies)
        
        logger.info(f"Tech search for '{technology}' (variations: {tech_variations}) found {len(matching)} companies in BigQuery")
        
        # Apply industry filter if specified
        if industry_filter and isinstance(industry_filter, str):
            industry_lower = industry_filter.lower()
            original_count = len(matching)
            
            # Filter by company_type first (cleaner filter), then by company_industry
            # This ensures "healthcare" matches company_type='Healthcare' primarily
            matching_with_filter = [
                c for c in matching 
                if industry_lower in c.get('company_type', '').lower() 
                or industry_lower in c.get('company_industry', '').lower()
            ]
            
            logger.info(f"Industry filter '{industry_filter}': {original_count} -> {len(matching_with_filter)} companies")
            logger.info(f"  - By company_type: {len([c for c in matching if industry_lower in c.get('company_type', '').lower()])} companies")
            logger.info(f"  - By company_industry: {len([c for c in matching if industry_lower in c.get('company_industry', '').lower()])} companies")
            
            # If no results with industry filter, automatically broaden search
            if len(matching_with_filter) == 0 and original_count > 0:
                logger.info(f"No results with industry filter '{industry_filter}'. Returning all {original_count} companies using {technology}")
                matching = sorted(matching, key=lambda x: x.get('prospect_score', 0), reverse=True)[:int(limit)]
                return {
                    'companies': matching,
                    'count': len(matching),
                    'technology': technology,
                    'industry_filter': None,
                    'broadened_search': True,
                    'message': f'No companies found using {technology} in {industry_filter}. Showing {len(matching)} companies using {technology} across all industries instead.'
                }
            else:
                matching = matching_with_filter
        
        # Sort by prospect score
        matching = sorted(matching, key=lambda x: x.get('prospect_score', 0), reverse=True)[:int(limit)]
        
        # Build appropriate message based on results
        if len(matching) == 0:
            if industry_filter:
                message = f'No companies found using {technology} in {industry_filter} or across all industries. This technology may not be commonly listed in job postings in the Benelux market, or it may be listed under a different name (e.g., as part of "GCP" or "Google Cloud Platform").'
            else:
                message = f'No companies found using {technology}. This technology may not be commonly listed in job postings in the Benelux market, or it may be listed under a different name (e.g., as part of "GCP" or "Google Cloud Platform"). Try searching for related technologies like "GCP", "Google Cloud", or "BigQuery".'
        else:
            message = f'Found {len(matching)} companies using {technology}'
            if industry_filter:
                message += f' in {industry_filter}'
        
        return {
            'companies': matching,
            'count': len(matching),
            'technology': technology,
            'industry_filter': industry_filter,
            'broadened_search': False,
            'message': message
        }
    
    def _get_top_prospects(self, limit: int = 5, min_score: int = 50, exclude_industry: str = None, context: Dict = None) -> Dict:
        """Get top-scored prospects or most active companies"""
        if not context or 'companies' not in context:
            return {'companies': [], 'count': 0, 'message': 'No company data available'}
        
        companies = context['companies']
        
        # Convert parameters to proper types
        limit = int(limit)
        min_score = float(min_score)
        
        # Filter by minimum score
        top = [c for c in companies if c.get('prospect_score', 0) >= min_score]
        
        # Exclude specific industry if requested
        if exclude_industry:
            exclude_keyword = exclude_industry.lower()
            original_count = len(top)
            top = [c for c in top if exclude_keyword not in c.get('company_industry', '').lower()]
            excluded_count = original_count - len(top)
            logger.info(f"Excluded {excluded_count} companies containing '{exclude_industry}' in industry")
        
        # Sort by job count (hiring activity) first, then by prospect score
        # This prioritizes companies with most open positions
        top = sorted(top, key=lambda x: (x.get('job_count', 0), x.get('prospect_score', 0)), reverse=True)[:limit]
        
        message = f'Found {len(top)} companies sorted by hiring activity (job count) and prospect score'
        if exclude_industry:
            message += f'. Excluded companies with "{exclude_industry}" in their industry.'
        
        return {
            'companies': top,
            'count': len(top),
            'min_score': min_score,
            'message': message
        }
    
    def _get_new_companies(self, days: int = 7, limit: int = 5, context: Dict = None) -> Dict:
        """Get recently discovered companies"""
        # Convert parameters to proper types
        days = int(days)
        limit = int(limit)
        
        if not context or 'companies' not in context:
            return {'companies': [], 'count': 0, 'message': 'No company data available'}
        
        from datetime import datetime, timedelta
        
        companies = context['companies']
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Filter by creation date
        new_companies = []
        for c in companies:
            if c.get('created_at'):
                try:
                    # Handle different date formats
                    created_str = str(c['created_at']).replace(' UTC', '').replace('+00:00', '')
                    created_date = datetime.fromisoformat(created_str)
                    if created_date >= cutoff_date:
                        new_companies.append(c)
                except (ValueError, AttributeError):
                    continue
        
        # Sort by prospect score
        new_companies = sorted(new_companies, key=lambda x: x.get('prospect_score', 0), reverse=True)[:limit]
        
        return {
            'companies': new_companies,
            'count': len(new_companies),
            'days': days,
            'message': f'Found {len(new_companies)} companies added in last {days} days'
        }
    
    def _filter_by_industry(self, industry: str, limit: int = 5, context: Dict = None) -> Dict:
        """Filter companies by industry"""
        # Convert parameters to proper types
        limit = int(limit)
        
        if not context or 'companies' not in context:
            return {'companies': [], 'count': 0, 'message': 'No company data available'}
        
        industry_lower = industry.lower()
        companies = context['companies']
        
        # Filter by industry (check both company_type and company_industry)
        matching = [
            c for c in companies 
            if (industry_lower in str(c.get('company_industry', '')).lower() or 
                industry_lower in str(c.get('company_type', '')).lower())
        ]
        
        # Sort by prospect score
        matching = sorted(matching, key=lambda x: x.get('prospect_score', 0), reverse=True)[:limit]
        
        return {
            'companies': matching,
            'count': len(matching),
            'industry': industry,
            'message': f'Found {len(matching)} companies in {industry}'
        }
    
    def _filter_by_job_count(self, min_jobs: int = 0, max_jobs: int = 999, min_score: int = 0, limit: int = 10, context: Dict = None) -> Dict:
        """Filter companies by number of open job positions"""
        # Convert parameters to proper types
        min_jobs = int(min_jobs)
        max_jobs = int(max_jobs)
        min_score = int(min_score)
        limit = int(limit)
        
        if not context or 'companies' not in context:
            return {'companies': [], 'count': 0, 'message': 'No company data available'}
        
        companies = context['companies']
        
        # Filter by job count range and minimum score
        matching = [
            c for c in companies
            if (min_jobs <= c.get('job_count', 0) <= max_jobs and 
                c.get('prospect_score', 0) >= min_score)
        ]
        
        # Sort by prospect score (warmth) first, then by job count
        matching = sorted(matching, key=lambda x: (x.get('prospect_score', 0), x.get('job_count', 0)), reverse=True)[:limit]
        
        # Build descriptive message
        job_range_desc = f"{min_jobs}-{max_jobs}" if max_jobs < 999 else f"{min_jobs}+"
        warmth_desc = ""
        if min_score >= 70:
            warmth_desc = " warm/hot"
        elif min_score >= 50:
            warmth_desc = " warm+"
        elif min_score >= 30:
            warmth_desc = " (all warmth levels)"
        
        return {
            'companies': matching,
            'count': len(matching),
            'min_jobs': min_jobs,
            'max_jobs': max_jobs,
            'min_score': min_score,
            'message': f'Found {len(matching)}{warmth_desc} companies with {job_range_desc} jobs'
        }
    
    def _get_company_details(self, company_name: str, context: Dict = None) -> Dict:
        """Get detailed information about a specific company - searches full database"""
        logger.info(f"Searching database for company: {company_name}")
        
        try:
            # First try searching in context (already loaded companies)
            if context and 'companies' in context:
                companies = context['companies']
                company_lower = company_name.lower()
                
                matching_in_context = []
                for c in companies:
                    company_name_in_data = str(c.get('company', c.get('company_name', '')))
                    if company_lower in company_name_in_data.lower():
                        matching_in_context.append(c)
                
                if matching_in_context:
                    logger.info(f"Found {len(matching_in_context)} matches in context")
                    
                    # If exactly one company, run strategy analysis
                    strategy_analysis = None
                    if len(matching_in_context) == 1:
                        logger.info(f"Single company in context, running strategy analysis")
                        strategy_result = self._analyze_company_strategy(company_name, {'companies': matching_in_context})
                        if strategy_result and 'analysis' in strategy_result:
                            strategy_analysis = strategy_result['analysis']
                            logger.info(f"Strategy analysis completed: {len(strategy_analysis)} characters")
                    
                    # Build message with strategy analysis if available
                    if strategy_analysis:
                        message = f'{strategy_analysis}\n\n💡 **Suggested Next Step:** Use `get_company_contacts` to fetch contact details for outreach.'
                    else:
                        message = f'Found 1 match for "{company_name}"'
                    
                    return {
                        'companies': matching_in_context,
                        'count': len(matching_in_context),
                        'strategy_analysis': strategy_analysis,
                        'message': message
                    }
            
            # If not found in context, search the full database
            logger.info(f"Company not in context, searching full database for: {company_name}")
            
            # Search using keyword filter (partial match)
            filters = {'keyword': company_name, 'min_jobs': 1}
            all_companies = self.bq_service.get_companies_with_filters(filters, limit=50)
            
            if all_companies:
                # Score the companies
                from apps.dashboard.services.prospect_scoring_service import get_prospect_scoring_service
                scoring_service = get_prospect_scoring_service()
                scored_companies = scoring_service.score_companies_batch(all_companies)
                
                logger.info(f"Found {len(scored_companies)} companies matching '{company_name}' in database")
                
                # If we found exactly one company, automatically analyze strategy
                strategy_analysis = None
                if len(scored_companies) == 1:
                    logger.info(f"Single company found, running strategy analysis")
                    strategy_result = self._analyze_company_strategy(company_name, {'companies': scored_companies})
                    if strategy_result and 'analysis' in strategy_result:
                        strategy_analysis = strategy_result['analysis']
                        logger.info(f"Strategy analysis completed: {len(strategy_analysis)} characters")
                
                # Build message with strategy analysis if available
                if strategy_analysis:
                    message = f'{strategy_analysis}\n\n💡 **Suggested Next Step:** Use `get_company_contacts` to fetch contact details for outreach.'
                else:
                    message = f'Found {len(scored_companies)} companies matching "{company_name}"'
                
                return {
                    'companies': scored_companies,
                    'count': len(scored_companies),
                    'strategy_analysis': strategy_analysis,
                    'message': message
                }
            
            # Still not found
            logger.warning(f"No matches found for '{company_name}' in database")
            return {
                'companies': [],
                'count': 0,
                'message': f'Company "{company_name}" not found. Try checking the spelling or use a different company name.'
            }
            
        except Exception as e:
            logger.error(f"Error searching for company {company_name}: {str(e)}")
            return {
                'companies': [],
                'count': 0,
                'error': str(e),
                'message': f'Error searching for "{company_name}": {str(e)}'
            }
    
    def _get_company_contacts(self, company_name: str, use_web_browser: bool = True, context: Dict = None) -> Dict:
        """Find contact information for a company using enhanced contact service"""
        logger.info(f"Getting contacts for: {company_name}")
        
        try:
            # Import the enhanced contact service
            from apps.dashboard.services.enhanced_contact_service import EnhancedContactService
            
            # Get company data from context if available
            company_data = {'company_name': company_name}
            if context and 'companies' in context:
                companies = context['companies']
                for c in companies:
                    if company_name.lower() in str(c.get('company_name', '')).lower():
                        company_data = c
                        break
            
            # Initialize contact service (use same AI provider as chat)
            contact_service = EnhancedContactService(ai_provider=self.provider)
            
            # Find contacts
            result = contact_service.find_contacts(
                company_data=company_data,
                use_web_browser=use_web_browser
            )
            
            # Parse AI response if it's JSON
            contacts_info = result.get('ai_response', 'No contact information found')
            logger.info(f"[DEBUG] contacts_info type: {type(contacts_info)}")
            
            try:
                import json
                if isinstance(contacts_info, str):
                    contacts_data = json.loads(contacts_info)
                    logger.info(f"[DEBUG] Parsed JSON from string")
                elif isinstance(contacts_info, dict):
                    contacts_data = contacts_info
                    logger.info(f"[DEBUG] Already a dict, using directly")
                else:
                    logger.error(f"[DEBUG] Unexpected type: {type(contacts_info)}")
                    contacts_data = {'raw_response': str(contacts_info)}
            except Exception as e:
                logger.error(f"[DEBUG] Parse error: {str(e)}")
                contacts_data = {'raw_response': str(contacts_info)}
            
            logger.info(f"[DEBUG] contacts_data keys: {contacts_data.keys()}")
            logger.info(f"[DEBUG] decision_makers count: {len(contacts_data.get('decision_makers', []))}")
            
            # Format contacts into a readable message
            message_parts = [f"**Contact Information for {company_name}**\n"]
            
            # Add general contact info
            if 'company' in contacts_data and contacts_data['company']:
                company_info = contacts_data['company']
                if company_info.get('website'):
                    message_parts.append(f"🌐 **Website:** {company_info['website']}")
                if company_info.get('address'):
                    message_parts.append(f"📍 **Address:** {company_info['address']}")
            
            if 'general_contact' in contacts_data and contacts_data['general_contact']:
                general = contacts_data['general_contact']
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
            elif 'suggested_contact_pages' in contacts_data:
                # No contacts found, show suggested contact pages
                message_parts.append(f"\n⚠️ **No contact details found on website**")
                message_parts.append(f"\nPlease try these contact pages manually:")
                for page in contacts_data['suggested_contact_pages']:
                    message_parts.append(f"• {page}")
            
            # Add notes if available
            if contacts_data.get('notes'):
                message_parts.append(f"\n📝 **Notes:** {contacts_data['notes']}")
            
            # Add data sources
            data_sources = result.get('data_sources', [])
            if data_sources:
                message_parts.append(f"\n📊 **Data Sources:** {', '.join(data_sources)}")
            
            formatted_message = '\n'.join(message_parts)
            
            return {
                'company_name': company_name,
                'contacts': contacts_data,
                'data_sources': data_sources,
                'processing_time': result.get('processing_time', 0),
                'message': formatted_message
            }
            
        except Exception as e:
            logger.error(f"Error getting contacts for {company_name}: {str(e)}", exc_info=True)
            return {
                'company_name': company_name,
                'contacts': None,
                'error': str(e),
                'message': f'Error finding contacts: {str(e)}'
            }
    
    def _analyze_company_strategy(self, company_name: str, context: Dict = None) -> Dict:
        """Analyze company's data challenges and provide Agiliz strategic recommendations"""
        logger.info(f"Analyzing strategy for: {company_name}")
        
        try:
            # Import BigQuery service to get company data
            from apps.dashboard.services.bigquery_service import BigQueryService
            
            bq_service = BigQueryService()
            
            # Get company details
            company_data = None
            if context and 'companies' in context:
                companies = context['companies']
                for c in companies:
                    company_field = str(c.get('company', c.get('company_name', '')))
                    if company_name.lower() in company_field.lower():
                        company_data = c
                        break
            
            # If not in context, search database
            if not company_data:
                filters = {'keyword': company_name, 'min_jobs': 1}
                companies = bq_service.get_companies_with_filters(filters, limit=1)
                if companies:
                    company_data = companies[0]
            
            if not company_data:
                return {
                    'company_name': company_name,
                    'error': 'Company not found',
                    'message': f'Could not find company "{company_name}" in database'
                }
            
            # Get job postings for context - prioritize recent (last 2 weeks)
            from datetime import datetime, timedelta
            two_weeks_ago = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
            
            all_jobs = bq_service.get_jobs_with_filters({'keyword': company_name}, limit=50)
            recent_jobs = [j for j in all_jobs if j.get('posted_date') and j.get('posted_date') >= two_weeks_ago]
            
            # Build analysis prompt with recent job focus
            tech_stack = ', '.join(company_data.get('tech_stacks', [])) or 'Not specified'
            
            total_job_count = company_data.get('job_count', 0)
            recent_job_count = len(recent_jobs)
            
            if recent_jobs:
                job_titles = ', '.join([job.get('job_title', '') for job in recent_jobs[:5]])
                job_context = f"{recent_job_count} recent jobs (last 2 weeks) out of {total_job_count} total"
            else:
                job_titles = ', '.join([job.get('job_title', '') for job in all_jobs[:5]]) if all_jobs else 'No jobs found'
                job_context = f"{total_job_count} total jobs (none in last 2 weeks)"
            
            prompt = f"""Analyze this company and provide strategic recommendations for Agiliz:

**Company:** {company_name}
**Industry:** {company_data.get('company_industry', 'Not specified')}
**Company Type:** {company_data.get('company_type', 'Not specified')}
**Size:** {company_data.get('company_size', 'Not specified')}
**Technology Stack:** {tech_stack}
**Job Postings:** {job_context}
**Recent Job Titles:** {job_titles}
**Location:** {company_data.get('location', 'Not specified')}

**IMPORTANT:** Focus your analysis on the **{recent_job_count} recent jobs (last 2 weeks)** as these indicate current hiring priorities and immediate needs. Outdated job postings should be ignored in your strategic assessment.

**About Agiliz:**
- We provide data activation consulting using GCP stack (BigQuery, Looker, Vertex AI) and MicroStrategy
- We offer both consulting services and staffing/talent placement
- We focus on Belgium and Netherlands markets
- We help businesses turn data into actionable insights

**Please provide:**

1. **Data Challenges** (2-3 specific challenges):
   - Based on their industry, size, tech stack, and **RECENT job postings (last 2 weeks)**
   - What are the biggest data infrastructure, analytics, or governance challenges they likely face?
   - Consider data pipelines, reporting, compliance, scalability issues
   - If they have few/no recent jobs, note this as a potential signal of hiring freeze or reduced growth

2. **Agiliz Next Steps** (strategic recommendations):
   - Should we contact them? (Yes/No and why - consider recent hiring activity)
   - Priority level: High/Medium/Low (adjust based on recent job count - active hiring = higher priority)
   - Recommended services: Which GCP/BigQuery/Looker/Vertex AI/MicroStrategy services should we offer?
   - Staffing opportunities: What specific roles from their **recent postings** would be valuable to place?
   - Best approach: How should we reach out? (LinkedIn, email, partner referral, etc.)
   - Reasoning: Why are they a good or bad fit for Agiliz? (Factor in hiring velocity from recent jobs)

Return your analysis in clear sections with bullet points."""

            # Get AI response
            if self.provider == 'vertex':
                response = self.model.generate_content(prompt)
                analysis = response.text
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a strategic business analyst for Agiliz, a data consulting company."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7
                )
                analysis = response.choices[0].message.content
            
            return {
                'company_name': company_name,
                'company_data': company_data,
                'analysis': analysis,
                'message': f'Strategic analysis complete for {company_name}'
            }
            
        except Exception as e:
            logger.error(f"Error analyzing strategy for {company_name}: {str(e)}", exc_info=True)
            return {
                'company_name': company_name,
                'error': str(e),
                'message': f'Error analyzing company: {str(e)}'
            }
    
    def reset_conversation(self):
        """Clear conversation history"""
        self.conversation_history = []
        logger.info("Conversation history reset")
    
    def get_suggestions(self) -> List[str]:
        """Get suggested queries for the user"""
        return [
            "Give me top 5 strong fits for prospects from today's pull",
            "I have a person who can do good Looker. Find me jobs where Looker will be a strong fit",
            "We are planning to create a tool for BigQuery. What are the best partners or prospects to reach out to?",
            "Show me new companies discovered this week with GCP stack",
            "Find technology companies in healthcare using Vertex AI",
            "Company details of Xccelerated"
        ]


# Singleton instance
_columbus_chat = None

def get_columbus_chat() -> ColumbusChatAI:
    """Get or create Columbus Chat singleton"""
    global _columbus_chat
    if _columbus_chat is None:
        _columbus_chat = ColumbusChatAI()
        logger.info("Columbus Chat AI service initialized")
    return _columbus_chat
