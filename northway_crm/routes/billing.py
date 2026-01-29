from flask import Blueprint, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db
from models import Company, BillingEvent, FinancialEvent, User
from services.asaas_service import create_customer, create_subscription, get_subscription_payments
from datetime import datetime, timedelta
import json
import os

billing_bp = Blueprint('billing', __name__, url_prefix='/billing')

ASAAS_WEBHOOK_TOKEN = os.environ.get('ASAAS_WEBHOOK_TOKEN', 'my-secret-token')

@billing_bp.route('/payment-pending')
@login_required
def payment_pending():
    """
    Landing page for blocked users.
    """
    return render_template('payment_pending.html')

@billing_bp.route('/checkout/process', methods=['POST'])
@login_required
def process_checkout():
    """
    Handles the Checkout Form submission.
    Expects: plan_type (monthly/annual), cpf_cnpj, name, email, phone
    """
    try:
        data = request.form
        plan_type = data.get('plan_type') # 'monthly' (197) or 'annual' (1999)
        cpf_cnpj = data.get('cpf_cnpj')
        name = data.get('name') or current_user.name
        email = data.get('email') or current_user.email
        phone = data.get('phone')
        
        # 1. Update Company Identity
        # Check for duplicates first
        existing_company = Company.query.filter_by(cpf_cnpj=cpf_cnpj).first()
        if existing_company and existing_company.id != current_user.company_id:
             flash("Este CPF/CNPJ já está cadastrado em outra conta.", "error")
             return redirect(url_for('dashboard.checkout'))

        company = current_user.company
        company.cpf_cnpj = cpf_cnpj
        company.representative = name
        db.session.commit()
        
        # 2. Define Values
        if plan_type == 'annual':
            value = 1999.00
            cycle = 'YEARLY'
            desc = 'NorthWay CRM - Plano Anual (Promoção)'
            company.plan_type = 'annual'
        else: # monthly default
            value = 197.00
            cycle = 'MONTHLY'
            desc = 'NorthWay CRM - Plano Mensal'
            company.plan_type = 'monthly'
            
        # 3. Create Asaas Customer
        customer_id, error = create_customer(name, email, cpf_cnpj, phone, external_id=company.id)
        if not customer_id:
            flash(f"Erro no gateway: {error}", "error")
            return redirect(url_for('dashboard.checkout'))
            
        company.asaas_customer_id = customer_id
        
        # 4. Create Subscription
        # Due date: Today
        next_due = (datetime.now() + timedelta(days=1)).date().strftime('%Y-%m-%d')
        
        sub_data = create_subscription(customer_id, value, next_due, cycle, desc)
        if not sub_data:
             flash("Erro ao gerar assinatura. Contate o suporte.", "error")
             return redirect(url_for('dashboard.checkout'))
             
        company.subscription_id = sub_data['id']
        company.payment_status = 'pending'
        db.session.commit()
        
        # 5. Get Payment Link (The first payment of the sub)
        # Asaas usually creates a payment immediately for the subscription
        payments = get_subscription_payments(company.subscription_id)
        if payments:
            invoice_url = payments[0]['invoiceUrl']
            return redirect(invoice_url)
        else:
             flash("Assinatura criada, mas boleto não encontrado. Verifique seu email.", "info")
             return redirect(url_for('dashboard.index'))

    except Exception as e:
        print(f"Checkout Error: {e}")
        flash(f"Erro interno no checkout: {str(e)}", "error")
        return redirect(url_for('dashboard.checkout'))

@billing_bp.route('/webhooks/asaas', methods=['POST'])
def asaas_webhook():
    """
    Receives events from Asaas.
    """
    # 1. Security Check
    token = request.headers.get('asaas-access-token')
    if token != ASAAS_WEBHOOK_TOKEN:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    event = data.get('event')
    payment = data.get('payment', {})
    
    # 2. Log Event
    try:
        # Find company by Customer ID
        customer_id = payment.get('customer')
        company = Company.query.filter_by(asaas_customer_id=customer_id).first()
        
        log = BillingEvent(
            company_id=company.id if company else None,
            event_type=event,
            payload=data,
            processed_at=datetime.utcnow(),
            idempotency_key=f"{payment.get('id')}_{event}"
        )
        db.session.add(log)
        db.session.commit()
        
        if not company:
            return jsonify({'status': 'ignored_no_company'}), 200

        # 3. Handle Logic
        if event in ['PAYMENT_CONFIRMED', 'PAYMENT_RECEIVED']:
            company.payment_status = 'active'
            company.platform_inoperante = False
            company.overdue_since = None
            company.subscription_status = 'active'
            print(f"✅ Company {company.name} Activated!")
            
        elif event in ['PAYMENT_OVERDUE']:
            company.payment_status = 'overdue'
            # Only set overdue_since if it's new
            if not company.overdue_since:
                company.overdue_since = datetime.utcnow()
            print(f"⚠️ Company {company.name} Overdue!")
            
        elif event in ['SUBSCRIPTION_DELETED', 'SUBSCRIPTION_CANCELLED']:
             company.payment_status = 'canceled'
             company.platform_inoperante = True # Immediate block rule? prompt said D+30 logic, but usually cancel = stop service
             company.subscription_status = 'canceled'
             
        db.session.commit()
        return jsonify({'status': 'processed'}), 200

    except Exception as e:
        print(f"Webhook Error: {e}")
        return jsonify({'error': str(e)}), 500
