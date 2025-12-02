"""
BigQuery Service
Handles all interactions with Google BigQuery for job data
Ported from Laravel BigQueryService.php with improvements
"""
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from google.cloud import bigquery
from google.oauth2 import service_account
from django.conf import settings
from django.core.cache import cache
import os

logger = logging.getLogger(__name__)


class BigQueryService:
    """Service for interacting with BigQuery job data"""
    
    def __init__(self):
        self.project_id = settings.GOOGLE_CLOUD['PROJECT_ID']
        self.dataset = settings.BIGQUERY['DATASET']
        self.table = settings.BIGQUERY['TABLE']
        self.companies_table = settings.BIGQUERY.get('COMPANIES_TABLE', 'companies')
        self.skills_registry_table = settings.BIGQUERY.get('SKILLS_REGISTRY_TABLE', 'skills_registry')
        self.credentials_path = settings.GOOGLE_CLOUD['CREDENTIALS_PATH']
        
        # Initialize BigQuery client
        self.client = self._initialize_client()
    
    def _initialize_client(self) -> Optional[bigquery.Client]:
        """Initialize BigQuery client with credentials"""
        try:
            if not self.credentials_path or not os.path.exists(self.credentials_path):
                logger.error(f"Credentials file not found: {self.credentials_path}")
                return None
            
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=["https://www.googleapis.com/auth/bigquery"]
            )
            
            client = bigquery.Client(
                credentials=credentials,
                project=self.project_id
            )
            
            logger.info(f"BigQuery client initialized successfully for project: {self.project_id}")
            return client
            
        except Exception as e:
            logger.error(f"Failed to initialize BigQuery client: {str(e)}")
            return None
    
    def _execute_query(self, query: str, parameters: Optional[List] = None) -> List[Dict[str, Any]]:
        """Execute a BigQuery SQL query and return results"""
        try:
            if not self.client:
                raise Exception("BigQuery client not initialized")
            
            # Configure query job
            job_config = bigquery.QueryJobConfig()
            if parameters:
                job_config.query_parameters = parameters
            
            # Execute query
            query_job = self.client.query(query, job_config=job_config)
            results = query_job.result()
            
            # Convert to list of dicts
            rows = []
            for row in results:
                row_dict = dict(row.items())
                # Convert datetime objects to strings
                for key, value in row_dict.items():
                    if isinstance(value, datetime):
                        row_dict[key] = value.isoformat()
                rows.append(row_dict)
            
            return rows
            
        except Exception as e:
            logger.error(f"BigQuery query failed: {str(e)}\nQuery: {query}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get dashboard statistics
        Cached for performance
        """
        cache_key = 'bigquery:stats'
        stats = cache.get(cache_key)
        
        if stats is not None:
            logger.debug("Returning cached stats")
            return stats
        
        try:
            query = f"""
                SELECT 
                    COUNT(DISTINCT job_id) as total_jobs,
                    COUNT(DISTINCT company) as total_companies,
                    COUNT(DISTINCT CASE WHEN DATE(scraped_at) = CURRENT_DATE() THEN job_id END) as jobs_today,
                    COUNT(DISTINCT country) as total_countries
                FROM `{self.project_id}.{self.dataset}.{self.table}`
            """
            
            results = self._execute_query(query)
            
            if results:
                stats = results[0]
                cache.set(cache_key, stats, settings.CACHE_TTL_STATS)
                logger.info(f"Stats retrieved: {stats}")
                return stats
            
            return {
                'total_jobs': 0,
                'total_companies': 0,
                'jobs_today': 0,
                'total_countries': 0
            }
            
        except Exception as e:
            logger.error(f"Failed to get stats: {str(e)}")
            return {
                'total_jobs': 0,
                'total_companies': 0,
                'jobs_today': 0,
                'total_countries': 0,
                'error': str(e)
            }
    
    def get_recent_jobs(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get most recently scraped jobs"""
        try:
            query = f"""
                SELECT 
                    job_id,
                    title,
                    company,
                    location,
                    country,
                    source,
                    scraped_at,
                    posted_date,
                    url
                FROM `{self.project_id}.{self.dataset}.{self.table}`
                ORDER BY scraped_at DESC
                LIMIT {limit}
            """
            
            return self._execute_query(query)
            
        except Exception as e:
            logger.error(f"Failed to get recent jobs: {str(e)}")
            return []
    
    def get_jobs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get jobs list
        Cached for performance
        """
        cache_key = f'bigquery:jobs:{limit}'
        jobs = cache.get(cache_key)
        
        if jobs is not None:
            logger.debug(f"Returning cached jobs (limit: {limit})")
            return jobs
        
        try:
            query = f"""
                SELECT 
                    job_id,
                    title,
                    company,
                    location,
                    country,
                    source,
                    scraped_at,
                    posted_date,
                    url,
                    description,
                    requirements,
                    skills,
                    search_keyword
                FROM `{self.project_id}.{self.dataset}.{self.table}`
                ORDER BY scraped_at DESC
                LIMIT {limit}
            """
            
            jobs = self._execute_query(query)
            cache.set(cache_key, jobs, settings.CACHE_TTL_JOBS)
            
            return jobs
            
        except Exception as e:
            logger.error(f"Failed to get jobs: {str(e)}")
            return []
    
    def get_jobs_with_filters(self, filters: Dict[str, str], limit: int = 20) -> List[Dict[str, Any]]:
        """Get jobs with advanced filtering"""
        try:
            where_clauses = []
            
            # Source filter
            if filters.get('source'):
                where_clauses.append(f"LOWER(source) = '{filters['source'].lower()}'")
            
            # Country filter
            if filters.get('country'):
                where_clauses.append(f"LOWER(country) = '{filters['country'].lower()}'")
            
            # Tech stack filter - search in skills array
            if filters.get('tech_stack'):
                tech = filters['tech_stack'].replace("'", "\\'")
                where_clauses.append(f"EXISTS(SELECT 1 FROM UNNEST(skills) AS skill WHERE LOWER(skill) LIKE '%{tech.lower()}%')")
            
            # Keyword search
            if filters.get('keyword'):
                keyword = filters['keyword'].replace("'", "\\'").lower()
                where_clauses.append(f"""
                    (LOWER(title) LIKE '%{keyword}%' 
                     OR LOWER(company) LIKE '%{keyword}%'
                     OR LOWER(location) LIKE '%{keyword}%'
                     OR LOWER(search_keyword) LIKE '%{keyword}%')
                """)
            
            # Posted within filter
            if filters.get('posted_within'):
                days = int(filters['posted_within'])
                where_clauses.append(f"DATE(scraped_at) >= DATE_SUB(CURRENT_DATE(), INTERVAL {days} DAY)")
            
            # Build WHERE clause
            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            # Sorting
            sort_by = filters.get('sort_by', 'scraped_at')
            if sort_by == 'posted_date':
                order_by = 'posted_date DESC'
            else:
                order_by = 'scraped_at DESC'
            
            query = f"""
                SELECT 
                    job_id,
                    title,
                    company,
                    company_name,
                    company_id,
                    location,
                    country,
                    source,
                    scraped_at,
                    posted_date,
                    url,
                    description,
                    skills,
                    search_keyword,
                    salary_min,
                    salary_max,
                    currency,
                    employment_type,
                    remote_option,
                    experience_level,
                    has_related_tech,
                    has_primary_skill
                FROM `{self.project_id}.{self.dataset}.{self.table}`
                WHERE {where_sql}
                ORDER BY {order_by}
                LIMIT {limit}
            """
            
            return self._execute_query(query)
            
        except Exception as e:
            logger.error(f"Failed to get filtered jobs: {str(e)}")
            return []
    
    def get_job_count(self) -> int:
        """Get total job count"""
        try:
            query = f"""
                SELECT COUNT(*) as count
                FROM `{self.project_id}.{self.dataset}.{self.table}`
            """
            results = self._execute_query(query)
            return results[0]['count'] if results else 0
        except:
            return 0
    
    def get_company_count(self) -> int:
        """Get total unique company count"""
        try:
            query = f"""
                SELECT COUNT(DISTINCT company) as count
                FROM `{self.project_id}.{self.dataset}.{self.table}`
            """
            results = self._execute_query(query)
            return results[0]['count'] if results else 0
        except:
            return 0
    
    def get_unique_countries(self) -> List[str]:
        """Get list of unique countries"""
        cache_key = 'bigquery:countries'
        countries = cache.get(cache_key)
        
        if countries is not None:
            return countries
        
        try:
            query = f"""
                SELECT DISTINCT country
                FROM `{self.project_id}.{self.dataset}.{self.table}`
                WHERE country IS NOT NULL
                ORDER BY country
            """
            results = self._execute_query(query)
            countries = [row['country'] for row in results]
            cache.set(cache_key, countries, 3600)  # Cache for 1 hour
            return countries
        except:
            return []
    
    def get_unique_tech_stacks(self) -> List[str]:
        """Get list of unique tech stacks (skills)"""
        cache_key = 'bigquery:tech_stacks'
        tech_stacks = cache.get(cache_key)
        
        if tech_stacks is not None:
            return tech_stacks
        
        try:
            query = f"""
                SELECT DISTINCT skill
                FROM `{self.project_id}.{self.dataset}.{self.table}`,
                UNNEST(skills) as skill
                WHERE skill IS NOT NULL AND skill != ''
                ORDER BY skill
                LIMIT 100
            """
            results = self._execute_query(query)
            tech_stacks = [row['skill'] for row in results]
            cache.set(cache_key, tech_stacks, 3600)  # Cache for 1 hour
            return tech_stacks
        except:
            return []
    
    def get_companies_with_filters(self, filters: Dict[str, str], limit: int = 10000) -> List[Dict[str, Any]]:
        """Get companies list with filters based on company table tech_stack and skills_registry
        
        Filters companies using tech_stack field from companies table matched against skills_registry.
        """
        try:
            where_clauses = ["comp.company_id IS NOT NULL"]
            
            # Filter by keyword (search in company name)
            keyword = filters.get('keyword', '').strip()
            if keyword:
                where_clauses.append(f"LOWER(comp.company_name) LIKE '%{keyword.lower()}%'")
            
            # Filter by country
            country = filters.get('country', '').strip()
            if country:
                where_clauses.append(f"""
                    EXISTS(
                        SELECT 1 
                        FROM UNNEST(cj.countries) AS job_country
                        WHERE LOWER(job_country) = '{country.lower()}'
                    )
                """)
            
            # Filter by tech stack using company.tech_stack REPEATED field
            tech_stack = filters.get('tech_stack', '').strip()
            if tech_stack:
                # Handle special case for Vertex AI / Google AI Platform
                if tech_stack.lower() in ['vertex ai', 'vertexai', 'vertex_ai']:
                    # Match companies with Google AI related skills
                    where_clauses.append("""
                        EXISTS(
                            SELECT 1 
                            FROM UNNEST(comp.tech_stack) AS tech 
                            WHERE LOWER(tech) IN (
                                'vertex ai', 'vertexai', 'vertex_ai',
                                'google ai platform', 'google ai',
                                'gemini', 'palm', 'imagen',
                                'automl', 'dialogflow'
                            )
                        )
                    """)
                else:
                    # Simplified tech stack filtering - direct pattern matching on tech_stack array
                    techs = [t.strip() for t in tech_stack.split(',') if t.strip()]
                    if techs:
                        # Build conditions to match tech_stack directly
                        tech_conditions = []
                        for tech in techs:
                            tech_conditions.append(f"""
                                EXISTS(
                                    SELECT 1 
                                    FROM UNNEST(comp.tech_stack) AS company_tech
                                    WHERE LOWER(company_tech) LIKE '%{tech.lower()}%'
                                )
                            """)
                        where_clauses.append(f"({' OR '.join(tech_conditions)})")
            
            # Filter by status and relevance
            relevant_filter = filters.get('relevant', 'relevant')
            status_filter = filters.get('status', '').strip()
            
            if status_filter:
                # Specific status selected
                where_clauses.append(f"LOWER(comp.status) = '{status_filter.lower()}'")
            elif relevant_filter == 'to_review':
                # To Review: Undecided AND NOT IT consulting
                where_clauses.append("""
                    (comp.company_industry != 'IT Services and IT Consulting'
                    AND comp.company_type != 'Consulting (Technology)'
                    AND LOWER(comp.status) = 'undecided')
                """)
            elif relevant_filter == 'relevant':
                # Relevant: prospect, follow up, qualified, customer
                where_clauses.append("""
                    LOWER(comp.status) IN ('prospect', 'follow up', 'qualified', 'customer')
                """)
            
            where_sql = " AND ".join(where_clauses)
            
            # Sorting
            sort_by = filters.get('sort_by', 'job_count_desc')
            order_mapping = {
                'job_count_desc': 'job_count DESC',
                'job_count_asc': 'job_count ASC',
                'company_asc': 'comp.company_name ASC',
                'company_desc': 'comp.company_name DESC',
                'company_name': 'comp.company_name ASC',  # Default alphabetical
            }
            order_by = order_mapping.get(sort_by, 'comp.company_name ASC')
            
            # Min jobs filter
            min_jobs = int(filters.get('min_jobs', '1'))
            
            query = f"""
                WITH company_jobs AS (
                    SELECT 
                        company_id,
                        COUNT(*) as job_count,
                        MAX(scraped_at) as last_job_date,
                        ARRAY_AGG(DISTINCT location IGNORE NULLS ORDER BY location LIMIT 10) as locations,
                        ARRAY_AGG(DISTINCT country IGNORE NULLS) as countries,
                        ARRAY_AGG(DISTINCT source IGNORE NULLS) as sources
                    FROM `{self.project_id}.{self.dataset}.{self.table}`
                    WHERE company_id IS NOT NULL
                    GROUP BY company_id
                    HAVING job_count >= {min_jobs}
                )
                SELECT 
                    comp.company_name as company,
                    comp.company_id,
                    COALESCE(cj.job_count, 0) as job_count,
                    cj.last_job_date,
                    cj.locations,
                    cj.countries,
                    cj.sources,
                    comp.tech_stack as tech_stacks,
                    comp.status,
                    comp.solution_domain,
                    comp.company_type,
                    comp.company_size,
                    comp.description,
                    comp.company_industry
                FROM `{self.project_id}.{self.dataset}.{self.companies_table}` comp
                INNER JOIN company_jobs cj ON comp.company_id = cj.company_id
                WHERE {where_sql}
                ORDER BY {order_by}
                LIMIT {limit}
            """
            
            results = self._execute_query(query)
            
            # Process results to ensure arrays are properly formatted
            for result in results:
                if 'locations' in result and result['locations']:
                    result['locations'] = [loc for loc in result['locations'] if loc]
                else:
                    result['locations'] = []
                    
                if 'countries' in result and result['countries']:
                    result['countries'] = [c for c in result['countries'] if c]
                else:
                    result['countries'] = []
                    
                if 'sources' in result and result['sources']:
                    result['sources'] = [s for s in result['sources'] if s]
                else:
                    result['sources'] = []
                    
                if 'tech_stacks' in result and result['tech_stacks']:
                    result['tech_stacks'] = [t for t in result['tech_stacks'] if t]
                else:
                    result['tech_stacks'] = []
                
                # Set defaults for missing company metadata
                if not result.get('status'):
                    result['status'] = 'undecided'  # Default from companies table
                if not result.get('company_type'):
                    result['company_type'] = None
                if not result.get('company_size'):
                    result['company_size'] = None
                if not result.get('description'):
                    result['description'] = None
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get companies: {str(e)}")
            return []
    
    def get_company_filter_options(self) -> Dict[str, List[str]]:
        """Get unique filter options for companies page from skills_registry"""
        try:
            # Get unique countries from jobs
            countries_query = f"""
                SELECT DISTINCT country
                FROM `{self.project_id}.{self.dataset}.{self.table}`
                WHERE country IS NOT NULL AND country != ''
                ORDER BY country
            """
            countries_result = self._execute_query(countries_query)
            countries = [row['country'] for row in countries_result if 'country' in row]
            
            # Get tech stacks from skills_registry (active skills only)
            tech_query = f"""
                SELECT skill_name, category, vendor
                FROM `{self.project_id}.{self.dataset}.{self.skills_registry_table}`
                WHERE is_active = TRUE
                ORDER BY category, skill_name
            """
            tech_result = self._execute_query(tech_query)
            tech_stacks = [row['skill_name'] for row in tech_result if 'skill_name' in row]
            
            return {
                'countries': countries,
                'tech_stacks': tech_stacks
            }
            
        except Exception as e:
            logger.error(f"Failed to get filter options: {str(e)}")
            return {'countries': [], 'tech_stacks': []}
    
    def get_top_locations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top locations by job count"""
        try:
            query = f"""
                SELECT 
                    location,
                    country,
                    COUNT(*) as job_count
                FROM `{self.project_id}.{self.dataset}.{self.table}`
                WHERE location IS NOT NULL AND location != ''
                GROUP BY location, country
                ORDER BY job_count DESC
                LIMIT {limit}
            """
            return self._execute_query(query)
        except:
            return []
    
    def update_company_status(self, company: str, status: str) -> bool:
        """Update company status (would need a companies table)"""
        # This would require a separate companies table in BigQuery
        # For now, return True as placeholder
        logger.info(f"Update company status: {company} -> {status}")
        return True
    
    def get_company_details(self, company: str) -> Dict[str, Any]:
        """Get detailed information about a company from BigQuery (jobs + company metadata)"""
        try:
            # First get company metadata from companies table
            company_query = f"""
                SELECT 
                    company_id,
                    company_name,
                    normalized_name,
                    status,
                    company_type,
                    description,
                    solution_domain,
                    company_size,
                    enrichment_status,
                    ai_confidence,
                    enriched_at
                FROM `{self.project_id}.{self.dataset}.{self.companies_table}`
                WHERE LOWER(company_name) = LOWER(@company) 
                   OR LOWER(normalized_name) = LOWER(@company)
                LIMIT 1
            """
            
            # Then get job aggregations
            jobs_query = f"""
                SELECT 
                    company,
                    company_name,
                    COUNT(DISTINCT job_id) as job_count,
                    ARRAY_AGG(DISTINCT location IGNORE NULLS ORDER BY location LIMIT 10) as locations,
                    ARRAY_AGG(DISTINCT country IGNORE NULLS ORDER BY country LIMIT 5) as countries,
                    ARRAY_AGG(DISTINCT source IGNORE NULLS ORDER BY source LIMIT 10) as sources,
                    ARRAY_AGG(DISTINCT skill IGNORE NULLS ORDER BY skill LIMIT 30) as skills,
                    MAX(posted_date) as latest_job_date,
                    MIN(posted_date) as earliest_job_date,
                    MAX(scraped_at) as last_scraped_at
                FROM `{self.project_id}.{self.dataset}.{self.table}`,
                UNNEST(skills) as skill
                WHERE LOWER(company) = LOWER(@company) 
                   OR LOWER(company_name) = LOWER(@company)
                GROUP BY company, company_name
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("company", "STRING", company)
                ]
            )
            
            # Get company metadata
            company_results = list(self.client.query(company_query, job_config=job_config).result())
            company_data = {}
            if company_results:
                row = company_results[0]
                company_data = {
                    'company_id': row.company_id,
                    'company_name': row.company_name,
                    'normalized_name': row.normalized_name,
                    'status': row.status,
                    'company_type': row.company_type,
                    'description': row.description,
                    'solution_domain': row.solution_domain,
                    'company_size': row.company_size,
                    'enrichment_status': row.enrichment_status,
                    'ai_confidence': row.ai_confidence,
                    'enriched_at': row.enriched_at.isoformat() if row.enriched_at else None
                }
            
            # Get job aggregations
            job_results = list(self.client.query(jobs_query, job_config=job_config).result())
            if job_results:
                row = job_results[0]
                company_data.update({
                    'company': row.company,
                    'job_count': row.job_count,
                    'locations': list(row.locations) if row.locations else [],
                    'countries': list(row.countries) if row.countries else [],
                    'sources': list(row.sources) if row.sources else [],
                    'skills': list(row.skills) if row.skills else [],
                    'latest_job_date': row.latest_job_date if row.latest_job_date else None,
                    'earliest_job_date': row.earliest_job_date if row.earliest_job_date else None,
                    'last_scraped_at': row.last_scraped_at.isoformat() if row.last_scraped_at else None
                })
            
            return company_data
            
        except Exception as e:
            logger.error(f"Failed to get company details: {str(e)}", exc_info=True)
            return {}
    
    # ===== SKILLS REGISTRY METHODS =====
    
    def get_skills_registry(self) -> List[Dict[str, Any]]:
        """Get all skills from skills_registry table"""
        try:
            query = f"""
                SELECT 
                    skill_id,
                    skill_name,
                    skill_keywords,
                    category,
                    vendor,
                    is_primary,
                    is_active,
                    added_date,
                    added_by
                FROM `{self.project_id}.{self.dataset}.{self.skills_registry_table}`
                ORDER BY category, skill_name
            """
            return self._execute_query(query)
        except Exception as e:
            logger.error(f"Failed to get skills registry: {str(e)}", exc_info=True)
            return []
    
    def add_skill(self, skill_data: Dict[str, Any]) -> bool:
        """Add new skill to skills_registry"""
        try:
            # Check if skill already exists
            check_query = f"""
                SELECT skill_id 
                FROM `{self.project_id}.{self.dataset}.{self.skills_registry_table}`
                WHERE skill_id = @skill_id
            """
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("skill_id", "STRING", skill_data['skill_id'])
                ]
            )
            results = list(self.client.query(check_query, job_config=job_config).result())
            
            if results:
                logger.warning(f"Skill {skill_data['skill_id']} already exists")
                return False
            
            # Insert new skill
            table_id = f"{self.project_id}.{self.dataset}.{self.skills_registry_table}"
            table = self.client.get_table(table_id)
            
            rows_to_insert = [{
                'skill_id': skill_data['skill_id'],
                'skill_name': skill_data['skill_name'],
                'skill_keywords': skill_data.get('skill_keywords', []),
                'category': skill_data.get('category'),
                'vendor': skill_data.get('vendor'),
                'is_primary': skill_data.get('is_primary', True),
                'is_active': skill_data.get('is_active', True),
                'added_by': skill_data.get('added_by', 'manual')
            }]
            
            errors = self.client.insert_rows_json(table, rows_to_insert)
            
            if errors:
                logger.error(f"Failed to insert skill: {errors}")
                return False
            
            logger.info(f"Successfully added skill: {skill_data['skill_id']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add skill: {str(e)}", exc_info=True)
            return False
    
    def update_skill(self, skill_data: Dict[str, Any]) -> bool:
        """Update existing skill in skills_registry"""
        try:
            # Build UPDATE query
            update_query = f"""
                UPDATE `{self.project_id}.{self.dataset}.{self.skills_registry_table}`
                SET 
                    skill_name = @skill_name,
                    skill_keywords = @skill_keywords,
                    category = @category,
                    vendor = @vendor,
                    is_primary = @is_primary,
                    is_active = @is_active
                WHERE skill_id = @skill_id
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("skill_id", "STRING", skill_data['skill_id']),
                    bigquery.ScalarQueryParameter("skill_name", "STRING", skill_data['skill_name']),
                    bigquery.ArrayQueryParameter("skill_keywords", "STRING", skill_data.get('skill_keywords', [])),
                    bigquery.ScalarQueryParameter("category", "STRING", skill_data.get('category')),
                    bigquery.ScalarQueryParameter("vendor", "STRING", skill_data.get('vendor')),
                    bigquery.ScalarQueryParameter("is_primary", "BOOL", skill_data.get('is_primary', True)),
                    bigquery.ScalarQueryParameter("is_active", "BOOL", skill_data.get('is_active', True))
                ]
            )
            
            query_job = self.client.query(update_query, job_config=job_config)
            query_job.result()  # Wait for completion
            
            logger.info(f"Successfully updated skill: {skill_data['skill_id']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update skill: {str(e)}", exc_info=True)
            return False
    
    def toggle_skill_active(self, skill_id: str, is_active: bool) -> bool:
        """Toggle skill active status"""
        try:
            query = f"""
                UPDATE `{self.project_id}.{self.dataset}.{self.skills_registry_table}`
                SET is_active = @is_active
                WHERE skill_id = @skill_id
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("skill_id", "STRING", skill_id),
                    bigquery.ScalarQueryParameter("is_active", "BOOL", is_active)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            query_job.result()
            
            logger.info(f"Toggled skill {skill_id} active status to {is_active}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to toggle skill status: {str(e)}", exc_info=True)
            return False
    
    def delete_skill(self, skill_id: str) -> bool:
        """Delete skill from skills_registry"""
        try:
            query = f"""
                DELETE FROM `{self.project_id}.{self.dataset}.{self.skills_registry_table}`
                WHERE skill_id = @skill_id
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("skill_id", "STRING", skill_id)
                ]
            )
            
            query_job = self.client.query(query, job_config=job_config)
            query_job.result()
            
            logger.info(f"Deleted skill: {skill_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete skill: {str(e)}", exc_info=True)
            return False
    
    # ===== SCRAPING CONFIGURATION METHODS =====
    
    def get_all_configurations(self) -> List[Dict[str, Any]]:
        """Get all scraping configurations from scraping_config table"""
        try:
            query = f"""
                SELECT 
                    is_active,
                    updated_at,
                    updated_by,
                    search_queries,
                    search_countries,
                    enabled_modules,
                    daily_max_per_module,
                    exhaustive_max_per_module,
                    enable_bigquery,
                    enable_filtering,
                    notes
                FROM `{self.project_id}.{self.dataset}.scraping_config`
                ORDER BY updated_at DESC
            """
            results = self._execute_query(query)
            
            # Format results to ensure arrays are properly serializable
            for result in results:
                result['search_queries'] = list(result.get('search_queries', []))
                result['search_countries'] = list(result.get('search_countries', []))
                result['enabled_modules'] = list(result.get('enabled_modules', []))
                if result.get('updated_at'):
                    result['updated_at'] = result['updated_at'].isoformat() if hasattr(result['updated_at'], 'isoformat') else str(result['updated_at'])
            
            return results
        except Exception as e:
            logger.error(f"Failed to get configurations: {str(e)}", exc_info=True)
            return []
    
    def add_configuration(self, config_data: Dict[str, Any]) -> bool:
        """Add new configuration using load job (not streaming) to allow immediate updates"""
        try:
            table_id = f"{self.project_id}.{self.dataset}.scraping_config"
            
            row_data = {
                'is_active': config_data.get('is_active', False),
                'updated_at': datetime.utcnow().isoformat(),
                'updated_by': config_data.get('updated_by', 'admin'),
                'search_queries': config_data.get('search_queries', []),
                'search_countries': config_data.get('search_countries', []),
                'enabled_modules': config_data.get('enabled_modules', []),
                'daily_max_per_module': config_data.get('daily_max_per_module', 100),
                'exhaustive_max_per_module': config_data.get('exhaustive_max_per_module', 500),
                'enable_bigquery': config_data.get('enable_bigquery', True),
                'enable_filtering': config_data.get('enable_filtering', True),
                'notes': config_data.get('notes', '')
            }
            
            # Use INSERT query instead of streaming API - allows immediate UPDATE/DELETE
            insert_query = f"""
                INSERT INTO `{table_id}` (
                    is_active, updated_at, updated_by, search_queries, search_countries,
                    enabled_modules, daily_max_per_module, exhaustive_max_per_module,
                    enable_bigquery, enable_filtering, notes
                ) VALUES (
                    @is_active, @updated_at, @updated_by, @search_queries, @search_countries,
                    @enabled_modules, @daily_max_per_module, @exhaustive_max_per_module,
                    @enable_bigquery, @enable_filtering, @notes
                )
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("is_active", "BOOL", row_data['is_active']),
                    bigquery.ScalarQueryParameter("updated_at", "TIMESTAMP", row_data['updated_at']),
                    bigquery.ScalarQueryParameter("updated_by", "STRING", row_data['updated_by']),
                    bigquery.ArrayQueryParameter("search_queries", "STRING", row_data['search_queries'] or []),
                    bigquery.ArrayQueryParameter("search_countries", "STRING", row_data['search_countries'] or []),
                    bigquery.ArrayQueryParameter("enabled_modules", "STRING", row_data['enabled_modules'] or []),
                    bigquery.ScalarQueryParameter("daily_max_per_module", "INT64", row_data['daily_max_per_module']),
                    bigquery.ScalarQueryParameter("exhaustive_max_per_module", "INT64", row_data['exhaustive_max_per_module']),
                    bigquery.ScalarQueryParameter("enable_bigquery", "BOOL", row_data['enable_bigquery']),
                    bigquery.ScalarQueryParameter("enable_filtering", "BOOL", row_data['enable_filtering']),
                    bigquery.ScalarQueryParameter("notes", "STRING", row_data['notes'])
                ]
            )
            
            query_job = self.client.query(insert_query, job_config=job_config)
            query_job.result()  # Wait for completion
            
            logger.info("Successfully added configuration via query (not streaming)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add configuration: {str(e)}", exc_info=True)
            return False
    
    def update_configuration_by_timestamp(self, old_timestamp: str, config_data: Dict[str, Any]) -> bool:
        """Update configuration in-place using UPDATE query (works if not in streaming buffer)"""
        try:
            if not old_timestamp:
                raise ValueError("Original timestamp is required for updates")

            # Direct UPDATE query - no streaming buffer restrictions
            update_query = f"""
                UPDATE `{self.project_id}.{self.dataset}.scraping_config`
                SET
                    search_queries = @search_queries,
                    search_countries = @search_countries,
                    enabled_modules = @enabled_modules,
                    daily_max_per_module = @daily_max_per_module,
                    exhaustive_max_per_module = @exhaustive_max_per_module,
                    enable_bigquery = @enable_bigquery,
                    enable_filtering = @enable_filtering,
                    notes = @notes,
                    is_active = @is_active,
                    updated_by = @updated_by,
                    updated_at = CURRENT_TIMESTAMP()
                WHERE updated_at = @old_timestamp
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("old_timestamp", "TIMESTAMP", old_timestamp),
                    bigquery.ArrayQueryParameter("search_queries", "STRING", config_data.get('search_queries', []) or []),
                    bigquery.ArrayQueryParameter("search_countries", "STRING", config_data.get('search_countries', []) or []),
                    bigquery.ArrayQueryParameter("enabled_modules", "STRING", config_data.get('enabled_modules', []) or []),
                    bigquery.ScalarQueryParameter("daily_max_per_module", "INT64", int(config_data.get('daily_max_per_module', 100))),
                    bigquery.ScalarQueryParameter("exhaustive_max_per_module", "INT64", int(config_data.get('exhaustive_max_per_module', 500))),
                    bigquery.ScalarQueryParameter("enable_bigquery", "BOOL", bool(config_data.get('enable_bigquery', True))),
                    bigquery.ScalarQueryParameter("enable_filtering", "BOOL", bool(config_data.get('enable_filtering', True))),
                    bigquery.ScalarQueryParameter("notes", "STRING", config_data.get('notes', '')),
                    bigquery.ScalarQueryParameter("is_active", "BOOL", bool(config_data.get('is_active', False))),
                    bigquery.ScalarQueryParameter("updated_by", "STRING", config_data.get('updated_by', 'admin'))
                ]
            )
            
            query_job = self.client.query(update_query, job_config=job_config)
            query_job.result()
            
            logger.info(f"Successfully updated configuration at {old_timestamp}")
            return True

        except Exception as e:
            logger.error(f"Failed to update configuration: {str(e)}", exc_info=True)
            return False
    
    def activate_configuration(self, config_timestamp: str, config_data: Dict[str, Any], updated_by: str = 'admin') -> bool:
        """Activate configuration by deleting and reinserting with is_active=True"""
        try:
            if not config_timestamp:
                raise ValueError("Configuration timestamp is required to activate")

            # Delete the specific config
            delete_query = f"""
                DELETE FROM `{self.project_id}.{self.dataset}.scraping_config`
                WHERE updated_at = @config_timestamp
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("config_timestamp", "TIMESTAMP", config_timestamp)
                ]
            )

            self.client.query(delete_query, job_config=job_config).result()

            # Reinsert as active
            config_data['is_active'] = True
            config_data['updated_by'] = updated_by
            config_data['updated_at'] = datetime.utcnow().isoformat()
            return self.add_configuration(config_data)

        except Exception as e:
            logger.error(f"Failed to activate configuration: {str(e)}", exc_info=True)
            return False
    
    def deactivate_configuration(self, config_timestamp: str, config_data: Dict[str, Any], updated_by: str = 'admin') -> bool:
        """Deactivate configuration by deleting and reinserting with is_active=False"""
        try:
            if not config_timestamp:
                raise ValueError("Configuration timestamp is required to deactivate")

            # Delete old
            delete_query = f"""
                DELETE FROM `{self.project_id}.{self.dataset}.scraping_config`
                WHERE updated_at = @config_timestamp
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("config_timestamp", "TIMESTAMP", config_timestamp)
                ]
            )

            self.client.query(delete_query, job_config=job_config).result()

            # Reinsert as inactive
            config_data['is_active'] = False
            config_data['updated_by'] = updated_by
            config_data['updated_at'] = datetime.utcnow().isoformat()
            return self.add_configuration(config_data)

        except Exception as e:
            logger.error(f"Failed to deactivate configuration: {str(e)}", exc_info=True)
            return False
    
    def delete_configuration(self, config_timestamp: str) -> bool:
        """Delete a configuration from scraping_config table by timestamp"""
        try:
            if not config_timestamp:
                raise ValueError("Configuration timestamp is required to delete")

            delete_query = f"""
                DELETE FROM `{self.project_id}.{self.dataset}.scraping_config`
                WHERE updated_at = @config_timestamp
            """

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("config_timestamp", "TIMESTAMP", config_timestamp)
                ]
            )

            self.client.query(delete_query, job_config=job_config).result()
            logger.info(f"Deleted configuration at {config_timestamp}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete configuration: {str(e)}", exc_info=True)
            return False


# Singleton instance
_bigquery_service = None

def get_bigquery_service() -> BigQueryService:
    """Get or create BigQueryService singleton"""
    global _bigquery_service
    if _bigquery_service is None:
        _bigquery_service = BigQueryService()
    return _bigquery_service
