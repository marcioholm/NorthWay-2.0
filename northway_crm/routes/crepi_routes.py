from flask import Blueprint, request, jsonify, abort
from flask_login import login_required, current_user
from models import db, Client, CREPIDiagnostico, CREPIPremissa, get_now_br
import uuid

crepi_bp = Blueprint('crepi', __name__)

@crepi_bp.route('/clients/<int:client_id>/crepi', methods=['POST'])
@login_required
def create_crepi(client_id):
    client = Client.query.get_or_404(client_id)
    if client.company_id != current_user.company_id:
        abort(403)
    
    data = request.get_json()
    new_diag = CREPIDiagnostico(
        id=str(uuid.uuid4()),
        client_id=client_id,
        projeto=data.get('projeto', 'Novo Projeto'),
        status='rascunho',
        created_at=get_now_br(),
        updated_at=get_now_br()
    )
    
    db.session.add(new_diag)
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'id': new_diag.id,
        'message': 'Diagnóstico CREPI criado com sucesso'
    }), 201

@crepi_bp.route('/crepi/<crepi_id>', methods=['GET'])
@login_required
def get_crepi(crepi_id):
    diag = CREPIDiagnostico.query.get_or_404(crepi_id)
    if diag.client.company_id != current_user.company_id:
        abort(403)
        
    premissas = []
    for p in diag.premissas:
        premissas.append({
            'id': p.id,
            'ordem': p.ordem,
            'nome': p.nome,
            'categoria': p.categoria,
            'causa': p.causa,
            'risco': p.risco,
            'efeito': p.efeito,
            'probabilidade': p.probabilidade,
            'impacto': p.impacto,
            'score': p.score,
            'decisao_consultor': p.decisao_consultor
        })
        
    return jsonify({
        'id': diag.id,
        'client_id': diag.client_id,
        'projeto': diag.projeto,
        'status': diag.status,
        'premissas': premissas,
        'created_at': diag.created_at.isoformat() if diag.created_at else None,
        'updated_at': diag.updated_at.isoformat() if diag.updated_at else None
    })

@crepi_bp.route('/crepi/<crepi_id>', methods=['PUT'])
@login_required
def update_crepi(crepi_id):
    diag = CREPIDiagnostico.query.get_or_404(crepi_id)
    if diag.client.company_id != current_user.company_id:
        abort(403)
        
    data = request.get_json()
    diag.projeto = data.get('projeto', diag.projeto)
    diag.status = data.get('status', diag.status)
    diag.updated_at = get_now_br()
    
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'message': 'Diagnóstico atualizado com sucesso'
    })

@crepi_bp.route('/crepi/<crepi_id>/premises', methods=['POST'])
@login_required
def save_premises(crepi_id):
    diag = CREPIDiagnostico.query.get_or_404(crepi_id)
    if diag.client.company_id != current_user.company_id:
        abort(403)
        
    data = request.get_json()
    premises_data = data.get('premissas', [])
    
    # Simple sync: Delete existing and re-add or update based on ID
    # For simplicity in this wizard, we can delete all and recreate if we want to preserve order exactly
    # But updating existing ones is better to avoid ID drift if they are referenced
    
    existing_ids = {p.id for p in diag.premissas}
    received_ids = {p.get('id') for p in premises_data if p.get('id')}
    
    # Delete removed premises
    for p in diag.premissas:
        if p.id not in received_ids:
            db.session.delete(p)
            
    # Update or Create
    for i, p_data in enumerate(premises_data):
        p_id = p_data.get('id')
        if p_id and p_id in existing_ids:
            p = next(x for x in diag.premissas if x.id == p_id)
        else:
            p = CREPIPremissa(id=p_id or str(uuid.uuid4()), diagnostico_id=crepi_id)
            db.session.add(p)
            
        p.ordem = i
        p.nome = p_data.get('nome', 'Nova Premissa')
        p.categoria = p_data.get('categoria', '')
        p.causa = p_data.get('causa', '')
        p.risco = p_data.get('risco', '')
        p.efeito = p_data.get('efeito', '')
        p.probabilidade = int(p_data.get('probabilidade', 0))
        p.impacto = int(p_data.get('impacto', 0))
        p.score = p.probabilidade * p.impacto
        p.decisao_consultor = p_data.get('decisao_consultor', '')
        p.updated_at = get_now_br()
        
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'message': 'Premissas salvas com sucesso'
    })

@crepi_bp.route('/crepi/<crepi_id>', methods=['DELETE'])
@login_required
def delete_crepi(crepi_id):
    diag = CREPIDiagnostico.query.get_or_404(crepi_id)
    if diag.client.company_id != current_user.company_id:
        abort(403)
        
    db.session.delete(diag)
    db.session.commit()
    
    return jsonify({
        'status': 'success',
        'message': 'Diagnóstico CREPI excluído com sucesso'
    })
