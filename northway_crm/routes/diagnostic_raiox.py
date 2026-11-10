from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
from flask_login import login_required, current_user
from models import db, Lead, Company, Pipeline, PipelineStage
from datetime import datetime
import json
import logging
import os
import urllib.parse
from sqlalchemy import text, or_

diagnostic_raiox_bp = Blueprint('diagnostic_raiox', __name__)
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------------
# Configuração dos 5 Eixos e 20 Perguntas Exatas da Metodologia NorthWay v2
# -------------------------------------------------------------------------
RAIOX_QUESTIONS = [
    # ATRAIR (1-4)
    {
        "id": 1, "eixo": "atrair", "eixo_nome": "Atrair",
        "pergunta": "Sua empresa sabe exatamente quem é o cliente ideal e onde ele está?",
        "acao": "Escreva em uma página quem é o seu cliente ideal: perfil, problema que quer resolver e onde procura solução. Use isso como base de toda a divulgação do mês."
    },
    {
        "id": 2, "eixo": "atrair", "eixo_nome": "Atrair",
        "pergunta": "Sua marca é facilmente encontrada no Google (busca e mapa)?",
        "acao": "Crie ou atualize o Perfil da Empresa no Google (endereço, horário, fotos, telefone) e peça avaliação a 5 clientes satisfeitos."
    },
    {
        "id": 3, "eixo": "atrair", "eixo_nome": "Atrair",
        "pergunta": "Sua empresa divulga com frequência planejada, seja com conteúdo ou anúncios?",
        "acao": "Monte um calendário de 4 semanas com 2 ações de divulgação por semana e cumpra até o fim do mês."
    },
    {
        "id": 4, "eixo": "atrair", "eixo_nome": "Atrair",
        "pergunta": "Você sabe de onde vêm os seus novos clientes?",
        "acao": "Pergunte a todo cliente novo \"como você conheceu a gente?\" e registre a resposta por 30 dias."
    },
    # ENGAJAR (5-8)
    {
        "id": 5, "eixo": "engajar", "eixo_nome": "Engajar",
        "pergunta": "Sua empresa possui um diferencial claro e comunica isso?",
        "acao": "Escreva em uma frase por que o cliente deveria comprar de você e não do concorrente. Use essa frase na bio, no atendimento e nos conteúdos."
    },
    {
        "id": 6, "eixo": "engajar", "eixo_nome": "Engajar",
        "pergunta": "Sua comunicação gera autoridade (bastidores, explicações, provas), e não só ofertas?",
        "acao": "Publique por semana pelo menos 1 conteúdo de bastidor, explicação ou prova de resultado, sem oferta."
    },
    {
        "id": 7, "eixo": "engajar", "eixo_nome": "Engajar",
        "pergunta": "Sua empresa coleta e mostra depoimentos ou avaliações de clientes?",
        "acao": "Peça avaliação a 10 clientes satisfeitos e publique as que forem autorizadas."
    },
    {
        "id": 8, "eixo": "engajar", "eixo_nome": "Engajar",
        "pergunta": "Existe uma lista organizada de contatos e interessados para manter relacionamento?",
        "acao": "Organize todos os interessados em uma lista única (etiquetas do WhatsApp Business ou planilha), com data e o que pediram."
    },
    # VENDER (9-12)
    {
        "id": 9, "eixo": "vender", "eixo_nome": "Vender",
        "pergunta": "Quando um lead chega, existe processo definido?",
        "acao": "Escreva o passo a passo do atendimento, do primeiro contato ao fechamento, e siga em todos os atendimentos do mês."
    },
    {
        "id": 10, "eixo": "vender", "eixo_nome": "Vender",
        "pergunta": "O tempo de resposta ao lead é rápido?",
        "acao": "Defina horários fixos para responder mensagens e um prazo máximo de resposta. Cumpra por 30 dias."
    },
    {
        "id": 11, "eixo": "vender", "eixo_nome": "Vender",
        "pergunta": "Existe follow-up estruturado?",
        "acao": "Reserve 15 minutos por dia para retomar contato com quem pediu orçamento ou informação e não fechou."
    },
    {
        "id": 12, "eixo": "vender", "eixo_nome": "Vender",
        "pergunta": "Existe CRM ou sistema de gestão de leads?",
        "acao": "Registre todo lead numa planilha ou CRM com etapa e data do próximo contato. Comece simples."
    },
    # RETER (13-16)
    {
        "id": 13, "eixo": "reter", "eixo_nome": "Reter",
        "pergunta": "Sua empresa entra em contato com o cliente depois da compra?",
        "acao": "Crie uma mensagem de pós-venda e envie a todo cliente de 3 a 7 dias depois da compra."
    },
    {
        "id": 14, "eixo": "reter", "eixo_nome": "Reter",
        "pergunta": "Existe alguma ação para estimular a recompra?",
        "acao": "Crie uma ação simples de recompra (lembrete de reposição, benefício para cliente da casa) e teste durante o mês."
    },
    {
        "id": 15, "eixo": "reter", "eixo_nome": "Reter",
        "pergunta": "Sua empresa pede indicação de forma ativa?",
        "acao": "Peça indicação a cada cliente satisfeito, usando sempre a mesma frase simples."
    },
    {
        "id": 16, "eixo": "reter", "eixo_nome": "Reter",
        "pergunta": "Você sabe quantos clientes voltaram a comprar nos últimos meses?",
        "acao": "Levante quantos clientes compraram mais de uma vez nos últimos 6 meses. Esse é o seu ponto de partida."
    },
    # GESTÃO (17-20)
    {
        "id": 17, "eixo": "gestao", "eixo_nome": "Gestão",
        "pergunta": "Você sabe se o negócio deu lucro no mês passado, depois de pagar tudo, inclusive você?",
        "acao": "Preencha a DRE dos últimos 3 meses, incluindo o pró-labore, e veja se o negócio está acima do ponto de equilíbrio."
    },
    {
        "id": 18, "eixo": "gestao", "eixo_nome": "Gestão",
        "pergunta": "Sua empresa tem metas de vendas definidas e acompanhadas?",
        "acao": "Defina a meta de vendas do mês de trás para frente (lucro → faturamento → vendas → atendimentos) e confira toda semana."
    },
    {
        "id": 19, "eixo": "gestao", "eixo_nome": "Gestão",
        "pergunta": "Você acompanha métricas comerciais (atendimentos, conversão, ticket médio)?",
        "acao": "Registre por 30 dias cada atendimento e se virou venda. No fim do mês, calcule conversão e ticket médio."
    },
    {
        "id": 20, "eixo": "gestao", "eixo_nome": "Gestão",
        "pergunta": "Sua empresa possui rastreamento de dados (Pixel, Analytics)?",
        "acao": "Instale o Pixel da Meta e o Google Analytics no site ou na página de vendas e confira se registram visitas."
    }
]

