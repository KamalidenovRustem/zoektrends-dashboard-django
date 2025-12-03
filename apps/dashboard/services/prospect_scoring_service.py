"""
Prospect Scoring Service for Agiliz
Intelligent scoring algorithm to identify best-fit companies for partnerships
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class ProspectScoringService:
    """
    Score companies based on Agiliz partnership fit
    
    Scoring Criteria:
    - Tech Stack Alignment (GCP, BigQuery, Looker, MicroStrategy)
    - Company Type (prefer Technology, avoid Consulting)
    - Industry Fit (Data-intensive industries)
    - Company Size (100-1000+ employees)
    - Job Volume (active hiring = budget + growth)
    - Recency (newly discovered companies)
    """
    
    def __init__(self):
        # Agiliz core tech stack
        self.core_tech = ['bigquery', 'looker', 'gcp', 'google cloud platform', 
                         'microstrategy', 'vertex ai', 'looker studio', 'lookml']
        
        # Secondary relevant tech
        self.secondary_tech = ['dataflow', 'dataproc', 'cloud storage', 'pubsub',
                              'cloud composer', 'cloud functions', 'cloud run']
        
        # Ideal company types (weighted) - Focus on companies that NEED our services
        self.company_type_weights = {
            'Retail': 10,              # Top priority - need data insights
            'Manufacturing': 10,       # Top priority - need data insights
            'Healthcare': 10,          # Top priority - need data insights
            'Finance': 9,              # High priority - data intensive
            'Logistics': 8,            # High priority - optimization needs
            'Energy': 8,               # High priority - analytics needs
            'Education': 7,            # Good fit - growing data needs
            'Government': 6,           # Moderate fit
            'Hospitality': 5,          # Some potential
            'Technology': -10,         # AVOID - they build their own
            'Consulting (Technology)': -10,  # AVOID - competitors
            'Consulting (Business)': -10,    # AVOID - competitors
            'Other': 2
        }
        
        # Ideal industries - Companies that NEED data services
        self.high_value_industries = [
            'Retail', 'E-commerce', 'Manufacturing', 'Healthcare', 
            'Biotechnology Research', 'Pharmaceutical Manufacturing',
            'Financial Services', 'Banking', 'Insurance',
            'Transportation', 'Logistics', 'Supply Chain',
            'Energy', 'Utilities', 'Oil and Gas',
            'Hospitality', 'Food and Beverage', 'Consumer Goods'
        ]
        
        # Industries to avoid - Tech companies and competitors
        self.avoid_industries = [
            'Software Development', 'IT Services and IT Consulting',
            'Information Services and Technology', 'Information and Internet',
            'Technology', 'Computer Software', 'Internet',
            'Business Consulting and Services', 'Professional Services',
            'Staffing and Recruiting', 'Management Consulting'
        ]
    
    def calculate_prospect_score(self, company: Dict[str, Any], job_count: int = 0) -> Dict[str, Any]:
        """
        Calculate comprehensive prospect score for a company
        
        Returns:
            {
                'total_score': int (0-100),
                'category': str ('Hot Prospect', 'Warm Lead', 'Cold Lead', 'Avoid'),
                'breakdown': {
                    'tech_score': int,
                    'company_type_score': int,
                    'industry_score': int,
                    'size_score': int,
                    'activity_score': int,
                    'recency_score': int
                },
                'reasoning': str
            }
        """
        try:
            breakdown = {}
            reasoning_parts = []
            
            # 1. Tech Stack Score (0-30 points)
            # Use tech_stacks (plural) as that's what BigQuery returns
            tech_stack = company.get('tech_stacks', company.get('tech_stack', []))
            tech_score = self._score_tech_stack(tech_stack)
            breakdown['tech_score'] = tech_score
            if tech_score >= 20:
                reasoning_parts.append(f"Strong tech alignment ({tech_score}/30)")
            elif tech_score >= 10:
                reasoning_parts.append(f"Moderate tech alignment ({tech_score}/30)")
            
            # 2. Company Type Score (0-20 points)
            company_type_score = self._score_company_type(company.get('company_type', ''))
            breakdown['company_type_score'] = company_type_score
            if company_type_score < 0:
                reasoning_parts.append(f"Consulting firm - likely competitor")
            elif company_type_score >= 8:
                reasoning_parts.append(f"Ideal company type: {company.get('company_type')}")
            
            # 3. Industry Score (0-15 points)
            industry_score = self._score_industry(company.get('company_industry', ''))
            breakdown['industry_score'] = industry_score
            
            # 4. Company Size Score (0-15 points)
            size_score = self._score_company_size(company.get('company_size', ''))
            breakdown['size_score'] = size_score
            if size_score >= 12:
                reasoning_parts.append(f"Enterprise size: {company.get('company_size')}")
            
            # 5. Activity Score (Job Volume) (0-15 points)
            activity_score = self._score_activity(job_count)
            breakdown['activity_score'] = activity_score
            if activity_score >= 10:
                reasoning_parts.append(f"Active hiring ({job_count} jobs) indicates growth")
            
            # 6. Recency Score (0-5 points)
            recency_score = self._score_recency(company.get('created_at'))
            breakdown['recency_score'] = recency_score
            if recency_score >= 4:
                reasoning_parts.append("Newly discovered company")
            
            # Calculate total score
            total_score = max(0, min(100, 
                tech_score + company_type_score + industry_score + 
                size_score + activity_score + recency_score
            ))
            
            # Categorize
            if total_score >= 70 and company_type_score >= 0:
                category = 'Hot Prospect'
                emoji = '🔥'
            elif total_score >= 50 and company_type_score >= 0:
                category = 'Warm Lead'
                emoji = '⭐'
            elif total_score >= 30:
                category = 'Cold Lead'
                emoji = '❄️'
            else:
                category = 'Avoid'
                emoji = '🚫'
            
            reasoning = f"{emoji} {category}: " + "; ".join(reasoning_parts) if reasoning_parts else f"{emoji} {category}"
            
            return {
                'total_score': total_score,
                'category': category,
                'emoji': emoji,
                'breakdown': breakdown,
                'reasoning': reasoning
            }
            
        except Exception as e:
            logger.error(f"Error calculating prospect score: {str(e)}")
            return {
                'total_score': 0,
                'category': 'Unknown',
                'emoji': '❓',
                'breakdown': {},
                'reasoning': 'Error calculating score'
            }
    
    def _score_tech_stack(self, tech_stack: List[str]) -> int:
        """Score based on tech stack alignment (0-30 points)
        
        Scoring: 6 points per matching technology
        - 1 tech = 6 points
        - 2 techs = 12 points
        - 3+ techs = 18+ points (max 30)
        """
        if not tech_stack:
            return 0
        
        tech_stack_lower = [tech.lower() for tech in tech_stack]
        matched_techs = set()
        
        # Check for core tech matches (6 points each)
        for tech in self.core_tech:
            if any(tech in stack_item for stack_item in tech_stack_lower):
                matched_techs.add(tech)
        
        # Check for secondary tech matches (6 points each)
        for tech in self.secondary_tech:
            if any(tech in stack_item for stack_item in tech_stack_lower):
                matched_techs.add(tech)
        
        # Calculate score: 6 points per unique matched technology
        score = len(matched_techs) * 6
        
        return min(30, score)
    
    def _score_company_type(self, company_type: str) -> int:
        """Score based on company type (0-20 points, can be negative)"""
        if not company_type:
            return 5  # Neutral
        
        # Direct match
        weight = self.company_type_weights.get(company_type, 2)
        
        # Convert to 0-20 scale (or negative for consulting)
        if weight >= 8:
            return 20
        elif weight >= 6:
            return 15
        elif weight >= 4:
            return 10
        elif weight >= 2:
            return 5
        else:
            return weight  # Negative for business consulting
    
    def _score_industry(self, industry: str) -> int:
        """Score based on industry (0-15 points)"""
        if not industry:
            return 5
        
        # Avoid industries
        if any(avoid.lower() in industry.lower() for avoid in self.avoid_industries):
            return 0
        
        # High-value industries
        if any(valuable.lower() in industry.lower() for valuable in self.high_value_industries):
            return 15
        
        return 8  # Neutral
    
    def _score_company_size(self, company_size: str) -> int:
        """Score based on company size (0-15 points)"""
        if not company_size:
            return 5
        
        size_lower = company_size.lower()
        
        if '1000+' in size_lower or '500-1000' in size_lower:
            return 15  # Enterprise - best budget
        elif '100-500' in size_lower or '200-500' in size_lower:
            return 12  # Mid-market - good fit
        elif '50-100' in size_lower or '50-200' in size_lower:
            return 8   # Growing company
        elif '10-50' in size_lower:
            return 5   # Small but potential
        else:
            return 3   # Very small
    
    def _score_activity(self, job_count: int) -> int:
        """Score based on job posting volume (0-15 points)
        
        IDEAL: 3-20 jobs indicates growth company that needs help
        AVOID: 50+ jobs indicates tech giant that builds internally
        """
        if job_count >= 50:
            return -10  # Tech giant, likely Google/Microsoft - avoid
        elif job_count >= 20:
            return 5   # Too large/enterprise, lower priority
        elif job_count >= 10:
            return 15  # IDEAL - active hiring, manageable size
        elif job_count >= 5:
            return 15  # IDEAL - growing, needs support
        elif job_count >= 3:
            return 12  # Good - some growth
        elif job_count >= 1:
            return 6
        else:
            return 0
    
    def _score_recency(self, created_at: Optional[str]) -> int:
        """Score based on when company was discovered (0-5 points)"""
        if not created_at:
            return 0
        
        try:
            if isinstance(created_at, str):
                # Parse timestamp
                created_date = datetime.fromisoformat(created_at.replace(' UTC', '').replace('Z', ''))
            else:
                created_date = created_at
            
            days_ago = (datetime.utcnow() - created_date).days
            
            if days_ago <= 7:
                return 5  # New this week
            elif days_ago <= 30:
                return 3  # New this month
            elif days_ago <= 90:
                return 1  # Last quarter
            else:
                return 0  # Old
        except Exception as e:
            logger.warning(f"Error parsing created_at: {str(e)}")
            return 0
    
    def score_companies_batch(self, companies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Score multiple companies and sort by score"""
        scored_companies = []
        
        for company in companies:
            score_data = self.calculate_prospect_score(
                company, 
                company.get('job_count', 0)
            )
            
            scored_company = {
                **company,
                'prospect_score': score_data['total_score'],
                'prospect_category': score_data['category'],
                'prospect_emoji': score_data['emoji'],
                'score_breakdown': score_data['breakdown'],
                'score_reasoning': score_data['reasoning']
            }
            scored_companies.append(scored_company)
        
        # Sort by score (descending)
        scored_companies.sort(key=lambda x: x['prospect_score'], reverse=True)
        
        return scored_companies
    
    def get_top_prospects(self, companies: List[Dict[str, Any]], 
                         limit: int = 5, 
                         min_score: int = 50) -> List[Dict[str, Any]]:
        """Get top N prospects above minimum score threshold"""
        scored = self.score_companies_batch(companies)
        
        # Filter by minimum score and avoid consulting firms
        filtered = [c for c in scored if c['prospect_score'] >= min_score 
                   and c.get('company_type') != 'Consulting (Business)']
        
        return filtered[:limit]
    
    def find_tech_specific_prospects(self, companies: List[Dict[str, Any]], 
                                    tech_keyword: str, 
                                    limit: int = 5) -> List[Dict[str, Any]]:
        """Find prospects with specific technology focus"""
        tech_lower = tech_keyword.lower()
        
        # Filter companies with the specific tech
        tech_companies = [c for c in companies 
                         if any(tech_lower in str(t).lower() 
                               for t in c.get('tech_stack', []))]
        
        # Score and return top matches
        return self.get_top_prospects(tech_companies, limit=limit, min_score=40)


# Singleton instance
_prospect_scoring_service = None

def get_prospect_scoring_service() -> ProspectScoringService:
    """Get or create ProspectScoringService singleton"""
    global _prospect_scoring_service
    if _prospect_scoring_service is None:
        _prospect_scoring_service = ProspectScoringService()
        logger.info("Prospect Scoring Service initialized")
    return _prospect_scoring_service
