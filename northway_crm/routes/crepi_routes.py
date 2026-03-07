from flask import Blueprint, request, jsonify, abort
from flask_login import login_required, current_user
from models import db, Client, CREPIDiagnostico, CREPIPremissa, get_now_br
import uuid

crepi_bp = Blueprint('crepi', __name__)

@crepi_bp.route('/api/clients/<int:client_id>/crepi/create', methods=['POST'])
@login_required
def create_crepi(client_id):
    client = Client.query.get_or_404(client_id)
    if client.company_id != current_user.company_id:
        abort(403)
    
    data = request.get_json() or {}
    new_diag = CREPIDiagnostico(
        id=str(uuid.uuid4()),
        client_id=client_id,
        projeto=data.get('projeto', 'Novo Projeto CREPI'),
        status='rascunho',
        created_at=get_now_br(),
        updated_at=get_now_br()
    )
    
    db.session.add(new_diag)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'id': new_diag.id,
        'message': 'Diagnóstico CREPI criado com sucesso'
    }), 201

@crepi_bp.route('/api/clients/<int:client_id>/crepi/list', methods=['GET'])
@login_required
def list_crepi(client_id):
    client = Client.query.get_or_404(client_id)
    if client.company_id != current_user.company_id:
        abort(403)
        
    diagnosticos = CREPIDiagnostico.query.filter_by(client_id=client_id).order_by(CREPIDiagnostico.created_at.desc()).all()
    
    data = []
    for diag in diagnosticos:
        data.append({
            'id': diag.id,
            'projeto': diag.projeto,
            'status': diag.status,
            'created_at': diag.created_at.isoformat() if diag.created_at else None,
            'total_premissas': len(diag.premissas),
            'critical_count': sum(1 for p in diag.premissas if p.score > 40),
            'medium_count': sum(1 for p in diag.premissas if 15 < p.score <= 40),
            'low_count': sum(1 for p in diag.premissas if p.score <= 15)
        })
        
    return jsonify({
        'success': True,
        'data': data
    })

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
        
    # Standardize the response format
    return jsonify({
        'success': True,
        'data': {
            'id': diag.id,
            'client_id': diag.client_id,
            'projeto_nome': diag.projeto,
            'status': diag.status,
            'premissas': premissas,
            'created_at': diag.created_at.isoformat() if diag.created_at else None,
            'updated_at': diag.updated_at.isoformat() if diag.updated_at else None
        }
    })

@crepi_bp.route('/api/clients/<int:client_id>/crepi/<crepi_id>/update', methods=['POST'])
@login_required
def update_crepi(client_id, crepi_id):
    diag = CREPIDiagnostico.query.get_or_404(crepi_id)
    if diag.client.company_id != current_user.company_id or diag.client_id != client_id:
        abort(403)
        
    data = request.get_json() or {}
    diag.projeto = data.get('projeto_nome', diag.projeto)
    diag.status = data.get('status', diag.status)
    diag.updated_at = get_now_br()
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Diagnóstico atualizado com sucesso'
    })

@crepi_bp.route('/api/clients/<int:client_id>/crepi/<crepi_id>/premises/save', methods=['POST'])
@login_required
def save_premises(client_id, crepi_id):
    diag = CREPIDiagnostico.query.get_or_404(crepi_id)
    if diag.client.company_id != current_user.company_id or diag.client_id != client_id:
        abort(403)
        
    data = request.get_json() or {}
    premises_data = data.get('premissas', [])
    
    existing_ids = {p.id for p in diag.premissas}
    received_ids = {p.get('id') for p in premises_data if p.get('id')}
    
    for p in diag.premissas:
        if p.id not in received_ids:
            db.session.delete(p)
            
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
        p.probabilidade = int(p_data.get('probabilidade', 0) or 0)
        p.impacto = int(p_data.get('impacto', 0) or 0)
        p.score = p.probabilidade * p.impacto
        p.decisao_consultor = p_data.get('decisao_consultor', '')
        p.updated_at = get_now_br()
        
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Premissas salvas com sucesso'
    })

@crepi_bp.route('/api/clients/<int:client_id>/crepi/<crepi_id>/delete', methods=['POST'])
@login_required
def delete_crepi(client_id, crepi_id):
    diag = CREPIDiagnostico.query.get_or_404(crepi_id)
    if diag.client.company_id != current_user.company_id or diag.client_id != client_id:
        abort(403)
        
    db.session.delete(diag)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Diagnóstico CREPI excluído com sucesso'
    })
