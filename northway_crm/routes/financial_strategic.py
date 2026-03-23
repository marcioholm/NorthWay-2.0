from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from models import db, Transaction, ServiceOrder, FixedCost, StrategicAuditLog, get_now_br, ROLE_ADMIN, Expense, FinancialCategory, User
from sqlalchemy import func, extract
from datetime import datetime, date, timedelta
import csv
import io
import json

financial_strategic_bp = Blueprint('financial_strategic', __name__)

@financial_strategic_bp.route('/financial/strategic')
@login_required
def dashboard():
    if not current_user.company_id:
        abort(403)
    
    # Only Admin/SuperAdmin for managing, but maybe others can view? 
    # Prompt says: "Usuários comuns: apenas visualizar"
    
    month = request.args.get('month', date.today().month, type=int)
    year = request.args.get('year', date.today().year, type=int)
    
    # 1. Receita Bruta (Paid Transactions + Paid Service Orders + Paid Projects)
    # Since Transaction model seems to be the hub for payments, we sum all paid Transactions in the month
    revenue = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.company_id == current_user.company_id,
        Transaction.status == 'paid',
        extract('month', Transaction.paid_date) == month,
        extract('year', Transaction.paid_date) == year
    ).scalar() or 0.0
    
    def is_cost_active_in_month(cost, y, m):
        if cost.status != 'Ativo':
            return False
        
        # Start date
        start_y = int(cost.inicio_competencia[:4])
        start_m = int(cost.inicio_competencia[5:])
        
        if y < start_y or (y == start_y and m < start_m):
            return False # Not started yet
            
        if cost.total_parcelas and cost.total_parcelas > 0:
            # End date = Start Date + (total_parcelas - 1) months
            months_diff = (y - start_y) * 12 + (m - start_m)
            if months_diff >= cost.total_parcelas:
                return False # Installments finished
                
        return True

    # 2. Custos Fixos
    fixed_costs_query = FixedCost.query.filter(
        FixedCost.tenant_id == current_user.company_id,
        FixedCost.status == 'Ativo',
        FixedCost.inicio_competencia <= f"{year}-{month:02d}"
    ).all()
    
    # DEBUG: Log query results
    print(f"[DEBUG] tenant_id={current_user.company_id}, year={year}, month={month}")
    print(f"[DEBUG] Found {len(fixed_costs_query)} fixed costs")
    for cost in fixed_costs_query:
        print(f"[DEBUG] Cost: {cost.nome_custo} = R$ {cost.valor}, tipo={cost.tipo}, inicio={cost.inicio_competencia}, parcelas={cost.total_parcelas}")
    
    total_fixed_costs = 0.0
    for cost in fixed_costs_query:
        is_active = is_cost_active_in_month(cost, year, month)
        print(f"[DEBUG] {cost.nome_custo}: is_active={is_active}")
        if is_active:
            if cost.tipo == 'Anual Rateado':
                total_fixed_costs += float(cost.valor) / 12
            else:
                total_fixed_costs += float(cost.valor)
    
    print(f"[DEBUG] Total fixed costs calculated: R$ {total_fixed_costs}")

            
    # 3. Resultado Operacional
    operational_result = float(revenue) - total_fixed_costs
    
    # 4. Ponto de Equilíbrio (Fase 1: Ponto de equilíbrio = Custos Fixos)
    break_even = total_fixed_costs
    
    # Trend Data (Last 6 Months) - Optimized Refactor (Eliminated N+1)
    trend_data = []
    months_labels = []
    
    # Calculate month labels and date range
    for i in range(5, -1, -1):
        m = (month - i - 1) % 12 + 1
        y = year + (month - i - 1) // 12
        months_labels.append({
            'y': y,
            'm': m,
            'label': f"{m:02d}/{y}"
        })
    
    start_date = date(months_labels[0]['y'], months_labels[0]['m'], 1)
    # End of target month (last day of input month)
    if month == 12:
        end_date = date(year, 12, 31)
    else:
        end_date = date(year, month + 1, 1) - timedelta(days=1)

    # 1. Bulk Revenue Query (Single query for all 6 months)
    revenue_rows = db.session.query(
        extract('month', Transaction.paid_date).label('m'),
        extract('year', Transaction.paid_date).label('y'),
        func.sum(Transaction.amount)
    ).filter(
        Transaction.company_id == current_user.company_id,
        Transaction.status == 'paid',
        Transaction.paid_date >= start_date,
        Transaction.paid_date <= end_date
    ).group_by('y', 'm').all()
    
    # Map revenue for efficient lookup
    revenue_map = {(int(r.y), int(r.m)): float(r[2] or 0) for r in revenue_rows}

    # 2. Bulk Fixed Costs (One query instead of per month)
    # Fetch all potentially active costs for the company
    all_active_costs = FixedCost.query.filter(
        FixedCost.tenant_id == current_user.company_id,
        FixedCost.status == 'Ativo'
    ).all()

    # Assemble Trend Data (In-memory aggregation)
    for ml in months_labels:
        y, m = ml['y'], ml['m']
        
        # Get Revenue from map
        m_rev = revenue_map.get((y, m), 0.0)
        
        # Calculate Costs from pre-fetched list
        m_costs = 0.0
        for c in all_active_costs:
            if is_cost_active_in_month(c, y, m):
                if c.tipo == 'Anual Rateado':
                    m_costs += float(c.valor) / 12
                else:
                    m_costs += float(c.valor)
        
        trend_data.append({
            'label': ml['label'],
            'revenue': m_rev,
            'costs': m_costs,
            'result': m_rev - m_costs
        })

    return render_template('financial/strategic_dre.html',
                         revenue=revenue,
                         total_fixed_costs=total_fixed_costs,
                         operational_result=operational_result,
                         break_even=break_even,
                         month=month,
                         year=year,
                         trend_data=trend_data)

