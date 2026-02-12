from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Client, User, Interaction, Task, Transaction, LEAD_STATUS_WON, ProcessTemplate, LibraryTemplate, FormInstance, TenantIntegration, DriveFolderTemplate
from utils import update_client_health, create_notification
from datetime import datetime, date
import csv
import io

clients_bp = Blueprint('clients', __name__)

@clients_bp.route('/clients')
@login_required
def clients():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    query = Client.query.filter_by(company_id=current_user.company_id)
    
    # Filters
    search_q = request.args.get('q')
    status = request.args.get('status')
    manager_id = request.args.get('manager')
    renewal_start = request.args.get('renewal_start')
    renewal_end = request.args.get('renewal_end')
    
    if search_q:
        search_term = f"%{search_q}%"
        query = query.filter(db.or_(
            Client.name.ilike(search_term),
            Client.email.ilike(search_term),
            Client.phone.ilike(search_term),
            Client.service.ilike(search_term)
        ))
    
    if status:
        query = query.filter_by(status=status)
        
    if manager_id:
        query = query.filter_by(account_manager_id=int(manager_id))
        
    if renewal_start:
        try:
            start_date = datetime.strptime(renewal_start, '%Y-%m-%d').date()
            query = query.filter(Client.renewal_date >= start_date)
        except ValueError:
            pass
        
    if renewal_end:
        try:
            end_date = datetime.strptime(renewal_end, '%Y-%m-%d').date()
            query = query.filter(Client.renewal_date <= end_date)
        except ValueError:
            pass
        
    # Eager load for performance
    pagination = query.options(
        db.joinedload(Client.account_manager),
        db.joinedload(Client.interactions)
    ).order_by(Client.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    clients_list = pagination.items
    
    # Auto-update health
    for client in clients_list:
        update_client_health(client)
    
    db.session.commit()
    
    users = User.query.filter_by(company_id=current_user.company_id).all()
    
    return render_template('clients.html', clients=clients_list, pagination=pagination, users=users, today=date.today())

@clients_bp.route('/clients/<int:id>', methods=['GET'])
@login_required
def client_details(id):
    client = Client.query.get_or_404(id)
    if client.company_id != current_user.company_id:
        return "Unauthorized", 403
        
    try:
        update_client_health(client)
        db.session.commit()
    except Exception as e:
        print(f"Error updating health for client {id}: {e}")
        db.session.rollback()

    # Get MRR
    mrr = client.monthly_value if client.monthly_value else 0.0
    
    # Financial Stats
    client_txs = Transaction.query.filter_by(client_id=client.id).order_by(Transaction.due_date.desc()).all()
    total_paid = sum(tx.amount for tx in client_txs if tx.status == 'paid')
    total_pending = sum(tx.amount for tx in client_txs if tx.status == 'pending')
    total_overdue = sum(tx.amount for tx in client_txs if tx.status == 'overdue')
    
    # Get Process Templates
    process_templates = ProcessTemplate.query.filter_by(company_id=current_user.company_id).all()
    
    # Get Users for Assignment
    users = User.query.filter_by(company_id=current_user.company_id).all()
    
    # Diagnostic Form Instance for Link Generation (Access Control)
    from models import LibraryTemplate, LibraryTemplateGrant, FormInstance
    diag_template = LibraryTemplate.query.filter_by(key="diagnostico_northway_v1").first()
    diag_instance = None
    if diag_template:
        has_grant = LibraryTemplateGrant.query.filter_by(
            user_id=current_user.id, 
            template_id=diag_template.id, 
            status="active"
        ).first()
        is_master = getattr(current_user, "is_super_admin", False) or current_user.email == "master@northway.com"
        if has_grant or is_master:
            diag_instance = FormInstance.query.filter_by(
                template_id=diag_template.id,
                owner_user_id=current_user.id
            ).first()

    # Fetch Drive Templates and Integration Status
    tenant_templates = DriveFolderTemplate.query.filter_by(company_id=current_user.company_id).all()
    
    # Global Templates
    allowed_ids = current_user.company.allowed_global_template_ids or []
    global_templates = DriveFolderTemplate.query.filter(
        DriveFolderTemplate.scope == 'global',
        DriveFolderTemplate.enabled == True,
        DriveFolderTemplate.id.in_(allowed_ids)
    ).all() if allowed_ids else []
    
    drive_templates = tenant_templates + global_templates
    
    drive_integration = TenantIntegration.query.filter_by(
        company_id=current_user.company_id, 
        provider='google_drive', 
        status='connected'
    ).first()
    is_drive_connected = bool(drive_integration)

    return render_template('client_details.html', 
                          client=client, 
                          mrr=mrr, 
                          today=date.today(),
                          client_txs=client_txs,
                          total_paid=total_paid,
                          total_pending=total_pending,
                          total_overdue=total_overdue,
                          process_templates=process_templates,
                          users=users,
                          diag_instance=diag_instance,
                          drive_templates=drive_templates,
                          is_drive_connected=is_drive_connected)

@clients_bp.route('/clients/<int:id>/update', methods=['POST'])
@login_required
def update_client(id):
    try:
        client = Client.query.get_or_404(id)
        if client.company_id != current_user.company_id:
             return "Unauthorized", 403
         
        # Basic fields
        if 'service' in request.form: client.service = request.form.get('service')
        if 'contract_type' in request.form: client.contract_type = request.form.get('contract_type')
        if 'niche' in request.form: client.niche = request.form.get('niche')

        # Registration Data
        for field in ['document', 'email_contact', 'representative', 'representative_cpf', 
                    'address_street', 'address_number', 'address_neighborhood', 
                    'address_city', 'address_state', 'address_zip']:
            if field in request.form:
                setattr(client, field, request.form.get(field))

        new_status = request.form.get('status')
        if new_status and new_status != client.status:
            client.status = new_status
            if client.account_manager_id and client.account_manager_id != current_user.id:
                 create_notification(
                     user_id=client.account_manager_id,
                     company_id=current_user.company_id,
                     type='client_status_changed',
                     title='Status do Cliente Alterado',
                     message=f"Status do cliente {client.name} alterado para {new_status} por {current_user.name}."
                 )

        if 'notes' in request.form: client.notes = request.form.get('notes')
        
        manager_id = request.form.get('account_manager_id')
        if manager_id:
            client.account_manager_id = int(manager_id)
        
        if 'monthly_value' in request.form:
            val = request.form.get('monthly_value')
            try:
                client.monthly_value = float(val) if val else 0.0
            except ValueError:
                pass
        
        if 'start_date' in request.form:
            start_date = request.form.get('start_date')
            if start_date:
                client.start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        
        if 'renewal_date' in request.form:
            renewal_date = request.form.get('renewal_date')
            if renewal_date:
                client.renewal_date = datetime.strptime(renewal_date, '%Y-%m-%d').date()
            else:
                client.renewal_date = None

        db.session.commit()
        flash('Dados do cliente atualizados!', 'success')
        return redirect(url_for('clients.client_details', id=client.id))

    except Exception as e:
        print(f'CRITICAL ERROR updating client: {e}')
        db.session.rollback()
        flash(f'Erro ao salvar: {str(e)}', 'error')
        return redirect(url_for('clients.client_details', id=id))

@clients_bp.route('/clients/<int:id>/delete', methods=['POST'])
@login_required
def delete_client(id):
    client = Client.query.get_or_404(id)
    if client.company_id != current_user.company_id:
        return "Unauthorized", 403
    
    db.session.delete(client)
    db.session.commit()
    flash('Cliente excluído com sucesso.', 'success')
    return redirect(url_for('clients.clients'))

@clients_bp.route('/clients/<int:id>/interactions', methods=['POST'])
@login_required
def add_client_interaction(id):
    client = Client.query.get_or_404(id)
    if client.company_id != current_user.company_id:
        return "Unauthorized", 403
    
    interaction = Interaction(
        client_id=client.id,
        user_id=current_user.id,
        company_id=current_user.company_id,
        type=request.form.get('type'),
        content=request.form.get('content'),
        created_at=datetime.now()
    )
    db.session.add(interaction)
    db.session.commit()
    flash('Interação registrada.', 'success')
    return redirect(url_for('clients.client_details', id=client.id))

@clients_bp.route('/clients/<int:id>/tasks', methods=['POST'])
@login_required
def add_client_task(id):
    client = Client.query.get_or_404(id)
    if client.company_id != current_user.company_id:
        return "Unauthorized", 403
    
    due_date_str = request.form.get('due_date')
    due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M') if due_date_str else None
    
    task = Task(
        title=request.form.get('title'),
        description=request.form.get('description'),
        due_date=due_date,
        priority=request.form.get('priority'),
        status='pendente',
        client_id=client.id,
        company_id=current_user.company_id,
        assigned_to_id=current_user.id
    )
    db.session.add(task)
    db.session.commit()
    flash('Tarefa adicionada.', 'success')
    return redirect(url_for('clients.client_details', id=client.id))

@clients_bp.route('/clients/create', methods=['POST'])
@login_required
def create_client():
    try:
        name = request.form.get('name')
        if not name:
            flash('Nome é obrigatório.', 'error')
            return redirect(url_for('clients.clients'))
            
        email = request.form.get('email')
        # Check for existing email if provided
        if email:
            existing = Client.query.filter_by(company_id=current_user.company_id, email=email).first()
            if existing:
                flash(f'Cliente já existe com este email: {existing.name}', 'error')
                return redirect(url_for('clients.clients'))

        # Prepare data
        monthly_value = 0.0
        try:
            val = request.form.get('monthly_value')
            if val: monthly_value = float(val)
        except:
            pass
            
        start_date = date.today()
        sd_str = request.form.get('start_date')
        if sd_str:
            try:
                start_date = datetime.strptime(sd_str, '%Y-%m-%d').date()
            except:
                pass

        new_client = Client(
            name=name,
            email=email,
            phone=request.form.get('phone'),
            company_id=current_user.company_id,
            account_manager_id=int(request.form.get('account_manager_id') or current_user.id),
            status=request.form.get('status', 'ativo'),
            service=request.form.get('service'),
            monthly_value=monthly_value,
            start_date=start_date,
            created_at=datetime.utcnow()
        )
        
        db.session.add(new_client)
        db.session.commit()
        
        flash(f'Cliente {name} criado com sucesso!', 'success')
        return redirect(url_for('clients.client_details', id=new_client.id))
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating client: {e}")
        flash(f'Erro ao criar cliente: {e}', 'error')
        return redirect(url_for('clients.clients'))

@clients_bp.route('/clients/import', methods=['POST'])
@login_required
def import_clients():
    if 'file' not in request.files:
        flash('Nenhum arquivo enviado.', 'error')
        return redirect(url_for('clients.clients'))
        
    file = request.files['file']
    if file.filename == '':
        flash('Nenhum arquivo selecionado.', 'error')
        return redirect(url_for('clients.clients'))
        
    if not file.filename.endswith('.csv'):
        flash('O arquivo deve ser um CSV.', 'error')
        return redirect(url_for('clients.clients'))

    try:
        stream = io.TextIOWrapper(file.stream._file, "utf-8", newline="")
        # Simple dialect sniffing or just assume standard
        csv_input = csv.DictReader(stream)
        
        # Normalize headers (remove BOM, strip spaces, lower case)
        # But DictReader uses the first line. Let's hope for standard format.
        # User instruction said: Name, Email, Phone...
        # Let's try to map common names.
        
        # We can't easily change headers of DictReader after init effectively without reading first.
        # Let's map dynamically per row.
        
        success_count = 0
        skipped_count = 0
        
        for row in csv_input:
            # Flexible key getting
            name = row.get('Nome') or row.get('name') or row.get('NOME')
            if not name: 
                continue # name required
                
            email = row.get('Email') or row.get('email') or row.get('EMAIL')
            phone = row.get('Telefone') or row.get('Phone') or row.get('phone') or row.get('TELEFONE')
            status_raw = row.get('Status') or row.get('status') or row.get('STATUS')
            value_raw = row.get('Valor') or row.get('Value') or row.get('valor') or row.get('VALOR')
            service = row.get('Servico') or row.get('Service') or row.get('servico') or row.get('SERVICO')
            start_date_raw = row.get('Data Inicio') or row.get('Start Date')
            
            # Check duplication
            if email:
                exists = Client.query.filter_by(company_id=current_user.company_id, email=email).first()
                if exists:
                    skipped_count += 1
                    continue
            
            # Status mapping
            status = 'ativo'
            if status_raw:
                s = status_raw.lower().strip()
                if 'cancel' in s: status = 'cancelado'
                elif 'inat' in s: status = 'cancelado'
                elif 'ex' in s: status = 'cancelado'
                elif 'encerr' in s: status = 'cancelado'
                elif 'paus' in s: status = 'pausado'
                elif 'board' in s: status = 'onboarding'
                elif 'ativ' in s: status = 'ativo'
            
            # Value parsing
            monthly_value = 0.0
            if value_raw:
                try:
                    # Clean currency symbols
                    v_str = str(value_raw).replace('R$', '').replace(' ', '').replace(',', '.')
                    monthly_value = float(v_str)
                except:
                    pass
            
            # Date parsing
            start_date = date.today()
            if start_date_raw:
                try:
                    # Try common formats
                    for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y']:
                        try:
                            start_date = datetime.strptime(start_date_raw, fmt).date()
                            break
                        except:
                            continue
                except:
                    pass

            new_client = Client(
                name=name,
                email=email,
                phone=phone,
                company_id=current_user.company_id,
                account_manager_id=current_user.id, # Default to uploader
                status=status,
                service=service,
                monthly_value=monthly_value,
                start_date=start_date,
                created_at=datetime.utcnow()
            )
            db.session.add(new_client)
            success_count += 1
            
        db.session.commit()
        
        msg_type = 'success' if success_count > 0 else 'warning'
        flash(f'Importação concluída: {success_count} importados, {skipped_count} pulados (email duplicado).', msg_type)
        return redirect(url_for('clients.clients'))


    except Exception as e:
        print(f"CSV Import Error: {e}")
        flash(f'Erro ao processar arquivo: {e}', 'error')
        return redirect(url_for('clients.clients'))

@clients_bp.route('/clients/<int:id>/create_drive_folder', methods=['POST'])
@login_required
def create_drive_folder(id):
    client = Client.query.get_or_404(id)
    if client.company_id != current_user.company_id:
        abort(403)

    drive_template_id = request.form.get('drive_template_id')
    
    try:
        from services.google_drive_service import GoogleDriveService
        drive_integration = TenantIntegration.query.filter_by(
            company_id=current_user.company_id, 
            provider='google_drive', 
            status='connected'
        ).first()

        if not drive_integration:
            flash('Integração com Google Drive não encontrada.', 'error')
            return redirect(url_for('clients.client_details', id=client.id))

        drive_service = GoogleDriveService(company_id=current_user.company_id)
        
        # 1. Ensure Main Folder Exists
        folder_id = client.drive_folder_id
        if not folder_id:
            root_id = drive_integration.root_folder_id
            folder_name = f"{client.name} - {client.id}"
            folder = drive_service.create_folder(drive_integration, folder_name, parent_id=root_id)
            if folder:
                client.drive_folder_id = folder.get('id')
                client.drive_folder_url = folder.get('webViewLink')
                client.drive_folder_name = folder_name
                folder_id = folder.get('id')
                db.session.commit()
                flash('Pasta do cliente criada com sucesso!', 'success')
            else:
                 flash('Falha ao criar pasta principal.', 'error')
                 return redirect(url_for('clients.client_details', id=client.id))
        else:
            # If folder already exists and no template selected, just notify
            if not drive_template_id:
                flash('Pasta já existe.', 'info')
        
        # 2. Create Structure from Template (Optional)
        if drive_template_id:
            template = DriveFolderTemplate.query.get(drive_template_id)
            
            # Validation: Tenant owns it OR it's allowed global
            is_valid = False
            if template:
                if template.company_id == current_user.company_id:
                    is_valid = True
                elif template.scope == 'global':
                    allowed_ids = current_user.company.allowed_global_template_ids or []
                    if template.id in allowed_ids:
                         is_valid = True
            
            if is_valid:
                drive_service.create_folder_structure(drive_integration, folder_id, template.structure_json)
                flash(f'Estrutura de pastas "{template.name}" criada com sucesso!', 'success')
            else:
                flash('Template inválido ou sem permissão.', 'error')

    except Exception as e:
        import traceback
        traceback.print_exc()
        flash(f'Erro ao criar pastas: {str(e)}', 'error')

    return redirect(url_for('clients.client_details', id=client.id))

@clients_bp.route('/clients/<int:id>/drive/scan', methods=['POST'])
@login_required
def scan_drive_folder(id):
    client = Client.query.get_or_404(id)
    if client.company_id != current_user.company_id:
        return jsonify({'error': 'Unauthorized'}), 403

    if not client.drive_folder_id:
        return jsonify({'error': 'Cliente sem pasta vinculada.'}), 400

    try:
        from services.google_drive_service import GoogleDriveService
        from models import DriveFileEvent
        
        drive_integration = TenantIntegration.query.filter_by(
            company_id=current_user.company_id, 
            provider='google_drive',
            status='connected'
        ).first()

        if not drive_integration:
            return jsonify({'error': 'Integração Google Drive não configurada.'}), 400

        service = GoogleDriveService(company_id=current_user.company_id)
        files = service.list_files(drive_integration, client.drive_folder_id)

        # Clear old events or update? 
        # Strategy: Delete strict duplicates or just append new?
        # For MVP: Clear and re-add to avoid dups, or check ID.
        # Let's check ID.
        
        existing_ids = {e.file_id for e in client.drive_files_events}
        new_count = 0
        
        for f in files:
            if f['id'] not in existing_ids:
                # Parse timestamp
                # 2023-10-27T10:00:00.000Z
                created_dt = None
                if f.get('createdTime'):
                    try:
                        created_dt = datetime.fromisoformat(f['createdTime'].replace('Z', '+00:00'))
                    except: pass
                
                event = DriveFileEvent(
                    company_id=current_user.company_id,
                    client_id=client.id,
                    file_id=f['id'],
                    file_name=f['name'],
                    mime_type=f['mimeType'],
                    web_view_link=f['webViewLink'],
                    created_time=created_dt
                )
                db.session.add(event)
                new_count += 1
        
        client.drive_last_scan_at = datetime.utcnow()
        client.drive_unread_files_count = new_count # Simple notification logic
        
        db.session.commit()
        
        return jsonify({'success': True, 'new_files': new_count})

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
