from flask import Blueprint, render_template, jsonify
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

@docs_bp.route('/briefing-aquisicao')
@login_required
def briefing_northway():
    return render_template('docs/briefing_northway.html')

@docs_bp.route('/scripts-vendas')
@login_required
def scripts_northway():
    return render_template('docs/scripts_northway.html')

@docs_bp.route('/guide-captacao')
@login_required
def guide_captacao():
    return render_template('docs/guide_captacao.html')

@docs_bp.route('/manual-edicao')
@login_required
def manual_edicao():
    return render_template('docs/manual_edicao.html')
@docs_bp.route('/api/docs/sync-library')
@login_required
def sync_library():
    # Emergency relaxation: allow admin role too if super_admin is not set
    is_super = getattr(current_user, 'is_super_admin', False)
    is_admin = getattr(current_user, 'role', '') == 'admin'
    
    if not (is_super or is_admin):
        return jsonify({'error': 'Unauthorized', 'is_super': is_super, 'role': getattr(current_user, 'role', '')}), 403
        
    import traceback
    results = []
    try:
        from models import db, LibraryBook, Company
        
        # 0. Emergency Schema Sync
        db.create_all()
        results.append("Schema synced via create_all()")
        
        # --- BOOK 1: APRESENTAÇÃO ---
        html_presentation = """
        <div class="presentation-header text-center mb-12">
            <h1 style="color: #fa0102; font-size: 3rem; font-weight: 900; margin-bottom: 0.5rem;">NORTHWAY CRM</h1>
            <p style="color: #666; font-size: 1.25rem;">Ecossistema Completo de Vendas, Operações e Inteligência</p>
        </div>
        <div style="background: #000; color: #fff; padding: 3rem; border-radius: 2rem; text-align: center; margin-top: 2rem;">
            <h2 style="font-weight: 900; margin-bottom: 1rem;">PREPARADO PARA ESCALAR?</h2>
            <a href="/static/library/apresentacao_crm_oficial.pdf" target="_blank" style="background: #fa0102; color: white; padding: 1rem 2.5rem; border-radius: 1rem; font-weight: bold; text-decoration: none;"> BAIXAR PDF COMPLETO </a>
        </div>
        """
        
        # --- BOOK 2: MANUAL ---
        html_manual = """
        <div class="presentation-header text-center mb-12">
            <h1 style="color: #fa0102; font-size: 2.5rem; font-weight: 800; margin-bottom: 0.5rem;">Manual de Funcionalidades</h1>
            <p style="color: #666;">Guia Completo do Ecossistema NorthWay</p>
        </div>
        <div style="background: #fa0102; color: #fff; padding: 2rem; border-radius: 1rem; text-align: center; margin-top: 2rem;">
            <a href="/static/library/manual_crm_northway.pdf" target="_blank" style="color: white; font-weight: bold; text-decoration: none;"> → BAIXAR MANUAL EM PDF </a>
        </div>
        """
        
        books_to_add = [
            ('Apresentação Oficial NorthWay CRM', 'Apresentação completa de ponta a ponta.', 'Comercial', html_presentation),
            ('Manual de Funcionalidades CRM', 'Guia prático de utilização.', 'Processos', html_manual)
        ]
        
        companies = Company.query.all()
        results.append(f"Found {len(companies)} companies")
        
        for title, desc, cat, content in books_to_add:
            existing = LibraryBook.query.filter_by(title=title).first()
            if existing:
                existing.content = content
                existing.description = desc
                results.append(f"Updated: {title}")
            else:
                book = LibraryBook(title=title, description=desc, category=cat, content=content, active=True)
                db.session.add(book)
                db.session.flush()
                for company in companies:
                    # Check if already has access (prevent unique constraint violations if any)
                    if company not in book.allowed_companies:
                        book.allowed_companies.append(company)
                results.append(f"Created: {title}")
                
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
