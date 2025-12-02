#!/usr/bin/env python
"""
Columbus Chat Server Diagnostic Script
Run this on the server to identify issues with BigQuery, scoring, and data structure
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, '/home/rustem_kamalidenov/zoektrends-dashboard')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

def test_environment():
    """Test environment variables"""
    print("=" * 60)
    print("1. ENVIRONMENT VARIABLES")
    print("=" * 60)
    
    creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    print(f"GOOGLE_APPLICATION_CREDENTIALS: {creds_path}")
    
    if creds_path:
        exists = os.path.exists(creds_path)
        print(f"Credentials file exists: {exists}")
        if exists:
            print(f"File size: {os.path.getsize(creds_path)} bytes")
    else:
        print("❌ GOOGLE_APPLICATION_CREDENTIALS not set!")
    
    print(f"GOOGLE_CLOUD_PROJECT: {os.getenv('GOOGLE_CLOUD_PROJECT')}")
    print(f"GOOGLE_CLOUD_REGION: {os.getenv('GOOGLE_CLOUD_REGION')}")
    print(f"DEBUG: {os.getenv('DEBUG')}")
    print()

def test_bigquery():
    """Test BigQuery connection"""
    print("=" * 60)
    print("2. BIGQUERY CONNECTION")
    print("=" * 60)
    
    try:
        from apps.dashboard.services.bigquery_service import get_bigquery_service
        
        bq = get_bigquery_service()
        print("✅ BigQueryService initialized")
        
        # Test query
        print("\nTesting query: get_companies_with_filters(limit=5)...")
        companies = bq.get_companies_with_filters(
            filters={'relevant': 'to_review'}, 
            limit=5
        )
        
        print(f"✅ Found {len(companies)} companies")
        
        if companies:
            print("\nFirst company structure:")
            first = companies[0]
            print(f"  - company_name: {first.get('company_name', 'N/A')}")
            print(f"  - company_id: {first.get('company_id', 'N/A')}")
            print(f"  - job_count: {first.get('job_count', 'N/A')}")
            print(f"  - tech_stack: {first.get('tech_stack', [])[:3]}...")  # First 3 techs
            print(f"  - Keys: {list(first.keys())[:10]}...")  # First 10 keys
        else:
            print("❌ No companies returned - BigQuery might not have data")
        
        return companies
        
    except Exception as e:
        print(f"❌ BigQuery error: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def test_scoring(companies):
    """Test company scoring"""
    print("\n" + "=" * 60)
    print("3. COMPANY SCORING")
    print("=" * 60)
    
    if not companies:
        print("❌ No companies to score (BigQuery returned nothing)")
        return []
    
    try:
        from apps.dashboard.services.prospect_scoring_service import get_prospect_scoring_service
        
        scoring = get_prospect_scoring_service()
        print("✅ ProspectScoringService initialized")
        
        print(f"\nScoring {len(companies)} companies...")
        scored = scoring.score_companies_batch(companies)
        
        print(f"✅ Scored {len(scored)} companies")
        
        if scored:
            print("\nFirst scored company structure:")
            first = scored[0]
            print(f"  - company_name: {first.get('company_name', 'N/A')}")
            print(f"  - prospect_score: {first.get('prospect_score', 'N/A')}")
            print(f"  - prospect_category: {first.get('prospect_category', 'N/A')}")
            print(f"  - prospect_emoji: {first.get('prospect_emoji', 'N/A')}")
            
            # CHECK FOR SCORE_BREAKDOWN - THIS IS THE CRITICAL FIELD
            if 'score_breakdown' in first:
                print(f"  ✅ score_breakdown exists!")
                breakdown = first['score_breakdown']
                print(f"     - tech_score: {breakdown.get('tech_score', 'N/A')}/30")
                print(f"     - company_type_score: {breakdown.get('company_type_score', 'N/A')}/20")
                print(f"     - industry_score: {breakdown.get('industry_score', 'N/A')}/15")
                print(f"     - size_score: {breakdown.get('size_score', 'N/A')}/15")
                print(f"     - activity_score: {breakdown.get('activity_score', 'N/A')}/15")
                print(f"     - recency_score: {breakdown.get('recency_score', 'N/A')}/5")
            else:
                print(f"  ❌ score_breakdown MISSING! This is the frontend bug cause.")
            
            print(f"\n  Full keys in scored company: {list(first.keys())}")
        
        return scored
        
    except Exception as e:
        print(f"❌ Scoring error: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def test_columbus_chat(scored_companies):
    """Test Columbus Chat service"""
    print("\n" + "=" * 60)
    print("4. COLUMBUS CHAT SERVICE")
    print("=" * 60)
    
    if not scored_companies:
        print("❌ No scored companies to test (previous steps failed)")
        return
    
    try:
        from apps.dashboard.services.columbus_chat_service import get_columbus_chat
        
        chat = get_columbus_chat()
        print("✅ ColumbusChat service initialized")
        
        # Prepare context like views_columbus_chat.py does
        context = {
            'companies': scored_companies,
            'total_companies': len(scored_companies)
        }
        
        print(f"\nContext prepared with {len(scored_companies)} scored companies")
        
        # Test a simple query
        print("\nTesting query: 'Give me top 5 prospects'...")
        result = chat.chat("Give me top 5 prospects", context=context)
        
        print(f"✅ Chat response generated")
        print(f"  - Response length: {len(result.get('response', ''))} chars")
        print(f"  - Function calls: {result.get('function_calls', [])}")
        
        if 'data' in result and result['data']:
            data = result['data']
            if 'companies' in data:
                companies_returned = data['companies']
                print(f"  - Companies returned: {len(companies_returned)}")
                
                if companies_returned:
                    first = companies_returned[0]
                    print(f"\n  First company in response:")
                    print(f"    - company_name: {first.get('company_name', 'N/A')}")
                    print(f"    - prospect_score: {first.get('prospect_score', 'N/A')}")
                    
                    # CRITICAL CHECK
                    if 'score_breakdown' in first:
                        print(f"    ✅ score_breakdown present in response!")
                    else:
                        print(f"    ❌ score_breakdown MISSING in response!")
                        print(f"    Available keys: {list(first.keys())}")
        
    except Exception as e:
        print(f"❌ Columbus Chat error: {str(e)}")
        import traceback
        traceback.print_exc()

def main():
    """Run all diagnostics"""
    print("\n" + "=" * 60)
    print("COLUMBUS CHAT SERVER DIAGNOSTICS")
    print("=" * 60)
    print()
    
    # Step 1: Environment
    test_environment()
    
    # Step 2: BigQuery
    companies = test_bigquery()
    
    # Step 3: Scoring
    scored = test_scoring(companies)
    
    # Step 4: Columbus Chat
    test_columbus_chat(scored)
    
    print("\n" + "=" * 60)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 60)
    print("\nIf score_breakdown is missing from scored companies,")
    print("the issue is in prospect_scoring_service.py")
    print("\nIf score_breakdown exists but missing from chat response,")
    print("the issue is in columbus_chat_service.py")
    print()

if __name__ == '__main__':
    main()
