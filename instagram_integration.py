"""
PotholeAI — Instagram Integration Module
-----------------------------------------
1. Scrape Instagram posts with pothole hashtags via Meta Graph API
2. Predict location from image using AI (Google Vision + text/landmark detection)
3. Auto-log detected potholes from Instagram into PotholeAI database
"""

import json, os, time, re, ssl, hashlib, random
import urllib.request as _req
import urllib.parse   as _parse
from datetime import datetime

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode    = ssl.CERT_NONE


# ─────────────────────────────────────────────────────────────────────────────
#  CONFIG  (set in .env or Streamlit secrets)
# ─────────────────────────────────────────────────────────────────────────────
IG_ACCESS_TOKEN   = os.environ.get("IG_ACCESS_TOKEN", "")       # Meta Graph API token
IG_USER_ID        = os.environ.get("IG_USER_ID", "")             # Instagram Business User ID
GOOGLE_VISION_KEY = os.environ.get("GOOGLE_VISION_KEY", "")      # Google Cloud Vision API key
ANTHROPIC_KEY     = os.environ.get("ANTHROPIC_API_KEY", "")      # For AI location prediction


# ─────────────────────────────────────────────────────────────────────────────
#  INSTAGRAM GRAPH API
# ─────────────────────────────────────────────────────────────────────────────

POTHOLE_HASHTAGS = [
    "pothole", "potholes", "roadpothole", "baadroad", "roadissue",
    "khaddaa", "sadakgadha", "पोटहोल", "खड्डा", "badroads",
    "indiaroads", "roadproblem", "roaddamage", "potholesindia",
    "mumbairoads", "delhiroads", "bangaloreroads", "puneroads",
]

def ig_get_hashtag_id(hashtag: str) -> str:
    """Get Instagram hashtag ID from Meta Graph API."""
    if not IG_ACCESS_TOKEN or not IG_USER_ID:
        return ""
    url = (
        f"https://graph.facebook.com/v18.0/ig_hashtag_search"
        f"?user_id={IG_USER_ID}"
        f"&q={_parse.quote(hashtag)}"
        f"&access_token={IG_ACCESS_TOKEN}"
    )
    try:
        with _req.urlopen(url, timeout=10, context=_ctx) as r:
            data = json.loads(r.read())
            return data.get("data", [{}])[0].get("id", "")
    except Exception:
        return ""


def ig_get_recent_media(hashtag_id: str, limit: int = 20) -> list:
    """Fetch recent posts for a hashtag."""
    if not hashtag_id or not IG_ACCESS_TOKEN or not IG_USER_ID:
        return []
    url = (
        f"https://graph.facebook.com/v18.0/{hashtag_id}/recent_media"
        f"?user_id={IG_USER_ID}"
        f"&fields=id,media_url,thumbnail_url,caption,location,timestamp,permalink"
        f"&limit={limit}"
        f"&access_token={IG_ACCESS_TOKEN}"
    )
    try:
        with _req.urlopen(url, timeout=10, context=_ctx) as r:
            data = json.loads(r.read())
            return data.get("data", [])
    except Exception:
        return []


def ig_search_potholes(max_posts: int = 50) -> list:
    """
    Search multiple pothole hashtags and return unique posts.
    Returns list of dicts with: id, image_url, caption, location, timestamp, permalink
    """
    if not IG_ACCESS_TOKEN:
        return _get_demo_posts()  # Return demo data if no API key

    seen_ids = set()
    all_posts = []

    for tag in POTHOLE_HASHTAGS[:8]:  # Check first 8 hashtags
        htag_id = ig_get_hashtag_id(tag)
        if not htag_id:
            continue
        posts = ig_get_recent_media(htag_id, limit=10)
        for p in posts:
            if p["id"] not in seen_ids:
                seen_ids.add(p["id"])
                all_posts.append({
                    "id":         p["id"],
                    "image_url":  p.get("media_url") or p.get("thumbnail_url", ""),
                    "caption":    p.get("caption", ""),
                    "location":   p.get("location", {}),
                    "timestamp":  p.get("timestamp", ""),
                    "permalink":  p.get("permalink", ""),
                    "hashtag":    tag,
                    "source":     "instagram",
                })
        if len(all_posts) >= max_posts:
            break

    return all_posts[:max_posts]


