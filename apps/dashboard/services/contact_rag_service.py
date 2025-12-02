"""
RAG-based Contact Finder
Uses existing job posting data to enhance AI contact research
Also scrapes company About pages to find real team member names
"""
import logging
import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, List, Optional
from urllib.parse import urljoin, urlparse
from apps.dashboard.services.bigquery_service import get_bigquery_service

logger = logging.getLogger(__name__)


class ContactRAGService:
    """
    Retrieval-Augmented Generation service for contact finding
    Uses existing job posting data to provide context to AI
    """
    
    def __init__(self):
        self.bq_service = get_bigquery_service()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def get_company_context(self, company_name: str) -> Dict[str, Any]:
        """
        Retrieve all available context about a company from job postings
        This creates a rich knowledge base without any web scraping
        """
        try:
            # Get all jobs for this company
            query = f"""
                SELECT 
                    job_id,
                    title,
                    url,
                    location,
                    country,
                    description,
                    skills,
                    posted_date,
                    scraped_at,
                    source
                FROM `agiliz-sales-tool.zoektrends_job_data.job_postings`
                WHERE LOWER(company) LIKE '%{company_name.lower()}%'
                   OR LOWER(company_name) LIKE '%{company_name.lower()}%'
                ORDER BY scraped_at DESC
                LIMIT 20
            """
            
            jobs = self.bq_service._execute_query(query)
            
            if not jobs:
                logger.warning(f"No job data found for {company_name}")
                return {
                    'company_name': company_name,
                    'jobs_found': 0,
                    'context': None
                }
            
            # Get company metadata
            company_query = f"""
                SELECT 
                    company_id,
                    company_name,
                    normalized_name,
                    status,
                    company_type,
                    company_industry,
                    company_size,
                    description,
                    solution_domain,
                    tech_stack
                FROM `agiliz-sales-tool.zoektrends_job_data.companies`
                WHERE LOWER(company_name) LIKE '%{company_name.lower()}%'
                LIMIT 1
            """
            
            company_data = self.bq_service._execute_query(company_query)
            company_info = company_data[0] if company_data else {}
            
            # Extract most common country/location from jobs
            countries = [job.get('country') for job in jobs if job.get('country')]
            most_common_country = max(set(countries), key=countries.count) if countries else None
            
            # Try to scrape company website for About/Team pages
            website_data = None
            if company_info.get('website'):
                logger.info(f"Attempting to scrape website: {company_info.get('website')}")
                website_data = self.scrape_company_website(company_name, company_info.get('website'))
            
            # Build comprehensive context
            context = self._build_context(jobs, company_info, website_data)
            
            return {
                'company_name': company_name,
                'jobs_found': len(jobs),
                'context': context,
                'country': most_common_country,
                'jobs': jobs,  # Include raw jobs for LinkedIn URL extraction
                'website_data': website_data  # Include scraped website data
            }
            
        except Exception as e:
            logger.error(f"Failed to get company context: {str(e)}")
            return {
                'company_name': company_name,
                'jobs_found': 0,
                'error': str(e)
            }
    
    def scrape_company_website(self, company_name: str, website_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Scrape company website to find About/Team pages with real names
        
        Returns:
            {
                'website': str,
                'about_pages_found': List[str],
                'team_members': List[Dict],  # [{name, title, bio}]
                'contact_info': Dict
            }
        """
        try:
            if not website_url:
                # Try to find website from job postings or construct from company name
                website_url = self._find_company_website(company_name)
                if not website_url:
                    logger.warning(f"No website found for {company_name}")
                    return {'error': 'No website found'}
            
            # Normalize URL
            if not website_url.startswith('http'):
                website_url = f'https://{website_url}'
            
            logger.info(f"Scraping website: {website_url}")
            
            # Find About pages
            about_pages = self._find_about_pages(website_url)
            
            # Extract team members from About pages
            team_members = []
            for page_url in about_pages[:5]:  # Limit to 5 pages
                members = self._extract_team_members(page_url)
                team_members.extend(members)
            
            # Remove duplicates
            unique_members = []
            seen_names = set()
            for member in team_members:
                name_key = member.get('name', '').lower().strip()
                if name_key and name_key not in seen_names:
                    seen_names.add(name_key)
                    unique_members.append(member)
            
            return {
                'website': website_url,
                'about_pages_found': about_pages,
                'team_members': unique_members,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Failed to scrape website {website_url}: {str(e)}")
            return {'error': str(e), 'success': False}
    
    def _find_company_website(self, company_name: str) -> Optional[str]:
        """Try to find company website from various sources"""
        try:
            # Check if we have it in company metadata
            query = f"""
                SELECT website, company_linkedin
                FROM `agiliz-sales-tool.zoektrends_job_data.companies`
                WHERE LOWER(company_name) LIKE '%{company_name.lower()}%'
                LIMIT 1
            """
            results = self.bq_service._execute_query(query)
            if results and results[0].get('website'):
                return results[0]['website']
            
            # If not found, try constructing from company name
            # This is just a guess - may not work
            clean_name = company_name.lower().replace(' ', '').replace('.', '')
            return f"https://www.{clean_name}.com"
            
        except Exception as e:
            logger.error(f"Error finding website: {str(e)}")
            return None
    
    def _find_about_pages(self, website_url: str) -> List[str]:
        """
        Find About/Team pages by checking common patterns
        """
        about_pages = []
        
        # Common About page patterns (prioritize these)
        patterns = [
            '/about', '/about-us', '/about/', '/about-us/',
            '/team', '/our-team', '/team/', '/our-team/',
            '/our-story', '/story', '/our-story/', '/story/',
            '/leadership', '/management', '/leadership/', '/management/',
            '/company', '/company/', '/over-ons', '/over-ons/',  # Dutch
            '/contact', '/contact-us', '/contact/', '/contact-us/'
        ]
        
        base_url = website_url.rstrip('/')
        
        for pattern in patterns:
            url = base_url + pattern
            try:
                response = self.session.get(url, timeout=5, allow_redirects=True)
                if response.status_code == 200:
                    # Check if page actually exists and has content
                    soup = BeautifulSoup(response.content, 'html.parser')
                    text_content = soup.get_text().lower()
                    
                    # Check for relevant keywords
                    if any(keyword in text_content for keyword in ['team', 'about', 'leadership', 'story', 'founder', 'ceo', 'cto']):
                        about_pages.append(response.url)
                        logger.info(f"Found About page: {response.url}")
                
            except Exception as e:
                logger.debug(f"Failed to check {url}: {str(e)}")
                continue
        
        return about_pages
    
    def _extract_team_members(self, page_url: str) -> List[Dict[str, str]]:
        """
        Extract team member names and titles from an About/Team page
        
        Returns:
            List of {name, title, linkedin, bio}
        """
        try:
            response = self.session.get(page_url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            members = []
            
            # Strategy 1: Look for structured team member sections
            # Common patterns: div.team-member, div.person, div.profile, article.team, etc.
            team_selectors = [
                '.team-member', '.team-card', '.person', '.profile',
                '.member', '.employee', '.staff', '[class*="team"]',
                '[class*="member"]', '[class*="person"]', 'article'
            ]
            
            for selector in team_selectors:
                team_elements = soup.select(selector)
                if team_elements:
                    logger.info(f"Found {len(team_elements)} potential team members with selector: {selector}")
                    
                    for element in team_elements:
                        member = self._parse_team_member_element(element)
                        if member and member.get('name'):
                            members.append(member)
                    
                    # If we found members, stop trying other selectors
                    if members:
                        break
            
            # Strategy 2: Look for name + title patterns in text
            if not members:
                members = self._extract_names_from_text(soup)
            
            logger.info(f"Extracted {len(members)} team members from {page_url}")
            return members
            
        except Exception as e:
            logger.error(f"Failed to extract team members from {page_url}: {str(e)}")
            return []
    
    def _parse_team_member_element(self, element) -> Optional[Dict[str, str]]:
        """Parse a single team member element to extract name, title, etc."""
        try:
            member = {}
            
            # Try to find name (usually in h2, h3, h4, or strong tags)
            name_element = element.find(['h1', 'h2', 'h3', 'h4', 'h5', 'strong', 'b', '.name', '[class*="name"]'])
            if name_element:
                name = name_element.get_text().strip()
                # Clean up name (remove extra whitespace, newlines)
                name = ' '.join(name.split())
                if len(name) > 2 and len(name) < 100:  # Sanity check
                    member['name'] = name
            
            # Try to find title/role
            title_element = element.find(['p', 'span', '.title', '.role', '.position', '[class*="title"]', '[class*="role"]'])
            if title_element and 'name' in member:
                title = title_element.get_text().strip()
                title = ' '.join(title.split())
                # Don't include if it's the same as the name
                if title and title != member['name'] and len(title) < 200:
                    member['title'] = title
            
            # Try to find LinkedIn
            linkedin_link = element.find('a', href=lambda x: x and 'linkedin.com' in x)
            if linkedin_link:
                member['linkedin'] = linkedin_link.get('href')
            
            # Try to find bio/description
            bio_element = element.find(['p', 'div'], class_=lambda x: x and any(word in str(x).lower() for word in ['bio', 'description', 'about']))
            if bio_element:
                bio = bio_element.get_text().strip()
                if len(bio) > 20 and len(bio) < 1000:
                    member['bio'] = bio[:500]  # Truncate long bios
            
            return member if member.get('name') else None
            
        except Exception as e:
            logger.debug(f"Error parsing team member element: {str(e)}")
            return None
    
    def _extract_names_from_text(self, soup) -> List[Dict[str, str]]:
        """
        Fallback: Extract names from text patterns like:
        'John Smith - CEO' or 'Jane Doe, CTO'
        """
        members = []
        text = soup.get_text()
        
        # Common title patterns
        title_patterns = [
            'CEO', 'CTO', 'CFO', 'COO', 'CIO', 'CMO',
            'Chief', 'Director', 'Manager', 'Head of',
            'VP', 'Vice President', 'President',
            'Lead', 'Founder', 'Co-Founder'
        ]
        
        lines = text.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Check if line contains a title
            if any(title in line for title in title_patterns):
                # Try to extract name and title
                # Pattern: "Name - Title" or "Name, Title" or "Name\nTitle"
                for separator in [' - ', ', ', ' – ', ' — ']:
                    if separator in line:
                        parts = line.split(separator, 1)
                        if len(parts) == 2:
                            potential_name = parts[0].strip()
                            potential_title = parts[1].strip()
                            
                            # Basic validation
                            if (2 <= len(potential_name.split()) <= 5 and  # 2-5 words
                                len(potential_name) < 50 and
                                any(title in potential_title for title in title_patterns)):
                                
                                members.append({
                                    'name': potential_name,
                                    'title': potential_title
                                })
                                break
        
        return members
    
    def _build_context(self, jobs: List[Dict], company_info: Dict, website_data: Optional[Dict] = None) -> str:
        """
        Build a rich context document from job data and website scraping
        This is what we'll feed to the AI
        """
        context_parts = []
        
        # Website team information (PRIORITY - show this first!)
        if website_data and website_data.get('success') and website_data.get('team_members'):
            context_parts.append("="*60)
            context_parts.append("TEAM MEMBERS FROM COMPANY WEBSITE (REAL NAMES)")
            context_parts.append("="*60)
            context_parts.append(f"Website: {website_data.get('website')}")
            context_parts.append(f"About pages found: {', '.join(website_data.get('about_pages_found', []))}")
            context_parts.append("")
            
            for member in website_data['team_members']:
                context_parts.append(f"• {member['name']}")
                if member.get('title'):
                    context_parts.append(f"  Title: {member['title']}")
                if member.get('linkedin'):
                    context_parts.append(f"  LinkedIn: {member['linkedin']}")
                if member.get('bio'):
                    context_parts.append(f"  Bio: {member['bio'][:200]}...")
                context_parts.append("")
            
            context_parts.append("="*60)
            context_parts.append("")
        
        # Company overview
        if company_info:
            context_parts.append(f"COMPANY OVERVIEW:")
            context_parts.append(f"- Official Name: {company_info.get('company_name', 'Unknown')}")
            context_parts.append(f"- Type: {company_info.get('company_type', 'Unknown')}")
            context_parts.append(f"- Industry: {company_info.get('company_industry', 'Unknown')}")
            context_parts.append(f"- Size: {company_info.get('company_size', 'Unknown')}")
            
            if company_info.get('tech_stack'):
                tech_stack = ', '.join(company_info.get('tech_stack', [])[:10])
                context_parts.append(f"- Technologies Used: {tech_stack}")
            
            if company_info.get('description'):
                context_parts.append(f"- Description: {company_info.get('description')}")
            
            context_parts.append("")
        
        # Active job postings
        context_parts.append(f"ACTIVE JOB POSTINGS ({len(jobs)}):")
        
        # Group jobs by role type
        data_roles = []
        tech_roles = []
        management_roles = []
        other_roles = []
        
        for job in jobs:
            title = job.get('title', '').lower()
            job_info = {
                'title': job.get('title'),
                'url': job.get('url'),
                'location': job.get('location'),
                'skills': job.get('skills', [])
            }
            
            if any(word in title for word in ['data', 'analytics', 'bi', 'analyst']):
                data_roles.append(job_info)
            elif any(word in title for word in ['engineer', 'developer', 'architect', 'devops', 'cloud']):
                tech_roles.append(job_info)
            elif any(word in title for word in ['manager', 'director', 'lead', 'head', 'vp', 'chief']):
                management_roles.append(job_info)
            else:
                other_roles.append(job_info)
        
        # Data & Analytics roles
        if data_roles:
            context_parts.append(f"\nData & Analytics Roles ({len(data_roles)}):")
            for job in data_roles[:5]:
                context_parts.append(f"  • {job['title']}")
                context_parts.append(f"    Location: {job['location']}")
                if job['url']:
                    context_parts.append(f"    LinkedIn: {job['url']}")
                if job['skills']:
                    context_parts.append(f"    Skills: {', '.join(job['skills'][:5])}")
        
        # Technical roles
        if tech_roles:
            context_parts.append(f"\nTechnical/Engineering Roles ({len(tech_roles)}):")
            for job in tech_roles[:5]:
                context_parts.append(f"  • {job['title']}")
                context_parts.append(f"    Location: {job['location']}")
                if job['url']:
                    context_parts.append(f"    LinkedIn: {job['url']}")
        
        # Management roles
        if management_roles:
            context_parts.append(f"\nManagement/Leadership Roles ({len(management_roles)}):")
            for job in management_roles[:3]:
                context_parts.append(f"  • {job['title']}")
                context_parts.append(f"    Location: {job['location']}")
                if job['url']:
                    context_parts.append(f"    LinkedIn: {job['url']}")
        
        # Key insights
        context_parts.append(f"\nKEY INSIGHTS:")
        
        # Most common skills
        all_skills = []
        for job in jobs:
            all_skills.extend(job.get('skills', []))
        
        if all_skills:
            from collections import Counter
            top_skills = Counter(all_skills).most_common(10)
            context_parts.append(f"- Top Technologies: {', '.join([skill for skill, _ in top_skills])}")
        
        # Locations
        locations = list(set([job.get('location') for job in jobs if job.get('location')]))
        if locations:
            context_parts.append(f"- Office Locations: {', '.join(locations[:5])}")
        
        # Hiring focus
        if data_roles:
            context_parts.append(f"- Strong focus on Data & Analytics hiring ({len(data_roles)} roles)")
        if tech_roles:
            context_parts.append(f"- Active technical hiring ({len(tech_roles)} roles)")
        
        context_parts.append(f"\nWHO TO CONTACT:")
        context_parts.append(f"Based on this hiring activity, Agiliz should reach out to:")
        context_parts.append(f"1. Head of Data/Analytics (they're hiring {len(data_roles)} data roles)")
        context_parts.append(f"2. CTO/Engineering Director (managing {len(tech_roles)} technical roles)")
        context_parts.append(f"3. Whoever posted these LinkedIn jobs (check job URLs above)")
        
        return "\n".join(context_parts)
    
    def enhance_ai_prompt(self, company_name: str, base_prompt: str) -> str:
        """
        Enhance the AI prompt with RAG context
        This gives the AI much more information to work with
        """
        rag_data = self.get_company_context(company_name)
        
        if rag_data.get('context'):
            enhanced_prompt = f"""{base_prompt}

ADDITIONAL CONTEXT FROM JOB POSTINGS DATABASE:
================================================

{rag_data['context']}

================================================

Using the above context, identify the most relevant contacts at {company_name} for Agiliz to reach out to.
Focus on people who would be managing these teams and making technology decisions.
"""
            return enhanced_prompt
        
        return base_prompt


# Singleton instance
_rag_service = None


def get_rag_service() -> ContactRAGService:
    """Get or create RAG service singleton"""
    global _rag_service
    if _rag_service is None:
        _rag_service = ContactRAGService()
    return _rag_service
