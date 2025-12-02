"""
Web Browser Service for Contact Research
Safely browses company websites (NOT LinkedIn) to find contact information
Uses requests + BeautifulSoup - no Selenium needed for most sites
"""
import logging
import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin, urlparse
import re
import time

logger = logging.getLogger(__name__)


class WebBrowserService:
    """
    Service to browse company websites and extract contact information
    
    IMPORTANT: This service DOES NOT access LinkedIn to avoid ToS violations.
    It only browses public company websites, contact pages, and about pages.
    """
    
    def __init__(self):
        self.session = requests.Session()
        # Use a real browser user agent to appear legitimate
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self.timeout = 10  # seconds
        self.max_pages_per_site = 10  # Increased to find more contact info
    
    def search_company_info(self, company_name: str, location: Optional[str] = None) -> Dict[str, Any]:
        """
        Search for company information using multiple strategies
        
        Args:
            company_name: Company name to search for
            location: Optional location/headquarters to help narrow search
        
        Returns:
            Dict with website, contact_page, about_page, team_page, emails, phones, social_links
        """
        logger.info(f"Searching web for: {company_name}" + (f" (location: {location})" if location else ""))
        
        result = {
            'company_name': company_name,
            'website': None,
            'contact_page': None,
            'about_page': None,
            'team_page': None,
            'emails': [],
            'phones': [],
            'addresses': [],
            'contact_names': [],
            'social_links': {},
            'description': None,
            'search_method': 'web_browser'
        }
        
        try:
            # Step 1: Try to find company website
            website = self._find_company_website(company_name, location=location)
            if not website:
                logger.warning(f"Could not find website for {company_name}")
                return result
            
            result['website'] = website
            logger.info(f"Found website: {website}")
            
            # Step 2: Browse the homepage
            homepage_data = self._browse_page(website)
            if homepage_data:
                result['emails'].extend(homepage_data.get('emails', []))
                result['phones'].extend(homepage_data.get('phones', []))
                result['addresses'].extend(homepage_data.get('addresses', []))
                result['description'] = homepage_data.get('description')
            
            # Step 3: Find and browse key pages
            key_pages = self._find_key_pages(website, homepage_data.get('soup'))
            logger.info(f"Found {len(key_pages)} key pages: {list(key_pages.keys())}")
            
            # Browse contact page
            if key_pages.get('contact'):
                logger.info(f"Browsing contact page: {key_pages['contact']}")
                result['contact_page'] = key_pages['contact']
                contact_data = self._browse_page(key_pages['contact'])
                if contact_data:
                    logger.info(f"Contact page data: {len(contact_data.get('emails', []))} emails, {len(contact_data.get('phones', []))} phones, {len(contact_data.get('addresses', []))} addresses")
                    result['emails'].extend(contact_data.get('emails', []))
                    result['phones'].extend(contact_data.get('phones', []))
                    result['addresses'].extend(contact_data.get('addresses', []))
                    result['contact_names'].extend(contact_data.get('names', []))
            else:
                logger.warning("No contact page found - trying common contact URLs")
                # Try common contact page URLs
                common_contact_urls = [
                    f"{website.rstrip('/')}/contact",
                    f"{website.rstrip('/')}/contact-us",
                    f"{website.rstrip('/')}/contactus",
                    f"{website.rstrip('/')}/get-in-touch",
                    f"{website.rstrip('/')}/about/contact",
                ]
                
                for contact_url in common_contact_urls:
                    try:
                        logger.info(f"Trying contact URL: {contact_url}")
                        contact_data = self._browse_page(contact_url)
                        if contact_data and (contact_data.get('emails') or contact_data.get('phones') or contact_data.get('addresses')):
                            logger.info(f"[OK] Found contact info at: {contact_url}")
                            result['contact_page'] = contact_url
                            result['emails'].extend(contact_data.get('emails', []))
                            result['phones'].extend(contact_data.get('phones', []))
                            result['addresses'].extend(contact_data.get('addresses', []))
                            result['contact_names'].extend(contact_data.get('names', []))
                            break  # Found contact info, stop trying
                    except Exception as e:
                        logger.debug(f"Failed to browse {contact_url}: {str(e)}")
                        continue
            
            # Browse about page
            if key_pages.get('about'):
                result['about_page'] = key_pages['about']
                about_data = self._browse_page(key_pages['about'])
                if about_data:
                    result['contact_names'].extend(about_data.get('names', []))
                    result['addresses'].extend(about_data.get('addresses', []))
            
            # Browse team page
            if key_pages.get('team'):
                result['team_page'] = key_pages['team']
                team_data = self._browse_page(key_pages['team'])
                if team_data:
                    result['contact_names'].extend(team_data.get('names', []))
                    result['emails'].extend(team_data.get('emails', []))
            
            # Step 4: Find social media links
            result['social_links'] = self._extract_social_links(homepage_data.get('soup'))
            
            # Deduplicate results
            result['emails'] = list(set(result['emails']))
            result['phones'] = list(set(result['phones']))
            result['addresses'] = list(set(result['addresses']))
            result['contact_names'] = list(set(result['contact_names']))
            
            # Step 5: Extract LinkedIn URLs from all visited pages
            # Collect contacts from all pages we've browsed
            all_contacts = []
            
            # Homepage contacts
            if homepage_data and homepage_data.get('contacts'):
                all_contacts.extend(homepage_data.get('contacts', []))
            
            # Contact page contacts (already browsed above)
            if key_pages.get('contact') and 'contact_data' in locals() and contact_data and contact_data.get('contacts'):
                all_contacts.extend(contact_data.get('contacts', []))
            
            # About page contacts (already browsed above)
            if key_pages.get('about') and 'about_data' in locals() and about_data and about_data.get('contacts'):
                all_contacts.extend(about_data.get('contacts', []))
            
            # Team page contacts (already browsed above)
            if key_pages.get('team') and 'team_data' in locals() and team_data and team_data.get('contacts'):
                all_contacts.extend(team_data.get('contacts', []))
            
            # Build LinkedIn URLs list
            linkedin_urls = []
            for contact in all_contacts:
                if contact.get('linkedin_url'):
                    linkedin_urls.append({
                        'name': contact.get('name'),
                        'title': contact.get('title'),
                        'linkedin_url': contact.get('linkedin_url'),
                        'confidence': contact.get('confidence', 'medium')
                    })
            
            result['linkedin_urls'] = linkedin_urls
            result['all_contacts'] = all_contacts  # Include full contact objects
            
            logger.info(f"Web search complete: {len(result['emails'])} emails, {len(result['contact_names'])} names, {len(linkedin_urls)} LinkedIn URLs found")
            
        except Exception as e:
            logger.error(f"Web search failed for {company_name}: {str(e)}")
        
        return result
    
    def _find_company_website(self, company_name: str, location: Optional[str] = None) -> Optional[str]:
        """
        Find the company website using web search
        Now uses DuckDuckGo search instead of just guessing
        
        Args:
            company_name: Company name
            location: Optional location to help narrow search
        """
        try:
            # Use web search service for better results
            from apps.dashboard.services.web_search_service import get_web_search_service
            search_service = get_web_search_service()
            website = search_service.search_company_website(company_name, location=location)
            return website
        except Exception as e:
            logger.error(f"Web search failed, falling back to domain guessing: {str(e)}")
            
            # Fallback to simple domain patterns
            company_slug = company_name.lower().replace(' ', '').replace('-', '').replace('_', '')
            
            potential_domains = [
                f"https://www.{company_slug}.com",
                f"https://{company_slug}.com",
                f"https://www.{company_slug}.io",
                f"https://{company_slug}.io",
                f"https://www.{company_slug}.co",
                f"https://{company_slug}.co",
            ]
            
            for url in potential_domains:
                try:
                    response = self.session.head(url, timeout=5, allow_redirects=True)
                    if response.status_code == 200:
                        return response.url  # Return final URL after redirects
                except:
                    continue
            
            return None
    
    def _browse_page(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Browse a page and extract useful information
        Uses AI-powered extraction for better accuracy
        """
        try:
            logger.debug(f"Browsing: {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Use AI to extract contacts from the page text
            page_text = soup.get_text()
            
            try:
                from apps.dashboard.services.ai_contact_extractor import get_ai_contact_extractor
                ai_extractor = get_ai_contact_extractor()
                ai_results = ai_extractor.extract_contacts_from_text(page_text, url, soup)
                
                logger.debug(f"AI extraction results: {ai_results}")
                
                # Extract data from AI results
                contacts = ai_results.get('contacts', [])
                names_with_titles = [
                    f"{c['name']}" + (f" ({c['title']})" if c.get('title') else "")
                    for c in contacts
                ]
                
                # Combine emails from AI and traditional extraction
                ai_emails = ai_results.get('general_emails', [])
                ai_emails.extend([c['email'] for c in contacts if c.get('email')])
                traditional_emails = self._extract_emails(soup)
                all_emails = list(set(ai_emails + traditional_emails))
                
                logger.debug(f"Emails - AI: {len(ai_emails)}, Traditional: {len(traditional_emails)}, Total: {len(all_emails)}")
                
                # Same for phones
                ai_phones = ai_results.get('general_phones', [])
                traditional_phones = self._extract_phones(soup)
                all_phones = list(set(ai_phones + traditional_phones))
                
                logger.debug(f"Phones - AI: {len(ai_phones)}, Traditional: {len(traditional_phones)}, Total: {len(all_phones)}")
                
                # Extract addresses
                addresses = self._extract_addresses(soup)
                
                logger.debug(f"Addresses extracted: {len(addresses)}")
                if addresses:
                    logger.info(f"Found addresses: {addresses[:3]}")  # Log first 3
                
                # Log a sample of the page text for debugging (look for "Tel" and addresses)
                if 'tel' in page_text.lower() or 'phone' in page_text.lower():
                    # Find the section with phone numbers
                    tel_index = page_text.lower().find('tel')
                    if tel_index > 0:
                        sample_start = max(0, tel_index - 100)
                        sample_end = min(len(page_text), tel_index + 200)
                        logger.info(f"Page contains 'Tel' - sample: {page_text[sample_start:sample_end]}")
                
                if 'utrecht' in page_text.lower() or 'netherlands' in page_text.lower():
                    # Find Netherlands section
                    nl_index = page_text.lower().find('netherlands')
                    if nl_index > 0:
                        sample_start = max(0, nl_index - 200)
                        sample_end = min(len(page_text), nl_index + 100)
                        logger.info(f"Page contains 'Netherlands' - sample: {page_text[sample_start:sample_end]}")
                
                # Store full contact objects
                data = {
                    'url': url,
                    'soup': soup,
                    'emails': all_emails,
                    'phones': all_phones,
                    'addresses': addresses,
                    'names': names_with_titles,
                    'contacts': contacts,  # Full structured data
                    'description': self._extract_description(soup)
                }
                
                logger.info(f"Page extraction complete: {len(all_emails)} emails, {len(all_phones)} phones, {len(addresses)} addresses, {len(names_with_titles)} names")
                
            except Exception as e:
                logger.warning(f"AI extraction failed, using traditional methods: {str(e)}")
                import traceback
                logger.debug(f"AI extraction error traceback: {traceback.format_exc()}")
                # Fallback to traditional extraction
                data = {
                    'url': url,
                    'soup': soup,
                    'emails': self._extract_emails(soup),
                    'phones': self._extract_phones(soup),
                    'addresses': self._extract_addresses(soup),
                    'names': self._extract_names(soup),
                    'contacts': [],
                    'description': self._extract_description(soup)
                }
            
            # Special handling for LinkedIn pages
            if 'linkedin.com' in url.lower():
                # Extract company LinkedIn profile URL (from job pages)
                company_linkedin_url = self._extract_company_linkedin_url(soup)
                if company_linkedin_url:
                    data['company_linkedin_url'] = company_linkedin_url
                    logger.info(f"Extracted company LinkedIn URL: {company_linkedin_url}")
                
                # Extract company website URL (from company pages)
                company_website = self._extract_company_website_from_linkedin(soup)
                if company_website:
                    data['company_website'] = company_website
                    logger.info(f"Extracted company website from LinkedIn: {company_website}")
            
            return data
            
        except Exception as e:
            logger.warning(f"Failed to browse {url}: {str(e)}")
            return None
    
    def _extract_company_linkedin_url(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract LinkedIn company profile URL from job posting pages
        Job pages have links to company pages like: linkedin.com/company/pm-group_165501
        """
        try:
            for link in soup.find_all('a', href=True):
                href = link.get('href')
                
                # Look for company profile URLs
                if href and '/company/' in href and 'linkedin.com' in href:
                    # Clean up tracking parameters
                    from urllib.parse import urlparse, urlunparse
                    parsed = urlparse(href)
                    # Remove query parameters (tracking)
                    clean_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
                    
                    # Make sure it starts with http
                    if not clean_url.startswith('http'):
                        clean_url = 'https://' + clean_url.lstrip('/')
                    
                    logger.debug(f"Found company LinkedIn URL: {clean_url}")
                    return clean_url
        
        except Exception as e:
            logger.warning(f"Failed to extract company LinkedIn URL: {e}")
        
        return None
    
    def _extract_company_website_from_linkedin(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract company website URL from LinkedIn company/job pages
        LinkedIn has "Visit website" or "Learn more" buttons with company URLs
        """
        try:
            # Look for links with "Visit website" or "Learn more" text
            for link in soup.find_all('a', href=True):
                text = link.get_text(strip=True).lower()
                
                # Check for typical button text
                if any(keyword in text for keyword in ['visit website', 'learn more', 'company website']):
                    href = link.get('href')
                    
                    # Skip LinkedIn internal links
                    if href and 'linkedin.com' not in href.lower():
                        # Clean up URL
                        if href.startswith('http'):
                            logger.debug(f"Found company website link via '{text}': {href}")
                            return href
            
            # Alternative: Look for external links in specific sections
            # LinkedIn often wraps website links in specific classes
            external_links = soup.find_all('a', class_=lambda c: c and 'external' in c.lower())
            for link in external_links:
                href = link.get('href')
                if href and href.startswith('http') and 'linkedin.com' not in href.lower():
                    # Verify it looks like a company website
                    from urllib.parse import urlparse
                    parsed = urlparse(href)
                    if parsed.netloc and not any(skip in parsed.netloc.lower() for skip in ['facebook', 'twitter', 'instagram']):
                        logger.debug(f"Found company website via external link: {href}")
                        return href
            
        except Exception as e:
            logger.warning(f"Failed to extract company website from LinkedIn: {e}")
        
        return None
    
    def _find_key_pages(self, base_url: str, soup: Optional[BeautifulSoup]) -> Dict[str, str]:
        """
        Find important pages like Contact, About, Team
        """
        key_pages = {}
        
        if not soup:
            return key_pages
        
        # Find all links
        links = soup.find_all('a', href=True)
        
        for link in links:
            href = link.get('href', '').lower()
            text = link.get_text().lower().strip()
            
            # Make absolute URL
            full_url = urljoin(base_url, link['href'])
            
            # Check if this is a domain we should skip (LinkedIn, etc.)
            if self._should_skip_url(full_url):
                continue
            
            # Contact page - expanded keywords
            if not key_pages.get('contact'):
                if any(keyword in href or keyword in text for keyword in [
                    'contact', 'get-in-touch', 'reach-us', 'kontakt', 'contacteer', 
                    'contact-us', 'contactgegevens', 'locations', 'offices', 'address'
                ]):
                    key_pages['contact'] = full_url
            
            # About page
            if not key_pages.get('about'):
                if any(keyword in href or keyword in text for keyword in ['about', 'who-we-are', 'company']):
                    key_pages['about'] = full_url
            
            # Team page
            if not key_pages.get('team'):
                if any(keyword in href or keyword in text for keyword in ['team', 'people', 'leadership', 'our-team', 'staff', 'our-people', 'client-services', 'services']):
                    key_pages['team'] = full_url
        
        return key_pages
    
    def _should_skip_url(self, url: str) -> bool:
        """
        Check if we should skip this URL (e.g., LinkedIn, social media)
        """
        skip_domains = [
            'linkedin.com',
            'facebook.com',
            'twitter.com',
            'instagram.com',
            'youtube.com',
            'tiktok.com'
        ]
        
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        return any(skip in domain for skip in skip_domains)
    
    def _extract_emails(self, soup: BeautifulSoup) -> List[str]:
        """Extract email addresses from page"""
        emails = []
        
        # Pattern for email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        
        # Search in text content
        text = soup.get_text()
        found_emails = re.findall(email_pattern, text)
        emails.extend(found_emails)
        
        # Search in mailto links
        mailto_links = soup.find_all('a', href=re.compile(r'^mailto:'))
        for link in mailto_links:
            email = link['href'].replace('mailto:', '').split('?')[0]
            emails.append(email)
        
        # Filter out common generic emails
        generic_patterns = ['example.com', 'domain.com', 'email.com', 'test@']
        emails = [e for e in emails if not any(pattern in e.lower() for pattern in generic_patterns)]
        
        return list(set(emails))
    
    def _extract_phones(self, soup: BeautifulSoup) -> List[str]:
        """Extract phone numbers from page - supports European and US formats"""
        phones = []
        
        text = soup.get_text()
        
        # Normalize text: replace multiple spaces/newlines with single space
        text_normalized = ' '.join(text.split())
        
        # Multiple phone patterns for different formats
        phone_patterns = [
            r'Tel\.?\s*\+\d{1,3}[\s\d]+',  # "Tel. +31 30 2 123 123" or "Tel +45 7020 2728"
            r'\+\d{1,3}[\s.-]?\d{1,4}[\s.-]?\d{1,4}[\s.-]?\d{1,4}[\s.-]?\d{1,4}',  # International: +31 30 2 123 123
            r'\+\d{1,3}[\s.-]?\(?\d{1,4}\)?[\s.-]?\d{1,4}[\s.-]?\d{1,4}',  # +1 (555) 123-4567
            r'\d{2,4}[\s.-]\d{1,4}[\s.-]\d{1,4}[\s.-]\d{1,4}',  # European: 030 123 456 78
            r'\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}',  # US: (555) 123-4567
        ]
        
        # Try on normalized text first
        for pattern in phone_patterns:
            found = re.findall(pattern, text_normalized)
            phones.extend(found)
        
        # Also try on original text in case normalization broke something
        for pattern in phone_patterns:
            found = re.findall(pattern, text)
            phones.extend(found)
        
        # Search in tel links
        tel_links = soup.find_all('a', href=re.compile(r'^tel:'))
        for link in tel_links:
            phone = link['href'].replace('tel:', '').strip()
            phones.append(phone)
        
        # Clean and deduplicate
        cleaned_phones = []
        logger.info(f"Raw phones found before cleaning: {phones[:5]}")  # Log first 5
        
        for phone in phones:
            # Clean "Tel." prefix if present
            phone = phone.replace('Tel.', '').replace('Tel', '').strip()
            # Remove extra whitespace
            phone = ' '.join(phone.split())
            # Only keep if it has enough digits (at least 7)
            digits_only = re.sub(r'[^\d]', '', phone)
            if len(digits_only) >= 7:
                cleaned_phones.append(phone)
        
        logger.info(f"Cleaned phones: {cleaned_phones}")
        return list(set(cleaned_phones))
    
    def _extract_addresses(self, soup: BeautifulSoup) -> List[str]:
        """Extract physical addresses from page"""
        addresses = []
        
        text = soup.get_text()
        
        # Look for structured addresses in the text
        # Pattern 1: Multi-line address with "Address" label
        # Example: "Address\nUppsalalaan 15\n3584 CT Utrecht\nThe Netherlands"
        lines = text.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            # Check if this line contains "Address" or "Visiting Address"
            if 'address' in line.lower() and len(line) < 50:
                # Collect next 3-4 lines as potential address
                addr_lines = []
                for j in range(i+1, min(i+5, len(lines))):
                    next_line = lines[j].strip()
                    if next_line and len(next_line) < 100:
                        addr_lines.append(next_line)
                        # Stop if we hit a line that looks like end of address
                        if any(keyword in next_line.lower() for keyword in ['tel', 'phone', 'email', 'fax', 'kvk', 'vat']):
                            break
                if len(addr_lines) >= 2:
                    # Join the address lines
                    full_address = ', '.join(addr_lines[:4])  # Take up to 4 lines
                    addresses.append(full_address)
        
        # Pattern 2: Dutch postal code pattern in text
        # "Street Number, 1234 AB City"
        postal_pattern = r'([A-Z][a-zà-ÿ]+(?:\s+[A-Z][a-zà-ÿ]+)*\s+\d+[a-zA-Z]?\s*,?\s*\d{4}\s*[A-Z]{2}\s+[A-Z][a-zà-ÿ]+)'
        found = re.findall(postal_pattern, text, re.MULTILINE)
        addresses.extend(found)
        
        # Look for address in structured HTML tags
        for tag in soup.find_all(['address', 'div'], class_=re.compile(r'address|location|contact')):
            addr_text = tag.get_text(separator=', ', strip=True)
            if len(addr_text) > 15 and len(addr_text) < 300:
                addresses.append(addr_text)
        
        # Clean and deduplicate
        cleaned_addresses = []
        for addr in addresses:
            # Remove excessive whitespace
            addr = ' '.join(addr.split())
            # Must be substantial and contain numbers (street number or postal code)
            if len(addr) > 15 and re.search(r'\d', addr):
                cleaned_addresses.append(addr)
        
        return list(set(cleaned_addresses))
    
    def _extract_names(self, soup: BeautifulSoup) -> List[str]:
        """
        Extract potential contact names from page
        Looks for common patterns: "John Smith, CEO" etc.
        """
        names = []
        
        # Strategy 1: Look for team/leadership sections
        team_sections = soup.find_all(['div', 'section', 'article'], class_=re.compile(r'team|staff|member|people|leadership|about', re.I))
        
        for section in team_sections:
            # Find headings that might be names
            headings = section.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b', 'p'])
            for heading in headings:
                text = heading.get_text().strip()
                # Check if it looks like a name (2-3 words, capitalized)
                words = text.split()
                if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if w and len(w) > 1):
                    # Filter out common non-name phrases
                    skip_phrases = ['View Our', 'Meet The', 'Our Team', 'The Team', 'Contact Us', 'Get In Touch']
                    if not any(skip in text for skip in skip_phrases):
                        names.append(text)
        
        # Strategy 2: Look for text patterns like "Name\nTitle" or "Name, Title"
        all_text = soup.get_text()
        
        # Pattern: Line with Name, next line with title (CEO, Director, etc.)
        lines = [line.strip() for line in all_text.split('\n') if line.strip()]
        title_keywords = ['CEO', 'COO', 'CFO', 'CTO', 'Director', 'Manager', 'President', 'Vice President', 'VP', 'Head', 'Chief', 'Lead']
        
        for i in range(len(lines) - 1):
            current_line = lines[i]
            next_line = lines[i + 1]
            
            # Check if current line looks like a name
            words = current_line.split()
            if 2 <= len(words) <= 4:
                # Check if next line contains a title
                if any(keyword in next_line for keyword in title_keywords):
                    # This is likely a name followed by a title
                    if current_line not in names:
                        names.append(current_line)
        
        # Strategy 3: Find structured data (JSON-LD, microdata)
        # Look for Person schema
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            try:
                import json
                data = json.loads(script.string)
                if isinstance(data, dict):
                    if data.get('@type') == 'Person' and data.get('name'):
                        names.append(data['name'])
                    elif data.get('@type') == 'Organization' and data.get('employee'):
                        employees = data['employee'] if isinstance(data['employee'], list) else [data['employee']]
                        for emp in employees:
                            if isinstance(emp, dict) and emp.get('name'):
                                names.append(emp['name'])
            except:
                pass
        
        # Deduplicate and clean
        cleaned_names = []
        seen = set()
        
        # Filter out common false positives
        skip_patterns = [
            'read more', 'learn more', 'click here', 'view', 'see more',
            'the team', 'our team', 'meet', 'about us', 'contact',
            'the leadership', 'leadership team', 'management team'
        ]
        
        for name in names:
            # Clean up the name
            name = re.sub(r'\s+', ' ', name).strip()
            
            # Skip false positives
            if any(skip in name.lower() for skip in skip_patterns):
                continue
            
            # Skip if too short or already seen
            if len(name) > 3 and name.lower() not in seen:
                seen.add(name.lower())
                cleaned_names.append(name)
        
        return cleaned_names[:30]  # Limit to 30 names
    
    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract company description from meta tags or about text"""
        
        # Try meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            return meta_desc['content'].strip()
        
        # Try og:description
        og_desc = soup.find('meta', attrs={'property': 'og:description'})
        if og_desc and og_desc.get('content'):
            return og_desc['content'].strip()
        
        return None
    
    def _extract_social_links(self, soup: Optional[BeautifulSoup]) -> Dict[str, str]:
        """Extract social media links (for reference, not scraping)"""
        if not soup:
            return {}
        
        social = {}
        
        social_patterns = {
            'linkedin_company': r'linkedin\.com/company/',
            'twitter': r'twitter\.com/',
            'facebook': r'facebook\.com/',
            'youtube': r'youtube\.com/'
        }
        
        links = soup.find_all('a', href=True)
        for link in links:
            href = link['href']
            for platform, pattern in social_patterns.items():
                if re.search(pattern, href) and platform not in social:
                    social[platform] = href
        
        return social


# Singleton instance
_web_browser_service = None


def get_web_browser_service() -> WebBrowserService:
    """Get or create web browser service singleton"""
    global _web_browser_service
    if _web_browser_service is None:
        _web_browser_service = WebBrowserService()
    return _web_browser_service
