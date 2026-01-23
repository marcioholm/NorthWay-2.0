from flask import Blueprint, request, jsonify, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from models import db, Client, ProcessTemplate, ClientChecklist, Task
import copy

checklists_bp = Blueprint('checklists', __name__)

@checklists_bp.route('/clients/<int:client_id>/processes/add', methods=['POST'])
@login_required
def add_client_process(client_id):
    client = Client.query.get_or_404(client_id)
    if client.company_id != current_user.company_id:
        abort(403)
        
    template_id = request.form.get('template_id')
    template = ProcessTemplate.query.get_or_404(template_id)
    if template.company_id != current_user.company_id:
        abort(403)

    progress = []
    for step in template.steps:
        new_items = []
        for item_text in step['items']:
            new_task = Task(
                title=item_text,
                description=f"Item do processo: {template.name} - Etapa: {step['title']}",
                client_id=client.id,
                # Assign to chosen user or fallback to manager/creator
                assigned_to_id=int(request.form.get('assigned_to_id')) if request.form.get('assigned_to_id') else (client.account_manager_id or current_user.id),
                company_id=current_user.company_id,
                status='pendente',
                priority='media'
            )
            db.session.add(new_task)
            db.session.flush()
        
            new_items.append({"text": item_text, "done": False, "task_id": new_task.id})
        
        progress.append({"title": step['title'], "items": new_items})
    
    assigned_to_id = request.form.get('assigned_to_id')
    
    checklist = ClientChecklist(
        client_id=client.id, 
        template_id=template.id, 
        name=template.name, 
        progress=progress, 
        company_id=current_user.company_id,
        assigned_to_id=int(assigned_to_id) if assigned_to_id else None
    )
    db.session.add(checklist)
    db.session.commit()

    flash(f'Processo "{template.name}" iniciado.', 'success')
    return redirect(url_for('clients.client_details', id=client.id))

@checklists_bp.route('/api/checklists/<int:id>/toggle', methods=['POST'])
@login_required
def toggle_checklist_item(id):
    checklist = ClientChecklist.query.get_or_404(id)
    if checklist.company_id != current_user.company_id:
         return jsonify({'error': 'Unauthorized'}), 403
     
    data = request.json
    step_idx = int(data.get('step_index'))
    item_idx = int(data.get('item_index'))
    done = data.get('done')

    try:
        current_progress = copy.deepcopy(checklist.progress)
        item_data = current_progress[step_idx]['items'][item_idx]
        item_data['done'] = done
    
        task_id = item_data.get('task_id')
        if task_id:
            task = Task.query.get(task_id)
            if task and task.company_id == current_user.company_id:
                task.status = 'concluida' if done else 'pendente'
                if done: task.completed_at = db.func.now()
                else: task.completed_at = None
    
        checklist.progress = current_progress
        db.session.commit()
    
        total = sum(len(s['items']) for s in current_progress)
        completed = sum(sum(1 for i in s['items'] if i['done']) for s in current_progress)
        percent = int((completed / total) * 100) if total > 0 else 0
    
        return jsonify({'success': True, 'percent': percent})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@checklists_bp.route('/api/checklists/<int:id>/delete', methods=['POST'])
@login_required
def delete_client_checklist(id):
    checklist = ClientChecklist.query.get_or_404(id)
    if checklist.company_id != current_user.company_id:
         return jsonify({'error': 'Unauthorized'}), 403

    for step in checklist.progress:
        for item in step['items']:
            task_id = item.get('task_id')
            if task_id:
                Task.query.filter_by(id=task_id, company_id=current_user.company_id).delete()

    db.session.delete(checklist)
    db.session.commit()
    return jsonify({'success': True})

@checklists_bp.route('/checklists/<int:id>/reassign', methods=['POST'])
@login_required
def reassign_checklist(id):
    checklist = ClientChecklist.query.get_or_404(id)
    if checklist.company_id != current_user.company_id:
        abort(403)
        
    assigned_to_id = request.form.get('assigned_to_id')
    if not assigned_to_id:
        flash('Usuário não selecionado.', 'error')
        return redirect(url_for('clients.client_details', id=checklist.client_id))
        
    try:
        new_user_id = int(assigned_to_id)
        # Update Checklist
        checklist.assigned_to_id = new_user_id
        
        # Cascade to all incomplete tasks linked to this checklist
        count_updated = 0
        for step in checklist.progress:
            for item in step['items']:
                task_id = item.get('task_id')
                # Only update checkable items with tasks
                if task_id:
                     task = Task.query.get(task_id)
                     if task and task.status != 'concluida' and task.company_id == current_user.company_id:
                         task.assigned_to_id = new_user_id
                         count_updated += 1
        
        db.session.commit()
        
        # Notify
        from utils import create_notification
        create_notification(
            user_id=new_user_id,
            company_id=current_user.company_id,
            type='task_assigned', # Reusing task type or create 'process_assigned'
            title='Processo Delegado',
            message=f"{current_user.name} delegou o processo '{checklist.name}' e {count_updated} tarefas para você."
        )
        
        flash(f'Processo delegado com sucesso! ({count_updated} tarefas atualizadas)', 'success')
        
    except ValueError:
        flash('ID de usuário inválido.', 'error')
    
    return redirect(url_for('clients.client_details', id=checklist.client_id))
