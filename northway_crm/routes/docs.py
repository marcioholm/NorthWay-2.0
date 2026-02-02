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

@docs_bp.route('/diagnostic-aprofundado')
@login_required
def presentation_diagnostic():
    return render_template('docs/presentation_diagnostic.html')

@docs_bp.route('/playbook-bdr')
@login_required
def presentation_playbook_bdr():
    return render_template('docs/playbook_bdr.html')

@docs_bp.route('/onboarding-institucional')
@login_required
def presentation_onboarding():
    return render_template('docs/presentation_onboarding.html')

@docs_bp.route('/custo-da-inacao')
@login_required
def presentation_cost_of_inaction():
    return render_template('docs/presentation_cost_of_inaction.html')

@docs_bp.route('/ebook-marketing-pilares')
@login_required
def ebook_marketing_pillars():
    return render_template('docs/ebook_marketing_pillars.html')

@docs_bp.route('/library')
@login_required
def library():
    from models import ContractTemplate, LibraryBook
    from flask_login import current_user
    
    # 1. Fetch Company-specific Templates (Legacy "Private Library")
    template_docs = ContractTemplate.query.filter_by(
        company_id=current_user.company_id, 
        active=True, 
        type='library_doc'
    ).order_by(ContractTemplate.created_at.desc()).all()

    # 2. Fetch System Library Books (Granular Access)
    # Join with association table implicitly via relationship
    system_books_raw = current_user.company.accessible_books.filter_by(active=True).all()
    
    # Validate route_names to prevent url_for crashes
    from flask import current_app
    system_books = []
    for book in system_books_raw:
        if book.route_name:
            # Check if endpoint exists in the URL map
            if book.route_name not in current_app.view_functions:
                # If it doesn't exist, we nullify it temporarily for the template
                # so it falls back to 'view_book' (or we just hide it)
                book.route_name = None 
        system_books.append(book)
    
    return render_template('docs/library.html', template_docs=template_docs, system_books=system_books)

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

@docs_bp.route('/book/<int:id>')
@login_required
def view_book(id):
    from models import LibraryBook
    from flask_login import current_user
    from flask import abort
    
    book = LibraryBook.query.get_or_404(id)
    
    # Security Check: Ensure book is accessible to user's company or user is super admin
    is_super = getattr(current_user, 'is_super_admin', False)
    if not is_super and current_user.company not in book.allowed_companies:
        abort(403)
        
    return render_template('docs/view_book.html', book=book)
