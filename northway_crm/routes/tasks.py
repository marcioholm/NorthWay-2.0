from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from models import db, Task, User, Client, Lead
from datetime import datetime

tasks_bp = Blueprint('tasks', __name__)

@tasks_bp.route('/tasks', methods=['GET', 'POST'])
@login_required
def tasks():
    if request.method == 'POST':
        title = request.form.get('title')
        due_date_str = request.form.get('due_date')
        lead_id = request.form.get('lead_id')
        assigned_to_id = request.form.get('assigned_to_id')
        is_recurring = request.form.get('is_recurring') == '1'

        if not title:
            flash('Título é obrigatório', 'error')
            return redirect(request.form.get('next') or request.referrer or url_for('tasks.tasks'))

        due_date = None
        if due_date_str:
            try:
                due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                pass
        
        # Determine correct assigned user (default to self if not provided or valid)
        assigned_user_id = current_user.id
        if assigned_to_id:
            try:
                assigned_user_id = int(assigned_to_id)
            except ValueError:
                pass

        new_task = Task(
            title=title,
            due_date=due_date,
            lead_id=lead_id if lead_id else None,
            company_id=current_user.company_id,
            assigned_to_id=assigned_user_id,
            status='pendente',
            is_recurring=is_recurring
        )

        db.session.add(new_task)
        db.session.commit()
        
        # Notification Logic: If assigned to someone else
        if assigned_user_id != current_user.id:
            from utils import create_notification
            create_notification(
                user_id=assigned_user_id,
                company_id=current_user.company_id,
                type='task_assigned',
                title='Nova Tarefa Atribuída',
                message=f"{current_user.name} atribuiu uma nova tarefa a você: {title}"
            )

        flash('Tarefa criada com sucesso!', 'success')
        return redirect(request.form.get('next') or request.referrer or url_for('tasks.tasks'))

    # GET Logic (Existing)...
    page = request.args.get('page', 1, type=int)
    per_page = 30
    
    # Filter by company AND assignment (optional, for now show all company tasks or filtered?)
    # NorthWay Logic: Sales see their own tasks. Managers/Admins see all?
    # For now, keeping existing logic: Show ALL tasks for company to visibility, 
    # but we might want to highlight assigned ones later.
    tasks_query = Task.query.filter_by(company_id=current_user.company_id)
    
    # View filters could be added here later (e.g. ?view=me)
    
    tasks_list = tasks_query\
        .options(db.joinedload(Task.responsible), db.joinedload(Task.client), db.joinedload(Task.lead))\
        .order_by(Task.due_date.asc()).all()
    
    # Categorize for template tabs
    lead_tasks = [t for t in tasks_list if t.lead_id and t.status != 'completa']
    client_tasks = [t for t in tasks_list if t.client_id and t.status != 'completa']
    general_tasks = [t for t in tasks_list if not t.lead_id and not t.client_id and t.status != 'completa']
    completed_tasks_list = [t for t in tasks_list if t.status == 'completa']
    
    total_tasks = len(tasks_list)
    completed_count = len(completed_tasks_list)
    progress_percent = int((completed_count / total_tasks * 100)) if total_tasks > 0 else 0
    
    users = User.query.filter_by(company_id=current_user.company_id).all()
    leads = Lead.query.filter_by(company_id=current_user.company_id).order_by(Lead.name).all() # Fetch leads for dropdown
    
    return render_template('tasks.html', 
                           lead_tasks=lead_tasks,
                           client_tasks=client_tasks,
                           general_tasks=general_tasks,
                           completed_tasks_list=completed_tasks_list,
                           completed_tasks=completed_count,
                           total_tasks=total_tasks,
                           progress_percent=progress_percent,
                           users=users,
                           leads=leads, # Pass leads to template
                           current_user=current_user,
                           now=datetime.now())

@tasks_bp.route('/tasks/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_task(id):
    task = Task.query.get_or_404(id)
    if task.company_id != current_user.company_id:
        abort(403)
        
    if task.status == 'completa':
        task.status = 'pendente'
        task.completed_at = None
    else:
        task.status = 'completa'
        task.completed_at = datetime.now()
        
    db.session.commit()
    
    # Return JSON for AJAX or redirect as fallback
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'status': task.status})
    
    return redirect(request.referrer or url_for('tasks.tasks'))

@tasks_bp.route('/tasks/<int:id>/delete', methods=['POST'])
@login_required
def delete_task(id):
    task = Task.query.get_or_404(id)
    if task.company_id != current_user.company_id:
        abort(403)
        
    db.session.delete(task)
    db.session.commit()
    flash('Tarefa excluída.', 'success')
    return redirect(request.referrer or url_for('tasks.tasks'))

@tasks_bp.route('/onboarding/dismiss', methods=['POST'])
@login_required
def dismiss_onboarding():
    current_user.onboarding_dismissed = True
    db.session.commit()
    return jsonify({'success': True})

@tasks_bp.route('/tasks/<int:id>/update', methods=['POST'])
@login_required
def update_task(id):
    task = Task.query.get_or_404(id)
    if task.company_id != current_user.company_id:
        abort(403)
        
    title = request.form.get('title')
    due_date_str = request.form.get('due_date')
    assigned_to_id = request.form.get('assigned_to_id')
    
    if title: 
        task.title = title
        
    if due_date_str:
        try:
            task.due_date = datetime.strptime(due_date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            pass
            
    if assigned_to_id:
        try:
            new_assignee_id = int(assigned_to_id)
            old_assignee_id = task.assigned_to_id
            
            if new_assignee_id != old_assignee_id:
                task.assigned_to_id = new_assignee_id
                
                # Notify new assignee
                if new_assignee_id != current_user.id:
                    from utils import create_notification
                    create_notification(
                        user_id=new_assignee_id,
                        company_id=current_user.company_id,
                        type='task_assigned',
                        title='Tarefa Delegada',
                        message=f"{current_user.name} delegou a tarefa '{task.title}' para você."
                    )
        except ValueError:
            pass

    db.session.commit()
    flash('Tarefa atualizada com sucesso.', 'success')
    return redirect(request.referrer or url_for('tasks.tasks'))