def safe_int(val, default=0):
    try:
        if val is None or val == '':
            return default
        return int(val)
    except (ValueError, TypeError):
        return default

def get_situacao_eixo(nota):
    """
    Classificação da situação do eixo:
    0–3,9 Crítico (Vermelho #fa0102)
    4–6,9 Em construção (Âmbar #f59e0b)
    7–8,9 Estruturado (Verde #10b981)
    9–10 Consistente (Verde #10b981)
    """
    if nota <= 3.9:
        return {
            "texto": "Crítico",
            "cor": "#fa0102",
            "badge_bg": "bg-red-500/15",
            "badge_text": "text-red-500",
            "border_color": "border-red-500/30"
        }
    elif nota <= 6.9:
        return {
            "texto": "Em construção",
            "cor": "#f59e0b",
            "badge_bg": "bg-amber-500/15",
            "badge_text": "text-amber-500",
            "border_color": "border-amber-500/30"
        }
    elif nota <= 8.9:
        return {
            "texto": "Estruturado",
            "cor": "#10b981",
            "badge_bg": "bg-emerald-500/15",
            "badge_text": "text-emerald-500",
            "border_color": "border-emerald-500/30"
        }
    else:
        return {
            "texto": "Consistente",
            "cor": "#10b981",
            "badge_bg": "bg-emerald-500/15",
            "badge_text": "text-emerald-500",
            "border_color": "border-emerald-500/30"
        }

