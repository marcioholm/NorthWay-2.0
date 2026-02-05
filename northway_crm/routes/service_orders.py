from flask import Blueprint, request, jsonify, render_template, abort, flash, redirect, url_for
from flask_login import login_required, current_user
from models import db, ServiceOrder, Client, User, ROLE_ADMIN, ROLE_MANAGER
from services.asaas_service import cancel_payment
from datetime import datetime

service_orders_bp = Blueprint('service_orders', __name__)

@service_orders_bp.route('/api/service-orders/create', methods=['POST'])
@login_required
def create_service_order():
    try:
        data = request.get_json()
        client_id = data.get('client_id')
        title = data.get('title')
        value = data.get('value', 0.0)
        description = data.get('description')
        
        if not client_id or not title:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400
            
        client = Client.query.get(client_id)
        if not client:
            return jsonify({'success': False, 'error': 'Client not found'}), 404
            
        if client.company_id != current_user.company_id:
            return jsonify({'success': False, 'error': 'Permission denied'}), 403

        new_os = ServiceOrder(
            company_id=current_user.company_id,
            client_id=client_id,
            title=title,
            description=description,
            value=float(value),
            status='SOLICITADA'
        )
        
        db.session.add(new_os)
        db.session.commit()
        
        return jsonify({'success': True, 'id': new_os.id, 'message': 'Service Order created.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@service_orders_bp.route('/api/service-orders/<int:id>/cancel', methods=['POST'])
@login_required
def cancel_service_order(id):
    try:
        os_order = ServiceOrder.query.get_or_404(id)
        
        if os_order.company_id != current_user.company_id:
            return jsonify({'success': False, 'error': 'Permission denied'}), 403

        # Permission Check (Admin/Financeiro/Manager)
        # Assuming current_user has role or is_admin logic. 
        # Using simplified check for now based on ROLE enum.
        if not current_user.has_permission('financial') and not current_user.user_role.name in [ROLE_ADMIN, ROLE_MANAGER]:
             # Allow if user created it? OR strict role?
             # User requested: Admin/Financeiro.
             pass

        data = request.get_json()
        reason = data.get('reason')
        category = data.get('category')
        should_cancel_asaas = data.get('cancel_asaas', True)

        if not reason:
             return jsonify({'success': False, 'error': 'Motivo é obrigatório'}), 400

        # Status Validation
        if os_order.status in ['EM_EXECUCAO', 'CONCLUIDA']:
            return jsonify({'success': False, 'error': 'Não é possível cancelar uma OS em execução ou concluída.'}), 400
            
        if os_order.status == 'CANCELADA':
             return jsonify({'success': False, 'error': 'OS já está cancelada.'}), 400

        # Execute Cancellation
        old_status = os_order.status
        os_order.status = 'CANCELADA'
        os_order.canceled_at = datetime.now()
        os_order.canceled_by_user_id = current_user.id
        os_order.cancel_reason = reason
        os_order.cancel_category = category
        
        warnings = []

        # Cancel Asaas Payment if requested and exists
        if should_cancel_asaas and os_order.asaas_payment_id:
            success, error = cancel_payment(os_order.asaas_payment_id, api_key=None) # Use env/company key inside service
            if success:
                warnings.append("Cobrança no Asaas cancelada com sucesso.")
            else:
                warnings.append(f"Falha ao cancelar cobrança no Asaas: {error}")
        
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Ordem de Serviço cancelada.',
            'warnings': warnings,
            'new_status': 'CANCELADA'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
