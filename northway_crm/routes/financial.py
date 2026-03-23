from flask import Blueprint, render_template, jsonify, abort, request, current_app
from flask_login import login_required, current_user
from models import db, Contract, Transaction, FinancialCategory, Expense, AccountsPayable, ROLE_ADMIN, ROLE_MANAGER

from datetime import date, datetime, timedelta
import json
from sqlalchemy import func, desc, extract, or_

financial_bp = Blueprint('financial', __name__)

def add_months(sourcedate, months):
    """Simple helper to add months."""
    month = sourcedate.month - 1 + months
    year = sourcedate.year + month // 12
    month = month % 12 + 1
    day = min(sourcedate.day, [31,
        29 if year % 4 == 0 and not year % 100 == 0 or year % 400 == 0 else 28,
        31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month-1])
    return date(year, month, day)

@financial_bp.route('/financial')
@login_required
def dashboard():
    if not current_user.company_id:
        abort(403)

    if current_user.role not in [ROLE_ADMIN, ROLE_MANAGER]:
        abort(403)

    return render_template('financial/dashboard.html')

@financial_bp.route('/api/financial/stats')
@login_required
def stats():
    if not current_user.company_id:
        abort(403)

    if current_user.role not in [ROLE_ADMIN, ROLE_MANAGER]:
        abort(403)
    
    company_id = current_user.company_id
    if not company_id:
        return jsonify({'error': 'Empresa não vinculada'}), 400
        
    today = date.today()
    
    # --- PROJECTION & REVENUE ---
    from datetime import timedelta
    
    forecast_30 = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.company_id == company_id,
        Transaction.status == 'pending',
        Transaction.due_date >= today,
        Transaction.due_date <= today + timedelta(days=30)
    ).scalar() or 0.0
    
    forecast_60 = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.company_id == company_id,
        Transaction.status == 'pending',
        Transaction.due_date >= today,
        Transaction.due_date <= today + timedelta(days=60)
    ).scalar() or 0.0
    
    forecast_90 = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.company_id == company_id,
        Transaction.status == 'pending',
        Transaction.due_date >= today,
        Transaction.due_date <= today + timedelta(days=90)
    ).scalar() or 0.0

    forecast_30 = float(forecast_30)
    forecast_60 = float(forecast_60)
    forecast_90 = float(forecast_90)
            
    # Confirmed Revenue (Paid this month)
    first_day_month = today.replace(day=1)
    paid_this_month = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.company_id == company_id,
        Transaction.status == 'paid',
        Transaction.paid_date >= first_day_month
    ).scalar() or 0
    
    # Risk Revenue (Overdue)
    overdue = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.company_id == company_id,
        Transaction.status == 'pending',
        Transaction.due_date < today
    ).scalar() or 0
    
    # --- MRR & TICKET ---
    # Performance: Use Client.monthly_value as the source of truth for MRR
    active_clients = Client.query.filter(
        Client.company_id == company_id,
        Client.status == 'ativo'
    ).all()
    
    mrr = 0
    mrr_at_risk = 0
    delinquent_count = 0
    active_clients_count = 0
    
    print(f"📊 DEBUG FINANCIAL: Found {len(active_clients)} active clients.")
    
    for c in active_clients:
        try:
            val = float(c.monthly_value or 0.0)
            
            if c.payment_status == 'inadimplente':
                mrr_at_risk += val
                delinquent_count += 1
            else:
                mrr += val
                active_clients_count += 1
        except Exception as e:
            pass
    
    avg_ticket = mrr / active_clients_count if active_clients_count > 0 else 0
    
    # Churn Rate: (Cancelled / (Active + Cancelled)) * 100
    cancelled_contracts = Contract.query.filter_by(company_id=company_id, status='cancelled').all()
    cancelled_count = len(cancelled_contracts)
    total_ever_signed = active_clients_count + cancelled_count
    churn_rate = (cancelled_count / total_ever_signed * 100) if total_ever_signed > 0 else 0
    
    # --- CHARTS (12 Months Projection) ---
    end_date = add_months(today, 11)
    if end_date.month == 12:
        max_date = end_date.replace(year=end_date.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        max_date = end_date.replace(month=end_date.month + 1, day=1) - timedelta(days=1)
        
    year_transactions = Transaction.query.filter(
        Transaction.company_id == company_id,
        Transaction.status == 'pending',
        Transaction.due_date >= today.replace(day=1),
        Transaction.due_date <= max_date
    ).all()
    
    results_map = {}
    for tx in year_transactions:
        m_key = tx.due_date.strftime('%Y-%m')
        results_map[m_key] = results_map.get(m_key, 0.0) + float(tx.amount or 0.0)

    chart_labels = []
    chart_values = []
    for i in range(12):
        future_date = add_months(today, i)
        m_key = future_date.strftime('%Y-%m')
        
        month_sum = results_map.get(m_key, 0.0)
        
        if i == 0:
             month_sum += float(paid_this_month)
             
        chart_labels.append(future_date.strftime('%b/%Y'))
        chart_values.append(float(month_sum))

    # --- NICHE STATS ---
    m_curr_start = today.replace(day=1)
    if today.month == 12:
        m_curr_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        m_curr_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

    current_month_txs = Transaction.query.options(db.joinedload(Transaction.client)).filter(
        Transaction.company_id == company_id,
        Transaction.status.in_(['pending', 'paid']),
        Transaction.due_date >= m_curr_start,
        Transaction.due_date <= m_curr_end
    ).all()
    
    niche_buckets = {} 
    niche_counts = {} 
    
    for tx in current_month_txs:
        try:
            val = float(tx.amount)
            niche = "Sem Nicho"
            if tx.client:
                niche = tx.client.niche or "Sem Nicho"
            elif tx.contract and tx.contract.client:
                niche = tx.contract.client.niche or "Sem Nicho"
            niche = niche.strip() or "Sem Nicho"
            if niche not in niche_buckets:
                niche_buckets[niche] = 0
                niche_counts[niche] = 0
            niche_buckets[niche] += val
            niche_counts[niche] += 1
        except: pass
            
    sorted_niches = sorted(niche_buckets.items(), key=lambda x: x[1], reverse=True)
    niche_labels = [item[0] for item in sorted_niches]
    niche_values = [item[1] for item in sorted_niches]
    niche_quantities = [niche_counts[label] for label in niche_labels]

    # --- RECENT TRANSACTIONS ---
    recent_txs = Transaction.query.filter(
        Transaction.company_id == company_id,
        Transaction.status != 'cancelled'
    ).order_by(Transaction.status == 'paid', Transaction.due_date.asc()).limit(50).all()
    
    tx_list = []
    for t in recent_txs:
        client_name = "Cliente"
        if t.contract: client_name = t.contract.client.name
        elif t.client: client_name = t.client.name
        tx_list.append({
            'id': t.id,
            'description': t.description,
            'client_name': client_name,
            'amount': t.amount,
            'due_date': t.due_date.strftime('%d/%m/%Y'),
            'paid_date': t.paid_date.strftime('%d/%m/%Y') if t.paid_date else '-',
            'created_at': t.created_at.strftime('%d/%m/%Y %H:%M') if t.created_at else '',
            'status': t.status
        })

    # --- ALERTS & THRESHOLDS ---
    alerts = []
    
    # 1. Total Revenue for threshold contexts (Competency of current month)
    curr_rev = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.company_id == company_id,
        Transaction.status != 'cancelled',
        extract('year', Transaction.due_date) == today.year,
        extract('month', Transaction.due_date) == today.month
    ).scalar() or 0
    
    # 2. Team Cost Alert
    expenses_today = Expense.query.filter(
        Expense.company_id == company_id,
        extract('year', Expense.due_date) == today.year,
        extract('month', Expense.due_date) == today.month
    ).all()
    
    team_cost = 0
    for e in expenses_today:
        c_name = e.category.name.lower()
        if any(k in c_name for k in ['salário', 'pro-labore', 'pró-labore', 'folha', 'encargo']):
            team_cost += e.amount
            
    if curr_rev > 0:
        tc_pct = (team_cost / curr_rev) * 100
        if tc_pct > 40:
            alerts.append({
                'level': 'red',
                'title': 'Custo de equipe elevado',
                'message': f'Gastos com pessoal representam {tc_pct:.1f}% da receita bruta.'
            })
            
    # 3. Net Margin Alert
    total_exp = sum(e.amount for e in expenses_today)
    comm_appx = db.session.query(func.sum(AccountsPayable.valor_comissao_calculado)).filter(
        AccountsPayable.tenant_id == company_id,
        AccountsPayable.competencia == today.strftime('%Y-%m'),
        AccountsPayable.status != 'CANCELADO'
    ).scalar() or 0
    
    monthly_net = float(curr_rev) - float(total_exp) - float(comm_appx)
    if curr_rev > 0:
        margin_pct = (monthly_net / float(curr_rev)) * 100
        if margin_pct < 20:
             alerts.append({
                'level': 'yellow',
                'title': 'Margem líquida em atenção',
                'message': f'A margem projetada para este mês é de {margin_pct:.1f}% (meta: 20%).'
            })
            
    # 4. MRR Delta
    lm_date = today.replace(day=1) - timedelta(days=1)
    mrr_last_month = 0
    for c in active_clients:
        if c.created_at.date() <= lm_date.replace(day=1):
            try:
                v = float(c.monthly_value or 0.0)
                mrr_last_month += v
            except: pass
            
    if mrr_last_month > 0:
        mrr_delta = ((mrr - mrr_last_month) / mrr_last_month) * 100
        if mrr_delta < -10:
             alerts.append({
                'level': 'red',
                'title': 'Queda acentuada de MRR',
                'message': f'Houve uma redução de {abs(mrr_delta):.1f}% na base recorrente vs mês anterior.'
            })

    return jsonify({
        'kpis': {
            'forecast_30': forecast_30,
            'forecast_60': forecast_60,
            'forecast_90': forecast_90,
            'confirmed': paid_this_month,
            'risk': overdue,
            'mrr': mrr,
            'mrr_at_risk': mrr_at_risk,
            'delinquent_count': delinquent_count,
            'avg_ticket': avg_ticket,
            'active_clients': active_clients_count,
            'churn_rate': round(churn_rate, 2)
        },
        'charts': {
            'forecast': {'labels': chart_labels, 'data': chart_values},
            'niches': {'labels': niche_labels, 'data': niche_values, 'counts': niche_quantities}
        },
        'alerts': alerts,
        'transactions': tx_list
    })

