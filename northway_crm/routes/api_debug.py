from flask import Blueprint, jsonify, request
from services.email_service import EmailService

api_debug_bp = Blueprint('api_debug', __name__)

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
