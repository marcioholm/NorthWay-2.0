
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, AccountsPayable, User, Company, Transaction, Contract, Client
from datetime import datetime, date
from sqlalchemy import desc

payable_bp = Blueprint('payable', __name__)

@payable_bp.route('/financial/payable')
@login_required
def list_payable():
    if not current_user.company_id:
        return "Unauthorized", 403

    # Filros
    status = request.args.get('status')
    competence = request.args.get('competence') # YYYY-MM
    beneficiary_id = request.args.get('beneficiary_id')
    
    query = AccountsPayable.query.filter_by(tenant_id=current_user.company_id)
    
    if status:
        query = query.filter_by(status=status)
    if competence:
        query = query.filter_by(competencia=competence)
    if beneficiary_id:
        query = query.filter_by(beneficiario_id=int(beneficiary_id))
        
    payables = query.order_by(desc(AccountsPayable.created_at)).all()
    
    # For filters
    beneficiaries = User.query.filter_by(company_id=current_user.company_id).all()
    # Unique competences from DB
    competences = db.session.query(AccountsPayable.competencia).filter_by(tenant_id=current_user.company_id).distinct().all()
    competences = [c[0] for c in competences]
    
    return render_template('financial/accounts_payable.html', 
                           payables=payables, 
                           beneficiaries=beneficiaries,
                           competences=competences)

@payable_bp.route('/financial/payable/<string:id>/pay', methods=['POST'])
@login_required
def mark_as_paid(id):
    payable = AccountsPayable.query.filter_by(id=id, tenant_id=current_user.company_id).first_or_404()
    
    final_value = request.form.get('valor_final_pago_colaborador')
    juros_pago = request.form.get('juros_pago_colaborador', '0')
    
    try:
        if final_value:
            payable.valor_final_pago_colaborador = float(final_value.replace('R$', '').replace('.', '').replace(',', '.').strip())
        else:
            payable.valor_final_pago_colaborador = payable.valor_comissao_calculado
            
        payable.juros_pago_colaborador = float(juros_pago.replace('R$', '').replace('.', '').replace(',', '.').strip())
        
        payable.status = 'PAGO'
        payable.data_pagamento = datetime.now()
        db.session.commit()
        flash('Pagamento registrado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao registrar pagamento: {str(e)}', 'error')
        
    return redirect(url_for('payable.list_payable'))

@payable_bp.route('/financial/payable/<string:id>/cancel', methods=['POST'])
@login_required
def cancel_payable(id):
    payable = AccountsPayable.query.filter_by(id=id, tenant_id=current_user.company_id).first_or_404()
    
    if payable.status == 'PAGO':
        flash('Não é possível cancelar um lançamento já pago.', 'error')
        return redirect(url_for('payable.list_payable'))
        
    payable.status = 'ESTORNADO'
    db.session.commit()
    flash('Lançamento estornado.', 'info')
    return redirect(url_for('payable.list_payable'))
