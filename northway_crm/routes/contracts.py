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

@contracts_bp.route('/contracts/autosave', methods=['POST'])
@login_required
def autosave_contract():
    try:
        data = request.json
        client_id = data.get('client_id')
        template_id = data.get('template_id')
        contract_id = data.get('contract_id')
        form_data = data.get('form_data')
        content = data.get('content')
        
        if not client_id or not template_id:
            return jsonify({'success': False, 'error': 'Missing data'}), 400

        # Find or Create Draft
        contract = None
        if contract_id:
            contract = Contract.query.get(contract_id)
        
        if not contract:
            # Create new draft
            contract = Contract(
                client_id=client_id,
                company_id=current_user.company_id,
                template_id=template_id,
                status='draft',
                form_data=json.dumps(form_data) if form_data else None,
                generated_content=content
            )
            db.session.add(contract)
        else:
            # Update existing draft
            contract.template_id = template_id
            contract.form_data = json.dumps(form_data) if form_data else contract.form_data
            contract.generated_content = content
            
        db.session.commit()
        return jsonify({'success': True, 'contract_id': contract.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@contracts_bp.route('/contracts/<int:contract_id>/resume')
@login_required
def load_draft(contract_id):
    if not current_user.company_id:
        abort(403)

    contract = Contract.query.get_or_404(contract_id)
    if contract.company_id != current_user.company_id:
        abort(403)
        
    client = contract.client
    
    # Load available templates for the select
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

    draft_data = json.loads(contract.form_data) if contract.form_data else {}
    
    return render_template('contracts/new_contract.html', 
                           client=client, 
                           templates=templates, 
                           attachments=attachments,
                           draft_data=draft_data,
                           contract_id=contract.id)

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

    # --- PREMIUM HEADER LOGIC ---
    logo_img_tag = ""
    if client.company.logo_base64:
        logo_img_tag = f'<img src="data:image/png;base64,{client.company.logo_base64}" alt="Logo" style="max-height: 80px; object-fit: contain;">'
    elif client.company.logo_filename:
        if client.company.logo_filename.startswith('http'):
            logo_url = client.company.logo_filename
        else:
            logo_url = url_for('static', filename='uploads/company/' + client.company.logo_filename)
        logo_img_tag = f'<img src="{logo_url}" alt="Logo" style="max-height: 80px; object-fit: contain;">'

    primary_col = client.company.primary_color or '#fa0102'
    second_col = client.company.secondary_color or '#111827'
    
    header_html = f"""
        <!-- Header -->
        <div style="font-family: 'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #111827; display: flex; justify-content: space-between; align-items: center; padding-bottom: 25px; border-bottom: 1px solid #e5e7eb; margin-bottom: 40px;">
            <div style="flex: 1;">
                {logo_img_tag}
            </div>
            <div style="text-align: right;">
                <h2 style="margin: 0; font-size: 20px; font-weight: 800; color: {second_col}; text-transform: uppercase; letter-spacing: 2px;">{client.company.name}</h2>
                <p style="margin: 4px 0 0; color: #6b7280; font-size: 13px; font-weight: 500;">CNPJ: {client.company.document or 'N/A'}</p>
                <div style="margin-top: 8px; font-size: 11px; font-weight: 600; color: #9ca3af; text-transform: uppercase; letter-spacing: 1px;">{datetime.now().strftime('%d de %B de %Y')}</div>
            </div>
        </div>
    """

    # Footer Logic
    footer_html = f"""
        <!-- Footer -->
        <div style="font-family: 'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif; margin-top: 60px; padding-top: 25px; border-top: 1px solid #f3f4f6; text-align: center;">
            <p style="margin: 0; font-size: 11px; font-weight: 700; color: #374151; text-transform: uppercase; letter-spacing: 1.5px;">{client.company.name}</p>
            <p style="margin: 4px 0; font-size: 10px; color: #9ca3af; line-height: 1.6;">{client.company.address or ''}</p>
            <div style="margin-top: 10px; width: 40px; height: 2px; background-color: {primary_col}; margin-left: auto; margin-right: auto; opacity: 0.3;"></div>
        </div>
    """

    # --- ANEXO I: QUADRO RESUMO (Mandatory) ---
    def generate_summary_sheet(client, replacements, primary_col):
        summary_html = f"""
        <div style="page-break-before: always; font-family: 'Inter', 'Helvetica Neue', Helvetica, Arial, sans-serif; padding: 40px; color: #111827;">
            <div style="text-align: center; margin-bottom: 40px;">
                <h1 style="font-size: 20px; font-weight: 800; color: {primary_col}; margin: 0; text-transform: uppercase; letter-spacing: 2px;">ANEXO I - QUADRO RESUMO</h1>
                <div style="width: 60px; height: 3px; background-color: {primary_col}; margin: 15px auto 0;"></div>
            </div>
            
            <p style="margin-bottom: 25px; font-size: 13px; color: #6b7280; line-height: 1.6; text-align: center; max-width: 80%; margin-left: auto; margin-right: auto;">
                Este documento consolida as principais condições comerciais acordadas. 
                Sua validade está vinculada ao contrato principal.
            </p>

            <h3 style="font-size: 12px; font-weight: 700; color: #374151; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
                <span style="width: 8px; height: 8px; border-radius: 50%; background-color: {primary_col}; display: inline-block; margin-right: 8px;"></span>
                1. Informações das Partes
            </h3>
            <table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 30px; border: 1px solid #f3f4f6; border-radius: 8px; overflow: hidden;">
                <tr style="background-color: #fafafa;">
                    <td style="padding: 12px 15px; border-bottom: 1px solid #f3f4f6; width: 30%; color: #6b7280;"><strong>CONTRATANTE</strong></td>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #f3f4f6; font-weight: 600;">{replacements.get('{{nome_empresarial_contratante}}', '')}</td>
                </tr>
                 <tr>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #f3f4f6; color: #6b7280;"><strong>CNPJ/CPF</strong></td>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #f3f4f6;">{replacements.get('{{cnpj_contratante}}', '')}</td>
                </tr>
                 <tr>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #f3f4f6; color: #6b7280;"><strong>Responsável</strong></td>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #f3f4f6;">{replacements.get('{{representante_legal_contratante}}', '')}</td>
                </tr>
            </table>

            <h3 style="font-size: 12px; font-weight: 700; color: #374151; text-transform: uppercase; letter-spacing: 1px; margin: 25px 0 12px; display: flex; align-items: center; gap: 8px;">
                <span style="width: 8px; height: 8px; border-radius: 50%; background-color: {primary_col}; display: inline-block; margin-right: 8px;"></span>
                2. Vigência e Prazo
            </h3>
            <table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 30px; border: 1px solid #f3f4f6; border-radius: 8px; overflow: hidden;">
                <tr style="background-color: #fafafa;">
                    <td style="padding: 12px 15px; border-bottom: 1px solid #f3f4f6; width: 30%; color: #6b7280;"><strong>Início</strong></td>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #f3f4f6; font-weight: 600;">{replacements.get('{{DATA_INICIO}}', replacements.get('{{data_inicio}}', ''))}</td>
                </tr>
                <tr>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #f3f4f6; color: #6b7280;"><strong>Término</strong></td>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #f3f4f6;">{replacements.get('{{DATA_FIM}}', replacements.get('{{data_fim}}', 'Indeterminado'))}</td>
                </tr>
                 <tr>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #f3f4f6; color: #6b7280;"><strong>Duração</strong></td>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #f3f4f6; font-weight: 600; color: {primary_col};">{replacements.get('{{VIGENCIA_MESES}}', replacements.get('{{vigencia_meses}}', ''))} meses</td>
                </tr>
            </table>
    
            <h3 style="font-size: 12px; font-weight: 700; color: #374151; text-transform: uppercase; letter-spacing: 1px; margin: 25px 0 12px; display: flex; align-items: center; gap: 8px;">
                <span style="width: 8px; height: 8px; border-radius: 50%; background-color: {primary_col}; display: inline-block; margin-right: 8px;"></span>
                3. Condições Comerciais
            </h3>
            <table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 40px; border: 1px solid #f3f4f6; border-radius: 8px; overflow: hidden;">
                <tr style="background-color: #fafafa;">
                    <td style="padding: 12px 15px; border-bottom: 1px solid #f3f4f6; width: 30%; color: #6b7280;"><strong>Valor Total</strong></td>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #f3f4f6; font-size: 15px; font-weight: 800; color: {primary_col};">R$ {replacements.get('{{valor_total}}', replacements.get('{{VALOR_TOTAL}}', '0,00'))}</td>
                </tr>
                <tr>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #f3f4f6; color: #6b7280;"><strong>Implantação</strong></td>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #f3f4f6;">R$ {replacements.get('{{VALOR_IMPLANTACAO}}', '0,00')}</td>
                </tr>
                 <tr>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #f3f4f6; color: #6b7280;"><strong>Mensalidade</strong></td>
                    <td style="padding: 12px 15px; border-bottom: 1px solid #f3f4f6;">
                        <span style="font-weight: 600;">{replacements.get('{{NUMERO_PARCELAS}}', '0')}x de R$ {replacements.get('{{VALOR_MENSAL}}', '0,00')}</span>
                        <br><small style="color: #9ca3af;">Vencimento: dia {replacements.get('{{DIA_VENCIMENTO}}', '')}</small>
                    </td>
                </tr>
                <tr style="background-color: #fafafa;">
                    <td style="padding: 12px 15px; color: #6b7280;"><strong>Tráfego Mínimo</strong></td>
                    <td style="padding: 12px 15px; font-weight: 500;">R$ {replacements.get('{{VALOR_MINIMO_TRAFEGO}}', '0,00')} / {replacements.get('{{PERIODO_TRAFEGO}}', 'mês')}</td>
                </tr>
            </table>

            <div style="margin-top: 60px; display: flex; justify-content: space-between; gap: 40px; text-align: center;">
                 <div style="flex: 1;">
                    <div style="height: 1px; background-color: #374151; margin-bottom: 12px;"></div>
                    <p style="margin: 0; font-size: 11px; font-weight: 700; color: #111827; text-transform: uppercase; letter-spacing: 0.5px;">{replacements.get('{{nome_empresarial_contratante}}', 'CONTRATANTE')}</p>
                    <p style="margin-top: 4px; font-size: 10px; color: #9ca3af; text-transform: uppercase;">Contratante</p>
                </div>
                <div style="flex: 1;">
                    <div style="height: 1px; background-color: #374151; margin-bottom: 12px;"></div>
                    <p style="margin: 0; font-size: 11px; font-weight: 700; color: #111827; text-transform: uppercase; letter-spacing: 0.5px;">{client.company.name}</p>
                    <p style="margin-top: 4px; font-size: 10px; color: #9ca3af; text-transform: uppercase;">Contratada</p>
                </div>
            </div>
        </div>
        """
        return summary_html

    summary_sheet = generate_summary_sheet(client, replacements, primary_col)
    
    return jsonify({'content': header_html + content + footer_html + summary_sheet})

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
            
            # Sync Address if present
            if form_data.get('contratante_endereco'):
                client.address_street = form_data.get('contratante_endereco') # Simplified sync
            
            # Sync Financials
            val_p = form_data.get('valor_parcela')
            if val_p:
                try:
                    client.monthly_value = float(val_p.replace('R$', '').replace('.', '').replace(',', '.').strip())
                except: pass
            
            client.start_date = datetime.strptime(form_data.get('data_inicio'), '%d/%m/%Y').date() if form_data.get('data_inicio') else client.start_date
        
        # Generate Content
        generated_content = template.content
        for key, value in replacements.items():
            generated_content = generated_content.replace(key, str(value))
        
        # --- PREMIUM HEADER & FOOTER LOGIC (CREATE) ---
        logo_img_tag = ""
        if current_user.company.logo_base64:
             logo_src = f"data:image/png;base64,{current_user.company.logo_base64}"
             logo_img_tag = f'<img src="{logo_src}" alt="Logo" style="max-height: 80px; width: auto;">'
        elif current_user.company.logo_filename:
             if current_user.company.logo_filename.startswith('http'):
                 logo_url = current_user.company.logo_filename
             else:
                 logo_url = url_for('static', filename='uploads/company/' + current_user.company.logo_filename, _external=True)
             logo_img_tag = f'<img src="{logo_url}" alt="Logo" style="max-height: 80px; width: auto;">'

        primary_col = current_user.company.primary_color or '#fa0102'
        second_col = current_user.company.secondary_color or '#111827'

        header_html = f"""
            <div style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; color: #333; width: 100%; border-bottom: 4px solid {primary_col}; margin-bottom: 40px; padding-bottom: 20px;">
                <table width="100%" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                        <td align="left" valign="middle">
                            {logo_img_tag}
                        </td>
                        <td align="right" valign="middle">
                            <h2 style="margin: 0; font-size: 24px; color: {second_col}; text-transform: uppercase; letter-spacing: 1px;">{current_user.company.name}</h2>
                            <p style="margin: 5px 0 0; color: #666; font-size: 14px;">CNPJ: {current_user.company.document}</p>
                        </td>
                    </tr>
                </table>
            </div>
        """

        footer_html = f"""
            <div style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; margin-top: 60px; padding-top: 20px; border-top: 1px solid {primary_col}; text-align: center; font-size: 12px; color: #777; page-break-inside: avoid;">
                <p style="margin: 0;"><strong>{current_user.company.name}</strong></p>
                <p style="margin: 2px 0;">{current_user.company.address}</p>
            </div>
        """
        
        generated_content = header_html + generated_content + footer_html

        # --- ANEXO I: QUADRO RESUMO (Mandatory - Duplicated for Safety) ---
        def generate_summary_sheet_create(client, replacements, primary_col):
            summary_html = f"""
            <div style="page-break-before: always; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; padding: 40px; color: #333;">
                <h1 style="text-align: center; font-size: 24px; color: {primary_col}; margin-bottom: 30px; border-bottom: 2px solid {primary_col}; padding-bottom: 10px;">ANEXO I - QUADRO RESUMO</h1>
                
                <p style="margin-bottom: 20px; font-size: 14px; color: #666;">Este anexo é parte integrante e indissociável do contrato principal, servindo como resumo vinculante das condições comerciais e financeiras acordadas.</p>
    
                <h3 style="background-color: #f3f4f6; padding: 10px; margin: 20px 0 10px; font-size: 16px; border-left: 4px solid {primary_col};">1. PARTES</h3>
                <table style="width: 100%; border-collapse: collapse; font-size: 14px; margin-bottom: 20px;">
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #eee; width: 30%;"><strong>CONTRATANTE:</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;">{replacements.get('{{nome_empresarial_contratante}}', '')}</td>
                    </tr>
                     <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>CPF/CNPJ:</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;">{replacements.get('{{cnpj_contratante}}', '')}</td>
                    </tr>
                     <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Resp. Legal:</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;">{replacements.get('{{representante_legal_contratante}}', '')}</td>
                    </tr>
                </table>
    
                <h3 style="background-color: #f3f4f6; padding: 10px; margin: 20px 0 10px; font-size: 16px; border-left: 4px solid {primary_col};">2. VIGÊNCIA E DATAS</h3>
                <table style="width: 100%; border-collapse: collapse; font-size: 14px; margin-bottom: 20px;">
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #eee; width: 30%;"><strong>Data de Início:</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;">{replacements.get('{{DATA_INICIO}}', replacements.get('{{data_inicio}}', ''))}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Data de Término:</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;">{replacements.get('{{DATA_FIM}}', replacements.get('{{data_fim}}', 'Indeterminado'))}</td>
                    </tr>
                     <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Prazo (Meses):</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;">{replacements.get('{{VIGENCIA_MESES}}', replacements.get('{{vigencia_meses}}', ''))} meses</td>
                    </tr>
                </table>
    
                <h3 style="background-color: #f3f4f6; padding: 10px; margin: 20px 0 10px; font-size: 16px; border-left: 4px solid {primary_col};">3. CONDIÇÕES FINANCEIRAS</h3>
                <table style="width: 100%; border-collapse: collapse; font-size: 14px; margin-bottom: 20px;">
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #eee; width: 30%;"><strong>Valor Total:</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #eee; font-weight: bold;">R$ {replacements.get('{{valor_total}}', replacements.get('{{VALOR_TOTAL}}', '0,00'))}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Taxa de Implantação:</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;">R$ {replacements.get('{{VALOR_IMPLANTACAO}}', '0,00')}</td>
                    </tr>
                     <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Mensalidade:</strong></td>
                         <td style="padding: 8px; border-bottom: 1px solid #eee;">
                            {replacements.get('{{NUMERO_PARCELAS}}', '0')}x parcelas de <strong>R$ {replacements.get('{{VALOR_MENSAL}}', '0,00')}</strong>
                        </td>
                    </tr>
                     <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Vencimento:</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;">Dia {replacements.get('{{DIA_VENCIMENTO}}', '')} de cada mês</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;"><strong>Tráfego Mínimo:</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #eee;">R$ {replacements.get('{{VALOR_MINIMO_TRAFEGO}}', '0,00')} / {replacements.get('{{PERIODO_TRAFEGO}}', '')}</td>
                    </tr>
                </table>
    
                <div style="margin-top: 60px; display: flex; justify-content: space-between; text-align: center;">
                     <div style="width: 45%;">
                        <p style="border-top: 1px solid #333; padding-top: 10px; margin-bottom: 5px;"><strong>{replacements.get('{{nome_empresarial_contratante}}', 'CONTRATANTE')}</strong></p>
                        <p style="font-size: 12px; color: #777;">Contratante</p>
                    </div>
                    <div style="width: 45%;">
                        <p style="border-top: 1px solid #333; padding-top: 10px; margin-bottom: 5px;"><strong>{replacements.get('{{nome_empresarial_contratada}}', 'CONTRATADA')}</strong></p>
                        <p style="font-size: 12px; color: #777;">Contratada</p>
                    </div>
                </div>
            </div>
            """
            return summary_html

        summary_sheet = generate_summary_sheet_create(client, replacements, primary_col)
        generated_content += summary_sheet

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
