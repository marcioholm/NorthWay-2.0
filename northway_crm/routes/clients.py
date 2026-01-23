from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Client, User, Interaction, Task, Transaction, LEAD_STATUS_WON, ProcessTemplate
from utils import update_client_health, create_notification
from datetime import datetime, date

clients_bp = Blueprint('clients', __name__)

@clients_bp.route('/clients')
@login_required
def clients():
    page = request.args.get('page', 1, type=int)
    per_page = 20
    query = Client.query.filter_by(company_id=current_user.company_id)
    
    # Filters
    status = request.args.get('status')
    manager_id = request.args.get('manager')
    renewal_start = request.args.get('renewal_start')
    renewal_end = request.args.get('renewal_end')
    
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
    
    return render_template('client_details.html', 
                          client=client, 
                          mrr=mrr, 
                          today=date.today(),
                          client_txs=client_txs,
                          total_paid=total_paid,
                          total_pending=total_pending,
                          total_overdue=total_overdue,
                          process_templates=process_templates,
                          users=users)

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
