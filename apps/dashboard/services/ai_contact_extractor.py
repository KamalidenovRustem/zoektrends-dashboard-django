"""
AI-Powered Contact Extractor
Uses AI to intelligently extract contact information from any webpage
No hardcoded patterns - AI figures it out!
"""
import logging
from typing import Dict, Any, List, Optional
from django.conf import settings
import json

logger = logging.getLogger(__name__)


class AIContactExtractor:
    """
    Uses AI to extract contact information from webpage text
    Much smarter than regex - works on any website structure
    Uses Gemini 2.5 Pro for intelligent extraction
    """
    
    def __init__(self):
        # Use Gemini instead of OpenAI
        from apps.dashboard.services.gemini_service import GeminiService
        self.gemini = GeminiService()
        logger.info("AI Contact Extractor initialized (using Gemini 2.5 Pro)")
    
    def extract_contacts_from_text(self, webpage_text: str, url: str, soup=None) -> Dict[str, Any]:
        """
        Use AI to intelligently extract contacts from webpage text
        
        Args:
            webpage_text: Raw text from webpage
            url: URL of the page (for context)
            soup: BeautifulSoup object (optional, for extracting links)
        
        Returns:
            Dict with names, titles, emails, phones, linkedin_urls
        """
        
        # If soup provided, extract LinkedIn links and append to text
        if soup:
            try:
                linkedin_links = soup.find_all('a', href=lambda href: href and 'linkedin.com/in/' in href.lower())
                if linkedin_links:
                    # Append LinkedIn URLs to text so AI can see them
                    webpage_text += "\n\n=== LINKEDIN PROFILE LINKS FOUND IN HTML ===\n"
                    for link in linkedin_links:
                        href = link.get('href')
                        # Get surrounding context (nearby text for matching name)
                        parent = link.parent
                        context = ""
                        if parent:
                            context = parent.get_text(strip=True)[:100]
                        webpage_text += f"\n{href}"
                        if context:
                            webpage_text += f" [Context: {context}]"
            except Exception as e:
                logger.warning(f"Failed to extract LinkedIn links from soup: {e}")
        
        # Limit text to avoid token overflow (first 12000 chars to include LinkedIn section)
        text_sample = webpage_text[:12000]
        
        prompt = f"""You are an expert at extracting contact information from website text.

WEBPAGE URL: {url}

WEBPAGE TEXT:
{text_sample}

TASK: Extract ALL contact information you can find. Look for:
1. **People's names** with their titles/roles
2. **Email addresses**
3. **Phone numbers**
4. **LinkedIn profile URLs** (format: linkedin.com/in/username)
5. **Job titles** associated with names

RULES:
- Extract ONLY what you actually see in the text
- Don't make up or guess information
- Include LinkedIn URLs if they appear anywhere in the text
- If you see "Name + Title" patterns, extract both
- Look for leadership/team sections

Return ONLY valid JSON in this format:
{{
  "contacts": [
    {{
      "name": "Full Name",
      "title": "Job Title or null",
      "linkedin_url": "https://linkedin.com/in/username or null",
      "email": "email@domain.com or null",
      "confidence": "high/medium/low"
    }}
  ],
  "general_emails": ["info@company.com"],
  "general_phones": ["+1234567890"]
}}

Extract everything you can find. Return empty arrays if nothing found."""

        try:
            # Use Gemini 2.5 Pro for contact extraction
            response = self.gemini.generate_content(
                prompt=prompt,
                model_name="gemini-2.5-pro",
                temperature=0.0,  # Deterministic for consistency
                max_tokens=2000
            )
            
            result_text = response
            
            # Log what we got
            if not result_text or result_text.strip() == "":
                logger.error(f"AI returned empty response for {url}")
                return {"contacts": [], "general_emails": [], "general_phones": []}
            
            logger.debug(f"AI response (first 200 chars): {result_text[:200]}")
            
            # Strip markdown code blocks if present
            import re
            cleaned_text = result_text.strip()
            
            # Remove ```json ... ``` wrapper
            json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', cleaned_text, re.DOTALL)
            if json_match:
                cleaned_text = json_match.group(1).strip()
            
            # Parse JSON
            result = json.loads(cleaned_text)
            
            logger.info(f"AI extracted {len(result.get('contacts', []))} contacts from {url}")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"AI returned invalid JSON: {e}")
            logger.error(f"Response was: {result_text[:500] if 'result_text' in locals() else 'No response'}")
            return {"contacts": [], "general_emails": [], "general_phones": []}
        except Exception as e:
            logger.error(f"AI extraction failed: {str(e)}")
            return {"contacts": [], "general_emails": [], "general_phones": []}


# Singleton
_ai_contact_extractor = None


def get_ai_contact_extractor() -> AIContactExtractor:
    """Get or create AI contact extractor singleton"""
    global _ai_contact_extractor
    if _ai_contact_extractor is None:
        _ai_contact_extractor = AIContactExtractor()
    return _ai_contact_extractor