@financial_bp.route('/api/transactions/<int:id>/pay', methods=['POST'])
@login_required
def pay_transaction(id):
    if current_user.role not in [ROLE_ADMIN, ROLE_MANAGER]:
        return jsonify({'success': False, 'error': 'Acesso negado. Apenas Admin/Gerente podem baixar pagamentos.'}), 403
    
    tx = Transaction.query.filter_by(id=id, company_id=current_user.company_id).first()
    if not tx:
        return jsonify({'success': False, 'error': 'Transação não encontrada.'}), 404
        
    try:
        tx.status = 'paid'
        tx.paid_date = date.today()
        
        # Update client summary status
        if tx.client_id:
            from utils import update_client_payment_status
            update_client_payment_status(tx.client_id)
            
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

@financial_bp.route('/financial/dre')
@login_required
def dre_page():
    if not current_user.company_id:
        abort(403)

    if current_user.role not in [ROLE_ADMIN, ROLE_MANAGER]:
        abort(403)
    return render_template('financial/dre.html', now=datetime.now()) # Pass now for date filters

@financial_bp.route('/api/financial/dre')
@login_required
def get_dre_data():
    if not current_user.company_id:
        abort(403)

    if current_user.role not in [ROLE_ADMIN, ROLE_MANAGER]:
        abort(403)
        
    company_id = current_user.company_id
    
    # Get filters
    year = request.args.get('year', type=int, default=date.today().year)
    month = request.args.get('month', type=int, default=date.today().month)
    regime = request.args.get('regime', 'competencia') # 'caixa' or 'competencia'
    
    # --- 1. RECEITA BRUTA ---
    if regime == 'caixa':
        revenue_txs = Transaction.query.filter(
            Transaction.company_id == company_id,
            Transaction.status == 'paid',
            extract('year', Transaction.paid_date) == year,
            extract('month', Transaction.paid_date) == month
        ).all()
    else:
        revenue_txs = Transaction.query.filter(
            Transaction.company_id == company_id,
            Transaction.status != 'cancelled',
            extract('year', Transaction.due_date) == year,
            extract('month', Transaction.due_date) == month
        ).all()
    
    gross_revenue = sum(t.amount for t in revenue_txs)
    revenue_by_type = {
        'recorrente': 0,
        'pontual': 0,
        'setup_onboarding': 0,
        'outros': 0
    }
    for t in revenue_txs:
        rtype = t.revenue_type or 'recorrente'
        if rtype not in revenue_by_type: rtype = 'outros'
        revenue_by_type[rtype] += t.amount
    
    # --- 2. EXPENSES & DEDUCTIONS --- 
    if regime == 'caixa':
        period_expenses = Expense.query.filter(
            Expense.company_id == company_id,
            Expense.status == 'paid',
            extract('year', Expense.paid_date) == year,
            extract('month', Expense.paid_date) == month
        ).all()
    else:
        period_expenses = Expense.query.filter(
            Expense.company_id == company_id,
            extract('year', Expense.due_date) == year,
            extract('month', Expense.due_date) == month
        ).all()
    
    # 3. Categorize
    taxes = 0 # Conceptually: Deductions
    variable_costs = 0
    fixed_expenses = 0
    breakdown = {}
    
    for exp in period_expenses:
        cat = exp.category
        val = exp.amount
        
        if cat.name not in breakdown: breakdown[cat.name] = 0
        breakdown[cat.name] += val
        
        if cat.is_deduction:
            taxes += val
        elif cat.type == 'cost':
            variable_costs += val
        else:
            fixed_expenses += val

    # --- 4. COMMISSIONS (VARIABLE COSTS) ---
    comp_str = f"{year}-{month:02d}"
    
    if regime == 'caixa':
        period_commissions = AccountsPayable.query.filter_by(
            tenant_id=company_id,
            competencia=comp_str,
            status='PAGO'
        ).all()
    else:
        period_commissions = AccountsPayable.query.filter(
            AccountsPayable.tenant_id == company_id,
            AccountsPayable.competencia == comp_str,
            AccountsPayable.status != 'CANCELADO'
        ).all()
    
    comm_total = sum(float(c.valor_comissao_calculado or 0) for c in period_commissions)
    variable_costs += comm_total
    
    if comm_total > 0:
        breakdown['Comissões Comerciais'] = comm_total

    # --- CALCULATION ---
    net_revenue = gross_revenue - taxes
    gross_profit = net_revenue - variable_costs # Margem de Contribuição
    ebitda = gross_profit - fixed_expenses
    net_result = ebitda 
    
    return jsonify({
        'gross_revenue': gross_revenue,
        'revenue_by_type': revenue_by_type,
        'taxes': taxes, # Impostos e Deduções
        'net_revenue': net_revenue,
        'variable_costs': variable_costs,
        'gross_profit': gross_profit, # Margem Contribuição
        'fixed_expenses': fixed_expenses,
        'ebitda': ebitda,
        'net_result': net_result,
        'breakdown': breakdown
    })

