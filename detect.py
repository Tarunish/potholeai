from ultralytics import YOLO
import cv2
import json
import os
import random
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

IMAGE_PATH = "pothole.jpg"
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

# ── ALL CHHATTISGARH HIGHWAYS & DISTRICTS ─────────────────────────────────────
# All 33 districts of Chhattisgarh
CG_LOCATIONS = [
    # Raipur Division
    {"lat":21.2514,"lon":81.6296,"road":"NH-30", "place":"Raipur City",      "district":"Raipur",        "division":"PWD Raipur"},
    {"lat":21.0900,"lon":81.7200,"road":"NH-30", "place":"Abhanpur",         "district":"Raipur",        "division":"PWD Raipur"},
    {"lat":21.4500,"lon":82.0200,"road":"SH-9",  "place":"Baloda Bazar",     "district":"Baloda Bazar",  "division":"PWD Baloda Bazar"},
    {"lat":21.6700,"lon":82.5700,"road":"SH-9",  "place":"Mahasamund",       "district":"Mahasamund",    "division":"PWD Mahasamund"},
    {"lat":20.9800,"lon":82.2500,"road":"SH-17", "place":"Gariaband",        "district":"Gariaband",     "division":"PWD Gariaband"},
    # Bilaspur Division
    {"lat":22.0900,"lon":82.1400,"road":"NH-130","place":"Bilaspur",         "district":"Bilaspur",      "division":"PWD Bilaspur"},
    {"lat":22.0400,"lon":82.5800,"road":"NH-53", "place":"Janjgir",          "district":"Janjgir-Champa","division":"PWD Janjgir"},
    {"lat":21.9800,"lon":82.0200,"road":"SH-10", "place":"Mungeli",          "district":"Mungeli",       "division":"PWD Mungeli"},
    {"lat":22.0200,"lon":81.6300,"road":"SH-12", "place":"Takhatpur",        "district":"Bilaspur",      "division":"PWD Bilaspur"},
    # Korba Division
    {"lat":22.3600,"lon":82.5700,"road":"NH-130","place":"Korba",            "district":"Korba",         "division":"PWD Korba"},
    {"lat":22.5500,"lon":82.7600,"road":"NH-130","place":"Katghora",         "district":"Korba",         "division":"PWD Korba"},
    # Raigarh Division
    {"lat":21.8970,"lon":83.3960,"road":"NH-53", "place":"Raigarh",          "district":"Raigarh",       "division":"PWD Raigarh"},
    {"lat":21.7500,"lon":83.6000,"road":"NH-53", "place":"Sarangarh",        "district":"Sarangarh-Bilaigarh","division":"PWD Raigarh"},
    {"lat":22.1000,"lon":83.1000,"road":"SH-21", "place":"Sakti",            "district":"Sakti",         "division":"PWD Sakti"},
    # Surguja Division
    {"lat":23.1200,"lon":83.2000,"road":"NH-43", "place":"Ambikapur",        "district":"Surguja",       "division":"PWD Ambikapur"},
    {"lat":23.5600,"lon":83.2800,"road":"SH-6",  "place":"Balrampur",        "district":"Balrampur-Ramanujganj","division":"PWD Balrampur"},
    {"lat":23.7800,"lon":83.9700,"road":"SH-6",  "place":"Surajpur",         "district":"Surajpur",      "division":"PWD Surajpur"},
    {"lat":23.0500,"lon":83.0500,"road":"NH-43", "place":"Baikunthpur",      "district":"Korea",         "division":"PWD Korea"},
    {"lat":23.2800,"lon":82.7600,"road":"NH-43", "place":"Manendragarh",     "district":"Manendragarh-Chirmiri-Bharatpur","division":"PWD Korea"},
    {"lat":23.9800,"lon":83.6800,"road":"SH-6",  "place":"Pratappur",        "district":"Surajpur",      "division":"PWD Surajpur"},
    # Durg Division
    {"lat":21.0974,"lon":81.0296,"road":"NH-49", "place":"Durg",             "district":"Durg",          "division":"PWD Durg"},
    {"lat":21.0900,"lon":80.9600,"road":"NH-49", "place":"Rajnandgaon",      "district":"Rajnandgaon",   "division":"PWD Rajnandgaon"},
    {"lat":22.6800,"lon":81.6300,"road":"SH-10", "place":"Kawardha",         "district":"Kabirdham",     "division":"PWD Kabirdham"},
    {"lat":20.9200,"lon":80.7000,"road":"NH-930","place":"Khairagarh",       "district":"Khairagarh-Chhuikhadan-Gandai","division":"PWD Rajnandgaon"},
    {"lat":20.7500,"lon":81.3500,"road":"SH-15", "place":"Mohla",            "district":"Mohla-Manpur-Ambagarh Chowki","division":"PWD Rajnandgaon"},
    # Bastar Division
    {"lat":20.9320,"lon":81.8390,"road":"NH-30", "place":"Kanker",           "district":"Kanker",        "division":"PWD Kanker"},
    {"lat":20.6100,"lon":81.9600,"road":"NH-30", "place":"Narayanpur",       "district":"Narayanpur",    "division":"PWD Narayanpur"},
    {"lat":20.4500,"lon":81.9500,"road":"NH-30", "place":"Kondagaon",        "district":"Kondagaon",     "division":"PWD Kondagaon"},
    {"lat":20.1200,"lon":81.9800,"road":"NH-30", "place":"Jagdalpur",        "district":"Bastar",        "division":"PWD Jagdalpur"},
    {"lat":19.0700,"lon":81.3500,"road":"SH-5",  "place":"Dantewada",        "district":"Dantewada",     "division":"PWD Dantewada"},
    {"lat":18.9000,"lon":81.2500,"road":"SH-5",  "place":"Bijapur",          "district":"Bijapur",       "division":"PWD Bijapur"},
    {"lat":19.0760,"lon":82.0180,"road":"NH-30", "place":"Sukma",            "district":"Sukma",         "division":"PWD Sukma"},
    {"lat":18.8500,"lon":81.9000,"road":"NH-30", "place":"Konta",            "district":"Sukma",         "division":"PWD Sukma"},
]