def _get_demo_posts() -> list:
    """Demo posts when no Instagram API key is configured."""
    return [
        {
            "id": "demo_001",
            "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8e/Pothole_in_road.jpg/320px-Pothole_in_road.jpg",
            "caption": "#pothole spotted on MG Road near the flyover! Please fix this #bangaloreroads #roaddamage",
            "location": {"name": "MG Road, Bengaluru", "lat": 12.9757, "lon": 77.6011},
            "timestamp": datetime.now().isoformat(),
            "permalink": "https://instagram.com/p/demo1",
            "hashtag": "pothole",
            "source": "instagram_demo",
        },
        {
            "id": "demo_002",
            "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8e/Pothole_in_road.jpg/320px-Pothole_in_road.jpg",
            "caption": "Huge khaddaa on Linking Road Bandra! #potholes #mumbairoads #badroads",
            "location": {"name": "Linking Road, Bandra, Mumbai"},
            "timestamp": datetime.now().isoformat(),
            "permalink": "https://instagram.com/p/demo2",
            "hashtag": "potholes",
            "source": "instagram_demo",
        },
        {
            "id": "demo_003",
            "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8e/Pothole_in_road.jpg/320px-Pothole_in_road.jpg",
            "caption": "Road completely destroyed near Connaught Place #delhiroads #pothole #खड्डा",
            "location": {"name": "Connaught Place, New Delhi"},
            "timestamp": datetime.now().isoformat(),
            "permalink": "https://instagram.com/p/demo3",
            "hashtag": "pothole",
            "source": "instagram_demo",
        },
        {
            "id": "demo_004",
            "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8e/Pothole_in_road.jpg/320px-Pothole_in_road.jpg",
            "caption": "Bad pothole near Chandni Chowk market area, very dangerous #indiaroads",
            "location": {"name": "Chandni Chowk, Delhi"},
            "timestamp": datetime.now().isoformat(),
            "permalink": "https://instagram.com/p/demo4",
            "hashtag": "indiaroads",
            "source": "instagram_demo",
        },
        {
            "id": "demo_005",
            "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8e/Pothole_in_road.jpg/320px-Pothole_in_road.jpg",
            "caption": "Huge pothole on Pune-Mumbai highway near Khopoli. Please repair! #puneroads #roaddamage",
            "location": {"name": "Pune-Mumbai Highway, Khopoli"},
            "timestamp": datetime.now().isoformat(),
            "permalink": "https://instagram.com/p/demo5",
            "hashtag": "puneroads",
            "source": "instagram_demo",
        },
    ]


# ─────────────────────────────────────────────────────────────────────────────
#  LOCATION PREDICTION
# ─────────────────────────────────────────────────────────────────────────────

def predict_location_from_caption(caption: str, existing_location: dict = None) -> dict:
    """
    Predict GPS coordinates from Instagram caption text using:
    1. Extract location mentions from caption (AI-powered)
    2. Geocode via OpenStreetMap Nominatim (free, no key needed)
    """
    if not caption:
        return existing_location or {}

    # Step 1: Extract location from caption using AI
    location_text = _extract_location_from_text(caption)
    if not location_text and existing_location:
        location_text = existing_location.get("name", "")

    if not location_text:
        return existing_location or {}

    # Step 2: Geocode with Nominatim
    coords = _geocode_nominatim(location_text + ", India")
    if coords:
        return {
            "name":   location_text,
            "lat":    coords["lat"],
            "lon":    coords["lon"],
            "source": "predicted_from_caption",
        }

    return existing_location or {"name": location_text}


