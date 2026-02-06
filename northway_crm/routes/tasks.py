from flask import Blueprint, render_template, jsonify, request, current_app
from flask_login import login_required, current_user
from services.task_service import TaskService
from models import Task, User

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
                'auto_generated': t.auto_generated
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
    
    try:
        TaskService.update_status(task_id, new_status, actor_id=current_user.id)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 400
