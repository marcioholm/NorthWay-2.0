from flask import Blueprint, render_template, jsonify, abort, request
from flask_login import login_required, current_user
from models import db, Contract, User, Goal, Transaction, ROLE_ADMIN, ROLE_MANAGER
from datetime import date, datetime
import json
from sqlalchemy import func, extract

goals_bp = Blueprint('goals', __name__)

@goals_bp.route('/goals')
@login_required
def dashboard():
    return render_template('goals.html', now=datetime.now())

@goals_bp.route('/api/goals/dashboard')
@login_required
def get_dashboard_data():
    company_id = current_user.company_id
    year = request.args.get('year', type=int, default=date.today().year)
    month = request.args.get('month', type=int, default=date.today().month)
    
    # --- 1. Fetch ALL Goals for the Year ---
    year_goals = Goal.query.filter_by(
        company_id=company_id,
        year=year
    ).all()
    
    # --- 2. Fetch ALL Transactions for the Year (Revenue) ---
    # We use Transaction.due_date as the reference for "Competence" (Faturamento prev/real)
    # Filter out cancelled. Use direct filter on Transaction.company_id to include manual charges.
    year_transactions = Transaction.query.filter(
        Transaction.company_id == company_id,
        extract('year', Transaction.due_date) == year,
        Transaction.status != 'cancelled'
    ).all()
    
    # --- 3. Fetch New Contracts for the Year (New Business Growth) ---
    # Used for the secondary condition "Minimum New Sales"
    year_new_contracts = Contract.query.filter(
        Contract.company_id == company_id,
        extract('year', Contract.created_at) == year, # Assuming created_at or specialized signed_at
        Contract.status.in_(['signed', 'active'])
    ).all()
    
    # Initialize Aggregators
    monthly_data = {
        'company_target': 0, 'company_actual': 0,
        'company_new_sales_target': 0, 'company_new_sales_actual': 0,
        'user_targets': {}, 'user_actuals': {}
    }
    annual_data = {
        'company_target': 0, 'company_actual': 0,
        'company_new_sales_target': 0, 'company_new_sales_actual': 0,
        'user_targets': {}, 'user_actuals': {}
    }
    
    # Helper to init user dicts
    all_users = User.query.filter_by(company_id=company_id).all()
    user_map = {u.id: u for u in all_users}
    for u in all_users:
        monthly_data['user_targets'][u.id] = 0
        monthly_data['user_actuals'][u.id] = 0
        annual_data['user_targets'][u.id] = 0
        annual_data['user_actuals'][u.id] = 0

    # Process Goals
    for g in year_goals:
        # Annual Aggregate
        if g.user_id is None:
            annual_data['company_target'] += g.target_amount
            annual_data['company_new_sales_target'] += (g.min_new_sales or 0)
        else:
            annual_data['user_targets'][g.user_id] = annual_data['user_targets'].get(g.user_id, 0) + g.target_amount
            
        # Monthly Specific
        if g.month == month:
            if g.user_id is None:
                monthly_data['company_target'] += g.target_amount
                monthly_data['company_new_sales_target'] += (g.min_new_sales or 0)
            else:
                monthly_data['user_targets'][g.user_id] = monthly_data['user_targets'].get(g.user_id, 0) + g.target_amount

    # Process Transactions (Revenue)
    for t in year_transactions:
        val = t.amount
        
        # Determine owners
        u_id = None
        if t.contract:
            u_id = t.contract.client.account_manager_id
        elif t.client:
            u_id = t.client.account_manager_id
        
        # Annual Aggregate
        annual_data['company_actual'] += val
        if u_id and u_id in annual_data['user_actuals']:
            annual_data['user_actuals'][u_id] += val
            
        # Monthly Specific
        if t.due_date.month == month:
            monthly_data['company_actual'] += val
            if u_id and u_id in monthly_data['user_actuals']:
                monthly_data['user_actuals'][u_id] += val
                
    # Process New Contracts (New Business)
    for c in year_new_contracts:
        try:
            data = json.loads(c.form_data)
            val_str = data.get('valor_parcela', '0')
            val = float(val_str.replace('.', '').replace(',', '.'))
        except:
            val = 0
            
        # Annual
        annual_data['company_new_sales_actual'] += val
        
        # Monthly
        if c.created_at.month == month:
            monthly_data['company_new_sales_actual'] += val

    # Helper to build Response Object
    def build_response(data_source):
        company_percent = int((data_source['company_actual'] / data_source['company_target'] * 100)) if data_source['company_target'] > 0 else 0
        
        ranking = []
        for u in all_users:
            target = data_source['user_targets'].get(u.id, 0)
            actual = data_source['user_actuals'].get(u.id, 0)
            percent = int((actual / target * 100)) if target > 0 else 0
            
            ranking.append({
                'user_id': u.id,
                'name': u.name,
                'role': u.role,
                'photo': u.profile_image,
                'target': target,
                'actual': actual,
                'percent': percent
            })
        ranking.sort(key=lambda x: x['percent'], reverse=True)
        
        return {
            'company': {
                'target': data_source['company_target'],
                'actual': data_source['company_actual'],
                'percent': company_percent,
                'new_sales_actual': data_source.get('company_new_sales_actual', 0)
            },
            'ranking': ranking
        }

    # Debug to File
    try:
        with open('debug_dashboard.log', 'w') as f:
            f.write(f"Year: {year}, Month: {month}\n")
            f.write(f"Monthly Data: {str(monthly_data)}\n")
            f.write(f"Response: {str(build_response(monthly_data))}\n")
    except: pass

    print(f"DEBUG DASHBOARD MONTHLY: {monthly_data}") 
    return jsonify({
        'monthly': build_response(monthly_data),
        'annual': build_response(annual_data)
    })