SEVERITIES       = ["Minor", "Moderate", "Critical"]
SEVERITY_WEIGHTS = [0.25, 0.45, 0.30]
STATUSES         = ["Filed", "Filed", "Filed", "Escalated", "Repaired"]

# ── REAL GPS FROM PHOTO EXIF ──────────────────────────────────────────────────
def extract_gps_from_image(image_path):
    """
    Reads real GPS coordinates embedded in phone photos (EXIF data).
    Returns (lat, lon) if found, or None if no GPS in image.
    """
    try:
        img  = Image.open(image_path)
        exif = img._getexif()
        if not exif:
            return None

        # Find GPS tag
        gps_info = {}
        for tag_id, value in exif.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "GPSInfo":
                for gps_tag_id, gps_value in value.items():
                    gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                    gps_info[gps_tag] = gps_value

        if not gps_info:
            return None

        # Convert DMS → decimal degrees
        def dms_to_decimal(dms, ref):
            deg  = float(dms[0])
            mins = float(dms[1])
            secs = float(dms[2])
            dd   = deg + mins/60 + secs/3600
            if ref in ["S", "W"]:
                dd = -dd
            return round(dd, 6)

        lat = dms_to_decimal(gps_info["GPSLatitude"],  gps_info["GPSLatitudeRef"])
        lon = dms_to_decimal(gps_info["GPSLongitude"], gps_info["GPSLongitudeRef"])
        print(f"📍 Real GPS extracted from photo: {lat}, {lon}")
        return lat, lon

    except Exception as e:
        print(f"ℹ️  No GPS in image ({e}) — using CG highway location")
        return None

def find_nearest_road(lat, lon):
    """Find the nearest CG highway to given GPS coordinates."""
    best  = None
    best_dist = float("inf")
    for loc in CG_LOCATIONS:
        dist = ((lat - loc["lat"])**2 + (lon - loc["lon"])**2)**0.5
        if dist < best_dist:
            best_dist = dist
            best      = loc
    return best

def get_severity(box, img_w, img_h):
    x1,y1,x2,y2 = box
    pct = ((x2-x1)*(y2-y1))/(img_w*img_h)*100
    if pct < 1.5:   return "Minor",    (0,255,0)
    elif pct < 4.0: return "Moderate", (0,165,255)
    else:           return "Critical", (0,0,255)

def gen_id(i):
    return f"CG-{random.choice(['NH','SH','MDR'])}{random.randint(30,216)}-2026-{10000+i*97+random.randint(1,99):05d}"

def rand_date(days=45):
    d = timedelta(days=random.randint(0,days), hours=random.randint(0,23), minutes=random.randint(0,59))
    return (datetime.now()-d).isoformat()

