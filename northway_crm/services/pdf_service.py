import io
import os
from fpdf import FPDF
from flask import current_app

class ContractPDF(FPDF):
    def __init__(self, contract_code, company_name="NORTHWAY", company_subtext=""):
        super().__init__()
        self.contract_code = contract_code
        self.company_name = company_name
        self.company_subtext = company_subtext
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        # Premium Header (Logo + Dynamic Text Fallback)
        
        logo_loaded = False
        try:
            # Try multiple common paths for the logo
            possible_paths = [
                os.path.join(current_app.root_path, 'static', 'img', 'logo_1.png'),
                os.path.join(current_app.root_path, 'static', 'images', 'logo.png'),
                os.path.join(current_app.root_path, 'static', 'img', 'logo.png')
            ]
            
            for logo_path in possible_paths:
                if os.path.exists(logo_path):
                    # Fixed width 33mm, auto height
                    self.image(logo_path, 10, 8, w=33)
                    logo_loaded = True
                    break
                    
        except Exception as e:
            current_app.logger.warning(f"Logo load failed (Pillow missing?): {e}")
            logo_loaded = False

        # If logo failed, use the Text Brand (Fallback)
        if not logo_loaded: 
            # 1. Main Brand (Company Name)
            self.set_font('Helvetica', 'B', 20)
            self.set_text_color(0, 0, 0) # Black
            # Fallback if empty
            display_name = self.company_name if self.company_name else "NORTHWAY"
            self.cell(0, 10, display_name, 0, 1, 'L')
        
        # 2. Sub-brand / CNPJ (Always show this, or adjust position if logo present?)
        # Design decision: If logo is present, we still want the CNPJ/Subtext, but maybe positioned differently?
        # Let's keep the subtext simple.
        
        if logo_loaded:
             # Move cursor to right to avoid overlapping logo? 
             # Actually, standard design: Logo Left, Title Right.
             # We just need to ensure we don't write over the logo.
             self.set_xy(10, 25) # Below logo
        else:
             self.set_font('Helvetica', '', 9)
             self.set_text_color(100, 100, 100) # Gray
             if self.company_subtext:
                self.cell(0, 5, self.company_subtext, 0, 1, 'L')

        # 3. Document Title (Right Aligned)
        self.set_y(15) # Top area
        self.set_font('Helvetica', 'B', 12)
        self.set_text_color(0)
        self.cell(0, 10, 'CONTRATO DE SERVIÇOS', 0, 1, 'R')
        
        # 4. Separator Line
        self.set_y(35)
        self.set_draw_color(200, 200, 200) # Light gray line
        self.set_line_width(0.5)
        self.line(10, 32, 200, 32)
        
        # 5. Reference Code
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
        footer_text = f"{self.company_name} - Documento Confidencial | Página " + str(self.page_no()) + " de {nb}"
        self.cell(0, 10, footer_text, 0, 0, 'C')

class PdfService:
    @staticmethod
    def _resolve_img_path(src):
        """
        Converts relative /static/ paths to absolute file system paths.
        Returns the absolute path if found, or None.
        """
        # Handle already absolute paths (unlikely in web context but possible)
        if os.path.isabs(src) and os.path.exists(src):
            return src
            
        # Handle /static/... pattern
        if src.startswith('/static/'):
            # Remove leading slash and join with root_path
            rel_path = src.lstrip('/')
            abs_path = os.path.join(current_app.root_path, rel_path)
            if os.path.exists(abs_path):
                return abs_path
                
        # Handle incomplete relative paths (e.g. static/img/...)
        possible_roots = [current_app.root_path]
        for root in possible_roots:
            abs_path = os.path.join(root, src.lstrip('/'))
            if os.path.exists(abs_path):
                return abs_path
                
        return None

    @staticmethod
    def generate_pdf(contract):
        """
        Generates a PDF for the contract using FPDF2.
        """
        current_app.logger.info(f"Generating PDF for Contract ID: {contract.id}")
        try:
            # 1. Prepare Dynamic Company Info
            company_name = "NORTHWAY"
            company_subtext = ""
            
            if contract.company:
                company_name = contract.company.name.upper()
                # Try to get CNPJ/Document
                doc = getattr(contract.company, 'document', None) or getattr(contract.company, 'cpf_cnpj', None)
                if doc:
                     company_subtext = f"{contract.company.name} | CNPJ: {doc}"
                else:
                     company_subtext = contract.company.name

            current_app.logger.info("Initializing ContractPDF...")
            pdf = ContractPDF(
                contract_code=contract.code or str(contract.id),
                company_name=company_name,
                company_subtext=company_subtext
            )
            
            pdf.alias_nb_pages()
            pdf.add_page()
            
            # Set basic font
            pdf.set_font('Helvetica', '', 10)
            
            # Write HTML content
            if contract.generated_content:
                html = contract.generated_content
                import re
                
                # --- A. IMAGE PATH CORRECTION ---
                # FPDF2 requires absolute paths. We must find <img src="..."> and fix it.
                def replace_img_src(match):
                    full_tag = match.group(0)
                    src_match = re.search(r'src=["\']([^"\']+)["\']', full_tag)
                    if src_match:
                        original_src = src_match.group(1)
                        abs_path = PdfService._resolve_img_path(original_src)
                        if abs_path:
                            # Replace the src with absolute path
                            return full_tag.replace(original_src, abs_path)
                    # If resolving fails, strip the image to prevent crash
                    current_app.logger.warning(f"Could not resolve image: {full_tag}")
                    return "" 
                
                # Execute replacement
                html = re.sub(r'<img[^>]+>', replace_img_src, html, flags=re.IGNORECASE)

                # --- B. LAYOUT PRESERVATION ---
                # FPDF2 sometimes treats <div> as inline. We must force a line break.
                html = re.sub(r'</div>', '<br>', html, flags=re.IGNORECASE)

                # Ensure all paragraphs are justified
                if '<p' in html:
                    html = re.sub(r'<p([^>]*)>', r'<p align="justify"\1>', html, flags=re.IGNORECASE)
                    
                # Clean up excessive breaks potentially caused by the div replacement
                html = re.sub(r'(<br\s*/?>\s*){3,}', '<br><br>', html, flags=re.IGNORECASE)
                    
                # --- C. CLEANUP ---
                # Strip Table Attributes that break layout
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

                # --- D. WRITE ---
                # Wrap via Styled Font for Justification & Typography
                # We use size 10 for better density.
                sty_html = f"""
                <font face="Helvetica" size="10">
                {html}
                </font>
                """
                pdf.write_html(sty_html)
            else:
                pdf.write(5, "Conteúdo do contrato não disponível.")
                
            return bytes(pdf.output())
            
        except Exception as e:
            current_app.logger.error(f"Error generating PDF (FPDF): {str(e)}")
            raise e
