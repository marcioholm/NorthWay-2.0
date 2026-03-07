from flask import Blueprint, request, jsonify, abort
from flask_login import login_required, current_user
from models import db, SwotAnalise, SwotItem, Client
from datetime import date
from utils import get_now_br
import uuid

swot_bp = Blueprint('swot', __name__)

@swot_bp.route('/api/clients/<int:client_id>/swot', methods=['GET'])
@login_required
def list_swot(client_id):
    client = Client.query.get_or_404(client_id)
    if client.company_id != current_user.company_id:
        abort(403)
        
    analises = SwotAnalise.query.filter_by(client_id=client_id).order_by(SwotAnalise.data_analise.desc(), SwotAnalise.created_at.desc()).all()
    
    data = []
    for analise in analises:
        forcas = sum(1 for item in analise.itens if item.quadrante == 'forca')
        fraquezas = sum(1 for item in analise.itens if item.quadrante == 'fraqueza')
        oportunidades = sum(1 for item in analise.itens if item.quadrante == 'oportunidade')
        ameacas = sum(1 for item in analise.itens if item.quadrante == 'ameaca')
        
        data.append({
            'id': analise.id,
            'contexto': analise.contexto,
            'data_analise': analise.data_analise.isoformat() if analise.data_analise else None,
            'status': analise.status,
            'created_at': analise.created_at.isoformat() if analise.created_at else None,
            'stats': {
                'forcas': forcas,
                'fraquezas': fraquezas,
                'oportunidades': oportunidades,
                'ameacas': ameacas
            }
        })
        
    return jsonify({
        'success': True,
        'data': data
    })

@swot_bp.route('/api/swot/<analise_id>', methods=['GET'])
@login_required
def get_swot(analise_id):
    analise = SwotAnalise.query.get_or_404(analise_id)
    if analise.client.company_id != current_user.company_id:
        abort(403)
        
    # Agrupar itens por quadrante
    forcas = []
    fraquezas = []
    oportunidades = []
    ameacas = []
    
    for item in analise.itens:
        item_data = {
            'id': item.id,
            'texto': item.texto,
            'ordem': item.ordem
        }
        if item.quadrante == 'forca':
            forcas.append(item_data)
        elif item.quadrante == 'fraqueza':
            fraquezas.append(item_data)
        elif item.quadrante == 'oportunidade':
            oportunidades.append(item_data)
        elif item.quadrante == 'ameaca':
            ameacas.append(item_data)
            
    return jsonify({
        'success': True,
        'data': {
            'id': analise.id,
            'contexto': analise.contexto,
            'data_analise': analise.data_analise.isoformat() if analise.data_analise else None,
            'status': analise.status,
            'client_id': analise.client_id,
            'client_name': analise.client.name,
            'quadrantes': {
                'forcas': forcas,
                'fraquezas': fraquezas,
                'oportunidades': oportunidades,
                'ameacas': ameacas
            }
        }
    })

@swot_bp.route('/api/clients/<int:client_id>/swot', methods=['POST'])
@login_required
def create_swot(client_id):
    client = Client.query.get_or_404(client_id)
    if client.company_id != current_user.company_id:
        abort(403)
        
    data = request.get_json() or {}
    
    new_analise = SwotAnalise(
        client_id=client_id,
        contexto=data.get('contexto', ''),
        data_analise=date.today(),
        status='rascunho'
    )
    
    db.session.add(new_analise)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'id': new_analise.id,
        'message': 'Análise SWOT iniciada com sucesso'
    }), 201

@swot_bp.route('/api/swot/<analise_id>', methods=['PUT', 'DELETE'])
@login_required
def update_or_delete_swot(analise_id):
    analise = SwotAnalise.query.get_or_404(analise_id)
    if analise.client.company_id != current_user.company_id:
        abort(403)
        
    if request.method == 'DELETE':
        db.session.delete(analise)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Análise SWOT excluída'})
        
    # PUT
    data = request.get_json() or {}
    
    if 'contexto' in data:
        analise.contexto = data['contexto']
    if 'status' in data:
        analise.status = data['status']
        
    analise.updated_at = get_now_br()
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'Análise SWOT atualizada'})

@swot_bp.route('/api/swot/<analise_id>/items', methods=['POST'])
@login_required
def add_swot_item(analise_id):
    analise = SwotAnalise.query.get_or_404(analise_id)
    if analise.client.company_id != current_user.company_id:
        abort(403)
        
    data = request.get_json() or {}
    quadrante = data.get('quadrante')
    texto = data.get('texto')
    ordem = data.get('ordem', 0)
    
    if not quadrante or not texto:
        return jsonify({'success': False, 'message': 'Dados incompletos'}), 400
        
    new_item = SwotItem(
        swot_analise_id=analise.id,
        quadrante=quadrante,
        texto=texto,
        ordem=ordem
    )
    
    db.session.add(new_item)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'id': new_item.id,
        'item': {
            'id': new_item.id,
            'texto': new_item.texto,
            'ordem': new_item.ordem,
            'quadrante': new_item.quadrante
        }
    }), 201

@swot_bp.route('/api/swot/items/<item_id>', methods=['PUT', 'DELETE'])
@login_required
def update_or_delete_swot_item(item_id):
    item = SwotItem.query.get_or_404(item_id)
    if item.analise.client.company_id != current_user.company_id:
        abort(403)
        
    if request.method == 'DELETE':
        db.session.delete(item)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Item excluído'})
        
    # PUT
    data = request.get_json() or {}
    if 'texto' in data:
        item.texto = data['texto']
    if 'ordem' in data:
        item.ordem = data['ordem']
        
    item.updated_at = get_now_br()
    item.analise.updated_at = get_now_br() # update parent
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'Item atualizado'})
