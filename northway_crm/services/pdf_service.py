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
        # Premium Typographic Header (No Images required)
        
        # 1. Main Brand
        self.set_font('Helvetica', 'B', 20)
        self.set_text_color(0, 0, 0) # Black
        self.cell(0, 10, 'NORTHWAY', 0, 1, 'L')
        
        # 2. Sub-brand / CNPJ
        self.set_font('Helvetica', '', 9)
        self.set_text_color(100, 100, 100) # Gray
        self.cell(0, 5, 'NorthWay Company | CNPJ: 56.106.629/0001-75', 0, 1, 'L')
        
        # 3. Document Title (Right Aligned, but moved up via Y adjustment if needed, 
        #    or just placed on next line for clean layout)
        #    Let's keep it simple: Line break then Title centered or right
        
        self.set_y(15) # Back to top area for right side
        self.set_font('Helvetica', 'B', 12)
        self.set_text_color(0)
        self.cell(0, 10, 'CONTRATO DE SERVIÇOS', 0, 1, 'R')
        
        # 4. Separator Line
        self.set_y(35)
        self.set_draw_color(200, 200, 200) # Light gray line
        self.set_line_width(0.5)
        self.line(10, 32, 200, 32)
        
        # 5. Reference Code (Small, Right, below line)
        if self.contract_code:
            self.set_xy(10, 33)
            self.set_font('Helvetica', 'I', 8)
            self.set_text_color(128)
            self.cell(0, 4, f"Ref: {self.contract_code}", 0, 1, 'R')
            
        self.ln(5) # Space after header

    def footer(self):
        # Position at 1.5 cm from bottom
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128)
        self.cell(0, 10, 'NorthWay Company - Documento Confidencial | Página ' + str(self.page_no()) + ' de {nb}', 0, 0, 'C')

class PdfService:
    @staticmethod
    def generate_pdf(contract):
        """
        Generates a PDF for the contract using FPDF2.
        """
        current_app.logger.info(f"Generating PDF for Contract ID: {contract.id}")
        try:
            current_app.logger.info("Initializing ContractPDF...")
            pdf = ContractPDF(contract_code=contract.code or str(contract.id))
            
            pdf.alias_nb_pages()
            pdf.add_page()
            
            # Set basic font
            pdf.set_font('Helvetica', '', 10)
            
            # Write HTML content
            if contract.generated_content:
                # 1. Clean up HTML
                html = contract.generated_content
                
                import re
                
                # Strip <img> tags (Pillow crash prevention)
                html = re.sub(r'<img[^>]*>', '', html, flags=re.IGNORECASE)

                # Strip Table Widths (Layout crash prevention)
                html = re.sub(r'(<table[^>]*?)\swidth="[^"]*"', r'\1', html, flags=re.IGNORECASE)
                html = re.sub(r'(<td[^>]*?)\swidth="[^"]*"', r'\1', html, flags=re.IGNORECASE)
                html = re.sub(r'(<th[^>]*?)\swidth="[^"]*"', r'\1', html, flags=re.IGNORECASE)
                html = re.sub(r'width:\s*[^;"\']+[;"\']?', '', html, flags=re.IGNORECASE)

                # Latin-1 Sanitization
                replacements = {
                    '\u2013': '-', '\u2014': '-',
                    '\u2018': "'", '\u2019': "'",
                    '\u201c': '"', '\u201d': '"',
                    '\u2022': '-', '\u2026': '...',
                    '\u00a0': ' ', '\u200b': '',
                }
                for src, dst in replacements.items():
                    html = html.replace(src, dst)
                
                # Force Encoding
                html = html.encode('latin-1', 'replace').decode('latin-1')

                # Flatten Block Elements inside tables/structure
                html = re.sub(r'</p>\s*<p[^>]*>', '<br><br>', html, flags=re.IGNORECASE) # Double break for paragraphs
                html = re.sub(r'</div>\s*<div[^>]*>', '<br>', html, flags=re.IGNORECASE)
                html = re.sub(r'</?div[^>]*>', '', html, flags=re.IGNORECASE)
                html = re.sub(r'</?p[^>]*>', '', html, flags=re.IGNORECASE)

                # 2. Wrap via Styled Div for Justification & Typography
                # Note: fpdf2 writes this as a flow. 
                # We use specific fonts and alignment to match "System" look.
                sty_html = f"""
                <font face="Helvetica" size="11">
                {html}
                </font>
                """
                
                # Note: fpdf2 write_html doesn't fully support <div align="justify"> perfectly in all versions, 
                # but standard write_html respects self.set_font etc.
                # We can try to replace <br> with proper spacing if needed.
                
                pdf.write_html(sty_html)
            else:
                pdf.write(5, "Conteúdo do contrato não disponível.")
                
            return bytes(pdf.output())
            
        except Exception as e:
            current_app.logger.error(f"Error generating PDF (FPDF): {str(e)}")
            raise e
