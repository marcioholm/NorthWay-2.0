from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user

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

@docs_bp.route('/diagnostic-combined')
@login_required
def presentation_diagnostic_combined():
    return render_template('docs/presentation_combined_diagnostic.html')

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

@docs_bp.route('/ebook-oportunidades-norte-pioneiro')
@login_required
def ebook_norte_pioneiro():
    return render_template('docs/ebook_norte_pioneiro.html')

@docs_bp.route('/ebook-oportunidades-campos-gerais')
@login_required
def ebook_campos_gerais():
    return render_template('docs/ebook_campos_gerais.html')

@docs_bp.route('/growth-framework')
@login_required
def presentation_growth_framework():
    return render_template('docs/presentation_growth_framework.html')

@docs_bp.route('/playbook-north-direcao')
@login_required
def playbook_north_direcao():
    return render_template('docs/pop_north_direcao.html')

@docs_bp.route('/ebook-quanto-vale-a-hora')
@login_required
def ebook_time_value():
    return render_template('docs/ebook_time_value.html')

@docs_bp.route('/ebook-institucional')
# Public access for sharing via link
def ebook_institutional():
    return render_template('docs/ebook_institutional.html')

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

@docs_bp.route('/apresentacao-crm-v2')
@login_required
def presentation_crm_v2():
    return render_template('docs/presentation_crm_v2.html')

@docs_bp.route('/guide-captacao')
@login_required
def guide_captacao():
    return render_template('docs/guide_captacao.html')

@docs_bp.route('/manual-edicao')
@login_required
def manual_edicao():
    return render_template('docs/manual_edicao.html')
@docs_bp.route('/api/docs/sync-library')
@docs_bp.route('/master/api/docs/sync-library')
@login_required
def sync_library():
    import traceback
    results = []
    try:
        from models import db, LibraryBook, Company, User
        
        # 0. Emergency Schema Sync (Tables)
        db.create_all()
        results.append("Schema synced via create_all()")
        
        # 1. PERMISSION CHECK (Deeper/Safer)
        is_super = getattr(current_user, 'is_super_admin', False)
        is_admin = getattr(current_user, 'role', '') == 'admin'
        
        if not (is_super or is_admin):
            return jsonify({
                'success': False,
                'error': 'Unauthorized', 
                'explanation': 'This route requires Super Admin or Admin role.'
            }), 403
            
        # --- CLEANUP: Remove old PDF-based books as requested ---
        old_titles = ['Apresentação Oficial NorthWay CRM', 'Manual de Funcionalidades CRM']
        for title in old_titles:
            book = LibraryBook.query.filter_by(title=title).first()
            if book:
                # 1. Clear association explicitly with raw SQL
                db.session.execute(db.text("DELETE FROM library_book_company_association WHERE book_id = :id"), {"id": book.id})
                # 2. Delete book
                db.session.delete(book)
        
        db.session.flush()
        results.append("Cleaned up old PDF materials (v2 logic)")
        
        # --- REGISTER: New Interactive Presentation ---
        title = "NorthWay CRM: Apresentação Oficial 2.0"
        desc = "Apresentação interativa de alta performance do ecossistema NorthWay."
        cat = "Apresentação"
        
        existing = LibraryBook.query.filter_by(title=title).first()
        if not existing:
            new_book = LibraryBook(
                title=title, 
                description=desc, 
                category=cat, 
                route_name='docs.presentation_crm_v2', 
                active=True
            )
            db.session.add(new_book)
            db.session.flush()
            
            companies = Company.query.all()
            for company in companies:
                if company not in new_book.allowed_companies:
                    new_book.allowed_companies.append(company)
            results.append(f"Registered: {title}")
        else:
            existing.description = desc
            existing.route_name = 'docs.presentation_crm_v2'
            results.append(f"Updated: {title}")
                
        db.session.commit()
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc(),
            'partial_results': results
        }), 500
