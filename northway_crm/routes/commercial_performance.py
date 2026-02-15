
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import db, User, Contract, CommissionSnapshot, AccountsPayable
from datetime import datetime
from sqlalchemy import func, extract
from decimal import Decimal

commercial_bp = Blueprint('commercial', __name__)

@commercial_bp.route('/commercial/performance')
@login_required
def performance():
    if not current_user.company_id:
        return "Unauthorized", 403

    # Filros
    competence = request.args.get('competence', datetime.now().strftime('%Y-%m'))
    collaborator_id = request.args.get('collaborator_id')

    # Base Metrics
    query_base = CommissionSnapshot.query.filter_by(competencia_fechamento=competence)
    if collaborator_id:
        query_base = query_base.filter_by(beneficiario_id=int(collaborator_id))
    else:
        # If no collaborator filtered, we might want to sum for lead/owner or just everyone in company
        # Actually snapshots are for everyone. We should probably filter by company too?
        # Snapshots are linked to contracts which have company_id.
        query_base = query_base.join(Contract).filter(Contract.company_id == current_user.company_id)

    snapshots = query_base.all()
    
    # Financial Stats (from AccountsPayable)
    query_ap = AccountsPayable.query.filter_by(tenant_id=current_user.company_id, competencia=competence)
    if collaborator_id:
        query_ap = query_ap.filter_by(beneficiario_id=int(collaborator_id))
        
    all_payables = query_ap.all()
    
    # Aggregates
    total_contracts = len(snapshots)
    total_revenue_base = sum(p.valor_base_contratual for p in all_payables if not p.eh_ajuste)
    total_comm_provisional = sum(p.valor_comissao_calculado for p in all_payables if not p.eh_ajuste)
    total_adjustments = sum(p.valor_comissao_calculado for p in all_payables if p.eh_ajuste)
    total_comm_final = total_comm_provisional + total_adjustments
    
    paid_comm = sum(p.valor_final_pago_colaborador or 0 for p in all_payables if p.status == 'PAGO')
    pending_comm = sum(p.valor_comissao_calculado for p in all_payables if p.status == 'A_PAGAR')

    # Collaborators for Filter
    collaborators = User.query.filter_by(company_id=current_user.company_id).all()
    
    # Chart Data (Summary by beneficiary if collaborator_id not set)
    chart_data = []
    if not collaborator_id:
        # Group by beneficiary
        beneficiaries_stats = db.session.query(
            User.name,
            func.count(CommissionSnapshot.id).label('qty')
        ).join(CommissionSnapshot, User.id == CommissionSnapshot.beneficiario_id)\
         .join(Contract, CommissionSnapshot.contract_id == Contract.id)\
         .filter(Contract.company_id == current_user.company_id, CommissionSnapshot.competence_fechamento == competence)\
         .group_by(User.id).all()
        
        chart_data = [{'name': b[0], 'qty': b[1]} for b in beneficiaries_stats]

    return render_template('commercial/performance.html',
                           snapshots=snapshots,
                           collaborators=collaborators,
                           competence=competence,
                           stats={
                               'contracts': total_contracts,
                               'revenue': total_revenue_base,
                               'comm_provisional': total_comm_provisional,
                               'adjustments': total_adjustments,
                               'comm_final': total_comm_final,
                               'paid': paid_comm,
                               'pending': pending_comm
                           },
                           chart_data=chart_data)