def detect(image_path):
    print(f"\n🔍 Running YOLOv11 on: {image_path}")

    # ── Try to get real GPS from photo ────────────────────────────────────────
    real_gps = extract_gps_from_image(image_path)
    if real_gps:
        real_lat, real_lon = real_gps
        nearest_road = find_nearest_road(real_lat, real_lon)
        print(f"🛣️  Nearest CG highway: {nearest_road['road']}, {nearest_road['place']}")
        gps_source = "REAL"
    else:
        real_gps = None
        gps_source = "SIMULATED"
        print("📡 No GPS in image — using CG highway simulation data")

    model = YOLO("yolo11n.pt")
    img   = cv2.imread(image_path)
    if img is None:
        print("❌ Image not found.")
        return
    img_h, img_w = img.shape[:2]
    results = model(image_path, conf=0.25)
    boxes   = results[0].boxes
    complaints = []

    # Real YOLO detections
    for i, box in enumerate(boxes):
        x1,y1,x2,y2 = map(int, box.xyxy[0])
        conf = float(box.conf[0])
        severity, color = get_severity((x1,y1,x2,y2), img_w, img_h)

        # Use real GPS if available, else pick random CG location
        if real_gps:
            lat = round(real_lat + random.uniform(-0.001, 0.001), 6)
            lon = round(real_lon + random.uniform(-0.001, 0.001), 6)
            loc = nearest_road
        else:
            loc = random.choice(CG_LOCATIONS)
            lat = round(loc["lat"] + random.uniform(-0.015, 0.015), 6)
            lon = round(loc["lon"] + random.uniform(-0.015, 0.015), 6)

        pid = gen_id(i)
        cv2.rectangle(img,(x1,y1),(x2,y2),color,3)
        lbl = f"{pid} | {severity}"
        (tw,th),_ = cv2.getTextSize(lbl,cv2.FONT_HERSHEY_SIMPLEX,0.45,2)
        cv2.rectangle(img,(x1,y1-th-8),(x1+tw+4,y1),color,-1)
        cv2.putText(img,lbl,(x1+2,y1-4),cv2.FONT_HERSHEY_SIMPLEX,0.45,(255,255,255),2)

        fd = datetime.now().isoformat()
        rd = (datetime.now()+timedelta(days=14)).strftime("%Y-%m-%d")
        complaints.append({
            "pothole_id": pid, "detected_at": fd,
            "road": loc["road"], "location": f"{loc['road']}, {loc['place']}",
            "place": loc["place"], "district": loc["district"],
            "gps": {"lat": lat, "lon": lon},
            "gps_source": gps_source,
            "severity": severity, "confidence": round(conf,3),
            "status": "Filed", "assigned_to": loc["division"],
            "grievance_portal": "PG Portal India",
            "complaint_filed_at": fd, "re_scan_due": rd,
            "highway_km": f"KM {random.randint(10,500)}+{random.randint(0,999):03d}",
        })

    # Fill up to 50 synthetic potholes
    random.shuffle(CG_LOCATIONS)
    for i in range(100 - len(complaints)):
        idx = i % len(CG_LOCATIONS)
        loc = CG_LOCATIONS[idx]

        # If real GPS available, cluster some near real location
        if real_gps and i < 5:
            lat = round(real_lat + random.uniform(-0.05, 0.05), 6)
            lon = round(real_lon + random.uniform(-0.05, 0.05), 6)
        else:
            lat = round(loc["lat"] + random.uniform(-0.025, 0.025), 6)
            lon = round(loc["lon"] + random.uniform(-0.025, 0.025), 6)

        sev = random.choices(SEVERITIES, weights=SEVERITY_WEIGHTS)[0]
        pid = gen_id(len(complaints)+i+100)
        fd  = rand_date()
        rd  = (datetime.fromisoformat(fd)+timedelta(days=14)).strftime("%Y-%m-%d")
        complaints.append({
            "pothole_id": pid, "detected_at": fd,
            "road": loc["road"], "location": f"{loc['road']}, {loc['place']}",
            "place": loc["place"], "district": loc["district"],
            "gps": {"lat": lat, "lon": lon},
            "gps_source": "SIMULATED",
            "severity": sev, "confidence": round(random.uniform(0.71,0.98),3),
            "status": random.choice(STATUSES), "assigned_to": loc["division"],
            "grievance_portal": "PG Portal India",
            "complaint_filed_at": fd, "re_scan_due": rd,
            "highway_km": f"KM {random.randint(10,500)}+{random.randint(0,999):03d}",
        })

    # Sort Critical first
    order = {"Critical":0,"Moderate":1,"Minor":2}
    complaints.sort(key=lambda x: order[x["severity"]])

    out_img  = str(OUTPUT_DIR/"detected.jpg")
    out_json = str(OUTPUT_DIR/"complaints.json")
    cv2.imwrite(out_img, img)

    # ── APPEND to existing complaints instead of overwriting ─────────────────
    existing = []
    if os.path.exists(out_json):
        try:
            with open(out_json) as f:
                existing = json.load(f)
        except:
            existing = []

    # Avoid duplicate IDs
    existing_ids = {c["pothole_id"] for c in existing}
    new_only = [c for c in complaints if c["pothole_id"] not in existing_ids]
    all_complaints = existing + new_only

    # Keep sorted by severity
    all_complaints.sort(key=lambda x: order[x["severity"]])

    with open(out_json,"w") as f:
        json.dump(all_complaints, f, indent=2)

    print(f"\n✅ New potholes added: {len(new_only)}")
    print(f"   Total in system: {len(all_complaints)}")

    print(f"\n✅ Total: {len(complaints)} potholes")
    print(f"   GPS Source: {gps_source}")
    if real_gps:
        print(f"   📍 Real location: {real_lat}, {real_lon}")
    print(f"   Critical: {sum(1 for c in complaints if c['severity']=='Critical')}")
    print(f"   Moderate: {sum(1 for c in complaints if c['severity']=='Moderate')}")
    print(f"   Minor:    {sum(1 for c in complaints if c['severity']=='Minor')}")

if __name__ == "__main__":
    detect(IMAGE_PATH)
