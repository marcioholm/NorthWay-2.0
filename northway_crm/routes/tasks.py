from flask import Blueprint, render_template, jsonify, request, current_app
from flask_login import login_required, current_user
from services.task_service import TaskService
from models import Task, User
from datetime import datetime

tasks_bp = Blueprint('tasks', __name__, url_prefix='/tasks')

# --- VIEWS ---

@tasks_bp.route('/execution')
@login_required
def execution_kanban():
    """
    Kanban Board View (My Execution)
    """
    return render_template('tasks/execution_kanban.html')

@tasks_bp.route('/execution/team')
@login_required
def team_execution():
    """
    Manager View (Team Execution)
    """
    # Check permissions (manager/admin)
    # MVP: Allow everyone for now or check role
    if not current_user.role in ['admin', 'gestor']:
         pass # Maybe restrict access later
         
    users = User.query.filter_by(company_id=current_user.company_id).all()
    return render_template('tasks/team_execution.html', users=users)


# --- API ENDPOINTS ---

@tasks_bp.route('/api/kanban', methods=['GET'])
@login_required
def get_kanban_data():
    """
    Returns filtered tasks for Kanban
    """
    user_id = request.args.get('user_id', current_user.id, type=int)
    
    # Security: Only allow viewing other users if Admin/Manager
    if user_id != current_user.id:
         if current_user.role not in ['admin', 'gestor']:
             return jsonify({'error': 'Unauthorized'}), 403

    kanban_data = TaskService.get_kanban_tasks(user_id)
    
    # Serialize tasks
    # We could do this in Service, but doing here for flexibility
    serialized = {}
    for status, tasks in kanban_data.items():
        serialized[status] = []
        for t in tasks:
            serialized[status].append({
                'id': t.id,
                'title': t.title,
                'description': t.description,
                'priority': t.priority,
                'due_date': t.due_date.strftime('%Y-%m-%d') if t.due_date else None,
                'source_type': t.source_type,
                'client_name': t.client.name if t.client else None,
                'auto_generated': t.auto_generated,
                'is_urgent': t.is_urgent,
                'is_important': t.is_important
            })
            
    return jsonify(serialized)

