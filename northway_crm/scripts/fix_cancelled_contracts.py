
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import Contract, Transaction, Client
from services.asaas_service import AsaasService
from datetime import datetime

def fix_cancelled_contracts():
    with app.app_context():
        print("--- Starting Cleanup for Contracts ---")
        
        # DEBUG: Find Client
        lucas = Client.query.filter(Client.name.like('%Lucas Renato%')).first()
        if lucas:
            print(f"Found Client: {lucas.name} (ID: {lucas.id})")
            # Get his contracts
            for c in lucas.contracts:
                 print(f"  > Contract #{c.id} Status: {c.status}")
                 # List pending transactions
                 pxts = Transaction.query.filter_by(contract_id=c.id, status='pending').all()
                 print(f"    Pending TXs: {len(pxts)}")
                 if pxts:
                     print(f"    Sample: {pxts[0].description}")
        else:
            print("Client 'Lucas Renato' NOT FOUND.")

        # DEBUG: Check recent transactions
        last_txs = Transaction.query.order_by(Transaction.id.desc()).limit(5).all()
        print(f"Recent TX Descriptions: {[t.description for t in last_txs]}")
        
        # ... rest of script ...
        total_cancelled_tx = 0

        
        # 0. Debug Statuses
        statuses = db.session.query(Contract.status).distinct().all()
        print(f"DEBUG: All Contract Statuses in DB: {[s[0] for s in statuses]}")

        # --- PART 1: Cleanup ALREADY CANCELLED contracts that have pending TXs ---
        cancelled_contracts = Contract.query.filter(Contract.status.in_(['cancelled', 'terminated'])).all()
        print(f"Found {len(cancelled_contracts)} cancelled contracts.")
        
        for contract in cancelled_contracts:
            # Check for ANY pending/overdue transactions
            bad_txs = Transaction.query.filter(
                Transaction.contract_id == contract.id,
                Transaction.status.in_(['pending', 'overdue'])
            ).all()
            
            if bad_txs:
                print(f"Contract #{contract.id} ({contract.client.name}) [Status: {contract.status}]: Found {len(bad_txs)} pending transactions.")
                for tx in bad_txs:
                    if tx.description.startswith("Multa Rescisória"):
                        continue # Skip the fee itself, it might be pending payment
                        
                    print(f"  Cancelling TX #{tx.id} ({tx.description})")
                    tx.status = 'cancelled'
                    total_cancelled_tx += 1
                    if tx.asaas_id:
                        try:
                            AsaasService.cancel_payment(contract.company_id, tx.asaas_id)
                        except: pass
        
        # --- PART 2: Find BROKEN cancellations (Active status + Termination Fee) ---
        print("\n--- Searching for Broken Cancellations (Fee exists but Contract Active) ---")
        termination_fees = Transaction.query.filter(Transaction.description.like('Multa Rescisória%')).all()
        
        broken_contracts = set()
        for fee in termination_fees:
            contract = Contract.query.get(fee.contract_id)
            if contract and contract.status not in ['cancelled', 'terminated']:
                print(f"Found Broken Contract #{contract.id} (Status: {contract.status}). Has Termination Fee TX #{fee.id}.")
                broken_contracts.add(contract)
        
        if not broken_contracts:
            print("No broken cancellations found.")
        
        for contract in broken_contracts:
             print(f"Fixing Contract #{contract.id} ({contract.client.name})...")
             contract.status = 'cancelled'
             contract.cancellation_date = datetime.now()
             contract.cancellation_reason = "Correction: Forced cancellation via script"
             
             # Cancel Pending
             bad_txs = Transaction.query.filter(
                Transaction.contract_id == contract.id,
                Transaction.status.in_(['pending', 'overdue'])
             ).all()
             
             count = 0
             for tx in bad_txs:
                 if tx.description.startswith("Multa Rescisória"):
                     continue 
                 tx.status = 'cancelled'
                 count += 1
                 if tx.asaas_id:
                     try: AsaasService.cancel_payment(contract.company_id, tx.asaas_id)
                     except: pass
            
             print(f"  > Cancelled {count} pending installments.")
             total_cancelled_tx += count
        
        if total_cancelled_tx > 0 or broken_contracts:
            db.session.commit()
            print(f"\nSUCCESS: Fixed {len(broken_contracts)} broken contracts and cancelled {total_cancelled_tx} transactions.")
        else:
            print("\nNothing to fix.")

if __name__ == "__main__":
    fix_cancelled_contracts()