def calculate_raiox_v2(respostas_list):
    """
    Calcula as notas dos 5 eixos, índice de maturidade, gargalo e ponto fraco.
    Regras:
    - Nota do eixo = soma das 4 respostas ÷ 12 × 10, arredondada para 1 casa decimal.
    - Índice de maturidade = média das 5 notas, com 1 casa decimal.
    - Gargalo = eixo com menor nota. Em empate: Atrair -> Engajar -> Vender -> Reter -> Gestão.
    - Ponto fraco = pergunta com a menor resposta dentro do gargalo. Em empate: primeira do eixo.
    - Ação prioritária = ação do ponto fraco.
    """
    eixos_def = [
        ('atrair', 'Atrair', respostas_list[0:4], 1),
        ('engajar', 'Engajar', respostas_list[4:8], 5),
        ('vender', 'Vender', respostas_list[8:12], 9),
        ('reter', 'Reter', respostas_list[12:16], 13),
        ('gestao', 'Gestão', respostas_list[16:20], 17)
    ]
    
    notas = {}
    eixos_resultado = []
    pontos_fracos_eixo = {}
    
    for key, name, resp_eixo, start_q in eixos_def:
        soma = sum(safe_int(x) for x in resp_eixo)
        nota = round((soma / 12.0) * 10, 1)
        notas[key] = nota
        sit = get_situacao_eixo(nota)
        
        # Ponto fraco dentro do eixo: menor resposta, empate: primeira do eixo
        min_val = min(resp_eixo)
        idx_min = resp_eixo.index(min_val)
        ponto_fraco_q = start_q + idx_min
        pontos_fracos_eixo[key] = ponto_fraco_q
        
        eixos_resultado.append({
            'key': key,
            'nome': name,
            'nota': nota,
            'nota_formatada': str(nota).replace('.', ','),
            'situacao': sit['texto'],
            'cor': sit['cor'],
            'badge_bg': sit['badge_bg'],
            'badge_text': sit['badge_text'],
            'border_color': sit['border_color'],
            'percentual': min(100, max(0, int(nota * 10))),
            'ponto_fraco_num': ponto_fraco_q
        })
        
    indice = round(sum(notas.values()) / 5.0, 1)
    
    # Gargalo: menor nota com desempate na ordem da lista
    gargalo_tuple = min(eixos_def, key=lambda e: notas[e[0]])
    gargalo_key = gargalo_tuple[0]
    gargalo_nome = gargalo_tuple[1]
    gargalo_nota = notas[gargalo_key]
    
    ponto_fraco_num = pontos_fracos_eixo[gargalo_key]
    q_data = RAIOX_QUESTIONS[ponto_fraco_num - 1]
    
    return {
        'notas': notas,
        'indice': indice,
        'indice_formatado': str(indice).replace('.', ','),
        'gargalo': gargalo_key,
        'gargalo_nome': gargalo_nome,
        'gargalo_nota': gargalo_nota,
        'gargalo_nota_formatada': str(gargalo_nota).replace('.', ','),
        'ponto_fraco_num': ponto_fraco_num,
        'ponto_fraco_pergunta': q_data['pergunta'],
        'acao_prioritaria': q_data['acao'],
        'eixos': eixos_resultado
    }

def clean_pdf_text(s):
    if not s:
        return ''
    rep = {
        '—': '-', '–': '-', '·': '-', '“': '"', '”': '"', '‘': "'", '’': "'",
        'ã': 'a', 'á': 'a', 'à': 'a', 'â': 'a', 'é': 'e', 'ê': 'e', 'í': 'i',
        'ó': 'o', 'ô': 'o', 'õ': 'o', 'ú': 'u', 'ü': 'u', 'ç': 'c',
        'Ã': 'A', 'Á': 'A', 'À': 'A', 'Â': 'A', 'É': 'E', 'Ê': 'E', 'Í': 'I',
        'Ó': 'O', 'Ô': 'O', 'Õ': 'O', 'Ú': 'U', 'Ç': 'C'
    }
    res = str(s)
    for k, v in rep.items():
        res = res.replace(k, v)
    return res.encode('latin-1', 'replace').decode('latin-1')

