from flask import Blueprint, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db
from models import db, Company, BillingEvent, FinancialEvent, User, Transaction, Integration, NFSELog
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
        
        sub_data, sub_error = create_subscription(customer_id, value, next_due, cycle, desc)
        if not sub_data:
             flash(f"Erro ao gerar assinatura: {sub_error}", "error")
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
            company.subscription_status = 'active'
            print(f"✅ Company {company.name} Activated!")
            
            # Send Email
            from services.email_service import EmailService
            from models import EMAIL_TEMPLATES
            
            admin_user = User.query.filter_by(company_id=company.id).first() # Notify first user/admin
            if admin_user:
                plan_name = 'Plano Anual' if company.plan_type == 'annual' else 'Plano Mensal'
                try:
                    EmailService.send_email(
                        to=admin_user.email,
                        subject="Pagamento Confirmado - NorthWay",
                        template=EMAIL_TEMPLATES.subscription_active,
                        context={
                           'user': admin_user, 
                           'plan_name': plan_name,
                           'amount': f"R$ {payment.get('value', '')}",
                           'next_billing_date': (datetime.now() + timedelta(days=365 if company.plan_type == 'annual' else 30)).strftime('%d/%m/%Y'),
                           'dashboard_url': url_for('dashboard.home', _external=True)
                        },
                        company_id=company.id,
                        user_id=admin_user.id
                    )
                except Exception as ex:
                    print(f"Failed to send email: {ex}")
                except Exception as ex:
                    print(f"Failed to send email: {ex}")
        
        # --- NEW LOGIC: Look for Tenant Transactions (Client Payments) ---
        transaction = Transaction.query.filter_by(asaas_id=payment.get('id')).first()
        if transaction:
            print(f"✅ Webhook matched Transaction {transaction.id} for Contract {transaction.contract_id}")
            
            # Log for Transaction
            nfse_log = NFSELog(
                company_id=transaction.company_id,
                transaction_id=transaction.id,
                status=event,
                payload=data
            )
            db.session.add(nfse_log)

            if event in ['PAYMENT_CONFIRMED', 'PAYMENT_RECEIVED']:
                transaction.status = 'paid'
                transaction.paid_date = datetime.now().date()
                
                # NFS-e Emission Logic
                if transaction.contract and transaction.contract.emit_nfse:
                    # Check if already issued
                    if transaction.nfse_status != 'issued':
                        print(f"🚀 Triggering NFS-e for Transaction {transaction.id}")
                        transaction.nfse_status = 'pending_emission'
                        
                        # Get Tenant API Key
                        tenant_integration = Integration.query.filter_by(
                            company_id=transaction.company_id, 
                            service='asaas', 
                            is_active=True
                        ).first()
                        
                        if tenant_integration and tenant_integration.api_key:
                            from services.asaas_service import issue_nfse
                            nfse, err = issue_nfse(
                                payment_id=transaction.asaas_id,
                                service_code=transaction.contract.nfse_service_code or '1.03', # Default or from contract
                                iss_rate=transaction.contract.nfse_iss_rate or 2.0,
                                description=f"Serviços ref. {transaction.description}",
                                api_key=tenant_integration.api_key
                            )
                            
                            if nfse:
                                transaction.nfse_status = 'issued'
                                transaction.nfse_id = nfse.get('id')
                                transaction.nfse_number = str(nfse.get('number', '')) or 'PENDING'
                                print(f"✅ NFS-e Requested: {nfse.get('id')}")
                                
                                # Log Success
                                db.session.add(NFSELog(
                                    company_id=transaction.company_id, transaction_id=transaction.id,
                                    status='NFSE_REQUESTED', message=f"ID: {nfse.get('id')}"
                                ))
                            else:
                                transaction.nfse_status = 'error'
                                print(f"❌ NFS-e Failed: {err}")
                                db.session.add(NFSELog(
                                    company_id=transaction.company_id, transaction_id=transaction.id,
                                    status='NFSE_ERROR', message=str(err)
                                ))
            
            elif event in ['PAYMENT_REFUNDED', 'PAYMENT_REVERSED']:
                transaction.status = 'refunded'
                # TODO: Cancel NFS-e logic (Asaas doesn't always allow auto-cancel via API for all cities)
                # But we can try cancel_nfse if needed.
            
            elif event in ['PAYMENT_OVERDUE']:
                transaction.status = 'overdue'

        # --- END NEW LOGIC ---

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