def _extract_location_from_text(text: str) -> str:
    """
    Extract location name from caption using:
    1. Regex patterns for common Indian location formats
    2. AI fallback (Claude) if available
    """
    # Common Indian road/location patterns
    patterns = [
        r'(?:near|on|at|in)\s+([A-Z][a-zA-Z\s]+(?:Road|Rd|Street|St|Nagar|Marg|Highway|NH|SH|Flyover|Bridge|Chowk|Circle|Square))',
        r'([A-Z][a-zA-Z\s]+(?:Road|Rd|Street|St|Nagar|Marg|Highway))',
        r'(?:near|at|in)\s+([A-Z][a-zA-Z\s]{3,25}),?\s*([A-Z][a-zA-Z\s]+)',
        r'#([a-zA-Z]+roads?|[a-zA-Z]+streets?)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            loc = match.group(1).strip()
            if len(loc) > 4:
                return loc

    # AI-powered extraction via Claude
    if ANTHROPIC_KEY:
        return _ai_extract_location(text)

    # Simple keyword extraction fallback
    city_keywords = [
        "Mumbai", "Delhi", "Bangalore", "Bengaluru", "Chennai", "Kolkata",
        "Hyderabad", "Pune", "Ahmedabad", "Jaipur", "Lucknow", "Surat",
        "Raipur", "Bhopal", "Indore", "Nagpur", "Patna", "Chandigarh",
    ]
    for city in city_keywords:
        if city.lower() in text.lower():
            # Try to get more specific location
            idx = text.lower().find(city.lower())
            surrounding = text[max(0, idx-30):idx+len(city)+30]
            return surrounding.strip().split("#")[0].strip()

    return ""


def _ai_extract_location(caption: str) -> str:
    """Use Claude to extract location from caption."""
    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 100,
        "messages": [{
            "role": "user",
            "content": (
                f"Extract only the location/place name from this Instagram caption. "
                f"Return ONLY the location name, nothing else. If no location found, return empty string.\n\n"
                f"Caption: {caption[:300]}"
            )
        }]
    }
    try:
        r = _req.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
                "x-api-key": ANTHROPIC_KEY,
            }
        )
        with _req.urlopen(r, timeout=10, context=_ctx) as resp:
            data = json.loads(resp.read())
            for block in data.get("content", []):
                if block.get("type") == "text":
                    loc = block["text"].strip()
                    return loc if len(loc) > 2 else ""
    except Exception:
        pass
    return ""


def _geocode_nominatim(query: str) -> dict:
    """Geocode a location string using OpenStreetMap Nominatim (free)."""
    url = (
        f"https://nominatim.openstreetmap.org/search"
        f"?q={_parse.quote(query)}"
        f"&format=json&limit=1&countrycodes=in"
    )
    headers = {"User-Agent": "PotholeAI/1.0 (potholeai@gmail.com)"}
    try:
        r = _req.Request(url, headers=headers)
        with _req.urlopen(r, timeout=8, context=_ctx) as resp:
            results = json.loads(resp.read())
            if results:
                return {
                    "lat": float(results[0]["lat"]),
                    "lon": float(results[0]["lon"]),
                    "display_name": results[0].get("display_name", query),
                }
    except Exception:
        pass
    return {}


def predict_location_from_image_url(image_url: str) -> dict:
    """
    Predict location from image using Google Cloud Vision API.
    Detects: landmarks, text on signs, business names → geocode them.
    """
    if not GOOGLE_VISION_KEY:
        return {}

    payload = {
        "requests": [{
            "image": {"source": {"imageUri": image_url}},
            "features": [
                {"type": "LANDMARK_DETECTION", "maxResults": 3},
                {"type": "TEXT_DETECTION",     "maxResults": 1},
                {"type": "WEB_DETECTION",      "maxResults": 3},
            ]
        }]
    }

    url = f"https://vision.googleapis.com/v1/images:annotate?key={GOOGLE_VISION_KEY}"
    try:
        r = _req.Request(
            url, data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}
        )
        with _req.urlopen(r, timeout=15, context=_ctx) as resp:
            data = json.loads(resp.read())
            response = data.get("responses", [{}])[0]

            # 1. Try landmark detection first (most accurate)
            landmarks = response.get("landmarkAnnotations", [])
            if landmarks:
                lm = landmarks[0]
                locs = lm.get("locations", [])
                if locs:
                    latlon = locs[0].get("latLng", {})
                    return {
                        "name":   lm.get("description", ""),
                        "lat":    latlon.get("latitude"),
                        "lon":    latlon.get("longitude"),
                        "source": "google_vision_landmark",
                        "confidence": lm.get("score", 0),
                    }

            # 2. Try text detection → extract location → geocode
            text_annots = response.get("textAnnotations", [])
            if text_annots:
                full_text = text_annots[0].get("description", "")
                loc_name  = _extract_location_from_text(full_text)
                if loc_name:
                    coords = _geocode_nominatim(loc_name + ", India")
                    if coords:
                        return {
                            "name":   loc_name,
                            "lat":    coords["lat"],
                            "lon":    coords["lon"],
                            "source": "google_vision_text",
                        }

            # 3. Web detection for best guess location
            web = response.get("webDetection", {})
            entities = web.get("webEntities", [])
            for entity in entities:
                desc = entity.get("description", "")
                if any(kw in desc.lower() for kw in ["road", "street", "nagar", "city", "india"]):
                    coords = _geocode_nominatim(desc + ", India")
                    if coords:
                        return {
                            "name":   desc,
                            "lat":    coords["lat"],
                            "lon":    coords["lon"],
                            "source": "google_vision_web",
                        }

    except Exception:
        pass

    return {}


