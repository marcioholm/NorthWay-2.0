from flask import Blueprint, render_template, request, jsonify, redirect, url_for, session
from flask_login import login_required, current_user
from models import db, Lead, Company, Pipeline, PipelineStage
from extensions import limiter
from datetime import datetime
import json
import logging
import os
import uuid
import urllib.parse
from sqlalchemy import text, or_
from utils.phone import normalize_phone

diagnostic_raiox_bp = Blueprint('diagnostic_raiox', __name__)
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------------
# Configuração dos 5 Eixos e 20 Perguntas Exatas da Metodologia NorthWay v2
# -------------------------------------------------------------------------
RAIOX_QUESTIONS = [
    # ATRAIR (1-4)
    {
        "id": 1, "eixo": "atrair", "eixo_nome": "Atrair",
        "pergunta": "Você sabe quem é o seu cliente ideal?",
        "opcoes": [
            {"value": 0, "label": "Não, atendo quem aparecer"},
            {"value": 1, "label": "Tenho uma ideia, mas nunca coloquei no papel"},
            {"value": 2, "label": "Sei bem: perfil, região e o que ele procura"},
            {"value": 3, "label": "Sei e uso isso para decidir onde e como divulgar"},
        ],
        "acao": "Escreva em uma página quem é o seu cliente ideal: perfil, problema que quer resolver e onde procura solução. Use isso como base de toda a divulgação do mês."
    },
    {
        "id": 2, "eixo": "atrair", "eixo_nome": "Atrair",
        "pergunta": "Quando alguém procura sua empresa no Google, encontra?",
        "opcoes": [
            {"value": 0, "label": "Não aparece, ou não sei"},
            {"value": 1, "label": "Aparece, mas com informação desatualizada ou sem fotos"},
            {"value": 2, "label": "Aparece com perfil completo (endereço, horário, fotos)"},
            {"value": 3, "label": "Perfil completo e com avaliações recentes respondidas"},
        ],
        "acao": "Crie ou atualize o Perfil da Empresa no Google (endereço, horário, fotos, telefone) e peça avaliação a 5 clientes satisfeitos."
    },
    {
        "id": 3, "eixo": "atrair", "eixo_nome": "Atrair",
        "pergunta": "Com que frequência sua empresa divulga (posts ou anúncios)?",
        "opcoes": [
            {"value": 0, "label": "Quase nunca"},
            {"value": 1, "label": "Quando sobra tempo, sem regularidade"},
            {"value": 2, "label": "Toda semana, com frequência definida"},
            {"value": 3, "label": "Toda semana, com calendário, e acompanho o resultado"},
        ],
        "acao": "Monte um calendário de 4 semanas com 2 ações de divulgação por semana e cumpra até o fim do mês."
    },
    {
        "id": 4, "eixo": "atrair", "eixo_nome": "Atrair",
        "pergunta": "Você sabe de onde vêm os seus novos clientes?",
        "opcoes": [
            {"value": 0, "label": "Não sei"},
            {"value": 1, "label": "Tenho um palpite (\"acho que é pelo Instagram\")"},
            {"value": 2, "label": "Pergunto ou anoto a origem da maioria"},
            {"value": 3, "label": "Anoto a origem de todos e sei quantos cada canal traz"},
        ],
        "acao": "Pergunte a todo cliente novo \"como você conheceu a gente?\" e registre a resposta por 30 dias."
    },
    # ENGAJAR (5-8)
    {
        "id": 5, "eixo": "engajar", "eixo_nome": "Engajar",
        "pergunta": "Está claro na sua divulgação por que o cliente deve escolher você e não o concorrente?",
        "opcoes": [
            {"value": 0, "label": "Não sei explicar meu diferencial"},
            {"value": 1, "label": "Sei explicar, mas não aparece na divulgação"},
            {"value": 2, "label": "Aparece na divulgação de vez em quando"},
            {"value": 3, "label": "Aparece sempre, e os clientes repetem esse motivo"},
        ],
        "acao": "Escreva em uma frase por que o cliente deveria comprar de você e não do concorrente. Use essa frase na bio, no atendimento e nos conteúdos."
    },
    {
        "id": 6, "eixo": "engajar", "eixo_nome": "Engajar",
        "pergunta": "Além de ofertas, você publica coisas que fazem o cliente confiar em você? (bastidores, explicações, resultados de clientes)",
        "opcoes": [
            {"value": 0, "label": "Só publico ofertas e preços, ou não publico"},
            {"value": 1, "label": "De vez em quando"},
            {"value": 2, "label": "Toda semana"},
            {"value": 3, "label": "Toda semana, e sei quais conteúdos trazem mais contatos"},
        ],
        "acao": "Publique por semana pelo menos 1 conteúdo de bastidor, explicação ou prova de resultado, sem oferta."
    },
    {
        "id": 7, "eixo": "engajar", "eixo_nome": "Engajar",
        "pergunta": "Sua empresa mostra depoimentos ou avaliações de clientes?",
        "opcoes": [
            {"value": 0, "label": "Não"},
            {"value": 1, "label": "Tenho alguns, mas quase não uso"},
            {"value": 2, "label": "Peço e publico com frequência"},
            {"value": 3, "label": "Peço a todo cliente e tenho avaliações recentes no Google e nas redes"},
        ],
        "acao": "Peça avaliação a 10 clientes satisfeitos e publique as que forem autorizadas."
    },
    {
        "id": 8, "eixo": "engajar", "eixo_nome": "Engajar",
        "pergunta": "Você guarda os contatos de clientes e interessados para falar com eles depois?",
        "opcoes": [
            {"value": 0, "label": "Não guardo"},
            {"value": 1, "label": "Ficam espalhados no celular e no WhatsApp"},
            {"value": 2, "label": "Tenho uma lista organizada (planilha ou sistema)"},
            {"value": 3, "label": "Lista organizada, e mando novidades com frequência"},
        ],
        "acao": "Organize todos os interessados em uma lista única (etiquetas do WhatsApp Business ou planilha), com data e o que pediram."
    },
    # VENDER (9-12)
    {
        "id": 9, "eixo": "vender", "eixo_nome": "Vender",
        "pergunta": "Quando alguém pede orçamento ou informação, existe um passo a passo de atendimento?",
        "opcoes": [
            {"value": 0, "label": "Não, cada um atende do seu jeito"},
            {"value": 1, "label": "Existe na minha cabeça, mas não está escrito"},
            {"value": 2, "label": "Existe e está escrito (roteiro, mensagens prontas)"},
            {"value": 3, "label": "Está escrito, todos seguem, e eu acompanho"},
        ],
        "acao": "Escreva o passo a passo do atendimento, do primeiro contato ao fechamento, e siga em todos os atendimentos do mês."
    },
    {
        "id": 10, "eixo": "vender", "eixo_nome": "Vender",
        "pergunta": "Quanto tempo vocês levam para responder um novo contato?",
        "opcoes": [
            {"value": 0, "label": "Mais de um dia, ou às vezes nem respondemos"},
            {"value": 1, "label": "Algumas horas"},
            {"value": 2, "label": "Menos de 1 hora, no horário comercial"},
            {"value": 3, "label": "Poucos minutos, e eu acompanho esse tempo"},
        ],
        "acao": "Defina horários fixos para responder mensagens e um prazo máximo de resposta. Cumpra por 30 dias."
    },
    {
        "id": 11, "eixo": "vender", "eixo_nome": "Vender",
        "pergunta": "Se a pessoa não fecha na hora, alguém volta a falar com ela?",
        "opcoes": [
            {"value": 0, "label": "Não, esperamos ela voltar"},
            {"value": 1, "label": "Às vezes, quando lembramos"},
            {"value": 2, "label": "Sim, sempre voltamos a falar em dias combinados"},
            {"value": 3, "label": "Sim, com datas definidas, anotando o resultado de cada retorno"},
        ],
        "acao": "Reserve 15 minutos por dia para retomar contato com quem pediu orçamento ou informação e não fechou."
    },
    {
        "id": 12, "eixo": "vender", "eixo_nome": "Vender",
        "pergunta": "Onde fica anotado quem pediu orçamento e em que etapa cada um está?",
        "opcoes": [
            {"value": 0, "label": "Em lugar nenhum, fica na memória"},
            {"value": 1, "label": "Só nas conversas do WhatsApp"},
            {"value": 2, "label": "Numa planilha ou caderno organizado"},
            {"value": 3, "label": "Num sistema de vendas (CRM) que toda a equipe atualiza"},
        ],
        "acao": "Registre todo lead numa planilha ou CRM com etapa e data do próximo contato. Comece simples."
    },
    # RETER (13-16)
    {
        "id": 13, "eixo": "reter", "eixo_nome": "Reter",
        "pergunta": "Depois da venda, sua empresa volta a falar com o cliente?",
        "opcoes": [
            {"value": 0, "label": "Não"},
            {"value": 1, "label": "Só se ele chamar ou tiver problema"},
            {"value": 2, "label": "Sim, para saber se ficou satisfeito"},
            {"value": 3, "label": "Sim, em datas planejadas, e anotamos o retorno"},
        ],
        "acao": "Crie uma mensagem de pós-venda e envie a todo cliente de 3 a 7 dias depois da compra."
    },
    {
        "id": 14, "eixo": "reter", "eixo_nome": "Reter",
        "pergunta": "Você faz alguma ação para o cliente comprar de novo?",
        "opcoes": [
            {"value": 0, "label": "Não"},
            {"value": 1, "label": "Às vezes mando uma promoção"},
            {"value": 2, "label": "Tenho ações frequentes (lembretes, ofertas para quem já comprou)"},
            {"value": 3, "label": "Ações frequentes, e sei quantos clientes voltaram por causa delas"},
        ],
        "acao": "Crie uma ação simples de recompra (lembrete de reposição, benefício para cliente da casa) e teste durante o mês."
    },
    {
        "id": 15, "eixo": "reter", "eixo_nome": "Reter",
        "pergunta": "Você pede para seus clientes indicarem sua empresa?",
        "opcoes": [
            {"value": 0, "label": "Não peço"},
            {"value": 1, "label": "Peço de vez em quando"},
            {"value": 2, "label": "Peço para todo cliente satisfeito"},
            {"value": 3, "label": "Peço sempre, e controlo quem indicou quem (com ou sem benefício)"},
        ],
        "acao": "Peça indicação a cada cliente satisfeito, usando sempre a mesma frase simples."
    },
    {
        "id": 16, "eixo": "reter", "eixo_nome": "Reter",
        "pergunta": "Você sabe quantos clientes voltaram a comprar nos últimos 3 meses?",
        "opcoes": [
            {"value": 0, "label": "Não faço ideia"},
            {"value": 1, "label": "Tenho uma noção"},
            {"value": 2, "label": "Consigo levantar esse número se precisar"},
            {"value": 3, "label": "Sei o número e acompanho todo mês"},
        ],
        "acao": "Levante quantos clientes compraram mais de uma vez nos últimos 6 meses. Esse é o seu ponto de partida."
    },
    # GESTÃO (17-20)
    {
        "id": 17, "eixo": "gestao", "eixo_nome": "Gestão",
        "pergunta": "Você sabe se a empresa deu lucro no mês passado, depois de pagar tudo, inclusive o seu salário?",
        "opcoes": [
            {"value": 0, "label": "Não sei"},
            {"value": 1, "label": "Tenho uma ideia pelo saldo da conta"},
            {"value": 2, "label": "Sei, faço essa conta todo mês"},
            {"value": 3, "label": "Sei, e comparo com os meses anteriores para tomar decisões"},
        ],
        "acao": "Preencha a DRE dos últimos 3 meses, incluindo o pró-labore, e veja se o negócio está acima do ponto de equilíbrio."
    },
    {
        "id": 18, "eixo": "gestao", "eixo_nome": "Gestão",
        "pergunta": "Sua empresa tem meta de vendas?",
        "opcoes": [
            {"value": 0, "label": "Não temos meta"},
            {"value": 1, "label": "Tenho um valor na cabeça"},
            {"value": 2, "label": "Temos meta mensal definida"},
            {"value": 3, "label": "Meta mensal definida e acompanhada toda semana"},
        ],
        "acao": "Defina a meta de vendas do mês de trás para frente (lucro → faturamento → vendas → atendimentos) e confira toda semana."
    },
    {
        "id": 19, "eixo": "gestao", "eixo_nome": "Gestão",
        "pergunta": "Você acompanha os números de vendas: quantos pediram orçamento, quantos compraram e o valor médio de cada venda?",
        "opcoes": [
            {"value": 0, "label": "Não acompanho"},
            {"value": 1, "label": "Só sei o total vendido"},
            {"value": 2, "label": "Acompanho alguns desses números"},
            {"value": 3, "label": "Acompanho todos, todo mês"},
        ],
        "acao": "Registre por 30 dias cada atendimento e se virou venda. No fim do mês, calcule conversão e ticket médio."
    },
    {
        "id": 20, "eixo": "gestao", "eixo_nome": "Gestão",
        "pergunta": "Seu site ou seus anúncios medem quantas pessoas visitam e entram em contato? (ex.: Pixel do Facebook, Google Analytics)",
        "opcoes": [
            {"value": 0, "label": "Não tenho site nem anúncio, ou não sei"},
            {"value": 1, "label": "Tenho, mas não sei se mede"},
            {"value": 2, "label": "Mede, está instalado"},
            {"value": 3, "label": "Mede, e eu olho os números para tomar decisões"},
        ],
        "acao": "Instale o Pixel da Meta e o Google Analytics no site ou na página de vendas e confira se registram visitas."
    }
]

