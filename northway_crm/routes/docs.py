from flask import Blueprint, render_template
from flask_login import login_required

docs_bp = Blueprint('docs', __name__)

@docs_bp.route('/manual-usuario')
@login_required
def user_manual():
    return render_template('docs/user_manual.html')

@docs_bp.route('/apresentacao-institucional')
@login_required
def presentation_institutional():
    return render_template('docs/presentation_institutional.html')

@docs_bp.route('/playbook-comercial')
@login_required
def playbook_comercial():
    return render_template('docs/playbook_comercial.html')


@docs_bp.route('/playbook-processos')
@login_required
def playbook_processos():
    return render_template('docs/playbook_processos.html')


@docs_bp.route('/playbook-treinamento')
@login_required
def playbook_treinamento():
    return render_template('docs/playbook_treinamento.html')

@docs_bp.route('/presentation-offer-main')
@login_required
def presentation_offer_main():
    return render_template('docs/presentation_offer_main.html')

@docs_bp.route('/presentation-offer-downsell')
@login_required
def presentation_offer_downsell():
    return render_template('docs/presentation_offer_downsell.html')


@docs_bp.route('/presentation-consultancy')
@login_required
def presentation_consultancy():
    return render_template('docs/presentation_consultancy.html')

@docs_bp.route('/library')
@login_required
def library():
    from models import ContractTemplate
    from flask_login import current_user
    
    # Fetch company-specific library documents
    library_docs = ContractTemplate.query.filter_by(
        company_id=current_user.company_id, 
        active=True, 
        type='library_doc'
    ).order_by(ContractTemplate.created_at.desc()).all()
    
    return render_template('docs/library.html', library_docs=library_docs)

@docs_bp.route('/view/<int:id>')
@login_required
def view_document(id):
    from models import ContractTemplate
    from flask_login import current_user
    from flask import abort
    
    doc = ContractTemplate.query.get_or_404(id)
    
    # Security Check: Ensure document belongs to user's company
    if doc.company_id != current_user.company_id:
        abort(403)
        
    return render_template('docs/view_document.html', doc=doc)
