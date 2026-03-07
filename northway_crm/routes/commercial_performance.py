
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
    # Snapshots are for everyone. Filter by company.
    # We join with Contract OR ServiceOrder to ensure we only get the company's data.
    from models import ServiceOrder
    query_base = CommissionSnapshot.query.filter(CommissionSnapshot.competencia_fechamento == competence)
    
    # Filter by Company (crucial for multitenancy)
    query_base = query_base.filter(
        db.or_(
            CommissionSnapshot.contract.has(Contract.company_id == current_user.company_id),
            CommissionSnapshot.service_order.has(ServiceOrder.company_id == current_user.company_id)
        )
    )

    if collaborator_id:
        query_base = query_base.filter_by(beneficiario_id=int(collaborator_id))

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
        # Group by beneficiary (summing counts of SOs and Contracts)
        from models import ServiceOrder
        beneficiaries_stats = db.session.query(
            User.name,
            func.count(CommissionSnapshot.id).label('qty')
        ).join(CommissionSnapshot, User.id == CommissionSnapshot.beneficiario_id)\
         .filter(
             CommissionSnapshot.competencia_fechamento == competence,
             db.or_(
                 CommissionSnapshot.contract.has(Contract.company_id == current_user.company_id),
                 CommissionSnapshot.service_order.has(ServiceOrder.company_id == current_user.company_id)
             )
         )\
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
