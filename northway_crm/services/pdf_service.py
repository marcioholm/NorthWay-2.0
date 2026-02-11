import logging
from xhtml2pdf import pisa
from flask import current_app
import io

class PdfService:
    @staticmethod
    def generate_pdf(html_content):
        """
        Generates a PDF from HTML content using xhtml2pdf.
        
        Args:
            html_content (str): The HTML string to convert.
            
        Returns:
            bytes: The generated PDF content.
        """
        try:
            # Create a BytesIO buffer for the PDF
            pdf_buffer = io.BytesIO()

            # Generate PDF
            # dest=pdf_buffer: Write PDF to buffer
            # src=html_content: Source HTML
            pisa_status = pisa.CreatePDF(
                src=html_content,    # the HTML to convert
                dest=pdf_buffer      # file handle to recieve result
            )

            # Check for errors
            if pisa_status.err:
                raise Exception(f"xhtml2pdf error: {pisa_status.err}")

            # Get the value from the buffer
            pdf_bytes = pdf_buffer.getvalue()
            pdf_buffer.close()
            
            return pdf_bytes
            
        except Exception as e:
            current_app.logger.error(f"Error generating PDF: {str(e)}")
            raise e
