from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file, current_app
from flask_login import login_required, current_user
from models import db, User, Company, CommercialPresentation
from datetime import datetime, timedelta
import uuid
import os

marketing_bp = Blueprint('marketing', __name__)

@marketing_bp.route('/marketing/presentation')
@login_required
def presentation():
    if getattr(current_user, 'role', '') not in ['admin', 'gestor']:
        flash('Acesso restrito a administradores e gestores.', 'error')
        return redirect(url_for('dashboard.index'))
    
    # Get last 20 presentations
    presentations = CommercialPresentation.query.filter_by(company_id=current_user.company_id).order_by(CommercialPresentation.gerado_em.desc()).limit(20).all()
    
    return render_template('marketing/presentation.html', presentations=presentations, now=datetime.utcnow())

@marketing_bp.route('/api/marketing/presentation/generate', methods=['POST'])
@login_required
def generate_presentation():
    if getattr(current_user, 'role', '') not in ['admin', 'gestor']:
        return jsonify({'error': 'Unauthorized'}), 403
    
    from services.presentation_service import PresentationService
    
    data = request.get_json()
    if not data or not data.get('prospect_name'):
        return jsonify({'error': 'Nome do prospect é obrigatório'}), 400
        
    try:
        # 1. Generate PDF
        pdf_bytes = PresentationService.generate_pdf(data)
        
        # 2. Upload to Supabase Storage
        unique_id = str(uuid.uuid4())
        filename = f"present_{unique_id}.pdf"
        bucket = 'company-assets'
        path = f"presentations/{filename}"
        
        pdf_url = None
        if hasattr(current_app, 'supabase') and current_app.supabase:
            try:
                # Content type is important for browser viewing
                current_app.supabase.storage.from_(bucket).upload(path, pdf_bytes, {"content-type": "application/pdf"})
                pdf_url = current_app.supabase.storage.from_(bucket).get_public_url(path)
                print(f"✅ Presentation uploaded: {pdf_url}")
            except Exception as e:
                print(f"❌ Storage error: {e}")
                # Fallback or error? User wants a link, so if it fails, we should probably error.
                return jsonify({'error': f'Erro no armazenamento: {str(e)}'}), 500
        else:
            return jsonify({'error': 'Serviço de armazenamento não configurado'}), 500

        # 3. Save to DB
        expira_em = datetime.utcnow() + timedelta(days=7)
        # Adjust for display/comparison if needed, but UTC is fine for backend
        
        new_p = CommercialPresentation(
            consultor_id=current_user.id,
            company_id=current_user.company_id,
            prospect_name=data.get('prospect_name'),
            prospect_logo=data.get('prospect_logo'),
            observacao=data.get('observacao'),
            pdf_url=pdf_url,
            expira_em=expira_em
        )
        
        db.session.add(new_p)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'download_url': pdf_url,
            'public_link': url_for('marketing.public_presentation', token=new_p.token, _external=True)
        })
        
    except Exception as e:
        current_app.logger.error(f"Error generating presentation: {str(e)}")
        return jsonify({'error': str(e)}), 500

@marketing_bp.route('/apresentacao/<token>')
def public_presentation(token):
    presentation = CommercialPresentation.query.filter_by(token=token).first_or_404()
    
    # Check expiration
    if presentation.expira_em < datetime.utcnow():
        return render_template('marketing/error_public.html'), 404
        
    return redirect(presentation.pdf_url)

@marketing_bp.route('/api/marketing/presentation/<id>', methods=['DELETE'])
@login_required
def delete_presentation(id):
    if getattr(current_user, 'role', '') not in ['admin', 'gestor']:
        return jsonify({'error': 'Unauthorized'}), 403
        
    presentation = CommercialPresentation.query.filter_by(id=id, company_id=current_user.company_id).first_or_404()
    
    # TODO: Delete from Supabase Storage? 
    # For now, just delete from DB
    db.session.delete(presentation)
    db.session.commit()
    
    return jsonify({'success': True})
