
from flask import Blueprint, render_template, request, jsonify, make_response
from flask_login import login_required, current_user
from models import db, User, Contract, CommissionSnapshot, AccountsPayable
from datetime import datetime
from sqlalchemy import func, extract
from decimal import Decimal

commercial_bp = Blueprint('commercial', __name__)

def clean_pdf_text(s):
    if not s:
        return ''
    return str(s).replace('—', '-').replace('–', '-').replace('·', '-').replace('"', '"').replace("'", "'").encode('latin-1', 'replace').decode('latin-1')

def ensure_budget_data(budget):
    if not budget.data:
        is_assoc = 'Associação' in (budget.client_name or '') or 'Wenceslau' in (budget.client_name or '')
        budget.data = {
            'quoteNum': budget.quote_num or '001/2026',
            'quoteDate': budget.created_at.strftime('%Y-%m-%d') if budget.created_at else datetime.now().strftime('%Y-%m-%d'),
            'cliName': budget.client_name or ('Associação Comercial e Empresarial de Wenceslau Braz' if is_assoc else 'Cliente'),
            'cliDoc': '78590304000143' if is_assoc else '',
            'cliContact': 'Adriana' if is_assoc else '',
            'cliPhone': '+55 43 99846-4728' if is_assoc else '',
            'cliAddr': 'R. Barão do Rio Branco, 461 - fundos - Centro, Wenceslau Braz - PR, 84950-000' if is_assoc else '',
            'billingCycle': 'unico',
            'discountPct': '10',
            'discountVal': str(round((budget.total_value or 3000) * 0.1, 2)).replace('.', ','),
            'installments': '0',
            'obsText': 'Obs: desconto de 10% mediante pagamento a vista. Parcelamos em ate 3X no boleto Em até 12X no cartão + taxa',
            'validity': '15 dias',
            'items': [
                {
                    'desc': 'Assessoria de marketing para a campanha',
                    'qty': '1',
                    'price': '{:,.2f}'.format(budget.total_value or 3000).replace(',', 'X').replace('.', ',').replace('X', '.'),
                    'sub': 'R$ {:,.2f}'.format(budget.total_value or 3000).replace(',', 'X').replace('.', ',').replace('X', '.')
                }
            ],
            'totalValue': budget.total_value or 3000
        }

