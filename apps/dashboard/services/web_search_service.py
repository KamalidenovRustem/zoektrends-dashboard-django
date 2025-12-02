"""
Web Search Service
Uses SerpAPI (Google Search) for reliable, accurate results
Fallback to domain guessing if needed
"""
import logging
import requests
from typing import Optional, Dict, List
from urllib.parse import urlparse, quote
import re
from django.conf import settings

logger = logging.getLogger(__name__)


class WebSearchService:
    """
    Service to search the web for company information
    Uses SerpAPI for Google Search (most reliable)
    """
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })
        
        # Get SerpAPI key from settings
        self.serpapi_key = getattr(settings, 'SERPAPI_KEY', None)
    
    def search_company_website(self, company_name: str, location: Optional[str] = None) -> Optional[str]:
        """
        Search for a company's official website
        
        Args:
            company_name: Company name to search for
            location: Company location/country to help filter results (e.g., "Belgium", "Netherlands")
        
        Returns:
            Company website URL or None
        """
        logger.info(f"Searching web for: {company_name}" + (f" (location: {location})" if location else ""))
        
        # Method 1: Try SerpAPI (Google Search) - Most reliable
        if self.serpapi_key:
            website = self._serpapi_search(company_name, location)
            if website:
                logger.info(f"Found website via SerpAPI (Google): {website}")
                return website
        else:
            logger.warning("SerpAPI key not configured, skipping Google search")
        
        # Method 2: Fallback to DuckDuckGo HTML
        website = self._duckduckgo_search(company_name, location)
        if website:
            logger.info(f"Found website via DuckDuckGo: {website}")
            return website
        
        # Method 3: Last resort - domain guessing
        website = self._guess_domain(company_name, location)
        if website:
            logger.info(f"Found website via domain guessing: {website}")
            return website
        
        logger.warning(f"Could not find website for {company_name}")
        return None
    
    def _serpapi_search(self, company_name: str, location: Optional[str] = None) -> Optional[str]:
        """
        Search using SerpAPI (Google Search) - Most reliable method
        
        Args:
            company_name: Company name
            location: Location to include in search (e.g., "Belgium", "Netherlands")
        
        Returns:
            Company website URL or None
        """
        try:
            # Build search query
            if location:
                query = f"{company_name} {location}"
            else:
                query = company_name
            
            logger.info(f"Searching with SerpAPI (Google): {query}")
            
            # Make SerpAPI request
            serpapi_url = "https://serpapi.com/search.json"
            params = {
                'q': query,
                'engine': 'google',
                'api_key': self.serpapi_key,
                'hl': 'en',
                'gl': 'us',
                'google_domain': 'google.com',
                'num': 10  # Get top 10 results
            }
            
            response = requests.get(serpapi_url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract organic results
            organic_results = data.get('organic_results', [])
            
            if not organic_results:
                logger.warning(f"SerpAPI returned no organic results for: {query}")
                return None
            
            logger.info(f"SerpAPI returned {len(organic_results)} results")
            
            # Prioritize first result (usually correct for company searches)
            # But check first 3 results to be sure
            for i, result in enumerate(organic_results[:3], 1):
                url = result.get('link', '')
                title = result.get('title', '')
                snippet = result.get('snippet', '')
                
                logger.info(f"SerpAPI result {i}: {url}")
                logger.debug(f"  Title: {title}")
                logger.debug(f"  Snippet: {snippet[:100]}")
                
                if self._is_likely_company_website(url, company_name, location):
                    logger.info(f"[OK] Found via SerpAPI (Google): {url}")
                    return url
                else:
                    logger.debug(f"[X] Rejected: {url}")
            
            # If first 3 didn't match, check remaining results
            for i, result in enumerate(organic_results[3:], 4):
                url = result.get('link', '')
                if url and self._is_likely_company_website(url, company_name, location):
                    logger.info(f"[OK] Found via SerpAPI (result #{i}): {url}")
                    return url
            
            logger.warning(f"No matching website found in SerpAPI results")
            return None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"SerpAPI request failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"SerpAPI search error: {str(e)}", exc_info=True)
            return None
    
    def _google_search(self, company_name: str, location: Optional[str] = None) -> Optional[str]:
        """
        Search using Google search (scraping results)
        Free, no API key needed
        """
        try:
            # Google search with user agent
            query = f"{company_name}"
            url = f"https://www.google.com/search?q={quote(query)}"
            
            # Use proper headers to avoid being blocked
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Parse HTML
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find search result links
            # Google uses different structures, try multiple selectors
            results = []
            
            # Method 1: Look for <a> tags with specific structure
            for link in soup.find_all('a', href=True):
                href = link['href']
                # Google wraps actual URLs in /url?q= format
                if '/url?q=' in href:
                    # Extract actual URL
                    import urllib.parse
                    try:
                        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
                        if 'q' in parsed:
                            actual_url = parsed['q'][0]
                            if actual_url.startswith('http'):
                                results.append(actual_url)
                    except:
                        continue
            
            # Process results
            for url in results[:10]:  # Check first 10 results
                if self._is_likely_company_website(url, company_name):
                    logger.info(f"Found via Google search: {url}")
                    return url
            
        except Exception as e:
            logger.debug(f"Google search failed (this is normal, Google blocks scrapers): {str(e)}")
        
        return None
    
    def _duckduckgo_search(self, company_name: str, location: Optional[str] = None) -> Optional[str]:
        """
        Search using DuckDuckGo API with multiple methods
        Tries: 1) JSON API, 2) DDGS library, 3) Multiple query variations
        """
        # For short company names, add .com to make search more specific
        search_name = company_name
        if len(company_name.strip()) <= 4 and '.' not in company_name:
            search_name = f"{company_name}.com"
            logger.info(f"Short company name detected, searching for: {search_name}")
        
        # Try multiple search strategies - prioritize company name to avoid location-only results
        search_queries = [
            search_name,  # Try company name first
            f"{company_name} official website",
            f"{search_name} {location}" if location else None
        ]
        
        # Filter out None values
        search_queries = [q for q in search_queries if q]
        
        logger.info(f"Searching for {company_name} (location: {location or 'none'}) - {len(search_queries)} query variations")
        
        for attempt, query in enumerate(search_queries, 1):
            logger.info(f"Search attempt {attempt}/{len(search_queries)}: {query}")
            
            # Method 1: Try DuckDuckGo HTML scraping (most reliable)
            result = self._duckduckgo_html_search(query, company_name, location)
            if result:
                return result
        
        logger.warning(f"No matching website found after {len(search_queries)} search attempts for '{company_name}'")
        return None
    
    def _duckduckgo_html_search(self, query: str, company_name: str, location: Optional[str] = None) -> Optional[str]:
        """
        Search DuckDuckGo by fetching HTML results and parsing links
        This is more reliable than the deprecated duckduckgo-search library
        
        Fetches: https://duckduckgo.com/html/?q=query
        """
        try:
            from bs4 import BeautifulSoup
            import time
            
            # URL encode the query
            encoded_query = quote(query)
            search_url = f"https://duckduckgo.com/html/?q={encoded_query}"
            
            logger.info(f"Fetching DuckDuckGo HTML: {search_url}")
            
            # Make request with proper headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Referer': 'https://duckduckgo.com/',
            }
            
            response = self.session.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find result links - DuckDuckGo wraps URLs in uddg= parameter
            results = []
            
            # Look for all links in results
            import urllib.parse
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                
                # DuckDuckGo wraps actual URLs in uddg= parameter
                if 'uddg=' in href:
                    try:
                        # Extract uddg parameter value
                        uddg_start = href.find('uddg=') + 5
                        uddg_end = href.find('&', uddg_start)
                        if uddg_end == -1:
                            uddg_value = href[uddg_start:]
                        else:
                            uddg_value = href[uddg_start:uddg_end]
                        
                        # URL decode it
                        actual_url = urllib.parse.unquote(uddg_value)
                        if actual_url.startswith('http') and 'duckduckgo.com' not in actual_url:
                            results.append(actual_url)
                            logger.debug(f"Extracted: {actual_url}")
                    except Exception as e:
                        logger.debug(f"Failed to extract URL from uddg: {e}")
                elif href.startswith('http') and 'duckduckgo.com' not in href:
                    # Direct URL (rare but possible)
                    results.append(href)
                    logger.debug(f"Direct URL: {href}")
            
            # Fallback: Look for links with result__snippet class nearby
            if not results:
                for result_div in soup.find_all('div', class_='links_main'):
                    for link in result_div.find_all('a', href=True):
                        href = link['href']
                        if 'uddg=' in href:
                            import urllib.parse
                            try:
                                uddg_start = href.find('uddg=') + 5
                                uddg_end = href.find('&', uddg_start)
                                if uddg_end == -1:
                                    uddg_value = href[uddg_start:]
                                else:
                                    uddg_value = href[uddg_start:uddg_end]
                                actual_url = urllib.parse.unquote(uddg_value)
                                if actual_url.startswith('http'):
                                    results.append(actual_url)
                            except:
                                pass
            
            logger.info(f"DuckDuckGo HTML returned {len(results)} results")
            
            # Process results
            for i, url in enumerate(results[:10], 1):  # Check first 10 results
                logger.info(f"DuckDuckGo result {i}: {url}")
                
                if self._is_likely_company_website(url, company_name, location):
                    logger.info(f"[OK] Found via DuckDuckGo HTML: {url}")
                    return url
                else:
                    logger.debug(f"[X] Rejected: {url}")
            
            # Small delay to be respectful
            time.sleep(0.5)
            
        except Exception as e:
            logger.warning(f"DuckDuckGo HTML search failed: {str(e)}")
        
        return None
    
    def _duckduckgo_json_api(self, query: str, company_name: str, location: Optional[str] = None) -> Optional[str]:
        """
        Try DuckDuckGo JSON API: https://api.duckduckgo.com/?q=query&format=json
        This returns instant answers but not full search results
        """
        try:
            import json
            
            # Encode query for URL
            encoded_query = quote(query)
            api_url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1&skip_disambig=1"
            
            logger.info(f"Trying DuckDuckGo JSON API: {api_url}")
            
            response = self.session.get(api_url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Check AbstractURL (primary result)
            if data.get('AbstractURL'):
                url = data['AbstractURL']
                logger.info(f"JSON API AbstractURL: {url}")
                if self._is_likely_company_website(url, company_name, location):
                    logger.info(f"[OK] Found via JSON API (AbstractURL): {url}")
                    return url
            
            # Check related topics
            for topic in data.get('RelatedTopics', []):
                if isinstance(topic, dict) and topic.get('FirstURL'):
                    url = topic['FirstURL']
                    logger.info(f"JSON API RelatedTopic: {url}")
                    if self._is_likely_company_website(url, company_name, location):
                        logger.info(f"[OK] Found via JSON API (RelatedTopic): {url}")
                        return url
            
            # Check results array
            for result in data.get('Results', []):
                if result.get('FirstURL'):
                    url = result['FirstURL']
                    logger.info(f"JSON API Result: {url}")
                    if self._is_likely_company_website(url, company_name, location):
                        logger.info(f"[OK] Found via JSON API (Result): {url}")
                        return url
            
            logger.info("JSON API returned no matching company website")
            
        except Exception as e:
            logger.warning(f"DuckDuckGo JSON API error: {str(e)}")
        
        return None
    
    def _is_likely_company_website(self, url: str, company_name: str, location: Optional[str] = None) -> bool:
        """
        Check if URL is likely the company's official website
        Filters out social media, job boards, etc.
        Prioritizes results matching company location
        """
        # Skip these domains
        skip_domains = [
            'linkedin.com',
            'facebook.com', 
            'twitter.com',
            'instagram.com',
            'youtube.com',
            'indeed.com',
            'glassdoor.com',
            'monster.com',
            'ziprecruiter.com',
            'wikipedia.org',
            'crunchbase.com',
            'bloomberg.com',
            'reuters.com',
            'ycombinator.com',
            'reddit.com',
            'duckduckgo.com',  # Skip DDG internal links
            'amazon.com',      # Skip Amazon ads
            'bing.com',        # Skip Bing ads
            'mapcarta.com',    # Skip map sites
            'maps.google.com',
            'openstreetmap.org',
            'archcompetition.net',  # Skip generic location sites
            'wework.com',      # Skip coworking spaces
            'regus.com',
            'spaces.com',
            'hubspot.com',     # Skip generic business tools
            'salesforce.com',
            'wordpress.com',
            'medium.com',
            'blogger.com',
            'atsmodding.com',  # Skip gaming/mod sites
            'modland.net',
            'allmods.net',
            'ets2world.com',
            'truckymods.io',
            'zhihu.com',       # Skip Chinese Q&A site
            'baidu.com',       # Skip Chinese search engine
        ]
        
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Skip if it's a blocked domain
        if any(skip in domain for skip in skip_domains):
            logger.debug(f"[SKIP] Domain {domain} is in skip list")
            return False
        
        # Extract key words from company name (ignore common words)
        ignore_words = ['the', 'inc', 'llc', 'ltd', 'company', 'group', 'international', 'corp', 'corporation', 'biotech', 'medtech', 'hightech', 'talents']
        company_words = company_name.lower().split()
        key_words = [w for w in company_words if w not in ignore_words and len(w) > 2]
        
        # Clean domain for comparison
        domain_clean = domain.replace('www.', '').replace('-', '').replace('_', '')
        
        # For very short company names (<=4 chars), require exact match in domain
        company_name_clean = company_name.lower().strip().replace(' ', '').replace('-', '').replace('_', '')
        if len(company_name_clean) <= 4:
            # Short name: must match exactly at start of domain
            matches_name = domain_clean.startswith(company_name_clean + '.')
            if matches_name:
                logger.debug(f"[OK] Short name '{company_name_clean}' matches domain '{domain_clean}'")
            else:
                logger.debug(f"[SKIP] Short name '{company_name_clean}' does not match domain '{domain_clean}'")
            return matches_name
        
        # Check if any key word appears in domain
        matches_name = False
        matched_word = None
        for word in key_words:
            word_clean = word.replace('-', '').replace('_', '')
            if word_clean in domain_clean:
                matches_name = True
                matched_word = word_clean
                break
        
        # Also check against full company slug
        if not matches_name:
            company_slug = company_name.lower().replace(' ', '').replace('-', '').replace('_', '')
            if len(company_slug) >= 8 and company_slug[:8] in domain_clean:
                matches_name = True
                matched_word = company_slug[:8]
            elif len(company_slug) < 8 and company_slug in domain_clean:
                matches_name = True
                matched_word = company_slug
        
        # CRITICAL: Only accept if company name matches domain
        # No longer accept generic domains just because they have valid TLDs
        if not matches_name:
            logger.debug(f"[SKIP] Domain {domain} does not contain company name '{company_name}'")
            return False
        
        logger.debug(f"[MATCH] Domain {domain} contains '{matched_word}' from company name '{company_name}'")
        
        # If we have location info, prioritize TLDs matching that location
        if location:
            location_lower = location.lower()
            # Map countries to their TLDs
            location_tlds = {
                'belgium': ['.be'],
                'netherlands': ['.nl'],
                'germany': ['.de'],
                'france': ['.fr'],
                'uk': ['.uk', '.co.uk'],
                'united kingdom': ['.uk', '.co.uk'],
                'australia': ['.au', '.com.au'],
                'canada': ['.ca'],
                'ireland': ['.ie'],
                'spain': ['.es'],
                'italy': ['.it'],
                'portugal': ['.pt'],
            }
            
            # Check if domain TLD matches location
            for country, tlds in location_tlds.items():
                if country in location_lower:
                    for tld in tlds:
                        if domain.endswith(tld):
                            logger.info(f"[OK] Domain {domain} matches location {location} (TLD: {tld})")
                            return True
        
        # Name matches - accept it
        return True
    
    def _guess_domain(self, company_name: str, location: Optional[str] = None) -> Optional[str]:
        """
        Fallback: Try common domain patterns
        """
        # Extract first meaningful word from company name (ignore common words)
        ignore_words = ['the', 'inc', 'llc', 'ltd', 'company', 'group', 'international', 'corp', 'corporation', 'biotech', 'medtech', 'hightech', 'talents']
        words = company_name.lower().split()
        key_words = [w for w in words if w not in ignore_words and len(w) > 2]
        
        # Clean company name (full)
        company_slug = company_name.lower()
        company_slug = re.sub(r'[^a-z0-9]', '', company_slug)
        
        # First word only (often the actual company name)
        first_word = key_words[0] if key_words else company_slug
        first_word_clean = re.sub(r'[^a-z0-9]', '', first_word)
        
        # Also try with hyphens
        company_hyphen = company_name.lower().replace(' ', '-')
        company_hyphen = re.sub(r'[^a-z0-9-]', '', company_hyphen)
        
        # IMPORTANT: Try -global variants FIRST (more specific for international companies)
        # Many large companies use company-global.com for their main site
        patterns = [
            f"https://www.{company_slug}-global.com",
            f"https://{company_slug}-global.com",
            f"https://www.{company_hyphen}-global.com",
            f"https://{company_hyphen}-global.com",
        ]
        
        # Then try first word patterns (e.g., "plusone" from "PlusOne - Biotech...")
        # This is often the actual company name
        patterns.extend([
            f"https://www.{first_word_clean}.be",  # Belgium companies
            f"https://{first_word_clean}.be",
            f"https://www.{first_word_clean}.com",
            f"https://{first_word_clean}.com",
            f"https://www.{first_word_clean}.io",
            f"https://{first_word_clean}.io",
        ])
        
        # Then try full name patterns
        patterns.extend([
            f"https://www.{company_slug}.com",
            f"https://{company_slug}.com",
            f"https://www.{company_hyphen}.com",
            f"https://{company_hyphen}.com",
            f"https://{company_slug}.io",
            f"https://www.{company_slug}.io",
            f"https://{company_slug}.co",
            f"https://www.{company_slug}.co",
            f"https://{company_slug}.be",  # Belgium
            f"https://www.{company_slug}.be",
        ])
        
        for url in patterns:
            try:
                response = self.session.head(url, timeout=5, allow_redirects=True)
                if response.status_code == 200:
                    return response.url  # Return final URL after redirects
            except:
                continue
        
        return None
    
    def search_company_info(self, company_name: str) -> Dict:
        """
        Search for comprehensive company information
        
        Returns:
            Dict with website, description, social links
        """
        result = {
            'company_name': company_name,
            'website': None,
            'description': None,
            'found_via': None
        }
        
        # Find website
        website = self.search_company_website(company_name)
        if website:
            result['website'] = website
            result['found_via'] = 'web_search'
        
        return result


# Singleton
_web_search_service = None


def get_web_search_service() -> WebSearchService:
    """Get or create web search service singleton"""
    global _web_search_service
    if _web_search_service is None:
        _web_search_service = WebSearchService()
    return _web_search_service