# ─────────────────────────────────────────────────────────────────────────────
#  MAIN PIPELINE — Process Instagram post → PotholeAI complaint
# ─────────────────────────────────────────────────────────────────────────────

def process_instagram_post(post: dict, detect_fn=None) -> dict:
    """
    Full pipeline:
    1. Get location (from post tag → caption AI → image vision)
    2. Download image
    3. Run YOLOv11 detection (if detect_fn provided)
    4. Return structured complaint dict
    """
    result = {
        "source":     "instagram",
        "ig_id":      post.get("id", ""),
        "ig_url":     post.get("permalink", ""),
        "ig_caption": post.get("caption", ""),
        "ig_hashtag": post.get("hashtag", ""),
        "timestamp":  post.get("timestamp", datetime.now().isoformat()),
        "location":   {},
        "detected":   False,
        "severity":   "Unknown",
        "confidence": 0.0,
    }

    # ── Step 1: Get location ──────────────────────────────────────────────────
    loc = post.get("location", {})

    # A. Instagram tagged location (most accurate)
    if loc and loc.get("lat"):
        result["location"] = {
            "name":   loc.get("name", ""),
            "lat":    loc["lat"],
            "lon":    loc["lon"],
            "source": "instagram_tag",
        }

    # B. Predict from caption
    elif post.get("caption"):
        predicted = predict_location_from_caption(
            post["caption"],
            existing_location={"name": loc.get("name", "")} if loc else {}
        )
        result["location"] = predicted

    # C. Predict from image (Google Vision)
    if not result["location"].get("lat") and post.get("image_url") and GOOGLE_VISION_KEY:
        vision_loc = predict_location_from_image_url(post["image_url"])
        if vision_loc:
            result["location"] = vision_loc

    # D. Geocode location name if we have name but no coords
    if result["location"].get("name") and not result["location"].get("lat"):
        coords = _geocode_nominatim(result["location"]["name"] + ", India")
        if coords:
            result["location"]["lat"] = coords["lat"]
            result["location"]["lon"] = coords["lon"]

    # ── Step 2: Download image ────────────────────────────────────────────────
    image_path = None
    if post.get("image_url"):
        image_path = _download_image(post["image_url"], post.get("id", "ig"))

    # ── Step 3: Run YOLOv11 detection ────────────────────────────────────────
    if image_path and detect_fn:
        try:
            detect_fn(image_path)
            # Load results
            complaints_path = "output/complaints.json"
            if os.path.exists(complaints_path):
                with open(complaints_path) as f:
                    raw = f.read().strip()
                complaints = json.loads(raw) if raw else []
                if complaints:
                    latest = complaints[-1]
                    result["detected"]   = True
                    result["severity"]   = latest.get("severity", "Unknown")
                    result["confidence"] = latest.get("confidence", 0.0)
        except Exception as e:
            result["detection_error"] = str(e)

    # ── Step 4: Build complaint ───────────────────────────────────────────────
    loc_data = result["location"]
    complaint = {
        "pothole_id":         f"IG-{post.get('id','')[:8].upper()}",
        "location":           loc_data.get("name", "Unknown — Instagram post"),
        "district":           _extract_district(loc_data.get("name", "")),
        "road":               _extract_road(loc_data.get("name", ""), post.get("caption", "")),
        "highway_km":         "—",
        "severity":           result["severity"] if result["detected"] else _estimate_severity(post.get("caption", "")),
        "confidence":         result["confidence"] if result["detected"] else 0.7,
        "status":             "Filed",
        "gps":                {"lat": loc_data.get("lat", 0), "lon": loc_data.get("lon", 0)},
        "assigned_to":        "PWD",
        "complaint_filed_at": datetime.now().isoformat(),
        "detected_at":        datetime.now().isoformat(),
        "re_scan_due":        "",
        "auto_verified_at":   "",
        "auto_escalated_at":  "",
        "source":             "instagram",
        "ig_url":             post.get("permalink", ""),
        "ig_caption":         (post.get("caption", "")[:100] + "...") if len(post.get("caption","")) > 100 else post.get("caption",""),
    }

    return complaint