def generate_budget_pdf_bytes(budget, company, user):
    from fpdf import FPDF
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    W = 210
    ML = 20
    MR = 20
    cw = W - ML - MR
    y = 16
    
    # 1. Cabeçalho da Empresa
    pdf.set_font('helvetica', 'B', 12)
    pdf.set_text_color(20, 20, 20)
    pdf.set_xy(ML, y)
    comp_name = clean_pdf_text(getattr(company, 'name', 'NorthWay Company') or 'NorthWay Company')
    pdf.cell(100, 5, comp_name, ln=True)
    
    pdf.set_font('helvetica', '', 8.5)
    pdf.set_text_color(80, 80, 80)
    
    doc = clean_pdf_text(getattr(company, 'cpf_cnpj', '') or getattr(company, 'document', '') or '56.106.629/0001-75')
    pdf.set_x(ML)
    pdf.cell(100, 4.5, f'CNPJ/CPF: {doc}', ln=True)
    
    pdf.set_x(ML)
    pdf.cell(100, 4.5, 'Licínio Roberto Araujo, 03 - Jardim Ceres', ln=True)
    
    pdf.set_x(ML)
    pdf.cell(100, 4.5, 'Arapoti/PR - CEP 84990000', ln=True)
    
    pdf.set_x(ML)
    pdf.cell(100, 4.5, '(42) 99989-6358 - marciogholmm@gmail.com', ln=True)
    
    y = pdf.get_y() + 4
    pdf.set_draw_color(227, 30, 36)
    pdf.set_line_width(0.7)
    pdf.line(ML, y, W - MR, y)
    
    # 2. ORÇAMENTO
    y += 5
    pdf.set_xy(ML, y)
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(90, 7, 'ORÇAMENTO', ln=False)
    
    quote_num = clean_pdf_text(getattr(budget, 'quote_num', '001/2026') or '001/2026')
    created_str = budget.created_at.strftime('%d/%m/%Y') if getattr(budget, 'created_at', None) else datetime.now().strftime('%d/%m/%Y')
    pdf.set_font('helvetica', '', 9.5)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(cw - 90, 7, f'Nº {quote_num} · {created_str}', align='R', ln=True)
    
    # 3. Dados do Cliente
    y = pdf.get_y() + 3
    pdf.set_xy(ML, y)
    pdf.set_font('helvetica', 'B', 9.5)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(cw, 5.5, 'Dados do Cliente', ln=True)
    
    b_data = getattr(budget, 'data', {}) or {}
    cli_name = clean_pdf_text(b_data.get('cliName') or getattr(budget, 'client_name', 'Associação Comercial e Empresarial de Wenceslau Braz'))
    cli_doc = clean_pdf_text(b_data.get('cliDoc') or '78590304000143')
    cli_contact = clean_pdf_text(b_data.get('cliContact') or 'Adriana')
    cli_phone = clean_pdf_text(b_data.get('cliPhone') or '+55 43 99846-4728')
    cli_addr = clean_pdf_text(b_data.get('cliAddr') or 'R. Barão do Rio Branco, 461 - fundos - Centro, Wenceslau Braz - PR, 84950-000')
    
    pdf.set_font('helvetica', '', 8.5)
    pdf.set_text_color(40, 40, 40)
    
    pdf.set_x(ML)
    pdf.cell(cw, 4.5, f'Empresa: {cli_name}', ln=True)
    pdf.set_x(ML)
    pdf.cell(cw, 4.5, f'CNPJ/CPF: {cli_doc}', ln=True)
    pdf.set_x(ML)
    pdf.cell(cw, 4.5, f'Contato: {cli_contact}', ln=True)
    pdf.set_x(ML)
    pdf.cell(cw, 4.5, f'Telefone: {cli_phone}', ln=True)
    pdf.set_x(ML)
    pdf.cell(cw, 4.5, f'Endereço: {cli_addr}', ln=True)
    
    # 4. Itens do Orçamento
    y = pdf.get_y() + 4
    pdf.set_xy(ML, y)
    pdf.set_font('helvetica', 'B', 9.5)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(cw, 5.5, 'Itens do Orçamento', ln=True)
    
    # Header tabela
    pdf.set_font('helvetica', 'B', 8.5)
    pdf.set_text_color(80, 80, 80)
    col_desc_w = cw * 0.52
    col_qty_w = cw * 0.12
    col_val_w = cw * 0.18
    col_sub_w = cw * 0.18
    
    pdf.set_x(ML)
    pdf.cell(col_desc_w, 5, 'Descrição', ln=False)
    pdf.cell(col_qty_w, 5, 'Qtd', align='C', ln=False)
    pdf.cell(col_val_w, 5, 'Valor Unit.', align='R', ln=False)
    pdf.cell(col_sub_w, 5, 'Subtotal', align='R', ln=True)
    
    pdf.set_draw_color(220, 220, 220)
    pdf.set_line_width(0.3)
    pdf.line(ML, pdf.get_y(), W - MR, pdf.get_y())
    
    items = b_data.get('items') or [{'desc': 'Assessoria de marketing para a campanha', 'qty': '1', 'price': '3.000,00', 'sub': 'R$ 3.000,00'}]
    pdf.set_font('helvetica', '', 8.5)
    pdf.set_text_color(30, 30, 30)
    
    for it in items:
        desc = clean_pdf_text(it.get('desc', ''))
        qty = clean_pdf_text(str(it.get('qty', '1')))
        price = clean_pdf_text(str(it.get('price', '')))
        sub = clean_pdf_text(str(it.get('sub', price)))
        if not sub.startswith('R$') and sub: sub = f'R$ {sub}'
        
        pdf.set_x(ML)
        pdf.cell(col_desc_w, 6, desc, ln=False)
        pdf.cell(col_qty_w, 6, qty, align='C', ln=False)
        pdf.cell(col_val_w, 6, price, align='R', ln=False)
        pdf.cell(col_sub_w, 6, sub, align='R', ln=True)
        pdf.line(ML, pdf.get_y(), W - MR, pdf.get_y())
    
    # TOTAL
    tot_val = getattr(budget, 'total_value', 3000.0) or 3000.0
    tot_str = f'R$ {tot_val:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    pdf.set_font('helvetica', 'B', 9)
    pdf.set_text_color(20, 20, 20)
    pdf.set_x(ML)
    pdf.cell(col_desc_w + col_qty_w, 7, '', ln=False)
    pdf.cell(col_val_w, 7, 'TOTAL', align='R', ln=False)
    pdf.cell(col_sub_w, 7, tot_str, align='R', ln=True)
    
    # 5. Condições de Pagamento (Box Rosa)
    y = pdf.get_y() + 4
    pdf.set_fill_color(255, 240, 240)
    pdf.rect(ML, y, cw, 18, 'F')
    
    pdf.set_xy(ML + 4, y + 2.5)
    pdf.set_font('helvetica', 'B', 8)
    pdf.set_text_color(227, 30, 36)
    pdf.cell(cw - 8, 4, 'CONDIÇÕES DE PAGAMENTO - PAGAMENTO ÚNICO', ln=True)
    
    pdf.set_x(ML + 4)
    pdf.set_font('helvetica', '', 8)
    pdf.set_text_color(227, 30, 36)
    pdf.cell(24, 4, f'De {tot_str}', ln=False)
    # Strikethrough
    pdf.set_draw_color(227, 30, 36)
    pdf.line(ML + 4, y + 8.5, ML + 26, y + 8.5)
    
    disc_val = tot_val * 0.9
    disc_str = f'R$ {disc_val:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    pdf.set_xy(ML + 4, y + 10.5)
    pdf.set_font('helvetica', 'B', 8.5)
    pdf.set_text_color(26, 135, 84)
    pdf.cell(cw - 8, 4, f'Por {disc_str} (10% de desconto)', ln=True)
    
    # 6. Observações
    y = y + 22
    pdf.set_xy(ML, y)
    pdf.set_font('helvetica', 'B', 9)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(cw, 5, 'Observações', ln=True)
    
    obs_text = clean_pdf_text(b_data.get('obsText') or 'Obs: desconto de 10% mediante pagamento a vista. Parcelamos em ate 3X no boleto Em até 12X no cartão + taxa')
    pdf.set_font('helvetica', '', 8)
    pdf.set_text_color(60, 60, 60)
    pdf.set_x(ML)
    pdf.multi_cell(cw, 4, obs_text)
    
    pdf.set_font('helvetica', '', 7.5)
    pdf.set_text_color(100, 100, 100)
    pdf.set_x(ML)
    pdf.cell(cw, 5, 'Validade: 15 dias a partir da data de emissão.', ln=True)
    
    pdf.set_font('helvetica', 'B', 8)
    pdf.set_text_color(20, 20, 20)
    pdf.set_x(ML)
    user_name = clean_pdf_text(getattr(user, 'name', 'Marcio Holm') or 'Marcio Holm')
    pdf.cell(cw, 4, user_name, ln=True)
    
    pdf.set_font('helvetica', '', 7.5)
    pdf.set_text_color(100, 100, 100)
    pdf.set_x(ML)
    pdf.cell(cw, 4, comp_name, ln=True)
    
    return bytes(pdf.output())