RAIOX_V3_QUESTIONS = {
    "1": {
        "id": 1,
        "area": "Atrair",
        "eixo": "atrair",
        "curto": "Cliente ideal",
        "pergunta": "Você sabe quem é o seu cliente ideal?",
        "opcoes": [
            "Não, atendo quem aparecer",
            "Tenho uma ideia, mas nunca coloquei no papel",
            "Sei bem: perfil, região e o que ele procura",
            "Sei e uso isso para decidir onde e como divulgar",
        ],
        "acao": "Escreva em uma página quem é o cliente que mais dá lucro e menos dá trabalho, o que ele procura e onde costuma estar. Use isso para ajustar sua comunicação e seus anúncios.",
    },
    "2": {
        "id": 2,
        "area": "Atrair",
        "eixo": "atrair",
        "curto": "Presença no Google",
        "pergunta": "Quando alguém procura sua empresa no Google, encontra?",
        "opcoes": [
            "Não aparece, ou não sei",
            "Aparece, mas com informação desatualizada ou sem fotos",
            "Aparece com perfil completo (endereço, horário, fotos)",
            "Perfil completo e com avaliações recentes respondidas",
        ],
        "acao": "Atualize hoje o Perfil da Empresa no Google: fotos recentes, horário, endereço, WhatsApp e link para contato. Peça avaliação para os próximos 10 clientes atendidos.",
    },
    "3": {
        "id": 3,
        "area": "Atrair",
        "eixo": "atrair",
        "curto": "Frequência de divulgação",
        "pergunta": "Com que frequência sua empresa divulga (posts ou anúncios)?",
        "opcoes": [
            "Quase nunca",
            "Quando sobra tempo, sem regularidade",
            "Toda semana, com frequência definida",
            "Toda semana, com calendário, e acompanho o resultado",
        ],
        "acao": "Defina uma rotina mínima semanal de divulgação (posts + oferta clara com chamada para o WhatsApp) e acompanhe quantas conversas chegam por semana.",
    },
    "4": {
        "id": 4,
        "area": "Atrair",
        "eixo": "atrair",
        "curto": "Origem dos clientes",
        "pergunta": "Você sabe de onde vêm os seus novos clientes?",
        "opcoes": [
            "Não sei",
            "Tenho um palpite (\"acho que é pelo Instagram\")",
            "Pergunto ou anoto a origem da maioria",
            "Anoto a origem de todos e sei quantos cada canal traz",
        ],
        "acao": "Passe a perguntar e anotar em todo atendimento: 'Como nos encontrou?' (Instagram, Google, Indicação, Anúncio). Em 30 dias você saberá onde investir com segurança.",
    },
    "7": {
        "id": 7,
        "area": "Engajar",
        "eixo": "engajar",
        "curto": "Prova social",
        "pergunta": "Sua empresa mostra depoimentos ou avaliações de clientes?",
        "opcoes": [
            "Não",
            "Tenho alguns, mas quase não uso",
            "Peço e publico com frequência",
            "Peço a todo cliente e tenho avaliações recentes no Google e nas redes",
        ],
        "acao": "Envie uma mensagem curta logo após a entrega pedindo uma avaliação no Google e publique 1 depoimento por semana nos stories e no perfil.",
    },
    "9": {
        "id": 9,
        "area": "Vender",
        "eixo": "vender",
        "curto": "Passo a passo de atendimento",
        "pergunta": "Quando alguém pede orçamento, existe um passo a passo de atendimento?",
        "opcoes": [
            "Não, cada um atende do seu jeito",
            "Existe na minha cabeça, mas não está escrito",
            "Existe e está escrito (roteiro, mensagens prontas)",
            "Está escrito, todos seguem, e eu acompanho",
        ],
        "acao": "Escreva um roteiro simples de 4 passos (saudação + 3 perguntas para entender a necessidade + apresentação de valor + proposta com prazo) para toda a equipe seguir.",
    },
    "10": {
        "id": 10,
        "area": "Vender",
        "eixo": "vender",
        "curto": "Tempo de resposta",
        "pergunta": "Quanto tempo vocês levam para responder um novo contato?",
        "opcoes": [
            "Mais de um dia, ou às vezes nem respondemos",
            "Algumas horas",
            "Menos de 1 hora, no horário comercial",
            "Poucos minutos, e eu acompanho esse tempo",
        ],
        "acao": "Defina a meta de responder todo novo lead em até 10 minutos no horário comercial e ative mensagem automática imediata fora do expediente.",
    },
    "11": {
        "id": 11,
        "area": "Vender",
        "eixo": "vender",
        "curto": "Follow-up de orçamento",
        "pergunta": "Se a pessoa não fecha na hora, alguém volta a falar com ela?",
        "opcoes": [
            "Não, esperamos ela voltar",
            "Às vezes, quando lembramos",
            "Sim, sempre voltamos a falar em dias combinados",
            "Sim, com datas definidas, anotando o resultado de cada retorno",
        ],
        "acao": "Crie uma regra fixa de retorno: 1 dia, 3 dias e 7 dias após o orçamento enviado, sempre com uma pergunta útil — sem isso você perde vendas já quase fechadas.",
    },
    "12": {
        "id": 12,
        "area": "Vender",
        "eixo": "vender",
        "curto": "Controle de orçamentos",
        "pergunta": "Onde fica anotado quem pediu orçamento e em que etapa cada um está?",
        "opcoes": [
            "Em lugar nenhum, fica na memória",
            "Só nas conversas do WhatsApp",
            "Numa planilha ou caderno organizado",
            "Num sistema de vendas (CRM) que toda a equipe atualiza",
        ],
        "acao": "Centralize todos os orçamentos em um funil simples (Novo → Em conversa → Proposta enviada → Fechado/Perdido) com data de próximo contato.",
    },
    "13": {
        "id": 13,
        "area": "Reter",
        "eixo": "reter",
        "curto": "Pós-venda",
        "pergunta": "Depois da venda, sua empresa volta a falar com o cliente?",
        "opcoes": [
            "Não",
            "Só se ele chamar ou tiver problema",
            "Sim, para saber se ficou satisfeito e oferecer algo novo",
            "Sim, em datas planejadas, e sei quantos voltam a comprar",
        ],
        "acao": "Coloque um lembrete automático para 7 dias após a venda perguntando como foi a experiência e 60–90 dias para oferecer recompra ou indicação.",
    },
    "17": {
        "id": 17,
        "area": "Gestão",
        "eixo": "gestao",
        "curto": "Lucro real do mês",
        "pergunta": "Você sabe se a empresa deu lucro no mês passado, depois de pagar tudo, inclusive o seu salário?",
        "opcoes": [
            "Não sei",
            "Tenho uma ideia pelo saldo da conta",
            "Sei, faço essa conta todo mês",
            "Sei, e comparo com os meses anteriores para tomar decisões",
        ],
        "acao": "Feche um DRE simples todo dia 5: tudo o que entrou menos custos, despesas fixas e seu pró-labore. Só assim você enxerga o lucro real.",
    },
    "18": {
        "id": 18,
        "area": "Gestão",
        "eixo": "gestao",
        "curto": "Meta de vendas",
        "pergunta": "Sua empresa tem meta de vendas?",
        "opcoes": [
            "Não temos meta",
            "Tenho um valor na cabeça",
            "Temos meta mensal definida",
            "Meta mensal definida e acompanhada toda semana",
        ],
        "acao": "Defina a meta de faturamento do mês dividida por semana e acompanhe toda segunda-feira quanto já foi vendido e quanto falta.",
    },
    "19": {
        "id": 19,
        "area": "Gestão",
        "eixo": "gestao",
        "curto": "Números de vendas",
        "pergunta": "Você acompanha os números de vendas: quantos pediram orçamento, quantos compraram e o valor médio de cada venda?",
        "opcoes": [
            "Não acompanho",
            "Só sei o total vendido",
            "Acompanho alguns desses números",
            "Acompanho todos, todo mês",
        ],
        "acao": "Anote semanalmente apenas 3 números: quantos orçamentos chegaram, quantos fecharam e o ticket médio. Com eles você sabe onde está o gargalo do caixa.",
    },
    "21": {
        "id": 21,
        "area": "Gestão",
        "eixo": "gestao",
        "curto": "Separação PF/PJ",
        "pergunta": "O dinheiro da empresa e o seu dinheiro pessoal ficam separados?",
        "opcoes": [
            "Não, é tudo junto",
            "Tenho conta da empresa, mas misturo bastante",
            "Separado, e eu tiro um valor fixo por mês",
            "Separado, com pró-labore fixo e controle de entradas e saídas",
        ],
        "acao": "Abra (ou passe a usar só) uma conta da empresa para tudo o que entra e sai do negócio e defina um pró-labore fixo mensal para você. Sem isso, não dá para saber se a empresa dá lucro.",
    },
    "22": {
        "id": 22,
        "area": "Gestão",
        "eixo": "gestao",
        "curto": "Formação de preço",
        "pergunta": "Como você define o preço do que vende?",
        "opcoes": [
            "Copio o preço do concorrente ou chuto",
            "Custo mais uma porcentagem, sem considerar despesas fixas",
            "Calculo com custos, despesas e impostos",
            "Calculo com custos, despesas, impostos e a margem de lucro que eu quero",
        ],
        "acao": "Liste custo do produto/serviço, despesas fixas do mês, impostos e taxas. Calcule o preço mínimo que cobre tudo e acrescente a margem desejada. Revise os 5 itens que você mais vende.",
    },
}

