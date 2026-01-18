from datetime import datetime, date, timedelta
import os
import json
import markdown
import markdown
import csv
import io
from datetime import datetime, timedelta, date
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Blueprint, abort, make_response, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Role, Lead, Client, Interaction, Task, Pipeline, PipelineStage, Company, Notification, Contract, ContractTemplate, Transaction, ProcessTemplate, ClientChecklist, WhatsAppMessage, ROLE_ADMIN, ROLE_MANAGER, ROLE_SALES, LEAD_STATUS_WON, LEAD_STATUS_NEW, LEAD_STATUS_IN_PROGRESS, LEAD_STATUS_LOST
from auth import auth as auth_blueprint
from master import master as master_blueprint
from routes.financial import financial_bp
from routes.docs import docs_bp
from routes.goals import goals_bp
from routes.prospecting import prospecting_bp
from routes.prospecting import prospecting_bp
from routes.integrations import integrations_bp
# from routes.admin import admin_bp (Moved to bottom registration)

main = Blueprint('main', __name__)

def create_notification(user_id, company_id, type, title, message):
    try:
        notification = Notification(
            user_id=user_id,
            company_id=company_id,
            type=type,
            title=title,
            message=message
        )
        db.session.add(notification)
        db.session.commit()
    except Exception as e:
        print(f"Error creating notification: {e}")
        db.session.rollback()

