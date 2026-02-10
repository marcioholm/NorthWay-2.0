
import os
import json
import logging
from datetime import datetime, timedelta
import google.oauth2.credentials
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from flask import url_for, current_app

from models import db, TenantIntegration

# Configure logging
logger = logging.getLogger(__name__)

class GoogleDriveService:
    SCOPES = ['https://www.googleapis.com/auth/drive.file']
    
    def __init__(self, company_id=None):
        self.company_id = company_id
        self.client_id = os.environ.get('GOOGLE_CLIENT_ID')
        self.client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
        # We need absolute URL for callback depending on environment
        # But flow usually takes the redirect_uri handling
        # For Vercel, this must be set in Env Vars or derived
        self.redirect_uri = os.environ.get('GOOGLE_REDIRECT_URI', 'http://localhost:5000/api/integrations/google-drive/callback')

    def get_auth_url(self):
        """Generates the authorization URL for the user."""
        if not self.client_id or not self.client_secret:
            raise ValueError("Google Client ID/Secret not configured")

        flow = google_auth_oauthlib.flow.Flow.from_client_config(
            self._get_client_config(),
            scopes=self.SCOPES
        )
        flow.redirect_uri = self.redirect_uri
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent' # Force consent to get refresh token
        )
        return authorization_url, state

    def fetch_token(self, code):
        """Exchanges the authorization code for tokens."""
        flow = google_auth_oauthlib.flow.Flow.from_client_config(
            self._get_client_config(),
            scopes=self.SCOPES
        )
        flow.redirect_uri = self.redirect_uri
        
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        return {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes,
            'expiry': credentials.expiry.isoformat() if credentials.expiry else None
        }

    def get_drive_service(self, tenant_integration):
        """Builds and returns the Drive API service for a given tenant."""
        if not tenant_integration or not tenant_integration.refresh_token_encrypted:
            raise ValueError("Integration not connected or missing refresh token")

        # In a real app, decrypt refresh_token_encrypted here
        # For this MVP, we assume text storage as per models.py comment or simple base64
        # Assuming plain text for now as per plan/speed, but labeled 'encrypted' for future
        refresh_token = tenant_integration.refresh_token_encrypted 

        creds_data = {
            'token': tenant_integration.access_token,
            'refresh_token': refresh_token,
            'token_uri': 'https://oauth2.googleapis.com/token',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'scopes': self.SCOPES
        }
        
        credentials = google.oauth2.credentials.Credentials.from_authorized_user_info(creds_data)
        
        # Auto-refresh if expired
        if credentials.expired:
            try:
                request = google.auth.transport.requests.Request()
                credentials.refresh(request)
                
                # Update DB with new access token
                tenant_integration.access_token = credentials.token
                tenant_integration.token_expiry_at = credentials.expiry
                db.session.commit()
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                tenant_integration.status = 'error'
                tenant_integration.last_error = f"Token Refresh Failed: {str(e)}"
                db.session.commit()
                raise e

        service = build('drive', 'v3', credentials=credentials)
        return service

    def create_folder(self, tenant_integration, folder_name, parent_id=None):
        """Creates a folder in Drive."""
        service = self.get_drive_service(tenant_integration)
        
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        if parent_id:
            file_metadata['parents'] = [parent_id]
            
        file = service.files().create(body=file_metadata, fields='id, webViewLink').execute()
        return file

    def list_files(self, tenant_integration, folder_id):
        """Lists files in a specific folder."""
        service = self.get_drive_service(tenant_integration)
        
        # Query: Inside folder, not trashed
        query = f"'{folder_id}' in parents and crashed = false" 
        # Fix typo: crashed -> trashed
        query = f"'{folder_id}' in parents and trashed = false"

        results = service.files().list(
            q=query,
            pageSize=50,
            fields="nextPageToken, files(id, name, mimeType, webViewLink, createdTime, modifiedTime)"
        ).execute()
        
        return results.get('files', [])

    def _get_client_config(self):
        return {
            "web": {
                "client_id": self.client_id,
                "project_id": "northway-crm", # generic
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_secret": self.client_secret,
                "redirect_uris": [self.redirect_uri]
            }
        }

    def create_folder_structure(self, tenant_integration, parent_id, structure_json):
        """
        Recursively creates folders based on a JSON structure.
        structure_json: List of dicts [{'name': '...', 'children': [...]}]
        """
        if isinstance(structure_json, str):
            try:
                structure = json.loads(structure_json)
            except:
                logger.error(f"Invalid JSON structure: {structure_json}")
                return
        else:
            structure = structure_json

        for item in structure:
            folder_name = item.get('name')
            if not folder_name: continue
            
            # Create the folder
            try:
                folder = self.create_folder(tenant_integration, folder_name, parent_id=parent_id)
                folder_id = folder.get('id')
                
                # Recursively create children
                children = item.get('children', [])
                if children and folder_id:
                    self.create_folder_structure(tenant_integration, folder_id, children)
            except Exception as e:
                logger.error(f"Failed to create folder {folder_name}: {e}")

    @staticmethod
    def parse_structure_text(text):
        """
        Parses indentation-based text into a JSON-compatible list structure.
        Example:
        Folder A
            Subfolder 1
        Folder B
        """
        lines = text.split('\n')
        root = []
        stack = [{'level': -1, 'children': root}]
        
        for line in lines:
            stripped = line.lstrip()
            if not stripped: continue
            
            # Detect Indentation (assume 4 spaces or 1 tab = 1 level, or just relative diff)
            # Actually, let's just count leading spaces
            indent = len(line) - len(stripped)
            level = indent 
            
            name = stripped.strip()
            node = {'name': name, 'children': []}
            
            # Find parent
            while stack[-1]['level'] >= level:
                stack.pop()
            
            stack[-1]['children'].append(node)
            stack.append({'level': level, 'children': node['children']})
            
        return root
