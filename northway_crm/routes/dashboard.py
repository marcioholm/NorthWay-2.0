from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Lead, Client, Task, Interaction, User, ROLE_ADMIN, ROLE_MANAGER, ROLE_SALES
from datetime import datetime, date, timedelta
from utils import update_client_health, api_response

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))
    return render_template('landing.html')

@dashboard_bp.route('/home')
@login_required
def home():
    company_id = current_user.company_id
    user_id = current_user.id
    
    # 1. Summary stats
    lead_count = Lead.query.filter_by(company_id=company_id).count()
    client_count = Client.query.filter_by(company_id=company_id).count()
    recent_leads = Lead.query.filter_by(company_id=company_id).order_by(Lead.created_at.desc()).limit(5).all()
    
    # 2. Daily items (Tasks and Attention Leads)
    today_tasks = get_today_tasks(company_id, user_id)
    attention_leads = get_attention_leads(company_id, user_id)
    
    # 3. Today Stats
    today_stats = {
        'leads_new': Lead.query.filter_by(company_id=company_id).filter(Lead.created_at >= date.today()).count(),
        'tasks_done': Task.query.filter_by(company_id=company_id, assigned_to_id=user_id, status='completa')\
                                   .filter(Task.completed_at >= date.today()).count()
    }
    
    # 4. Onboarding
    # Simple logic: if less than 5 leads/clients or no integrations
    step_leads = Lead.query.filter_by(company_id=company_id).count() > 0
    step_clients = Client.query.filter_by(company_id=company_id).count() > 0
    from models import Integration
    step_integrations = Integration.query.filter_by(company_id=company_id, is_active=True).count() > 0
    
    steps = [
        {'title': 'Adicionar primeiro lead', 'done': step_leads, 'link': url_for('leads.leads')},
        {'title': 'Converter primeiro cliente', 'done': step_clients, 'link': url_for('leads.leads')},
        {'title': 'Configurar Integrações', 'done': step_integrations, 'link': url_for('admin.settings_integrations')},
    ]
    
    onboarding = {
        'completed': all([s['done'] for s in steps]),
        'steps': steps,
        'progress': int(sum([1 for s in steps if s['done']]) / len(steps) * 100)
    }
    
    return render_template('home.html', 
                           lead_count=lead_count, 
                           client_count=client_count,
                           recent_leads=recent_leads,
                           today_tasks=today_tasks,
                           attention_leads=attention_leads,
                           today_stats=today_stats,
                           onboarding=onboarding,
                           now=datetime.now())

@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    company_id = current_user.company_id
    user_id = current_user.id
    
    # 1. KPIs
    total_leads = Lead.query.filter_by(company_id=company_id).count()
    active_clients = Client.query.filter_by(company_id=company_id, status='ativo').count()
    won_deals = Lead.query.filter_by(company_id=company_id, status='won').count()
    
    # Calculate MRR
    mrr_query = db.session.query(db.func.sum(Client.monthly_value)).filter_by(company_id=company_id, status='ativo').scalar()
    mrr = mrr_query if mrr_query else 0.0
    
    # 2. Risk & Tasks
    risky_clients = Client.query.filter_by(company_id=company_id, health_status='vermelho').count()
    pending_tasks = Task.query.filter_by(company_id=company_id, assigned_to_id=user_id, status='pendente').count()
    overdue_tasks = Task.query.filter_by(company_id=company_id, assigned_to_id=user_id, status='pendente')\
                               .filter(Task.due_date < datetime.now()).count()
    
    return render_template('dashboard.html',
                           total_leads=total_leads,
                           active_clients=active_clients,
                           won_deals=won_deals,
                           mrr=mrr,
                           risky_clients=risky_clients,
                           pending_tasks=pending_tasks,
                           overdue_tasks=overdue_tasks,
                           now=datetime.now())

def get_today_tasks(company_id, user_id):
    return Task.query.filter_by(company_id=company_id, assigned_to_id=user_id, status='pendente')\
               .filter(Task.due_date <= datetime.now()).all()

def get_attention_leads(company_id, user_id):
    # Leads with no interaction in over 3 days
    three_days_ago = datetime.now() - timedelta(days=3)
    return Lead.query.filter_by(company_id=company_id, assigned_to_id=user_id)\
               .filter(Lead.status != 'won')\
               .outerjoin(Interaction, (Interaction.lead_id == Lead.id) & (Interaction.company_id == company_id))\
               .group_by(Lead.id)\
               .having(db.or_(db.func.max(Interaction.created_at) < three_days_ago, db.func.max(Interaction.created_at) == None)).all()

def get_today_stats(company_id, user_id):
    # This is a placeholder for real time-series data
    return {
        'new_leads_today': 0,
        'conversions_today': 0,
        'completed_tasks_today': Task.query.filter_by(company_id=company_id, assigned_to_id=user_id, status='completa')\
                                      .filter(Task.due_date >= date.today()).count()
    }

@dashboard_bp.route('/api/dashboard/chart-data')
@login_required
def get_chart_data():
    period = request.args.get('period', 'monthly')
    now = datetime.now()
    company_id = current_user.company_id

    if period == 'today':
        start_date = datetime(now.year, now.month, now.day)
    elif period == 'daily':
        start_date = now - timedelta(days=30)
    elif period == 'weekly':
        start_date = now - timedelta(weeks=12)
    elif period == 'monthly':
        start_date = now - timedelta(days=365)
    else:
        start_date = now - timedelta(days=180)

    from models import Lead, Client # Local import
    leads = Lead.query.filter(Lead.company_id == company_id, Lead.created_at >= start_date).all()
    clients = Client.query.filter(Client.company_id == company_id, Client.created_at >= start_date).all()

    data_buckets = {}

    def get_bucket_key(date_obj, period):
        if period == 'today': return date_obj.strftime('%Y-%m-%d-%H'), date_obj.strftime('%H:00')
        if period == 'daily': return date_obj.strftime('%Y-%m-%d'), date_obj.strftime('%d/%m')
        if period == 'weekly': return date_obj.strftime('%Y-%W'), f"Sem {date_obj.strftime('%W')}"
        if period == 'monthly': return date_obj.strftime('%Y-%m'), date_obj.strftime('%b')
        return date_obj.strftime('%Y-%m'), date_obj.strftime('%b')

    for l in leads:
        sort_key, label = get_bucket_key(l.created_at, period)
        if sort_key not in data_buckets: data_buckets[sort_key] = {'label': label, 'leads': 0, 'sales': 0}
        data_buckets[sort_key]['leads'] += 1
    
    for c in clients:
        sort_key, label = get_bucket_key(c.created_at, period)
        if sort_key not in data_buckets: data_buckets[sort_key] = {'label': label, 'leads': 0, 'sales': 0}
        data_buckets[sort_key]['sales'] += 1
    
    sorted_keys = sorted(data_buckets.keys())
    return api_response(data={
        'labels': [data_buckets[k]['label'] for k in sorted_keys],
        'leads': [data_buckets[k]['leads'] for k in sorted_keys],
        'sales': [data_buckets[k]['sales'] for k in sorted_keys]
    })