@financial_bp.route('/api/expenses', methods=['GET', 'POST'])
@login_required
def expenses_api():
    if not current_user.company_id:
        abort(403)

    company_id = current_user.company_id
    if current_user.role not in [ROLE_ADMIN, ROLE_MANAGER]:
        abort(403)
        
    if request.method == 'POST':
        data = request.json
        
        try:
            amount = float(str(data['amount']).replace('R$', '').replace('.', '').replace(',', '.'))
        except:
            return jsonify({'error': 'Valor inválido'}), 400
            
        new_exp = Expense(
            description=data['description'],
            amount=amount,
            due_date=datetime.strptime(data['due_date'], '%Y-%m-%d').date(),
            paid_date=datetime.strptime(data['paid_date'], '%Y-%m-%d').date() if data.get('paid_date') else None,
            status=data.get('status', 'paid'),
            category_id=int(data['category_id']),
            company_id=company_id,
            user_id=current_user.id
        )
        db.session.add(new_exp)
        db.session.commit()
        return jsonify({'success': True})
        
    # GET - List recent or filtered
    # For simplicity, returning categories for the modal first
    return jsonify({'error': 'Use specific endpoints'})

@financial_bp.route('/api/financial/revenue', methods=['POST'])
@login_required
def create_revenue():
    if not current_user.company_id:
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.json
    company_id = current_user.company_id
    
    # Validation
    if not data.get('amount') or not data.get('due_date'):
        return jsonify({'error': 'Valor e Data de Vencimento são obrigatórios.'}), 400

    try:
        from models import Client, Transaction
        from datetime import datetime
        
        # 1. Handle Client (Existing or New)
        client_id = data.get('client_id')
        new_client_name = data.get('new_client_name')
        
        if not client_id and new_client_name:
            # Create NEW Client on the fly
            # Check dupes first?
            existing = Client.query.filter_by(company_id=company_id, name=new_client_name).first()
            if existing:
                client_id = existing.id
            else:
                new_client = Client(
                    name=new_client_name,
                    company_id=company_id,
                    status='ativo', # Active by default
                    created_at=datetime.utcnow(),
                    account_manager_id=current_user.id # Assigned to creator
                )
                db.session.add(new_client)
                db.session.flush() # Get ID
                client_id = new_client.id
        elif not client_id and not new_client_name:
             return jsonify({'error': 'Selecione um cliente ou informe um nome para o novo.'}), 400

        # 2. Parse Data
        try:
             amount = float(str(data['amount']).replace('R$', '').replace('.', '').replace(',', '.'))
        except:
             return jsonify({'error': 'Formato de valor inválido.'}), 400
             
        due_date = datetime.strptime(data['due_date'], '%Y-%m-%d').date()
        paid_date = None
        if data.get('paid_date'):
             paid_date = datetime.strptime(data['paid_date'], '%Y-%m-%d').date()
        
        # 3. Create Transaction
        new_tx = Transaction(
            company_id=company_id,
            client_id=client_id,
            description=data.get('description') or 'Receita Manual',
            amount=amount,
            due_date=due_date,
            paid_date=paid_date,
            status=data.get('status', 'pending'), # pending or paid
            created_at=datetime.utcnow()
        )
        
        db.session.add(new_tx)
        
        # 4. Update Client MRR if requested? (Optional, user might just want one-off)
        # For now, just transaction.
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Receita lançada com sucesso!'})

    except Exception as e:
        db.session.rollback()
        print(f"Error adding revenue: {e}")
        return jsonify({'error': str(e)}), 500

