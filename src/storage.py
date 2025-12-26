import os
import sqlite3
import pandas as pd
import json
from datetime import datetime
from .security import SecurityManager

class StorageEngine:
    def __init__(self, db_name="invoices.db"):
        base_dir = os.path.dirname(os.path.abspath(__file__)) 
        project_root = os.path.dirname(base_dir)              
        data_dir = os.path.join(project_root, "data")
        os.makedirs(data_dir, exist_ok=True)
        self.db_path = os.path.join(data_dir, db_name)
        
        self.sec = SecurityManager()
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_hash TEXT UNIQUE,
                filename TEXT,
                upload_date TEXT,
                
                invoice_number TEXT,
                invoice_date TEXT,
                vendor_name TEXT,
                vendor_gstin TEXT,
                buyer_name TEXT,
                
                cgst TEXT,
                sgst TEXT,
                grand_total TEXT,
                currency TEXT,
                
                json_data_enc BLOB,
                status TEXT
            )
        """)
        conn.commit()
        conn.close()

    def save_invoice(self, filename, file_hash, data):
        json_enc = self.sec.encrypt_data(json.dumps(data))
        
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        try:
            cur.execute("""
                INSERT INTO invoices (
                    file_hash, filename, upload_date,
                    invoice_number, invoice_date,
                    vendor_name, vendor_gstin,
                    buyer_name,
                    cgst, sgst, grand_total, currency,
                    json_data_enc, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                file_hash, 
                filename, 
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                data.get('invoice_number', 'N/A'),
                data.get('invoice_date', 'N/A'),
                data.get('vendor_name', 'Unknown'),
                data.get('vendor_gstin', 'N/A'),
                data.get('buyer_name', 'Unknown'),
                str(data.get('cgst', '0')),
                str(data.get('sgst', '0')),
                str(data.get('grand_total', '0')),
                data.get('currency', 'INR'),
                json_enc,
                "PROCESSED"
            ))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False 
        finally:
            conn.close()

    def export_to_csv(self, output_path):
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("""
            SELECT 
                filename as 'Filename',
                invoice_number as 'Invoice No',
                invoice_date as 'Invoice Date',
                vendor_name as 'Vendor Name',
                vendor_gstin as 'Vendor GSTIN',
                buyer_name as 'Buyer Name',
                cgst as 'CGST',
                sgst as 'SGST',
                grand_total as 'Grand Total',
                currency as 'Currency',
                status as 'Status',
                upload_date as 'Processed On'
            FROM invoices
        """, conn)
        conn.close()
        
        if df.empty:
            return 0
        
        df.to_csv(output_path, index=False)
        return len(df)