from flask import Blueprint, send_file, render_template, current_app, abort
from flask_login import login_required, current_user
from models import Contract
import io

pdf_bp = Blueprint('pdf', __name__)

@pdf_bp.route('/contracts/<int:id>/pdf')
@login_required
def download_contract_pdf(id):
    """
    Generates and downloads a PDF for a specific contract.
    """
    try:
        from services.pdf_service import PdfService
    except ImportError as e:
        current_app.logger.error(f"Failed to import PdfService: {e}")
        return f"Configuration Error: {e}", 500
    # 1. Fetch Contract & verify permission
    contract = Contract.query.get_or_404(id)
    
    # Check company access
    if contract.company_id != current_user.company_id:
        abort(403)

    try:
        # 2. Generate PDF using FPDF2 (Zero-dependency)
        # We pass the contract object directly, no intermediate HTML template needed for layout
        pdf_bytes = PdfService.generate_pdf(contract)

        # 4. Return as attachment
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"Contrato_{contract.code or contract.id}.pdf"
        )
        
    except Exception as e:
        current_app.logger.error(f"Failed to generate PDF for contract {id}: {str(e)}")
        # Return the actual error to the user for debugging
        return f"Erro ao gerar PDF: {str(e)}", 500