@financial_bp.route('/api/financial/categories')
@login_required
def get_categories():
    if not current_user.company_id:
        abort(403)
        
    cats = FinancialCategory.query.filter(FinancialCategory.company_id == current_user.company_id).all()
    return jsonify([{ 'id': c.id, 'name': c.name, 'type': c.type } for c in cats])

@financial_bp.route('/clients/<int:id>/charges/new', methods=['POST'])
@login_required
def create_manual_charge(id):
    if not current_user.company_id:
        abort(403)

    from models import Client
    from services.asaas_service import AsaasService
    
    # Check Client
    client = Client.query.get_or_404(id)
    if client.company_id != current_user.company_id:
        abort(403)
        
    # Get Data
    description = request.form.get('description')
    amount_str = request.form.get('amount')
    due_date_str = request.form.get('due_date')
    
    if not description or not amount_str or not due_date_str:
        return jsonify({'error': 'Todos os campos são obrigatórios'}), 400
        
    # try:
    #     amount = float(amount_str.replace('R$', '').replace('.', '').replace(',', '.').strip())
    #     due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        
    #     # Create Transaction (Local)
    #     tx = Transaction(
    #         contract_id=None, # Manual Charge
    #         client_id=client.id,
    #         company_id=client.company_id,
    #         description=description,
    #         amount=amount,
    #         due_date=due_date,
    #         status='pending'
    #     )
    #     db.session.add(tx)
    #     db.session.flush()
        
    #     # Create in Asaas
    #     # Ensure customer exists
    #     # customer_id = AsaasService.create_customer(client.company_id, client)
    #     # payment_data = AsaasService.create_payment(client.company_id, customer_id, tx)
        
    #     # tx.asaas_id = payment_data.get('id')
    #     # tx.asaas_invoice_url = payment_data.get('invoiceUrl')
        
    #     db.session.commit()
         
    #     return jsonify({'success': True, 'message': 'Cobrança gerada com sucesso!'})
        
    # except Exception as e:
    #     db.session.rollback()
    #     import traceback
    #     traceback.print_exc()
    #     return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'Funcionalidade em manutenção (Migração Asaas v2)'}), 503

