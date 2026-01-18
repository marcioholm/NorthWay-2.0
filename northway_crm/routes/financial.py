from flask import Blueprint, render_template, jsonify, abort, request
from flask_login import login_required, current_user
from models import db, Contract, Transaction, FinancialCategory, Expense, ROLE_ADMIN, ROLE_MANAGER
from datetime import date, datetime
import json
from sqlalchemy import func, desc, extract

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
    if current_user.role not in [ROLE_ADMIN, ROLE_MANAGER]:
        abort(403)
    return render_template('financial/dashboard.html')

@financial_bp.route('/api/financial/stats')
@login_required
def stats():
    if current_user.role not in [ROLE_ADMIN, ROLE_MANAGER]:
        abort(403)
    
    company_id = current_user.company_id
    today = date.today()
    
    # --- PROJECTION & REVENUE ---
    # Optimized: Single aggregate query for future revenue buckets could be faster,
    # but Python loop is acceptable for <10k transactions.
    
    forecast_30 = 0
    forecast_60 = 0
    forecast_90 = 0
    
    # Fetch all pending future transactions
    # Performance Note: Index on (company_id, status, due_date) would be ideal.
    upcoming_transactions = Transaction.query.join(Contract).filter(
        Contract.company_id == company_id,
        Transaction.status == 'pending',
        Transaction.due_date >= today
    ).all()
    
    for t in upcoming_transactions:
        days_diff = (t.due_date - today).days
        if days_diff <= 30:
            forecast_30 += t.amount
        if days_diff <= 60:
            forecast_60 += t.amount
        if days_diff <= 90:
            forecast_90 += t.amount
            
    # Confirmed Revenue (Paid this month)
    first_day_month = today.replace(day=1)
    paid_this_month = db.session.query(func.sum(Transaction.amount)).join(Contract).filter(
        Contract.company_id == company_id,
        Transaction.status == 'paid',
        Transaction.paid_date >= first_day_month
    ).scalar() or 0
    
    # Risk Revenue (Overdue)
    overdue = db.session.query(func.sum(Transaction.amount)).join(Contract).filter(
        Contract.company_id == company_id,
        Transaction.status == 'pending',
        Transaction.due_date < today
    ).scalar() or 0
    
    # --- MRR & TICKET ---
    # Performance: Avoid parsing JSON for every request if possible.
    # For now, we iterate active contracts.
    active_contracts = Contract.query.filter_by(company_id=company_id, status='signed').all()
    cancelled_contracts = Contract.query.filter_by(company_id=company_id, status='cancelled').all() # Assuming 'cancelled' status exists/used
    
    mrr = 0
    active_clients_count = len(active_contracts)
    cancelled_count = len(cancelled_contracts)
    
    for c in active_contracts:
        try:
            data = json.loads(c.form_data)
            val_str = data.get('valor_parcela', '0')
            val = float(val_str.replace('.', '').replace(',', '.'))
            mrr += val
        except:
            pass

    avg_ticket = mrr / active_clients_count if active_clients_count > 0 else 0
    
    # Churn Rate: (Cancelled / (Active + Cancelled)) * 100
    total_ever_signed = active_clients_count + cancelled_count
    churn_rate = (cancelled_count / total_ever_signed * 100) if total_ever_signed > 0 else 0

    # --- CHARTS (12 Months Projection) ---
    chart_labels = []
    chart_values = []
    for i in range(12):
        future_date = add_months(today, i)
        # Sum transactions due in that month/year
        month_sum = db.session.query(func.sum(Transaction.amount)).join(Contract).filter(
            Contract.company_id == company_id,
            Transaction.status == 'pending',
            extract('month', Transaction.due_date) == future_date.month,
            extract('year', Transaction.due_date) == future_date.year
        ).scalar() or 0
        
        if i == 0:
             month_sum += paid_this_month
             
        chart_labels.append(future_date.strftime('%b/%Y'))
        chart_values.append(month_sum)

    # --- NICHE STATS (New) ---
    # Aggregate MRR by Client Niche
    # We iterate active contracts and group by their client's niche
    niche_buckets = {} # For MRR
    niche_counts = {} # For Client Count
    
    for c in active_contracts:
        try:
            # Extract value from contract JSON
            data = json.loads(c.form_data)
            val_str = data.get('valor_parcela', '0')
            val = float(val_str.replace('.', '').replace(',', '.'))
            
            # Get Niche
            niche = c.client.niche or "Sem Nicho"
            niche = niche.strip()
            if not niche: niche = "Sem Nicho"
            
            if niche not in niche_buckets:
                niche_buckets[niche] = 0
                niche_counts[niche] = 0
            niche_buckets[niche] += val
            niche_counts[niche] += 1
        except:
            pass
            
    # Sort Niches by MRR (desc)
    sorted_niches = sorted(niche_buckets.items(), key=lambda x: x[1], reverse=True)
    niche_labels = [item[0] for item in sorted_niches]
    niche_values = [item[1] for item in sorted_niches]
    # Create matching list of counts for the frontend (same order as labels)
    niche_quantities = [niche_counts[label] for label in niche_labels]

    # --- RECENT TRANSACTIONS ---
    recent_txs = Transaction.query.join(Contract).filter(
        Contract.company_id == company_id
    ).order_by(
        Transaction.status == 'paid', # Pending first
        Transaction.due_date.asc()
    ).limit(50).all()
    
    tx_list = []
    for t in recent_txs:
        tx_list.append({
            'id': t.id,
            'description': t.description,
            'client_name': t.contract.client.name,
            'amount': t.amount,
            'due_date': t.due_date.strftime('%d/%m/%Y'),
            'status': t.status
        })

    return jsonify({
        'kpis': {
            'forecast_30': forecast_30,
            'forecast_60': forecast_60,
            'forecast_90': forecast_90,
            'confirmed': paid_this_month,
            'risk': overdue,
            'mrr': mrr,
            'avg_ticket': avg_ticket,
            'active_clients': active_clients_count,
            'churn_rate': round(churn_rate, 2)
        },
        'charts': {
            'forecast': {'labels': chart_labels, 'data': chart_values},
            'niches': {'labels': niche_labels, 'data': niche_values, 'counts': niche_quantities} # NEW
        },
        'transactions': tx_list
    })

    t.paid_date = date.today()
    db.session.commit()
    return jsonify({'success': True})

