"""
Looker Embed Service
Generates signed SSO embed URLs for Looker dashboards
Ported from Laravel LookerEmbedService.php
"""
import time
import hashlib
import hmac
import base64
import secrets
import json
from urllib.parse import urlencode, quote
from typing import Dict, List, Optional
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class LookerEmbedService:
    """Service for generating Looker embed URLs with SSO"""
    
    def __init__(self):
        self.looker_host = settings.LOOKER['HOST']
        self.embed_secret = settings.LOOKER['EMBED_SECRET']
        self.embed_user = settings.LOOKER['EMBED_USER']
    
    def generate_dashboard_embed_url(
        self,
        dashboard_id: str,
        filters: Optional[Dict[str, str]] = None,
        permissions: Optional[List[str]] = None
    ) -> str:
        """
        Generate a signed SSO embed URL for a Looker dashboard
        
        Args:
            dashboard_id: The Looker dashboard ID
            filters: Optional filters to apply to the dashboard
            permissions: Optional user permissions
        
        Returns:
            Signed embed URL
        """
        try:
            # Build the embed path
            embed_path = f"/login/embed/{quote(f'/embed/dashboards/{dashboard_id}')}"
            
            # Generate nonce (random string to prevent replay attacks)
            nonce = secrets.token_hex(16)
            
            # Current timestamp
            timestamp = str(int(time.time()))
            
            # Build embed user details
            embed_user_data = {
                'external_user_id': self.embed_user,
                'first_name': 'ZoekTrends',
                'last_name': 'User',
                'session_length': 3600,  # 1 hour session
                'force_logout_login': True,
                'permissions': permissions or [
                    'access_data',
                    'see_looks',
                    'see_user_dashboards',
                    'explore',
                    'create_table_calculations',
                    'download_with_limit',
                    'download_without_limit',
                    'see_drill_overlay',
                    'save_content',
                    'embed_browse_spaces',
                    'schedule_look_emails',
                    'schedule_external_look_emails',
                    'send_outgoing_webhook',
                    'send_to_s3',
                    'send_to_sftp'
                ],
                'models': ['zoektrends'],  # Your Looker model name
                'group_ids': [],
                'external_group_id': 'zoektrends_users',
                'user_attributes': {},
                'access_filters': {}
            }
            
            # Add filters if provided
            if filters:
                filter_params = []
                for field, value in filters.items():
                    filter_params.append(f"{quote(field)}={quote(value)}")
                embed_path += '?' + '&'.join(filter_params)
            
            # Create the string to sign
            # Note: Using empty session_id as we're not using PHP sessions
            session_id = ''
            string_to_sign = "\n".join([
                self.looker_host,
                embed_path,
                nonce,
                timestamp,
                session_id,
                json.dumps(embed_user_data, separators=(',', ':'))
            ])
            
            # Generate signature using HMAC SHA256
            signature = base64.b64encode(
                hmac.new(
                    self.embed_secret.encode('utf-8'),
                    string_to_sign.encode('utf-8'),
                    hashlib.sha256
                ).digest()
            ).decode('utf-8')
            
            # Build the final URL with all parameters
            params = {
                'nonce': nonce,
                'time': timestamp,
                'session_length': embed_user_data['session_length'],
                'external_user_id': embed_user_data['external_user_id'],
                'permissions': json.dumps(embed_user_data['permissions']),
                'models': json.dumps(embed_user_data['models']),
                'access_filters': json.dumps(embed_user_data['access_filters']),
                'first_name': embed_user_data['first_name'],
                'last_name': embed_user_data['last_name'],
                'group_ids': json.dumps(embed_user_data['group_ids']),
                'external_group_id': embed_user_data['external_group_id'],
                'user_attributes': json.dumps(embed_user_data['user_attributes']),
                'force_logout_login': 'true' if embed_user_data['force_logout_login'] else 'false',
                'signature': signature
            }
            
            # Build final URL
            embed_url = f"https://{self.looker_host}{embed_path}"
            if '?' in embed_url:
                embed_url += '&' + urlencode(params)
            else:
                embed_url += '?' + urlencode(params)
            
            logger.info(f"Generated Looker embed URL for dashboard: {dashboard_id}")
            return embed_url
            
        except Exception as e:
            logger.error(f"Failed to generate Looker embed URL: {str(e)}")
            raise
    
    def get_default_dashboard_url(self) -> str:
        """Get the default dashboard embed URL"""
        dashboard_id = settings.LOOKER.get('DEFAULT_DASHBOARD_ID', '')
        if not dashboard_id:
            raise ValueError("No default dashboard ID configured")
        
        return self.generate_dashboard_embed_url(dashboard_id)


# Singleton instance
_looker_service = None

def get_looker_service() -> LookerEmbedService:
    """Get or create LookerEmbedService singleton"""
    global _looker_service
    if _looker_service is None:
        _looker_service = LookerEmbedService()
    return _looker_service
