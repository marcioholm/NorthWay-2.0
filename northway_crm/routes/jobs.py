from flask import Blueprint, jsonify, current_app
from models import db, TenantIntegration, Client, DriveFileEvent, Lead
from services.google_drive_service import GoogleDriveService
from datetime import datetime, timedelta

jobs_bp = Blueprint('jobs_bp', __name__)

@jobs_bp.route('/api/cron/drive-sync', methods=['GET', 'POST'])
def drive_sync_job():
    """
    Cron job to sync Google Drive files for all connected tenants.
    Should be called every ~10-15 minutes by an external cron (e.g. Vercel Cron).
    """
    results = {
        'processed_tenants': 0,
        'processed_clients': 0,
        'new_files': 0,
        'errors': []
    }
    
    # 1. Get all connected Drive integrations
    integrations = TenantIntegration.query.filter_by(
        provider='google_drive', 
        status='connected'
    ).all()
    
    results['processed_tenants'] = len(integrations)
    
    for integration in integrations:
        try:
            # Initialize Service
            service = GoogleDriveService(company_id=integration.company_id)
            
            # Get Clients with Drive Folders
            clients = Client.query.filter(
                Client.company_id == integration.company_id,
                Client.drive_folder_id.isnot(None)
            ).all()
            
            results['processed_clients'] += len(clients)
            
            for client in clients:
                try:
                    # Sync Logic
                    # Only sync if not synced in last 5 minutes (debounce)
                    if client.drive_last_scan_at and (datetime.utcnow() - client.drive_last_scan_at).total_seconds() < 300:
                        continue
                        
                    drive_files = service.list_files(integration, client.drive_folder_id)
                    
                    new_files_count = 0
                    
                    for f in drive_files:
                        file_id = f.get('id')
                        # Check if event exists
                        exists = DriveFileEvent.query.filter_by(
                            company_id=integration.company_id,
                            file_id=file_id
                        ).first()
                        
                        modified_time = None
                        if f.get('modifiedTime'):
                            modified_time = datetime.fromisoformat(f['modifiedTime'].replace('Z', ''))

                        if not exists:
                            # New File Found
                            event = DriveFileEvent(
                                company_id=integration.company_id,
                                client_id=client.id,
                                file_id=file_id,
                                file_name=f.get('name'),
                                mime_type=f.get('mimeType'),
                                web_view_link=f.get('webViewLink'),
                                created_time=datetime.fromisoformat(f['createdTime'].replace('Z', '')) if f.get('createdTime') else None,
                                modified_time=modified_time
                            )
                            db.session.add(event)
                            new_files_count += 1
                        else:
                            # Update modification time if changed
                            if modified_time and exists.modified_time != modified_time:
                                exists.modified_time = modified_time
                                # Could trigger "updated" notification here
                    
                    if new_files_count > 0:
                        client.drive_unread_files_count = (client.drive_unread_files_count or 0) + new_files_count
                        results['new_files'] += new_files_count
                    
                    client.drive_last_scan_at = datetime.utcnow()
                    db.session.commit()
                    
                except Exception as client_e:
                    # Log but continue
                    client_error = f"Client {client.id} Sync Error: {str(client_e)}"
                    print(client_error)
                    results['errors'].append(client_error)
                    db.session.rollback()
            
            # Update Integration Last Sync
            integration.updated_at = datetime.utcnow() # Abuse updated_at for now or add last_sync_at (TenantIntegration has it?)
            # TenantIntegration schema I made has last_error but not last_sync_at explicitly? 
            # I think I added last_error. Let's start with updated_at.
            db.session.commit()

        except Exception as tenant_e:
            err_msg = f"Tenant {integration.company_id} Sync Error: {str(tenant_e)}"
            print(err_msg)
            integration.last_error = str(tenant_e)
            results['errors'].append(err_msg)
            db.session.commit()

    return jsonify(results)
