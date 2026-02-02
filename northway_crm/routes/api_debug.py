from flask import Blueprint, jsonify, request, render_template, current_app
from services.email_service import EmailService
from models import EMAIL_TEMPLATES, Company, User
from datetime import datetime

api_debug_bp = Blueprint('api_debug', __name__)

@api_debug_bp.route('/debug/emails', methods=['GET'])
def list_email_templates():
    """
    List all available email templates for preview.
    """
    templates = [t.name for t in EMAIL_TEMPLATES]
    
    html = """
    <html>
    <head>
        <title>Email Templates Preview</title>
        <style>
            body { font-family: sans-serif; padding: 40px; }
            h1 { color: #DC2626; }
            ul { list-style: none; padding: 0; }
            li { margin: 10px 0; }
            a { 
                display: block; 
                padding: 15px; 
                background: #f3f4f6; 
                border-radius: 8px; 
                text-decoration: none; 
                color: #1f2937; 
                font-weight: bold;
                border: 1px solid #e5e7eb;
            }
            a:hover { background: #fee2e2; border-color: #DC2626; }
        </style>
    </head>
    <body>
        <h1>📧 Email Templates Preview</h1>
        <p>Click below to preview rendered templates with mock data.</p>
        <ul>
    """
    
    for t in templates:
        html += f'<li><a href="/debug/emails/{t}" target="_blank">{t}</a></li>'
        
    html += """
        </ul>
    </body>
    </html>
    """
    return html

@api_debug_bp.route('/debug/emails/<template_name>', methods=['GET'])
def preview_email_template(template_name):
    """
    Render a specific email template with mock data.
    """
    try:
        # Resolve Enum
        template_enum = EMAIL_TEMPLATES[template_name]
        filename = EmailService.TEMPLATE_FILES.get(template_enum)
        
        if not filename:
            return f"<h1>Error</h1><p>No file mapped for template: {template_name}</p>", 404
            
        # Mock Data
        mock_user = User(name="Usuário Teste", email="teste@northway.com")
        mock_company = Company(name="Empresa Exemplo Ltda", logo_filename="default_logo.png")
        mock_context = {
            'user': mock_user,
            'company': mock_company,
            'reset_url': 'https://crm.northwaycompany.com.br/reset-password/TOKEN-EXEMPLO',
            'app_name': 'NorthWay Testing',
            'now': datetime.now()
        }
        
        return render_template(f"emails/{filename}", **mock_context)
        
    except KeyError:
        return f"<h1>Error</h1><p>Invalid template name: {template_name}</p>", 404
    except Exception as e:
        return f"<h1>Render Error</h1><pre>{str(e)}</pre>", 500

@api_debug_bp.route('/api/email/test', methods=['GET'])
def test_email():
    """
    Test Resend configuration.
    Usage: /api/email/test?to=your_email@example.com
    P.S. Requires RESEND_API_KEY env var set.
    """
    to_email = request.args.get('to')
    if not to_email:
        return jsonify({'error': 'Missing to parameter'}), 400
        
    subject = "Teste Resend - NorthWay"
    html_content = """
    <div style="font-family: sans-serif; padding: 20px;">
        <h1 style="color: #DC2626;">Teste de Envio ✅</h1>
        <p>Se você recebeu este email, a integração com Resend está funcionando corretamente.</p>
        <p>Provider ID: SERÁ GERADO</p>
    </div>
    """
    
    success, result = EmailService.send_email(
        to=to_email,
        subject=subject,
        html_content=html_content,
        company_id=None, # Global system test
        user_id=None
    )
    
    if success:
         return jsonify({'status': 'success', 'result': str(result)})
    else:
         return jsonify({'status': 'error', 'message': str(result)}), 500