@commercial_bp.route('/commercial/budget_generator')
@login_required
def budget_generator():
    if not current_user.company_id:
        return "Unauthorized", 403
    budget_id = request.args.get('id', type=int)
    budget = None
    if budget_id:
        from models import Budget
        budget = Budget.query.filter_by(id=budget_id, company_id=current_user.company_id).first()
        if budget:
            ensure_budget_data(budget)
    return render_template('commercial/budget_generator.html', budget=budget, budget_id=budget_id)

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

@commercial_bp.route('/commercial/budgets')
@login_required
def budget_history():
    if not current_user.company_id:
        return "Unauthorized", 403
    from models import Budget, db
    # Ensure the table exists on production (workaround for broken migrations)
    try:
        Budget.__table__.create(db.engine, checkfirst=True)
    except Exception:
        pass

    budgets = Budget.query.filter_by(company_id=current_user.company_id).order_by(Budget.created_at.desc()).all()
    return render_template('commercial/budget_history.html', budgets=budgets)

@commercial_bp.route('/commercial/budgets/<int:budget_id>/view')
@commercial_bp.route('/commercial/budgets/<int:budget_id>/print')
@login_required
def view_budget(budget_id):
    if not current_user.company_id:
        return "Unauthorized", 403
    from models import Budget
    budget = Budget.query.filter_by(id=budget_id, company_id=current_user.company_id).first_or_404()
    ensure_budget_data(budget)
    return render_template('commercial/budget_view.html', budget=budget)