@financial_strategic_bp.route('/financial/strategic/fixed-costs')
@login_required
def fixed_costs():
    if not current_user.company_id:
        abort(403)
    
    costs = FixedCost.query.filter_by(tenant_id=current_user.company_id).order_by(FixedCost.inicio_competencia.desc()).all()
    users = User.query.filter_by(company_id=current_user.company_id).all()
    return render_template('financial/fixed_costs.html', costs=costs, users=users)

@financial_strategic_bp.route('/financial/strategic/fixed-costs/new', methods=['POST'])
@login_required
def add_fixed_cost():
    if not current_user.has_permission('admin_view'):
        abort(403)
        
    cost = FixedCost(
        tenant_id=current_user.company_id,
        nome_custo=request.form.get('nome_custo'),
        categoria=request.form.get('categoria'),
        valor=float(request.form.get('valor').replace(',', '.')),
        tipo=request.form.get('tipo'),
        status=request.form.get('status', 'Ativo'),
        observacao=request.form.get('observacao'),
        inicio_competencia=request.form.get('inicio_competencia'),
        total_parcelas=int(request.form.get('total_parcelas', 0) or 0),
        is_variable=bool(request.form.get('is_variable')),
        linked_user_id=int(request.form.get('linked_user_id')) if request.form.get('linked_user_id') else None,
        created_by=current_user.id
    )
    db.session.add(cost)
    
    # Audit Log
    log = StrategicAuditLog(
        tenant_id=current_user.company_id,
        user_id=current_user.id,
        action='CREATE',
        target_type='FixedCost',
        target_id=cost.id,
        changes=json.dumps({'new': {
            'nome': cost.nome_custo,
            'valor': float(cost.valor),
            'tipo': cost.tipo,
            'total_parcelas': cost.total_parcelas
        }})
    )
    db.session.add(log)
    
    db.session.commit()
    flash('Custo fixo adicionado com sucesso.', 'success')
    return redirect(url_for('financial_strategic.fixed_costs'))

@financial_strategic_bp.route('/financial/strategic/fixed-costs/api-update/<id>', methods=['POST'])
@login_required
def api_update_fixed_cost(id):
    if not current_user.has_permission('admin_view'):
        return jsonify({"error": "Forbidden"}), 403
        
    cost = FixedCost.query.get_or_404(id)
    if cost.tenant_id != current_user.company_id:
        return jsonify({"error": "Forbidden"}), 403
        
    data = request.json
    if 'is_variable' in data:
        cost.is_variable = bool(data['is_variable'])
    if 'linked_user_id' in data:
        cost.linked_user_id = int(data['linked_user_id']) if data['linked_user_id'] else None
        
    db.session.commit()
    return jsonify({"status": "success"})

