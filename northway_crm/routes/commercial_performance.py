
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

    # Filtros
    competence = request.args.get('competence', datetime.now().strftime('%Y-%m'))
    collaborator_id = request.args.get('collaborator_id')

    # RECONCILIATION: Ensure snapshots exist for already closed deals this month
    try:
        from models import ServiceOrder, Contract, CommissionSnapshot
        from services.commission_service import CommissionService
        from datetime import date, timedelta
        
        y, m = map(int, competence.split('-'))
        m_start = datetime(y, m, 1)
        if m == 12:
            m_end = datetime(y + 1, 1, 1) - timedelta(seconds=1)
        else:
            m_end = datetime(y, m + 1, 1) - timedelta(seconds=1)

        # 1. Reconcile Contracts signed in this month but missing snapshots
        contracts = Contract.query.filter(
            Contract.company_id == current_user.company_id,
            Contract.status.in_(['signed', 'active']),
            Contract.created_at >= m_start,
            Contract.created_at <= m_end
        ).all()
        
        for c in contracts:
            existing = CommissionSnapshot.query.filter_by(contract_id=c.id).first()
            if not existing:
                beneficiary = c.client.account_manager or current_user
                CommissionService.create_snapshot(beneficiary, contract=c)
                
        # 2. Reconcile Service Orders approved in this month but missing snapshots
        sos = ServiceOrder.query.filter(
            ServiceOrder.company_id == current_user.company_id,
            ServiceOrder.status.in_(['EM_EXECUCAO', 'CONCLUIDA', 'AGUARDANDO_PAGAMENTO']),
            ServiceOrder.created_at >= m_start,
            ServiceOrder.created_at <= m_end
        ).all()
        
        for so in sos:
            existing = CommissionSnapshot.query.filter_by(service_order_id=so.id).first()
            if not existing:
                beneficiary = so.client.account_manager or current_user
                CommissionService.create_snapshot(beneficiary, service_order=so)
                
        db.session.commit()
    except Exception as e:
        print(f"⚠️ Reconciliation Error: {e}")
        db.session.rollback()

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

    # GOALS (Metas)
    from models import Goal
    try:
        y, m = map(int, competence.split('-'))
        # If collaborator filtered, find user goal. Otherwise company goal (user_id=None)
        g_query = Goal.query.filter_by(company_id=current_user.company_id, year=y, month=m)
        if collaborator_id:
            g_query = g_query.filter_by(user_id=int(collaborator_id))
        else:
            g_query = g_query.filter_by(user_id=None)
        
        goal_obj = g_query.first()
        target_amount = float(goal_obj.target_amount) if goal_obj else 0.0
    except:
        target_amount = 0.0

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
                               'pending': pending_comm,
                               'goal': target_amount,
                               'percent': (total_revenue_base / target_amount * 100) if target_amount > 0 else 0
                           },
                           chart_data=chart_data)
