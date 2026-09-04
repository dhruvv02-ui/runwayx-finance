import pandas as pd
import numpy as np
import re

class AIFinanceController:
    def __init__(self, ledger_df, bank_df, l_map=None, b_map=None, *args, **kwargs):
        self.ledger_raw = ledger_df.copy()
        self.bank_raw = bank_df.copy()
        
        self.ledger_raw.columns = self.ledger_raw.columns.astype(str).str.strip()
        self.bank_raw.columns = self.bank_raw.columns.astype(str).str.strip()
        
        self.l_map = l_map if isinstance(l_map, dict) else {}
        self.b_map = b_map if isinstance(b_map, dict) else {}
        
        self.ledger = self._standardize_ledger()
        self.bank = self._standardize_bank()
        
        self.reconciled_pairs = []
        self.exceptions = []

    def _clean_amount(self, series):
        if pd.api.types.is_numeric_dtype(series):
            return series.fillna(0.0).astype(float)
        return (
            series.astype(str)
            .str.replace(',', '', regex=False)
            .str.replace(' ', '', regex=False)
            .str.replace('₹', '', regex=False)
            .str.extract(r'([-+]?\d*\.?\d+)', expand=False)
            .astype(float)
            .fillna(0.0)
        )

    def _standardize_ledger(self):
        df = pd.DataFrame(index=self.ledger_raw.index)
        
        ref_col = self.l_map.get('ref_id')
        if not ref_col or ref_col not in self.ledger_raw.columns:
            ref_col = self.ledger_raw.columns[0]
        df['order_id'] = self.ledger_raw[ref_col].astype(str).str.strip()
        df['invoice_id'] = self.ledger_raw['invoice_id'].astype(str).str.strip() if 'invoice_id' in self.ledger_raw.columns else df['order_id']
        
        cust_col = self.l_map.get('customer')
        if cust_col and cust_col in self.ledger_raw.columns and cust_col != "None":
            df['customer_name'] = self.ledger_raw[cust_col].astype(str).str.strip()
        else:
            df['customer_name'] = "Enterprise Counterparty"
            
        if 'ledger_amount' in self.ledger_raw.columns:
            df['ledger_amount'] = self._clean_amount(self.ledger_raw['ledger_amount'])
        elif 'Credit' in self.ledger_raw.columns and 'Debit' in self.ledger_raw.columns:
            c = self._clean_amount(self.ledger_raw['Credit'])
            d = self._clean_amount(self.ledger_raw['Debit'])
            df['ledger_amount'] = np.where(c > 0, c, d)
        elif self.l_map.get('amount') and self.l_map.get('amount') in self.ledger_raw.columns:
            df['ledger_amount'] = self._clean_amount(self.ledger_raw[self.l_map['amount']])
        else:
            num_cols = self.ledger_raw.select_dtypes(include=[np.number]).columns
            df['ledger_amount'] = self._clean_amount(self.ledger_raw[num_cols[0]]) if len(num_cols) > 0 else 0.0
            
        date_col = self.l_map.get('date')
        if not date_col or date_col not in self.ledger_raw.columns:
            date_col = self.ledger_raw.columns[0]
        df['ledger_date'] = pd.to_datetime(self.ledger_raw[date_col], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S').fillna("2026-08-01 00:00:00")
        df['matched'] = False
        return df

    def _standardize_bank(self):
        df = pd.DataFrame(index=self.bank_raw.index)
        
        utr_col = self.b_map.get('bank_ref')
        if utr_col and utr_col in self.bank_raw.columns and utr_col != "Auto-Generate":
            df['utr_number'] = self.bank_raw[utr_col].astype(str).str.strip()
        else:
            df['utr_number'] = [f"UTR_{i+1:06d}" for i in range(len(self.bank_raw))]
            
        narr_col = self.b_map.get('narration')
        if not narr_col or narr_col not in self.bank_raw.columns:
            for col in ['narration', 'description', 'particulars', 'desc', 'details']:
                if col in self.bank_raw.columns:
                    narr_col = col
                break
        if not narr_col:
            narr_col = self.bank_raw.columns[0]
        df['narration'] = self.bank_raw[narr_col].astype(str).str.strip()

        if 'bank_amount' in self.bank_raw.columns:
            df['bank_amount'] = self._clean_amount(self.bank_raw['bank_amount'])
        elif 'DEPOSIT AMT' in self.bank_raw.columns or 'WITHDRAWAL AMT' in self.bank_raw.columns:
            dep = self._clean_amount(self.bank_raw['DEPOSIT AMT']) if 'DEPOSIT AMT' in self.bank_raw.columns else 0.0
            withd = self._clean_amount(self.bank_raw['WITHDRAWAL AMT']) if 'WITHDRAWAL AMT' in self.bank_raw.columns else 0.0
            df['bank_amount'] = np.where(dep > 0, dep, withd)
        elif self.b_map.get('amount') and self.b_map.get('amount') in self.bank_raw.columns:
            df['bank_amount'] = self._clean_amount(self.bank_raw[self.b_map['amount']])
        else:
            num_cols = self.bank_raw.select_dtypes(include=[np.number]).columns
            df['bank_amount'] = self._clean_amount(self.bank_raw[num_cols[0]]) if len(num_cols) > 0 else 0.0
            
        date_col = self.b_map.get('date')
        if not date_col or date_col not in self.bank_raw.columns:
            date_col = self.bank_raw.columns[0]
        df['bank_date'] = pd.to_datetime(self.bank_raw[date_col], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S').fillna("2026-08-01 00:00:00")
        df['matched'] = False
        return df

    def run(self):
        merged = pd.merge(
            self.ledger.reset_index(), 
            self.bank.reset_index(), 
            left_on='ledger_amount', 
            right_on='bank_amount', 
            suffixes=('_ledger', '_bank')
        )
        
        if not merged.empty:
            merged['ref_in_narr'] = merged.apply(lambda r: str(r['order_id']).lower() in str(r['narration']).lower(), axis=1)
            exact_matches = merged[merged['ref_in_narr']].drop_duplicates(subset=['index_ledger'])
            
            for _, r in exact_matches.iterrows():
                l_idx = int(r['index_ledger'])
                b_idx = int(r['index_bank'])
                if not self.ledger.at[l_idx, 'matched'] and not self.bank.at[b_idx, 'matched']:
                    self.ledger.at[l_idx, 'matched'] = True
                    self.bank.at[b_idx, 'matched'] = True
                    self.reconciled_pairs.append({
                        "order_id": r['order_id'],
                        "invoice_id": r['invoice_id'],
                        "customer_name": r['customer_name'],
                        "ledger_amount": r['ledger_amount'],
                        "bank_amount": r['bank_amount'],
                        "fee_deducted": 0.0,
                        "utr_number": r['utr_number'],
                        "match_type": "EXACT_MATCH",
                        "confidence_score": 1.0,
                        "audit_notes": "Deterministic Reference ID & Exact Settlement verified."
                    })

        unmatched_l = self.ledger[~self.ledger['matched']]
        unmatched_b = self.bank[~self.bank['matched']]
        
        for l_idx, l_row in unmatched_l.head(1000).iterrows():
            amt = l_row['ledger_amount']
            expected_net = amt * (1 - (0.02 * 1.18))
            order_id = l_row['order_id']
            
            candidates = unmatched_b[
                (~unmatched_b['matched']) & 
                (unmatched_b['narration'].str.contains(order_id, na=False, case=False, regex=False)) &
                (np.isclose(unmatched_b['bank_amount'], expected_net, atol=2.0))
            ]
            
            if not candidates.empty:
                b_idx = candidates.index[0]
                self.ledger.at[l_idx, 'matched'] = True
                self.bank.at[b_idx, 'matched'] = True
                fee_diff = round(amt - self.bank.at[b_idx, 'bank_amount'], 2)
                self.reconciled_pairs.append({
                    "order_id": order_id,
                    "invoice_id": l_row['invoice_id'],
                    "customer_name": l_row['customer_name'],
                    "ledger_amount": amt,
                    "bank_amount": self.bank.at[b_idx, 'bank_amount'],
                    "fee_deducted": fee_diff,
                    "utr_number": self.bank.at[b_idx, 'utr_number'],
                    "match_type": "MDR_GST_ADJUSTED",
                    "confidence_score": 0.98,
                    "audit_notes": f"Reconciled with 2% PG Fee + 18% GST (₹{fee_diff:,.2f})."
                })

        for _, row in self.ledger[~self.ledger['matched']].iterrows():
            self.exceptions.append({
                "source": "INTERNAL_LEDGER",
                "reference_id": row['order_id'],
                "customer_or_sender": row['customer_name'],
                "amount": row['ledger_amount'],
                "date": row['ledger_date'],
                "exception_category": "MISSING_BANK_DEPOSIT",
                "severity": "HIGH" if row['ledger_amount'] > 10000 else "MEDIUM",
                "suggested_action": "Follow up with Payment Gateway for pending payout."
            })
            
        for _, row in self.bank[~self.bank['matched']].iterrows():
            self.exceptions.append({
                "source": "BANK_STATEMENT",
                "reference_id": row['utr_number'],
                "customer_or_sender": row['narration'][:45],
                "amount": row['bank_amount'],
                "date": row['bank_date'],
                "exception_category": "UNIDENTIFIED_BANK_CREDIT",
                "severity": "MEDIUM",
                "suggested_action": "Create manual ledger receipt or trace sender UTR."
            })

        df_reconciled = pd.DataFrame(self.reconciled_pairs)
        df_exceptions = pd.DataFrame(self.exceptions)
        
        summary = {
            "total_ledger": len(self.ledger),
            "total_ledger_records": len(self.ledger),
            "total_bank": len(self.bank),
            "total_bank_records": len(self.bank),
            "reconciled_records": len(df_reconciled),
            "match_rate_pct": round((len(df_reconciled) / len(self.ledger) * 100), 2) if len(self.ledger) > 0 else 0,
            "exceptions_count": len(df_exceptions),
            "reconciled_vol": df_reconciled['ledger_amount'].sum() if not df_reconciled.empty else 0.0,
            "fee_variance": df_reconciled['fee_deducted'].sum() if ('fee_deducted' in df_reconciled.columns and not df_reconciled.empty) else 0.0
        }
        
        return df_reconciled, df_exceptions, summary

    @staticmethod
    def generate_ai_dispute_email(ref_id, party, amt, date):
        return f"""Subject: Urgent Settlement Escalation - Reference [{ref_id}] - ₹{amt:,.2f}

Dear Banking Operations & Gateway Support Team,

Our autonomous financial controller has identified an unresolved settlement discrepancy:

- Internal Reference: {ref_id}
- Party / Counterparty: {party}
- Ledger Amount: ₹{amt:,.2f}
- Recorded Date: {date}

Status: Verified in internal sales ledger, but missing corresponding bank settlement credit beyond standard T+2 SLA.

Please provide the associated Bank UTR reference or advise on the payout hold status immediately.

Sincerely,
Autonomous Finance Controller | Automated Audit Engine"""