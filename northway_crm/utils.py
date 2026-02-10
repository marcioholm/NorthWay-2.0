from datetime import datetime, timedelta
from flask import jsonify
from flask_login import current_user
from models import db, Notification, Interaction, Integration
import time
import functools
import requests

def get_now_br():
    """Returns the current time in Brasília (UTC-3)"""
    return datetime.utcnow() - timedelta(hours=3)

def get_date_extenso_br():
    """Returns current date in format: 10 de Fevereiro de 2026"""
    now = get_now_br()
    months = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
        5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
        9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
    }
    return f"{now.day} de {months[now.month]} de {now.year}"

def api_response(success=True, data=None, error=None, status=200):
    """Standardized JSON response for all API routes."""
    response = {
        'success': success,
        'data': data,
        'error': error
    }
    return jsonify(response), status

def create_notification(user_id, company_id, type, title, message):
    try:
        notification = Notification(
            user_id=user_id,
            company_id=company_id,
            type=type,
            title=title,
            message=message
        )
        db.session.add(notification)
        db.session.commit()
    except Exception as e:
        print(f"Error creating notification: {e}")
        try:
            db.session.rollback()
        except:
            pass

def update_client_health(client):
    """
    Updates client health based on interaction recency.
    Green: <= 3 days
    Yellow: 4-7 days
    Red: > 7 days or No interaction
    """
    last_interaction = None
    if client.interactions:
        # Sort descending in memory (Relationship is lazy=True but can be joinedloaded)
        interactions_list = sorted(client.interactions, key=lambda x: x.created_at, reverse=True)
        if interactions_list:
            last_interaction = interactions_list[0]
    
    status = 'vermelho' # Default critical
    
    if last_interaction:
        days_diff = (get_now_br() - last_interaction.created_at).days
        
        if days_diff <= 3:
            status = 'verde'
        elif days_diff <= 7:
            status = 'amarelo'
        else:
            status = 'vermelho'
    
    if status != client.health_status:
        client.health_status = status
        
        # NOTIFICATION: Status Changed
        if client.account_manager_id and client.account_manager_id != current_user.id:
             create_notification(
                 user_id=client.account_manager_id,
                 company_id=client.company_id,
                 type='client_status_changed',
                 title='Status do Cliente Alterado',
                 message=f"Status do cliente {client.name} alterado para {status} por {current_user.name}."
             )

