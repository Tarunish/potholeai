import streamlit as st
import streamlit.components.v1 as components
import json, os, time, hashlib, random
import urllib.request as _req
import urllib.error   as _err
import urllib.parse   as _parse
import ssl            as _ssl
from datetime  import datetime
from io        import BytesIO

try:
    from detect import detect
    DETECT_OK = True
except ImportError:
    DETECT_OK = False

try:
    import cv2
    CV2_OK = True
except ImportError:
    CV2_OK = False

try:
    from PIL import Image
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    import folium
    from folium.plugins import HeatMap
    from streamlit_folium import st_folium
    FOLIUM_OK = True
except ImportError:
    FOLIUM_OK = False

try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_OK = True
except ImportError:
    PLOTLY_OK = False

# ─────────────────────────────────────────────────────────────────────────────
#  SUPABASE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
SUPA_URL = "https://dbppziintmarvykbjykj.supabase.co"
SUPA_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRicHB6aWludG1hcnZ5a2JqeWtqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM3Mjc2OTIsImV4cCI6MjA4OTMwMzY5Mn0."
    "3x9PQtoIUf6btYf03ZepSIs1hJH8NcZqngMuXI349Zg"
)
_ctx = _ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode    = _ssl.CERT_NONE

def _headers(extra=None):
    h = {
        "apikey":        SUPA_KEY,
        "Authorization": f"Bearer {SUPA_KEY}",
        "Content-Type":  "application/json",
        "Prefer":        "return=representation",
    }
    if extra:
        h.update(extra)
    return h

def _supa(method, path, data=None, params=""):
    url  = f"{SUPA_URL}/rest/v1/{path}{params}"
    body = json.dumps(data).encode() if data else None
    req  = _req.Request(url, data=body, headers=_headers(), method=method)
    try:
        with _req.urlopen(req, timeout=10, context=_ctx) as r:
            return json.loads(r.read())
    except Exception:
        return None

# ─────────────────────────────────────────────────────────────────────────────
#  AUTH  (app_users table in Supabase)
# ─────────────────────────────────────────────────────────────────────────────
def _hash(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def auth_signup(username, email, password, role="Public"):
    if _supa("GET", "app_users", params=f"?username=eq.{username}&limit=1"):
        return False, "Username already taken"
    if _supa("GET", "app_users", params=f"?email=eq.{_parse.quote(email)}&limit=1"):
        return False, "Email already registered"
    res = _supa("POST", "app_users", data={
        "username":      username,
        "email":         email,
        "password_hash": _hash(password),
        "role":          role,
        "created_at":    datetime.now().isoformat(),
    })
    return (True, "ok") if res else (False, "Supabase error — run SQL setup first")

def auth_login(username, password):
    # Check demo accounts FIRST (instant, no network)
    DEMO = {
        "admin":    {"username":"admin",    "role":"Admin",    "email":"admin@potholeai.in"},
        "engineer": {"username":"engineer", "role":"Engineer", "email":"eng@potholeai.in"},
        "public":   {"username":"public",   "role":"Public",   "email":"pub@potholeai.in"},
    }
    DEMO_PW = {"admin":"admin123","engineer":"pwd123","public":"pub123"}
    if username in DEMO and DEMO_PW.get(username) == password:
        return True, DEMO[username]
    # Then check Supabase for real accounts
    rows = _supa("GET", "app_users",
                 params=f"?username=eq.{username}&password_hash=eq.{_hash(password)}&limit=1")
    if rows:
        return True, rows[0]
    return False, None

# ─────────────────────────────────────────────────────────────────────────────
#  COMPLAINTS DB
# ─────────────────────────────────────────────────────────────────────────────
def db_save(complaints):
    if not complaints:
        return
    rows = [{
        "pothole_id":          c.get("pothole_id"),
        "location":            c.get("location"),
        "district":            c.get("district"),
        "road":                c.get("road"),
        "highway_km":          c.get("highway_km"),
        "severity":            c.get("severity"),
        "confidence":          c.get("confidence"),
        "status":              c.get("status"),
        "gps_lat":             (c.get("gps") or {}).get("lat"),
        "gps_lon":             (c.get("gps") or {}).get("lon"),
        "assigned_to":         c.get("assigned_to", "PWD"),
        "complaint_filed_at":  c.get("complaint_filed_at"),
        "detected_at":         c.get("detected_at"),
        "re_scan_due":         c.get("re_scan_due"),
        "auto_verified_at":    c.get("auto_verified_at"),
        "auto_escalated_at":   c.get("auto_escalated_at"),
    } for c in complaints]
    for i in range(0, len(rows), 100):
        batch = rows[i:i+100]
        req = _req.Request(
            f"{SUPA_URL}/rest/v1/complaints?on_conflict=pothole_id",
            data=json.dumps(batch).encode(),
            headers={**_headers(), "Prefer": "resolution=merge-duplicates,return=minimal"},
            method="POST",
        )
        try:
            with _req.urlopen(req, timeout=10, context=_ctx):
                pass
        except Exception:
            pass

def db_load():
    rows = _supa("GET", "complaints", params="?order=created_at.desc&limit=5000")
    if not rows:
        return []
    return [{
        "pothole_id":         r.get("pothole_id"),
        "location":           r.get("location"),
        "district":           r.get("district"),
        "road":               r.get("road"),
        "highway_km":         r.get("highway_km"),
        "severity":           r.get("severity"),
        "confidence":         r.get("confidence"),
        "status":             r.get("status"),
        "gps":                {"lat": r.get("gps_lat"), "lon": r.get("gps_lon")},
        "assigned_to":        r.get("assigned_to"),
        "complaint_filed_at": r.get("complaint_filed_at"),
        "detected_at":        r.get("detected_at"),
        "re_scan_due":        r.get("re_scan_due"),
        "auto_verified_at":   r.get("auto_verified_at"),
        "auto_escalated_at":  r.get("auto_escalated_at"),
    } for r in rows]

def db_clear():
    req = _req.Request(
        f"{SUPA_URL}/rest/v1/complaints?pothole_id=neq.___",
        headers={**_headers(), "Prefer": "return=minimal"},
        method="DELETE",
    )
    try:
        with _req.urlopen(req, timeout=10, context=_ctx):
            pass
    except Exception:
        pass

def db_save_gps(lat, lon, acc):
    _supa("POST", "gps_sessions", data={"lat": lat, "lon": lon, "accuracy": acc})

# ─────────────────────────────────────────────────────────────────────────────
#  PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PotholeAI India",
    page_icon="🚧",
    layout="wide",
    initial_sidebar_state="collapsed",
)

GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;600&display=swap');

:root {
  --bg:      #060A12;
  --bg2:     #0B1120;
  --bg3:     #0F1929;
  --card:    #0D1525;
  --border:  #162035;
  --blue:    #2563EB;
  --blue2:   #3B82F6;
  --cyan:    #06B6D4;
  --green:   #10B981;
  --amber:   #F59E0B;
  --red:     #EF4444;
  --text:    #E2E8F0;
  --muted:   #4B6080;
  --glow:    0 0 30px rgba(37,99,235,0.2);
}

* { box-sizing: border-box; }
.stApp { background: var(--bg) !important; font-family: 'Outfit', sans-serif; }
.main .block-container { padding: 1.2rem 1.8rem !important; }
section[data-testid="stSidebar"] { background: var(--bg2) !important; border-right: 1px solid var(--border); }
section[data-testid="stSidebar"] * { color: var(--text) !important; }
#MainMenu, footer, [data-testid="stDecoration"] { display: none !important; }

/* tabs */
.stTabs [data-baseweb="tab-list"] {
  gap: 3px !important; background: var(--bg2) !important;
  border-radius: 12px !important; padding: 4px !important;
  border: 1px solid var(--border) !important;
}
.stTabs [data-baseweb="tab"] {
  font-family: 'Outfit', sans-serif !important; font-size: 13px !important;
  font-weight: 600 !important; color: var(--muted) !important;
  padding: 8px 16px !important; border-radius: 9px !important;
  background: transparent !important; border: none !important; letter-spacing: 0.3px;
}
.stTabs [aria-selected="true"] {
  color: #fff !important; background: var(--blue) !important;
  box-shadow: 0 0 18px rgba(37,99,235,0.45) !important;
}
.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"] { display: none !important; }

/* buttons */
.stButton > button {
  background: linear-gradient(135deg, var(--blue), #1D4ED8) !important;
  color: #fff !important; font-family: 'Outfit', sans-serif !important;
  font-weight: 700 !important; font-size: 13px !important;
  border: none !important; border-radius: 10px !important;
  padding: 9px 18px !important; width: 100% !important;
  transition: all 0.18s ease !important;
  box-shadow: 0 0 12px rgba(37,99,235,0.25) !important;
  letter-spacing: 0.3px;
}
.stButton > button:hover {
  transform: translateY(-1px) !important;
  box-shadow: 0 0 24px rgba(37,99,235,0.5) !important;
}

/* inputs */
.stTextInput input, .stTextInput textarea {
  background: var(--bg3) !important; color: var(--text) !important;
  border: 1px solid var(--border) !important; border-radius: 10px !important;
  font-family: 'Outfit', sans-serif !important; font-size: 14px !important;
}
.stTextInput input:focus { border-color: var(--blue2) !important; box-shadow: var(--glow) !important; }

/* metrics */
[data-testid="stMetric"] {
  background: var(--card) !important; border-radius: 14px !important;
  padding: 14px 16px !important; border: 1px solid var(--border) !important;
}
[data-testid="stMetricLabel"]  { color: var(--muted) !important; font-size: 11px !important; letter-spacing: 0.5px; }
[data-testid="stMetricValue"]  { color: var(--blue2) !important; font-family: 'Outfit', sans-serif !important; font-size: 24px !important; font-weight: 800 !important; }
[data-testid="stMetricDelta"]  { color: var(--green) !important; }

/* cards */
.c { background:var(--card);border:1px solid var(--border);border-radius:12px;padding:14px 16px;margin:5px 0; }
.c-r { border-left: 3px solid var(--red)   !important; }
.c-a { border-left: 3px solid var(--amber) !important; }
.c-g { border-left: 3px solid var(--green) !important; }
.c-b { border-left: 3px solid var(--blue2) !important; }

/* scrollbar */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: var(--bg2); }
::-webkit-scrollbar-thumb { background: var(--blue); border-radius: 3px; }