def generate_raiox_v2_pdf_bytes(nome, empresa, resultado, faixa_faturamento, funcionarios):
    """
    Gera o PDF formatado do Raio-X NorthWay v2 (5 eixos da metodologia)
    com fpdf2 (import tardio para resiliência).
    """
    from fpdf import FPDF
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    W = 210
    ML = 16
    MR = 16
    cw = W - ML - MR
    
    # 1. Top accent line (vermelho NorthWay #FA0102)
    pdf.set_fill_color(250, 1, 2)
    pdf.rect(0, 0, W, 6, 'F')
    
    # 2. Header (fundo escuro #050505)
    pdf.set_fill_color(5, 5, 5)
    pdf.rect(0, 6, W, 22, 'F')
    
    pdf.set_xy(ML, 10)
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(100, 12, 'NORTHWAY  |  RAIO-X DE MATURIDADE', align='L')
    
    pdf.set_font('helvetica', '', 9)
    pdf.set_text_color(180, 180, 180)
    pdf.cell(cw - 100, 12, datetime.now().strftime('%d/%m/%Y'), align='R')
    pdf.ln(18)
    
    # 3. Informações da Empresa / Contato
    pdf.set_xy(ML, 32)
    pdf.set_font('helvetica', 'B', 9)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(cw, 5, 'DADOS DO DIAGNOSTICO')
    pdf.ln(6)
    
    pdf.set_fill_color(248, 250, 252)
    pdf.set_draw_color(226, 232, 240)
    info_y = pdf.get_y()
    pdf.rect(ML, info_y, cw, 22, 'DF')
    
    pdf.set_xy(ML + 4, info_y + 3)
    pdf.set_font('helvetica', 'B', 8.5)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(50, 5, 'EMPRESA:')
    pdf.cell(50, 5, 'RESPONSAVEL:')
    pdf.cell(40, 5, 'FATURAMENTO:')
    pdf.cell(38, 5, 'EQUIPE:')
    pdf.ln(5)
    
    pdf.set_x(ML + 4)
    pdf.set_font('helvetica', 'B', 9.5)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(50, 6, clean_pdf_text(empresa or 'Nao informada')[:24])
    pdf.cell(50, 6, clean_pdf_text(nome or 'Cliente')[:24])
    pdf.cell(40, 6, clean_pdf_text(faixa_faturamento or 'Nao informado')[:18])
    pdf.cell(38, 6, clean_pdf_text(funcionarios or 'Nao informado')[:16])
    pdf.ln(12)
    
    # 4. Cards de Score Geral
    card_y = pdf.get_y()
    card_w = (cw - 8) / 2
    
    # Card Índice
    pdf.set_fill_color(241, 245, 249)
    pdf.set_draw_color(203, 213, 225)
    pdf.rect(ML, card_y, card_w, 24, 'DF')
    
    pdf.set_xy(ML, card_y + 3)
    pdf.set_font('helvetica', 'B', 8)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(card_w, 4, 'INDICE DE MATURIDADE GERAL', align='C')
    pdf.ln(5)
    pdf.set_x(ML)
    pdf.set_font('helvetica', 'B', 15)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(card_w, 8, f"{resultado.get('indice_formatado', '0')}/10", align='C')
    
    # Card Gargalo
    gx = ML + card_w + 8
    pdf.set_fill_color(254, 242, 242)
    pdf.set_draw_color(252, 165, 165)
    pdf.rect(gx, card_y, card_w, 24, 'DF')
    
    pdf.set_xy(gx, card_y + 3)
    pdf.set_font('helvetica', 'B', 8)
    pdf.set_text_color(227, 30, 36)
    pdf.cell(card_w, 4, 'PRINCIPAL GARGALO IDENTIFICADO', align='C')
    pdf.ln(5)
    pdf.set_x(gx)
    pdf.set_font('helvetica', 'B', 13)
    pdf.set_text_color(227, 30, 36)
    gargalo_str = clean_pdf_text(f"{resultado.get('gargalo_nome', '').upper()} ({resultado.get('gargalo_nota_formatada', '0')}/10)")
    pdf.cell(card_w, 8, gargalo_str, align='C')
    
    pdf.set_xy(ML, card_y + 28)
    
    # 5. Desempenho por Eixo
    pdf.set_font('helvetica', 'B', 10)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(cw, 6, 'DESEMPENHO NOS 5 EIXOS METODOLOGICOS')
    pdf.ln(8)
    
    eixos = resultado.get('eixos', [])
    for e in eixos:
        ey = pdf.get_y()
        pdf.set_font('helvetica', 'B', 9)
        pdf.set_text_color(30, 41, 59)
        pdf.cell(32, 5, clean_pdf_text(e['nome']))
        
        pdf.set_font('helvetica', 'B', 8.5)
        pdf.cell(20, 5, f"{e['nota_formatada']}/10", align='R')
        
        sit = e.get('situacao', '')
        if 'Critico' in sit:
            pdf.set_text_color(227, 30, 36)
        elif 'construcao' in sit:
            pdf.set_text_color(217, 119, 6)
        else:
            pdf.set_text_color(22, 163, 74)
        pdf.cell(36, 5, f"  [{clean_pdf_text(sit)}]", align='L')
        
        # Barra de progresso
        bar_x = ML + 92
        bar_w = cw - 92
        pdf.set_fill_color(226, 232, 240)
        pdf.rect(bar_x, ey + 1.2, bar_w, 3, 'F')
        
        pct = max(0, min(100, e.get('percentual', 0)))
        fill_w = (bar_w * pct) / 100.0
        if fill_w > 0:
            if 'Critico' in sit:
                pdf.set_fill_color(250, 1, 2)
            elif 'construcao' in sit:
                pdf.set_fill_color(245, 158, 11)
            else:
                pdf.set_fill_color(16, 185, 129)
            pdf.rect(bar_x, ey + 1.2, fill_w, 3, 'F')
            
        pdf.ln(6.5)
        
    pdf.ln(4)
    
    # 6. Card Destacado do Gargalo & Ação Prioritária
    callout_y = pdf.get_y()
    pdf.set_fill_color(255, 241, 242)
    pdf.set_draw_color(254, 205, 211)
    
    empresa_str = clean_pdf_text(empresa or 'Sua Empresa')
    gargalo_nome_str = clean_pdf_text(resultado.get('gargalo_nome', ''))
    title_box = f"{empresa_str}: o foco agora e {gargalo_nome_str}"
    
    pdf.rect(ML, callout_y, cw, 42, 'DF')
    pdf.set_xy(ML + 5, callout_y + 4)
    pdf.set_font('helvetica', 'B', 11)
    pdf.set_text_color(190, 18, 60)
    pdf.cell(cw - 10, 5, title_box)
    pdf.ln(7)
    
    # Ponto Fraco
    pdf.set_x(ML + 5)
    pdf.set_font('helvetica', 'B', 8.5)
    pdf.set_text_color(136, 19, 55)
    pdf.cell(cw - 10, 4, f"Ponto Fraco Identificado (Questao {resultado.get('ponto_fraco_num', '')}):")
    pdf.ln(4.5)
    pdf.set_x(ML + 5)
    pdf.set_font('helvetica', '', 8)
    pdf.set_text_color(51, 65, 85)
    pf_txt = clean_pdf_text(resultado.get('ponto_fraco_pergunta', ''))
    pdf.multi_cell(cw - 10, 4, pf_txt)
    pdf.ln(2)
    
    # Ação Prioritária
    pdf.set_x(ML + 5)
    pdf.set_font('helvetica', 'B', 8.5)
    pdf.set_text_color(136, 19, 55)
    pdf.cell(cw - 10, 4, "Acao Prioritaria Recomendada:")
    pdf.ln(4.5)
    pdf.set_x(ML + 5)
    pdf.set_font('helvetica', 'B', 8)
    pdf.set_text_color(15, 23, 42)
    acao_txt = clean_pdf_text(resultado.get('acao_prioritaria', ''))
    pdf.multi_cell(cw - 10, 4, acao_txt)
    
    # 7. Rodapé
    pdf.set_xy(ML, 268)
    pdf.set_draw_color(226, 232, 240)
    pdf.line(ML, 266, W - MR, 266)
    pdf.set_font('helvetica', 'I', 7.5)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(cw, 4, clean_pdf_text('Este Raio-X e uma autoavaliacao. Ele aponta onde olhar primeiro; o diagnostico completo considera tambem numeros, processos e contexto.'), align='C')
    pdf.ln(4)
    pdf.set_font('helvetica', 'B', 7.5)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(cw, 4, 'NorthWay Company - Metodologia de Aceleracao Comercial - northwaycompany.com.br', align='C')
    
    return bytes(pdf.output())