@financial_bp.route('/financial/dre')
@login_required
def dre_page():
    if current_user.role not in [ROLE_ADMIN, ROLE_MANAGER]:
        abort(403)
    return render_template('financial/dre.html', now=datetime.now()) # Pass now for date filters

@financial_bp.route('/api/financial/dre')
@login_required
def get_dre_data():
    if current_user.role not in [ROLE_ADMIN, ROLE_MANAGER]:
        abort(403)
        
    company_id = current_user.company_id
    
    # Get filters
    year = request.args.get('year', type=int, default=date.today().year)
    month = request.args.get('month', type=int, default=date.today().month)
    
    # --- 1. RECEITA BRUTA (Transactions Paid + Issued in that month?) ---
    # Usually DRE is Competence Regime (issued invoice). Let's use 'due_date' (vencimento/competencia approx) or created_at?
    # For MVP financial, let's use 'due_date' as proxy for competence if paid or pending.
    # Ideally we should have 'competence_date', but due_date is close enough for simple CRM.
    
    # Fetch Revenue Transactions
    revenue_txs = Transaction.query.join(Contract).filter(
        Contract.company_id == company_id,
        extract('year', Transaction.due_date) == year,
        extract('month', Transaction.due_date) == month
        # We include all, or just paid? DRE Competency = All Billed. DRE Cash = All Paid.
        # Let's do COMPETENCY (Billed/Faturado).
    ).all()
    
    gross_revenue = sum(t.amount for t in revenue_txs)
    
    # --- 2. DEDUÇÕES (Impostos) --- 
    # Simple approx: Category 'Impostos' manually added OR calculated
    # Let's fetch Manual Expenses of type 'expense' named 'Impostos' or similar?
    # Actually, we defined Expense Types.
    # Let's fetch ALL Expenses for the period (by due_date)
    
    period_expenses = Expense.query.filter(
        Expense.company_id == company_id,
        extract('year', Expense.due_date) == year,
        extract('month', Expense.due_date) == month
    ).all()
    
    # Categorize
    taxes = 0
    variable_costs = 0 # Markting if variable? Or commissions?
    fixed_expenses = 0
    
    # Map from our DB Categories
    # We need to join with Category to check type
    
    # Helper to group by category for frontend
    breakdown_expenses = {} # { 'Pessoal': 5000, 'Marketing': 1000 }
    
    for exp in period_expenses:
        cat = exp.category
        val = exp.amount
        
        # Populate Breakdown
        if cat.name not in breakdown_expenses:
            breakdown_expenses[cat.name] = 0
        breakdown_expenses[cat.name] += val
        
        # Aggregate High Level
        if cat.type == 'cost':
             variable_costs += val
        elif cat.name.lower().startswith('imposto'): # Hacky if user didn't use default
             taxes += val
        else:
             # Default to fixed expense
             fixed_expenses += val
             
    # Adjust: If 'Impostos' is a category, we might have double counted in fixed_expenses if we didn't filtering logic properly.
    # Let's refine. type='revenue' (not used for expense), 'expense', 'cost'.
    # We will assume 'cost' = CMV/Variable. 'expense' = Fixed.
    # 'Impostos' usually is separate. Let's look for a category named "Impostos e Taxas".
    
    # Refined Loop
    taxes = 0
    variable_costs = 0
    fixed_expenses = 0
    breakdown = {}
    
    for exp in period_expenses:
        cat = exp.category
        val = exp.amount
        
        if cat.name not in breakdown: breakdown[cat.name] = 0
        breakdown[cat.name] += val
        
        if "imposto" in cat.name.lower():
            taxes += val
        elif cat.type == 'cost':
            variable_costs += val
        else:
            fixed_expenses += val

    # --- CALCULATION ---
    net_revenue = gross_revenue - taxes
    gross_profit = net_revenue - variable_costs # Margem de Contribuição
    # EBITDA = Gross Profit - Fixed Expenses (before interest/depreciation)
    # We assume all 'fixed_expenses' are operating expenses for EBITDA in this simple model.
    ebitda = gross_profit - fixed_expenses
    
    # Net Result (ignoring depreciation/interest for MVP)
    net_result = ebitda 
    
    return jsonify({
        'gross_revenue': gross_revenue,
        'taxes': taxes,
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

@financial_bp.route('/api/financial/categories')
@login_required
def get_categories():
    cats = FinancialCategory.query.filter_by(company_id=current_user.company_id).all()
    return jsonify([{ 'id': c.id, 'name': c.name, 'type': c.type } for c in cats])

@financial_bp.route('/clients/<int:id>/charges/new', methods=['POST'])
@login_required
def create_manual_charge(id):
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
        
    try:
        amount = float(amount_str.replace('R$', '').replace('.', '').replace(',', '.').strip())
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        
        # Create Transaction (Local)
        tx = Transaction(
            contract_id=None, # Manual Charge
            client_id=client.id,
            company_id=client.company_id,
            description=description,
            amount=amount,
            due_date=due_date,
            status='pending'
        )
        db.session.add(tx)
        db.session.flush()
        
        # Create in Asaas
        # Ensure customer exists
        customer_id = AsaasService.create_customer(client.company_id, client)
        payment_data = AsaasService.create_payment(client.company_id, customer_id, tx)
        
        tx.asaas_id = payment_data.get('id')
        tx.asaas_invoice_url = payment_data.get('invoiceUrl')
        
        db.session.commit()
         
        return jsonify({'success': True, 'message': 'Cobrança gerada com sucesso!'})
        
    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