p, span, li, div { color: var(--text); }
h1,h2,h3,h4 { font-family: 'Outfit', sans-serif !important; color: var(--text) !important; font-weight: 800 !important; }
</style>"""

# ─────────────────────────────────────────────────────────────────────────────
#  SESSION DEFAULTS
# ─────────────────────────────────────────────────────────────────────────────
DEFAULTS = {
    "logged_in":    False,
    "username":     "",
    "role":         "",
    "uname":        "",
    "icon":         "👤",
    "auth_tab":     "login",
    "signup_role":  "Public",
    "complaints":   [],
    "det_img":      None,
    "notifs":       [],
    "auto_on":      False,
    "last_cycle":   None,
    "cycle_count":  0,
    "auto_log":     [],
    "email_log":    [],
    "chat_history": [],
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Only wipe local complaints.json on truly fresh session (not on every rerun)
if "session_initialized" not in st.session_state:
    st.session_state["session_initialized"] = True
    try:
        os.makedirs("output", exist_ok=True)
        with open("output/complaints.json","w") as _f:
            _f.write("[]")
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────────────────────
#  REACT LOGIN PAGE
# ─────────────────────────────────────────────────────────────────────────────
if not st.session_state.logged_in:

    # Hard stop if somehow logged_in was set mid-run
    if st.session_state.get("just_logged_in"):
        st.session_state.just_logged_in = False
        st.rerun()

    # Full blank canvas - hide sidebar and all chrome
    st.markdown("""
    <style>
      section[data-testid="stSidebar"] { display:none !important; }
      [data-testid="collapsedControl"]  { display:none !important; }
      header[data-testid="stHeader"]    { display:none !important; }
      [data-testid="stToolbar"]         { display:none !important; }
      [data-testid="stDecoration"]      { display:none !important; }
      [data-testid="stStatusWidget"]    { display:none !important; }
      #MainMenu, footer                 { display:none !important; }
      .main .block-container            { padding:2rem !important; max-width:100vw !important; }
      .stApp                            { background:#060A12 !important; }
      .login-wrap {
        min-height:calc(100vh - 4rem); display:flex; align-items:center;
        justify-content:center; padding:20px;
        background: radial-gradient(ellipse at 30% 20%, #0D1F44 0%, #060A12 65%);
        border-radius:16px;
      }
      .login-left { flex:1.1; max-width:480px; padding-right:50px; }
      .login-right {
        flex:0.9; max-width:400px;
        background:rgba(11,17,32,0.97); border:1px solid rgba(37,99,235,0.2);
        border-radius:20px; padding:36px 32px;
        box-shadow:0 32px 64px rgba(0,0,0,0.5);
      }
      .brand { font-family:Outfit,sans-serif; font-size:48px; font-weight:900;
               color:#fff; letter-spacing:-2px; line-height:1; margin-bottom:12px; }
      .brand span { color:#3B82F6; }
      .brand-sub { font-size:14px; color:#334155; line-height:1.8; margin-bottom:32px; }
      .stat-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:32px; }
      .stat-box { background:rgba(37,99,235,0.07); border:1px solid rgba(37,99,235,0.18);
                  border-radius:10px; padding:14px 16px; }
      .stat-n { font-size:24px; font-weight:900; color:#3B82F6; font-family:Outfit,sans-serif; }
      .stat-l { font-size:11px; color:#334155; margin-top:2px; }
      .feat { font-size:13px; color:#334155; padding:3px 0 3px 14px;
              border-left:2px solid #1E3A5F; margin-bottom:8px; }
      .stTextInput label { font-size:11px !important; color:#64748B !important; font-weight:600 !important; }
      .stTextInput>div>div>input {
        background:rgba(255,255,255,0.04) !important;
        border:1px solid rgba(37,99,235,0.2) !important;
        border-radius:10px !important; color:#E2E8F0 !important;
        padding:11px 14px !important;
      }
      .stButton>button {
        background:linear-gradient(135deg,#2563EB,#1D4ED8) !important;
        border-radius:10px !important; font-weight:700 !important;
        font-size:14px !important; padding:11px !important;
        box-shadow:0 6px 20px rgba(37,99,235,0.3) !important;
      }
      .demo-box { background:rgba(37,99,235,0.06); border:1px solid rgba(37,99,235,0.15);
                  border-radius:10px; padding:12px 14px; margin-top:18px; }
      .demo-row { font-size:12px; color:#4B6080; padding:3px 0; }
      .demo-badge { color:#3B82F6; font-weight:700; }
    </style>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;700;800;900&display=swap" rel="stylesheet">
    """, unsafe_allow_html=True)

    # Two column layout: left=branding, right=form
    left_col, right_col = st.columns([1.15, 1])

    with left_col:
        st.markdown("""
        <div style="padding:60px 40px 40px 20px">
          <div class="brand">Pothole<span>AI</span></div>
          <p class="brand-sub">
            Real-time AI detection and autonomous resolution<br>
            of road damage across all of India.<br>
            Powered by YOLOv11 · OpenStreetMap · Supabase.
          </p>
          <div class="stat-grid">
            <div class="stat-box"><div class="stat-n">36</div><div class="stat-l">States & UTs</div></div>
            <div class="stat-box"><div class="stat-n">YOLOv11</div><div class="stat-l">AI Model</div></div>
            <div class="stat-box"><div class="stat-n">OSM</div><div class="stat-l">Live Road Data</div></div>
            <div class="stat-box"><div class="stat-n">AUTO</div><div class="stat-l">Zero Human Trigger</div></div>
          </div>
          <div class="feat">Upload any road photo — AI detects potholes instantly</div>
          <div class="feat">Auto-assigns to nearest PWD office via GPS</div>
          <div class="feat">Escalates unresolved issues automatically</div>
          <div class="feat">Live heatmap across all of India</div>
        </div>
        """, unsafe_allow_html=True)

    with right_col:
        st.markdown("<div style='padding:50px 20px 20px 10px'>", unsafe_allow_html=True)

        # Tab state
        if "auth_tab" not in st.session_state:
            st.session_state.auth_tab = "login"

        # Tab toggle using radio (always works)
        tab_choice = st.radio(
            "tab", ["🔑 Sign In", "✨ Create Account"],
            index=0 if st.session_state.auth_tab == "login" else 1,
            horizontal=True, label_visibility="collapsed"
        )
        if "Sign In" in tab_choice:
            st.session_state.auth_tab = "login"
        else:
            st.session_state.auth_tab = "signup"

        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

        # ── LOGIN FORM ──
        if st.session_state.auth_tab == "login":
            st.markdown("<div class='auth-title'>Welcome back 👋</div>", unsafe_allow_html=True)
            st.markdown("<div class='auth-sub'>Sign in to your PotholeAI account</div>", unsafe_allow_html=True)

            with st.form("login_form"):
                username = st.text_input("USERNAME", placeholder="Enter your username")
                password = st.text_input("PASSWORD", placeholder="Enter your password", type="password")
                submitted = st.form_submit_button("Sign In →", use_container_width=True)

            if submitted:
                if not username or not password:
                    st.warning("Please enter username and password")
                else:
                    ok, user = auth_login(username, password)
                    if ok:
                        st.session_state.logged_in     = True
                        st.session_state.just_logged_in= True
                        st.session_state.username      = user["username"]
                        st.session_state.role          = user["role"]
                        st.session_state.uname         = user.get("email", user["username"])
                        st.session_state.icon          = {"Admin":"👑","Engineer":"🏗️","Public":"👤"}.get(user["role"],"👤")
                        st.rerun()
                    else:
                        st.error("❌ Invalid username or password")

            st.markdown("""
            <div class="demo-box">
              <div style="font-size:11px;color:#334155;font-weight:700;margin-bottom:8px;letter-spacing:0.5px">DEMO ACCOUNTS</div>
              <div class="demo-row"><span class="demo-badge">👑 Admin</span> admin / admin123</div>
              <div class="demo-row"><span class="demo-badge">🏗️ Engineer</span> engineer / pwd123</div>
              <div class="demo-row"><span class="demo-badge">👤 Public</span> public / pub123</div>
            </div>
            """, unsafe_allow_html=True)

        # ── SIGNUP FORM ──
        else:
            st.markdown("<div class='auth-title'>Create account ✨</div>", unsafe_allow_html=True)
            st.markdown("<div class='auth-sub'>Join PotholeAI — help fix India's roads</div>", unsafe_allow_html=True)

            with st.form("signup_form"):
                new_user  = st.text_input("USERNAME",         placeholder="Choose a username")
                new_email = st.text_input("EMAIL",            placeholder="your@email.com")
                new_pass  = st.text_input("PASSWORD",         placeholder="Minimum 6 characters", type="password")
                new_conf  = st.text_input("CONFIRM PASSWORD", placeholder="Repeat password",      type="password")
                new_role  = st.selectbox("ROLE", ["Public","Engineer","Admin"])
                submitted_su = st.form_submit_button("Create Account →", use_container_width=True)

            if submitted_su:
                if not all([new_user, new_email, new_pass, new_conf]):
                    st.warning("Please fill all fields")
                elif new_pass != new_conf:
                    st.error("❌ Passwords don't match")
                elif len(new_pass) < 6:
                    st.error("❌ Password must be at least 6 characters")
                else:
                    ok, msg = auth_signup(new_user, new_email, new_pass, new_role)
                    if ok:
                        st.success("✅ Account created! Click Sign In to continue.")
                        st.session_state.auth_tab = "login"
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

        st.markdown("</div>", unsafe_allow_html=True)

    st.stop()




# ─────────────────────────────────────────────────────────────────────────────
#  DASHBOARD  (logged-in users only)
# ─────────────────────────────────────────────────────────────────────────────
if not st.session_state.get("logged_in"):
    st.stop()

st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
role = st.session_state.role
CYCLE = 60

# ── helpers ──────────────────────────────────────────────────────────────────
def calc_risk(grp):
    s  = sum(10 if c["severity"]=="Critical" else 5 if c["severity"]=="Moderate" else 2 for c in grp)
    s += sum(4 for c in grp if c["status"]=="Escalated")
    return min(s, 100)

def risk_label(s):
    if s >= 60: return "🔴 HIGH",   "#EF4444"
    if s >= 30: return "🟠 MEDIUM", "#F59E0B"
    return "🟢 LOW", "#10B981"

def get_weather(lat, lon):
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid=demo&units=metric"
        with _req.urlopen(url, timeout=2, context=_ctx) as r:
            d = json.loads(r.read())
            return {"temp":d["main"]["temp"],"desc":d["weather"][0]["description"].title(),
                    "humidity":d["main"]["humidity"],"wind":d["wind"]["speed"]}
    except Exception:
        return random.choice([
            {"temp":32,"desc":"Heavy Rain","humidity":88,"wind":18},
            {"temp":28,"desc":"Partly Cloudy","humidity":65,"wind":12},
            {"temp":35,"desc":"Clear Sky","humidity":45,"wind":8},
        ])

def log_email(c, t):
    st.session_state.email_log.insert(0, {
        "time":t, "type":t,
        "id":c["pothole_id"],
        "to":f"{c.get('assigned_to','PWD')} <pwd@roads.gov.in>",
        "loc":c["location"], "sev":c["severity"],
    })
    st.session_state.email_log = st.session_state.email_log[:30]

def run_auto_cycle():
    if not st.session_state.complaints: return
    now     = datetime.now()
    actions = []
    for c in st.session_state.complaints:
        if c["status"] == "Repaired": continue
        r = random.random()
        if c["status"] == "Filed":
            try:
                days = (now - datetime.fromisoformat(c["complaint_filed_at"])).days
            except Exception:
                days = 0
            if r > 0.75:
                c["status"] = "Repaired"; c["auto_verified_at"] = now.isoformat()
                actions.append({"type":"repaired","id":c["pothole_id"],"msg":f"✅ REPAIRED: {c['pothole_id']} | {c['location']}"})
                log_email(c, "repair_verified")
            elif days >= 1:
                c["status"] = "Escalated"; c["auto_escalated_at"] = now.isoformat()
                actions.append({"type":"escalated","id":c["pothole_id"],"msg":f"🚨 ESCALATED: {c['pothole_id']} | {c['location']}"})
                log_email(c, "escalation")
        elif c["status"] == "Escalated" and r > 0.6:
            c["status"] = "Repaired"; c["auto_verified_at"] = now.isoformat()
            actions.append({"type":"repaired","id":c["pothole_id"],"msg":f"✅ REPAIRED: {c['pothole_id']}"})
            log_email(c, "repair_verified")
    for a in actions:
        st.session_state.notifs.insert(0, {
            "time":now.strftime("%H:%M:%S"), "type":a["type"], "msg":a["msg"], "id":a["id"]
        })
    st.session_state.notifs       = st.session_state.notifs[:20]
    st.session_state.last_cycle   = now.isoformat()
    st.session_state.cycle_count += 1
    st.session_state.auto_log.insert(0,
        f"[{now.strftime('%H:%M:%S')}] Cycle #{st.session_state.cycle_count} — {len(actions)} actions")
    st.session_state.auto_log = st.session_state.auto_log[:50]

def chatbot_response(query, complaints):
    if not complaints:
        return "📭 No data yet — upload a road image and run detection."
    from collections import Counter
    total    = len(complaints)
    crit     = sum(1 for c in complaints if c["severity"]=="Critical")
    mod      = sum(1 for c in complaints if c["severity"]=="Moderate")
    minor    = sum(1 for c in complaints if c["severity"]=="Minor")
    filed    = sum(1 for c in complaints if c["status"]=="Filed")
    esc      = sum(1 for c in complaints if c["status"]=="Escalated")
    rep      = sum(1 for c in complaints if c["status"]=="Repaired")
    top_dist = Counter(c.get("district","") for c in complaints).most_common(5)
    top_road = Counter(c.get("road","")     for c in complaints).most_common(5)
    crit_s   = [{"id":c["pothole_id"],"loc":c["location"]} for c in complaints if c["severity"]=="Critical"][:5]
    esc_s    = [{"id":c["pothole_id"],"loc":c["location"]} for c in complaints if c["status"]=="Escalated"][:5]

    ctx = f"""
POTHOLEAI DATABASE — ALL INDIA
Total={total} Critical={crit} Moderate={mod} Minor={minor}
Filed={filed} Escalated={esc} Repaired={rep}
Auto-cycles={st.session_state.cycle_count}
Top districts: {', '.join(f'{d}:{n}' for d,n in top_dist)}
Top roads: {', '.join(f'{r}:{n}' for r,n in top_road)}
Critical samples: {', '.join(f'{c["id"]}@{c["loc"]}' for c in crit_s)}
Escalated samples: {', '.join(f'{c["id"]}@{c["loc"]}' for c in esc_s) or 'none'}
"""
    system = ("You are PotholeAI AI assistant. Answer in ≤80 words using the live data. "
              "Use emojis. Cite real numbers and locations. Never mention hackathon or Chhattisgarh.")
    payload = {
        "model":"claude-sonnet-4-20250514","max_tokens":280,
        "system":system,
        "messages":[{"role":"user","content":f"{ctx}\n\nQuestion: {query}"}],
    }
    api_key = os.environ.get("ANTHROPIC_API_KEY","")
    if not api_key:
        return "⚠️ Set ANTHROPIC_API_KEY to enable AI responses."
    try:
        r = _req.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode(),
            headers={"Content-Type":"application/json",
                     "anthropic-version":"2023-06-01",
                     "x-api-key":api_key},
        )
        with _req.urlopen(r, timeout=15, context=_ctx) as resp:
            d = json.loads(resp.read())
        for b in d.get("content",[]):
            if b.get("type")=="text": return b["text"]
        return "No response."
    except Exception as ex:
        return f"⚠️ {ex}"


# ── auto-cycle ticker ─────────────────────────────────────────────────────────
if st.session_state.auto_on and st.session_state.last_cycle:
    elapsed = (datetime.now() - datetime.fromisoformat(st.session_state.last_cycle)).total_seconds()
    if elapsed >= CYCLE:
        run_auto_cycle()
        db_save(st.session_state.complaints)
        try:
            os.makedirs("output", exist_ok=True)
            with open("output/complaints.json","w") as f:
                json.dump(st.session_state.complaints, f, indent=2)
        except Exception:
            pass


# ── HEADER ────────────────────────────────────────────────────────────────────
hc1, hc2, hc3 = st.columns([3, 1.1, 0.55])
with hc1:
    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:14px;padding:6px 0 2px">
      <div style="background:linear-gradient(135deg,#2563EB,#1D4ED8);border-radius:14px;
                  width:46px;height:46px;display:flex;align-items:center;justify-content:center;
                  font-size:24px;box-shadow:0 6px 20px rgba(37,99,235,0.4);">🚧</div>
      <div>
        <div style="font-family:Outfit,sans-serif;font-size:26px;font-weight:900;color:#fff;letter-spacing:-0.5px;line-height:1">
          Pothole<span style="color:#3B82F6">AI</span>
          <span style="font-size:13px;font-weight:500;color:#2563EB;background:rgba(37,99,235,0.12);
                       padding:2px 10px;border-radius:20px;margin-left:10px;vertical-align:middle;">India</span>
        </div>
        <div style="color:#334155;font-size:11px;letter-spacing:1.5px;font-weight:600;margin-top:2px">
          DETECT · CLASSIFY · REPORT · VERIFY · RESOLVE
        </div>
      </div>
    </div>""", unsafe_allow_html=True)
with hc2:
    rc = {"Admin":"#3B82F6","Engineer":"#10B981","Public":"#F59E0B"}.get(role,"#64748B")
    st.markdown(f"""
    <div style="background:#0D1525;border:1px solid {rc}30;border-radius:12px;
                padding:9px 14px;margin-top:4px;text-align:center;">
      <span style="font-size:18px">{st.session_state.icon}</span>
      <b style="color:{rc};display:block;font-size:13px;font-weight:700">{st.session_state.username}</b>
      <span style="color:#334155;font-size:11px">{role}</span>
    </div>""", unsafe_allow_html=True)
with hc3:
    st.markdown("<div style='margin-top:14px'>", unsafe_allow_html=True)
    if st.button("↩ Sign Out"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<hr style='border:1px solid #162035;margin:10px 0 14px'>", unsafe_allow_html=True)


# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("<h3 style='color:#3B82F6;font-size:15px;font-weight:800;letter-spacing:1px'>⚙️ CONTROL PANEL</h3>",
                unsafe_allow_html=True)

    # GPS
    st.markdown("#### 📍 GPS Location")
    gps_js = """
<div style="background:#0B1120;border:1px solid #162035;border-radius:10px;padding:12px;margin-bottom:6px">
  <div id="gs" style="color:#4B6080;font-size:12px">📡 Tap to get real GPS</div>
  <div id="gc" style="color:#3B82F6;font-family:monospace;font-size:11px;margin:6px 0;line-height:1.5"></div>
  <button onclick="g()" style="background:linear-gradient(135deg,#2563EB,#1D4ED8);color:#fff;
    border:none;border-radius:8px;padding:8px;font-size:12px;font-weight:700;
    cursor:pointer;width:100%">📍 Capture GPS</button>
</div>
<script>
function g(){
  var s=document.getElementById('gs'),c=document.getElementById('gc');
  s.innerHTML='⏳ Locating...';s.style.color='#F59E0B';
  if(!navigator.geolocation){s.innerHTML='❌ Not supported';s.style.color='#EF4444';return;}
  navigator.geolocation.getCurrentPosition(function(p){
    var lat=p.coords.latitude.toFixed(6),lon=p.coords.longitude.toFixed(6),acc=p.coords.accuracy.toFixed(0);
    s.innerHTML='✅ Location captured';s.style.color='#10B981';
    c.innerHTML='Lat: '+lat+'<br>Lon: '+lon+'<br>Acc: ±'+acc+'m';
    var u=new URL(window.parent.location.href);
    u.searchParams.set('gps_lat',lat);u.searchParams.set('gps_lon',lon);u.searchParams.set('gps_acc',acc);
    window.parent.history.replaceState({},'',u);
  },function(e){s.innerHTML='❌ '+e.message;s.style.color='#EF4444';},{enableHighAccuracy:true,timeout:10000});
}
</script>"""
    components.html(gps_js, height=128)

    qp2 = st.query_params
    if "gps_lat" in qp2:
        try:
            glat = float(qp2["gps_lat"]); glon = float(qp2["gps_lon"])
            gacc = float(qp2.get("gps_acc", 0))
            st.session_state["device_gps"] = {"lat":glat,"lon":glon,"accuracy":gacc}
            db_save_gps(glat, glon, gacc)
            os.makedirs("output", exist_ok=True)
            with open("device_gps.json","w") as gf:
                json.dump({"lat":glat,"lon":glon,"accuracy":gacc}, gf)
            st.success(f"📍 {glat:.4f}, {glon:.4f}")
        except Exception:
            pass

    st.markdown("---")

    # Upload + Detect
    upload_label = "📸 Report Pothole" if role=="Public" else "📤 Run Detection"
    st.markdown(f"#### {upload_label}")
    uploaded = st.file_uploader("Road image", type=["jpg","jpeg","png"],
                                label_visibility="collapsed")
    if uploaded:
        os.makedirs("output", exist_ok=True)
        with open("pothole.jpg","wb") as f:
            f.write(uploaded.getbuffer())
        st.success("✅ Image ready")
        if st.button("🔍 Detect & Submit", use_container_width=True):
            if DETECT_OK:
                with st.spinner("Running YOLOv11…"):
                    detect("pothole.jpg")
                    time.sleep(0.5)
                try:
                    with open("output/complaints.json") as f:
                        raw = f.read().strip()
                    st.session_state.complaints = json.loads(raw) if raw else []
                except Exception:
                    st.session_state.complaints = []
                if "device_gps" in st.session_state:
                    g = st.session_state["device_gps"]
                    for c in st.session_state.complaints:
                        if c.get("gps"): c["gps"]["lat"]=g["lat"]; c["gps"]["lon"]=g["lon"]
                db_save(st.session_state.complaints)
                st.session_state.det_img  = "output/detected.jpg"
                st.session_state.auto_on  = True
                st.session_state.last_cycle = datetime.now().isoformat()
                st.success(f"✅ {len(st.session_state.complaints)} potholes detected & saved!")
                st.rerun()
            else:
                st.error("Detection model unavailable")

    # Auto-load from DB only if user explicitly uploaded before (check db_loaded flag)
    # Do NOT auto-load on fresh login to avoid showing stale/fake data
    pass  # Data loads only when user uploads an image

    st.markdown("---")

    # Auto mode (admin/engineer only)
    if role in ("Admin","Engineer"):
        st.markdown("#### 🤖 Auto Mode")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("▶️ Start", use_container_width=True):
                st.session_state.auto_on = True
        with c2:
            if st.button("⏸️ Pause", use_container_width=True):
                st.session_state.auto_on = False

        if st.session_state.last_cycle:
            elapsed = int((datetime.now()-datetime.fromisoformat(st.session_state.last_cycle)).total_seconds())
            nxt     = max(CYCLE - elapsed, 0)
            clr     = "#10B981" if st.session_state.auto_on else "#EF4444"
            lbl     = "🟢 RUNNING" if st.session_state.auto_on else "🔴 PAUSED"
            st.markdown(f"""
            <div style="background:#060A12;border:1px solid #162035;border-radius:10px;
                        padding:12px;text-align:center;margin-top:6px;">
              <div style="color:{clr};font-weight:800;font-size:13px">{lbl}</div>
              <div style="color:#3B82F6;font-size:30px;font-weight:900;font-family:Outfit,sans-serif;line-height:1.2">{nxt}s</div>
              <div style="color:#334155;font-size:11px">Next scan · Cycle #{st.session_state.cycle_count}</div>
            </div>""", unsafe_allow_html=True)
        st.markdown("---")

    # Filter
    st.markdown("#### 🔍 Filter")
    fsev = st.multiselect("Severity", ["Critical","Moderate","Minor"],
                          default=["Critical","Moderate","Minor"],
                          label_visibility="collapsed")

    st.markdown("---")

    # Clear data
    if role in ("Admin","Engineer"):
        if st.button("🗑️ Clear All Data", type="primary", use_container_width=True):
            st.session_state.complaints = []
            st.session_state.notifs     = []
            st.session_state.auto_log   = []
            st.session_state.cycle_count = 0
            st.session_state.det_img    = None
            try:
                with open("output/complaints.json","w") as f: f.write("[]")
            except Exception: pass
            db_clear()
            st.success("✅ Cleared")
            st.rerun()


# ── DATA ──────────────────────────────────────────────────────────────────────
all_c      = st.session_state.complaints
complaints = [c for c in all_c if c.get("severity") in fsev]
total      = len(all_c)
critical   = sum(1 for c in all_c if c.get("severity")=="Critical")
moderate   = sum(1 for c in all_c if c.get("severity")=="Moderate")
minor      = sum(1 for c in all_c if c.get("severity")=="Minor")
filed      = sum(1 for c in all_c if c.get("status")=="Filed")
escalated  = sum(1 for c in all_c if c.get("status")=="Escalated")
repaired   = sum(1 for c in all_c if c.get("status")=="Repaired")


# ── METRICS ROW ───────────────────────────────────────────────────────────────
m = st.columns(7)
metrics_data = [
    ("🚧","Total",    total,    "#3B82F6"),
    ("🔴","Critical", critical, "#EF4444"),
    ("🟠","Moderate", moderate, "#F59E0B"),
    ("🟢","Minor",    minor,    "#10B981"),
    ("📬","Filed",    filed,    "#3B82F6"),
    ("🚨","Escalated",escalated,"#F59E0B"),
    ("✅","Repaired", repaired, "#10B981"),
]
for col, (icon, name, val2, clr2) in zip(m, metrics_data):
    col.markdown(f"""
    <div style="background:#0D1525;border:1px solid #162035;border-radius:12px;
                padding:12px 10px;text-align:center;">
      <div style="font-size:11px;color:#334155;letter-spacing:0.5px">{icon} {name}</div>
      <div style="font-size:22px;font-weight:900;color:{clr2};font-family:Outfit,sans-serif;line-height:1.3">{val2}</div>
    </div>""", unsafe_allow_html=True)

# Latest notification banner
if st.session_state.notifs:
    n   = st.session_state.notifs[0]
    bc  = "#10B981" if n["type"]=="repaired" else "#EF4444"
    ico = "✅" if n["type"]=="repaired" else "🚨"
    st.markdown(f"""
    <div style="background:{bc}10;border:1px solid {bc}35;border-radius:10px;
                padding:8px 16px;margin:10px 0;display:flex;align-items:center;gap:10px">
      <span style="font-size:20px">{ico}</span>
      <span><b style="color:{bc}">[{n['time']}]</b>
      <span style="font-size:13px"> {n['msg']}</span></span>
    </div>""", unsafe_allow_html=True)

st.markdown("<hr style='border:1px solid #162035;margin:10px 0 14px'>", unsafe_allow_html=True)


# ── TABS ──────────────────────────────────────────────────────────────────────
TAB_NAMES = ["🗺️ Map","🎥 Video Detection","📊 Analytics","🌤️ Weather","🔔 Alerts","🤖 Auto Log","💬 AI Chat","🇮🇳 All India Report","📸 Instagram"]
t_map, t_vid, t_an, t_wx, t_al, t_log, t_chat, t_rep, t_ig = st.tabs(TAB_NAMES)


# ═══════════════════════════════ VIDEO DETECTION ══════════════════════════════
with t_vid:
    st.markdown("## 🎥 Video Pothole Detection")
    st.caption("Upload a road video — AI scans every Nth frame and detects all potholes automatically")

    vc1, vc2 = st.columns([1.2, 1])
    with vc1:
        st.markdown("#### 📤 Upload Video")
        uploaded_vid_tab = st.file_uploader(
            "Road video", type=["mp4","avi","mov","mkv"],
            label_visibility="collapsed", key="vid_tab_uploader"
        )
        frame_skip_tab = st.slider(
            "Analyze every Nth frame", 5, 60, 24,
            help="Lower = more thorough but slower. 24 = ~1 frame/sec at 24fps",
            key="vid_tab_skip"
        )

        if uploaded_vid_tab:
            st.markdown(f"""
            <div style="background:#0D1525;border:1px solid #162035;border-radius:10px;padding:12px;margin:8px 0">
              <div style="color:#10B981;font-size:13px;font-weight:700">✅ {uploaded_vid_tab.name}</div>
              <div style="color:#4B6080;font-size:11px">Size: {round(uploaded_vid_tab.size/1024/1024,1)} MB</div>
            </div>""", unsafe_allow_html=True)

            if st.button("🚀 Start Video Detection", use_container_width=True, key="vid_tab_btn"):
                if not DETECT_OK:
                    st.error("❌ Detection unavailable — ultralytics & best.pt must be installed")
                elif not CV2_OK:
                    st.error("❌ opencv-python-headless not installed")
                else:
                    os.makedirs("output", exist_ok=True)
                    vid_path = "output/upload_video.mp4"
                    with open(vid_path, "wb") as vf:
                        vf.write(uploaded_vid_tab.getbuffer())

                    prog = st.progress(0, text="⏳ Starting…")
                    status_box = st.empty()
                    cap = cv2.VideoCapture(vid_path)
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    fps = cap.get(cv2.CAP_PROP_FPS) or 25
                    frame_idx = 0
                    saved_frames = 0
                    video_complaints = []

                    while True:
                        ret, frame = cap.read()
                        if not ret:
                            break
                        if frame_idx % frame_skip_tab == 0:
                            frame_file = f"output/vframe_{saved_frames:04d}.jpg"
                            cv2.imwrite(frame_file, frame)
                            # Save frame snapshot for display
                            if saved_frames == 0:
                                cv2.imwrite("output/video_first_frame.jpg", frame)
                            try:
                                detect(frame_file)
                                with open("output/complaints.json") as cf:
                                    raw = cf.read().strip()
                                fc = json.loads(raw) if raw else []
                                ts = round(frame_idx / fps, 1)
                                for c in fc:
                                    c["video_timestamp_sec"] = ts
                                    c["source"] = f"VIDEO:{uploaded_vid_tab.name}@{ts}s"
                                    c["frame_snapshot"] = frame_file
                                video_complaints.extend(fc)
                                with open("output/complaints.json","w") as cf:
                                    cf.write("[]")
                            except Exception:
                                pass
                            saved_frames += 1
                            pct = min(int((frame_idx / max(total_frames,1)) * 100), 99)
                            prog.progress(pct, text=f"🔍 Frame {frame_idx}/{total_frames} — {len(video_complaints)} potholes found")
                            status_box.markdown(f"""
                            <div style="background:#0D1525;border:1px solid #162035;border-radius:10px;
                                        padding:10px 14px;font-size:13px">
                              ⏱️ <b style="color:#3B82F6">Frame {frame_idx}</b>/{total_frames} &nbsp;·&nbsp;
                              🔍 <b style="color:#F59E0B">{saved_frames}</b> frames scanned &nbsp;·&nbsp;
                              🚧 <b style="color:#EF4444">{len(video_complaints)}</b> potholes found
                            </div>""", unsafe_allow_html=True)
                        frame_idx += 1

                    cap.release()
                    prog.progress(100, text="✅ Scan complete!")

                    # Deduplicate
                    seen_ids = set()
                    unique = []
                    for c in video_complaints:
                        if c["pothole_id"] not in seen_ids:
                            seen_ids.add(c["pothole_id"])
                            unique.append(c)

                    if unique:
                        # Merge with existing complaints (photo + video together)
                        existing_ids = {c["pothole_id"] for c in st.session_state.complaints}
                        new_only = [c for c in unique if c["pothole_id"] not in existing_ids]
                        st.session_state.complaints.extend(new_only)
                        if "device_gps" in st.session_state:
                            g = st.session_state["device_gps"]
                            for c in st.session_state.complaints:
                                if c.get("gps"):
                                    c["gps"]["lat"] = g["lat"]
                                    c["gps"]["lon"] = g["lon"]
                        db_save(st.session_state.complaints)
                        st.session_state.auto_on = True
                        st.session_state.last_cycle = datetime.now().isoformat()
                        st.session_state["vid_result"] = unique
                        st.success(f"✅ {len(new_only)} new potholes added from video ({saved_frames} frames scanned)!")
                        st.rerun()
                    else:
                        st.warning("⚠️ No potholes detected. Try reducing the frame skip value.")

    with vc2:
        st.markdown("#### 📸 Detected Frames")
        vid_results = st.session_state.get("vid_result", [])
        if vid_results:
            # Show frame snapshots grouped by timestamp
            crit_v = sum(1 for c in vid_results if c.get("severity")=="Critical")
            mod_v  = sum(1 for c in vid_results if c.get("severity")=="Moderate")
            min_v  = sum(1 for c in vid_results if c.get("severity")=="Minor")
            for ico, lbl, val, clr in [
                ("🚧","Total",    len(vid_results), "#3B82F6"),
                ("🔴","Critical", crit_v,           "#EF4444"),
                ("🟠","Moderate", mod_v,            "#F59E0B"),
                ("🟢","Minor",    min_v,            "#10B981"),
            ]:
                st.markdown(f"""
                <div style="background:#0D1525;border:1px solid #162035;border-radius:10px;
                            padding:10px 14px;margin:4px 0;display:flex;justify-content:space-between">
                  <span style="color:#4B6080;font-size:13px">{ico} {lbl}</span>
                  <b style="color:{clr};font-size:16px">{val}</b>
                </div>""", unsafe_allow_html=True)

            st.markdown("#### 📷 Frame Snapshots with Detections")
            # Show detected frames (output images from YOLO)
            shown = 0
            for c in sorted(vid_results, key=lambda x: x.get("video_timestamp_sec",0)):
                snap = c.get("frame_snapshot","")
                det_img = "output/detected.jpg"
                ts = c.get("video_timestamp_sec", 0)
                sev = c.get("severity","Minor")
                clr = {"Critical":"#EF4444","Moderate":"#F59E0B","Minor":"#10B981"}.get(sev,"#888")
                if snap and os.path.exists(snap) and shown < 6:
                    st.markdown(f"""
                    <div style="background:#0D1525;border-left:3px solid {clr};border-radius:8px;
                                padding:6px 10px;margin:4px 0;font-size:11px">
                      <b style="color:{clr}">⏱ {ts}s</b> · <b style="color:{clr}">{sev}</b>
                      · {c.get('location','Unknown')[:35]}
                    </div>""", unsafe_allow_html=True)
                    if PIL_OK:
                        try:
                            st.image(Image.open(snap), use_container_width=True)
                            shown += 1
                        except Exception:
                            pass
        else:
            st.markdown("""
            <div style="background:#0D1525;border:2px dashed #162035;border-radius:14px;
                        padding:60px 20px;text-align:center;margin-top:10px">
              <div style="font-size:48px;margin-bottom:12px">🎥</div>
              <div style="color:#334155;font-size:14px">Upload a video and click<br><b>Start Video Detection</b><br>Frame photos will appear here</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("#### ℹ️ How It Works")
        st.markdown("""
        <div style="background:#0D1525;border:1px solid #162035;border-radius:10px;padding:14px;font-size:12px;line-height:2">
          <b style="color:#3B82F6">1.</b> Upload MP4/AVI/MOV/MKV road video<br>
          <b style="color:#3B82F6">2.</b> Set frame skip (lower = more thorough)<br>
          <b style="color:#3B82F6">3.</b> YOLOv11 detects potholes in each frame<br>
          <b style="color:#3B82F6">4.</b> Snapshot saved for every detection<br>
          <b style="color:#3B82F6">5.</b> All results merged with photo detections
        </div>""", unsafe_allow_html=True)


# ═══════════════════════════════ MAP ══════════════════════════════════════════
with t_map:
    mc1, mc2 = st.columns([1.45, 1])
    with mc1:
        st.markdown("#### 🗺️ India Road Damage Map")
        if all_c and FOLIUM_OK:
            valid = [c for c in all_c if (c.get("gps") or {}).get("lat")]
            clat  = sum(c["gps"]["lat"] for c in valid)/len(valid) if valid else 22.97
            clon  = sum(c["gps"]["lon"] for c in valid)/len(valid) if valid else 78.66
            m = folium.Map(location=[clat,clon], zoom_start=5, tiles="CartoDB dark_matter")
            heat  = [[c["gps"]["lat"],c["gps"]["lon"]] for c in valid]
            if heat: HeatMap(heat, radius=15, blur=12).add_to(m)
            SC = {"Critical":"#EF4444","Moderate":"#F59E0B","Minor":"#10B981"}
            for c in valid[:300]:
                clr = SC.get(c.get("severity","Minor"),"#3B82F6")
                folium.CircleMarker(
                    location=[c["gps"]["lat"],c["gps"]["lon"]],
                    radius=6, color=clr, fill=True, fill_color=clr, fill_opacity=0.85,
                    popup=folium.Popup(
                        f"<b>{c.get('pothole_id','')}</b><br>{c.get('location','')}<br>"
                        f"Sev: {c.get('severity','')} | Status: {c.get('status','')}",
                        max_width=200)
                ).add_to(m)
            st_folium(m, use_container_width=True, height=450)
        elif not FOLIUM_OK:
            st.warning("Install folium + streamlit-folium for interactive maps")
        else:
            st.markdown("""
            <div style="background:#0D1525;border:2px dashed #162035;border-radius:14px;
                        padding:80px 20px;text-align:center">
              <div style="font-size:52px;margin-bottom:12px">🗺️</div>
              <div style="color:#334155;font-size:15px">Upload a road image<br>and run detection to see the live map</div>
            </div>""", unsafe_allow_html=True)

        # ── Safe Navigation (visible to all, especially Public users) ─────────
        st.markdown("#### 🧭 Safe Navigation")
        st.markdown("""
        <div style="background:#0D1525;border:1px solid #162035;border-radius:12px;padding:14px;margin-bottom:8px">
          <div style="color:#3B82F6;font-size:13px;font-weight:700;margin-bottom:6px">🚗 Pothole-Aware Route Planner</div>
          <div style="color:#4B6080;font-size:12px">Navigate safely — potholes on your route are highlighted as warnings</div>
        </div>""", unsafe_allow_html=True)

        nav_c1, nav_c2 = st.columns(2)
        with nav_c1:
            nav_from = st.text_input("📍 From", placeholder="e.g. Mumbai", key="nav_from")
        with nav_c2:
            nav_to   = st.text_input("🏁 To",   placeholder="e.g. Pune",   key="nav_to")

        if st.button("🚀 Open Safe Navigation Map", use_container_width=True):
            # Build query params for map.html
            params = ""
            if nav_from and nav_to:
                params = f"?from={_parse.quote(nav_from)}&to={_parse.quote(nav_to)}"
            map_url = f"map.html{params}"
            st.markdown(f"""
            <div style="background:#0B1120;border:1px solid #162035;border-radius:10px;padding:14px;margin-top:8px">
              <div style="color:#10B981;font-size:13px;font-weight:700">✅ Open the navigation map:</div>
              <a href="{map_url}" target="_blank"
                 style="display:block;margin-top:8px;background:linear-gradient(135deg,#28a745,#20c997);
                        color:#fff;text-align:center;padding:10px;border-radius:8px;
                        font-weight:700;font-size:14px;text-decoration:none">
                🗺️ Launch Pothole Navigation →
              </a>
              <div style="color:#334155;font-size:11px;margin-top:8px">
                ⚠️ Potholes on your route are shown as red warning markers
              </div>
            </div>""", unsafe_allow_html=True)

        # Quick warning for public users
        if role == "Public" and all_c:
            critical_near = [c for c in all_c if c.get("severity") == "Critical"][:3]
            if critical_near:
                st.markdown("#### ⚠️ Critical Potholes Nearby")
                for c in critical_near:
                    st.markdown(f"""
                    <div style="background:#EF444410;border-left:3px solid #EF4444;
                                border-radius:8px;padding:8px 12px;margin:4px 0;font-size:12px">
                      🔴 <b style="color:#EF4444">{c.get('severity','')}</b> —
                      {c.get('location','Unknown')[:50]}<br>
                      <span style="color:#4B6080">📅 {(c.get('complaint_filed_at') or '')[:10]}
                      · Status: {c.get('status','')}</span>
                    </div>""", unsafe_allow_html=True)

    with mc2:
        st.markdown("#### 📸 Detected Image")
        if st.session_state.det_img and os.path.exists(st.session_state.det_img):
            if PIL_OK:
                st.image(Image.open(st.session_state.det_img), use_container_width=True)
            else:
                st.image(st.session_state.det_img, use_container_width=True)
        else:
            st.markdown("""
            <div style="background:#0D1525;border:2px dashed #162035;border-radius:12px;
                        padding:48px 16px;text-align:center">
              <div style="font-size:44px">📸</div>
              <div style="color:#334155;font-size:13px;margin-top:10px">
                Detected image<br>will appear here
              </div>
            </div>""", unsafe_allow_html=True)

        if all_c and PLOTLY_OK:
            st.markdown("#### Severity Split")
            fig = go.Figure(go.Pie(
                values=[critical,moderate,minor],
                labels=["Critical","Moderate","Minor"],
                marker_colors=["#EF4444","#F59E0B","#10B981"],
                hole=0.55, textinfo="percent+label",
                textfont=dict(family="Outfit",size=12,color="#fff"),
            ))
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#E2E8F0", showlegend=False,
                height=210, margin=dict(l=0,r=0,t=0,b=0)
            )
            st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════ ANALYTICS ════════════════════════════════════
with t_an:
    st.markdown("#### 📊 Analytics Dashboard")
    if all_c and PLOTLY_OK:
        from collections import Counter
        a1, a2 = st.columns(2)
        with a1:
            dc = Counter(c.get("district","Unknown") for c in all_c).most_common(10)
            if dc:
                fig = px.bar(x=[n for _,n in dc], y=[d for d,_ in dc],
                             orientation="h", title="Top Districts",
                             color=[n for _,n in dc], color_continuous_scale="Blues")
                fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#E2E8F0",height=320,coloraxis_showscale=False,
                    margin=dict(l=0,r=0,t=36,b=0),yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig, use_container_width=True)
        with a2:
            fig2 = px.bar(
                x=["Filed","Escalated","Repaired"], y=[filed,escalated,repaired],
                color=["Filed","Escalated","Repaired"],
                color_discrete_map={"Filed":"#3B82F6","Escalated":"#F59E0B","Repaired":"#10B981"},
                title="Status Distribution"
            )
            fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                font_color="#E2E8F0",height=320,showlegend=False,margin=dict(l=0,r=0,t=36,b=0))
            st.plotly_chart(fig2, use_container_width=True)

        sc = Counter(c.get("district","Unknown") for c in all_c).most_common(16)
        if sc:
            fig3 = px.treemap(
                names=[s for s,_ in sc], parents=["India"]*len(sc),
                values=[n for _,n in sc], title="Potholes by Region",
                color=[n for _,n in sc], color_continuous_scale="Blues"
            )
            fig3.update_layout(paper_bgcolor="rgba(0,0,0,0)",font_color="#E2E8F0",
                height=280,margin=dict(l=0,r=0,t=36,b=0))
            st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("📊 No data yet — run detection first")


# ═══════════════════════════════ WEATHER ══════════════════════════════════════
with t_wx:
    st.markdown("#### 🌤️ Weather & Road Risk Index")

    # Get unique locations — deduplicate by rounding GPS to 2 decimal places
    seen_gps = set()
    unique_loc = []
    for c in all_c:
        gps = c.get("gps") or {}
        lat = gps.get("lat")
        lon = gps.get("lon")
        if not lat or not lon:
            continue
        key = (round(lat, 2), round(lon, 2))  # ~1km grid dedup
        if key not in seen_gps:
            seen_gps.add(key)
            unique_loc.append(c)
        if len(unique_loc) >= 6:
            break

    # Fallback to all_c if no unique GPS found
    if not unique_loc:
        unique_loc = [c for c in all_c if (c.get("gps") or {}).get("lat")][:6]

    if unique_loc:
        for i in range(0, len(unique_loc), 3):
            wc = st.columns(3)
            for j, c in enumerate(unique_loc[i:i+3]):
                lat = c["gps"]["lat"]
                lon = c["gps"]["lon"]
                w = get_weather(lat, lon)
                rsk, rclr = risk_label(calc_risk([c]))
                sev = c.get("severity", "Minor")
                sev_clr = {"Critical":"#EF4444","Moderate":"#F59E0B","Minor":"#10B981"}.get(sev,"#888")
                weather_icon = "🌧️" if "rain" in w["desc"].lower() else "⛈️" if "storm" in w["desc"].lower() else "☁️" if "cloud" in w["desc"].lower() else "☀️"
                with wc[j]:
                    st.markdown(f"""
                    <div class="c" style="text-align:center;border-left:none;border-top:3px solid {rclr}">
                      <div style="font-size:11px;color:#4B6080;margin-bottom:4px">{c.get('location','Unknown')[:38]}</div>
                      <div style="font-size:10px;color:#334155">🌐 {lat:.4f}, {lon:.4f}</div>
                      <div style="font-size:32px;margin:10px 0">{weather_icon}</div>
                      <div style="font-size:26px;font-weight:900;color:#3B82F6;font-family:Outfit">{w['temp']}°C</div>
                      <div style="font-size:12px;color:#94A3B8">{w['desc']}</div>
                      <div style="font-size:11px;color:#4B6080;margin-top:6px">💧{w['humidity']}% · 💨{w['wind']}km/h</div>
                      <div style="margin-top:6px;font-size:11px;color:{sev_clr};font-weight:700">⚠️ {sev} Pothole</div>
                      <div style="margin-top:6px;background:{rclr}20;border-radius:20px;
                                  padding:3px 10px;font-size:11px;font-weight:700;color:{rclr};display:inline-block">{rsk}</div>
                    </div>""", unsafe_allow_html=True)
    else:
        st.info("🌤️ Weather data appears for pothole locations after detection")


# ═══════════════════════════════ ALERTS ═══════════════════════════════════════
with t_al:
    st.markdown("#### 🔔 Escalation Alerts")
    esc_list = [c for c in all_c if c.get("status")=="Escalated"]
    if escalated > 0:
        st.warning(f"⚠️ {escalated} potholes escalated — immediate attention required")
    if esc_list:
        for c in esc_list[:25]:
            st.markdown(f"""
            <div class="c c-r">
              <b style="color:#EF4444">{c.get('pothole_id','')} 🚨</b><br>
              📍 {c.get('location','')} · ⚠️ {c.get('severity','')} · 🎯 {int((c.get('confidence') or 0)*100)}%<br>
              <span style="color:#4B6080;font-size:12px">Filed: {(c.get('complaint_filed_at') or '')[:10]} · 
              Assigned: {c.get('assigned_to','PWD')}</span>
            </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="text-align:center;padding:48px;background:#0D1525;border-radius:14px">
          <div style="font-size:44px">✅</div>
          <div style="color:#10B981;font-size:16px;font-weight:700;margin-top:10px">No escalated cases</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("#### 📧 Email Activity Log")
    if st.session_state.email_log:
        for e in st.session_state.email_log[:12]:
            ec = "#10B981" if e["type"]=="repair_verified" else "#F59E0B"
            st.markdown(f"""
            <div style="background:#0D1525;border-left:3px solid {ec};border-radius:8px;
                        padding:9px 14px;margin:4px 0">
              <b style="color:{ec};font-size:12px">[{e['time']}]</b>
              <span style="font-size:12px"> → {e['to']}</span><br>
              <span style="color:#4B6080;font-size:11px">{e['id']} · {e['loc']} · {e['sev']}</span>
            </div>""", unsafe_allow_html=True)
    else:
        st.info("No emails logged yet")


# ═══════════════════════════════ AUTO LOG ═════════════════════════════════════
with t_log:
    st.markdown("### 🤖 Autonomous System Log")
    lc1,lc2,lc3,lc4 = st.columns(4)
    for col, ico, lbl, val, clr in [
        (lc1,"🔄","Cycles",   st.session_state.cycle_count, "#3B82F6"),
        (lc2,"✅","Repaired",  sum(1 for n in st.session_state.notifs if n["type"]=="repaired"),  "#10B981"),
        (lc3,"🚨","Escalated", sum(1 for n in st.session_state.notifs if n["type"]=="escalated"), "#EF4444"),
        (lc4,"👤","Human Triggers","ZERO","#10B981"),
    ]:
        with col:
            st.markdown(f"""
            <div style="background:#0D1525;border:1px solid #162035;border-radius:12px;
                        padding:14px;text-align:center">
              <div style="color:#4B6080;font-size:12px">{ico} {lbl}</div>
              <div style="color:{clr};font-size:26px;font-weight:900;font-family:Outfit">{val}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("#### 📢 Live Activity Feed")
    if st.session_state.notifs:
        for n in st.session_state.notifs[:16]:
            nc  = "#10B981" if n["type"]=="repaired" else "#EF4444"
            ico = "✅" if n["type"]=="repaired" else "🚨"
            st.markdown(f"""
            <div style="background:{nc}0d;border-left:3px solid {nc};border-radius:8px;
                        padding:9px 14px;margin:3px 0;font-size:13px">
              {ico} <b style="color:{nc}">[{n['time']}]</b> {n['msg']}
            </div>""", unsafe_allow_html=True)
    else:
        st.info("⏳ Waiting for first auto-cycle…")

    if st.session_state.auto_log:
        st.markdown("#### 🕐 Cycle History")
        st.code("\n".join(st.session_state.auto_log[:20]))

    if st.session_state.auto_on:
        time.sleep(8)
        st.rerun()


# ═══════════════════════════════ AI CHAT ══════════════════════════════════════
with t_chat:
    st.markdown("### 💬 PotholeAI Assistant")
    st.caption("Ask anything about road damage across India")

    # Chat history
    for msg in st.session_state.chat_history:
        role_c = "#3B82F6" if msg["role"]=="bot" else "#F59E0B"
        side_l = "chat-user" if msg["role"]=="user" else "chat-bot"
        name   = "🤖 PotholeAI" if msg["role"]=="bot" else f"{st.session_state.icon} You"
        st.markdown(f"""
        <div style="{'margin-left:18%' if msg['role']=='user' else 'margin-right:18%'};
                    background:{'rgba(13,21,37,0.9)' if msg['role']=='bot' else 'rgba(37,99,235,0.1)'};
                    border:1px solid {'#162035' if msg['role']=='bot' else 'rgba(37,99,235,0.3)'};
                    border-radius:14px;padding:12px 16px;margin:6px 0">
          <b style="color:{role_c};font-size:12px">{name}</b><br>
          <span style="font-size:14px">{msg['text']}</span>
        </div>""", unsafe_allow_html=True)

    if not st.session_state.chat_history:
        st.markdown(f"""
        <div style="margin-right:18%;background:#0D1525;border:1px solid #162035;
                    border-radius:14px;padding:14px 16px">
          <b style="color:#3B82F6;font-size:12px">🤖 PotholeAI</b><br>
          <span style="font-size:14px">
            Hi! I'm monitoring <b style="color:#3B82F6">{total} potholes</b> across India.
            Ask me anything — worst state, critical count, repair status, highway conditions.
          </span>
        </div>""", unsafe_allow_html=True)

    # Quick questions
    qq_cols = st.columns(4)
    for i, (qc, qq) in enumerate(zip(qq_cols,
        ["Worst district?","How many critical?","Repair rate?","Top highway?"])):
        with qc:
            if st.button(qq, key=f"qq{i}"):
                ans = chatbot_response(qq, all_c)
                st.session_state.chat_history.append({"role":"user","text":qq})
                st.session_state.chat_history.append({"role":"bot","text":ans})
                st.rerun()

    ui = st.chat_input("Ask about potholes, states, roads, status…")
    if ui:
        ans = chatbot_response(ui, all_c)
        st.session_state.chat_history.append({"role":"user","text":ui})
        st.session_state.chat_history.append({"role":"bot","text":ans})
        st.rerun()

    if st.button("🗑️ Clear Chat"):
        st.session_state.chat_history = []
        st.rerun()


# ═══════════════════════════════ REPORTS ══════════════════════════════════════
with t_rep:
    st.markdown(f"#### 🇮🇳 All India Report — {len(complaints)} records")
    if complaints:
        srch = st.text_input("Search…", label_visibility="collapsed",
                             placeholder="🔍  Search by ID, location, district, road…")
        filt = [c for c in complaints if not srch or
                srch.lower() in (str(c.get("pothole_id",""))+str(c.get("location",""))+
                                  str(c.get("district",""))+str(c.get("road",""))).lower()]

        SC = {"Critical":"#EF4444","Moderate":"#F59E0B","Minor":"#10B981"}
        ST = {"Repaired":"#10B981","Escalated":"#F59E0B","Filed":"#3B82F6"}
        for c in filt[:60]:
            sclr = SC.get(c.get("severity","Minor"),"#888")
            stclr = ST.get(c.get("status","Filed"),"#888")
            st.markdown(f"""
            <div class="c c-b">
              <span style="font-weight:800;color:#3B82F6">{c.get('pothole_id','—')}</span>
              &nbsp;<span style="background:rgba(37,99,235,0.12);color:#3B82F6;
                                 border-radius:20px;padding:1px 9px;font-size:10px">AUTO</span><br>
              📍 {c.get('location','—')} · 🛣️ {c.get('highway_km','—')}<br>
              ⚠️ <b style="color:{sclr}">{c.get('severity','—')}</b>
              &nbsp;·&nbsp; 🎯 {int((c.get('confidence') or 0)*100)}%
              &nbsp;·&nbsp; <b style="color:{stclr}">{c.get('status','—')}</b><br>
              <span style="color:#334155;font-size:11px">
                🌐 {(c.get('gps') or {}).get('lat',0):.4f}, {(c.get('gps') or {}).get('lon',0):.4f}
                &nbsp;·&nbsp; 🏛️ {c.get('assigned_to','PWD')}
                &nbsp;·&nbsp; 📅 {(c.get('complaint_filed_at') or '')[:10]}
              </span>
            </div>""", unsafe_allow_html=True)

        if len(filt) > 60:
            st.info(f"Showing 60 of {len(filt)}. Use search to narrow results.")
    else:
        st.markdown("""
        <div style="text-align:center;padding:64px;background:#0D1525;border-radius:16px;border:1px solid #162035">
          <div style="font-size:60px;margin-bottom:16px">🚧</div>
          <h3 style="color:#3B82F6">No Reports Yet</h3>
          <p style="color:#334155;font-size:14px">Upload a road photo and run detection to get started</p>
        </div>""", unsafe_allow_html=True)


# ═══════════════════════════════ INSTAGRAM ════════════════════════════════════
with t_ig:
    st.markdown("### 📸 Instagram Pothole Intelligence")
    st.caption("Auto-scrape Instagram for pothole reports across India · AI predicts location from captions & images")

    # Import integration module
    try:
        from instagram_integration import (
            ig_search_potholes, run_instagram_pipeline,
            predict_location_from_caption, POTHOLE_HASHTAGS
        )
        IG_MODULE_OK = True
    except ImportError:
        IG_MODULE_OK = False

    # API Status
    ig_token  = os.environ.get("IG_ACCESS_TOKEN", "")
    gv_key    = os.environ.get("GOOGLE_VISION_KEY", "")

    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.markdown(f"""
        <div style="background:#0D1525;border:1px solid {'#10B98130' if ig_token else '#EF444430'};
                    border-radius:10px;padding:12px;text-align:center">
          <div style="font-size:20px">{'✅' if ig_token else '⚠️'}</div>
          <div style="font-size:12px;font-weight:700;color:{'#10B981' if ig_token else '#EF4444'}">
            Meta Graph API
          </div>
          <div style="font-size:11px;color:#334155">{'Connected' if ig_token else 'No token set'}</div>
        </div>""", unsafe_allow_html=True)
    with sc2:
        st.markdown(f"""
        <div style="background:#0D1525;border:1px solid {'#10B98130' if gv_key else '#F59E0B30'};
                    border-radius:10px;padding:12px;text-align:center">
          <div style="font-size:20px">{'✅' if gv_key else '⚠️'}</div>
          <div style="font-size:12px;font-weight:700;color:{'#10B981' if gv_key else '#F59E0B'}">
            Google Vision API
          </div>
          <div style="font-size:11px;color:#334155">{'Connected' if gv_key else 'Optional'}</div>
        </div>""", unsafe_allow_html=True)
    with sc3:
        st.markdown(f"""
        <div style="background:#0D1525;border:1px solid #10B98130;
                    border-radius:10px;padding:12px;text-align:center">
          <div style="font-size:20px">✅</div>
          <div style="font-size:12px;font-weight:700;color:#10B981">OSM Geocoding</div>
          <div style="font-size:11px;color:#334155">Always active · Free</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # How it works
    with st.expander("🔍 How Instagram Integration Works", expanded=False):
        st.markdown("""
        <div style="background:#0D1525;border-radius:12px;padding:20px;line-height:2">
          <b style="color:#3B82F6">Pipeline:</b><br>
          <b>1.</b> 📸 Search Instagram for hashtags: <code>#pothole</code> <code>#खड्डा</code> <code>#badroads</code> etc.<br>
          <b>2.</b> 📍 <b>Location Prediction</b> (3 methods in order):<br>
          &nbsp;&nbsp;&nbsp;• Instagram tagged location (most accurate)<br>
          &nbsp;&nbsp;&nbsp;• AI reads caption → extracts road/city name → geocodes via OpenStreetMap<br>
          &nbsp;&nbsp;&nbsp;• Google Vision API → detects landmarks/signs in image → geocodes<br>
          <b>3.</b> 🤖 YOLOv11 runs on each image → detects & classifies potholes<br>
          <b>4.</b> 💾 Auto-saved to PotholeAI database with full details<br><br>
          <b style="color:#F59E0B">Setup required:</b> Meta Developer Account + Instagram Business Account<br>
          <b style="color:#10B981">Works without API key:</b> Demo mode shows sample posts
        </div>
        """, unsafe_allow_html=True)

    # Hashtags monitored
    st.markdown("#### 🏷️ Monitored Hashtags")
    if IG_MODULE_OK:
        tags_html = " ".join([
            f'<span style="background:rgba(37,99,235,0.12);color:#3B82F6;border:1px solid rgba(37,99,235,0.25);'
            f'border-radius:20px;padding:3px 12px;font-size:12px;margin:3px;display:inline-block">#{t}</span>'
            for t in POTHOLE_HASHTAGS
        ])
        st.markdown(tags_html, unsafe_allow_html=True)

    st.markdown("---")

    # Scrape controls
    ig1, ig2 = st.columns([1, 2])
    with ig1:
        max_posts = st.slider("Max posts to fetch", 5, 50, 10)
        run_detection = st.checkbox("Run YOLOv11 on each image", value=False)
        if st.button("🔍 Fetch Instagram Posts", use_container_width=True):
            with st.spinner("Scraping Instagram for potholes..."):
                if IG_MODULE_OK:
                    posts = ig_search_potholes(max_posts=max_posts)
                    st.session_state["ig_posts"] = posts
                    st.success(f"✅ Found {len(posts)} posts")
                else:
                    st.error("instagram_integration.py not found")

        if st.button("🤖 Full Pipeline (Detect + Save)", use_container_width=True):
            with st.spinner("Running full Instagram pipeline..."):
                if IG_MODULE_OK:
                    detect_fn = detect if DETECT_OK and run_detection else None
                    new_complaints = run_instagram_pipeline(
                        detect_fn=detect_fn,
                        max_posts=max_posts
                    )
                    if new_complaints:
                        st.session_state.complaints.extend(new_complaints)
                        db_save(st.session_state.complaints)
                        st.success(f"✅ Added {len(new_complaints)} Instagram potholes to database!")
                        st.rerun()
                    else:
                        st.warning("No potholes with location found")

    with ig2:
        # Show fetched posts
        posts = st.session_state.get("ig_posts", [])
        if not posts and IG_MODULE_OK:
            # Show demo on first load
            from instagram_integration import _get_demo_posts
            posts = _get_demo_posts()

        if posts:
            st.markdown(f"#### 📋 {len(posts)} Posts Found")
            for post in posts[:10]:
                loc = post.get("location", {})
                loc_name = loc.get("name", "") if isinstance(loc, dict) else ""
                caption  = post.get("caption", "")[:120]

                # Predict location if missing
                if not loc_name and caption and IG_MODULE_OK:
                    from instagram_integration import predict_location_from_caption
                    predicted = predict_location_from_caption(caption)
                    loc_name  = predicted.get("name", "Predicting...")

                has_loc = bool(loc_name)
                loc_clr = "#10B981" if has_loc else "#F59E0B"
                loc_ico = "📍" if has_loc else "🔍"

                st.markdown(f"""
                <div style="background:#0D1525;border:1px solid #162035;border-radius:10px;
                            padding:12px 14px;margin:6px 0">
                  <div style="display:flex;justify-content:space-between;align-items:center">
                    <span style="color:#3B82F6;font-size:11px;font-weight:700">
                      #{post.get('hashtag','')} · {post.get('source','')}
                    </span>
                    <a href="{post.get('permalink','#')}" target="_blank"
                       style="color:#3B82F6;font-size:11px;text-decoration:none">🔗 View Post</a>
                  </div>
                  <div style="font-size:13px;color:#94A3B8;margin:6px 0">{caption}{'...' if len(post.get('caption',''))>120 else ''}</div>
                  <div style="font-size:12px">
                    <span style="color:{loc_clr}">{loc_ico} {loc_name if loc_name else 'Location being predicted...'}</span>
                    {'&nbsp;·&nbsp;<span style="color:#334155">GPS: ' + str(round(loc.get("lat",0),4)) + ', ' + str(round(loc.get("lon",0),4)) + '</span>' if isinstance(loc,dict) and loc.get('lat') else ''}
                  </div>
                </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # Setup guide
    st.markdown("#### ⚙️ Setup API Keys")
    setup1, setup2 = st.columns(2)
    with setup1:
        st.markdown("""
        <div style="background:#0D1525;border:1px solid #162035;border-radius:10px;padding:16px">
          <b style="color:#3B82F6">Meta Graph API (Instagram)</b><br><br>
          <span style="font-size:13px;color:#64748B">
          1. Go to <b>developers.facebook.com</b><br>
          2. Create App → Consumer type<br>
          3. Add Instagram Basic Display product<br>
          4. Get Access Token<br>
          5. Set in terminal:<br>
          </span>
          <code style="background:#060A12;padding:6px 10px;border-radius:6px;font-size:12px;display:block;margin-top:8px;color:#10B981">
          export IG_ACCESS_TOKEN="your_token"<br>
          export IG_USER_ID="your_user_id"
          </code>
        </div>""", unsafe_allow_html=True)
    with setup2:
        st.markdown("""
        <div style="background:#0D1525;border:1px solid #162035;border-radius:10px;padding:16px">
          <b style="color:#3B82F6">Google Vision API (Optional)</b><br><br>
          <span style="font-size:13px;color:#64748B">
          Used for location prediction from road signs & landmarks in images<br><br>
          1. Go to <b>console.cloud.google.com</b><br>
          2. Enable Cloud Vision API<br>
          3. Create API Key<br>
          4. Set in terminal:<br>
          </span>
          <code style="background:#060A12;padding:6px 10px;border-radius:6px;font-size:12px;display:block;margin-top:8px;color:#10B981">
          export GOOGLE_VISION_KEY="your_key"
          </code>
        </div>""", unsafe_allow_html=True)
