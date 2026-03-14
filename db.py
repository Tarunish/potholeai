import sqlite3
import json
import os

DB_PATH = "potholeai.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            pothole_id TEXT PRIMARY KEY,
            detected_at TEXT,
            road TEXT,
            location TEXT,
            place TEXT,
            district TEXT,
            gps_lat REAL,
            gps_lon REAL,
            gps_source TEXT,
            severity TEXT,
            confidence REAL,
            status TEXT,
            assigned_to TEXT,
            grievance_portal TEXT,
            complaint_filed_at TEXT,
            re_scan_due TEXT,
            highway_km TEXT,
            auto_verified_at TEXT,
            auto_escalated_at TEXT
        )
    ''')
    conn.commit()
    conn.close()

def dict_to_row(d):
    return (
        d.get("pothole_id"),
        d.get("detected_at"),
        d.get("road"),
        d.get("location"),
        d.get("place"),
        d.get("district"),
        d.get("gps", {}).get("lat"),
        d.get("gps", {}).get("lon"),
        d.get("gps_source"),
        d.get("severity"),
        d.get("confidence"),
        d.get("status"),
        d.get("assigned_to"),
        d.get("grievance_portal"),
        d.get("complaint_filed_at"),
        d.get("re_scan_due"),
        d.get("highway_km"),
        d.get("auto_verified_at"),
        d.get("auto_escalated_at")
    )

def row_to_dict(r):
    return {
        "pothole_id": r[0],
        "detected_at": r[1],
        "road": r[2],
        "location": r[3],
        "place": r[4],
        "district": r[5],
        "gps": {"lat": r[6], "lon": r[7]},
        "gps_source": r[8],
        "severity": r[9],
        "confidence": r[10],
        "status": r[11],
        "assigned_to": r[12],
        "grievance_portal": r[13],
        "complaint_filed_at": r[14],
        "re_scan_due": r[15],
        "highway_km": r[16],
        "auto_verified_at": r[17],
        "auto_escalated_at": r[18]
    }

def insert_complaints(complaints_list):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Insert or ignore if ID already exists
    c.executemany('''
        INSERT OR IGNORE INTO complaints VALUES (
            ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
        )
    ''', [dict_to_row(comp) for comp in complaints_list])
    
    # Alternatively, you could do an INSERT OR REPLACE if you want new runs to overwrite old identical IDs.
    
    conn.commit()
    inserted_count = c.rowcount
    conn.close()
    return inserted_count

def get_all_complaints():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM complaints")
    rows = c.fetchall()
    conn.close()
    
    complaints = [row_to_dict(r) for r in rows]
    # Keep sorted by severity
    order = {"Critical":0,"Moderate":1,"Minor":2}
    complaints.sort(key=lambda x: order.get(x["severity"], 3))
    return complaints

def update_complaint_status(complaint_id, status, timestamp_field, timestamp):
    """
    Updates status and relevant timestamp fields for a specific complaint
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    if timestamp_field == "auto_verified_at":
        c.execute("UPDATE complaints SET status=?, auto_verified_at=? WHERE pothole_id=?", 
                  (status, timestamp, complaint_id))
    elif timestamp_field == "auto_escalated_at":
        c.execute("UPDATE complaints SET status=?, auto_escalated_at=? WHERE pothole_id=?", 
                  (status, timestamp, complaint_id))
    else:
        c.execute("UPDATE complaints SET status=? WHERE pothole_id=?", 
                  (status, complaint_id))
        
    conn.commit()
    conn.close()

def migrate_json_to_db(json_path="output/complaints.json"):
    """One-time run to migrate existing data."""
    if os.path.exists(json_path):
        with open(json_path, 'r') as f:
            try:
                data = json.load(f)
                if data:
                    insert_complaints(data)
                    return len(data)
            except Exception as e:
                print(f"Migration error: {e}")
    return 0

# Ensure DB is initialized when imported
init_db()
