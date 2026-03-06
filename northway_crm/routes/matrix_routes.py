from flask import Blueprint, request, jsonify, abort
from flask_login import login_required, current_user
from models import db, Client, AudienceMatrix, get_now_br
import uuid

matrix_bp = Blueprint('matrix', __name__)

@matrix_bp.route('/clients/<int:client_id>/matrix', methods=['POST'])
@login_required
def create_matrix(client_id):
    client = Client.query.get_or_404(client_id)
    if client.company_id != current_user.company_id:
        abort(403)
    
    data = request.get_json()
    new_matrix = AudienceMatrix(
        id=str(uuid.uuid4()),
        client_id=client_id,
        product=data.get('product', ''),
        status=data.get('status', 'rascunho'),
        audiences=data.get('audiences', []),
        created_at=get_now_br(),
        updated_at=get_now_br()
    )
    
    db.session.add(new_matrix)
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'id': new_matrix.id,
        'message': 'Matriz criada com sucesso'
    }), 201

@matrix_bp.route('/matrix/<matrix_id>', methods=['GET'])
@login_required
def get_matrix(matrix_id):
    matrix = AudienceMatrix.query.get_or_404(matrix_id)
    # Check if client belongs to same company
    if matrix.client.company_id != current_user.company_id:
        abort(403)
        
    return jsonify({
        'id': matrix.id,
        'client_id': matrix.client_id,
        'product': matrix.product,
        'status': matrix.status,
        'audiences': matrix.audiences,
        'created_at': matrix.created_at.isoformat() if matrix.created_at else None,
        'updated_at': matrix.updated_at.isoformat() if matrix.updated_at else None
    })

@matrix_bp.route('/matrix/<matrix_id>', methods=['PUT'])
@login_required
def update_matrix(matrix_id):
    matrix = AudienceMatrix.query.get_or_404(matrix_id)
    if matrix.client.company_id != current_user.company_id:
        abort(403)
        
    data = request.get_json()
    matrix.product = data.get('product', matrix.product)
    matrix.status = data.get('status', matrix.status)
    matrix.audiences = data.get('audiences', matrix.audiences)
    matrix.updated_at = get_now_br()
    
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'message': 'Matriz atualizada com sucesso'
    })

@matrix_bp.route('/matrix/<matrix_id>', methods=['DELETE'])
@login_required
def delete_matrix(matrix_id):
    matrix = AudienceMatrix.query.get_or_404(matrix_id)
    if matrix.client.company_id != current_user.company_id:
        abort(403)
        
    db.session.delete(matrix)
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'message': 'Matriz excluída com sucesso'
    })
