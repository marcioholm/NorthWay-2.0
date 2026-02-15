from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from models import db, Transaction, ServiceOrder, FixedCost, StrategicAuditLog, get_now_br, ROLE_ADMIN
from sqlalchemy import func, extract
from datetime import datetime, date
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
    
    total_fixed_costs = 0.0
    for cost in fixed_costs_query:
        if is_cost_active_in_month(cost, year, month):
            if cost.tipo == 'Anual Rateado':
                total_fixed_costs += float(cost.valor) / 12
            else:
                total_fixed_costs += float(cost.valor)
            
    # 3. Resultado Operacional
    operational_result = float(revenue) - total_fixed_costs
    
    # 4. Ponto de Equilíbrio (Fase 1: Ponto de equilíbrio = Custos Fixos)
    break_even = total_fixed_costs
    
    # Trend Data (Last 6 Months)
    trend_data = []
    for i in range(5, -1, -1):
        d = date(year, month, 1)
        # Simple month subtraction helper
        m = (month - i - 1) % 12 + 1
        y = year + (month - i - 1) // 12
        
        # Monthly Revenue
        m_rev = db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.company_id == current_user.company_id,
            Transaction.status == 'paid',
            extract('month', Transaction.paid_date) == m,
            extract('year', Transaction.paid_date) == y
        ).scalar() or 0.0
        
        # Monthly Fixed Costs
        m_costs_q = FixedCost.query.filter(
            FixedCost.tenant_id == current_user.company_id,
            FixedCost.status == 'Ativo',
            FixedCost.inicio_competencia <= f"{y}-{m:02d}"
        ).all()
        m_costs = 0.0
        for c in m_costs_q:
            if is_cost_active_in_month(c, y, m):
                if c.tipo == 'Anual Rateado':
                    m_costs += float(c.valor) / 12
                else:
                    m_costs += float(c.valor)
        
        trend_data.append({
            'label': f"{m:02d}/{y}",
            'revenue': float(m_rev),
            'costs': m_costs,
            'result': float(m_rev) - m_costs
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
    return render_template('financial/fixed_costs.html', costs=costs)

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
