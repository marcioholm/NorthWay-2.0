from flask import Blueprint, jsonify, current_app
from models import db, TenantIntegration, Client, DriveFileEvent, Lead, Task, Notification
from services.google_drive_service import GoogleDriveService
from datetime import datetime, timedelta
from utils import create_notification, get_now_br

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

@jobs_bp.route('/api/cron/task-reminders', methods=['GET', 'POST'])
def task_reminders_job():
    """
    Cron job to send notifications for upcoming and overdue tasks.
    Should be called every ~15-30 minutes.
    """
    now = get_now_br()
    results = {'upcoming_alerts': 0, 'overdue_alerts': 0, 'errors': []}
    
    # 1. Upcoming Tasks (Due in next 45 min, not yet reminded)
    upcoming_limit = now + timedelta(minutes=45)
    upcoming_tasks = Task.query.filter(
        Task.status == 'pendente',
        Task.due_date <= upcoming_limit,
        Task.due_date > now,
        Task.reminder_sent == False
    ).all()
    
    for task in upcoming_tasks:
        try:
            create_notification(
                user_id=task.assigned_to_id,
                company_id=task.company_id,
                type='task_reminder',
                title=f"Tarefa em breve: {task.title}",
                message=f"Sua tarefa para o lead {task.lead.name if task.lead else '---'} vence em breve ({task.due_date.strftime('%H:%M')})."
            )
            task.reminder_sent = True
            results['upcoming_alerts'] += 1
        except Exception as e:
            results['errors'].append(f"Error reminding task {task.id}: {str(e)}")

    # 2. Overdue Tasks (Due in the past, not yet reminded as overdue)
    overdue_tasks = Task.query.filter(
        Task.status == 'pendente',
        Task.due_date < now,
        Task.overdue_reminder_sent == False
    ).all()
    
    for task in overdue_tasks:
        try:
            create_notification(
                user_id=task.assigned_to_id,
                company_id=task.company_id,
                type='task_overdue',
                title=f"TAREFA ATRASADA: {task.title}",
                message=f"Atenção! A tarefa para {task.lead.name if task.lead else '---'} está atrasada desde {task.due_date.strftime('%d/%m %H:%M')}."
            )
            task.overdue_reminder_sent = True
            results['overdue_alerts'] += 1
        except Exception as e:
            results['errors'].append(f"Error overdue alert for task {task.id}: {str(e)}")
            
    db.session.commit()
    return jsonify(results)

@jobs_bp.route('/api/cron/prospecting-scheduler', methods=['GET', 'POST'])
def prospecting_scheduler_job():
    """
    Cron job to trigger automated prospecting campaigns.
    Should be called regularly (e.g. every 10-15 minutes or hourly) by an external cron.
    """
    import requests
    from models import ProspectingCampaign, ProspectingSetting, User, Lead
    
    now = get_now_br()
    results = {
        'triggered_campaigns': [],
        'notifications_sent': 0,
        'errors': []
    }
    
    # 1. Obter todas as campanhas ativas
    active_campaigns = ProspectingCampaign.query.filter_by(status='ativa', is_active=True).all()
    
    for campaign in active_campaigns:
        try:
            # Obter configurações de prospecção da empresa
            setting = ProspectingSetting.query.filter_by(company_id=campaign.company_id).first()
            if not setting:
                continue
                
            start_time_str = setting.sending_start_time or '09:00'
            
            # Verificar se o horário atual é posterior ou igual ao horário de início
            try:
                start_hour, start_minute = map(int, start_time_str.split(':'))
            except Exception:
                start_hour, start_minute = 9, 0
                
            # Somente disparar se a hora atual do Brasil for maior ou igual ao início agendado
            if now.hour < start_hour or (now.hour == start_hour and now.minute < start_minute):
                continue
                
            # Verificar se a campanha já disparou a notificação de início hoje
            today_start = datetime(now.year, now.month, now.day, 0, 0, 0)
            today_end = datetime(now.year, now.month, now.day, 23, 59, 59)
            
            already_notified = Notification.query.filter(
                Notification.company_id == campaign.company_id,
                Notification.type == 'campaign_start',
                Notification.message.like(f"%{campaign.name}%"),
                Notification.created_at >= today_start,
                Notification.created_at <= today_end
            ).first()
            
            if already_notified:
                continue
                
            # Verificar se há leads pendentes na campanha (status 'novo')
            pending_leads_count = Lead.query.filter_by(
                prospecting_campaign_id=campaign.id,
                company_id=campaign.company_id,
                prospecting_status='novo'
            ).count()
            
            if pending_leads_count == 0:
                continue
                
            # Enviar notificação de início para todos os usuários da empresa
            users = User.query.filter_by(company_id=campaign.company_id).all()
            for user in users:
                create_notification(
                    user_id=user.id,
                    company_id=campaign.company_id,
                    type='campaign_start',
                    title=f"Campanha '{campaign.name}' Iniciada",
                    message=f"A prospecção automática para a campanha '{campaign.name}' foi iniciada às {start_time_str}. {pending_leads_count} leads pendentes na fila."
                )
                results['notifications_sent'] += 1
                
            # Chamar webhook externo (n8n/NORA) se configurado
            if setting.generate_message_webhook_url:
                payload = {
                    'action': 'start_campaign_batch',
                    'campaign_id': campaign.id,
                    'company_id': campaign.company_id,
                    'company_name': campaign.company.name,
                    'limit': setting.daily_send_limit or 50
                }
                try:
                    requests.post(setting.generate_message_webhook_url, json=payload, timeout=5)
                except Exception as req_e:
                    print(f"Erro ao chamar webhook do n8n para campanha {campaign.id}: {req_e}")
                    
            results['triggered_campaigns'].append({
                'campaign_id': campaign.id,
                'name': campaign.name,
                'pending_leads': pending_leads_count
            })
            
        except Exception as e:
            results['errors'].append(f"Erro ao agendar campanha {campaign.id}: {str(e)}")
            
    db.session.commit()
    return jsonify(results)
