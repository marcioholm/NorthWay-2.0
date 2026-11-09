from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
from flask_login import login_required, current_user
from models import db, Lead, Company, Pipeline, PipelineStage
from datetime import datetime
import json
import logging
from fpdf import FPDF

diagnostic_raiox_bp = Blueprint('diagnostic_raiox', __name__)
logger = logging.getLogger(__name__)

def safe_int(val, default=0):
    try:
        if val is None or val == '':
            return default
        return int(val)
    except (ValueError, TypeError):
        return default

def generate_raiox_pdf_bytes(nome, empresa, score_total, nivel, stars, pillars_dict, pilar_mais_fraco, faturamento_str):
    """
    Gera o PDF formatado do Raio-X de Escala Digital com fpdf2
    """
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Barra Superior Vermelha NorthWay
    pdf.set_fill_color(227, 30, 36) # #E31E24
    pdf.rect(0, 0, 210, 8, 'F')

    # Cabeçalho da Empresa
    pdf.set_fill_color(15, 23, 42) # slate-900
    pdf.rect(0, 8, 210, 24, 'F')

    pdf.set_text_color(255, 255, 255)
    pdf.set_font('helvetica', 'B', 15)
    pdf.set_xy(16, 14)
    pdf.cell(100, 8, 'NORTHWAY  |  RAIO-X DE ESCALA DIGITAL', ln=False)

    pdf.set_font('helvetica', '', 9)
    pdf.set_xy(140, 14)
    pdf.cell(54, 8, datetime.now().strftime('%d/%m/%Y'), align='R', ln=True)

    # Bloco: Dados da Empresa
    pdf.set_text_color(15, 23, 42)
    pdf.set_xy(16, 38)
    pdf.set_font('helvetica', 'B', 12)
    pdf.cell(0, 7, 'DIAGNOSTICO DE MATURIDADE COMERCIAL & DIGITAL', ln=True)

    pdf.set_fill_color(248, 250, 252) # slate-50
    pdf.set_draw_color(226, 232, 240) # slate-200
    pdf.rect(16, 46, 178, 22, 'DF')

    pdf.set_font('helvetica', 'B', 9)
    pdf.set_text_color(100, 116, 139)
    pdf.set_xy(20, 48)
    pdf.cell(40, 6, 'EMPRESA:', ln=False)
    pdf.cell(50, 6, 'RESPONSAVEL:', ln=False)
    pdf.cell(50, 6, 'FAIXA DE FATURAMENTO:', ln=True)

    pdf.set_font('helvetica', 'B', 10)
    pdf.set_text_color(15, 23, 42)
    pdf.set_xy(20, 54)
    pdf.cell(40, 6, (empresa or 'Nao informada')[:22], ln=False)
    pdf.cell(50, 6, (nome or 'Cliente')[:24], ln=False)
    pdf.cell(50, 6, (faturamento_str or 'Nao informado')[:22], ln=True)

    # Bloco: Pontuação Geral (Cards de Score)
    pdf.set_xy(16, 74)
    pdf.set_font('helvetica', 'B', 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 6, 'RESULTADO GERAL DO DIAGNOSTICO', ln=True)

    # 3 Cards de Score
    # Card 1: Score Geral
    pdf.set_fill_color(241, 245, 249)
    pdf.rect(16, 82, 56, 26, 'DF')
    pdf.set_xy(16, 85)
    pdf.set_font('helvetica', 'B', 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(56, 5, 'PONTUACAO GERAL', align='C', ln=True)
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(227, 30, 36)
    pdf.cell(56, 8, f'{score_total} / 60 pts', align='C', ln=True)
    pdf.set_font('helvetica', '', 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(56, 4, f'Nota: {stars} de 5.0 estrelas', align='C', ln=True)

    # Card 2: Nivel de Maturidade
    pdf.rect(77, 82, 56, 26, 'DF')
    pdf.set_xy(77, 85)
    pdf.set_font('helvetica', 'B', 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(56, 5, 'MATURIDADE DIGITAL', align='C', ln=True)
    pdf.set_font('helvetica', 'B', 14)
    nivel_label = 'N1 - Operacional' if nivel == 'N1' else ('N2 - Tracao' if nivel == 'N2' else 'N3 - Escala')
    pdf.set_text_color(15, 23, 42)
    pdf.cell(56, 8, nivel_label, align='C', ln=True)
    pdf.set_font('helvetica', '', 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(56, 4, f'Classificacao: {nivel}', align='C', ln=True)

    # Card 3: Principal Gargalo
    pdf.set_fill_color(254, 242, 242) # red-50
    pdf.set_draw_color(252, 165, 165) # red-300
    pdf.rect(138, 82, 56, 26, 'DF')
    pdf.set_xy(138, 85)
    pdf.set_font('helvetica', 'B', 8)
    pdf.set_text_color(185, 28, 28)
    pdf.cell(56, 5, 'MAIOR GARGALO (GAP)', align='C', ln=True)
    pdf.set_font('helvetica', 'B', 10)
    pdf.set_text_color(153, 27, 27)
    pdf.set_xy(138, 91)
    pdf.multi_cell(56, 5, str(pilar_mais_fraco)[:30], align='C')

    # Bloco: Desempenho por Pilar (Tabela com Barras de Progresso)
    pdf.set_draw_color(226, 232, 240)
    pdf.set_xy(16, 115)
    pdf.set_font('helvetica', 'B', 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 6, 'DESEMPENHO DETALHADO POR PILAR ESTRATEGICO', ln=True)

    pilares_nomes = [
        ('Presenca Digital', pillars_dict.get('Presença Digital', 0)),
        ('Comercial & Conversao', pillars_dict.get('Comercial & Conversão', 0)),
        ('Posicionamento & Autoridade', pillars_dict.get('Posicionamento & Autoridade', 0)),
        ('Escala & Estrategia', pillars_dict.get('Escala & Estratégia', 0))
    ]

    y_pos = 125
    for p_name, p_val in pilares_nomes:
        pdf.set_xy(16, y_pos)
        pdf.set_font('helvetica', 'B', 9)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(70, 6, p_name, ln=False)

        # Barra de fundo (15 pontos max = 80mm)
        bar_x = 90
        max_w = 75
        w = max(4, int((p_val / 15.0) * max_w))
        pdf.set_fill_color(241, 245, 249)
        pdf.rect(bar_x, y_pos + 1, max_w, 4.5, 'F')

        # Barra preenchida (verde se >= 10, amarela se >= 6, vermelha se < 6)
        if p_val >= 10:
            pdf.set_fill_color(16, 185, 129) # esmeralda
        elif p_val >= 6:
            pdf.set_fill_color(245, 158, 11) # ambar
        else:
            pdf.set_fill_color(227, 30, 36) # vermelho
        pdf.rect(bar_x, y_pos + 1, w, 4.5, 'F')

        pdf.set_xy(170, y_pos)
        pdf.set_font('helvetica', 'B', 9)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(24, 6, f'{p_val} / 15 pts', align='R', ln=True)

        y_pos += 10

    # Bloco: Plano de Ação Recomendado
    pdf.set_xy(16, 172)
    pdf.set_fill_color(248, 250, 252)
    pdf.rect(16, 172, 178, 62, 'DF')

    pdf.set_xy(22, 176)
    pdf.set_font('helvetica', 'B', 10)
    pdf.set_text_color(227, 30, 36)
    pdf.cell(0, 6, 'DIRECAO ESTRATEGICA RECOMENDADA:', ln=True)

    pdf.set_font('helvetica', '', 8.5)
    pdf.set_text_color(51, 65, 85)
    pdf.set_xy(22, 184)
    recommendation_text = (
        f"1. Foco Imediato: O seu maior gap atual esta no pilar '{pilar_mais_fraco}'. "
        "A prioridade da sua operacao deve ser destravar esse ponto antes de escalar o investimento.\n\n"
        "2. Processo Comercial: Garanta que cada oportunidade receba contato em menos de 15 minutos e "
        "possua follow-up estruturado de 5 a 7 etapas no CRM.\n\n"
        "3. Posicionamento: Diferenciais claros e provas sociais de clientes aumentam as taxas de fechamento "
        "sem necessidade de baixar precos.\n\n"
        "4. Acompanhamento: Agende uma sessao estrategica com a equipe da NorthWay para detalhar o plano de execucao."
    )
    pdf.multi_cell(166, 4.5, recommendation_text)

    # Rodapé
    pdf.set_draw_color(226, 232, 240)
    pdf.line(16, 270, 194, 270)
    pdf.set_xy(16, 273)
    pdf.set_font('helvetica', 'B', 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(100, 5, 'NORTHWAY COMPANY - CRM, ESTRATEGIA & ESCALA COMERCIAL', ln=False)
    pdf.set_font('helvetica', '', 8)
    pdf.cell(78, 5, 'contato@northwaycompany.com.br', align='R', ln=True)

    return bytes(pdf.output())

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
        
        # Pilares (espera arrays de 5 valores cada: 0 a 3, seguro contra None/null)
        presenca = sum(safe_int(x) for x in answers.get('presenca_digital', [0]*5))
        comercial = sum(safe_int(x) for x in answers.get('comercial_conversao', [0]*5))
        posicionamento = sum(safe_int(x) for x in answers.get('posicionamento_autoridade', [0]*5))
        escala = sum(safe_int(x) for x in answers.get('escala_estrategia', [0]*5))
        
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
        lead.diagnostic_stars = stars
        
        # Store individual answers inside diagnostic_pillars for per-question breakdown (seguro contra None)
        pillars_dict['_answers'] = {k: [safe_int(x) for x in (v or [])] for k, v in answers.items()}
        
        # Append tags to 'interest' or notes
        tags = [nivel, 'Lead Diagnóstico', dest_type.capitalize(), gap_tag]
        lead.interest = ", ".join(tags)
        
        if is_new:
            db.session.add(lead)
            
        db.session.commit()
        
        # 6. Enviar PDF do Raio-X por E-mail via Resend
        if email:
            try:
                from services.email_service import EmailService
                pdf_bytes = generate_raiox_pdf_bytes(
                    nome=nome or 'Cliente',
                    empresa=empresa or 'Sua Empresa',
                    score_total=score_total,
                    nivel=nivel,
                    stars=stars,
                    pillars_dict=pillars_dict,
                    pilar_mais_fraco=pilar_mais_fraco,
                    faturamento_str=faturamento_str or 'Não informado'
                )

                email_html = f"""
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; color: #0F172A; background-color: #ffffff;">
                    <div style="border-bottom: 3px solid #E31E24; padding-bottom: 16px; margin-bottom: 24px;">
                        <h2 style="color: #E31E24; margin: 0; font-size: 24px; font-weight: 800;">NORTHWAY</h2>
                        <p style="margin: 4px 0 0 0; color: #64748B; font-size: 13px;">Raio-X de Escala Digital</p>
                    </div>
                    <p style="font-size: 15px; line-height: 1.6;">Olá, <strong>{nome}</strong>!</p>
                    <p style="font-size: 14px; line-height: 1.6; color: #334155;">
                        Seu diagnóstico de maturidade digital da empresa <strong>{empresa or 'seu negócio'}</strong> foi concluído com sucesso.
                    </p>
                    <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 12px; padding: 18px; margin: 20px 0;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                            <span style="font-size: 13px; color: #64748B; font-weight: 600;">Pontuação Geral:</span>
                            <strong style="font-size: 16px; color: #0F172A;">{score_total} / 60 pontos ({stars} ⭐)</strong>
                        </div>
                        <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                            <span style="font-size: 13px; color: #64748B; font-weight: 600;">Classificação de Maturidade:</span>
                            <strong style="font-size: 14px; color: #E31E24;">Nível {nivel}</strong>
                        </div>
                        <div style="display: flex; justify-content: space-between;">
                            <span style="font-size: 13px; color: #64748B; font-weight: 600;">Principal Gargalo Identificado:</span>
                            <strong style="font-size: 14px; color: #EA580C;">{pilar_mais_fraco}</strong>
                        </div>
                    </div>
                    <p style="font-size: 14px; line-height: 1.6; color: #334155;">
                        Anexamos a este e-mail o seu <strong>Relatório Completo em PDF</strong> com a pontuação detalhada de cada um dos 4 pilares estratégicos.
                    </p>
                    <div style="margin-top: 32px; padding-top: 16px; border-top: 1px solid #E2E8F0; font-size: 12px; color: #94A3B8;">
                        Equipe NorthWay Company · Transformação Digital e Escala Comercial
                    </div>
                </div>
                """

                filename_clean = (empresa or 'NorthWay').replace(' ', '_').replace('/', '_')
                attachments = [{
                    "filename": f"RaioX-Digital-{filename_clean}.pdf",
                    "content": list(pdf_bytes)
                }]

                EmailService.send_email(
                    to=[email],
                    subject=f"Seu Raio-X Digital está pronto | {empresa or nome} ({score_total}/60 pts)",
                    html_content=email_html,
                    company_id=company_id,
                    attachments=attachments
                )
                logger.info(f"E-mail com PDF do Raio-X disparado via Resend para {email}")
            except Exception as email_err:
                logger.error(f"Erro ao enviar e-mail com PDF via Resend: {email_err}")
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

    # Remove _answers from pillars in Python to avoid TypeError in Jinja2 dictsort
    clean_leads = []
    for l in leads:
        if isinstance(l.diagnostic_pillars, dict):
            l.diagnostic_pillars = {k: v for k, v in l.diagnostic_pillars.items() if k != '_answers'}
        clean_leads.append(l)

    return render_template('forms/raiox_leads.html', leads=clean_leads)


@diagnostic_raiox_bp.route('/raiox/report/<int:lead_id>', methods=['GET'])
@login_required
def report(lead_id):
    """
    Relatório do Raio-X.
    ?mode=simple  → apenas gráfico + barras (para enviar ao cliente)
    ?mode=complete → gráfico + barras + perguntas individuais
    """
    mode = request.args.get('mode', 'simple')
    lead = Lead.query.filter_by(id=lead_id, company_id=current_user.company_id).first_or_404()
    if lead.source != 'Raio-X Digital' or lead.diagnostic_status != 'done':
        return redirect(url_for('diagnostic_raiox.leads_list'))

    pillars_config = [
        {'key': 'presenca_digital', 'name': 'Presença Digital',
         'questions': [
             'Sua empresa possui um site profissional funcionando?',
             'Sua empresa publica conteúdo com frequência?',
             'Você roda anúncios pagos atualmente?',
             'Sua empresa possui rastreamento de dados (Pixel/Analytics)?',
             'Sua marca é facilmente encontrada no Google?']},
        {'key': 'comercial_conversao', 'name': 'Comercial & Conversão',
         'questions': [
             'Quando um lead chega, existe processo definido?',
             'O tempo de resposta ao lead é rápido?',
             'Existe follow-up estruturado?',
             'Você acompanha métricas comerciais?',
             'Existe CRM ou sistema de gestão de leads?']},
        {'key': 'posicionamento_autoridade', 'name': 'Posicionamento & Autoridade',
         'questions': [
             'Sua empresa possui diferencial claro?',
             'Você sabe quem são seus principais concorrentes?',
             'Sua comunicação gera autoridade?',
             'Sua empresa possui provas sociais?',
             'Seu marketing comunica transformação ou apenas serviço?']},
        {'key': 'escala_estrategia', 'name': 'Escala & Estratégia',
         'questions': [
             'Sua empresa possui metas trimestrais claras?',
             'Existe planejamento de campanhas?',
             'Você sabe quanto pode investir para crescer?',
             'Sua empresa possui previsibilidade de vendas?',
             'Seu negócio consegue crescer sem depender totalmente do dono?']}
    ]

    option_labels = [
        'Não fazemos',
        'Fazemos parcialmente',
        'Fazemos com alguma consistência',
        'Fazemos e acompanhamos métricas'
    ]

    pillars = lead.diagnostic_pillars or {}
    answers = pillars.pop('_answers', {}) if isinstance(pillars, dict) else {}

    has_answers = bool(answers and any(answers.values()))

    return render_template(
        'forms/raiox_report.html',
        lead=lead,
        pillars_config=pillars_config,
        option_labels=option_labels,
        answers=answers,
        pillars=pillars,
        has_answers=has_answers,
        mode=mode
    )


@diagnostic_raiox_bp.route('/raiox/<int:lead_id>/delete', methods=['POST'])
@login_required
def delete(lead_id):
    """
    Remove os dados de diagnóstico de um lead (Raio-X).
    """
    lead = Lead.query.filter_by(id=lead_id, company_id=current_user.company_id).first_or_404()
    if lead.source != 'Raio-X Digital':
        return jsonify({'status': 'error', 'message': 'Lead não é do Raio-X'}), 400

    lead.diagnostic_status = 'pending'
    lead.diagnostic_score = None
    lead.diagnostic_stars = None
    lead.diagnostic_classification = None
    lead.diagnostic_date = None
    lead.diagnostic_pillars = None
    lead.source = None
    lead.interest = None
    db.session.commit()

    return jsonify({'status': 'success'})
