from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app, abort
from flask_login import login_required, current_user
from models import db, Lead, Client, Task, Interaction, User, Integration, ROLE_ADMIN, ROLE_MANAGER, ROLE_SALES
from datetime import datetime, date, timedelta
from utils import update_client_health, api_response

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.home'))
    return render_template('landing.html')

@dashboard_bp.route('/checkout')
@login_required
def checkout():
    if not current_user.company_id:
        return redirect(url_for('auth.login'))
        
    return render_template('checkout_standalone.html')

@dashboard_bp.route('/home')
@login_required
def home():
    if not current_user.company_id:
        abort(403)
        
    company_id = current_user.company_id
    user_id = current_user.id
    
    try:
        # 1. Summary stats
        lead_count = Lead.query.filter(Lead.company_id == company_id).count()
        client_count = Client.query.filter(Client.company_id == company_id).count()
        
        recent_leads = Lead.query.filter(Lead.company_id == company_id).order_by(Lead.created_at.desc()).limit(5).all()
        
        # 2. Daily items (Tasks and Attention Leads)
        today_tasks = get_today_tasks(company_id, user_id)
        attention_leads = get_attention_leads(company_id, user_id)
        
        # 3. Today Stats
        start_of_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        today_stats = {
            'leads_new': Lead.query.filter(Lead.company_id == company_id, Lead.created_at >= start_of_day).count(),
            'tasks_done': Task.query.filter(Task.company_id == company_id, Task.assigned_to_id == user_id, Task.status.in_(['completa', 'concluida']), Task.completed_at >= start_of_day).count()
        }
        
        # 4. Onboarding (Defensive Coding)
        try:
            step_leads = lead_count > 0
            step_clients = client_count > 0
            step_integrations = Integration.query.filter(Integration.company_id == company_id, Integration.is_active.is_(True)).count() > 0
            
            steps = [
                {'title': 'Adicionar primeiro lead', 'done': step_leads, 'link': url_for('leads.leads')},
                {'title': 'Converter primeiro cliente', 'done': step_clients, 'link': url_for('leads.leads')},
                {'title': 'Configurar Integrações', 'done': step_integrations, 'link': url_for('admin.settings_integrations')},
            ]
            
            onboarding = {
                'completed': current_user.onboarding_dismissed or all([s['done'] for s in steps]),
                'steps': steps,
                'progress': int(sum([1 for s in steps if s['done']]) / len(steps) * 100)
            }
        except Exception as e:
            print(f"Error in Onboarding Logic: {e}")
            onboarding = None
        
        # Calculate Overdue Count safely in Python
        now = datetime.now()
        overdue_count = len([t for t in today_tasks if t.due_date and t.due_date < now])

        return render_template('home.html', 
                               lead_count=lead_count, 
                               client_count=client_count,
                               recent_leads=recent_leads,
                               today_tasks=today_tasks,
                               overdue_count=overdue_count,
                               attention_leads=attention_leads,
                               today_stats=today_stats,
                               onboarding=onboarding,
                               now=now)
    except Exception as e:
        print(f"Error in home route: {e}")
        return render_template('home.html',
                               lead_count=0,
                               client_count=0,
                               recent_leads=[],
                               today_tasks=[],
                               overdue_count=0,
                               attention_leads=[],
                               today_stats={'leads_new': 0, 'tasks_done': 0},
                               onboarding=None,
                               now=datetime.now())

@dashboard_bp.route('/dashboard')
@login_required
def dashboard():
    if not current_user.company_id:
        abort(403)

    company_id = current_user.company_id
    user_id = current_user.id
    
    from flask import current_app
    # 1. KPIs
    total_leads = Lead.query.filter(Lead.company_id == company_id).count()
    active_clients = Client.query.filter(Client.company_id == company_id, Client.status == 'ativo').count()
    won_deals = Lead.query.filter(Lead.company_id == company_id, Lead.status == 'won').count()
    
    
    # Calculate MRR (exclude inadimplentes for accurate projections)
    mrr_query = db.session.query(db.func.sum(Client.monthly_value)).filter(
        Client.company_id == company_id,
        Client.status == 'ativo',
        Client.payment_status.in_(['em_dia', 'atrasado'])  # Exclude inadimplentes
    ).scalar()
    mrr = mrr_query if mrr_query else 0.0
    
    # MRR at Risk (inadimplentes)
    mrr_risk_query = db.session.query(db.func.sum(Client.monthly_value)).filter(
        Client.company_id == company_id,
        Client.status == 'ativo',
        Client.payment_status == 'inadimplente'
    ).scalar()
    mrr_at_risk = mrr_risk_query if mrr_risk_query else 0.0
    
    # 2. Risk & Tasks
    risky_clients = Client.query.filter_by(company_id=company_id, health_status='vermelho').count()
    pending_tasks = Task.query.filter_by(company_id=company_id, assigned_to_id=user_id, status='pendente').count()
    overdue_tasks = Task.query.filter_by(company_id=company_id, assigned_to_id=user_id, status='pendente')\
                               .filter(Task.due_date < datetime.now()).count()
    
    # 3. Pipelines & Funnel Data (Default to First)
    from models import Pipeline, PipelineStage
    pipelines = Pipeline.query.filter_by(company_id=company_id).all()
    
    # Default Funnel Data (First Pipeline)
    current_pipeline_id = pipelines[0].id if pipelines else None
    
    return render_template('dashboard.html',
                           total_leads=total_leads,
                           active_clients=active_clients,
                           won_deals=won_deals,
                           mrr=mrr,
                           mrr_at_risk=mrr_at_risk,
                           risky_clients=risky_clients,
                           pending_tasks=pending_tasks,
                           overdue_tasks=overdue_tasks,
                           pipelines=pipelines,
                           current_pipeline_id=current_pipeline_id,
                           now=datetime.now())

