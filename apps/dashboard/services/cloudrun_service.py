"""
Cloud Run Job Service
Handles triggering Google Cloud Run Jobs
Ported from Laravel CloudRunJobService.php
"""
import logging
from typing import Dict, Any
from google.cloud import run_v2
from google.oauth2 import service_account
from django.conf import settings
import os

logger = logging.getLogger(__name__)


class CloudRunJobService:
    """Service for triggering Google Cloud Run Jobs"""
    
    def __init__(self):
        self.project = settings.GOOGLE_CLOUD['PROJECT_ID']
        self.region = settings.GOOGLE_CLOUD['REGION']
        self.credentials_path = settings.GOOGLE_CLOUD['CREDENTIALS_PATH']
        
        # Initialize Cloud Run Jobs client
        self.client = self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Cloud Run Jobs client"""
        try:
            if not self.credentials_path or not os.path.exists(self.credentials_path):
                logger.error(f"Credentials file not found: {self.credentials_path}")
                return None
            
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path
            )
            
            client = run_v2.JobsClient(credentials=credentials)
            logger.info("Cloud Run Jobs client initialized successfully")
            return client
            
        except Exception as e:
            logger.error(f"Failed to initialize Cloud Run Jobs client: {str(e)}")
            return None
    
    def trigger_job(self, job_name: str, overrides: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Trigger a Cloud Run Job execution
        
        Args:
            job_name: Name of the job to trigger
            overrides: Optional environment variable overrides
        
        Returns:
            Response with execution details
        """
        try:
            if not self.client:
                raise Exception("Cloud Run Jobs client not initialized")
            
            # Build job path
            job_path = f"projects/{self.project}/locations/{self.region}/jobs/{job_name}"
            
            # Create run request
            request = run_v2.RunJobRequest(name=job_path)
            
            # Log environment overrides (not directly supported in execution)
            if overrides:
                logger.info(f"Environment overrides requested: {overrides}")
                logger.warning("Environment overrides not directly supported in Cloud Run Job execution")
            
            # Execute the job
            operation = self.client.run_job(request=request)
            
            # Wait for operation to complete
            result = operation.result()
            
            logger.info(f"Cloud Run Job triggered successfully: {job_name}")
            logger.info(f"Execution: {result.name}")
            
            return {
                'success': True,
                'job': job_name,
                'execution': result.name,
                'status': 'triggered'
            }
            
        except Exception as e:
            logger.error(f"Failed to trigger Cloud Run Job: {job_name} - {str(e)}")
            return {
                'success': False,
                'job': job_name,
                'error': str(e)
            }
    
    def trigger_daily_scraper(self) -> Dict[str, Any]:
        """Trigger daily scraper job"""
        return self.trigger_job('zoektrends-daily')
    
    def trigger_exhaustive_scraper(self) -> Dict[str, Any]:
        """Trigger exhaustive scraper job"""
        return self.trigger_job('zoektrends-exhaustive')


# Singleton instance
_cloudrun_service = None

def get_cloudrun_service() -> CloudRunJobService:
    """Get or create CloudRunJobService singleton"""
    global _cloudrun_service
    if _cloudrun_service is None:
        _cloudrun_service = CloudRunJobService()
    return _cloudrun_service
