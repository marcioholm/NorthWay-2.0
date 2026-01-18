from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from models import db, Client, Contract, ContractTemplate, Transaction, Task, WhatsAppMessage
from utils import create_notification, get_contract_replacements
from datetime import datetime, date, timedelta
import json
import uuid
import markdown

contracts_bp = Blueprint('contracts', __name__)

@contracts_bp.route('/clients/<int:id>/contracts/new')
@login_required
def new_contract(id):
    if not current_user.company_id:
        abort(403)

    client = Client.query.get_or_404(id)
    if client.company_id != current_user.company_id:
        return "Unauthorized", 403
        
    from models import template_company_association
    templates = ContractTemplate.query.outerjoin(template_company_association)\
        .filter(
            db.or_(
                ContractTemplate.company_id == current_user.company_id,
                ContractTemplate.is_global == True,
                template_company_association.c.company_id == current_user.company_id
            ),
            ContractTemplate.active == True,
            ContractTemplate.type == 'contract'
        ).all()
    
    attachments = ContractTemplate.query.outerjoin(template_company_association)\
        .filter(
            db.or_(
                ContractTemplate.company_id == current_user.company_id,
                ContractTemplate.is_global == True,
                template_company_association.c.company_id == current_user.company_id
            ),
            ContractTemplate.active == True,
            ContractTemplate.type == 'attachment'
        ).all()
    
    return render_template('contracts/new_contract.html', client=client, templates=templates, attachments=attachments)

@contracts_bp.route('/api/contracts/preview', methods=['POST'])
@login_required
def preview_contract():
    if not current_user.company_id:
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.json
    client_id = data.get('client_id')
    template_id = data.get('template_id')
    attachment_id = data.get('attachment_id')
    form_data = data.get('form_data', {})
    
    client = Client.query.get_or_404(client_id)
    template = ContractTemplate.query.get_or_404(template_id)
    
    if client.company_id != current_user.company_id:
        return jsonify({'error': 'Unauthorized'}), 403

    replacements = get_contract_replacements(client, form_data)
    
    content = template.content
    for key, value in replacements.items():
        content = content.replace(key, str(value))
    
    try:
        content = markdown.markdown(content)
    except Exception as e:
        print(f"Markdown Error: {e}")
    
    if attachment_id:
        attachment = ContractTemplate.query.get(attachment_id)
        if attachment and attachment.company_id == client.company_id:
            att_content = attachment.content
            for key, value in replacements.items():
                att_content = att_content.replace(key, str(value))
            try:
                att_content = markdown.markdown(att_content)
                content += f"<br><hr><br><div class='attachment-section'>{att_content}</div>"
            except:
                pass

    # Branding
    logo_html = ""
    if client.company.logo_filename:
        logo_url = url_for('static', filename='uploads/company/' + client.company.logo_filename)
        logo_html = f'<img src="{logo_url}" alt="Logo" class="h-16 object-contain">'

    header_html = f"""
    <div class="mb-8 border-b-2 pb-4" style="border-color: {client.company.primary_color or '#fa0102'}">
        <div class="flex items-center justify-between">
            <div>
                <h2 class="text-2xl font-bold" style="color: {client.company.secondary_color or '#111827'}">{client.company.name}</h2>
                <p class="text-sm text-gray-500">CNPJ: {client.company.document or ''}</p>
            </div>
            {logo_html}
        </div>
        <p class="text-xs text-gray-400 mt-2">Pré-visualização gerada em {datetime.now().strftime('%d/%m/%Y')}</p>
    </div>
    """
    return jsonify({'content': header_html + content})

@contracts_bp.route('/clients/<int:id>/contracts', methods=['POST'])
@login_required
def create_contract(id):
    if not current_user.company_id:
        abort(403)

    client = Client.query.get_or_404(id)
    if client.company_id != current_user.company_id:
        abort(403)
    
    try:
        action = request.form.get('action', 'issue')
        template_id = request.form.get('template_id')
        contract_id = request.form.get('contract_id')
        template = ContractTemplate.query.get_or_404(template_id)
        form_data = request.form.to_dict()
        
        replacements = get_contract_replacements(client, form_data)
        
        # Sync Client Data
        if form_data.get('sync_client') == 'on':
            client.name = form_data.get('contratante_nome') or client.name
            client.document = form_data.get('contratante_documento') or client.document
            client.representative = form_data.get('contratante_representante') or client.representative
            client.representative_cpf = form_data.get('contratante_cpf') or client.representative_cpf
            client.email_contact = form_data.get('contratante_email') or client.email_contact
            
            val_p = form_data.get('valor_parcela')
            if val_p:
                try:
                    client.monthly_value = float(val_p.replace('R$', '').replace('.', '').replace(',', '.').strip())
                except: pass
        
        # Generate Content
        generated_content = template.content
        for key, value in replacements.items():
            generated_content = generated_content.replace(key, str(value))
        
        generated_content = markdown.markdown(generated_content)

        # Branded Header
        if current_user.company.logo_filename:
             logo_url = url_for('static', filename='uploads/company/' + current_user.company.logo_filename, _external=True)
             header_html = f"""
                 <div style="text-align:center; margin-bottom: 40px; border-bottom: 2px solid {current_user.company.primary_color or '#fa0102'}; padding-bottom: 20px;">
                     <h2 style="color: {current_user.company.secondary_color or '#111827'}; margin: 0; text-transform: uppercase;">{current_user.company.name}</h2>
                     <p style="color: #666; font-size: 12px; margin: 5px 0;">CNPJ: {current_user.company.document}</p>
                     <img src="{logo_url}" style="max-height: 60px; margin-top: 10px;">
                 </div>
             """
             generated_content = header_html + generated_content

        status = 'issued' if action == 'issue' else 'draft'
        
        if contract_id:
            contract = Contract.query.get(contract_id)
            if contract and contract.company_id == current_user.company_id:
                contract.template_id = template.id
                contract.generated_content = generated_content
                contract.form_data = json.dumps(form_data)
                contract.status = status
                if not contract.code:
                    contract.code = f"CTR-{datetime.now().year}-{uuid.uuid4().hex[:8].upper()}"
            else:
                 contract = Contract(
                    client_id=client.id, company_id=client.company.id, template_id=template.id,
                    generated_content=generated_content, form_data=json.dumps(form_data),
                    status=status, code=f"CTR-{datetime.now().year}-{uuid.uuid4().hex[:8].upper()}"
                )
                 db.session.add(contract)
        else: 
            contract = Contract(
                client_id=client.id, company_id=client.company.id, template_id=template.id,
                generated_content=generated_content, form_data=json.dumps(form_data),
                status=status, code=f"CTR-{datetime.now().year}-{uuid.uuid4().hex[:8].upper()}"
            )
            db.session.add(contract)
        
        db.session.commit()
    
        if status == 'issued':
            create_notification(current_user.id, client.company_id, 'client_status_changed', f"Contrato emitido para {client.name}", f"Contrato #{contract.id} gerado.")
            task = Task(
                title="Enviar contrato para assinatura",
                description=f"Contrato #{contract.id} emitido. Enviar para assinatura do cliente.",
                due_date=datetime.now(), priority='urgente', status='pendente',
                company_id=current_user.company_id, client_id=client.id, assigned_to_id=current_user.id
            )
            db.session.add(task)
            db.session.commit()
            flash('Contrato emitido e tarefa de assinatura criada!', 'success')
        else:
            flash('Rascunho salvo!', 'info')

        return redirect(url_for('clients.client_details', id=client.id))
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao emitir contrato: {str(e)}", 'error')
        return redirect(url_for('clients.client_details', id=id))