@dashboard_bp.route('/api/dashboard/funnel-data/<int:pipeline_id>')
@login_required
def get_funnel_data(pipeline_id):
    if not current_user.company_id:
        return jsonify({'error': 'Unauthorized'}), 403
        
    from models import Pipeline, PipelineStage
    
    # 1. Date Filtering
    period = request.args.get('period', 'monthly')
    now = datetime.now()
    start_date = None
    
    if period == 'today':
        start_date = datetime(now.year, now.month, now.day)
    elif period == 'daily': # Last 30 days
        start_date = now - timedelta(days=30)
    elif period == 'weekly': # Last 12 weeks
        start_date = now - timedelta(weeks=12)
    elif period == 'monthly': # Last year
        start_date = now - timedelta(days=365)
    elif period == 'bimonthly':
        start_date = now - timedelta(days=730)
    elif period == 'quarterly':
        start_date = now - timedelta(days=730)
    elif period == 'semiannual':
         start_date = now - timedelta(days=1095)
    elif period == 'annual':
        start_date = now - timedelta(days=1825)
    elif period == 'all_time':
        start_date = None
    else: # Default
        start_date = None # Standard to see all history if no valid period selected

    # Verify pipeline
    pipeline = Pipeline.query.filter_by(id=pipeline_id, company_id=current_user.company_id).first()
    if not pipeline:
        return jsonify({'error': 'Pipeline not found'}), 404
        
    # Get Stages
    stages = PipelineStage.query.filter_by(pipeline_id=pipeline.id).order_by(PipelineStage.order).all()
    
    # 2. Get Raw Counts per Stage (Filtered by Cohort/Date)
    # We filter by Lead Creation Date to see the performance of the cohort generated in that period.
    raw_counts = {}
    base_query = Lead.query.filter(
        Lead.company_id == current_user.company_id,
        Lead.pipeline_id == pipeline.id
    )
    
    if start_date:
        base_query = base_query.filter(Lead.created_at >= start_date)
        
    counts = base_query.with_entities(Lead.pipeline_stage_id, db.func.count(Lead.id)).group_by(Lead.pipeline_stage_id).all()
    raw_counts = dict(counts)

    # 3. Calculate Cumulative (Waterfall) Counts
    # If a lead is in Stage 3, they count for Stage 3, Stage 2, and Stage 1.
    funnel_data = {'labels': [], 'data': []}
    
    # Iterate stages in order
    for i, stage in enumerate(stages):
        cumulative_count = 0
        
        # Add counts from this stage AND all subsequent stages
        for subsequent_stage in stages[i:]:
            cumulative_count += raw_counts.get(subsequent_stage.id, 0)
            
        funnel_data['labels'].append(stage.name)
        funnel_data['data'].append(cumulative_count)
        
    return jsonify(funnel_data)

def get_today_tasks(company_id, user_id):
    # Tasks due today or before (overdue), ensuring standard DateTime comparison
    now = datetime.now()
    return Task.query.filter(
        Task.company_id == company_id, 
        Task.assigned_to_id == user_id, 
        Task.status == 'pendente',
        Task.due_date < now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    ).all()


def get_attention_leads(company_id, user_id):
    # Leads with no interaction in over 3 days
    three_days_ago = datetime.now() - timedelta(days=3)
    query = Lead.query.filter(Lead.company_id == company_id, Lead.assigned_to_id == user_id, Lead.status != 'won')\
               .outerjoin(Interaction, (Interaction.lead_id == Lead.id) & (Interaction.company_id == company_id))\
               .group_by(Lead.id)\
               .having(db.or_(db.func.max(Interaction.created_at) < three_days_ago, db.func.max(Interaction.created_at) == None))
    return query.all()

def get_today_stats(company_id, user_id):
    # This is a placeholder for real time-series data
    return {
        'new_leads_today': 0,
        'conversions_today': 0,
        'completed_tasks_today': Task.query.filter_by(company_id=company_id, assigned_to_id=user_id, ).filter(Task.status.in_(['completa', 'concluida']))\
                                      .filter(Task.due_date >= date.today()).count()
    }


def get_bucket_key(date_obj, period):
    from services.chart_service import bucket_key
    return bucket_key(date_obj, period)


@dashboard_bp.route('/api/dashboard/chart-data')
@login_required
def get_chart_data():
    if not current_user.company_id:
        abort(403)
    from services.chart_service import chart_data
    period = request.args.get('period', 'monthly')
    try:
        data = chart_data(current_user.company_id, period)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    return api_response(data=data)

@dashboard_bp.route('/api/trigger-automation', methods=['POST'])
@login_required
def trigger_automation():
    if getattr(current_user, 'role', '') not in ['admin', 'gestor']:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
        
    from services.automation_service import AutomationService
    try:
        AutomationService.check_leads_followup(current_user.company_id)
        return jsonify({"success": True, "message": "Automation cadence checks triggered successfully"}), 200
    except Exception as e:
        current_app.logger.error(f"❌ Error triggering cadence check via API: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


