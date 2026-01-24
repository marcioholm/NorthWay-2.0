from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user
# Defer model imports to avoid circular dependency with app initialization
# from models import db, User, Role, ROLE_ADMIN, ROLE_MANAGER, ROLE_SALES
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
import os
import time
import base64

admin_bp = Blueprint('admin', __name__)

# ... (rest of file)

        # Logo Upload Logic
        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename != '':
                try:
                    filename = secure_filename(file.filename)
                    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'png'
                    unique_filename = f"logo_{company.id}_{int(time.time())}.{ext}"
                    
                    uploaded = False
                    # 1. Try Supabase Storage
                    if hasattr(current_app, 'supabase') and current_app.supabase:
                        try:
                            # Reset cursor ensures clean read
                            file.seek(0)
                            bucket = 'company-assets'
                            file_content = file.read()
                            path = f"logos/{unique_filename}"
                            current_app.supabase.storage.from_(bucket).upload(path, file_content, {"content-type": file.content_type})
                            public_url = current_app.supabase.storage.from_(bucket).get_public_url(path)
                            company.logo_filename = public_url
                            # Clear base64 if cloud upload works to save DB space (optional, but good practice)
                            company.logo_base64 = None 
                            uploaded = True
                            print(f"✅ Uploaded logo to Supabase: {public_url}")
                        except Exception as storage_e:
                            print(f"⚠️ Supabase Upload Failed: {storage_e}")
                            # Fallback continues below
                    
                    # 2. Fallback: Base64 Database Storage (Persistence Guarantee)
                    if not uploaded:
                        try:
                            print("💾 Falling back to Base64 Database Storage...")
                            file.seek(0) # Reset cursor again
                            file_data = file.read()
                            base64_str = base64.b64encode(file_data).decode('utf-8')
                            company.logo_base64 = base64_str
                            # Set filename to indicate base64 mode if needed, or keep for reference
                            # company.logo_filename = "base64" 
                            uploaded = True
                            print("✅ Logo saved as Base64 in Database.")
                        except Exception as b64_e:
                            print(f"❌ Base64 Conversion Failed: {b64_e}")
                            raise b64_e # Trigger outer except

                except Exception as e:
                    print(f"❌ Error uploading logo: {e}")
                    flash(f'Erro ao salvar logotipo: {str(e)}', 'error')
    
        db.session.commit()
        flash('Configurações da empresa atualizadas!', 'success')
        return redirect(url_for('admin.company_settings'))
    
    return render_template('company_settings.html', company=company)

@admin_bp.route('/settings/integrations', methods=['GET', 'POST'])
def settings_integrations():
    from models import db, Integration
    import json
    
    if not current_user.company_id:
        abort(403)

    if request.method == 'POST':
        service = request.form.get('service')
        api_key = request.form.get('api_key')
        if service and api_key:
            # Strict filter
            intg = Integration.query.filter(Integration.company_id == current_user.company_id, Integration.service == service).first()
            if not intg:
                intg = Integration(company_id=current_user.company_id, service=service)
                db.session.add(intg)
            intg.api_key = api_key
            intg.is_active = True
            db.session.commit()
            flash('Integração salva!', 'success')
        return redirect(url_for('admin.settings_integrations'))

    # Strict filter
    integrations = Integration.query.filter(Integration.company_id == current_user.company_id).all()
    integrations_map = {i.service: i for i in integrations}
    
    zapi_config = {}
    if 'z_api' in integrations_map:
        try: zapi_config = json.loads(integrations_map['z_api'].config_json or '{}')
        except: pass
        
    return render_template('settings_integrations.html', company=current_user.company, integrations_map=integrations_map, zapi_config=zapi_config)

@admin_bp.route('/settings/integrations/delete/<service>', methods=['POST'])
def delete_integration(service):
    from models import db, Integration
    if not current_user.company_id:
        abort(403)
        
    intg = Integration.query.filter_by(company_id=current_user.company_id, service=service).first()
    if intg:
        db.session.delete(intg)
        db.session.commit()
        flash(f'Integração {service} removida.', 'success')
    else:
        flash('Integração não encontrada.', 'error')
        
    return redirect(url_for('admin.settings_integrations'))

@admin_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    from models import db
    if request.method == 'POST':
        current_user.name = request.form.get('name')
        current_user.phone = request.form.get('phone')
        current_user.status_message = request.form.get('status_message')
        
        password = request.form.get('password')
        if password:
            current_user.password_hash = generate_password_hash(password)
            
        db.session.commit()
        flash('Perfil atualizado!', 'success')
        return redirect(url_for('admin.profile'))
        
    return render_template('profile.html', user=current_user)

@admin_bp.route('/settings')
@login_required
def settings_index():
    return redirect(url_for('admin.profile'))