@contracts_bp.route('/contracts/<int:id>/terminate', methods=['POST'])
@login_required
def terminate_contract(id):
    if not current_user.company_id:
        return jsonify({'error': 'Unauthorized'}), 403

    contract = Contract.query.get_or_404(id)
    if contract.company_id != current_user.company_id:
        abort(403)
    
    try:
        data = request.json
        reason = data.get('reason')
        penalty = float(data.get('penalty', 0))
        due_date_str = data.get('due_date')
    
        contract.status = 'cancelled'
        contract.cancellation_reason = reason
        contract.canceled_at = datetime.now()
    
        # Cancel Pending/Overdue
        targets = Transaction.query.filter(
            Transaction.contract_id == contract.id, 
            Transaction.status.in_(['pending', 'overdue'])
        ).all()
    
        from services.asaas_service import AsaasService
        for tx in targets:
            tx.status = 'cancelled'
            if tx.asaas_id:
                try: AsaasService.cancel_payment(contract.company_id, tx.asaas_id)
                except: pass
    
        db.session.commit()
    
        if penalty > 0:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else date.today()
            fee_tx = Transaction(
                contract_id=contract.id, company_id=contract.company_id, client_id=contract.client_id,
                description=f"Multa Rescisória - Contrato #{contract.id}", amount=penalty,
                due_date=due_date, status='pending'
            )
            db.session.add(fee_tx)
            db.session.commit()
            try:
                cust_id = AsaasService.create_customer(contract.company_id, contract.client)
                AsaasService.create_payment(contract.company_id, cust_id, fee_tx)
                db.session.commit()
            except: pass
    
        return jsonify({'message': 'Contrato encerrado com sucesso.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Erro: {str(e)}'}), 500

@contracts_bp.route('/contracts/<int:id>/sign', methods=['POST'])
@login_required
def sign_contract(id):
    if not current_user.company_id:
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        def add_months_helper(sourcedate, months):
            month = sourcedate.month - 1 + months
            year = sourcedate.year + month // 12
            month = month % 12 + 1
            day = min(sourcedate.day, [31, 29 if year % 4 == 0 and not year % 100 == 0 or year % 400 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month-1])
            return date(year, month, day)

        contract = Contract.query.get_or_404(id)
        if contract.company_id != current_user.company_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = json.loads(contract.form_data)
        val_p = float(data.get('valor_parcela', '0').replace('.', '').replace(',', '.'))
        qtd_p = int(data.get('qtd_parcelas', '12'))
        venc = int(data.get('dia_vencimento', '5'))
        start_d = datetime.strptime(data.get('data_inicio'), '%d/%m/%Y').date()
    
        if Transaction.query.filter_by(contract_id=contract.id).count() == 0:
            for i in range(qtd_p):
                target_m = add_months_helper(start_d, i)
                try: due_d = date(target_m.year, target_m.month, venc)
                except ValueError: due_d = date(target_m.year, target_m.month, 28)
            
                t = Transaction(
                    contract_id=contract.id, client_id=contract.client_id, company_id=contract.company_id,
                    description=f"Parcela {i+1}/{qtd_p}", amount=val_p, due_date=due_d, status='pending'
                )
                db.session.add(t)
        
        contract.signed_at = datetime.now()
        contract.status = 'active'
        db.session.commit()
        return jsonify({'message': 'Contrato assinado e parcelas geradas.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Erro: {str(e)}'}), 500

@contracts_bp.route('/contracts/<int:id>')
@login_required
def view_contract(id):
    if not current_user.company_id:
        abort(403)

    contract = Contract.query.get_or_404(id)
    if contract.company_id != current_user.company_id:
        abort(403)
    return render_template('contracts/view_contract.html', contract=contract)