def ensure_raiox_v2_columns():
    """
    Garante de forma resiliente que as colunas da v2 do Raio-X existam no banco.
    Também limpa leads de teste conforme critério de aceite.
    """
    try:
        is_postgres = 'postgresql' in str(db.engine.url)
        cols = [
            ("origem", "VARCHAR(100)"),
            ("faixa_faturamento", "VARCHAR(50)"),
            ("funcionarios", "VARCHAR(50)"),
            ("respostas", "JSONB" if is_postgres else "TEXT"),
            ("nota_atrair", "FLOAT"),
            ("nota_engajar", "FLOAT"),
            ("nota_vender", "FLOAT"),
            ("nota_reter", "FLOAT"),
            ("nota_gestao", "FLOAT"),
            ("indice_maturidade", "FLOAT"),
            ("gargalo", "VARCHAR(50)"),
            ("ponto_fraco", "INTEGER"),
            ("consentimento", "BOOLEAN DEFAULT FALSE"),
            ("consentimento_em", "TIMESTAMP")
        ]
        with db.engine.connect() as conn:
            for col_name, col_type in cols:
                try:
                    if is_postgres:
                        conn.execute(text(f'ALTER TABLE "lead" ADD COLUMN IF NOT EXISTS {col_name} {col_type}'))
                    else:
                        conn.execute(text(f'ALTER TABLE "lead" ADD COLUMN {col_name} {col_type}'))
                    conn.commit()
                except Exception:
                    conn.rollback()

            # Limpeza de leads de teste (Critério de aceite)
            try:
                conn.execute(text("DELETE FROM \"lead\" WHERE email = 'teste.claude@exemplo.com' OR name = 'TESTE Claude - apagar'"))
                conn.commit()
            except Exception:
                conn.rollback()
    except Exception as e:
        logger.warning(f"ensure_raiox_v2_columns: {e}")

