from flask import Blueprint, send_file, render_template, current_app, abort
from flask_login import login_required, current_user
from northway_crm.models.contracts import Contract
from northway_crm.services.pdf_service import PdfService
import io

pdf_bp = Blueprint('pdf', __name__)

@pdf_bp.route('/contracts/<int:id>/pdf')
@login_required
def download_contract_pdf(id):
    """
    Generates and downloads a PDF for a specific contract.
    """
    # 1. Fetch Contract & verify permission
    contract = Contract.query.get_or_404(id)
    
    # Check tenant access
    if contract.tenant_id != current_user.tenant_id:
        abort(403)

    try:
        # 2. Render HTML template
        # We use a dedicated print template that is optimized for WeasyPrint (A4, no JS)
        html_content = render_template('contracts/print_template.html', contract=contract)

        # 3. Generate PDF
        pdf_bytes = PdfService.generate_pdf(html_content)

        # 4. Return as attachment
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"Contrato_{contract.code or contract.id}.pdf"
        )
        
    except Exception as e:
        current_app.logger.error(f"Failed to generate PDF for contract {id}: {str(e)}")
        return "Erro ao gerar PDF", 500
