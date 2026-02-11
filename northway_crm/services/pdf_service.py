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
            # Try multiple common paths
            possible_paths = [
                os.path.join(current_app.root_path, 'static', 'img', 'logo_1.png'),
                os.path.join(current_app.root_path, 'static', 'images', 'logo.png'),
                os.path.join(current_app.root_path, 'static', 'img', 'logo.png')
            ]
            
            logo_found = False
            for logo_path in possible_paths:
                if os.path.exists(logo_path):
                    # Force width to 33mm
                    self.image(logo_path, 10, 8, 33)
                    logo_found = True
                    break
            
            if not logo_found:
                current_app.logger.warning("Logo file not found in any expected location.")
                
        except Exception as e:
            # This catches 'Pillow not available' and other image errors
            current_app.logger.warning(f"Could not load logo for PDF (Pillow missing?): {e}")
            # Fallback: Write text instead of logo
            self.set_font("Helvetica", "B", 10)
            self.set_xy(10, 10)
            self.cell(33, 10, "[NorthWay]", 0, 0, 'C')

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
        current_app.logger.info(f"Generating PDF for Contract ID: {contract.id}")
        try:
            current_app.logger.info("Initializing ContractPDF...")
            pdf = ContractPDF(contract_code=contract.code or str(contract.id))
            
            current_app.logger.info("Calling alias_nb_pages...")
            pdf.alias_nb_pages()
            
            current_app.logger.info(f"Calling add_page... (Current page: {pdf.page_no()})")
            pdf.add_page()
            current_app.logger.info(f"Page added. (Current page: {pdf.page_no()})")
            
            if pdf.page_no() == 0:
                current_app.logger.error("CRITICAL: add_page() failed to increment page number!")
                raise Exception("add_page() failed to create a page (page_no is 0)")
            
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

                # FPDF2 / Pillow on Vercel is broken for images.
                # We actively remove <img> tags to prevent "Pillow not available" crashes.
                html = re.sub(r'<img[^>]*>', '', html, flags=re.IGNORECASE)
                
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
