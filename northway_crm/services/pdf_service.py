import io
import os
from fpdf import FPDF
from flask import current_app

class ContractPDF(FPDF):
    def __init__(self, contract_code):
        super().__init__()
        self.contract_code = contract_code
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        # Logo
        try:
            # Path to logo - adjust based on your structure
            logo_path = os.path.join(current_app.root_path, 'static', 'images', 'logo.png')
            if os.path.exists(logo_path):
                self.image(logo_path, 10, 8, 33)
        except Exception as e:
            pass # Skip logo if missing

        # Font for Title
        self.set_font('Arial', 'B', 15)
        # Move to the right
        self.cell(80)
        # Title
        self.cell(30, 10, 'CONTRATO DE SERVIÇOS', 0, 0, 'C')
        
        # Line break
        self.ln(20)
        
        # Contract Code
        if self.contract_code:
            self.set_font('Arial', 'I', 8)
            self.set_text_color(128)
            self.set_xy(10, 25) # Position below logo
            self.cell(0, 5, f"Ref: {self.contract_code}", 0, 1, 'L')
            self.set_text_color(0) # Reset color

    def footer(self):
        # Position at 1.5 cm from bottom
        self.set_y(-15)
        # Arial italic 8
        self.set_font('Arial', 'I', 8)
        self.set_text_color(128)
        # Page number
        self.cell(0, 10, 'Página ' + str(self.page_no()) + ' de {nb}', 0, 0, 'C')

class PdfService:
    @staticmethod
    def generate_pdf(contract):
        """
        Generates a PDF for the contract using FPDF2.
        
        Args:
            contract (Contract): The contract model instance.
            
        Returns:
            bytes: The generated PDF content.
        """
        try:
            pdf = ContractPDF(contract_code=contract.code or str(contract.id))
            pdf.alias_nb_pages()
            pdf.add_page()
            
            # Set font for body
            pdf.set_font('Arial', '', 11)
            
            # Write HTML content
            # Note: generated_content is HTML. write_html handles it.
            if contract.generated_content:
                # Basic cleanup if needed
                html = contract.generated_content
                
                # FPDF2 write_html choke on 'auto' values for width/height/margin
                # We replace them with valid values or remove them
                import re
                html = re.sub(r'width:\s*auto;?', '', html, flags=re.IGNORECASE)
                html = re.sub(r'height:\s*auto;?', '', html, flags=re.IGNORECASE)
                html = re.sub(r'margin:\s*auto;?', '', html, flags=re.IGNORECASE)
                html = re.sub(r'width="auto"', '', html, flags=re.IGNORECASE)
                html = re.sub(r'height="auto"', '', html, flags=re.IGNORECASE)
                
                # FPDF2 Tables DO NOT support nested block elements (p, div) or mixed content well.
                # We flatten the structure:
                # 1. Replace block breaks with <br>
                html = re.sub(r'</p>\s*<p[^>]*>', '<br>', html, flags=re.IGNORECASE)
                html = re.sub(r'</div>\s*<div[^>]*>', '<br>', html, flags=re.IGNORECASE)
                
                # 2. Remove remaining block tags (unwrap content)
                html = re.sub(r'</?div[^>]*>', '', html, flags=re.IGNORECASE)
                html = re.sub(r'</?p[^>]*>', '', html, flags=re.IGNORECASE)
                
                # 3. Clean up spans that might just be structural
                # html = re.sub(r'</?span[^>]*>', '', html, flags=re.IGNORECASE) # Spans usually usually fine unless they split content? keep for now.
                
                pdf.write_html(html)
            else:
                pdf.write(5, "Conteúdo do contrato não disponível.")
                
            return pdf.output(dest='S').encode('latin-1', 'replace') # 'replace' handles unencodable chars safely
            
        except Exception as e:
            current_app.logger.error(f"Error generating PDF (FPDF): {str(e)}")
            raise e
