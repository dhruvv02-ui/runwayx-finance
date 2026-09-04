import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

def generate_synthetic_data(n=70, seed=None):
    if seed is not None:
        np.random.seed(seed)
        random.seed(seed)
    else:
        np.random.seed()
        random.seed()
    
    base_date = datetime.now()
    
    customers = [
        "Aarav Sharma", "Priya Patel", "Rohan Mehta", "Sneha Rao", "Vikram Singh", 
        "Ananya Iyer", "Aditya Verma", "Kavya Nair", "Rajesh Gupta", "Meera Joshi"
    ]
    
    ledger_records = []
    for i in range(1, n + 1):
        order_id = f"ORD-{2026000 + i}"
        invoice_id = f"INV-{1000 + i}"
        customer = random.choice(customers)
        amount = round(random.uniform(1000, 20000), 2)
        date = (base_date + timedelta(days=random.randint(0, 18), hours=random.randint(9, 18))).strftime("%Y-%m-%d %H:%M:%S")
        
        ledger_records.append({
            "order_id": order_id,
            "invoice_id": invoice_id,
            "customer_name": customer,
            "ledger_amount": amount,
            "ledger_date": date,
            "ledger_status": "COMPLETED"
        })
    
    df_ledger = pd.DataFrame(ledger_records)
    
    bank_records = []
    
    for idx in range(0, 35):
        row = df_ledger.iloc[idx]
        utr = f"UTR{random.randint(100000000000, 999999999999)}"
        txn_date = (datetime.strptime(row["ledger_date"], "%Y-%m-%d %H:%M:%S") + timedelta(hours=random.randint(2, 24))).strftime("%Y-%m-%d %H:%M:%S")
        bank_records.append({
            "utr_number": utr,
            "bank_amount": row["ledger_amount"],
            "bank_date": txn_date,
            "narration": f"CMS/Razorpay/Settlement/{row['order_id']}/{row['customer_name'].replace(' ', '')}"
        })
    
    for idx in range(35, 45):
        row = df_ledger.iloc[idx]
        utr = f"UTR{random.randint(100000000000, 999999999999)}"
        txn_date = (datetime.strptime(row["ledger_date"], "%Y-%m-%d %H:%M:%S") + timedelta(hours=random.randint(2, 24))).strftime("%Y-%m-%d %H:%M:%S")
        
        mdr_fee = row["ledger_amount"] * 0.02
        gst_on_fee = mdr_fee * 0.18
        net_bank_amount = round(row["ledger_amount"] - (mdr_fee + gst_on_fee), 2)
        
        bank_records.append({
            "utr_number": utr,
            "bank_amount": net_bank_amount,
            "bank_date": txn_date,
            "narration": f"RZP_SETTLE_NET_MDR_GST_{row['order_id']}"
        })
        
    for idx in range(45, 52):
        row = df_ledger.iloc[idx]
        utr = f"UTR{random.randint(100000000000, 999999999999)}"
        txn_date = (datetime.strptime(row["ledger_date"], "%Y-%m-%d %H:%M:%S") + timedelta(hours=random.randint(2, 24))).strftime("%Y-%m-%d %H:%M:%S")
        
        first_name = row['customer_name'].split()[0]
        bank_records.append({
            "utr_number": utr,
            "bank_amount": row["ledger_amount"],
            "bank_date": txn_date,
            "narration": f"UPI/TXN/{first_name.upper()}/DIRECT_TRANSFER_NO_REF"
        })

    b1_rows = df_ledger.iloc[52:55]
    b1_gross = b1_rows["ledger_amount"].sum()
    b1_net = round(b1_gross * (1 - (0.02 * 1.18)), 2)
    b1_orders = "+".join(b1_rows["order_id"].tolist())
    bank_records.append({
        "utr_number": f"UTR_BATCH_{random.randint(100000, 999999)}",
        "bank_amount": b1_net,
        "bank_date": (base_date + timedelta(days=12)).strftime("%Y-%m-%d %H:%M:%S"),
        "narration": f"RZP_AGGREGATE_BATCH_SETTLE:[{b1_orders}]"
    })

    b2_rows = df_ledger.iloc[55:58]
    b2_gross = b2_rows["ledger_amount"].sum()
    b2_net = round(b2_gross * (1 - (0.02 * 1.18)), 2)
    b2_orders = "+".join(b2_rows["order_id"].tolist())
    bank_records.append({
        "utr_number": f"UTR_BATCH_{random.randint(100000, 999999)}",
        "bank_amount": b2_net,
        "bank_date": (base_date + timedelta(days=15)).strftime("%Y-%m-%d %H:%M:%S"),
        "narration": f"RZP_AGGREGATE_BATCH_SETTLE:[{b2_orders}]"
    })

    for k in range(1, 6):
        extra_utr = f"UTR_UNKNOWN_{k:05d}"
        extra_date = (base_date + timedelta(days=random.randint(5, 20))).strftime("%Y-%m-%d %H:%M:%S")
        bank_records.append({
            "utr_number": extra_utr,
            "bank_amount": round(random.uniform(2000, 15000), 2),
            "bank_date": extra_date,
            "narration": f"NEFT_UNKNOWN_COUNTERPARTY_PAYMENT_SLOT_{k}"
        })
        
    df_bank = pd.DataFrame(bank_records)
    
    df_ledger.to_csv("internal_ledger.csv", index=False)
    df_bank.to_csv("bank_statement.csv", index=False)
    return df_ledger, df_bank

if __name__ == "__main__":
    generate_synthetic_data(70)