def get_contract_replacements(client, form_data):
    """Helper to build the replacements dictionary for contracts."""
    from datetime import date
    try:
        current_user_name = current_user.name
    except:
        current_user_name = "Sistema"
    
    # Parse Foro into Comarca/Estado if possible
    cidade_foro = form_data.get('cidade_foro', 'São Paulo - SP')
    if '-' in cidade_foro:
        foro_parts = cidade_foro.split('-')
    elif '/' in cidade_foro:
        foro_parts = cidade_foro.split('/')
    else:
        foro_parts = [cidade_foro, '']
    
    if len(foro_parts) >= 2:
        foro_comarca = foro_parts[0].strip()
        foro_estado = foro_parts[1].strip()
    else:
        foro_comarca = cidade_foro.strip()
        foro_estado = ''
    
    if len(foro_parts) >= 2:
        foro_comarca = foro_parts[0].strip()
        foro_estado = foro_parts[1].strip()
    else:
        foro_comarca = cidade_foro.strip()
        foro_estado = ''

    def format_addr(obj):
        parts = []
        if obj.address_street: parts.append(f"{obj.address_street}")
        if obj.address_number: parts.append(f"nº {obj.address_number}")
        if obj.address_neighborhood: parts.append(f"- {obj.address_neighborhood}")
        if obj.address_city and obj.address_state: parts.append(f"- {obj.address_city}/{obj.address_state}")
        elif obj.address_city: parts.append(f"- {obj.address_city}")
        if obj.address_zip: parts.append(f"CEP: {obj.address_zip}")
        return " ".join(parts) if parts else "Endereço não informado"

    today_br = get_now_br().date()

    replacements = {
        # --- CONTRATANTE (CLIENTE) ---
        '{{CONTRATANTE_NOME_EMPRESARIAL}}': form_data.get('contratante_nome') or client.name,
        '{{CONTRATANTE_NOME}}': form_data.get('contratante_nome') or client.name,
    
        '{{CONTRATANTE_DOCUMENTO}}': form_data.get('contratante_documento') or client.document or 'N/A',
        '{{CONTRATANTE_CNPJ}}': form_data.get('contratante_documento') or client.document or 'N/A',
        '{{CONTRATANTE_CPF}}': form_data.get('contratante_cpf') or client.representative_cpf or '',
    
        '{{CONTRATANTE_ENDERECO}}': form_data.get('contratante_endereco') or format_addr(client),
        '{{CONTRATANTE_EMAIL}}': client.email,
        '{{CONTRATANTE_TELEFONE}}': client.phone,
    
        '{{CONTRATANTE_REPRESENTANTE}}': form_data.get('contratante_representante') or client.representative or '',
        '{{CONTRATANTE_REPRESENTANTE_LEGAL}}': form_data.get('contratante_representante') or client.representative or '',
    
        '{{CONTRATANTE_CPF_REPRESENTANTE}}': form_data.get('contratante_cpf') or client.representative_cpf or '',
        '{{CONTRATANTE_ENDERECO_REPRESENTANTE}}': form_data.get('contratante_endereco_representante') or '',

        # --- LOWERCASE ALIASES (Compatibility) ---
        '{{contratante_razao_social}}': form_data.get('contratante_nome') or client.name,
        '{{contratante_cnpj}}': form_data.get('contratante_documento') or client.document or 'N/A',
        '{{contratante_endereco}}': form_data.get('contratante_endereco') or format_addr(client),
        '{{contratante_representante_nome}}': form_data.get('contratante_representante') or client.representative or '',
        '{{contratante_representante_cpf}}': form_data.get('contratante_cpf') or client.representative_cpf or '',
        '{{contratante_email}}': client.email,

        # --- English Aliases ---
        '{{COMPANY_NAME}}': client.company.name,
        '{{CLIENT_NAME}}': form_data.get('contratante_nome') or client.name,
        '{{VALUE}}': form_data.get('valor_total', '0,00'),

        # --- CONTRATADA ---
        '{{CONTRATADA_NOME_EMPRESARIAL}}': client.company.name,
        '{{CONTRATADA_DOCUMENTO}}': client.company.document,
        '{{CONTRATADA_CNPJ}}': client.company.document,
        '{{CONTRATADA_ENDERECO}}': format_addr(client.company),
        '{{CONTRATADA_EMAIL}}': getattr(client.company, 'email', None) or current_user.email,
        '{{CONTRATADA_TELEFONE}}': getattr(client.company, 'phone', ''),
    
        '{{CONTRATADA_REPRESENTANTE}}': getattr(client.company, 'representative', '') or current_user_name,
        '{{CONTRATADA_REPRESENTANTE_LEGAL}}': getattr(client.company, 'representative', '') or current_user_name,
        '{{CONTRATADA_CPF}}': getattr(client.company, 'representative_cpf', '') or '', 

        # --- LOWERCASE ALIASES (Compatibility: Contratada) ---
        '{{contratada_razao_social}}': client.company.name,
        '{{contratada_cnpj}}': client.company.document,
        '{{contratada_endereco}}': format_addr(client.company),
        '{{contratada_representante_nome}}': getattr(client.company, 'representative', '') or current_user_name,
        '{{contratada_representante_cpf}}': getattr(client.company, 'representative_cpf', '') or '',

        # --- VALORES E PAGAMENTO ---
        '{{VALOR_TOTAL_CONTRATO}}': form_data.get('valor_total', '0,00'),
        '{{VALOR_TOTAL}}': form_data.get('valor_total', '0,00'),
        '{{VALOR_IMPLANTACAO}}': form_data.get('valor_implantacao', '0,00'),
        '{{VALOR_PARCELA}}': form_data.get('valor_parcela', '0,00'),
        '{{VALOR_MENSAL}}': form_data.get('valor_parcela', '0,00'),
        '{{NUMERO_PARCELAS}}': form_data.get('qtd_parcelas', '12'),
        '{{QTD_PARCELAS}}': form_data.get('qtd_parcelas', '12'),
        '{{DIA_VENCIMENTO}}': form_data.get('dia_vencimento', '5'),
    
        # --- TRAFEGO ---
        '{{VALOR_MINIMO_TRAFEGO}}': form_data.get('valor_minimo_trafego', '0,00'),
        '{{VALOR_MINIMO_TRÁFEGO}}': form_data.get('valor_minimo_trafego', '0,00'),
        '{{PERIODO_TRAFEGO}}': form_data.get('periodo_trafego', '30 dias'),
        '{{PERIODO_TRÁFEGO}}': form_data.get('periodo_trafego', '30 dias'),

        # --- DATAS E VIGÊNCIA ---
        '{{DATA_INICIO}}': form_data.get('data_inicio', today_br.strftime('%d/%m/%Y')),
        '{{VIGENCIA_MESES}}': form_data.get('vigencia_meses', '12'),
        '{{DATA_FIM}}': form_data.get('data_fim', ''),
        '{{DATA_FINAL}}': form_data.get('data_fim', ''),
        '{{DATA_TERMINO}}': form_data.get('data_fim', ''),
        '{{CIDADE_FORO}}': foro_comarca,
        '{{ESTADO_FORO}}': foro_estado,
        '{{FORO_COMARCA}}': foro_comarca,
        '{{FORO_ESTADO}}': foro_estado,
        '{{DATA_ATUAL}}': today_br.strftime('%d/%m/%Y'),
        '{{CURRENT_DATE}}': today_br.strftime('%d/%m/%Y'),
        '{{CIDADE_ASSINATURA}}': form_data.get('cidade_assinatura', foro_comarca),
        '{{DATA_ASSINATURA}}': form_data.get('data_assinatura', today_br.strftime('%d/%m/%Y')),
        '{{NUMERO_VIAS}}': form_data.get('numero_vias', '2'),

        # --- ASSINATURAS ---
        '{{CONTRATANTE_ASSINATURA_NOME}}': form_data.get('contratante_representante') or client.representative or (form_data.get('contratante_nome') or client.name),
        '{{CONTRATADA_ASSINATURA_NOME}}': getattr(client.company, 'representative', '') or current_user_name,

        # --- LOWERCASE ALIASES ---
        '{{data_inicio}}': form_data.get('data_inicio', today_br.strftime('%d/%m/%Y')),
        '{{data_proposta}}': form_data.get('data_proposta', today_br.strftime('%d/%m/%Y')),
        '{{data_assinatura}}': form_data.get('data_assinatura', today_br.strftime('%d/%m/%Y')),
        '{{data_atual}}': today_br.strftime('%d/%m/%Y'),

        # --- SPECIFIC USER ALIASES ---
        '{{data_inicio_contrato}}': form_data.get('data_inicio', today_br.strftime('%d/%m/%Y')),
        '{{prazo_meses}}': form_data.get('vigencia_meses', '12'),
        '{{valor_contrato}}': form_data.get('valor_total', '0,00'),
        
        '{{nome_assinante_contratante}}': form_data.get('contratante_representante') or client.representative or (form_data.get('contratante_nome') or client.name),
        '{{nome_assinante_contratada}}': getattr(client.company, 'representative', '') or current_user_name,
        '{{cnpj_contratada}}': client.company.document,

        '{{testemunha1_nome}}': form_data.get('testemunha1_nome', ''),
        '{{testemunha1_cpf}}': form_data.get('testemunha1_cpf', ''),
        '{{testemunha2_nome}}': form_data.get('testemunha2_nome', ''),
        '{{testemunha2_cpf}}': form_data.get('testemunha2_cpf', ''),

        '{{nome_testemunha_1}}': form_data.get('testemunha1_nome', ''),
        '{{cpf_testemunha_1}}': form_data.get('testemunha1_cpf', ''),
        '{{nome_testemunha_2}}': form_data.get('testemunha2_nome', ''),
        '{{cpf_testemunha_2}}': form_data.get('testemunha2_cpf', ''),

        '{{foro_completo}}': f"{foro_comarca} - {foro_estado}" if foro_estado else foro_comarca,
        '{{foro_comarca}}': foro_comarca,
        '{{foro_estado}}': foro_estado,

        # --- COMPATIBILITY ALIASES (Summary Sheet & Lowercase) ---
        '{{nome_empresarial_contratante}}': form_data.get('contratante_nome') or client.name,
        '{{cnpj_contratante}}': form_data.get('contratante_documento') or client.document or 'N/A',
        '{{representante_legal_contratante}}': form_data.get('contratante_representante') or client.representative or '',
        '{{vigencia_meses}}': form_data.get('vigencia_meses', '12'),
        '{{valor_total}}': form_data.get('valor_total', '0,00'),
        '{{valor_mensal}}': form_data.get('valor_parcela', '0,00'),
        '{{dia_vencimento}}': form_data.get('dia_vencimento', '5'),
    }
    return replacements

def retry_request(retries=3, backoff_factor=0.3, status_codes=(500, 502, 503, 504)):
    """
    Decorator for retrying requests with exponential backoff.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for i in range(retries + 1):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException as e:
                    last_exception = e
                    # Only retry if it's a server error or timeout
                    is_retryable = False
                    if hasattr(e, 'response') and e.response is not None:
                        if e.response.status_code in status_codes:
                            is_retryable = True
                    elif isinstance(e, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
                        is_retryable = True
                    
                    if not is_retryable or i == retries:
                        raise e
                    
                    wait_time = backoff_factor * (2 ** i)
                    time.sleep(wait_time)
            raise last_exception
        return wrapper
    return decorator

def update_integration_health(company_id, service, error=None):
    """Updates the last_error and last_sync_at for an integration."""
    try:
        integration = Integration.query.filter_by(company_id=company_id, service=service).first()
        if integration:
            if error:
                integration.last_error = str(error)
            else:
                integration.last_error = None
                integration.last_sync_at = get_now_br()
            db.session.commit()
    except Exception as e:
        print(f"Error updating integration health: {e}")
        db.session.rollback()
