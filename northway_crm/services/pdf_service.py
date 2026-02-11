import logging
from weasyprint import HTML, CSS
from flask import current_app

class PdfService:
    @staticmethod
    def generate_pdf(html_content):
        """
        Generates a PDF from HTML content using WeasyPrint.
        
        Args:
            html_content (str): The HTML string to convert.
            
        Returns:
            bytes: The generated PDF content.
        """
        try:
            # Configure logging to suppress verbose WeasyPrint output
            logger = logging.getLogger('weasyprint')
            logger.setLevel(logging.ERROR)

            # Create HTML object
            # base_url is set to current_app.root_path to allow relative paths for static assets if needed
            html = HTML(string=html_content, base_url=current_app.root_path)

            # Generate PDF
            # presentational_hints=True allows deprecated HTML attributes (like align, bgcolor) to be respected
            pdf_bytes = html.write_pdf(presentational_hints=True)
            
            return pdf_bytes
            
        except Exception as e:
            current_app.logger.error(f"Error generating PDF: {str(e)}")
            raise e