@financial_strategic_bp.route('/financial/strategic/fixed-costs/generate-expenses', methods=['POST'])
@login_required
def generate_monthly_expenses():
    if not current_user.has_permission('admin_view'):
        abort(403)
        
    today = date.today()
    month = today.month
    year = today.year
    
    # 1. Helper to get or create category
    def get_category(name):
        cat = FinancialCategory.query.filter_by(company_id=current_user.company_id, name=name).first()
        if not cat:
            cat = FinancialCategory(name=name, type='expense', company_id=current_user.company_id)
            db.session.add(cat)
            db.session.flush()
        return cat

    # 2. Get active costs
    costs = FixedCost.query.filter_by(
        tenant_id=current_user.company_id,
        status='Ativo'
    ).all()
    
    # helper from dashboard route (duplicated here for simplicity or we could refactor)
    def is_active(cost, y, m):
        start_y = int(cost.inicio_competencia[:4])
        start_m = int(cost.inicio_competencia[5:])
        if y < start_y or (y == start_y and m < start_m): return False
        if cost.total_parcelas and cost.total_parcelas > 0:
            months_diff = (y - start_y) * 12 + (m - start_m)
            if months_diff >= cost.total_parcelas: return False
        return True

    generated_count = 0
    skipped_count = 0
    
    for cost in costs:
        if is_active(cost, year, month):
            # Check if already generated for this month
            # We look for an Expense linked to this fixed_cost_id with due date in this month
            existing = Expense.query.filter(
                Expense.fixed_cost_id == cost.id,
                extract('month', Expense.due_date) == month,
                extract('year', Expense.due_date) == year
            ).first()
            
            if existing:
                skipped_count += 1
                continue
                
            # Create Expense
            cat = get_category(cost.categoria)
            
            amount = float(cost.valor)
            if cost.tipo == 'Anual Rateado':
                amount = amount / 12
                
            new_expense = Expense(
                description=f"{cost.nome_custo} ({month:02d}/{year})",
                amount=amount,
                due_date=date(year, month, 5), # Default to 5th
                status='pending',
                category_id=cat.id,
                company_id=current_user.company_id,
                user_id=current_user.id,
                fixed_cost_id=cost.id
            )
            db.session.add(new_expense)
            generated_count += 1
            
    db.session.commit()
    
    # Audit Log
    log = StrategicAuditLog(
        tenant_id=current_user.company_id,
        user_id=current_user.id,
        action='GENERATE_EXPENSES',
        target_type='Expense',
        changes=json.dumps({'generated': generated_count, 'skipped': skipped_count})
    )
    db.session.add(log)
    db.session.commit()
    
    flash(f'Sucesso: {generated_count} despesas geradas. {skipped_count} já existiam.', 'success')
    return redirect(url_for('financial_strategic.fixed_costs'))

@financial_strategic_bp.route('/financial/strategic/fixed-costs/edit/<id>', methods=['POST'])
@login_required
def edit_fixed_cost(id):
    if not current_user.has_permission('admin_view'):
        abort(403)
        
    cost = FixedCost.query.get_or_404(id)
    if cost.tenant_id != current_user.company_id:
        abort(403)
        
    old_data = {
        'nome': cost.nome_custo,
        'valor': float(cost.valor),
        'tipo': cost.tipo,
        'status': cost.status
    }
    
    cost.nome_custo = request.form.get('nome_custo')
    cost.categoria = request.form.get('categoria')
    cost.valor = float(request.form.get('valor').replace(',', '.'))
    cost.tipo = request.form.get('tipo')
    cost.status = request.form.get('status', 'Ativo')
    cost.observacao = request.form.get('observacao')
    cost.inicio_competencia = request.form.get('inicio_competencia')
    cost.total_parcelas = int(request.form.get('total_parcelas', 0) or 0)
    cost.is_variable = bool(request.form.get('is_variable'))
    cost.linked_user_id = int(request.form.get('linked_user_id')) if request.form.get('linked_user_id') else None
    cost.updated_by = current_user.id
    cost.updated_at = get_now_br()
    
    # Audit Log
    log = StrategicAuditLog(
        tenant_id=current_user.company_id,
        user_id=current_user.id,
        action='UPDATE',
        target_type='FixedCost',
        target_id=cost.id,
        changes=json.dumps({
            'old': old_data,
            'new': {
                'nome': cost.nome_custo,
                'valor': float(cost.valor),
                'tipo': cost.tipo,
                'status': cost.status,
                'total_parcelas': cost.total_parcelas
            }
        })
    )
    db.session.add(log)
    
    db.session.commit()
    flash('Custo fixo atualizado com sucesso.', 'success')
    return redirect(url_for('financial_strategic.fixed_costs'))

@financial_strategic_bp.route('/financial/strategic/fixed-costs/delete/<id>', methods=['POST'])
@login_required
def delete_fixed_cost(id):
    if not current_user.has_permission('admin_view'):
        abort(403)
        
    cost = FixedCost.query.get_or_404(id)
    if cost.tenant_id != current_user.company_id:
        abort(403)
        
    # Audit Log before deletion
    log = StrategicAuditLog(
        tenant_id=current_user.company_id,
        user_id=current_user.id,
        action='DELETE',
        target_type='FixedCost',
        target_id=cost.id,
        changes=json.dumps({'deleted': {'nome': cost.nome_custo, 'valor': float(cost.valor)}})
    )
    db.session.add(log)
    
    db.session.delete(cost)
    db.session.commit()
    flash('Custo fixo removido com sucesso.', 'warning')
    return redirect(url_for('financial_strategic.fixed_costs'))

