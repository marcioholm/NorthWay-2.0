from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
from flask_login import login_required, current_user
from models import db, Lead, Company, Pipeline, PipelineStage
from datetime import datetime
import json
import logging

diagnostic_raiox_bp = Blueprint('diagnostic_raiox', __name__)
logger = logging.getLogger(__name__)

# Questions configuration to avoid hardcoding in both template and backend if needed,
# but we'll mainly use it in backend for validation if necessary. 
# The template will handle the UI.

@diagnostic_raiox_bp.route('/raiox', methods=['GET'])
def index():
    """
    Renderiza a Landing Page / Funil do Raio-X de Escala Digital
    """
    return render_template('forms/raiox_funnel.html')


@diagnostic_raiox_bp.route('/raiox/submit', methods=['POST'])
def submit():
    """
    Processa os dados do Raio-X
    Calcula scores, salva o lead, e retorna o resultado ou URL de redirect.
    """
    try:
        data = request.json
        
        # 1. Extrair Dados do Lead
        lead_info = data.get('lead_info', {})
        nome = lead_info.get('nome')
        email = lead_info.get('email')
        whatsapp = lead_info.get('whatsapp')
        empresa = lead_info.get('empresa')
        funcionarios = lead_info.get('quantidade_funcionarios')
        faturamento_str = lead_info.get('faturamento_mensal')
        
        # Converter faturamento para um número base para regras (em milhar)
        faturamento_val = 0
        if faturamento_str == '0-50k': faturamento_val = 25
        elif faturamento_str == '50k-100k': faturamento_val = 75
        elif faturamento_str == '100k-150k': faturamento_val = 125
        elif faturamento_str == '150k-200k': faturamento_val = 175
        elif faturamento_str == '200k+': faturamento_val = 250
        
        # 2. Calcular Scores
        answers = data.get('answers', {})
        
        # Pilares (espera arrays de 5 valores cada: 0 a 3)
        presenca = sum(int(x) for x in answers.get('presenca_digital', [0]*5))
        comercial = sum(int(x) for x in answers.get('comercial_conversao', [0]*5))
        posicionamento = sum(int(x) for x in answers.get('posicionamento_autoridade', [0]*5))
        escala = sum(int(x) for x in answers.get('escala_estrategia', [0]*5))
        
        score_total = presenca + comercial + posicionamento + escala
        
        # 3. Classificação e Gap
        nivel = 'N1'
        if score_total <= 20:
            nivel = 'N1'
        elif score_total <= 40:
            nivel = 'N2'
        else:
            nivel = 'N3'
            
        pillars_dict = {
            'Presença Digital': presenca,
            'Comercial & Conversão': comercial,
            'Posicionamento & Autoridade': posicionamento,
            'Escala & Estratégia': escala
        }
        
        # Pilar mais fraco
        pilar_mais_fraco = min(pillars_dict, key=pillars_dict.get)
        gap_tag = f"Gap {pilar_mais_fraco.split(' ')[0]}"
        
        # 4. Redirecionamento
        # Curso: Faturamento <= 100k E score_total < 35 -> Vai direto para LP do curso
        # Auditoria: Faturamento > 100k OU score_total >= 35 -> Vai para LP Auditoria
        dest_type = 'auditoria'
        redirect_url = 'https://northway-lp.vercel.app/auditoria.html'
        
        if faturamento_val <= 100 and score_total < 35:
            dest_type = 'curso'
            redirect_url = 'https://northway-lp.vercel.app'
        
        # Calculate Stars (0 to 5)
        # Max score is 60. 
        stars = round((score_total / 60.0) * 5.0, 1)

        # 5. Salvar no CRM
        # Procura a empresa master da NorthWay (id=1 usualmente)
        company_id = 1 
        company = Company.query.get(company_id)
        if not company:
            # Fallback for first company
            company = Company.query.first()
            if company:
                company_id = company.id
        
        # Verify if lead already exists by email/phone
        lead = Lead.query.filter_by(email=email, company_id=company_id).first()
        if not lead and whatsapp:
            # format phone maybe? 
            lead = Lead.query.filter_by(whatsapp=whatsapp, company_id=company_id).first()
            
        is_new = False
        if not lead:
            lead = Lead(company_id=company_id)
            is_new = True
            
            # Associate with the default pipeline and its first stage
            default_pipeline = Pipeline.query.filter_by(company_id=company_id).first()
            if default_pipeline:
                lead.pipeline_id = default_pipeline.id
                first_stage = PipelineStage.query.filter_by(pipeline_id=default_pipeline.id).order_by(PipelineStage.order).first()
                if first_stage:
                    lead.pipeline_stage_id = first_stage.id
            
        lead.name = nome
        lead.email = email
        lead.whatsapp = whatsapp
        lead.phone = whatsapp
        lead.legal_name = empresa
        lead.company_size = funcionarios
        lead.estimated_value = faturamento_val * 1000 # Convert to actual R$ roughly
        
        # Tags and Diagnostic Info
        lead.source = 'Raio-X Digital'
        lead.diagnostic_status = 'done'
        lead.diagnostic_score = float(score_total)
        lead.diagnostic_classification = nivel
        lead.diagnostic_date = datetime.utcnow()
        lead.diagnostic_pillars = pillars_dict
        lead.diagnostic_answers = {k: [int(x) for x in v] for k, v in answers.items()}
        lead.diagnostic_stars = stars
        
        # Append tags to 'interest' or notes
        tags = [nivel, 'Lead Diagnóstico', dest_type.capitalize(), gap_tag]
        lead.interest = ", ".join(tags)
        
        if is_new:
            db.session.add(lead)
            
        db.session.commit()
        
        # Trigger automations for the first stage if new lead
        if is_new and lead.pipeline_stage_id:
            try:
                from tasks_utils import generate_tasks_for_stage, process_funnel_automations
                generate_tasks_for_stage(lead.id, lead.pipeline_stage_id)
                process_funnel_automations(lead.id, lead.pipeline_stage_id)
            except Exception as e:
                logger.error(f"Error triggering organic lead automations: {e}")
        
        # Store results in session for the result page
        session['raiox_resultado'] = {
            'nome': nome,
            'score_total': score_total,
            'nivel': nivel,
            'pillars': pillars_dict,
            'pilar_mais_fraco': pilar_mais_fraco,
            'dest_type': dest_type,
            'faturamento': faturamento_str,
            'stars': stars
        }
        
        return jsonify({
            'status': 'success',
            'redirect_url': redirect_url
        })
        
    except Exception as e:
        logger.error(f"Erro ao processar Raio-X: {e}")
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500