# -------------------------------------------------------------------------
# Rotas
# -------------------------------------------------------------------------

@diagnostic_raiox_bp.route('/raiox', methods=['GET'])
def index():
    """
    Renderiza a Landing Page / Funil do Raio-X NorthWay v2
    """
    ensure_raiox_v2_columns()
    origem = request.args.get('origem', 'direto')
    whatsapp_number = os.environ.get('NORTHWAY_WHATSAPP', '5542999896358').replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
    return render_template(
        'forms/raiox_funnel.html',
        origem=origem,
        whatsapp_number=whatsapp_number,
        questions=RAIOX_QUESTIONS
    )


@diagnostic_raiox_bp.route('/raiox/submit', methods=['POST'])
def submit():
    """
    Processa os dados do Raio-X NorthWay v2.
    Calcula scores dos 5 eixos, índice, gargalo e ponto fraco.
    Salva no CRM e retorna o resultado para renderização inline na mesma página.
    """
    try:
        ensure_raiox_v2_columns()
        data = request.json or {}
        
        # 1. Dados do Lead
        lead_info = data.get('lead_info', {})
        nome = (lead_info.get('nome') or '').strip()
        email = (lead_info.get('email') or '').strip().lower()
        whatsapp = (lead_info.get('whatsapp') or '').strip()
        empresa = (lead_info.get('empresa') or '').strip()
        funcionarios = lead_info.get('quantidade_funcionarios')
        faixa_faturamento = lead_info.get('faturamento_mensal')
        origem = (lead_info.get('origem') or request.args.get('origem') or 'direto').strip()
        consentimento = bool(lead_info.get('consentimento', False))
        
        # Validação obrigatória de consentimento
        if not consentimento:
            return jsonify({'status': 'error', 'message': 'O consentimento para uso dos dados é obrigatório.'}), 400

        consentimento_em = datetime.utcnow()

        # 2. Extração das Respostas (20 inteiros de 0 a 3)
        raw_answers = data.get('answers')
        respostas_list = []
        
        if isinstance(raw_answers, list):
            respostas_list = [safe_int(x, 0) for x in raw_answers]
        elif isinstance(raw_answers, dict):
            # Ordem exata dos 5 eixos
            for e_key in ['atrair', 'engajar', 'vender', 'reter', 'gestao']:
                sub_arr = raw_answers.get(e_key, [])
                for val in sub_arr:
                    respostas_list.append(safe_int(val, 0))
        
        # Garantir exatamente 20 respostas
        while len(respostas_list) < 20:
            respostas_list.append(0)
        respostas_list = respostas_list[:20]

        # 3. Cálculo das Notas e Gargalo
        resultado = calculate_raiox_v2(respostas_list)
        notas = resultado['notas']
        indice = resultado['indice']
        gargalo = resultado['gargalo']
        gargalo_nome = resultado['gargalo_nome']
        gargalo_nota_formatada = resultado['gargalo_nota_formatada']
        ponto_fraco = resultado['ponto_fraco_num']

        # 4. Salvar no CRM
        company_id = 1 
        company = Company.query.get(company_id)
        if not company:
            company = Company.query.first()
            if company:
                company_id = company.id
        
        # Localiza lead existente ou cria novo
        lead = None
        if email:
            lead = Lead.query.filter_by(email=email, company_id=company_id).first()
        if not lead and whatsapp:
            lead = Lead.query.filter_by(whatsapp=whatsapp, company_id=company_id).first()
            
        is_new = False
        if not lead:
            lead = Lead(company_id=company_id)
            is_new = True
            
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
        
        # Novos campos v2
        lead.origem = origem
        lead.faixa_faturamento = faixa_faturamento
        lead.funcionarios = funcionarios
        lead.company_size = funcionarios
        lead.respostas = respostas_list
        lead.nota_atrair = notas['atrair']
        lead.nota_engajar = notas['engajar']
        lead.nota_vender = notas['vender']
        lead.nota_reter = notas['reter']
        lead.nota_gestao = notas['gestao']
        lead.indice_maturidade = indice
        lead.gargalo = gargalo
        lead.ponto_fraco = ponto_fraco
        lead.consentimento = consentimento
        lead.consentimento_em = consentimento_em

        # Campos legados preservados para compatibilidade
        lead.source = 'Raio-X Digital'
        lead.diagnostic_status = 'done'
        lead.diagnostic_score = indice
        lead.diagnostic_classification = gargalo.capitalize()
        lead.diagnostic_date = datetime.utcnow()
        lead.diagnostic_stars = round((indice / 10.0) * 5.0, 1)
        lead.diagnostic_pillars = {
            'Atrair': notas['atrair'],
            'Engajar': notas['engajar'],
            'Vender': notas['vender'],
            'Reter': notas['reter'],
            'Gestão': notas['gestao'],
            '_respostas': respostas_list
        }
        
        tags = [f"Gargalo {gargalo_nome}", f"Índice {str(indice).replace('.', ',')}", f"Origem {origem}", "Raio-X v2"]
        lead.interest = ", ".join(tags)
        
        if is_new:
            db.session.add(lead)
            
        db.session.commit()
        
        # Disparo de automações para novo lead
        if is_new and lead.pipeline_stage_id:
            try:
                from tasks_utils import generate_tasks_for_stage, process_funnel_automations
                generate_tasks_for_stage(lead.id, lead.pipeline_stage_id)
                process_funnel_automations(lead.id, lead.pipeline_stage_id)
            except Exception as e:
                logger.error(f"Erro ao disparar automações de estágio: {e}")

        # 5. Gerar Link do WhatsApp
        whatsapp_number = os.environ.get('NORTHWAY_WHATSAPP', '5542999896358').replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
        wa_text = f"Olá! Sou {nome or 'um empreendedor'}, da {empresa or 'minha empresa'}. Fiz o Raio-X e meu principal gargalo é {gargalo_nome} ({gargalo_nota_formatada}/10). Quero entender os próximos passos."
        wa_url = f"https://wa.me/{whatsapp_number}?text={urllib.parse.quote(wa_text)}"
        resultado['whatsapp_url'] = wa_url
        resultado['empresa'] = empresa
        resultado['nome'] = nome

        # 6. Enviar PDF do Raio-X v2 por E-mail via Resend
        if email:
            try:
                from services.email_service import EmailService
                pdf_bytes = generate_raiox_v2_pdf_bytes(
                    nome=nome or 'Cliente',
                    empresa=empresa or 'Sua Empresa',
                    resultado=resultado,
                    faixa_faturamento=faixa_faturamento or 'Não informado',
                    funcionarios=funcionarios or 'Não informado'
                )

                email_html = f"""
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 28px; color: #0F172A; background-color: #ffffff; border: 1px solid #E2E8F0; border-radius: 12px;">
                    <div style="border-bottom: 3px solid #FA0102; padding-bottom: 16px; margin-bottom: 24px;">
                        <h2 style="color: #FA0102; margin: 0; font-size: 24px; font-weight: 800; letter-spacing: -0.5px;">NORTHWAY</h2>
                        <p style="margin: 4px 0 0 0; color: #64748B; font-size: 13px;">Raio-X de Maturidade Comercial</p>
                    </div>
                    
                    <p style="font-size: 16px; font-weight: 700; margin-bottom: 12px;">Olá, {nome or 'Empreendedor'}!</p>
                    
                    <p style="font-size: 14px; line-height: 1.6; color: #334155;">
                        Seu diagnóstico pelo <strong>Raio-X NorthWay v2</strong> foi concluído com sucesso. Abaixo está o resumo da avaliação da sua empresa ({empresa or 'Sua Empresa'}):
                    </p>
                    
                    <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 18px; margin: 20px 0;">
                        <div style="margin-bottom: 10px;">
                            <span style="font-size: 13px; color: #64748B; font-weight: 600;">Índice Geral de Maturidade:</span>
                            <strong style="font-size: 16px; color: #0F172A; margin-left: 6px;">{resultado.get('indice_formatado', '0')} / 10</strong>
                        </div>
                        <div style="margin-bottom: 10px;">
                            <span style="font-size: 13px; color: #64748B; font-weight: 600;">Principal Gargalo Identificado:</span>
                            <strong style="font-size: 15px; color: #FA0102; margin-left: 6px;">{gargalo_nome} ({gargalo_nota_formatada}/10)</strong>
                        </div>
                        <div style="margin-bottom: 10px; font-size: 13px; color: #334155;">
                            <strong>Ponto Fraco (Questão {resultado.get('ponto_fraco_num', '')}):</strong> {resultado.get('ponto_fraco_pergunta', '')}
                        </div>
                        <div style="font-size: 13px; color: #334155;">
                            <strong>Ação Prioritária:</strong> {resultado.get('acao_prioritaria', '')}
                        </div>
                    </div>
                    
                    <p style="font-size: 14px; line-height: 1.6; color: #334155;">
                        Anexamos a este e-mail o seu <strong>Relatório Completo em PDF</strong> com as notas detalhadas dos 5 eixos metodológicos (Atrair, Engajar, Vender, Reter e Gestão).
                    </p>
                    
                    <div style="text-align: center; margin: 28px 0;">
                        <a href="{wa_url}" style="background-color: #25D366; color: #ffffff; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 14px; display: inline-block;">
                            Conversar com a NorthWay no WhatsApp
                        </a>
                    </div>
                    
                    <div style="margin-top: 32px; padding-top: 16px; border-top: 1px solid #E2E8F0; font-size: 12px; color: #94A3B8; text-align: center;">
                        NorthWay Company · northwaycompany.com.br
                    </div>
                </div>
                """

                filename_clean = (empresa or 'NorthWay').replace(' ', '_').replace('/', '_')
                attachments = [{
                    "filename": f"RaioX-NorthWay-{filename_clean}.pdf",
                    "content": list(pdf_bytes)
                }]

                EmailService.send_email(
                    to=[email],
                    subject=f"Seu Raio-X NorthWay está pronto | {empresa or nome} (Índice {resultado.get('indice_formatado', '0')}/10)",
                    html_content=email_html,
                    company_id=company_id,
                    attachments=attachments
                )
                logger.info(f"E-mail com PDF do Raio-X v2 disparado via Resend para {email}")
            except Exception as email_err:
                logger.error(f"Erro ao enviar e-mail com PDF via Resend: {email_err}")

        # Armazena na sessão caso o usuário queira recarregar
        session['raiox_resultado'] = resultado

        # 7. Retorno em JSON para renderização instantânea na mesma página
        return jsonify({
            'status': 'success',
            'resultado': resultado
        })
        
    except Exception as e:
        logger.error(f"Erro ao processar Raio-X v2: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500


@diagnostic_raiox_bp.route('/raiox/resultado', methods=['GET'])
def resultado():
    """
    Fallback para visualização de resultados de sessão (se acessado diretamente)
    """
    res = session.get('raiox_resultado')
    if not res:
        return redirect(url_for('diagnostic_raiox.index'))
    return render_template('forms/raiox_resultado.html', res=res)


@diagnostic_raiox_bp.route('/raiox/leads', methods=['GET'])
@login_required
def leads_list():
    """
    Lista todos os leads que fizeram o Raio-X Digital
    """
    leads = (Lead.query
             .filter(Lead.source == 'Raio-X Digital')
             .filter(Lead.diagnostic_status == 'done')
             .order_by(Lead.diagnostic_date.desc())
             .all())

    clean_leads = []
    for l in leads:
        if isinstance(l.diagnostic_pillars, dict):
            l.diagnostic_pillars = {k: v for k, v in l.diagnostic_pillars.items() if not k.startswith('_')}
        clean_leads.append(l)

    return render_template('forms/raiox_leads.html', leads=clean_leads)


@diagnostic_raiox_bp.route('/raiox/report/<int:lead_id>', methods=['GET'])
@login_required
def report(lead_id):
    """
    Relatório administrativo do lead no CRM
    """
    mode = request.args.get('mode', 'simple')
    lead = Lead.query.filter_by(id=lead_id, company_id=current_user.company_id).first_or_404()
    if lead.source != 'Raio-X Digital' or lead.diagnostic_status != 'done':
        return redirect(url_for('diagnostic_raiox.leads_list'))

    return render_template(
        'forms/raiox_report.html',
        lead=lead,
        questions=RAIOX_QUESTIONS,
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
    lead.origem = None
    lead.respostas = None
    lead.gargalo = None
    lead.ponto_fraco = None
    lead.source = None
    lead.interest = None
    db.session.commit()

    return jsonify({'status': 'success'})
