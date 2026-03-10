from fpdf import FPDF
import os
from flask import current_app
from datetime import datetime

class PresentationPDF(FPDF):
    def __init__(self, company_name="NORTHWAY"):
        super().__init__()
        self.company_name = company_name
        self.primary_color = (250, 1, 2) # NorthWay Red
        self.bg_color = (18, 18, 23) # Dark background
        self.text_color = (255, 255, 255)
        self.secondary_text = (160, 160, 170)
        
    def header(self):
        # We don't want headers on all pages for a presentation style
        pass

    def footer(self):
        if self.page_no() > 1:
            self.set_y(-15)
            self.set_font('Helvetica', 'I', 8)
            self.set_text_color(*self.secondary_text)
            self.cell(0, 10, f'NorthWay CRM - Inteligência de Vendas | Página {self.page_no()}', 0, 0, 'C')

    def add_presentation_page(self, title, subtitle=None):
        self.add_page()
        # Dark Background
        self.set_fill_color(self.bg_color[0], self.bg_color[1], self.bg_color[2])
        self.rect(0, 0, 210, 297, 'F')
        
        # Decorative Elements (Glassmorphism inspired)
        self.set_draw_color(self.primary_color[0], self.primary_color[1], self.primary_color[2])
        self.set_line_width(0.5)
        self.line(10, 25, 60, 25)
        
        # Title
        self.set_xy(10, 30)
        self.set_font('Helvetica', 'B', 24)
        self.set_text_color(self.text_color[0], self.text_color[1], self.text_color[2])
        self.cell(0, 15, title.upper(), 0, 1, 'L')
        
        if subtitle:
            self.set_font('Helvetica', '', 12)
            self.set_text_color(self.secondary_text[0], self.secondary_text[1], self.secondary_text[2])
            self.cell(0, 10, subtitle, 0, 1, 'L')
            self.ln(10)