def create_app():
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')
    
    # Database Configuration
    # Prioritize DATABASE_URL (Postgres on Vercel), fallback to SQLite locally
    database_url = os.environ.get('DATABASE_URL')
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///crm.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # API Key provided by user (Should be in env vars in production)
    app.config['GOOGLE_MAPS_API_KEY'] = os.environ.get('GOOGLE_MAPS_API_KEY', 'AIzaSyCjgXOawchWfTjqoeWtHg65VtGmVu7xwT8')
    COMPANY_UPLOAD_FOLDER = 'static/uploads/company'
    app.config['UPLOAD_FOLDER'] = 'static/uploads/profiles' # Keep existing
    app.config['COMPANY_UPLOAD_FOLDER'] = COMPANY_UPLOAD_FOLDER

    # Supabase Configuration
    # Defaults provided for LOCAL development convenience, but PROD must use Envs
    app.config['SUPABASE_URL'] = os.environ.get('SUPABASE_URL', 'https://bnumpvhsfujpprovajkt.supabase.co')
    app.config['SUPABASE_KEY'] = os.environ.get('SUPABASE_KEY', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJudW1wdmhzZnVqcHByb3Zhamt0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjgzNjA5OTgsImV4cCI6MjA4MzkzNjk5OH0.pVcON2srZ2FXQ36Q-72WAHB-gVdrP_5Se-_K8XQ15Gs')
    
    from services.supabase_service import init_supabase
    app.supabase = init_supabase(app)
    
    # Ensure directories exist
    # Ensure directories exist (Handle Read-Only Filesystem for Vercel)
    try:
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        os.makedirs(app.config['COMPANY_UPLOAD_FOLDER'], exist_ok=True)
    except OSError:
        # Likely read-only filesystem (Vercel)
        print("Warning: Could not create upload directories. Using /tmp if needed.")
        app.config['UPLOAD_FOLDER'] = '/tmp/uploads/profiles'
        app.config['COMPANY_UPLOAD_FOLDER'] = '/tmp/uploads/company'
        try:
           os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
           os.makedirs(app.config['COMPANY_UPLOAD_FOLDER'], exist_ok=True)
        except:
           pass

    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # 16MB limit

    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    # Initialize extensions
    db.init_app(app)
    
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register Blueprints
    app.register_blueprint(auth_blueprint)
    app.register_blueprint(master_blueprint)
    app.register_blueprint(integrations_bp)
    
    # Main Blueprint (defined here for simplicity in MVP)
    from flask import Blueprint
    main = Blueprint('main', __name__)

    @app.context_processor
    def inject_counts():
        if current_user.is_authenticated:
            pending_count = Task.query.filter_by(assigned_to_id=current_user.id, status='pendente').count()
            return dict(pending_tasks_count=pending_count)
        return dict(pending_tasks_count=0)

    @main.route('/')
    def index():
        if current_user.is_authenticated:
            if getattr(current_user, 'is_super_admin', False):
                return redirect(url_for('master.dashboard'))
            return redirect(url_for('main.home'))
        return redirect(url_for('auth.login'))

    @main.route('/home')
    @login_required
    def home():
        company_id = current_user.company_id
        
        # Onboarding Logic
        # (Mock Logic for now, real logic would check DB records)
        onboarding = {
            'completed': current_user.onboarding_dismissed if hasattr(current_user, 'onboarding_dismissed') else False,
            'progress': 25,
            'steps': [
                {'title': 'Completar Perfil', 'done': True, 'link': url_for('main.profile')},
                {'title': 'Criar Primeiro Funil', 'done': False, 'link': url_for('main.pipeline')},
                {'title': 'Adicionar 5 Leads', 'done': False, 'action': "window.location.href='/leads'"} 
            ]
        }

        return render_template('home.html',
                               now=datetime.now(),
                               onboarding=onboarding,
                               today_tasks=get_today_tasks(company_id=company_id, user_id=current_user.id),
                               attention_leads=get_attention_leads(company_id=company_id, user_id=current_user.id),
                               today_stats=get_today_stats(company_id=company_id, user_id=current_user.id)
                               )

    def update_client_health(client):
        """
        Updates client health based on interaction recency.
        Green: <= 3 days
        Yellow: 4-7 days
        Red: > 7 days or No interaction
        """
        # Optimize: use eager loaded relationship sorted in Python
        # last_interaction = Interaction.query.filter_by(client_id=client.id, company_id=client.company_id).order_by(Interaction.created_at.desc()).first()
        last_interaction = None
        if client.interactions:
            # Sort descending in memory (Relationship is lazy=True but we joinedload it in caller)
            # Or if it's already loaded, we just sort.
            interactions_list = sorted(client.interactions, key=lambda x: x.created_at, reverse=True)
            if interactions_list:
                last_interaction = interactions_list[0]
        
        status = 'vermelho' # Default critical
        
        if last_interaction:
            days_diff = (datetime.now() - last_interaction.created_at).days
            
            if days_diff <= 3:
                status = 'verde'
            elif days_diff <= 7:
                status = 'amarelo'
            else:
                status = 'vermelho'
        
        if status and status != client.health_status:
            client.health_status = status
            
            # NOTIFICATION: Status Changed
            # Notify account manager
            if client.account_manager_id and client.account_manager_id != current_user.id:
                 create_notification(
                     user_id=client.account_manager_id,
                     company_id=current_user.company_id,
                     type='client_status_changed',
                     title='Status do Cliente Alterado',
                     message=f"Status do cliente {client.name} alterado para {status} por {current_user.name}."
                 )
            # Commit removed from here to allow bulk commit in caller

    @main.route('/dashboard')
    @login_required
    def dashboard():
        company_id = current_user.company_id
        
        # RBAC: Sales only see their own stats
        query_filters = {'company_id': company_id}
        if current_user.role not in [ROLE_ADMIN, ROLE_MANAGER]:
            query_filters['assigned_to_id'] = current_user.id
            
        # Leads Stats
        total_leads = Lead.query.filter_by(**query_filters).count()
        won_deals = Lead.query.filter_by(status=LEAD_STATUS_WON, **query_filters).count()
        
        # Client Stats (New)
        active_clients = Client.query.filter_by(company_id=current_user.company_id).filter(Client.status.in_(['ativo', 'onboarding'])).count()
        
        # Health Risks
        risky_clients = Client.query.filter_by(company_id=current_user.company_id).filter(Client.health_status.in_(['amarelo', 'vermelho'])).count()
        
        # Renewals (Next 30 days or overdue)
        today = date.today()
        renewal_threshold = today + timedelta(days=30)
        renewal_alerts = Client.query.filter_by(company_id=current_user.company_id).filter(Client.renewal_date != None).filter(Client.renewal_date <= renewal_threshold).count()
        
        # Overdue Tasks
        overdue_tasks = Task.query.filter_by(company_id=current_user.company_id, status='pendente').filter(Task.due_date < datetime.now()).count()
        
        # All Pending Tasks (User request)
        pending_tasks = Task.query.filter_by(company_id=current_user.company_id, status='pendente').count()
        
        # --- AUTOMATION: Lost Lead Recovery ---
        # Logic: Find leads 'lost' > 90 days ago that don't have a recent recovery task
        try:
            recovery_threshold = datetime.now() - timedelta(days=90)
            
            lost_leads = Lead.query.filter(
                Lead.company_id == current_user.company_id,
                Lead.status == LEAD_STATUS_LOST,
                # Simple approximation: Using created_at or updated_at if available. 
                # Since we didn't add updated_at schema, we rely on interactions or created_at.
                # Let's use created_at for safety or last interaction check.
                Lead.created_at <= recovery_threshold
            ).limit(5).all() # Limit batch size
            
            for lead in lost_leads:
                # Check if we already created a recovery task recently (avoid spam)
                has_recovery_task = Task.query.filter(
                    Task.lead_id == lead.id,
                    Task.title.like('Reconexão:%')
                ).count() > 0
                
                if not has_recovery_task:
                    recovery_task = Task(
                        title=f"Reconexão: {lead.name}",
                        description="Este lead foi perdido há mais de 3 meses. Vale a pena tentar um novo contato para ver se o momento mudou.",
                        due_date=datetime.now() + timedelta(days=1),
                        priority='media',
                        status='pendente',
                        lead_id=lead.id,
                        assigned_to_id=lead.assigned_to_id or current_user.id,
                        company_id=lead.company_id
                    )
                    db.session.add(recovery_task)
                    
                    # Notify
                    create_notification(
                        user_id=lead.assigned_to_id or current_user.id,
                        company_id=current_user.company_id,
                        type='task_assigned',
                        title='Oportunidade de Recuperação',
                        message=f"O sistema sugeriu uma reconexão com {lead.name}."
                    )
            
            db.session.commit()
        except Exception as e:
            print(f"Error in automation: {e}")
            db.session.rollback()
        # --------------------------------------

        return render_template('dashboard.html', 
                               total_leads=total_leads, 
                               won_deals=won_deals,
                               active_clients=active_clients,
                               risky_clients=risky_clients,
                               overdue_tasks=overdue_tasks,
                               pending_tasks=pending_tasks,
                               now=datetime.now())

    def get_today_tasks(company_id, user_id):
        now = datetime.now()
        end_of_day = now.replace(hour=23, minute=59, second=59)
        # Tasks due today or overdue
        return Task.query.filter(
            Task.company_id == company_id,
            Task.assigned_to_id == user_id,
            Task.status == 'pendente',
            db.or_(Task.due_date <= end_of_day, Task.due_date == None)
        ).order_by(Task.due_date.nullsfirst()).all()

    def get_attention_leads(company_id, user_id):
        # Leads assigned to user that haven't had an interaction today
        # Limit to 5
        assigned_leads = Lead.query.filter_by(
            company_id=company_id, 
            assigned_to_id=user_id,
            status=LEAD_STATUS_IN_PROGRESS
        ).limit(30).all() # Fetch reasonably active leads to check
        
        today = date.today()
        attention_list = []
        
        for lead in assigned_leads:
            # Check interactions today
            has_interaction = False
            # Optimize: Could be joined query, but loop safe for MVP scale
            for interaction in lead.interactions:
                 if interaction.created_at.date() == today:
                     has_interaction = True
                     break
            if not has_interaction and len(attention_list) < 5:
                attention_list.append(lead)
                
        return attention_list

    def get_today_stats(company_id, user_id):
        now = datetime.now()
        start_of_day = now.replace(hour=0, minute=0, second=0)
        
        # New Leads Today
        leads_new = Lead.query.filter(
            Lead.company_id == company_id, 
            Lead.assigned_to_id == user_id,
            Lead.created_at >= start_of_day
        ).count()
        
        # Tasks Completed Today
        # We don't track completed_at explicitly in this simple model, so we check status 'concluida' 
        # but strictly we can't know IF it was today without a 'completed_at' field or interaction check.
        # BEST EFFORT CHECK: Count 'tarefa_concluida' interactions for this user today.
        tasks_done = Interaction.query.filter(
            Interaction.user_id == user_id,
            Interaction.company_id == company_id,
            Interaction.type == 'tarefa_concluida',
            Interaction.created_at >= start_of_day
        ).count()

        return {
            'leads_new': leads_new,
            'tasks_done': tasks_done
        }

    @main.route('/leads', methods=['GET', 'POST'])
    @login_required
    def leads():
        # Similar logic to before, but we might want to let them select pipeline for new lead
        # For MVP, default to user's first allowed pipeline
        
        if request.method == 'POST':
            name = request.form.get('name')
            email = request.form.get('email')
            phone = request.form.get('phone')
            source = request.form.get('source')
            interest = request.form.get('interest')
            notes = request.form.get('notes')
            assigned_to_id = request.form.get('assigned_to_id')
            
            # RBAC: Only Admin/Manager can delegate
            if current_user.role in [ROLE_ADMIN, ROLE_MANAGER]:
                assigned_to = int(assigned_to_id) if assigned_to_id else current_user.id
            else:
                assigned_to = current_user.id
            
            # Get default pipeline for this user/company
            default_pipeline = current_user.allowed_pipelines[0] if current_user.allowed_pipelines else None
            first_stage = None
            if default_pipeline:
                first_stage = PipelineStage.query.filter_by(pipeline_id=default_pipeline.id).order_by(PipelineStage.order).first()
            
            new_lead = Lead(
                name=name,
                email=email,
                phone=phone,
                source=source,
                interest=interest,
                notes=notes,
                company_id=current_user.company_id,
                pipeline_id=default_pipeline.id if default_pipeline else None,
                pipeline_stage_id=first_stage.id if first_stage else None,
                assigned_to_id=assigned_to
            )
            
            db.session.add(new_lead)
            db.session.commit()
            
            # Notify assignee if not self
            if assigned_to != current_user.id:
                create_notification(
                    user_id=assigned_to, 
                    company_id=current_user.company_id,
                    type='lead_assigned',
                    title='Novo Lead Atribuído',
                    message=f"Você recebeu um novo lead: {name}"
                )
            
            flash('Lead criado com sucesso!', 'success')
            return redirect(url_for('main.leads'))

        # RBAC: Filter filtering
        query = Lead.query.filter_by(company_id=current_user.company_id)
        if current_user.role not in [ROLE_ADMIN, ROLE_MANAGER]:
            query = query.filter_by(assigned_to_id=current_user.id)
            
        leads = query.options(db.joinedload(Lead.assigned_user)).order_by(Lead.created_at.desc()).all()
        users = User.query.filter_by(company_id=current_user.company_id).all()
        return render_template('leads.html', leads=leads, users=users)

    @main.route('/pipeline')
    @main.route('/pipeline/<int:pipeline_id>')
    @login_required
    def pipeline(pipeline_id=None):
        if current_user.role == ROLE_ADMIN:
            allowed = Pipeline.query.filter_by(company_id=current_user.company_id).all()
        else:
            allowed = current_user.allowed_pipelines
        if not allowed:
            flash('Você não tem acesso a nenhum funil.', 'error')
            return redirect(url_for('main.dashboard'))
            
        if pipeline_id:
            # Check access
            active_pipeline = next((p for p in allowed if p.id == pipeline_id), None)
            if not active_pipeline:
                 flash('Acesso negado a este funil.', 'error')
                 return redirect(url_for('main.pipeline'))
        else:
            active_pipeline = allowed[0]
            
        stages = PipelineStage.query.filter_by(pipeline_id=active_pipeline.id).order_by(PipelineStage.order).all()
        
        # RBAC: Filter leads
        leads_query = Lead.query.filter_by(company_id=current_user.company_id, pipeline_id=active_pipeline.id)
        if current_user.role not in [ROLE_ADMIN, ROLE_MANAGER]:
            leads_query = leads_query.filter_by(assigned_to_id=current_user.id)
            
        leads = leads_query.options(db.joinedload(Lead.assigned_user)).all()
        
        return render_template('pipeline.html', 
                             stages=stages, 
                             leads=leads, 
                             active_pipeline=active_pipeline, 
                             pipelines=allowed)

    @main.route('/pipelines/<int:id>/stages', methods=['POST'])
    @login_required
    def create_stage(id):
        if current_user.role != 'admin':
            return "Unauthorized", 403
            
        pipeline = Pipeline.query.get_or_404(id)
        # Check access (simplified: creator or admin of company)
        if pipeline.company_id != current_user.company_id:
             return "Unauthorized", 403
             
        name = request.form.get('name')
        if name:
            # Append to end
            last_stage = PipelineStage.query.filter_by(pipeline_id=pipeline.id).order_by(PipelineStage.order.desc()).first()
            new_order = last_stage.order + 1 if last_stage else 0
            
            stage = PipelineStage(
                name=name,
                order=new_order,
                pipeline_id=pipeline.id,
                company_id=current_user.company_id
            )
            db.session.add(stage)
            db.session.commit()
            flash('Etapa criada.', 'success')
            
        return redirect(url_for('main.pipeline', pipeline_id=id))

    @main.route('/stages/<int:id>/update', methods=['POST'])
    @login_required
    def update_stage(id):
        if current_user.role != 'admin':
            return "Unauthorized", 403
            
        stage = PipelineStage.query.get_or_404(id)
        if stage.company_id != current_user.company_id:
            return "Unauthorized", 403
            
        name = request.form.get('name')
        if name:
            stage.name = name
            db.session.commit()
            flash('Etapa renomeada.', 'success')
            
        return redirect(url_for('main.pipeline', pipeline_id=stage.pipeline_id))

    @main.route('/stages/<int:id>/delete', methods=['POST'])
    @login_required
    def delete_stage(id):
        if current_user.role != 'admin':
            return "Unauthorized", 403
            
        stage = PipelineStage.query.get_or_404(id)
        if stage.company_id != current_user.company_id:
            return "Unauthorized", 403
            
        # Check for leads
        lead_count = Lead.query.filter_by(pipeline_stage_id=stage.id).count()
        if lead_count > 0:
            flash(f'Não é possível excluir etapa com {lead_count} leads. Mova-os primeiro.', 'error')
        else:
            db.session.delete(stage)
            db.session.commit()
            flash('Etapa excluída.', 'success')
            
        return redirect(url_for('main.pipeline', pipeline_id=stage.pipeline_id))

    @main.route('/pipelines/new', methods=['POST'])
    @login_required
    def create_pipeline():
        if current_user.role != 'admin':
            flash('Apenas administradores podem criar funis.', 'error')
            return redirect(url_for('main.pipeline'))
            
        name = request.form.get('name')
        if not name:
            flash('Nome do funil é obrigatório.', 'error')
            return redirect(url_for('main.pipeline'))
            
        # Create Pipeline
        new_pipeline = Pipeline(name=name, company_id=current_user.company_id)
        db.session.add(new_pipeline)
        db.session.commit()
        
        # Add default stages
        default_stages = ['Novo', 'Qualificação', 'Proposta', 'Negociação', 'Fechado']
        for i, stage_name in enumerate(default_stages):
            stage = PipelineStage(
                name=stage_name, 
                order=i, 
                pipeline_id=new_pipeline.id,
                company_id=current_user.company_id
            )
            db.session.add(stage)
            
        # Grant access to creator
        current_user.allowed_pipelines.append(new_pipeline)
        db.session.commit()
        
        flash(f'Funil "{name}" criado com sucesso!', 'success')
        return redirect(url_for('main.pipeline', pipeline_id=new_pipeline.id))

    @main.route('/tasks', methods=['GET', 'POST'])
    @login_required
    def tasks():
        if request.method == 'POST':
            title = request.form.get('title')
            due_date_str = request.form.get('due_date')
            lead_id = request.form.get('lead_id')
            
            due_date = None
            if due_date_str:
                # Support "YYYY-MM-DDTHH:MM" (local datetime)
                try:
                    due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    # Fallback for just date if happened
                    try:
                        due_date = datetime.strptime(due_date_str, '%Y-%m-%d')
                    except:
                        pass
                
            if lead_id:
                lead_id = int(lead_id)
                lead = Lead.query.get(lead_id)
                assigned_to = lead.assigned_to_id if lead else current_user.id
            else:
                lead_id = None
                assigned_to = current_user.id
                
            # Handle client_id
            client_id = request.form.get('client_id')
            if client_id:
                client_id = int(client_id)
                client = Client.query.get(client_id)
                if client:
                    assigned_to = client.account_manager_id or current_user.id
            else:
                client_id = None
            
            is_recurring = True if request.form.get('is_recurring') else False

            new_task = Task(
                title=title,
                due_date=due_date,
                lead_id=lead_id,
                client_id=client_id,
                assigned_to_id=assigned_to,
                company_id=current_user.company_id,
                is_recurring=is_recurring,
                recurrence='mensal' if is_recurring else None
                # reminder_sent default is False
            )
            
            db.session.add(new_task)
            
            # Log interaction if client task
            if client_id:
                interaction = Interaction(
                    client_id=client_id,
                    user_id=current_user.id,
                    company_id=current_user.company_id,
                    type='tarefa_criada',
                    content=f"Criou a tarefa: {title}",
                    created_at=datetime.now()
                )
                db.session.add(interaction)
                
            db.session.commit()
            
            # NOTIFICATION: Task Assigned
            if assigned_to != current_user.id:
                create_notification(
                    user_id=assigned_to,
                    company_id=current_user.company_id,
                    type='task_assigned',
                    title='Nova Tarefa Atribuída',
                    message=f"Você recebeu uma nova tarefa: {title}"
                )
                
            flash('Tarefa criada!', 'success')
            return redirect(request.referrer or url_for('main.tasks'))

        all_tasks = Task.query.filter_by(company_id=current_user.company_id).order_by(Task.status, Task.due_date).all()
        
        # Filter Pending vs Completed
        pending_tasks = [t for t in all_tasks if t.status != 'concluida']
        
        # Sort completed tasks by completed_at desc (newest first)
        completed_tasks_with_date = [t for t in all_tasks if t.status == 'concluida']
        completed_tasks_list = sorted(completed_tasks_with_date, key=lambda x: x.completed_at or datetime.min, reverse=True)
        
        # Split PENDING tasks for main tabs (Active work)
        lead_tasks = [t for t in pending_tasks if t.lead_id is not None]
        client_tasks = [t for t in pending_tasks if t.client_id is not None]
        general_tasks = [t for t in pending_tasks if t.lead_id is None and t.client_id is None]
        
        # Calculate stats (Overall)
        total_tasks = len(all_tasks)
        completed_tasks = len([t for t in all_tasks if t.status == 'concluida'])
        progress_percent = int((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0
        
        leads = Lead.query.filter_by(company_id=current_user.company_id).all() # For dropdown
        clients = Client.query.filter_by(company_id=current_user.company_id).all() # For dropdown (if we add quick add for clients)

        # Onboarding Stats
        onboarding_data = None
        if not current_user.onboarding_dismissed:
            has_profile = bool(current_user.phone or current_user.status_message)
            has_leads = Lead.query.filter_by(company_id=current_user.company_id).count() > 0
            # For "Configure Pipeline", we'll check if they have created a new pipeline OR visited settings (approximated by checking pipeline count > 1 or manual dismiss)
            # Simplified: Check if they have moved a lead (interactions > 0)?
            # Let's simple check: Have they created a new pipeline?
            has_pipeline_config = Pipeline.query.filter_by(company_id=current_user.company_id).count() > 1
            
            # Or simplest: Just checking if they have leads in 'In Progress' stages?
            # Let's stick to "Create First Task" as a substitute? No, user asked for "Configurar Funil".
            # Let's count stages. If != 5 (default), maybe they configured it?
            # For MVP, let's mark it done if they have > 0 leads, assuming they used the funnel.
            # Actually, let's use: has_leads AND has_profile.
            
            onboarding_steps = [
                {'id': 'profile', 'title': 'Completar Perfil', 'done': has_profile, 'link': url_for('main.profile')},
                {'id': 'lead', 'title': 'Criar Primeiro Lead', 'done': has_leads, 'action': "toggleModal('createLeadModal')"},
                {'id': 'pipeline', 'title': 'Configurar Funil', 'done': has_pipeline_config, 'link': url_for('main.pipeline')},
            ]
            
            completed_count = sum(1 for step in onboarding_steps if step['done'])
            progress = int((completed_count / 3) * 100)
            onboarding_data = {'steps': onboarding_steps, 'progress': progress} # Assign onboarding_data here
        leads = Lead.query.filter_by(company_id=current_user.company_id).all() # For dropdown
        clients = Client.query.filter_by(company_id=current_user.company_id).all() # For dropdown (if we add quick add for clients)

        return render_template('tasks.html', 
                             lead_tasks=lead_tasks,
                             client_tasks=client_tasks,
                             general_tasks=general_tasks,
                             completed_tasks_list=completed_tasks_list,
                             leads=leads, 
                             clients=clients,
                             total_tasks=total_tasks, 
                             completed_tasks=completed_tasks, 
                             progress_percent=progress_percent,
                             onboarding_data=onboarding_data,
                             now=datetime.now())

    @main.route('/dismiss_onboarding', methods=['POST'])
    @login_required
    def dismiss_onboarding():
        current_user.onboarding_dismissed = True
        db.session.commit()
        return '', 204



    @main.route('/tasks/<int:id>/toggle', methods=['POST'])
    @login_required
    def toggle_task(id):
        task = Task.query.get_or_404(id)
        if task.company_id != current_user.company_id:
            return "Unauthorized", 403
            
        if task.status == 'pendente':
            task.status = 'concluida'
            task.completed_at = datetime.now()
            
            # Handle Recurrence
            if task.is_recurring and task.recurrence == 'mensal':
                # Create next task
                next_due_date = None
                if task.due_date:
                    import calendar
                    year = task.due_date.year
                    month = task.due_date.month + 1
                    if month > 12:
                        month = 1
                        year += 1
                    
                    try:
                        day = min(task.due_date.day, calendar.monthrange(year, month)[1])
                        next_due_date = task.due_date.replace(year=year, month=month, day=day)
                    except ValueError:
                         # Fallback for safe date math errors
                         next_due_date = task.due_date + timedelta(days=30)

                next_task = Task(
                    title=task.title,
                    due_date=next_due_date,
                    status='pendente',
                    lead_id=task.lead_id,
                    client_id=task.client_id,
                    company_id=task.company_id,
                    assigned_to_id=task.assigned_to_id,
                    is_recurring=True,
                    recurrence='mensal'
                )
                db.session.add(next_task)
                flash('Tarefa concluída! Próxima recorrência mensal agendada.', 'success')
            
            # Log Interaction if it's a client task
            if task.client_id:
                interaction = Interaction(
                    client_id=task.client_id,
                    user_id=current_user.id,
                    company_id=current_user.company_id,
                    type='tarefa_concluida',
                    content=f"Concluiu a tarefa: {task.title}",
                    created_at=datetime.now()
                )
                db.session.add(interaction)

        else:
            task.status = 'pendente'
            task.completed_at = None
            
        db.session.commit()
        
        # Redirect back to where we came from (tasks list or lead details)
        return redirect(request.referrer or url_for('main.tasks'))

    @main.route('/tasks/<int:id>/delete', methods=['POST'])
    @login_required
    def delete_task(id):
        if current_user.role != 'admin':
            flash('Apenas administradores podem excluir tarefas.', 'error')
            return redirect(request.referrer or url_for('main.tasks'))
            
        task = Task.query.get_or_404(id)
        if task.company_id != current_user.company_id:
            return "Unauthorized", 403
            
        db.session.delete(task)
        db.session.commit()
        flash('Tarefa excluída.', 'success')
        return redirect(request.referrer or url_for('main.tasks'))

    @main.route('/leads/<int:id>/move/<direction>', methods=['POST'])
    @login_required
    def move_lead(id, direction):
        lead = Lead.query.get_or_404(id)
        if lead.company_id != current_user.company_id:
            return "Unauthorized", 403
            
        # Get stages for this lead's pipeline
        if not lead.pipeline_id:
             # Fallback/Error state
             return redirect(url_for('main.pipeline'))

        stages = PipelineStage.query.filter_by(pipeline_id=lead.pipeline_id).order_by(PipelineStage.order).all()
        current_stage_index = next((i for i, s in enumerate(stages) if s.id == lead.pipeline_stage_id), -1)
        
        if current_stage_index != -1:
            new_index = current_stage_index + 1 if direction == 'next' else current_stage_index - 1
            if 0 <= new_index < len(stages):
                lead.pipeline_stage_id = stages[new_index].id
                db.session.commit()
                
        return redirect(url_for('main.pipeline', pipeline_id=lead.pipeline_id))

    @main.route('/leads/<int:id>/convert', methods=['POST'])
    @login_required
    def convert_lead(id):
        lead = Lead.query.get_or_404(id)
        if lead.company_id != current_user.company_id:
            return "Unauthorized", 403
            
        # Parse Form Data
        service = request.form.get('service')
        contract_type = request.form.get('contract_type')
        start_date_str = request.form.get('start_date')
        
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else datetime.utcnow().date()
        renewal_date = start_date + timedelta(days=30)
        
        # Parse Value
        monthly_value = request.form.get('monthly_value')
        try:
            if monthly_value:
                clean_value = monthly_value.replace('R$', '').replace('.', '').replace(',', '.').strip()
                value = float(clean_value)
            else:
                value = 0.0
        except ValueError:
            value = 0.0

        # Create Client
        client = Client(
            name=lead.name,
            email=lead.email,
            phone=lead.phone,
            company_id=lead.company_id,
            account_manager_id=lead.assigned_to_id or current_user.id, # Keep relation
            lead_id=lead.id,
            status='onboarding',
            health_status='verde',
            service=service,
            contract_type=contract_type,
            monthly_value=value,
            start_date=start_date,
            renewal_date=renewal_date,
            notes=f"Convertido de Lead em {start_date.strftime('%d/%m/%Y')}. \n{lead.notes or ''}",
            niche=lead.bant_need,
            address_street="", 
            address_city=""
        )
        
        db.session.add(client)
        db.session.flush() # Get ID
        
        # Update Lead
        lead.status = LEAD_STATUS_WON
        lead.client_id = client.id
        
        # Move lead to "Fechado" stage if exists
        fechado_stage = PipelineStage.query.filter(
            PipelineStage.pipeline_id == lead.pipeline_id,
            PipelineStage.company_id == current_user.company_id,
            PipelineStage.name.ilike('%fechado%')
        ).first()
        
        if fechado_stage:
            lead.pipeline_stage_id = fechado_stage.id
            
        # 1. Create Onboarding Checklist
        template = ProcessTemplate.query.filter_by(company_id=current_user.company_id, name="Onboarding Padrão").first()
        
        checklist_data = []
        if template:
            checklist_data = template.steps
        else:
            checklist_data = [{
                "title": "Start",
                "items": [
                    {"text": "Enviar Welcome Kit", "done": False},
                    {"text": "Solicitar Acessos", "done": False},
                    {"text": "Agendar Kickoff", "done": False},
                    {"text": "Criar Pasta no Drive", "done": False}
                ]
            }]
            
        checklist = ClientChecklist(
            client_id=client.id,
            company_id=current_user.company_id,
            name="Onboarding Inicial",
            progress=checklist_data
        )
        db.session.add(checklist)
        
        # 2. auto-create Tasks (Contract)
        task_create = Task(
            title="Criar Contrato",
            description=f"Gerar/Emitir contrato para {client.name}.",
            due_date=datetime.utcnow() + timedelta(days=1),
            priority='alta',
            status='pendente',
            client_id=client.id,
            assigned_to_id=client.account_manager_id,
            company_id=client.company_id
        )
        db.session.add(task_create)

        # 3. Notify
        if client.account_manager_id and client.account_manager_id != current_user.id:
            create_notification(
                user_id=client.account_manager_id,
                company_id=current_user.company_id,
                type='lead_converted',
                title='Lead Convertido',
                message=f"Lead {lead.name} convertido e atribuído a você."
            )
        
        # 4. Migrate WhatsApp Messages (History)
        # Update messages currently attached to this lead to point to the new client
        WhatsAppMessage.query.filter_by(lead_id=lead.id).update({'client_id': client.id, 'lead_id': None})
        
        db.session.commit()
        flash(f'Parabéns! {client.name} agora é um cliente ativo.', 'success')
        return redirect(url_for('main.client_details', id=client.id))

    @main.route('/leads/<int:id>/update_bant', methods=['POST'])
    @login_required
    def update_bant(id):
        lead = Lead.query.get_or_404(id)
        if lead.company_id != current_user.company_id:
             return "Unauthorized", 403
             
        lead.bant_budget = request.form.get('bant_budget')
        lead.bant_authority = request.form.get('bant_authority')
        lead.bant_timeline = request.form.get('bant_timeline')
        lead.bant_need = request.form.get('bant_need')
        
        # Log interaction for update
        interaction = Interaction(
             lead_id=lead.id,
             user_id=current_user.id,
             type='ajuste',
             content="Atualizou qualificação BANT",
             created_at=datetime.utcnow()
        )
        db.session.add(interaction)
        
        db.session.commit()
        flash('Qualificação atualizada.', 'success')
        return redirect(request.referrer)

    @main.route('/leads/<int:id>', methods=['GET', 'POST'])
    @login_required
    def lead_details(id):
        lead = Lead.query.get_or_404(id)
        if lead.company_id != current_user.company_id:
            return "Unauthorized", 403

        if request.method == 'POST':
            content = request.form.get('content')
            
            interaction = Interaction(
                lead_id=lead.id,
                type='nota',
                content=content,
                created_at=datetime.utcnow()
            )
            db.session.add(interaction)
            db.session.commit()
            flash('Nota adicionada!', 'success')
            return redirect(url_for('main.lead_details', id=id))
            
        return render_template('lead_details.html', lead=lead, now=datetime.utcnow())



    @main.route('/clients/<int:id>/delete', methods=['POST'])
    @login_required
    def delete_client(id):
        if current_user.role not in ['admin', 'manager']:
            return "Unauthorized", 403
            
        client = Client.query.get_or_404(id)
        if client.company_id != current_user.company_id:
            return "Unauthorized", 403
            
        # Optional: Cascade delete tasks/interactions or keep them?
        # For now, let's just delete the client, SQLAlchemy cascade should handle if configured, 
        # but let's be safe and just delete.
        db.session.delete(client)
        db.session.commit()
        
        flash('Cliente excluído com sucesso.', 'success')
        return redirect(url_for('main.clients'))

    @main.route('/clients')
    @login_required
    def clients():
        query = Client.query.filter_by(company_id=current_user.company_id)
        
        # Filters
        status = request.args.get('status')
        manager_id = request.args.get('manager')
        renewal_start = request.args.get('renewal_start')
        renewal_end = request.args.get('renewal_end')
        
        if status:
            query = query.filter_by(status=status)
            
        if manager_id:
            query = query.filter_by(account_manager_id=int(manager_id))
            
        if renewal_start:
            start_date = datetime.strptime(renewal_start, '%Y-%m-%d').date()
            query = query.filter(Client.renewal_date >= start_date)
            
        if renewal_end:
            end_date = datetime.strptime(renewal_end, '%Y-%m-%d').date()
            query = query.filter(Client.renewal_date <= end_date)
            
        # Eager load for performance
        clients = query.options(
            db.joinedload(Client.account_manager),
            db.joinedload(Client.interactions)
        ).order_by(Client.created_at.desc()).all()
        
        # Auto-update health
        for client in clients:
            update_client_health(client)
        
        db.session.commit() # Commit all changes at once
            
        users = User.query.filter_by(company_id=current_user.company_id).all()
        
        return render_template('clients.html', clients=clients, users=users, today=date.today())

    @main.route('/clients/<int:id>', methods=['GET'])
    @login_required
    def client_details(id):
        client = Client.query.get_or_404(id)
        if client.company_id != current_user.company_id:
            return "Unauthorized", 403
            
        # Auto-update health
        update_client_health(client)
            
        users = User.query.filter_by(company_id=current_user.company_id).all()
        process_templates = ProcessTemplate.query.filter_by(company_id=current_user.company_id).all()
        
        return render_template('client_details.html', 
                             client=client, 
                             users=users, 
                             process_templates=process_templates,
                             now=datetime.utcnow(), 
                             today=date.today())

    @main.route('/profile', methods=['GET', 'POST'])
    @login_required
    def profile():
        if request.method == 'POST':
            # Update basic info
            current_user.phone = request.form.get('phone')
            current_user.status_message = request.form.get('status_message')
            
            # Handle photo upload
            if 'profile_image' in request.files:
                file = request.files['profile_image']
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(f"user_{current_user.id}_{file.filename}")
                    
                    # Ensure directory exists
                    upload_path = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
                    os.makedirs(upload_path, exist_ok=True)
                    
                    file.save(os.path.join(upload_path, filename))
                    current_user.profile_image = filename
            
            # Change Password (Optional)
            new_password = request.form.get('new_password')
            if new_password:
                current_user.password_hash = generate_password_hash(new_password)
                
            db.session.commit()
            flash('Perfil atualizado com sucesso!', 'success')
            return redirect(url_for('main.profile'))
            
        return render_template('profile.html', user=current_user)

    @main.route('/clients/<int:id>/update', methods=['POST'])
    @login_required
    def update_client(id):
        client = Client.query.get_or_404(id)
        if client.company_id != current_user.company_id:
             return "Unauthorized", 403
             
        # Basic fields
        client.service = request.form.get('service')
        client.contract_type = request.form.get('contract_type')
        client.niche = request.form.get('niche') # Capture Niche

        # Registration Data (New Fields)
        client.document = request.form.get('document')
        client.email_contact = request.form.get('email_contact')
        client.representative = request.form.get('representative')
        client.representative_cpf = request.form.get('representative_cpf')
        
        client.address_street = request.form.get('address_street')
        client.address_number = request.form.get('address_number')
        client.address_neighborhood = request.form.get('address_neighborhood')
        client.address_city = request.form.get('address_city')
        client.address_state = request.form.get('address_state')
        client.address_zip = request.form.get('address_zip')
        
        new_status = request.form.get('status')
        if new_status and new_status != client.status:
            client.status = new_status
            
            # NOTIFICATION: Lifecycle Status Changed
            if client.account_manager_id and client.account_manager_id != current_user.id:
                 create_notification(
                     user_id=client.account_manager_id,
                     company_id=current_user.company_id,
                     type='client_status_changed',
                     title='Status do Cliente Alterado',
                     message=f"Status do cliente {client.name} alterado para {new_status} por {current_user.name}."
                 )
        
        # client.health_status = request.form.get('health_status') # Automated now
        client.notes = request.form.get('notes')
        
        # Manager
        manager_id = request.form.get('account_manager_id')
        if manager_id:
            client.account_manager_id = int(manager_id)
            
        # Values
        monthly_value = request.form.get('monthly_value')
        try:
            client.monthly_value = float(monthly_value) if monthly_value else 0.0
        except ValueError:
            pass # Keep old or ignore error for now
            
        # Dates
        start_date = request.form.get('start_date')
        if start_date:
            client.start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            
        renewal_date = request.form.get('renewal_date')
        if renewal_date:
            client.renewal_date = datetime.strptime(renewal_date, '%Y-%m-%d').date()
        else:
            client.renewal_date = None

        db.session.commit()
        flash('Dados do cliente atualizados!', 'success')
        return redirect(url_for('main.client_details', id=client.id))

    @main.route('/clients/<int:id>/interactions', methods=['POST'])
    @login_required
    def add_client_interaction(id):
        client = Client.query.get_or_404(id)
        if client.company_id != current_user.company_id:
            return "Unauthorized", 403
            
        type = request.form.get('type')
        content = request.form.get('content')
        
        interaction = Interaction(
            client_id=client.id,
            user_id=current_user.id,
            type=type,
            content=content,
            created_at=datetime.now()
        )
        db.session.add(interaction)
        db.session.commit()
        
        flash('Interação registrada!', 'success')
        return redirect(url_for('main.client_details', id=client.id))

    @main.route('/clients/<int:id>/tasks', methods=['POST'])
    @login_required
    def add_client_task(id):
        client = Client.query.get_or_404(id)
        if client.company_id != current_user.company_id:
             return "Unauthorized", 403
             
        title = request.form.get('title')
        due_date_str = request.form.get('due_date')
        responsible_id = request.form.get('responsible_id')
        is_recurring = True if request.form.get('is_recurring') else False
        
        due_date = None
        if due_date_str:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
            
        task = Task(
            title=title,
            due_date=due_date,
            client_id=client.id,
            company_id=client.company_id,
            assigned_to_id=int(responsible_id) if responsible_id else current_user.id,
            is_recurring=is_recurring,
            recurrence='mensal' if is_recurring else None
        )
        
        db.session.add(task)
        
        # Log Interaction
        interaction = Interaction(
            client_id=client.id,
            user_id=current_user.id,
            type='tarefa_criada',
            content=f"Criou a tarefa: {title}",
            created_at=datetime.now()
        )
        db.session.add(interaction)
        
        db.session.commit()
        
        flash('Tarefa adicionada!', 'success')
    # --- ADMIN ROUTES ---
    @main.route('/admin/users')
    @login_required
    def admin_users():
        return redirect(url_for('main.settings_team'))

    @main.route('/admin/users/new', methods=['GET', 'POST'])
    @login_required
    def admin_new_user():
        if current_user.role != ROLE_ADMIN:
             return "Acesso negado", 403

        pipelines = Pipeline.query.filter_by(company_id=current_user.company_id).all()
        roles = Role.query.filter_by(company_id=current_user.company_id).all()

        if request.method == 'POST':
            name = request.form.get('name')
            email = request.form.get('email')
            password = request.form.get('password')
            role_id = request.form.get('role_id') # Changed from 'role' to 'role_id'
            allowed_pipeline_ids = request.form.getlist('pipelines') # List of IDs
            
            existing = User.query.filter_by(email=email).first()
            if existing:
                flash('Email já cadastrado', 'error')
            else:
                # Find the Role Object
                selected_role = Role.query.get(role_id) if role_id else None
                legacy_role_name = selected_role.name if selected_role else ROLE_SALES # Fallback
                
                # Mapping simple names for legacy column if needed (e.g. 'Vendedor' -> 'vendedor')
                # But typically we just store 'Vendedor' now. Or we can normalize.
                # Let's trust the Role.name is what we want, or lowercase it if your legacy code expects lowercase.
                # Looking at models.py, constants are 'vendedor', 'gestor', 'admin'. 
                # Ideally Role names in DB matches these or we Map them.
                # For now, let's just save the name.
                
                user = User(
                    name=name,
                    email=email,
                    password_hash=generate_password_hash(password),
                    role=legacy_role_name, # Legacy Field
                    role_id=selected_role.id if selected_role else None, # New Field
                    company_id=current_user.company_id
                )
                
                # Add pipeline access
                for pid in allowed_pipeline_ids:
                    p = Pipeline.query.get(int(pid))
                    if p:
                        user.allowed_pipelines.append(p)

                db.session.add(user)
                db.session.commit()
                flash('Usuário criado com sucesso!', 'success')
                return redirect(url_for('main.settings_team'))
        
        return render_template('admin_user_form.html', pipelines=pipelines, roles=roles, user=None)

    @main.route('/admin/users/<int:id>/edit', methods=['GET', 'POST'])
    @login_required
    def admin_edit_user(id):
        if current_user.role != ROLE_ADMIN:
             return "Acesso negado", 403
            
        user = User.query.get_or_404(id)
        if user.company_id != current_user.company_id:
             return "Unauthorized", 403
             
        pipelines = Pipeline.query.filter_by(company_id=current_user.company_id).all()
        roles = Role.query.filter_by(company_id=current_user.company_id).all()

        if request.method == 'POST':
            user.name = request.form.get('name')
            
            role_id = request.form.get('role_id')
            selected_role = Role.query.get(role_id) if role_id else None
            
            if selected_role:
                user.role_id = selected_role.id
                user.role = selected_role.name # Legacy sync
            
            # Update password if provided
            password = request.form.get('password')
            if password:
                user.password_hash = generate_password_hash(password)
                
            # Update pipelines
            allowed_pipeline_ids = request.form.getlist('pipelines')
            user.allowed_pipelines = [] # Reset
            for pid in allowed_pipeline_ids:
                p = Pipeline.query.get(int(pid))
                if p:
                    user.allowed_pipelines.append(p)
            
            db.session.commit()
            flash('Usuário atualizado!', 'success')
            return redirect(url_for('main.settings_team'))

        return render_template('admin_user_form.html', pipelines=pipelines, roles=roles, user=user)

    @main.route('/init_db')
    def init_db():
        """Helper to initialize DB and create test data"""
        with app.app_context():
            db.create_all()
            
            # Create default company and user if not exists
            if not Company.query.first():
                company = Company(name='NorthWay')
                db.session.add(company)
                db.session.commit()
                
                # Create Default Pipeline
                pipeline_vendas = Pipeline(name='Vendas B2B', company_id=company.id)
                db.session.add(pipeline_vendas)
                db.session.commit()

                # Default admin
                admin = User(
                    name='Admin User',
                    email='admin@northway.com',
                    password_hash=generate_password_hash('123456'),
                    role=ROLE_ADMIN,
                    company_id=company.id
                )
                admin.allowed_pipelines.append(pipeline_vendas) # Admin sees all
                db.session.add(admin)
                
                # Default stages
                stages = ['Novo', 'Qualificação', 'Proposta', 'Negociação', 'Fechado']
                for i, name in enumerate(stages):
                    stage = PipelineStage(name=name, order=i, company_id=company.id, pipeline_id=pipeline_vendas.id)
                    db.session.add(stage)
                
                db.session.commit()
                return "Database initialized with default data!"
            return "Database already initialized."

    @main.route('/init_roles')
    def init_roles():
        """Helper to seed roles for existing companies"""
        companies = Company.query.all()
        created_count = 0
        updated_users = 0
        
        for company in companies:
            # Check/Create Roles
            roles_map = {}
            default_roles = ['Administrador', 'Gestor', 'Vendedor']
            
            for role_name in default_roles:
                role = Role.query.filter_by(company_id=company.id, name=role_name).first()
                if not role:
                    role = Role(name=role_name, company_id=company.id, permissions=[])
                    db.session.add(role)
                    created_count += 1
                roles_map[role_name] = role
            
            db.session.commit()
            
            # Backfill Users
            users = User.query.filter_by(company_id=company.id).all()
            for user in users:
                if not user.role_id:
                    # Map legacy strings to new Role objects
                    target_role = None
                    if user.role == 'admin': target_role = roles_map.get('Administrador')
                    elif user.role == 'gestor': target_role = roles_map.get('Gestor')
                    elif user.role == 'vendedor': target_role = roles_map.get('Vendedor')
                    
                    if target_role:
                        user.role_id = target_role.id
                        updated_users += 1
                        
            db.session.commit()
            
        return f"Roles Initialized: {created_count} roles created, {updated_users} users updated."

    @main.route('/api/notifications')
    @login_required
    def get_notifications():
        # Lazy check for due tasks
        now = datetime.now()
        limit_time = now + timedelta(minutes=15)
        
        tasks_to_notify = Task.query.filter(
            Task.assigned_to_id == current_user.id,
            Task.status == 'pendente',
            Task.reminder_sent == False,
            Task.due_date != None,
            Task.due_date <= limit_time
        ).all()
        
        for task in tasks_to_notify:
             create_notification(
                 user_id=current_user.id,
                 company_id=current_user.company_id,
                 type='task_due',
                 title='Tarefa Próxima do Prazo',
                 message=f"A tarefa '{task.title}' vence em breve ({task.due_date.strftime('%H:%M')})."
             )
             task.reminder_sent = True
        
        if tasks_to_notify:
            db.session.commit()
            
        notifications = Notification.query.filter_by(
            user_id=current_user.id, 
            company_id=current_user.company_id
        ).order_by(Notification.created_at.desc()).limit(20).all()
        
        data = [{
            'id': n.id,
            'type': n.type,
            'title': n.title,
            'message': n.message,
            'read': n.read,
            'created_at': n.created_at.strftime('%d/%m %H:%M')
        } for n in notifications]
        
        unread_count = Notification.query.filter_by(
            user_id=current_user.id, 
            company_id=current_user.company_id, 
            read=False
        ).count()
        
        return jsonify({'notifications': data, 'unread_count': unread_count})

    @main.route('/api/notifications/<int:id>/read', methods=['POST'])
    @login_required
    def mark_notification_read(id):
        notification = Notification.query.get_or_404(id)
        if notification.user_id != current_user.id:
            return "Unauthorized", 403
        notification.read = True
        db.session.commit()
        return jsonify({'success': True})

    @main.route('/api/notifications/read-all', methods=['POST'])
    @login_required
    def mark_all_read():
        Notification.query.filter_by(user_id=current_user.id, read=False).update({'read': True})
        db.session.commit()
        return jsonify({'success': True})


    @main.route('/api/dashboard/chart-data')
    @login_required
    def get_chart_data():
        period = request.args.get('period', 'monthly')
        now = datetime.now()
        company_id = current_user.company_id
        
        # Determine start date and label format
        if period == 'today':
            start_date = datetime(now.year, now.month, now.day) # Midnight today
            date_format = '%H:00'
            delta_step = timedelta(hours=1)
        elif period == 'daily':
            start_date = now - timedelta(days=30)
            date_format = '%d/%m' # 01/01
            delta_step = timedelta(days=1)
        elif period == 'weekly':
            start_date = now - timedelta(weeks=12)
            date_format = 'Semana %W' 
            delta_step = timedelta(weeks=1)
        elif period == 'monthly':
            start_date = now - timedelta(days=365) # Last 12 months
            date_format = '%b %y' # Jan 23
        elif period == 'bimonthly':
            start_date = now - timedelta(days=365*2) # Last 2 years approx
            date_format = '%b %y'
        elif period == 'quarterly':
            start_date = now - timedelta(days=365*2) # Last 2 years
            date_format = 'Q%q %Y' # Custom logic needed for Quadrimester? No Quartile.
        elif period == 'semiannual':
            start_date = now - timedelta(days=365*3)
            date_format = '%Y-%m' 
        elif period == 'annual':
            start_date = now - timedelta(days=365*5)
            date_format = '%Y'
        else:
            # Default Monthly
            start_date = now - timedelta(days=180)
            date_format = '%b'

        # Fetch Data
        leads = Lead.query.filter(Lead.company_id == company_id, Lead.created_at >= start_date).all()
        clients = Client.query.filter(Client.company_id == company_id, Client.created_at >= start_date).all()

        # Aggregation Logic
        # We use a dictionary to bucket data: bucket_key -> {leads: 0, sales: 0}
        data_buckets = {}
        
        # Pre-fill buckets to ensure continuous line (optional but good for charts)
        # For simplicity in this iteration, we allow dynamic sparse keys and correct sorting.
        
        def get_bucket_key(date_obj, period):
            if period == 'today':
                return date_obj.strftime('%Y-%m-%d-%H'), date_obj.strftime('%H:00')
            elif period == 'daily':
                return date_obj.strftime('%Y-%m-%d'), date_obj.strftime('%d/%m')
            elif period == 'weekly':
                # Year + Week number
                return date_obj.strftime('%Y-%W'), f"Sem {date_obj.strftime('%W')}"
            elif period == 'monthly':
                return date_obj.strftime('%Y-%m'), date_obj.strftime('%b')
            elif period == 'bimonthly':
                # Group 1-2, 3-4, etc.
                month = date_obj.month
                bi = (month + 1) // 2
                return f"{date_obj.year}-{bi}", f"{bi}º Bim {date_obj.strftime('%y')}"
            elif period == 'quarterly':
                quarter = (date_obj.month - 1) // 3 + 1
                return f"{date_obj.year}-Q{quarter}", f"Q{quarter} {date_obj.year}"
            elif period == 'semiannual':
                semi = 1 if date_obj.month <= 6 else 2
                return f"{date_obj.year}-S{semi}", f"S{semi} {date_obj.year}"
            elif period == 'annual':
                return date_obj.strftime('%Y'), date_obj.strftime('%Y')
            return date_obj.strftime('%Y-%m'), date_obj.strftime('%b')

        # Process Leads
        for l in leads:
            sort_key, label = get_bucket_key(l.created_at, period)
            if sort_key not in data_buckets:
                data_buckets[sort_key] = {'label': label, 'leads': 0, 'sales': 0}
            data_buckets[sort_key]['leads'] += 1
            
        # Process Sales (Clients)
        for c in clients:
            sort_key, label = get_bucket_key(c.created_at, period)
            if sort_key not in data_buckets:
                data_buckets[sort_key] = {'label': label, 'leads': 0, 'sales': 0}
            data_buckets[sort_key]['sales'] += 1
            
        # Sort by key (chronological)
        sorted_keys = sorted(data_buckets.keys())
        
        labels = [data_buckets[k]['label'] for k in sorted_keys]
        leads_data = [data_buckets[k]['leads'] for k in sorted_keys]
        sales_data = [data_buckets[k]['sales'] for k in sorted_keys]
        
        return jsonify({
            'labels': labels,
            'leads': leads_data,
            'sales': sales_data
        })



    # ==========================
    # CONTRACTS ROUTES
    # ==========================
    
    @main.route('/clients/<int:id>/contracts/new')
    @login_required
    def new_contract(id):
        client = Client.query.get_or_404(id)
        if client.company_id != current_user.company_id:
            abort(403)
            
        templates = ContractTemplate.query.filter_by(company_id=current_user.company_id, active=True, type='contract').all()
        attachments = ContractTemplate.query.filter_by(company_id=current_user.company_id, active=True, type='attachment').all()
        
        # Determine fallback default templates if none exist (for UI safety)
        if not templates:
            # Fallback to any active if types not set correctly? 
            # Or just show empty.
            pass

        return render_template('contracts/new_contract.html', client=client, templates=templates, attachments=attachments)


    def get_contract_replacements(client, form_data):
        """Helper to build the replacements dictionary for contracts."""
        try:
            current_user_name = current_user.name
        except:
            current_user_name = "Sistema"
            
        # Parse Foro into Comarca/Estado if possible
        cidade_foro = form_data.get('cidade_foro', 'São Paulo - SP')
        if '-' in cidade_foro:
            foro_parts = cidade_foro.split('-')
        elif '/' in cidade_foro:
            foro_parts = cidade_foro.split('/')
        else:
            foro_parts = [cidade_foro, '']
            
        if len(foro_parts) >= 2:
            foro_comarca = foro_parts[0].strip()
            foro_estado = foro_parts[1].strip()
        else:
            foro_comarca = cidade_foro.strip()
            foro_estado = ''

        def format_addr(obj):
            parts = []
            if obj.address_street: parts.append(f"{obj.address_street}")
            if obj.address_number: parts.append(f"nº {obj.address_number}")
            if obj.address_neighborhood: parts.append(f"- {obj.address_neighborhood}")
            if obj.address_city and obj.address_state: parts.append(f"- {obj.address_city}/{obj.address_state}")
            elif obj.address_city: parts.append(f"- {obj.address_city}")
            if obj.address_zip: parts.append(f"CEP: {obj.address_zip}")
            return " ".join(parts) if parts else "Endereço não informado"

        replacements = {
            # --- CONTRATANTE (CLIENTE) ---
            '{{CONTRATANTE_NOME_EMPRESARIAL}}': form_data.get('contratante_nome') or client.name,
            '{{CONTRATANTE_NOME}}': form_data.get('contratante_nome') or client.name, # Alias
            
            '{{CONTRATANTE_DOCUMENTO}}': form_data.get('contratante_documento') or client.document or 'N/A',
            '{{CONTRATANTE_CNPJ}}': form_data.get('contratante_documento') or client.document or 'N/A', # Alias
            '{{CONTRATANTE_CPF}}': form_data.get('contratante_cpf') or client.representative_cpf or '', # Rep CPF usually, or Client CPF if PF
            
            '{{CONTRATANTE_ENDERECO}}': form_data.get('contratante_endereco') or format_addr(client),
            '{{CONTRATANTE_EMAIL}}': client.email,
            '{{CONTRATANTE_TELEFONE}}': client.phone,
            
            '{{CONTRATANTE_REPRESENTANTE}}': form_data.get('contratante_representante') or client.representative or '',
            '{{CONTRATANTE_REPRESENTANTE_LEGAL}}': form_data.get('contratante_representante') or client.representative or '', # Alias
            
            '{{CONTRATANTE_CPF_REPRESENTANTE}}': form_data.get('contratante_cpf') or client.representative_cpf or '',
            '{{CONTRATANTE_ENDERECO_REPRESENTANTE}}': form_data.get('contratante_endereco_representante') or '',

            # --- English Aliases (Standard) ---
            '{{COMPANY_NAME}}': client.company.name,
            '{{CLIENT_NAME}}': form_data.get('contratante_nome') or client.name,
            '{{VALUE}}': form_data.get('valor_total', '0,00'),

            # --- CONTRATADA (EMPRESA DO USUÁRIO) ---
            '{{CONTRATADA_NOME_EMPRESARIAL}}': client.company.name,
            '{{CONTRATADA_DOCUMENTO}}': client.company.document,
            '{{CONTRATADA_CNPJ}}': client.company.document, # Alias
            '{{CONTRATADA_ENDERECO}}': format_addr(client.company),
            '{{CONTRATADA_EMAIL}}': getattr(client.company, 'email', None) or current_user.email,
            '{{CONTRATADA_TELEFONE}}': getattr(client.company, 'phone', ''),
            
            # Using Company Settings for Legal Representative (instead of logged-in user)
            '{{CONTRATADA_REPRESENTANTE}}': getattr(client.company, 'representative', '') or current_user.name,
            '{{CONTRATADA_REPRESENTANTE_LEGAL}}': getattr(client.company, 'representative', '') or current_user.name, # Alias
            '{{CONTRATADA_CPF}}': getattr(client.company, 'representative_cpf', '') or '', 

            # --- VALORES E PAGAMENTO ---
            '{{VALOR_TOTAL_CONTRATO}}': form_data.get('valor_total', '0,00'),
            '{{VALOR_TOTAL}}': form_data.get('valor_total', '0,00'),
            '{{VALOR_IMPLANTACAO}}': form_data.get('valor_implantacao', '0,00'),
            '{{VALOR_PARCELA}}': form_data.get('valor_parcela', '0,00'),
            '{{VALOR_MENSAL}}': form_data.get('valor_parcela', '0,00'),
            '{{NUMERO_PARCELAS}}': form_data.get('qtd_parcelas', '12'),
            '{{QTD_PARCELAS}}': form_data.get('qtd_parcelas', '12'),
            '{{DIA_VENCIMENTO}}': form_data.get('dia_vencimento', '5'),
            
            # --- TRAFEGO ---
            '{{VALOR_MINIMO_TRAFEGO}}': form_data.get('valor_minimo_trafego', '0,00'),
            '{{VALOR_MINIMO_TRÁFEGO}}': form_data.get('valor_minimo_trafego', '0,00'), # User Alias
            '{{PERIODO_TRAFEGO}}': form_data.get('periodo_trafego', '30 dias'),
            '{{PERIODO_TRÁFEGO}}': form_data.get('periodo_trafego', '30 dias'), # User Alias

            # --- DATAS E VIGÊNCIA ---
            '{{DATA_INICIO}}': form_data.get('data_inicio', date.today().strftime('%d/%m/%Y')),
            '{{VIGENCIA_MESES}}': form_data.get('vigencia_meses', '12'),
            '{{DATA_FIM}}': form_data.get('data_fim', ''),
            '{{DATA_FINAL}}': form_data.get('data_fim', ''), # Alias
            '{{DATA_TERMINO}}': form_data.get('data_fim', ''), # User Alias
            '{{DATA_PROPOSTA}}': form_data.get('data_proposta', date.today().strftime('%d/%m/%Y')),
            '{{VALIDADE_PROPOSTA}}': '15 dias',

            # --- LOCAL E ASSINATURA ---
            '{{CIDADE_FORO}}': form_data.get('cidade_foro', 'São Paulo - SP'),
            '{{FORO_COMARCA}}': foro_comarca,
            '{{FORO_ESTADO}}': foro_estado,
            '{{CIDADE_ASSINATURA}}': form_data.get('cidade_assinatura', 'São Paulo'),
            '{{DATA_ASSINATURA}}': form_data.get('data_assinatura', date.today().strftime('%d/%m/%Y')),
            '{{NUMERO_VIAS}}': form_data.get('numero_vias', '2'),
            
            # --- ASSINATURAS ---
            '{{CONTRATANTE_ASSINATURA_NOME}}': form_data.get('contratante_representante') or client.representative or client.name,
            '{{CONTRATADA_ASSINATURA_NOME}}': getattr(client.company, 'representative', '') or client.company.name,
            
            # --- ENDEREÇO REPRESENTANTE CONTRATADA (USER) ---
            # User model doesn't have home address, defaulting to company or empty string to match user expectation
            '{{CONTRATADA_ENDERECO_REPRESENTANTE}}': format_addr(client.company), 

            # --- TESTEMUNHAS ---
            '{{TESTEMUNHA1_NOME}}': form_data.get('testemunha1_nome', ''),
            '{{TESTEMUNHA1_CPF}}': form_data.get('testemunha1_cpf', ''),
            '{{TESTEMUNHA2_NOME}}': form_data.get('testemunha2_nome', ''),
            '{{TESTEMUNHA2_CPF}}': form_data.get('testemunha2_cpf', ''),
        }
        return replacements
        client_full_address = format_addr(client)
        company_full_address = format_addr(client.company)

        return {
            # --- UPPERCASE VARIATIONS (User Preference) ---
            '{{CONTRATANTE_NOME_EMPRESARIAL}}': form_data.get('contratante_nome', client.name),
            '{{CONTRATANTE_CNPJ}}': form_data.get('contratante_documento', client.document or 'não informado'),
            '{{CONTRATANTE_DOCUMENTO}}': form_data.get('contratante_documento', client.document or 'não informado'),
            
            # Composite Address (Legacy)
            '{{CONTRATANTE_ENDERECO}}': form_data.get('contratante_endereco', client_full_address),
            
            # Split Address Fields
            '{{CONTRATANTE_RUA}}': client.address_street or '',
            '{{CONTRATANTE_NUMERO}}': client.address_number or '',
            '{{CONTRATANTE_BAIRRO}}': client.address_neighborhood or '',
            '{{CONTRATANTE_CIDADE}}': client.address_city or '',
            '{{CONTRATANTE_ESTADO}}': client.address_state or '',
            '{{CONTRATANTE_CEP}}': client.address_zip or '',

            '{{CONTRATANTE_REPRESENTANTE}}': form_data.get('contratante_representante', client.representative or 'não informado'),
            '{{CONTRATANTE_REPRESENTANTE_LEGAL}}': form_data.get('contratante_representante', client.representative or 'não informado'),
            '{{CONTRATANTE_CPF}}': form_data.get('contratante_cpf', client.representative_cpf or 'não informado'),
            '{{CONTRATANTE_EMAIL}}': form_data.get('contratante_email', client.email_contact or client.email or 'não informado'),
            '{{CONTRATANTE_TELEFONE}}': form_data.get('contratante_telefone', client.phone or 'não informado'),

            '{{CONTRATADA_NOME_EMPRESARIAL}}': client.company.name,
            '{{CONTRATADA_CNPJ}}': client.company.document or '00.000.000/0001-00',
            '{{CONTRATADA_DOCUMENTO}}': client.company.document or '00.000.000/0001-00',
            
            # Composite Address (Legacy)
            '{{CONTRATADA_ENDERECO}}': company_full_address,
            
            # Split Address Fields
            '{{CONTRATADA_RUA}}': client.company.address_street or '',
            '{{CONTRATADA_NUMERO}}': client.company.address_number or '',
            '{{CONTRATADA_BAIRRO}}': client.company.address_neighborhood or '',
            '{{CONTRATADA_CIDADE}}': client.company.address_city or '',
            '{{CONTRATADA_ESTADO}}': client.company.address_state or '',
            '{{CONTRATADA_CEP}}': client.company.address_zip or '',

            '{{CONTRATADA_REPRESENTANTE}}': client.company.representative or current_user_name,
            '{{CONTRATADA_REPRESENTANTE_LEGAL}}': client.company.representative or current_user_name,
            '{{CONTRATADA_CPF}}': client.company.representative_cpf or '000.000.000-00',
            '{{CONTRATADA_ENDERECO_REPRESENTANTE}}': 'Endereço do Representante da Empresa', # Placeholder if not in DB, company usually doesn't have this specific field separate from address unless added. Using generic for now or blank.
            
            # --- Dynamic Contract Fields ---
            '{{VALOR_MINIMO_TRÁFEGO}}': form_data.get('valor_minimo_trafego', '0,00'),
            '{{VALOR_IMPLANTACAO}}': form_data.get('valor_implantacao', '0,00'),
            '{{PERIODO_TRAFEGO}}': form_data.get('periodo_trafego', '30 dias'),
            '{{DATA_PROPOSTA}}': form_data.get('data_proposta', datetime.now().strftime('%d/%m/%Y')),
            '{{DESCRIÇÃO_SERVIÇOS}}': form_data.get('descricao_servicos', 'Gestão de Tráfego Pago'),
            
            '{{NUMERO_VIAS}}': form_data.get('numero_vias', '2'),
            '{{FORO_COMARCA}}': foro_comarca,
            '{{FORO_ESTADO}}': foro_estado,
            
            '{{CIDADE_ASSINATURA}}': form_data.get('cidade_assinatura', foro_comarca),
            '{{DATA_ASSINATURA}}': form_data.get('data_assinatura', datetime.now().strftime('%d/%m/%Y')),
            
            '{{TESTEMUNHA1_NOME}}': form_data.get('testemunha1_nome', '______________________'),
            '{{TESTEMUNHA1_CPF}}': form_data.get('testemunha1_cpf', '___.___.___-__'),
            '{{TESTEMUNHA2_NOME}}': form_data.get('testemunha2_nome', '______________________'),
            '{{TESTEMUNHA2_CPF}}': form_data.get('testemunha2_cpf', '___.___.___-__'),

            '{{CONTRATANTE_ASSINATURA_NOME}}': form_data.get('contratante_nome', client.name),
            '{{CONTRATADA_ASSINATURA_NOME}}': client.company.name,

            # Additional Custom Fields (User requested)
            '{{CONTRATANTE_ENDERECO_REPRESENTANTE}}': form_data.get('contratante_endereco_representante', 'Endereço não informado'),
            
            # --- Legacy / Lowercase Support ---
            '{{contratante_nome_empresarial}}': form_data.get('contratante_nome', client.name),
            '{{contratante_cnpj}}': form_data.get('contratante_documento', client.document or 'não informado'),
            '{{contratante_endereco}}': form_data.get('contratante_endereco', client_full_address),
            '{{contratante_representante}}': form_data.get('contratante_representante', client.representative or 'não informado'),
            '{{contratante_cpf}}': form_data.get('contratante_cpf', client.representative_cpf or 'não informado'),
            '{{email_contratante}}': form_data.get('contratante_email', client.email_contact or client.email or 'não informado'),
            '{{telefone_contratante}}': form_data.get('contratante_telefone', client.phone or 'não informado'),

            '{{contratada_nome_empresarial}}': client.company.name,
            '{{contratada_cnpj}}': client.company.document or '00.000.000/0001-00',
            '{{contratada_endereco}}': company_full_address,
            '{{contratada_representante}}': client.company.representative or current_user_name,
            '{{contratada_cpf}}': client.company.representative_cpf or '000.000.000-00',
            
            '{{empresa_nome}}': client.company.name,
            '{{empresa_documento}}': client.company.document or '00.000.000/0001-00',
            '{{responsavel_nome}}': current_user_name,

            '{{data_contrato}}': datetime.now().strftime('%d/%m/%Y'),
            '{{data_inicio}}': form_data.get('data_inicio', datetime.now().strftime('%d/%m/%Y')),
            '{{data_fim}}': form_data.get('data_fim', (datetime.now() + timedelta(days=365)).strftime('%d/%m/%Y')),
            '{{DATA_TERMINO}}': form_data.get('data_fim', (datetime.now() + timedelta(days=365)).strftime('%d/%m/%Y')),
            '{{DATA_FINAL}}': form_data.get('data_fim', (datetime.now() + timedelta(days=365)).strftime('%d/%m/%Y')),
            '{{cidade_foro}}': form_data.get('cidade_foro', 'São Paulo/SP'),

            # --- Financial Uppercase Support ---
            '{{DATA_INICIO}}': form_data.get('data_inicio', datetime.now().strftime('%d/%m/%Y')),
            '{{VALOR_TOTAL_CONTRATO}}': form_data.get('valor_total', '0,00'),
            '{{VALOR_PARCELA}}': form_data.get('valor_parcela', '0,00'),
            '{{NUMERO_PARCELAS}}': form_data.get('qtd_parcelas', '12'), # Alias for NUMERO_PARCELAS
            '{{QTD_PARCELAS}}': form_data.get('qtd_parcelas', '12'),
            '{{DIA_VENCIMENTO}}': form_data.get('dia_vencimento', '5'),
            '{{FORMA_PAGAMENTO}}': form_data.get('forma_pagamento', 'Boleto Bancário'),

            '{{valor_total_contrato}}': form_data.get('valor_total', '0,00'),
            '{{valor_parcela}}': form_data.get('valor_parcela', '0,00'),
            '{{quantidade_parcelas}}': form_data.get('qtd_parcelas', '12'),
            '{{dia_vencimento}}': form_data.get('dia_vencimento', '5'),
            '{{forma_pagamento}}': form_data.get('forma_pagamento', 'Boleto Bancário'),
            
            '{{cliente_nome}}': client.name,
            '{{cliente_documento}}': client.document or 'não informado',
            '{{cliente_endereco}}': client_full_address or 'não informado',
        }
        
    @main.route('/api/contracts/preview', methods=['POST'])
    @login_required
    def preview_contract():
        data = request.json
        client_id = data.get('client_id')
        template_id = data.get('template_id')
        attachment_id = data.get('attachment_id')
        form_data = data.get('form_data', {}) # User overrides
        
        client = Client.query.get_or_404(client_id)
        template = ContractTemplate.query.get_or_404(template_id)
        
        if client.company_id != current_user.company_id:
            return jsonify({'error': 'Unauthorized'}), 403

        # Logic to split City/State and Replacements are handled by helper
        replacements = get_contract_replacements(client, form_data)
        
        # 1. Process Main Content
        content = template.content
        for key, value in replacements.items():
            content = content.replace(key, str(value))
        
        try:
            content = markdown.markdown(content)
        except Exception as e:
            print(f"Markdown Error: {e}")
            
        # 2. Process Attachment
        if attachment_id:
            attachment = ContractTemplate.query.get(attachment_id)
            if attachment and attachment.company_id == client.company_id:
                att_content = attachment.content
                # Apply replacements to attachment too
                for key, value in replacements.items():
                    att_content = att_content.replace(key, str(value))
                
                try:
                    att_content = markdown.markdown(att_content)
                except:
                    pass
                
                content += f"<br><hr><br><div class='attachment-section'>{att_content}</div>"

        # Inject Branded Header (For Preview Only)
        logo_html = ""
        if client.company.logo_filename:
            logo_url = url_for('static', filename='uploads/company/' + client.company.logo_filename)
            logo_html = f'<img src="{logo_url}" alt="Logo" class="h-16 object-contain">'
        
        primary_color = client.company.primary_color or '#fa0102'
        secondary_color = client.company.secondary_color or '#111827'
        
        header_html = f"""
        <div class="mb-8 border-b-2 pb-4" style="border-color: {primary_color}">
            <div class="flex items-center justify-between">
                <div>
                    <h2 class="text-2xl font-bold" style="color: {secondary_color}">{client.company.name}</h2>
                    <p class="text-sm text-gray-500">CNPJ: {client.company.document or ''}</p>
                </div>
                {logo_html}
            </div>
            <p class="text-xs text-gray-400 mt-2">Pré-visualização gerada em {datetime.now().strftime('%d/%m/%Y')}</p>
        </div>
        """
        
        final_content = header_html + content

        return jsonify({'content': final_content})

    @main.route('/clients/<int:id>/contracts', methods=['POST'])
    @login_required
    def create_contract(id):
        client = Client.query.get_or_404(id)
        if client.company_id != current_user.company_id:
            abort(403)
            
        try:
            action = request.form.get('action', 'issue')
            template_id = request.form.get('template_id')
            contract_id = request.form.get('contract_id')
            template = ContractTemplate.query.get_or_404(template_id)
            form_data = request.form.to_dict()
            # Prepare final content server-side to ensure Markdown conversion
            # Use Helper
            replacements = get_contract_replacements(client, form_data)
            
            # --- SYNC CLIENT DATA (Bug Fix) ---
            # Update client record with fresh data from the contract form
            user_wants_sync = True # Could be a checkbox, but default to True for consistency
            if user_wants_sync:
                if form_data.get('contratante_nome'):
                    client.name = form_data.get('contratante_nome')
                
                if form_data.get('contratante_documento'):
                    client.document = form_data.get('contratante_documento')
                
                if form_data.get('contratante_representante'):
                    client.representative = form_data.get('contratante_representante')
                    
                if form_data.get('contratante_cpf'):
                    client.representative_cpf = form_data.get('contratante_cpf')

                # Email & Address Sync
                if form_data.get('contratante_email'):
                     client.email_contact = form_data.get('contratante_email')
                     
                # Address Mapping (Contract Form -> Client Model)
                # Assuming contract form sends 'contratante_endereco' as a single string? NO.
                # We need to check what the contract form sends.
                # In new_contract.html, checking inputs...
                # The form has: contratante_endereco (single line fallback)
                # BUT it also has "Details" section: contratante_endereco (which is just one field).
                # WAIT. The user screenshot shows "Rua", "Bairro", etc. empty in Client Details.
                # Does the Contract Form HAVE separate address inputs?
                # Looking at new_contract.html: 
                # It has 'contratante_endereco' (single input).
                # It DOES NOT seems to have separate address inputs for the CLIENT EDIT section in the contract form.
                # It has 'contratante_endereco' placeholder="Endereço".
                
                # HOWEVER, the Client Model has separate fields.
                # If the contract form only provides a single "Endereço" string, we can at least save that to 'address_street' as a fallback or 'address_neighborhood' etc?
                # Or better, we should probably ENHANCE the contract form to have split address fields if we want to sync properly.
                # OR we try to parse it? Parsing is risky.
                
                # Let's check get_contract_replacements:
                # '{{CONTRATANTE_ENDERECO}}': form_data.get('contratante_endereco') or format_addr(client),
                
                # If the user enters "Rua X, 123" in the single 'contratante_endereco' field, we can't easily split it into street, number, neighborhood, city, state.
                # UNLESS we add those fields to the New Contract form too.
                
                # BUT: checking new_contract.html again...
                # "Details" section:
                # <input type="text" name="contratante_endereco" ... placeholder="Endereço">
                
                # So currently, the contract form ONLY has a single address field.
                # If the user fills this, we should save it to `address_street` as a best effort?
                # Or maybe `address_street` is not the right place if it contains the full address.
                # But the Client Details UI clearly separates them.
                
                # CRITICAL FIX: Do NOT overwrite separate address fields with the full combined string.
                # This causes recursion (MyStreet -> MyStreet, 123, Neighborhood -> MyStreet, 123, Neighborhood, 123, Neighborhood...)
                # and crashes the DB with StringTruncation error.
                # if form_data.get('contratante_endereco'):
                #      client.address_street = form_data.get('contratante_endereco')

                # Financials
                val_parcela = form_data.get('valor_parcela')
                if val_parcela:
                    try:
                        # 1.250,50 -> 1250.50
                        cleaned = val_parcela.replace('R$', '').replace('.', '').replace(',', '.').strip()
                        client.monthly_value = float(cleaned)
                    except ValueError:
                        pass
            # ----------------------------------
            
            
            # 1. Process Main Content
            generated_content = template.content
            for key, value in replacements.items():
                generated_content = generated_content.replace(key, str(value))
            
            try:
                generated_content = markdown.markdown(generated_content)
            except Exception as e:
                print(f"Markdown Error: {e}")

            # Inject Branded Header
            if current_user.company.logo_filename:
                 logo_url = url_for('static', filename='uploads/company/' + current_user.company.logo_filename, _external=True)
                 primary_color = current_user.company.primary_color or '#fa0102'
                 secondary_color = current_user.company.secondary_color or '#111827'
                 header_html = f"""
                     <div style="text-align:center; margin-bottom: 40px; border-bottom: 2px solid {primary_color}; padding-bottom: 20px;">
                         <h2 style="color: {secondary_color}; margin: 0; text-transform: uppercase;">{current_user.company.name}</h2>
                         <p style="color: #666; font-size: 12px; margin: 5px 0;">CNPJ: {current_user.company.document}</p>
                         <img src="{logo_url}" style="max-height: 60px; margin-top: 10px;">
                     </div>
                 """
                 generated_content = header_html + generated_content

            status = 'issued' if action == 'issue' else 'draft'
            
            if contract_id:
                contract = Contract.query.get(contract_id)
                if contract and contract.company_id == current_user.company_id:
                    contract.template_id = template.id
                    contract.generated_content = generated_content
                    contract.form_data = json.dumps(form_data)
                    contract.status = status
                else:
                    # Fallback to create if ID invalid
                     contract = Contract(
                        client_id=client.id,
                        company_id=client.company.id,
                        template_id=template.id,
                        generated_content=generated_content,
                        form_data=json.dumps(form_data),
                        status=status
                    )
                     db.session.add(contract)
            else: 
                contract = Contract(
                    client_id=client.id,
                    company_id=client.company.id,
                    template_id=template.id,
                    generated_content=generated_content,
                    form_data=json.dumps(form_data),
                    status=status
                )
                db.session.add(contract)
                
            db.session.commit()
            
            if status == 'issued':
                create_notification(current_user.id, client.company_id, 'client_status_changed', f"Contrato emitido para {client.name}", f"Contrato #{contract.id} gerado.")
                
                # Auto-Create Urgent Task
                task = Task(
                    title="Enviar contrato para assinatura",
                    description=f"Contrato #{contract.id} emitido. Enviar para assinatura do cliente.",
                    due_date=datetime.now(),
                    priority='urgente',
                    status='pendente',
                    company_id=current_user.company_id,
                    client_id=client.id,
                    assigned_to_id=current_user.id
                )
                db.session.add(task)
                db.session.commit()
                
                flash('Contrato emitido e tarefa de assinatura criada!', 'success')
            else:
                flash('Rascunho salvo com sucesso!', 'info')

            return redirect(url_for('main.client_details', id=client.id))
        except Exception as e:
            import traceback
            traceback.print_exc()
            error_msg = str(e)
            flash(f"Erro ao emitir contrato: {error_msg}", 'error')
            
            # Log to DB for debugging
            try:
                db.session.rollback() # Rollback the failed contract transaction first
                create_notification(
                    user_id=current_user.id,
                    company_id=current_user.company_id,
                    type='system_error',
                    title='Erro ao Emitir Contrato (Debug)',
                    message=f"Erro técnico: {error_msg}"
                )
            except:
                pass # Fail silently if logging fails
                
            return redirect(url_for('main.client_details', id=client.id))


    @main.route('/contracts/<int:id>/cancel', methods=['POST'])
    @login_required
    def cancel_contract(id):
        contract = Contract.query.get_or_404(id)
        if contract.company_id != current_user.company_id:
            abort(403)
            
    @main.route('/contracts/<int:id>/terminate', methods=['POST'])
    @login_required
    def terminate_contract(id):
        contract = Contract.query.get_or_404(id)
        if contract.company_id != current_user.company_id:
            abort(403)
            
        # Log Start
        print(f"DEBUG: Canceling Contract #{id}")
        debug_log = [f"Início Cancelamento Contrato #{id}"]
        
        try:
            data = request.json
            reason = data.get('reason')
            penalty = data.get('penalty', 0)
            due_date_str = data.get('due_date')
            
            contract.cancellation_reason = reason
            contract.cancellation_date = datetime.now()
            
            debug_log.append(f"Motivo: {reason}, Multa: {penalty}, Data: {due_date_str}")
            
            # 1. Cancel Pending/Overdue Transactions (Local + Asaas)
            # Fetch both pending and overdue to ensure we stop all future/unpaid obligations
            targets = Transaction.query.filter(
                Transaction.contract_id == contract.id, 
                Transaction.status.in_(['pending', 'overdue'])
            ).all()
            
            debug_log.append(f"Transações para cancelar encontradas: {len(targets)}")
            
            from services.asaas_service import AsaasService
            
            asaas_cancelled_count = 0
            for tx in targets:
                tx.status = 'cancelled'
                if tx.asaas_id:
                    try:
                        success = AsaasService.cancel_payment(contract.company_id, tx.asaas_id)
                        if success: 
                            asaas_cancelled_count += 1
                            debug_log.append(f"TX #{tx.id} (Asaas {tx.asaas_id}): Cancelado.")
                        else:
                            debug_log.append(f"TX #{tx.id}: Falha cancelamento API.")
                    except Exception as e:
                        debug_log.append(f"TX #{tx.id}: Erro API: {e}")
            
            # 2. Update Contract Status
            contract.status = 'cancelled'
            
            # CRITICAL: Commit cancellations NOW before risking Fee generation errors
            db.session.commit()
            debug_log.append("Cancelamentos salvos no banco com sucesso.")
            
            # 3. Create Termination Fee (if requested)
            if penalty and penalty > 0:
                try:
                     due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date() if due_date_str else date.today()
                     
                     fee_tx = Transaction(
                        contract_id=contract.id,
                        company_id=contract.company_id,
                        client_id=contract.client_id, # Link client directly
                        description=f"Multa Rescisória - Contrato #{contract.id}",
                        amount=penalty,
                        due_date=due_date,
                        status='pending'
                    )
                     db.session.add(fee_tx)
                     db.session.commit() # Commit local fee first to get ID
                     
                     # Integration
                     debug_log.append(f"Gerando Boleto Multa: {penalty}")
                     customer_id = AsaasService.create_customer(contract.company_id, contract.client)
                     AsaasService.create_payment(contract.company_id, customer_id, fee_tx)
                     
                     # Final commit for Asaas ID updates
                     db.session.commit()
                     debug_log.append("Multa gerada no Asaas com sucesso.")
                     
                except Exception as e:
                    debug_log.append(f"ERRO AO GERAR MULTA: {str(e)}")
                    # Not re-raising to avoid 500 response, just logging.
                    # Cancellation is already done.
            
            # Notify Log
            try:
                create_notification(
                    user_id=current_user.id,
                    company_id=current_user.company_id,
                    type='system_info',
                    title=f'Cancelamento #{contract.id}',
                    message="\n".join(debug_log)
                )
            except: pass
            
            return jsonify({'message': 'Contrato cancelado com sucesso.'})
            
        except Exception as e:
            db.session.rollback()
            print(f"Error terminating contract: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'message': f'Erro ao cancelar: {str(e)}'}), 500

    @main.route('/settings/integrations', methods=['GET', 'POST'])
    @login_required
    def settings_integrations():
        if current_user.role != ROLE_ADMIN:
            abort(403)
            
        from models import Integration
        
        # Determine active tab
        active_tab = 'integrations'
        
        if request.method == 'POST':
            # Handle Add/Update
            service_name = request.form.get('service')
            api_key = request.form.get('api_key')
            
            if service_name and api_key:
                # Upsert
                integration = Integration.query.filter_by(company_id=current_user.company_id, service=service_name).first()
                if not integration:
                    integration = Integration(
                        company_id=current_user.company_id,
                        service=service_name
                    )
                    db.session.add(integration)
                
                integration.api_key = api_key
                integration.is_active = True
                db.session.commit()
                flash('Integração salva com sucesso!', 'success')
            else:
                flash('Campos obrigatórios faltando.', 'error')
                
            return redirect(url_for('main.settings_integrations'))

        # List existing
        integrations = Integration.query.filter_by(company_id=current_user.company_id).all()
        # Helper dict for template access by service name easily if needed, or iterate list
        integrations_map = {i.service: i for i in integrations}
        
        # Prepare Z-API Config for convenience
        zapi_config = {}
        if 'z_api' in integrations_map:
            import json
            try:
                zapi_config = json.loads(integrations_map['z_api'].config_json)
                if zapi_config is None: zapi_config = {}
            except:
                zapi_config = {}
        
        return render_template('settings_integrations.html', company=current_user.company, integrations_map=integrations_map, zapi_config=zapi_config)

    @main.route('/settings/integrations/delete/<service>', methods=['POST'])
    @login_required
    def delete_integration(service):
        if current_user.role != ROLE_ADMIN:
            abort(403)
        
        from models import Integration
        integration = Integration.query.filter_by(company_id=current_user.company_id, service=service).first()
        
        if integration:
            db.session.delete(integration)
            db.session.commit()
            flash(f'Integração {service} removida.', 'success')
        
        return redirect(url_for('main.settings_integrations'))

    @main.route('/api/contracts/autosave', methods=['POST'])
    @login_required
    def autosave_contract():
        data = request.json
        client_id = data.get('client_id')
        contract_id = data.get('contract_id')
        template_id = data.get('template_id')
        form_data = data.get('form_data')
        content = data.get('content')
        
        if not client_id or not template_id:
             return jsonify({'error': 'Missing data'}), 400
             
        client = Client.query.get(client_id)
        if not client or client.company_id != current_user.company_id:
            return jsonify({'error': 'Invalid client'}), 403
            
        if contract_id:
            contract = Contract.query.get(contract_id)
            if contract and contract.company_id == current_user.company_id:
                contract.template_id = template_id
                contract.generated_content = content
                contract.form_data = json.dumps(form_data)
                # Ensure status remains draft
                contract.status = 'draft'
            else:
                 return jsonify({'error': 'Invalid contract'}), 404
        else:
             contract = Contract(
                client_id=client.id,
                company_id=client.company.id,
                template_id=template_id,
                generated_content=content,
                form_data=json.dumps(form_data),
                status='draft'
            )
             db.session.add(contract)
        
        db.session.commit()
        return jsonify({'success': True, 'contract_id': contract.id})

    @main.route('/contracts/<int:id>/resume')
    @login_required
    def resume_contract(id):
        contract = Contract.query.get_or_404(id)
        if contract.company_id != current_user.company_id:
            abort(403)
            
        # If already issued, redirect to view
        if contract.status == 'issued':
            flash('Este contrato já foi emitido.', 'warning')
            return redirect(url_for('main.view_contract', id=contract.id))
            
        client = Client.query.get(contract.client_id)
        templates = ContractTemplate.query.filter_by(company_id=current_user.company_id, active=True, type='contract').all()
        attachments = ContractTemplate.query.filter_by(company_id=current_user.company_id, active=True, type='attachment').all()
        
        draft_data = json.loads(contract.form_data) if contract.form_data else {}
        # Inject contract_id into draft_data to ensure inputs match
        draft_data['contract_id'] = contract.id
        
        return render_template('contracts/new_contract.html', client=client, templates=templates, attachments=attachments, draft_data=draft_data, contract_id=contract.id)

    @main.route('/contracts/<int:id>')
    @login_required
    def view_contract(id):
        contract = Contract.query.get_or_404(id)
        if contract.company_id != current_user.company_id:
            abort(403)
        return render_template('contracts/view_contract.html', contract=contract)

    @main.route('/settings/company', methods=['GET', 'POST'])
    @login_required
    def company_settings():
        company = Company.query.get(current_user.company_id)
        if not company:
            abort(404)
            
        if request.method == 'POST':
            company.name = request.form.get('name')
            company.document = request.form.get('document')
            
            company.address_street = request.form.get('address_street')
            company.address_number = request.form.get('address_number')
            company.address_neighborhood = request.form.get('address_neighborhood')
            company.address_city = request.form.get('address_city')
            company.address_state = request.form.get('address_state')
            company.address_zip = request.form.get('address_zip')

            company.representative = request.form.get('representative')
            company.representative_cpf = request.form.get('representative_cpf')
            
            # Branding
            company.primary_color = request.form.get('primary_color', '#fa0102')
            company.secondary_color = request.form.get('secondary_color', '#111827')
            
            # Logo Upload
            if 'logo' in request.files:
                file = request.files['logo']
                if file and file.filename != '' and allowed_file(file.filename):
                    filename = secure_filename(f"company_{company.id}_{int(datetime.now().timestamp())}.{file.filename.rsplit('.', 1)[1].lower()}")
                    file.save(os.path.join(app.config['COMPANY_UPLOAD_FOLDER'], filename))
                    company.logo_filename = filename

            db.session.commit()
            flash('Configurações da empresa atualizadas com sucesso!', 'success')
            return redirect(url_for('main.company_settings'))
            
        return render_template('company_settings.html', company=company)

    @main.route('/settings/templates')
    @login_required
    def settings_templates():
        templates = ContractTemplate.query.filter(
            (ContractTemplate.company_id == current_user.company_id) | (ContractTemplate.is_global == True)
        ).filter_by(active=True).all()
        return render_template('settings_templates.html', templates=templates)

    @main.route('/settings/templates/new', methods=['GET', 'POST'])
    @login_required
    def settings_template_new():
        if request.method == 'POST':
            name = request.form.get('name')
            type_ = request.form.get('type')
            content = request.form.get('content')
            
            template = ContractTemplate(
                company_id=current_user.company_id,
                name=name,
                type=type_,
                content=content,
                active=True
            )
            db.session.add(template)
            db.session.commit()
            flash('Modelo criado com sucesso!', 'success')
            return redirect(url_for('main.settings_templates'))
            
        return render_template('settings_template_edit.html', template=None)

    @main.route('/settings/templates/<int:id>/edit', methods=['GET', 'POST'])
    @login_required
    def settings_template_edit(id):
        template = ContractTemplate.query.get_or_404(id)
        
        # Access Logic: Own Company OR Global
        if template.company_id != current_user.company_id and not template.is_global:
            abort(403)
            
        # Write Logic: Only Owner can edit. Others see Read-Only (handled in template or redirect to duplicate?)
        # For now, if global and not owner, we just pass it to template, but backend block save.
        
        if request.method == 'POST':
            # BLOCK SAVE if Global and not Owner
            if template.is_global and template.company_id != current_user.company_id:
                  flash('Modelos globais não podem ser editados. Use a opção "Duplicar" para criar sua versão.', 'error')
                  return redirect(url_for('main.settings_template_edit', id=id))

            template.name = request.form.get('name')
            template.type = request.form.get('type')
            template.content = request.form.get('content')
            
            db.session.commit()
            flash('Modelo atualizado com sucesso!', 'success')
            return redirect(url_for('main.settings_templates'))
            
        return render_template('settings_template_edit.html', template=template)

    @main.route('/settings/templates/<int:id>/delete', methods=['POST'])
    @login_required
    def settings_template_delete(id):
        template = ContractTemplate.query.get_or_404(id)
        if template.company_id != current_user.company_id:
            abort(403)
            
        template.active = False # Soft delete
        db.session.commit()
        flash('Modelo excluído com sucesso!', 'success')
        return redirect(url_for('main.settings_templates'))

    # ==========================
    # FINANCIAL MODULE ROUTES
    # ==========================

    def add_months(sourcedate, months):
        """Simple helper to add months."""
        month = sourcedate.month - 1 + months
        year = sourcedate.year + month // 12
        month = month % 12 + 1
        day = min(sourcedate.day, [31,
            29 if year % 4 == 0 and not year % 100 == 0 or year % 400 == 0 else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month-1])
        return date(year, month, day)





    @main.route('/contracts/<int:id>/sign', methods=['POST'])
    @login_required
    def sign_contract(id):
        def add_months_helper(sourcedate, months):
            month = sourcedate.month - 1 + months
            year = sourcedate.year + month // 12
            month = month % 12 + 1
            day = min(sourcedate.day, [31,
                29 if year % 4 == 0 and not year % 100 == 0 or year % 400 == 0 else 28,
                31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month-1])
            return date(year, month, day)

        contract = Contract.query.get_or_404(id)
        if contract.company_id != current_user.company_id:
            abort(403)
            
        # Parse Form Data to get financial terms
        try:
            data = json.loads(contract.form_data)
            val_parcela_str = data.get('valor_parcela', '0')
            qtd_parcelas = int(data.get('qtd_parcelas', '12'))
            dia_vencimento = int(data.get('dia_vencimento', '5'))
            data_inicio_str = data.get('data_inicio')
            
            # Implantation Data
            val_implantacao_str = data.get('valor_implantacao', '0')
            forma_implantacao = data.get('forma_implantacao', 'junto_primeira') # junto_primeira, separado_unico, separado_parcelado
            
            val_parcela = float(val_parcela_str.replace('.', '').replace(',', '.'))
            val_implantacao = float(val_implantacao_str.replace('.', '').replace(',', '.')) if val_implantacao_str else 0.0
            
            start_date = datetime.strptime(data_inicio_str, '%d/%m/%Y').date()
            
            new_transactions = []
            
            # Check if transactions already exist to avoid duplicates if re-signed (safety check)
            existing_count = Transaction.query.filter_by(contract_id=contract.id).count()
            
            if existing_count == 0:
                # 1. GENERATE REGULAR INSTALLMENTS
                for i in range(qtd_parcelas):
                    target_month_date = add_months_helper(start_date, i)
                    try:
                        due_date = date(target_month_date.year, target_month_date.month, dia_vencimento)
                    except ValueError:
                        due_date = date(target_month_date.year, target_month_date.month, 28)
                    
                    description = f"Parcela {i+1}/{qtd_parcelas} - {contract.template.name}"
                    amount = val_parcela
                    
                    # Logic A: Merge Implantation into First Installment
                    if i == 0 and val_implantacao > 0 and forma_implantacao == 'junto_primeira':
                        amount += val_implantacao
                        description += " + Taxa de Implantação"

                    t = Transaction(
                        contract_id=contract.id,
                        description=description,
                        amount=amount,
                        due_date=due_date,
                        status='pending'
                    )
                    db.session.add(t)
                    new_transactions.append(t)
                
                # 2. GENERATE SEPARATE IMPLANTATION TRANSACTIONS (If applicable)
                if val_implantacao > 0 and forma_implantacao in ['separado_unico', 'separado_parcelado']:
                    
                    # Determine Count and Due Date
                    impl_qtd = 1
                    impl_date = start_date # Default to start date (or specific date if provided?)
                    
                    # Usually "separado" implies an upfront payment or specific date
                    # Let's check if form provided 'data_vencimento_implantacao'
                    impl_due_date_str = data.get('data_vencimento_implantacao')
                    if impl_due_date_str:
                         try:
                             impl_date = datetime.strptime(impl_due_date_str, '%d/%m/%Y').date()
                         except:
                             impl_date = start_date

                    if forma_implantacao == 'separado_parcelado':
                        impl_qtd_str = data.get('qtd_parcelas_implantacao', '1')
                        impl_qtd = int(impl_qtd_str) if impl_qtd_str else 1
                        
                    impl_installment_val = val_implantacao / impl_qtd
                    
                    for k in range(impl_qtd):
                        # Separate due dates? Usually monthly if parcelled.
                        # If single, just one date.
                        # If parcelled, starting from custom date.
                        target_impl_date = add_months_helper(impl_date, k)
                        
                        desc_extra = f"Taxa de Implantação"
                        if impl_qtd > 1:
                            desc_extra += f" {k+1}/{impl_qtd}"
                        
                        # Use client_id directly now (new feature support)
                        t_impl = Transaction(
                            contract_id=contract.id,
                            client_id=contract.client_id, # Linking explicitly
                            description=desc_extra,
                            amount=impl_installment_val,
                            due_date=target_impl_date,
                            status='pending'
                        )
                        db.session.add(t_impl)
                        new_transactions.append(t_impl)

            
            # --- ASAAS INTEGRATION ---
            from models import Integration
            from services.asaas_service import AsaasService
            
            integration = Integration.query.filter_by(company_id=contract.company_id, service='asaas', is_active=True).first()
            if integration:
                # 1. Ensure Customer Exists
                customer_id = AsaasService.create_customer(contract.company_id, contract.client)
                
                # 2. Create Charges (only for new/pending transactions)
                txs_to_process = new_transactions if new_transactions else Transaction.query.filter_by(contract_id=contract.id, status='pending', asaas_id=None).all()
                
                for tx in txs_to_process:
                    create_data = AsaasService.create_payment(contract.company_id, customer_id, tx)
                    # Helper handles updates
            
            contract.status = 'signed'
            # contract.signed_at = datetime.now() 
            
            db.session.commit()
            
            if integration:
                return jsonify({'success': True, 'message': 'Contrato assinado e cobranças geradas no Asaas!'})
            else:
                return jsonify({'success': True, 'message': 'Contrato assinado (Integração Asaas inativa).'})
            
        except Exception as e:
            print(f"Error signing contract: {e}")
            import traceback
            traceback.print_exc()
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    from routes.financial import financial_bp
    from routes.docs import docs_bp
    # RBAC Routes & Logic
    
    AVAILABLE_PERMISSIONS = {
        'leads': {
            'view_all_leads': 'Ver Todos Leads',
            'edit_all_leads': 'Editar Todos Leads', 
            'delete_leads': 'Excluir Leads',
            'view_assigned_leads': 'Ver Leads Próprios',
            'edit_assigned_leads': 'Editar Leads Próprios',
            'create_leads': 'Criar Leads'
        },
        'clients': {
            'view_all_clients': 'Ver Todos Clientes',
            'edit_all_clients': 'Editar Todos Clientes',
            'delete_clients': 'Excluir Clientes',
            'view_assigned_clients': 'Ver Clientes Próprios',
            'edit_assigned_clients': 'Editar Clientes Próprios'
        },
        'tasks': {
            'view_all_tasks': 'Ver Todas Tarefas',
            'manage_tasks': 'Gerenciar Tarefas'
        },
        'admin': {
            'manage_settings': 'Gerenciar Configurações',
            'manage_team': 'Gerenciar Equipe',
            'manage_financial': 'Acessar Financeiro',
            'manage_pipelines': 'Gerenciar Funis'
        }
    }
    
    CATEGORY_LABELS = {
        'leads': 'Gestão de Leads',
        'clients': 'Gestão de Carteira',
        'tasks': 'Tarefas & Agenda',
        'admin': 'Administração'
    }

    @main.route('/settings/permissions')
    @login_required
    def settings_permissions():
        # Only Allow access if user has 'manage_team' or is admin legacy
        # MVP: Strict to Admin Role ID check or specific permission
        if current_user.user_role.name != 'Administrador' and 'manage_team' not in (current_user.user_role.permissions or []):
             flash('Acesso negado.', 'error')
             return redirect(url_for('main.dashboard'))
             
        roles = Role.query.filter_by(company_id=current_user.company_id).all()
        return render_template('settings_permissions.html', 
                             roles=roles, 
                             available_permissions=AVAILABLE_PERMISSIONS,
                             category_labels=CATEGORY_LABELS)

    @main.route('/settings/roles/new', methods=['POST'])
    @login_required
    def create_role():
        if current_user.user_role.name != 'Administrador' and 'manage_team' not in (current_user.user_role.permissions or []):
             return "Unauthorized", 403
             
        name = request.form.get('name')
        if name:
            role = Role(name=name, company_id=current_user.company_id, permissions=[], is_default=False)
            db.session.add(role)
            db.session.commit()
            flash('Cargo criado com sucesso.', 'success')
            
        return redirect(url_for('main.settings_permissions'))

    @main.route('/settings/roles/<int:id>/update', methods=['POST'])
    @login_required
    def update_role(id):
        if current_user.user_role.name != 'Administrador' and 'manage_team' not in (current_user.user_role.permissions or []):
             return "Unauthorized", 403
             
        role = Role.query.get_or_404(id)
        if role.company_id != current_user.company_id:
             return "Unauthorized", 403
             
        # Update Name (if not default)
        name = request.form.get('name')
        if name and not role.is_default:
            role.name = name
            
        # Update Permissions
        perms = request.form.getlist('permissions[]')
        role.permissions = perms
        
        db.session.commit()
        flash('Permissões atualizadas.', 'success')
        return redirect(url_for('main.settings_permissions'))

    @main.route('/settings/roles/<int:id>/delete', methods=['POST'])
    @login_required
    def delete_role(id):
        if current_user.user_role.name != 'Administrador' and 'manage_team' not in (current_user.user_role.permissions or []):
             return "Unauthorized", 403
             
        role = Role.query.get_or_404(id)
        if role.company_id != current_user.company_id or role.is_default:
             return "Unauthorized", 403
             
        if len(role.users) > 0:
            flash('Não é possível excluir um cargo com usuários ativos.', 'error')
        else:
            db.session.delete(role)
            db.session.commit()
            flash('Cargo excluído.', 'success')
            
        return redirect(url_for('main.settings_permissions'))

    @main.route('/settings/team')
    @login_required
    def settings_team():
        # Check permissions similar to admin_users
        if current_user.role != ROLE_ADMIN:
             return "Acesso negado", 403
        
        users = User.query.filter_by(company_id=current_user.company_id).all()
        return render_template('settings_team.html', users=users)

    # Lead Import/Export Routes

    @main.route('/leads/import/template')
    @login_required
    def download_lead_template():
        # Generate CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Headers
        headers = ['Nome', 'Email', 'Telefone', 'Origem', 'Interesse', 'Notas']
        writer.writerow(headers)
        
        # Example Row
        writer.writerow(['Exemplo da Silva', 'exemplo@email.com', '11999999999', 'Indicação', 'Consultoria', 'Cliente em potencial'])

        output.seek(0)
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            mimetype='text/csv',
            as_attachment=True,
            download_name='modelo_importacao_leads.csv'
        )

    @main.route('/leads/export')
    @login_required
    def export_leads():
        # Filter Logic (Duplicate of leads list logic)
        query = Lead.query.filter_by(company_id=current_user.company_id)
        
        # RBAC Check (Simplified)
        can_view_all = current_user.user_role.name in ['Administrador', 'Gestor'] or 'view_all_leads' in (current_user.user_role.permissions or [])
        if not can_view_all:
             query = query.filter_by(assigned_to_id=current_user.id)
             
        leads = query.order_by(Lead.created_at.desc()).all()
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        headers = ['ID', 'Nome', 'Email', 'Telefone', 'Origem', 'Status', 'Interesse', 'Atribuído Para', 'Criado Em', 'Notas']
        writer.writerow(headers)
        
        for lead in leads:
            assigned_name = lead.assigned_user.name if lead.assigned_user else 'N/A'
            writer.writerow([
                lead.id,
                lead.name,
                lead.email or '',
                lead.phone or '',
                lead.source or '',
                lead.status,
                lead.interest or '',
                assigned_name,
                lead.created_at.strftime('%d/%m/%Y %H:%M'),
                lead.notes or ''
            ])
            
        output.seek(0)
        
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'leads_export_{datetime.now().strftime("%Y%m%d")}.csv'
        )

    @main.route('/leads/import', methods=['POST'])
    @login_required
    def import_leads():
        if 'file' not in request.files:
            flash('Nenhum arquivo enviado.', 'error')
            return redirect(url_for('main.leads'))
            
        file = request.files['file']
        if file.filename == '':
            flash('Nenhum arquivo selecionado.', 'error')
            return redirect(url_for('main.leads'))
            
        if file and file.filename.endswith('.csv'):
            try:
                stream = io.StringIO(file.stream.read().decode("utf-8-sig"), newline=None)
                csv_input = csv.DictReader(stream)
                
                count_success = 0
                count_error = 0
                
                # Get default pipeline stage
                default_pipeline = current_user.allowed_pipelines[0] if current_user.allowed_pipelines else None
                first_stage = None
                if default_pipeline:
                    first_stage = PipelineStage.query.filter_by(pipeline_id=default_pipeline.id).order_by(PipelineStage.order).first()

                for row in csv_input:
                    # Validate Name
                    if not row.get('Nome'):
                        count_error += 1
                        continue
                        
                    # Create Lead
                    new_lead = Lead(
                        name=row.get('Nome'),
                        email=row.get('Email'),
                        phone=row.get('Telefone'),
                        source=row.get('Origem') or 'Importação',
                        interest=row.get('Interesse'),
                        notes=row.get('Notas'),
                        company_id=current_user.company_id,
                        # Assign to uploader by default
                        assigned_to_id=current_user.id,
                        pipeline_id=default_pipeline.id if default_pipeline else None,
                        pipeline_stage_id=first_stage.id if first_stage else None
                    )
                    
                    db.session.add(new_lead)
                    count_success += 1
                
                db.session.commit()
                
                if count_success > 0:
                    flash(f'{count_success} leads importados com sucesso!', 'success')
                if count_error > 0:
                    flash(f'{count_error} linhas ignoradas (nome inválido).', 'warning')
                    
            except Exception as e:
                flash(f'Erro ao processar arquivo: {str(e)}', 'error')
                
        else:
            flash('Formato inválido. Use apenas CSV.', 'error')
            
        return redirect(url_for('main.leads'))

    # Process Checklist Routes (Workflows)

    @main.route('/settings/processes')
    @login_required
    def settings_processes():
        try:
            # RBAC Check with Safety
            if not current_user.user_role:
                 # Fallback for users without RBAC Role linked
                 if current_user.role == 'admin':
                     can_manage = True
                 else:
                     can_manage = False
            else:
                can_manage = current_user.user_role.name in ['Administrador', 'Gestor', 'admin'] or 'manage_settings' in (current_user.user_role.permissions or [])
                
            if not can_manage:
                 flash('Acesso negado.', 'error')
                 return redirect(url_for('main.dashboard'))
                 
            templates = ProcessTemplate.query.filter_by(company_id=current_user.company_id).all()
            return render_template('settings_processes.html', templates=templates)
        except Exception as e:
            return f"<h1>Error Loading Processes</h1><p>{str(e)}</p>"

    @main.route('/settings/processes/new', methods=['POST'])
    @login_required
    def create_process_template():
        can_manage = current_user.user_role.name in ['Administrador', 'Gestor'] or 'manage_settings' in (current_user.user_role.permissions or [])
        if not can_manage:
             return "Unauthorized", 403
             
        name = request.form.get('name')
        description = request.form.get('description')
        
        # Default empty step structure
        steps = [{"title": "Etapa 1", "items": ["Item A"]}]
        
        template = ProcessTemplate(
            name=name, 
            description=description, 
            steps=steps, 
            company_id=current_user.company_id
        )
        db.session.add(template)
        db.session.commit()
        
        flash('Modelo de processo criado.', 'success')
        return redirect(url_for('main.edit_process_template', id=template.id))

    @main.route('/settings/processes/<int:id>/edit', methods=['GET', 'POST'])
    @login_required
    def edit_process_template(id):
        template = ProcessTemplate.query.get_or_404(id)
        if template.company_id != current_user.company_id:
            return "Unauthorized", 403
            
        if request.method == 'POST':
            # Save Steps from JSON Editor
            template.name = request.form.get('name')
            template.description = request.form.get('description')
            steps_json = request.form.get('steps_json')
            
            try:
                template.steps = json.loads(steps_json)
                db.session.commit()
                flash('Processo salvo com sucesso.', 'success')
            except json.JSONDecodeError:
                flash('Erro ao salvar estrutura JSON.', 'error')
                
            return redirect(url_for('main.edit_process_template', id=id))
            
        return render_template('settings_process_edit.html', template=template)

    @main.route('/settings/processes/<int:id>/delete', methods=['POST'])
    @login_required
    def delete_process_template(id):
        template = ProcessTemplate.query.get_or_404(id)
        if template.company_id != current_user.company_id:
            return "Unauthorized", 403
            
        db.session.delete(template)
        db.session.commit()
        flash('Modelo excluído.', 'success')
        return redirect(url_for('main.settings_processes'))

    # Client Checklist Execution Routes

    @main.route('/clients/<int:client_id>/processes/add', methods=['POST'])
    @login_required
    def add_client_process(client_id):
        client = Client.query.get_or_404(client_id)
        template_id = request.form.get('template_id')
        template = ProcessTemplate.query.get_or_404(template_id)
        
        # Instantiate Process and Create Linked Tasks
        progress = []
        for step in template.steps:
            new_items = []
            for item_text in step['items']:
                # Create Task
                new_task = Task(
                    title=item_text,
                    description=f"Item do processo: {template.name} - Etapa: {step['title']}",
                    client_id=client.id,
                    assigned_to_id=client.account_manager_id or current_user.id,
                    company_id=current_user.company_id,
                    status='pendente',
                    priority='media'
                )
                db.session.add(new_task)
                db.session.flush() # Get ID
                
                new_items.append({
                    "text": item_text, 
                    "done": False,
                    "task_id": new_task.id
                })
                
            progress.append({
                "title": step['title'],
                "items": new_items
            })
            
        checklist = ClientChecklist(
            client_id=client.id,
            template_id=template.id,
            name=template.name,
            progress=progress
        )
        db.session.add(checklist)
        db.session.commit()
        
        flash(f'Processo "{template.name}" iniciado para este cliente.', 'success')
        return redirect(url_for('main.client_details', id=client.id))

    @main.route('/api/checklists/<int:id>/toggle', methods=['POST'])
    @login_required
    def toggle_checklist_item(id):
        checklist = ClientChecklist.query.get_or_404(id)
        if checklist.client.company_id != current_user.company_id:
             return jsonify({'error': 'Unauthorized'}), 403
             
        data = request.json
        step_index = int(data.get('step_index'))
        item_index = int(data.get('item_index'))
        done = data.get('done')
        
        try:
            import copy
            # Use deepcopy to ensure SQLAlchemy detects the change as a new object
            current_progress = copy.deepcopy(checklist.progress)
            
            # Validation
            if step_index >= len(current_progress):
                raise IndexError(f"Step index {step_index} out of range")
            
            step = current_progress[step_index]
            if item_index >= len(step['items']):
                raise IndexError(f"Item index {item_index} out of range in step {step_index}")
            
            item_data = step['items'][item_index]
            print(f"DEBUG: Toggling Item '{item_data.get('text')}' -> {done}")
            
            item_data['done'] = done
            
            # Sync Linked Task
            task_id = item_data.get('task_id')
            print(f"DEBUG: Linked Task ID: {task_id}")
            
            if task_id:
                task = Task.query.get(task_id)
                if task:
                    print(f"DEBUG: Found Task {task.id}. Company Match: {task.company_id} vs {current_user.company_id}")
                    if task.company_id == current_user.company_id:
                        task.status = 'concluida' if done else 'pendente'
                        db.session.add(task) # Ensure updated
                        print(f"DEBUG: Task status set to {task.status}")
                else:
                    print("DEBUG: Task not found in DB")
            
            checklist.progress = current_progress
            db.session.add(checklist) # Explicit add
            db.session.commit()
            print("DEBUG: Commit successful")
            
            # Calculate Progress
            total_items = 0
            completed_items = 0
            for step in current_progress:
                for item in step['items']:
                    total_items += 1
                    if item['done']: completed_items += 1
                    
            percent = int((completed_items / total_items) * 100) if total_items > 0 else 0
            
            return jsonify({'success': True, 'percent': percent})
            
        except Exception as e:
            print(f"Error toggling checklist: {str(e)}") # Log to console
            return jsonify({'success': False, 'error': str(e)}), 500

    @main.route('/api/checklists/<int:id>/delete', methods=['POST'])
    @login_required
    def delete_client_checklist(id):
        checklist = ClientChecklist.query.get_or_404(id)
        if checklist.client.company_id != current_user.company_id:
             return jsonify({'error': 'Unauthorized'}), 403

        # Cleanup Linked Tasks
        for step in checklist.progress:
            for item in step['items']:
                task_id = item.get('task_id')
                if task_id:
                    Task.query.filter_by(id=task_id).delete()

        db.session.delete(checklist)
        db.session.commit()
        return jsonify({'success': True})
    
    # app.register_blueprint(master_blueprint) # Removed duplicate (Already registered at top)
    app.register_blueprint(financial_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(goals_bp)
    app.register_blueprint(prospecting_bp)
    
    from routes.admin import admin_bp
    app.register_blueprint(admin_bp)
    
    from routes.whatsapp import whatsapp_bp
    app.register_blueprint(whatsapp_bp)
    
    app.register_blueprint(main)
    
    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=False, port=5001)