@financial_bp.route('/api/transactions/<int:id>/cancel', methods=['POST'])
@login_required
def cancel_transaction_route(id):
    if current_user.role not in [ROLE_ADMIN, ROLE_MANAGER]:
        return jsonify({'success': False, 'error': 'Acesso negado. Apenas Admin/Gerente podem cancelar.'}), 403
    
    # Get Transaction safely (scoped to company)
    tx = Transaction.query.filter_by(id=id, company_id=current_user.company_id).first()
    if not tx:
        return jsonify({'success': False, 'error': 'Transação não encontrada ou acesso negado.'}), 404
        
    try:
        # Cancel in Asaas if linked
        if tx.asaas_id:
            return jsonify({'success': False, 'error': 'Cancelamento Asaas em manutenção. Cancele direto no painel.'}), 400
            # try:
            #     success = AsaasService.cancel_payment(current_user.company_id, tx.asaas_id)
            #     if not success:
            #         # In some cases, we might want to allow local cancellation even if Asaas fails?
            #         # For now, we enforce sync.
            #         return jsonify({'success': False, 'error': 'Falha ao cancelar no Asaas. Verifique se a cobrança já foi paga ou removida.'}), 400
            # except Exception as asaas_error:
            #      return jsonify({'success': False, 'error': f'Erro de comunicação com Asaas: {str(asaas_error)}'}), 500

        # Update Local Status
        tx.status = 'cancelled'
        
        # Save Reason
        if request.is_json:
            reason = request.json.get('reason')
            if reason:
                tx.cancellation_reason = reason
        
        # Update client status
        if tx.client_id:
            from utils import update_client_payment_status
            update_client_payment_status(tx.client_id)
                
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500