@goals_bp.route('/api/goals', methods=['POST'])
@login_required
def save_goals():
    if current_user.role not in [ROLE_ADMIN, ROLE_MANAGER]:
        abort(403)
        
    data = request.json
    year = int(data.get('year'))
    month = int(data.get('month'))
    print(f"DEBUG SAVE_GOALS: {data}") # Debugging
    
    
    # Safe Float Conversion Helper
    def parse_float(val):
        if not val or val == '': return 0.0
        return float(str(val).replace('.', '').replace(',', '.'))

    company_target = parse_float(data.get('company_target'))
    min_new_sales = parse_float(data.get('min_new_sales'))
    
    user_targets = data.get('user_targets', [])
    replicate = data.get('replicate', False)
    distribute_annual = data.get('distribute_annual', False)
    
    # Logic for Target Months & Values
    target_months = [month]
    monthly_company_target = company_target
    monthly_new_sales = min_new_sales
    monthly_user_scaler = 1.0 # Multiplier for user targets
    
    if distribute_annual:
        # If setting Annual Goal, apply to ALL months, but divided by 12
        target_months = range(1, 13)
        monthly_company_target = company_target / 12
        monthly_new_sales = min_new_sales / 12
        monthly_user_scaler = 1.0 / 12
    elif replicate:
        # If Replicating Monthly Goal, apply SAME value to ALL months
        target_months = range(1, 13)
        monthly_company_target = company_target
        monthly_new_sales = min_new_sales
        monthly_user_scaler = 1.0
        
    for m in target_months:
        # Upsert Company Goal
        c_goal = Goal.query.filter_by(company_id=current_user.company_id, user_id=None, year=year, month=m).first()
        if not c_goal:
            c_goal = Goal(company_id=current_user.company_id, user_id=None, year=year, month=m, type='revenue')
            db.session.add(c_goal)
        c_goal.target_amount = monthly_company_target
        c_goal.min_new_sales = monthly_new_sales
        
        # Upsert User Goals
        # Upsert User Goals
        for item in user_targets:
            u_id = item['user_id']
            amount = parse_float(item['amount'])
            
            # Apply Scaler (Divide by 12 if annual distribution)
            final_amount = amount * monthly_user_scaler
            
            u_goal = Goal.query.filter_by(company_id=current_user.company_id, user_id=u_id, year=year, month=m).first()
            if not u_goal:
                u_goal = Goal(company_id=current_user.company_id, user_id=u_id, year=year, month=m, type='revenue')
                db.session.add(u_goal)
            u_goal.target_amount = final_amount
        
    db.session.commit()
    return jsonify({'success': True})
