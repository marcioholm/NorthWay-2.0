
from models import db, User, Contract, CommissionSnapshot, CommissionRule, AccountsPayable, Task
from datetime import datetime
import json
from decimal import Decimal

class CommissionService:
    @staticmethod
    def get_user_closings_count(user_id, company_id, competence):
        """Counts how many closures (Contracts or SOs) a user made in a specific competence (YYYY-MM)."""
        count = CommissionSnapshot.query.filter_by(
            beneficiario_id=user_id,
            competencia_fechamento=competence
        ).count()
        return count

    @staticmethod
    def calculate_percent_for_tier(rule, count):
        """Calculates the percentage based on FAIXA_MENSAL_UNICA parameters."""
        params = rule.parametros
        if rule.modelo == 'FAIXA_MENSAL_UNICA':
            faixas = params.get('faixas_por_quantidade', [])
            # Sort faixas by min just in case
            faixas = sorted(faixas, key=lambda x: x['min'])
            
            percentual = 0
            for faixa in faixas:
                if count >= faixa['min'] and count <= faixa.get('max', 999999):
                    percentual = faixa['percentual']
            return percentual
        elif rule.modelo == 'PERCENTUAL_FIXO_LIFETIME':
            return params.get('percentual', 0)
        return 0

    @classmethod
    def create_snapshot(cls, user, contract=None, service_order=None):
        """Creates a commission snapshot when a contract or service order is closed."""
        if not user or not user.papel_comercial_id or not user.regra_comissao_id:
            return None # No commercial rule for this user

        rule = CommissionRule.query.get(user.regra_comissao_id)
        if not rule or not rule.ativo:
            return None

        competence = datetime.now().strftime('%Y-%m')
        
        # Current count in the month (including this one soon)
        count = cls.get_user_closings_count(user.id, user.company_id, competence) + 1
        
        percentual = cls.calculate_percent_for_tier(rule, count)

        snapshot = CommissionSnapshot(
            contract_id=contract.id if contract else None,
            service_order_id=service_order.id if service_order else None,
            beneficiario_id=user.id,
            papel_comercial_id=user.papel_comercial_id,
            regra_id=rule.id,
            modelo=rule.modelo,
            percentual_provisorio=percentual,
            competencia_fechamento=competence,
            base_calculo=rule.parametros.get('base', 'valor_pago'),
            recorrente=rule.parametros.get('recorrente_lifetime', True) if contract else False
        )
        db.session.add(snapshot)
        
        # Trigger Adjustment Check
        if rule.modelo == 'FAIXA_MENSAL_UNICA' and rule.parametros.get('modo_ajuste') == 'AJUSTE_AUTOMATICO':
            cls.check_and_generate_adjustments(user.id, competence, percentual)

        return snapshot

    @classmethod
    def check_and_generate_adjustments(cls, user_id, competence, new_percent):
        """
        If the tier increased, find all previous commissions for this month/user 
        and generate adjustment records.
        """
        # Find all CommissionSnapshots for this user in this month
        snapshots = CommissionSnapshot.query.filter_by(
            beneficiario_id=user_id,
            competencia_fechamento=competence
        ).all()

        for snap in snapshots:
            # Update snapshot definitively if not already higher
            if snap.percentual_provisorio < new_percent:
                old_percent = snap.percentual_provisorio
                snap.percentual_definitivo = new_percent
                
                # Check all PAID commissions (AccountsPayable) for this contract in this competence
                # that were calculated with the old percentage.
                payables = AccountsPayable.query.filter_by(
                    beneficiario_id=user_id,
                    contract_id=snap.contract_id,
                    competence=competence,
                    eh_ajuste=False
                ).all()

                for p in payables:
                    # If this specific payment was calculated with a lower percentage
                    if p.percentual_aplicado < new_percent:
                        diff_percent = new_percent - p.percentual_aplicado
                        diff_value = Decimal(str(p.valor_base_contratual)) * (Decimal(str(diff_percent)) / Decimal('100'))
                        
                        if diff_value > 0:
                            adjustment = AccountsPayable(
                                tenant_id=p.tenant_id,
                                tipo='COMISSAO',
                                beneficiario_id=user_id,
                                contract_id=snap.contract_id,
                                cliente_id=p.cliente_id,
                                competencia=competence,
                                valor_base_contratual=p.valor_base_contratual,
                                valor_pago_cliente_total=p.valor_pago_cliente_total,
                                percentual_aplicado=diff_percent,
                                valor_comissao_calculado=diff_value,
                                eh_ajuste=True,
                                referencia_comissao_id=p.id,
                                status='A_PAGAR'
                            )
                            db.session.add(adjustment)
                            
                            # Update p.percentual_aplicado? 
                            # No, we keep it as reference. The sum of p + adjustments = final commission.
                            
                            # Create Task for adjustment
                            cls.create_finance_task(adjustment, is_adjustment=True)

    @staticmethod
    def create_finance_task(payable, is_adjustment=False):
        """Creates a task for the finance team to pay the commission."""
        beneficiary = User.query.get(payable.beneficiario_id)
        beneficiary_name = beneficiary.name if beneficiary else "Colaborador"
        
        client_name = "Cliente"
        if payable.cliente_obj:
            client_name = payable.client_obj.name

        title = f"Pagar comissão – {beneficiary_name} – {client_name}"
        if is_adjustment:
            title = f"AJUSTE: {title}"

        desc = f"Comissão gerada para o colaborador {beneficiary_name}.\n"
        desc += f"Competência: {payable.competencia}\n"
        if is_adjustment:
            desc += "Motivo: Ajuste automático por mudança de faixa mensal.\n"
        
        desc += f"Percentual: {payable.percentual_aplicado}%\n"
        desc += f"Valor Base (Contratual): R$ {payable.valor_base_contratual:,.2f}\n"
        desc += f"Valor Comissão: R$ {payable.valor_comissao_calculado:,.2f}\n"
        
        # Link to accounts payable (pseudo-link for now)
        desc += f"\nID Financeiro: {payable.id}"

        # Find an Admin to assign to
        admin = User.query.filter_by(company_id=payable.tenant_id, role='admin').first()
        
        task = Task(
            company_id=payable.tenant_id,
            title=title,
            description=desc,
            due_date=datetime.now() + timedelta(days=1),
            priority='alta',
            status='pendente',
            assigned_to_id=admin.id if admin else None,
            category='financeiro'
        )
        db.session.add(task)

    @classmethod
    def process_payment_received(cls, transaction, payload):
        """
        Hooked into Asaas Webhook. 
        Generates commission record when payment is confirmed.
        """
        # Commission can come from Contract or Service Order
        contract = transaction.contract
        service_order = transaction.service_order
        
        if not contract and not service_order:
            return

        # Find the snapshot for this specific close
        if contract:
            snapshot = CommissionSnapshot.query.filter_by(contract_id=contract.id).first()
        else:
            snapshot = CommissionSnapshot.query.filter_by(service_order_id=service_order.id).first()
            
        if not snapshot:
            return # No commission set for this closure

        # 1. Base Logic: Only Contract Value
        valor_base = Decimal(str(transaction.amount)) # valor nominal da parcela
        
        # From Payload
        juros = Decimal(str(payload.get('payment', {}).get('interestValue', 0) or 0))
        multa = Decimal(str(payload.get('payment', {}).get('fineValue', 0) or 0))
        valor_total_pago = Decimal(str(payload.get('payment', {}).get('value', 0)))

        # 2. Get Percent
        # For PJ with tiers, we use the current tier.
        percentual = snapshot.percentual_provisorio
        if snapshot.percentual_definitivo:
            percentual = snapshot.percentual_definitivo
        
        valor_comissao = valor_base * (Decimal(str(percentual)) / Decimal('100'))

        # 3. Create Accounts Payable
        payable = AccountsPayable(
            tenant_id=transaction.company_id,
            tipo='COMISSAO',
            beneficiario_id=snapshot.beneficiario_id,
            contract_id=contract.id if contract else None,
            service_order_id=service_order.id if service_order else None,
            cliente_id=contract.client_id if contract else service_order.client_id,
            asaas_payment_id=transaction.asaas_id,
            competencia=datetime.now().strftime('%Y-%m'), 
            
            valor_base_contratual=valor_base,
            valor_pago_cliente_total=valor_total_pago,
            juros_cliente=juros,
            multa_cliente=multa,
            
            percentual_aplicado=percentual,
            valor_comissao_calculado=valor_comissao,
            status='A_PAGAR'
        )
        db.session.add(payable)
        
        # 4. Task
        cls.create_finance_task(payable)

from datetime import timedelta