class PresentationService:
    @staticmethod
    def generate_pdf(data):
        """
        Generates a 10-page commercial presentation.
        data keys: prospect_name, consultant_name, consultant_title, observacao, prospect_logo
        """
        prospect_name = data.get('prospect_name', 'Cliente')
        consultant_name = data.get('consultant_name', 'Consultor NorthWay')
        consultant_title = data.get('consultant_title', 'Consultor Comercial')
        obs = data.get('observacao', '')
        
        pdf = PresentationPDF()
        pdf.set_auto_page_break(False)

        # PAGE 1: COVER
        pdf.add_page()
        pdf.set_fill_color(18, 18, 23)
        pdf.rect(0, 0, 210, 297, 'F')
        
        # Logo placeholder or real logo
        # We assume there's a logo at static/images/logo.png for NorthWay
        logo_path = os.path.join(current_app.root_path, 'static', 'images', 'logo.png')
        if os.path.exists(logo_path):
            pdf.image(logo_path, 80, 40, w=50)
            
        pdf.set_xy(10, 110)
        pdf.set_font('Helvetica', 'B', 32)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 20, "APRESENTAÇÃO", 0, 1, 'C')
        pdf.set_text_color(250, 1, 2)
        pdf.cell(0, 20, "COMERCIAL", 0, 1, 'C')
        
        pdf.ln(30)
        pdf.set_font('Helvetica', 'B', 16)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 10, f"Preparado para: {prospect_name}", 0, 1, 'C')
        
        if obs:
            pdf.ln(10)
            pdf.set_font('Helvetica', 'I', 11)
            pdf.set_text_color(160, 160, 170)
            pdf.multi_cell(0, 6, obs, 0, 'C')
            
        pdf.set_y(250)
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(0, 10, consultant_name.upper(), 0, 1, 'C')
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(160, 160, 170)
        pdf.cell(0, 5, consultant_title, 0, 1, 'C')

        # PAGE 2: INTRO
        pdf.add_presentation_page("A NORTHWAY", "Mais que um CRM, seu ecossistema de crescimento.")
        pdf.set_font('Helvetica', '', 12)
        text = (
            "A NorthWay nasceu para consolidar o caos comercial em inteligência operacional. "
            "Unimos prospecção, gestão de relacionamento e controle financeiro em uma única plataforma premium. "
            "\n\nNossa missão é garantir que cada lead seja tratado como uma oportunidade de ouro, "
            "minimizando falhas humanas e maximizando a conversão através de processos validados."
        )
        pdf.set_xy(15, 70)
        pdf.multi_cell(0, 8, text, 0, 'L')

        # PAGE 3: ECOSSISTEMA
        pdf.add_presentation_page("ECOSSISTEMA COMPLETO", "Tudo o que sua empresa precisa em um só lugar.")
        items = [
            ("Prospecção Ativa", "Enriquecimento de dados oficial e busca inteligente."),
            ("Gestão de Funis", "Múltiplas etapas e automação de alertas."),
            ("CRM de Vendas", "Histórico completo, tarefas e interações."),
            ("Financeiro Estratégico", "DRE, Contas a Pagar e Controle de Comissões."),
            ("WhatsApp Integrado", "Inbox centralizado sem troca de chip."),
            ("Biblioteca de Conhecimento", "Treinamentos e playbooks integrados.")
        ]
        pdf.set_xy(15, 70)
        for title, desc in items:
            pdf.set_font('Helvetica', 'B', 12)
            pdf.set_text_color(250, 1, 2)
            pdf.cell(0, 8, f"> {title}", 0, 1)
            pdf.set_font('Helvetica', '', 11)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(0, 8, f"  {desc}", 0, 1)
            pdf.ln(4)

        # PAGE 4: PROCESSOS
        pdf.add_presentation_page("PROCESSOS E FUNIS", "Visibilidade total do seu pipeline de vendas.")
        pdf.set_font('Helvetica', '', 12)
        text = (
            "O Funil da NorthWay não é apenas visual. Ele é funcional. "
            "Com o Kanban de execução, seu time sabe exatamente o que fazer hoje, agora. "
            "\n\n- Cards automáticos por status.\n- Alertas de ociosidade."
            "\n- Histórico de movimentação detalhado.\n- Integração com checklists de processos."
        )
        pdf.set_xy(15, 70)
        pdf.multi_cell(0, 8, text, 0, 'L')

        # PAGE 5: INTELIGÊNCIA ESTRATÉGICA
        pdf.add_presentation_page("INTELIGÊNCIA ESTRATÉGICA", "Decisões baseadas em dados, não em palpites.")
        stats = [
            "Matriz SWOT: Analise forças e fraquezas com um clique.",
            "Matriz de Público: Identifique onde está seu lucro real.",
            "Diagnóstico CREPI: Avalie riscos e probabilidades de fechamento.",
            "Metas Dinâmicas: Projeções baseadas em performance histórica."
        ]
        pdf.set_xy(15, 70)
        for s in stats:
            pdf.set_font('Helvetica', 'B', 12)
            pdf.set_text_color(250, 1, 2)
            pdf.cell(10, 10, "*", 0, 0)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(0, 10, s, 0, 1)

        # PAGE 6: ENRIQUECIMENTO
        pdf.add_presentation_page("PODER DO ENRIQUECIMENTO", "Dados oficiais da Receita Federal em segundos.")
        text = (
            "Com a integração CNPJ, você tem acesso ao QSA (Quadro de Sócios), "
            "Capital Social, CNAE oficial e data de abertura sem digitar nada. "
            "\n\nEssa camada de dados permite abordagens muito mais assertivas "
            "e uma qualificação de lead (BANT) feita em tempo recorde."
        )
        pdf.set_xy(15, 70)
        pdf.multi_cell(0, 8, text, 0, 'L')

        # PAGE 7: FINANCEIRO
        pdf.add_presentation_page("FINANCEIRO ESTRATÉGICO", "Sua rentabilidade na ponta do lápis.")
        text = (
            "- DRE Estratégico em tempo real.\n- Fluxo de caixa de comissões.\n"
            "- Controle de inadimplência automatizado.\n- Geração de notas fiscais e contratos digitais."
        )
        pdf.set_xy(15, 70)
        pdf.multi_cell(0, 8, text, 0, 'L')

        # PAGE 8: PRODUTIVIDADE
        pdf.add_presentation_page("PRODUTIVIDADE", "Foco no que gera venda.")
        text = (
            "O CRM NorthWay centraliza as tarefas de todo o time. "
            "Com notificações em tempo real e o Kanban de Execução, "
            "o consultor não perde tempo procurando o que fazer, "
            "ele foca em fechar o próximo contrato."
        )
        pdf.set_xy(15, 70)
        pdf.multi_cell(0, 8, text, 0, 'L')

        # PAGE 9: INTEGRAÇÕES
        pdf.add_presentation_page("INTEGRAÇÕES NATIVAS", "Seu fluxo de trabalho sem interrupções.")
        integrations = [
            "WhatsApp API: Inbox profissional e logs de conversa.",
            "Google Drive: Organização automática de documentos e pastas.",
            "Supabase: Segurança de dados de nível bancário.",
            "E-mail Marketing: Nutrição integrada de leads."
        ]
        pdf.set_xy(15, 70)
        for i in integrations:
            pdf.set_font('Helvetica', '', 12)
            pdf.cell(0, 10, f"- {i}", 0, 1)

        # PAGE 10: CONCLUSÃO
        pdf.add_presentation_page("PRÓXIMOS PASSOS", "O futuro das suas vendas começa agora.")
        pdf.set_font('Helvetica', 'B', 14)
        pdf.set_text_color(250, 1, 2)
        pdf.set_xy(15, 70)
        pdf.cell(0, 10, "VAMOS CONVERSAR?", 0, 1, 'C')
        
        pdf.set_font('Helvetica', '', 12)
        pdf.set_text_color(255, 255, 255)
        pdf.ln(10)
        pdf.multi_cell(0, 8, "Estamos prontos para transformar sua operação comercial. "
                              "Escaneie o QR Code no seu dashboard ou entre em contato direto pelo WhatsApp.", 0, 'C')

        return pdf.output()