@diagnostic_raiox_bp.route('/raiox/resultado', methods=['GET'])
def resultado():
    """
    Mostra a tela de resultados.
    """
    res = session.get('raiox_resultado')
    if not res:
        return redirect(url_for('diagnostic_raiox.index'))
        
    # Inject stars dynamically if missing from old sessions
    if isinstance(res, dict) and 'stars' not in res and 'score_total' in res:
        res['stars'] = round((res['score_total'] / 60.0) * 5.0, 1)
        session['raiox_resultado'] = res
        
    return render_template('forms/raiox_resultado.html', res=res)


@diagnostic_raiox_bp.route('/raiox/leads', methods=['GET'])
@login_required
def leads_list():
    """
    Lista todos os leads que fizeram o Raio-X Digital (source = 'Raio-X Digital')
    com diagnóstico concluído.
    """
    leads = (Lead.query
             .filter(Lead.source == 'Raio-X Digital')
             .filter(Lead.diagnostic_status == 'done')
             .order_by(Lead.diagnostic_date.desc())
             .all())

    return render_template('forms/raiox_leads.html', leads=leads)


@diagnostic_raiox_bp.route('/raiox/report/<int:lead_id>', methods=['GET'])
@login_required
def report(lead_id):
    """
    Relatório detalhado do Raio-X com todas as perguntas e respostas,
    pronto para impressão/PDF.
    """
    lead = Lead.query.get_or_404(lead_id)
    if lead.source != 'Raio-X Digital' or lead.diagnostic_status != 'done':
        return redirect(url_for('diagnostic_raiox.leads_list'))

    pillars_config = [
        {
            'key': 'presenca_digital',
            'name': 'Presença Digital',
            'icon': 'globe',
            'questions': [
                'Sua empresa possui um site profissional funcionando?',
                'Sua empresa publica conteúdo com frequência?',
                'Você roda anúncios pagos atualmente?',
                'Sua empresa possui rastreamento de dados (Pixel/Analytics)?',
                'Sua marca é facilmente encontrada no Google?',
            ]
        },
        {
            'key': 'comercial_conversao',
            'name': 'Comercial & Conversão',
            'icon': 'target',
            'questions': [
                'Quando um lead chega, existe processo definido?',
                'O tempo de resposta ao lead é rápido?',
                'Existe follow-up estruturado?',
                'Você acompanha métricas comerciais?',
                'Existe CRM ou sistema de gestão de leads?',
            ]
        },
        {
            'key': 'posicionamento_autoridade',
            'name': 'Posicionamento & Autoridade',
            'icon': 'award',
            'questions': [
                'Sua empresa possui diferencial claro?',
                'Você sabe quem são seus principais concorrentes?',
                'Sua comunicação gera autoridade?',
                'Sua empresa possui provas sociais?',
                'Seu marketing comunica transformação ou apenas serviço?',
            ]
        },
        {
            'key': 'escala_estrategia',
            'name': 'Escala & Estratégia',
            'icon': 'trending-up',
            'questions': [
                'Sua empresa possui metas trimestrais claras?',
                'Existe planejamento de campanhas?',
                'Você sabe quanto pode investir para crescer?',
                'Sua empresa possui previsibilidade de vendas?',
                'Seu negócio consegue crescer sem depender totalmente do dono?',
            ]
        }
    ]

    option_labels = [
        'Não fazemos',
        'Fazemos parcialmente',
        'Fazemos com alguma consistência',
        'Fazemos e acompanhamos métricas'
    ]

    answers = lead.diagnostic_answers or {}
    pillars = lead.diagnostic_pillars or {}

    return render_template(
        'forms/raiox_report.html',
        lead=lead,
        pillars_config=pillars_config,
        option_labels=option_labels,
        answers=answers,
        pillars=pillars
    )