RAIOX_V3_PATHS = {
    "marketing": {
        "key": "marketing",
        "label": "Atrair clientes",
        "area": "Marketing",
        "eixo": "atrair",
        "ids": [1, 2, 3, 4, 7],
    },
    "comercial": {
        "key": "comercial",
        "label": "Vender",
        "area": "Comercial",
        "eixo": "vender",
        "ids": [10, 9, 11, 12, 13],
    },
    "gestao": {
        "key": "gestao",
        "label": "Organizar a empresa",
        "area": "Gestão",
        "eixo": "gestao",
        "ids": [17, 21, 18, 19, 22],
    },
    "geral": {
        "key": "geral",
        "label": "Diagnóstico Geral",
        "area": "Geral",
        "eixo": "geral",
        "ids": [4, 7, 10, 13, 17],
    },
}


def calculate_raiox_v3(path_key, raw_answers):
    """
    Calcula o resultado do Raio-X v3 (1 + 5 perguntas).
    Nota da área = soma / 15 * 10 (1 casa decimal).
    """
    path = RAIOX_V3_PATHS.get(path_key) or RAIOX_V3_PATHS["geral"]
    q_ids = path["ids"]

    ans_map = {}
    if isinstance(raw_answers, dict):
        for qid in q_ids:
            val = raw_answers.get(str(qid), raw_answers.get(qid, 0))
            ans_map[str(qid)] = max(0, min(3, safe_int(val, 0)))
    elif isinstance(raw_answers, list):
        for idx, qid in enumerate(q_ids):
            val = raw_answers[idx] if idx < len(raw_answers) else 0
            ans_map[str(qid)] = max(0, min(3, safe_int(val, 0)))
    else:
        for qid in q_ids:
            ans_map[str(qid)] = 0

    soma = sum(ans_map[str(qid)] for qid in q_ids)
    nota = round((soma / 15.0) * 10.0, 1)
    nota_formatada = f"{nota:.1f}".replace(".", ",")

    # Ponto mais urgente: pergunta com menor nota (empate: primeira na ordem do caminho)
    urg_qid = min(q_ids, key=lambda qid: ans_map[str(qid)])
    urg_q = RAIOX_V3_QUESTIONS[str(urg_qid)]

    # Calcula notas por eixo quando disponíveis
    eixos_vals = {"atrair": [], "engajar": [], "vender": [], "reter": [], "gestao": []}
    detalhes = []
    for qid in q_ids:
        q = RAIOX_V3_QUESTIONS[str(qid)]
        val = ans_map[str(qid)]
        eixos_vals[q["eixo"]].append(val)
        detalhes.append({
            "id": qid,
            "curto": q["curto"],
            "area": q["area"],
            "eixo": q["eixo"],
            "pergunta": q["pergunta"],
            "valor": val,
            "resposta": q["opcoes"][val],
        })

    notas_eixos = {}
    for eixo_k, vals in eixos_vals.items():
        if vals:
            notas_eixos[eixo_k] = round((sum(vals) / (3.0 * len(vals))) * 10.0, 1)
        else:
            notas_eixos[eixo_k] = None

    if path["key"] == "geral":
        gargalo_eixo = urg_q["eixo"]
        gargalo_nome = urg_q["area"]
        gargalo_nota = notas_eixos.get(gargalo_eixo) if notas_eixos.get(gargalo_eixo) is not None else nota
    else:
        gargalo_eixo = path["eixo"]
        gargalo_nome = path["area"]
        gargalo_nota = nota

    gargalo_nota_formatada = f"{gargalo_nota:.1f}".replace(".", ",")

    return {
        "version": "v3",
        "caminho": path["key"],
        "caminho_label": path["label"],
        "area_nome": path["area"],
        "soma": soma,
        "nota": nota,
        "nota_formatada": nota_formatada,
        "indice": nota,
        "indice_formatado": nota_formatada,
        "notas": {
            "atrair": notas_eixos["atrair"] if notas_eixos["atrair"] is not None else 0.0,
            "engajar": notas_eixos["engajar"] if notas_eixos["engajar"] is not None else 0.0,
            "vender": notas_eixos["vender"] if notas_eixos["vender"] is not None else 0.0,
            "reter": notas_eixos["reter"] if notas_eixos["reter"] is not None else 0.0,
            "gestao": notas_eixos["gestao"] if notas_eixos["gestao"] is not None else 0.0,
        },
        "gargalo": gargalo_eixo,
        "gargalo_nome": gargalo_nome,
        "gargalo_nota": gargalo_nota,
        "gargalo_nota_formatada": gargalo_nota_formatada,
        "ponto_fraco_num": urg_qid,
        "urgente_id": urg_qid,
        "urgente_curto": urg_q["curto"],
        "urgente_area": urg_q["area"],
        "urgente_pergunta": urg_q["pergunta"],
        "urgente_valor": ans_map[str(urg_qid)],
        "ponto_fraco_pergunta": urg_q["pergunta"],
        "acao_prioritaria": urg_q["acao"],
        "respostas_dict": ans_map,
        "detalhes": detalhes,
    }

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
            ("consentimento_em", "TIMESTAMP"),
            ("raiox_token", "VARCHAR(100)"),
            ("raiox_status", "VARCHAR(50)"),
            ("raiox_ultima_pergunta", "INTEGER"),
            ("raiox_respostas_parciais", "JSONB" if is_postgres else "TEXT"),
            ("raiox_atualizado_em", "TIMESTAMP"),
            ("utm_source", "VARCHAR(255)"),
            ("utm_medium", "VARCHAR(255)"),
            ("utm_campaign", "VARCHAR(255)"),
            ("utm_content", "VARCHAR(255)"),
            ("utm_term", "VARCHAR(255)"),
            ("fbclid", "VARCHAR(255)"),
            ("meta_event_id", "VARCHAR(100)"),
            ("raiox_whatsapp_status", "VARCHAR(30)"),
            ("raiox_whatsapp_em", "TIMESTAMP"),
            ("raiox_recuperacao_em", "TIMESTAMP"),
            ("opt_out", "BOOLEAN DEFAULT FALSE")
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

            try:
                if is_postgres:
                    conn.execute(text('CREATE INDEX IF NOT EXISTS ix_lead_raiox_token ON "lead" (raiox_token)'))
                else:
                    conn.execute(text('CREATE INDEX IF NOT EXISTS ix_lead_raiox_token ON "lead" (raiox_token)'))
                conn.commit()
            except Exception:
                conn.rollback()

            # Tabela de sessões anônimas do funil Raio-X v3
            try:
                pk_def = "SERIAL PRIMARY KEY" if is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
                conn.execute(text(f"""
                    CREATE TABLE IF NOT EXISTS raiox_sessions (
                        id {pk_def},
                        session_token VARCHAR(100) UNIQUE NOT NULL,
                        caminho VARCHAR(30),
                        etapa_maxima VARCHAR(30) DEFAULT 'abriu',
                        etapa_ordem INTEGER DEFAULT 0,
                        respostas_json TEXT,
                        lead_id INTEGER,
                        origem VARCHAR(100),
                        utm_source VARCHAR(255),
                        utm_medium VARCHAR(255),
                        utm_campaign VARCHAR(255),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_raiox_sessions_created_at ON raiox_sessions (created_at)'))
                conn.execute(text('CREATE INDEX IF NOT EXISTS ix_raiox_sessions_etapa ON raiox_sessions (etapa_maxima)'))
                conn.commit()
            except Exception as ex_sess:
                logger.warning(f"ensure_raiox_v2_columns raiox_sessions: {ex_sess}")
                conn.rollback()

            # Limpeza de leads de teste (Critério de aceite)
            try:
                conn.execute(text("DELETE FROM \"lead\" WHERE email = 'teste.claude@exemplo.com' OR name = 'TESTE Claude - apagar'"))
                conn.commit()
            except Exception:
                conn.rollback()
    except Exception as e:
        logger.warning(f"ensure_raiox_v2_columns: {e}")


RAIOX_SESSION_STAGE_ORDER = {
    'abriu': 0,
    'inicio': 1,
    'iniciou': 1,
    'p1': 2,
    'p2': 3,
    'p3': 4,
    'p4': 5,
    'p5': 6,
    'dados': 7,
    'concluido': 8,
}


def upsert_raiox_session(
    token,
    caminho=None,
    etapa=None,
    answers=None,
    lead_id=None,
    origem=None,
    utm_source=None,
    utm_medium=None,
    utm_campaign=None,
):
    """
    Registra/atualiza o progresso anônimo da sessão no funil Raio-X.
    Mantém sempre a etapa mais avançada atingida (etapa_maxima / etapa_ordem).
    """
    if not token:
        return
    try:
        etapa_norm = (str(etapa or 'abriu').strip().lower()) or 'abriu'
        if etapa_norm in RAIOX_SESSION_STAGE_ORDER:
            etapa_ordem = RAIOX_SESSION_STAGE_ORDER[etapa_norm]
            if etapa_norm == 'iniciou':
                etapa_norm = 'inicio'
        else:
            # Fallback para etapas numéricas (v2)
            try:
                q_n = int(etapa_norm)
                etapa_norm = f"p{q_n}" if q_n <= 5 else "dados"
                etapa_ordem = min(6, max(1, q_n + 1))
            except ValueError:
                etapa_norm = 'abriu'
                etapa_ordem = 0

        respostas_str = json.dumps(answers, ensure_ascii=False) if answers is not None else None
        agora = datetime.utcnow()

        row = db.session.execute(
            text("SELECT id, etapa_ordem, etapa_maxima, caminho, respostas_json, lead_id FROM raiox_sessions WHERE session_token = :tok"),
            {"tok": token},
        ).fetchone()

        if not row:
            db.session.execute(
                text("""
                    INSERT INTO raiox_sessions (
                        session_token, caminho, etapa_maxima, etapa_ordem,
                        respostas_json, lead_id, origem, utm_source, utm_medium, utm_campaign,
                        created_at, updated_at
                    ) VALUES (
                        :tok, :caminho, :etapa, :ordem,
                        :resp, :lead_id, :origem, :us, :um, :uc,
                        :agora, :agora
                    )
                """),
                {
                    "tok": token,
                    "caminho": caminho,
                    "etapa": etapa_norm,
                    "ordem": etapa_ordem,
                    "resp": respostas_str,
                    "lead_id": lead_id,
                    "origem": origem,
                    "us": utm_source,
                    "um": utm_medium,
                    "uc": utm_campaign,
                    "agora": agora,
                },
            )
        else:
            curr_ordem = row[1] if row[1] is not None else 0
            new_etapa = etapa_norm if etapa_ordem >= curr_ordem else row[2]
            new_ordem = max(curr_ordem, etapa_ordem)
            new_caminho = caminho or row[3]
            new_resp = respostas_str if respostas_str is not None else row[4]
            new_lead_id = lead_id if lead_id is not None else row[5]

            db.session.execute(
                text("""
                    UPDATE raiox_sessions
                    SET caminho = :caminho,
                        etapa_maxima = :etapa,
                        etapa_ordem = :ordem,
                        respostas_json = :resp,
                        lead_id = :lead_id,
                        updated_at = :agora
                    WHERE session_token = :tok
                """),
                {
                    "tok": token,
                    "caminho": new_caminho,
                    "etapa": new_etapa,
                    "ordem": new_ordem,
                    "resp": new_resp,
                    "lead_id": new_lead_id,
                    "agora": agora,
                },
            )
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.warning(f"upsert_raiox_session: {e}")

# -------------------------------------------------------------------------
# Rotas
# -------------------------------------------------------------------------

N8N_RAIOX_PRODUCTION_WEBHOOK = "https://n8n.vps11962.panel.icontainer.work/webhook/raiox-concluido"

def get_n8n_raiox_webhook_url():
    """
    Retorna a URL oficial de webhook do n8n para conclusão do Raio-X.
    Prioriza https://n8n.vps11962.panel.icontainer.work/webhook/raiox-concluido e rejeita
    URLs de teste (/webhook-test/) ou domínios não resolvidos.
    """
    try:
        from models import IntegrationWebhook
        wh = IntegrationWebhook.query.filter_by(company_id=35, name='raiox_concluido').first()
        if wh and wh.url and 'webhook' in wh.url and 'webhook-test' not in wh.url and 'northwaycompany.co' not in wh.url:
            return wh.url.strip()
    except Exception:
        pass

    env_url = (os.environ.get('N8N_RAIOX_WEBHOOK_URL') or '').strip()
    if env_url and 'webhook-test' not in env_url and 'northwaycompany.co' not in env_url:
        return env_url

    return N8N_RAIOX_PRODUCTION_WEBHOOK

def dispatch_n8n_raiox_webhook(lead, payload):
    """
    Dispara webhook de conclusão do Raio-X para o n8n no backend.
    Executa de forma síncrona com timeout de 5s para garantir entrega em ambiente Serverless (Vercel).
    Registra status HTTP, URL de destino e resposta detalhada nos logs e no banco.
    """
    webhook_url = get_n8n_raiox_webhook_url()
    logger.info(f"[N8N_RAIOX] Iniciando disparo de webhook para lead_id={lead.id} na URL: {webhook_url}")

    try:
        from utils.webhooks import send_outbound_webhook
        success, resp_payload, err_msg = send_outbound_webhook(
            tenant_id=lead.company_id or 35,
            lead_id=lead.id,
            action='raiox_concluido',
            webhook_url=webhook_url,
            payload=payload,
            timeout=5,
            max_retries=2
        )
        if success:
            logger.info(f"[N8N_RAIOX] SUCESSO HTTP: Webhook entregue com sucesso ao n8n para lead {lead.id}. Resposta: {resp_payload}")
        else:
            logger.error(f"[N8N_RAIOX] ERRO ao entregar webhook n8n para lead {lead.id}. Erro: {err_msg} | Resposta: {resp_payload}")
        return success, resp_payload, err_msg
    except Exception as e:
        logger.error(f"[N8N_RAIOX] EXCEÇÃO inesperada ao disparar webhook para n8n: {e}", exc_info=True)
        return False, None, str(e)


def get_raiox_company_and_pipeline():
    """
    Retorna a empresa oficial NorthWay e o primeiro estágio do seu Funil de Vendas.
    Prioriza a NorthWay Company (ID 35).
    """
    company = (
        Company.query.filter_by(id=35).first()
        or Company.query.filter(Company.name.ilike('%NorthWay Company%')).first()
        or Company.query.filter(Company.name.ilike('%NorthWay%')).first()
        or Company.query.first()
    )
    company_id = company.id if company else 35

    pipeline = (
        Pipeline.query.filter_by(company_id=company_id, name='Funil de Vendas').first()
        or Pipeline.query.filter_by(company_id=company_id).first()
        or Pipeline.query.first()
    )
    pipeline_id = pipeline.id if pipeline else None

    stage_id = None
    if pipeline:
        first_stage = PipelineStage.query.filter_by(pipeline_id=pipeline.id).order_by(PipelineStage.order.asc()).first()
        if first_stage:
            stage_id = first_stage.id

    return company_id, pipeline_id, stage_id


@diagnostic_raiox_bp.route('/privacidade', methods=['GET'])
def privacidade():
    """
    Página de transparência e Política de Privacidade do Raio-X
    """
    return render_template('legal/privacy.html')


@diagnostic_raiox_bp.route('/raiox', methods=['GET'])
def index():
    """
    Renderiza a Landing Page / Funil do Raio-X NorthWay v2
    Suporta retomada com ?retomar=<token>
    """
    ensure_raiox_v2_columns()
    origem = request.args.get('origem', 'direto')
    retomar_token = request.args.get('retomar')
    resume_data = None
    if retomar_token:
        lead = Lead.query.filter_by(raiox_token=retomar_token).first()
        if lead and lead.raiox_status != 'concluido':
            resume_data = {
                'token': lead.raiox_token,
                'nome': lead.name or '',
                'email': lead.email or '',
                'whatsapp': lead.phone or lead.whatsapp or '',
                'empresa': lead.raiox_empresa or lead.legal_name or '',
                'quantidade_funcionarios': lead.funcionarios or '',
                'faturamento_mensal': lead.faixa_faturamento or '',
                'origem': lead.origem or 'direto',
                'respostas': lead.raiox_respostas_parciais or [],
                'ultima_pergunta': lead.raiox_ultima_pergunta or 0
            }

    whatsapp_number = os.environ.get('NORTHWAY_WHATSAPP', '5542999896358').replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
    return render_template(
        'forms/raiox_funnel.html',
        origem=origem,
        whatsapp_number=whatsapp_number,
        questions=RAIOX_QUESTIONS,
        v3_questions=RAIOX_V3_QUESTIONS,
        v3_paths=RAIOX_V3_PATHS,
        resume_data=resume_data
    )


@diagnostic_raiox_bp.route('/raiox/progresso', methods=['POST'])
@limiter.limit("60 per minute")
def progresso():
    """
    Captura progressiva do Raio-X NorthWay.
    Sempre registra a sessão anônima em raiox_sessions.
    Só cria/atualiza Lead no CRM quando há WhatsApp ou Nome+E-mail.
    """
    try:
        ensure_raiox_v2_columns()
        data = request.json or {}
        token = (data.get('token') or '').strip()
        if not token:
            return jsonify({'status': 'error', 'message': 'Token obrigatório'}), 400

        etapa = str(data.get('etapa') or '').strip()
        caminho = (data.get('path') or data.get('caminho') or '').strip() or None
        lead_info = data.get('lead_info') or {}
        answers = data.get('answers')

        nome = (lead_info.get('nome') or '').strip()
        email = (lead_info.get('email') or '').strip().lower()
        raw_whatsapp = (lead_info.get('whatsapp') or '').strip()
        whatsapp = normalize_phone(raw_whatsapp)
        empresa = (lead_info.get('empresa') or '').strip()
        funcionarios = lead_info.get('quantidade_funcionarios')
        faixa_faturamento = lead_info.get('faturamento_mensal')
        origem = (lead_info.get('origem') or request.args.get('origem') or lead_info.get('utm_source') or 'direto').strip()

        # UTMs e Meta Event ID
        utm_source = lead_info.get('utm_source')
        utm_medium = lead_info.get('utm_medium')
        utm_campaign = lead_info.get('utm_campaign')
        utm_content = lead_info.get('utm_content')
        utm_term = lead_info.get('utm_term')
        fbclid = lead_info.get('fbclid')
        meta_event_id = (data.get('event_id') or lead_info.get('event_id') or f"lead_{uuid.uuid4().hex[:16]}").strip()

        # Sempre grava progresso anônimo da sessão (sem exigir dados pessoais)
        upsert_raiox_session(
            token=token,
            caminho=caminho,
            etapa=etapa or 'abriu',
            answers=answers,
            origem=origem,
            utm_source=utm_source,
            utm_medium=utm_medium,
            utm_campaign=utm_campaign,
        )

        company_id, _, _ = get_raiox_company_and_pipeline()

        lead = Lead.query.filter_by(raiox_token=token).first()
        if not lead and email:
            lead = Lead.query.filter_by(email=email).first()
        if not lead and whatsapp:
            lead = Lead.query.filter_by(whatsapp=whatsapp).first()
            if not lead:
                lead = Lead.query.filter_by(phone=whatsapp).first()

        # Só cria novo Lead quando o usuário já informou WhatsApp (ou Nome + Email)
        has_contact = bool(whatsapp) or bool(nome and email)
        if not lead and not has_contact:
            return jsonify({'status': 'ok', 'session_only': True})

        is_new = False
        if not lead:
            lead = Lead(
                company_id=company_id,
                name=nome or (f"Lead {whatsapp}" if whatsapp else "Lead Raio-X"),
                source='Raio-X Digital (parcial)',
                pipeline_id=None,
                pipeline_stage_id=None,
                raiox_token=token,
                raiox_status='parcial_dados'
            )
            is_new = True

        # Atualiza apenas campos fornecidos e preenchidos (nunca apaga campo preenchido)
        if token and not lead.raiox_token:
            lead.raiox_token = token
        if nome:
            lead.name = nome
        if email:
            lead.email = email
        if whatsapp:
            lead.whatsapp = whatsapp
            lead.phone = whatsapp
        if empresa:
            lead.legal_name = empresa
        if funcionarios:
            lead.funcionarios = str(funcionarios)
            lead.company_size = str(funcionarios)
        if faixa_faturamento:
            lead.faixa_faturamento = str(faixa_faturamento)
        if origem and (not lead.origem or lead.origem == 'direto'):
            lead.origem = origem

        # UTMs e Meta Event ID
        if utm_source: lead.utm_source = utm_source
        if utm_medium: lead.utm_medium = utm_medium
        if utm_campaign: lead.utm_campaign = utm_campaign
        if utm_content: lead.utm_content = utm_content
        if utm_term: lead.utm_term = utm_term
        if fbclid: lead.fbclid = fbclid
        if meta_event_id: lead.meta_event_id = meta_event_id

        # Atualização de status e etapa
        agora = datetime.utcnow()
        lead.raiox_atualizado_em = agora

        if etapa == 'iniciou':
            lead.consentimento = True
            lead.consentimento_em = agora
            if lead.raiox_status != 'concluido':
                lead.raiox_status = 'parcial_iniciou'
        elif etapa == 'dados':
            if not lead.raiox_status:
                lead.raiox_status = 'parcial_dados'
        else:
            # Pergunta respondida
            try:
                q_num = int(etapa)
                lead.raiox_ultima_pergunta = max(lead.raiox_ultima_pergunta or 0, q_num)
                if lead.raiox_status != 'concluido':
                    lead.raiox_status = 'parcial_iniciou'
            except ValueError:
                pass

        if answers is not None and isinstance(answers, list):
            lead.raiox_respostas_parciais = answers

        if is_new:
            db.session.add(lead)

        db.session.commit()
        return jsonify({'status': 'ok'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro em /raiox/progresso: {e}")
        return jsonify({'status': 'ok'}), 200


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
        token = (data.get('token') or '').strip()
        
        # 1. Dados do Lead
        lead_info = data.get('lead_info', {})
        nome = (lead_info.get('nome') or '').strip()
        email = (lead_info.get('email') or '').strip().lower()
        raw_whatsapp = (lead_info.get('whatsapp') or '').strip()
        whatsapp = normalize_phone(raw_whatsapp)
        empresa = (lead_info.get('empresa') or '').strip()
        funcionarios = lead_info.get('quantidade_funcionarios')
        faixa_faturamento = lead_info.get('faturamento_mensal')
        origem = (lead_info.get('origem') or request.args.get('origem') or lead_info.get('utm_source') or 'direto').strip()

        # UTMs e Meta Event ID
        utm_source = lead_info.get('utm_source')
        utm_medium = lead_info.get('utm_medium')
        utm_campaign = lead_info.get('utm_campaign')
        utm_content = lead_info.get('utm_content')
        utm_term = lead_info.get('utm_term')
        fbclid = lead_info.get('fbclid')
        meta_event_id = (data.get('event_id') or lead_info.get('event_id') or f"lead_{uuid.uuid4().hex[:16]}").strip()
        
        # Consentimento é implícito ao iniciar o diagnóstico
        consentimento = True
        consentimento_em = datetime.utcnow()

        # 2. Detectar versão (v3 = 1+5 perguntas ou v2 = 20 perguntas)
        raw_answers = data.get('answers')
        path_key = (data.get('path') or data.get('caminho') or '').strip().lower()
        is_v3 = (
            data.get('version') == 'v3'
            or path_key in RAIOX_V3_PATHS
            or (
                isinstance(raw_answers, dict)
                and any(str(k) in RAIOX_V3_QUESTIONS for k in raw_answers.keys())
            )
        )

        if is_v3:
            if path_key not in RAIOX_V3_PATHS:
                path_key = 'geral'
            if not nome or not whatsapp:
                return jsonify({'status': 'error', 'message': 'Nome e WhatsApp são obrigatórios.'}), 400
            resultado = calculate_raiox_v3(path_key, raw_answers)
            respostas_storage = {
                'version': 'v3',
                'path': path_key,
                'answers': resultado['respostas_dict'],
            }
            notas = resultado['notas']
            indice = resultado['nota']
            gargalo = resultado['gargalo']
            gargalo_nome = resultado['gargalo_nome']
            gargalo_nota_formatada = resultado['gargalo_nota_formatada']
            ponto_fraco = resultado['ponto_fraco_num']
            respostas_list = [d['valor'] for d in resultado['detalhes']]
        else:
            # Extração das Respostas v2 (20 inteiros de 0 a 3)
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

            resultado = calculate_raiox_v2(respostas_list)
            respostas_storage = respostas_list
            notas = resultado['notas']
            indice = resultado['indice']
            gargalo = resultado['gargalo']
            gargalo_nome = resultado['gargalo_nome']
            gargalo_nota_formatada = resultado['gargalo_nota_formatada']
            ponto_fraco = resultado['ponto_fraco_num']

        # 4. Salvar no CRM
        company_id, _, _ = get_raiox_company_and_pipeline()
        
        # Localiza lead existente: primeiro por token, depois email, depois whatsapp
        lead = None
        if token:
            lead = Lead.query.filter_by(raiox_token=token).first()
        if not lead and email:
            lead = Lead.query.filter_by(email=email).first()
        if not lead and whatsapp:
            lead = Lead.query.filter_by(whatsapp=whatsapp).first()
            if not lead:
                lead = Lead.query.filter_by(phone=whatsapp).first()
            
        is_new = False
        if not lead:
            lead = Lead(company_id=company_id, raiox_token=token)
            is_new = True

        primeira_conclusao = (lead.raiox_status != 'concluido')
            
        if nome: lead.name = nome
        if email: lead.email = email
        if whatsapp:
            lead.whatsapp = whatsapp
            lead.phone = whatsapp
        if empresa: lead.legal_name = empresa
        if token: lead.raiox_token = token
        
        # Novos campos v2
        if origem: lead.origem = origem
        if faixa_faturamento: lead.faixa_faturamento = str(faixa_faturamento)
        if funcionarios:
            lead.funcionarios = str(funcionarios)
            lead.company_size = str(funcionarios)
        lead.respostas = respostas_storage
        lead.nota_atrair = notas['atrair']
        lead.nota_engajar = notas['engajar']
        lead.nota_vender = notas['vender']
        lead.nota_reter = notas['reter']
        lead.nota_gestao = notas['gestao']
        lead.indice_maturidade = indice
        lead.gargalo = gargalo
        lead.ponto_fraco = ponto_fraco
        lead.consentimento = consentimento
        lead.consentimento_em = lead.consentimento_em or consentimento_em

        # UTMs e Meta Event ID
        if utm_source: lead.utm_source = utm_source
        if utm_medium: lead.utm_medium = utm_medium
        if utm_campaign: lead.utm_campaign = utm_campaign
        if utm_content: lead.utm_content = utm_content
        if utm_term: lead.utm_term = utm_term
        if fbclid: lead.fbclid = fbclid
        if meta_event_id: lead.meta_event_id = meta_event_id

        # Status do Raio-X
        lead.raiox_status = 'concluido'
        lead.raiox_ultima_pergunta = 5 if is_v3 else 20
        lead.raiox_atualizado_em = datetime.utcnow()

        # Campos legados preservados para compatibilidade
        lead.source = 'Raio-X Digital'
        lead.diagnostic_status = 'done'
        lead.diagnostic_score = indice
        lead.diagnostic_classification = gargalo_nome
        lead.diagnostic_date = datetime.utcnow()
        lead.diagnostic_stars = round((indice / 10.0) * 5.0, 1)
        lead.diagnostic_pillars = {
            'Atrair': notas['atrair'],
            'Engajar': notas['engajar'],
            'Vender': notas['vender'],
            'Reter': notas['reter'],
            'Gestão': notas['gestao'],
            '_respostas': respostas_storage
        }

        if is_v3:
            tags = [
                f"Caminho {resultado['caminho_label']}",
                f"Nota {resultado['nota_formatada']}",
                f"Urgente Q{resultado['urgente_id']}",
                f"Origem {origem}",
                "Raio-X v3",
            ]
        else:
            tags = [f"Gargalo {gargalo_nome}", f"Índice {str(indice).replace('.', ',')}", f"Origem {origem}", "Raio-X v2"]
        lead.interest = ", ".join(tags)

        # Se for primeira conclusão, aloca estágio no pipeline e executa automações
        if primeira_conclusao:
            lead.source = 'Raio-X Digital'
            target_cid, target_pid, target_sid = get_raiox_company_and_pipeline()
            lead.company_id = target_cid
            lead.pipeline_id = target_pid
            lead.pipeline_stage_id = target_sid
        
        if is_new:
            db.session.add(lead)
            
        db.session.commit()

        if token:
            upsert_raiox_session(
                token=token,
                caminho=path_key if is_v3 else None,
                etapa='concluido',
                answers=respostas_storage,
                lead_id=lead.id,
                origem=origem,
                utm_source=utm_source,
                utm_medium=utm_medium,
                utm_campaign=utm_campaign,
            )
        
        # Disparo de automações para primeira conclusão
        if primeira_conclusao and lead.pipeline_stage_id:
            try:
                from tasks_utils import generate_tasks_for_stage, process_funnel_automations
                generate_tasks_for_stage(lead.id, lead.pipeline_stage_id)
                process_funnel_automations(lead.id, lead.pipeline_stage_id)
            except Exception as e:
                logger.error(f"Erro ao disparar automações de estágio: {e}")

        # Disparo de webhook de conclusão para o n8n no backend
        if primeira_conclusao:
            try:
                payload_n8n = {
                    "event": "raiox_concluido",
                    "lead_id": lead.id,
                    "token": lead.raiox_token,
                    "nome": lead.name or nome or '',
                    "email": lead.email or email or '',
                    "whatsapp": lead.phone or lead.whatsapp or whatsapp or '',
                    "empresa": lead.raiox_empresa or empresa or '',
                    "porte": lead.raiox_porte or funcionarios or '',
                    "faturamento": lead.raiox_faturamento or faixa_faturamento or '',
                    "origem": lead.raiox_origem or origem or 'direto',
                    "utms": {
                        "source": lead.utm_source,
                        "medium": lead.utm_medium,
                        "campaign": lead.utm_campaign,
                        "content": lead.utm_content,
                        "term": lead.utm_term,
                        "fbclid": lead.fbclid
                    },
                    "meta_event_id": lead.meta_event_id or meta_event_id,
                    "score_geral": lead.raiox_score_geral if lead.raiox_score_geral is not None else indice,
                    "scores_eixos": {
                        "atrair": lead.raiox_score_atrair if lead.raiox_score_atrair is not None else notas['atrair'],
                        "engajar": lead.raiox_score_engajar if lead.raiox_score_engajar is not None else notas['engajar'],
                        "vender": lead.raiox_score_vender if lead.raiox_score_vender is not None else notas['vender'],
                        "reter": lead.raiox_score_reter if lead.raiox_score_reter is not None else notas['reter'],
                        "gestao": lead.raiox_score_gestao if lead.raiox_score_gestao is not None else notas['gestao']
                    },
                    "gargalo_principal": lead.raiox_gargalo_principal or gargalo,
                    "respostas": lead.raiox_respostas or respostas_list,
                    "versao": "v3" if is_v3 else "v2",
                    "caminho": resultado.get("caminho") if is_v3 else None,
                    "caminho_label": resultado.get("caminho_label") if is_v3 else None,
                    "ponto_urgente": resultado.get("urgente_curto") if is_v3 else None,
                    "acao_recomendada": resultado.get("acao_prioritaria"),
                    "concluido_em": datetime.utcnow().isoformat()
                }
                dispatch_n8n_raiox_webhook(lead, payload_n8n)
            except Exception as e:
                logger.error(f"[N8N_RAIOX] Erro crítico ao preparar ou disparar webhook n8n: {e}", exc_info=True)

        # 5. Gerar Link do WhatsApp
        whatsapp_number = os.environ.get('NORTHWAY_WHATSAPP', '5542999896358').replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
        wa_text = f"Olá! Sou {nome or 'um empreendedor'}, da {empresa or 'minha empresa'}. Fiz o Raio-X e meu principal gargalo é {gargalo_nome} ({gargalo_nota_formatada}/10). Quero entender os próximos passos."
        wa_url = f"https://wa.me/{whatsapp_number}?text={urllib.parse.quote(wa_text)}"
        resultado['whatsapp_url'] = wa_url
        resultado['empresa'] = empresa
        resultado['nome'] = nome
        resultado['event_id'] = meta_event_id

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

                EmailService.send_email(
                    to_email=email,
                    subject=f"Seu Raio-X NorthWay: {empresa or 'Diagnóstico de Escala Digital'}",
                    html_content=email_html,
                    pdf_bytes=pdf_bytes,
                    pdf_filename=f"Raio-X-NorthWay-{nome or 'Diagnostico'}.pdf"
                )
            except Exception as mail_err:
                logger.warning(f"Não foi possível despachar e-mail do Raio-X via Resend: {mail_err}")

        session['raiox_resultado'] = resultado

        # 7. Retorno em JSON para renderização instantânea na mesma página
        return jsonify({
            'status': 'success',
            'resultado': resultado,
            'event_id': meta_event_id
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
    Lista todos os leads que fizeram o Raio-X Digital (concluídos e abandonados).
    Filtro por status: todos, concluidos, abandonados.
    """
    status_filter = request.args.get('status', 'todos').lower()

    query = Lead.query.filter(
        or_(
            Lead.source.in_(['Raio-X Digital', 'Raio-X Digital (parcial)']),
            Lead.raiox_token.isnot(None),
            Lead.raiox_status.isnot(None)
        )
    )

    if status_filter == 'concluidos':
        query = query.filter(
            or_(
                Lead.raiox_status == 'concluido',
                (Lead.source == 'Raio-X Digital') & (Lead.diagnostic_status == 'done')
            )
        )
    elif status_filter == 'abandonados':
        query = query.filter(
            or_(
                Lead.raiox_status.in_(['parcial_dados', 'parcial_iniciou']),
                Lead.source == 'Raio-X Digital (parcial)'
            )
        )

    leads = query.order_by(Lead.created_at.desc()).all()

    clean_leads = []
    for l in leads:
        if isinstance(l.diagnostic_pillars, dict):
            l.diagnostic_pillars = {k: v for k, v in l.diagnostic_pillars.items() if not k.startswith('_')}
        clean_leads.append(l)

    return render_template('forms/raiox_leads.html', leads=clean_leads, current_status=status_filter)


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