def _download_image(url: str, post_id: str) -> str:
    """Download image from URL to temp file."""
    os.makedirs("output/ig_images", exist_ok=True)
    path = f"output/ig_images/{post_id}.jpg"
    if os.path.exists(path):
        return path
    try:
        r = _req.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with _req.urlopen(r, timeout=15, context=_ctx) as resp:
            with open(path, "wb") as f:
                f.write(resp.read())
        return path
    except Exception:
        return ""


def _extract_district(location_name: str) -> str:
    """Extract district/city from location name."""
    INDIA_CITIES = [
        "Mumbai", "Delhi", "Bangalore", "Bengaluru", "Chennai", "Kolkata",
        "Hyderabad", "Pune", "Ahmedabad", "Jaipur", "Lucknow", "Surat",
        "Raipur", "Bhopal", "Indore", "Nagpur", "Patna", "Chandigarh",
        "Bandra", "Andheri", "Thane", "Navi Mumbai", "Gurgaon", "Noida",
        "Ghaziabad", "Faridabad", "Coimbatore", "Kochi", "Visakhapatnam",
    ]
    for city in INDIA_CITIES:
        if city.lower() in location_name.lower():
            return city
    parts = location_name.split(",")
    return parts[-1].strip() if len(parts) > 1 else location_name.split()[0] if location_name else "Unknown"


def _extract_road(location_name: str, caption: str) -> str:
    """Extract road name from location or caption."""
    text = location_name + " " + caption
    road_match = re.search(
        r'([A-Z][a-zA-Z\s]+(?:Road|Rd|Street|Marg|Highway|NH|SH|Lane|Avenue))',
        text
    )
    return road_match.group(1).strip() if road_match else location_name.split(",")[0] if location_name else "Unknown Road"


def _estimate_severity(caption: str) -> str:
    """Estimate severity from caption keywords."""
    caption_lower = caption.lower()
    if any(w in caption_lower for w in ["huge", "massive", "dangerous", "accident", "बड़ा", "गहरा", "deep", "big"]):
        return "Critical"
    if any(w in caption_lower for w in ["pothole", "bad", "broken", "damaged", "खड्डा"]):
        return "Moderate"
    return "Minor"


# ─────────────────────────────────────────────────────────────────────────────
#  BATCH PROCESS — Scrape + Detect + Save
# ─────────────────────────────────────────────────────────────────────────────

def run_instagram_pipeline(detect_fn=None, max_posts: int = 20) -> list:
    """
    Full pipeline:
    1. Scrape Instagram for pothole posts
    2. Predict location for each
    3. Run detection on each image
    4. Return list of complaints ready to save to DB
    """
    posts      = ig_search_potholes(max_posts=max_posts)
    complaints = []

    for post in posts:
        try:
            complaint = process_instagram_post(post, detect_fn=detect_fn)
            if complaint.get("location", {}).get("lat"):  # Only save if we have location
                complaints.append(complaint)
            time.sleep(0.5)  # Rate limiting
        except Exception:
            continue

    return complaints