@commercial_bp.route('/commercial/budgets/<int:budget_id>/pdf')
@login_required
def download_budget_pdf(budget_id):
    if not current_user.company_id:
        return "Unauthorized", 403
    if request.args.get('raw') != '1':
        from flask import redirect, url_for
        return redirect(url_for('commercial.view_budget', budget_id=budget_id, print='true'))
    from models import Budget
    budget = Budget.query.filter_by(id=budget_id, company_id=current_user.company_id).first_or_404()
    ensure_budget_data(budget)
    
    pdf_bytes = generate_budget_pdf_bytes(budget, current_user.company, current_user)
    num_clean = (budget.quote_num or '001-2026').replace('/', '-')
    cli_clean = (budget.client_name or 'cliente').replace(' ', '_').replace('/', '_')
    filename = f"orcamento-{num_clean}-{cli_clean}.pdf"
    
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@commercial_bp.route('/commercial/api/budgets', methods=['POST'])
@login_required
def save_budget():
    if not current_user.company_id:
        return jsonify({'error': 'Unauthorized'}), 403
    try:
        from models import Budget, db
        # Ensure the table exists on production
        try:
            Budget.__table__.create(db.engine, checkfirst=True)
        except Exception:
            pass

        data = request.json
        budget_id = data.get('budget_id') or data.get('id')
        if budget_id:
            budget = Budget.query.filter_by(id=budget_id, company_id=current_user.company_id).first()
            if budget:
                budget.quote_num = data.get('quoteNum')
                budget.client_name = data.get('cliName')
                budget.total_value = data.get('totalValue', 0.0)
                budget.data = data
                db.session.commit()
                return jsonify({'success': True, 'budget_id': budget.id, 'updated': True})

        budget = Budget(
            company_id=current_user.company_id,
            user_id=current_user.id,
            quote_num=data.get('quoteNum'),
            client_name=data.get('cliName'),
            total_value=data.get('totalValue', 0.0),
            data=data
        )
        db.session.add(budget)
        db.session.commit()
        return jsonify({'success': True, 'budget_id': budget.id})
    except Exception as e:
        db.session.rollback()
        print(f"Error saving budget: {e}")
        return jsonify({'error': str(e)}), 500

@commercial_bp.route('/commercial/api/budgets/<int:budget_id>', methods=['GET'])
@login_required
def get_budget(budget_id):
    if not current_user.company_id:
        return jsonify({'error': 'Unauthorized'}), 403
    from models import Budget
    budget = Budget.query.filter_by(id=budget_id, company_id=current_user.company_id).first()
    if not budget:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({
        'id': budget.id,
        'quote_num': budget.quote_num,
        'client_name': budget.client_name,
        'total_value': budget.total_value,
        'status': budget.status,
        'data': budget.data,
        'created_at': budget.created_at.isoformat() if budget.created_at else None
    })

@commercial_bp.route('/commercial/api/budgets/<int:budget_id>', methods=['DELETE'])
@login_required
def delete_budget(budget_id):
    if not current_user.company_id:
        return jsonify({'error': 'Unauthorized'}), 403
    try:
        from models import Budget
        budget = Budget.query.filter_by(id=budget_id, company_id=current_user.company_id).first()
        if not budget:
            return jsonify({'error': 'Not found'}), 404
        db.session.delete(budget)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
