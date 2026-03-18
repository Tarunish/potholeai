from ultralytics import YOLO
import cv2
import json
import os
import random
import ssl
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

IMAGE_PATH = "pothole.jpg"
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

# ── SSL FIX FOR MACOS ─────────────────────────────────────────────────────────
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

# ── FETCH REAL POTHOLE DATA FROM OPENSTREETMAP (WHOLE INDIA) ──────────────────
def fetch_osm_potholes(lat=None, lon=None, radius_km=50):
    """
    Fetch real reported road damage/potholes from OpenStreetMap
    for whole India or near a specific location.
    Returns list of real pothole records.
    """
    print("🌐 Fetching real pothole data from OpenStreetMap...")

    # Overpass API query — whole India road damage + potholes
    if lat and lon:
        # Near specific location
        radius_m = radius_km * 1000
        query = f"""
        [out:json][timeout:25];
        (
          node["highway"="road_damage"](around:{radius_m},{lat},{lon});
          node["surface"="potholes"](around:{radius_m},{lat},{lon});
          node["highway"="pothole"](around:{radius_m},{lat},{lon});
          way["surface"="potholes"](around:{radius_m},{lat},{lon});
        );
        out center 200;
        """
    else:
        # Whole India bounding box: 6.5°N to 37.5°N, 68°E to 97.5°E
        query = """
        [out:json][timeout:30];
        (
          node["highway"="road_damage"](6.5,68.0,37.5,97.5);
          node["surface"="potholes"](6.5,68.0,37.5,97.5);
          node["highway"="pothole"](6.5,68.0,37.5,97.5);
          node["road:condition"="bad"](6.5,68.0,37.5,97.5);
          node["road:condition"="very_bad"](6.5,68.0,37.5,97.5);
          way["surface"="potholes"](6.5,68.0,37.5,97.5);
        );
        out center 500;
        """

    url = "https://overpass-api.de/api/interpreter"
    data = urllib.parse.urlencode({"data": query}).encode()
    req  = urllib.request.Request(url, data=data,
                                   headers={"Content-Type": "application/x-www-form-urlencoded",
                                            "User-Agent": "PotholeAI/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as r:
            result = json.loads(r.read())
        elements = result.get("elements", [])
        print(f"✅ OSM returned {len(elements)} real pothole records from India")
        return elements
    except Exception as e:
        print(f"⚠️  OSM fetch failed: {e}")
        return []

def osm_element_to_complaint(elem, index):
    """Convert OSM element to complaint record format."""
    # Get coordinates
    if elem.get("type") == "node":
        lat = elem.get("lat", 0)
        lon = elem.get("lon", 0)
    else:
        center = elem.get("center", {})
        lat = center.get("lat", 0)
        lon = center.get("lon", 0)

    tags = elem.get("tags", {})

    # Extract real info from OSM tags
    road    = tags.get("name") or tags.get("ref") or tags.get("highway") or "Unknown Road"
    place   = tags.get("addr:city") or tags.get("addr:district") or tags.get("addr:state") or "India"
    district = tags.get("addr:district") or tags.get("is_in:district") or place
    state   = tags.get("addr:state") or tags.get("is_in:state") or "India"

    # Determine severity from OSM tags
    condition = tags.get("road:condition") or tags.get("surface") or ""
    if "very_bad" in condition or "terrible" in condition:
        severity = "Critical"
    elif "bad" in condition or "pothole" in condition.lower():
        severity = "Moderate"
    else:
        severity = "Minor"

    now = datetime.now()
    pid = f"OSM-{elem.get('id', index)}-INDIA"
    fd  = now.isoformat()
    rd  = (now + timedelta(days=14)).strftime("%Y-%m-%d")

    return {
        "pothole_id":          pid,
        "detected_at":         fd,
        "road":                road,
        "location":            f"{road}, {place}, {state}",
        "place":               place,
        "district":            district,
        "state":               state,
        "gps":                 {"lat": round(lat, 6), "lon": round(lon, 6)},
        "gps_source":          "OSM_REAL",
        "severity":            severity,
        "confidence":          1.0,
        "status":              "Filed",
        "assigned_to":         f"PWD {state}",
        "grievance_portal":    "PG Portal India",
        "complaint_filed_at":  fd,
        "re_scan_due":         rd,
        "highway_km":          tags.get("ref", ""),
        "osm_id":              elem.get("id"),
        "osm_tags":            tags,
    }

# ── REVERSE GEOCODE using Nominatim (free) ────────────────────────────────────
def reverse_geocode(lat, lon):
    """Get real address from GPS coordinates using OpenStreetMap Nominatim."""
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json"
        req = urllib.request.Request(url, headers={"User-Agent": "PotholeAI/1.0"})
        with urllib.request.urlopen(req, timeout=8, context=ssl_ctx) as r:
            data = json.loads(r.read())
        addr = data.get("address", {})
        road     = addr.get("road") or addr.get("highway") or "Unknown Road"
        city     = addr.get("city") or addr.get("town") or addr.get("village") or ""
        district = addr.get("county") or addr.get("district") or city
        state    = addr.get("state") or "India"
        place    = city or district
        display  = data.get("display_name", f"{lat}, {lon}")
        print(f"📍 Geocoded: {road}, {place}, {state}")
        return road, place, district, state, display
    except Exception as e:
        print(f"⚠️  Geocode failed: {e}")
        return "Unknown Road", "Unknown", "Unknown", "India", f"{lat},{lon}"

# ── GPS FROM EXIF ─────────────────────────────────────────────────────────────
def extract_gps_from_image(image_path):
    try:
        img  = Image.open(image_path)
        exif = img._getexif()
        if not exif:
            return None
        gps_info = {}
        for tag_id, value in exif.items():
            tag = TAGS.get(tag_id, tag_id)
            if tag == "GPSInfo":
                for gps_tag_id, gps_value in value.items():
                    gps_tag = GPSTAGS.get(gps_tag_id, gps_tag_id)
                    gps_info[gps_tag] = gps_value
        if not gps_info:
            return None
        def dms_to_decimal(dms, ref):
            dd = float(dms[0]) + float(dms[1])/60 + float(dms[2])/3600
            if ref in ["S","W"]: dd = -dd
            return round(dd, 6)
        lat = dms_to_decimal(gps_info["GPSLatitude"],  gps_info["GPSLatitudeRef"])
        lon = dms_to_decimal(gps_info["GPSLongitude"], gps_info["GPSLongitudeRef"])
        print(f"📍 Real GPS from photo EXIF: {lat}, {lon}")
        return lat, lon
    except Exception as e:
        print(f"ℹ️  No EXIF GPS: {e}")
        return None

def get_severity(box, img_w, img_h):
    x1,y1,x2,y2 = box
    pct = ((x2-x1)*(y2-y1))/(img_w*img_h)*100
    if pct < 1.5:   return "Minor",    (0,255,0)
    elif pct < 4.0: return "Moderate", (0,165,255)
    else:           return "Critical", (0,0,255)

def gen_id(prefix="YOLO"):
    ts = datetime.now().strftime("%H%M%S")
    return f"{prefix}-{ts}-{random.randint(1000,9999)}"

def detect(image_path):
    print(f"\n🔍 Running YOLOv11 on: {image_path}")

    # ── Step 1: Get GPS ───────────────────────────────────────────────────────
    real_gps = extract_gps_from_image(image_path)

    # Try device GPS from file
    device_gps = None
    if os.path.exists("device_gps.json"):
        try:
            with open("device_gps.json") as gf:
                device_gps = json.load(gf)
        except:
            pass

    if real_gps:
        lat, lon = real_gps
        gps_source = "PHOTO_EXIF"
    elif device_gps:
        lat  = device_gps["lat"]
        lon  = device_gps["lon"]
        gps_source = "DEVICE_GPS"
        print(f"📱 Using device GPS: {lat}, {lon}")
    else:
        lat, lon = None, None
        gps_source = "UNKNOWN"
        print("⚠️  No GPS found. Capture GPS in sidebar before detecting.")

    # ── Step 2: Reverse geocode real location ─────────────────────────────────
    if lat and lon:
        road, place, district, state, display = reverse_geocode(lat, lon)
    else:
        road, place, district, state, display = "Unknown", "Unknown", "Unknown", "India", "Unknown"

    # ── Step 3: Run YOLO ──────────────────────────────────────────────────────
    model   = YOLO("best.pt")
    img     = cv2.imread(image_path)
    if img is None:
        print("❌ Image not found.")
        return
    img_h, img_w = img.shape[:2]
    results = model(image_path, conf=0.25)
    boxes   = results[0].boxes
    yolo_complaints = []

    for i, box in enumerate(boxes):
        x1,y1,x2,y2 = map(int, box.xyxy[0])
        conf = float(box.conf[0])
        severity, color = get_severity((x1,y1,x2,y2), img_w, img_h)

        # Slightly offset GPS per detection so they don't stack
        det_lat = round(lat + random.uniform(-0.0003, 0.0003), 6) if lat else 0.0
        det_lon = round(lon + random.uniform(-0.0003, 0.0003), 6) if lon else 0.0

        pid = gen_id("YOLO")
        cv2.rectangle(img, (x1,y1), (x2,y2), color, 3)
        lbl = f"{pid[-8:]} | {severity}"
        (tw,th),_ = cv2.getTextSize(lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 2)
        cv2.rectangle(img, (x1,y1-th-8), (x1+tw+4,y1), color, -1)
        cv2.putText(img, lbl, (x1+2,y1-4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255,255,255), 2)

        now = datetime.now()
        fd  = now.isoformat()
        rd  = (now + timedelta(days=14)).strftime("%Y-%m-%d")

        yolo_complaints.append({
            "pothole_id":         pid,
            "detected_at":        fd,
            "road":               road,
            "location":           display if lat else "Unknown Location",
            "place":              place,
            "district":           district,
            "state":              state,
            "gps":                {"lat": det_lat, "lon": det_lon},
            "gps_source":         gps_source,
            "severity":           severity,
            "confidence":         round(conf, 3),
            "status":             "Filed",
            "assigned_to":        f"PWD {state}",
            "grievance_portal":   "PG Portal India",
            "complaint_filed_at": fd,
            "re_scan_due":        rd,
            "highway_km":         road,
        })

    print(f"✅ YOLO detected {len(yolo_complaints)} real potholes")

    # ── Step 4: Fetch real OSM data for whole India ───────────────────────────
    osm_elements = fetch_osm_potholes(lat, lon, radius_km=100 if lat else None)
    osm_complaints = []
    for i, elem in enumerate(osm_elements):
        c = osm_element_to_complaint(elem, i)
        osm_complaints.append(c)
    print(f"✅ OSM real potholes loaded: {len(osm_complaints)}")

    # ── Step 5: Combine YOLO + OSM real data ─────────────────────────────────
    all_new = yolo_complaints + osm_complaints

    # Sort Critical first
    order = {"Critical":0,"Moderate":1,"Minor":2}
    all_new.sort(key=lambda x: order.get(x["severity"], 3))

    # Save output image
    out_img = str(OUTPUT_DIR/"detected.jpg")
    cv2.imwrite(out_img, img)

    # ── Step 6: Append to existing (no duplicates) ────────────────────────────
    out_json = str(OUTPUT_DIR/"complaints.json")
    existing = []
    if os.path.exists(out_json):
        try:
            with open(out_json) as f:
                existing = json.load(f)
        except:
            existing = []

    existing_ids = {c["pothole_id"] for c in existing}
    new_only = [c for c in all_new if c["pothole_id"] not in existing_ids]
    final = existing + new_only
    final.sort(key=lambda x: order.get(x["severity"], 3))

    with open(out_json,"w") as f:
        json.dump(final, f, indent=2)

    print(f"\n📊 Summary:")
    print(f"   YOLO detections : {len(yolo_complaints)}")
    print(f"   OSM real data   : {len(osm_complaints)}")
    print(f"   New added       : {len(new_only)}")
    print(f"   Total in system : {len(final)}")
    if lat:
        print(f"   📍 Location: {display}")

if __name__ == "__main__":
    detect(IMAGE_PATH)