@financial_strategic_bp.route('/financial/strategic/import', methods=['POST'])
@login_required
def import_csv():
    if not current_user.has_permission('admin_view'):
        abort(403)

    if 'file' not in request.files:
        flash('Arquivo não enviado.', 'error')
        return redirect(url_for('financial_strategic.fixed_costs'))

    file = request.files['file']
    if file.filename == '':
        flash('Arquivo vazio.', 'error')
        return redirect(url_for('financial_strategic.fixed_costs'))

    try:
        content = file.stream.read().decode("utf-8")
        stream = io.StringIO(content)
        # Use csv.DictReader or detected delimiter
        delimiter = ';' if ';' in content else ','
        reader = csv.DictReader(stream, delimiter=delimiter)
        
        success_count = 0
        error_logs = []
        
        valid_categories = ['Equipe', 'Ferramenta', 'Estrutura', 'Impostos', 'Outros', 'Investimento']
        valid_types = ['Mensal', 'Anual Rateado']
        
        row_num = 1 # Header is row 0 technically in count
        for row in reader:
            row_num += 1
            errors = []
            
            nome = row.get('nome_custo', '').strip()
            cat = row.get('categoria', '').strip()
            valor_str = row.get('valor', '').replace(',', '.').strip()
            tipo = row.get('tipo', '').strip()
            comp = row.get('inicio_competencia', '').strip()
            parcelas_str = row.get('total_parcelas', '0').strip()
            
            # Validations
            if not nome:
                errors.append("nome_custo não pode ser vazio")
            if cat not in valid_categories:
                errors.append(f"categoria inválida '{cat}'")
            
            valor = 0.0
            try:
                valor = float(valor_str)
                if valor <= 0:
                    errors.append("valor deve ser maior que zero")
            except:
                errors.append(f"valor inválido '{valor_str}'")
                
            if tipo not in valid_types:
                errors.append("tipo deve ser 'Mensal' ou 'Anual Rateado'")
            
            total_parcelas = 0
            try:
                total_parcelas = int(parcelas_str or 0)
            except:
                errors.append(f"total_parcelas inválido '{parcelas_str}'")
            
            # YYYY-MM validation
            try:
                datetime.strptime(comp, '%Y-%m-%d') # The prompt said YYYY-MM but standard CSVs might have more.
            except:
                if len(comp) == 7 and comp[4] == '-':
                    pass # Fine
                else:
                    errors.append(f"inicio_competencia formato inválido '{comp}' (esperado YYYY-MM)")

            # Duplicates check
            if not errors:
                exists = FixedCost.query.filter_by(
                    tenant_id=current_user.company_id,
                    nome_custo=nome,
                    valor=valor,
                    inicio_competencia=comp
                ).first()
                if exists:
                    errors.append("registro duplicado detectado")

            if errors:
                for err in errors:
                    error_logs.append(f"Linha {row_num}: {err}")
            else:
                cost = FixedCost(
                    tenant_id=current_user.company_id,
                    nome_custo=nome,
                    categoria=cat,
                    valor=valor,
                    tipo=tipo,
                    status='Ativo',
                    observacao=row.get('observacao', ''),
                    inicio_competencia=comp,
                    total_parcelas=total_parcelas,
                    created_by=current_user.id
                )
                db.session.add(cost)
                success_count += 1

        if success_count > 0:
            # Audit Import
            log = StrategicAuditLog(
                tenant_id=current_user.company_id,
                user_id=current_user.id,
                action='IMPORT',
                target_type='FixedCost',
                changes=json.dumps({'count': success_count})
            )
            db.session.add(log)
            db.session.commit()
            flash(f'{success_count} registros importados com sucesso.', 'success')
        
        if error_logs:
            for log in error_logs:
                flash(log, 'error')
                
    except Exception as e:
        flash(f'Erro ao processar CSV: {str(e)}', 'error')

    return redirect(url_for('financial_strategic.fixed_costs'))

@financial_strategic_bp.route('/financial/strategic/export-pdf')
@login_required
def export_pdf():
    # To be implemented using PDF service
    flash('Funcionalidade de exportação PDF em desenvolvimento.', 'info')
    return redirect(url_for('financial_strategic.dashboard'))