@tasks_bp.route('/api/create', methods=['POST'])
@login_required
def create_task_api():
    """
    Creates a new manual task
    """
    data = request.json
    try:
        # Enforce company_id
        data['company_id'] = current_user.company_id
        
        # Enforce created_by
        # If assigning to someone else, check permissions? MVP: Allow.
        
        # Extract priority flags
        is_urgent = data.get('is_urgent', False)
        is_important = data.get('is_important', False)
        
        # Add to data payload if not present (or handled by service)
        data['is_urgent'] = is_urgent
        data['is_important'] = is_important
        
        task = TaskService.create_task(data, user_id=current_user.id)
        return jsonify({'status': 'success', 'task_id': task.id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@tasks_bp.route('/api/move/<int:task_id>', methods=['PATCH'])
@login_required
def move_task_api(task_id):
    """
    Drag and Drop: Update Status
    """
    data = request.json
    new_status = data.get('status')
    
    # Handle dragging in Matrix (updates urgency/importance)
    is_urgent = data.get('is_urgent')
    is_important = data.get('is_important')
    
    try:
        # If status is present, update status
        if new_status:
            TaskService.update_status(task_id, new_status, actor_id=current_user.id)
            
        # If urgency/importance present, update them
        # We need to expose a method in Service or do it here manually for MVP
        if is_urgent is not None or is_important is not None:
             from models import Task, db
             task = Task.query.get(task_id)
             if task and task.company_id == current_user.company_id:
                 if is_urgent is not None: task.is_urgent = is_urgent
                 if is_important is not None: task.is_important = is_important
                 db.session.commit()

        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@tasks_bp.route('/', methods=['GET', 'POST'])
@login_required
def tasks():
    # POST: Create Task
    if request.method == 'POST':
        title = request.form.get('title')
        lead_id = request.form.get('lead_id')
        assigned_to_id = request.form.get('assigned_to_id')
        due_date_str = request.form.get('due_date')
        is_recurring = request.form.get('is_recurring') == '1'
        
        if not title:
            # flash('Título é obrigatório', 'error') # Need flash
            return jsonify({'error': 'Title required'}), 400

        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass
                
        # Handle empty/none lead_id
        if not lead_id or lead_id == 'None':
            lead_id = None
            
        task = Task(
            title=title,
            description=request.form.get('description'), # Added description
            due_date=due_date,
            lead_id=lead_id,
            assigned_to_id=assigned_to_id or current_user.id,
            company_id=current_user.company_id,
            status='pendente',
            is_recurring=is_recurring
        )
        
        try:
            from models import db
            db.session.add(task)
            db.session.commit()
            # flash('Tarefa criada!', 'success')
        except Exception as e:
            # flash(f'Erro: {e}', 'error')
            pass
            
        return render_template('tasks.html') # Redirect usually, but let's follow standard pattern
        # Actually standard is redirect.
        return redirect(url_for('tasks.tasks'))

    # GET: List Tasks
    from models import Lead  # Safe import
    user_id = current_user.id
    company_id = current_user.company_id
    
    # Queries
    # 1. Lead Tasks (Pending/Active)
    lead_tasks = Task.query.filter(
        Task.company_id == company_id,
        Task.assigned_to_id == user_id,
        Task.lead_id != None,
        Task.status != 'concluida'
    ).order_by(Task.due_date.asc()).all()
    
    # 2. Client Tasks (Pending)
    client_tasks = Task.query.filter(
        Task.company_id == company_id,
        Task.assigned_to_id == user_id,
        Task.client_id != None,
        Task.status != 'concluida'
    ).order_by(Task.due_date.asc()).all()
    
    # 3. General Tasks
    general_tasks = Task.query.filter(
        Task.company_id == company_id,
        Task.assigned_to_id == user_id,
        Task.lead_id == None,
        Task.client_id == None,
        Task.status != 'concluida'
    ).order_by(Task.due_date.asc()).all()
    
    # 4. Completed Tasks
    completed_tasks_list = Task.query.filter(
        Task.company_id == company_id,
        Task.assigned_to_id == user_id,
        Task.status == 'concluida'
    ).order_by(Task.completed_at.desc()).limit(50).all()
    
    total_tasks = Task.query.filter_by(company_id=company_id, assigned_to_id=user_id).count()
    completed_count = Task.query.filter_by(company_id=company_id, assigned_to_id=user_id, status='concluida').count()
    
    progress_percent = 0
    if total_tasks > 0:
        progress_percent = int((completed_count / total_tasks) * 100)
        
    # Context data for modals
    leads = Lead.query.filter_by(company_id=company_id).all()
    users = User.query.filter_by(company_id=company_id).all()
    
    now = datetime.now()
    
    return render_template('tasks.html',
                           lead_tasks=lead_tasks,
                           client_tasks=client_tasks,
                           general_tasks=general_tasks,
                           completed_tasks_list=completed_tasks_list,
                           completed_tasks=completed_count,
                           total_tasks=total_tasks,
                           progress_percent=progress_percent,
                           leads=leads,
                           users=users,
                           now=now)

@tasks_bp.route('/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_task(id):
    from models import db
    task = Task.query.get_or_404(id)
    if task.company_id != current_user.company_id:
        return jsonify({'error': 'Unauthorized'}), 403
        
    if task.status == 'concluida':
        task.status = 'pendente'
        task.completed_at = None
    else:
        task.status = 'concluida'
        task.completed_at = datetime.now()
        
    db.session.commit()
    return redirect(request.referrer or url_for('tasks.tasks'))

@tasks_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete_task(id):
    from models import db
    task = Task.query.get_or_404(id)
    if task.company_id != current_user.company_id:
        return jsonify({'error': 'Unauthorized'}), 403
        
    db.session.delete(task)
    db.session.commit()
    return redirect(request.referrer or url_for('tasks.tasks'))

@tasks_bp.route('/<int:id>/update', methods=['POST'])
@login_required
def update(id):
    from models import db
    task = Task.query.get_or_404(id)
    if task.company_id != current_user.company_id:
        return jsonify({'error': 'Unauthorized'}), 403
        
    task.title = request.form.get('title')
    task.description = request.form.get('description') # Update description
    task.assigned_to_id = request.form.get('assigned_to_id')
    
    due_date_str = request.form.get('due_date')
    if due_date_str:
        try:
            task.due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            pass
            
    db.session.commit()
    return redirect(request.referrer or url_for('tasks.tasks'))
