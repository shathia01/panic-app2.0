import streamlit as st
import requests
import math
import smtplib
import json
import time
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from streamlit_js_eval import streamlit_js_eval

st.title("🚨 One-Click Emergency Panic Button")

# ---------- GMAIL CONFIG ----------
SENDER_EMAIL = "shathia190304@gmail.com"
SENDER_APP_PASSWORD = "kvskirvfdhsscege"
SENDER_NAME = "Emergency Alert"

# ---------- DEFAULT HARDCODED CONTACTS ----------
DEFAULT_CONTACTS = [
    {"name": "Admin", "email": "shathia190304@gmail.com"},
]

# ---------- SESSION STATE INIT ----------
for key, default in [
    ("extreme_active", False),
    ("update_count", 0),
    ("last_sent", None),
    ("tracking_locations", []),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ---------- READ SAVED CONTACT FROM localStorage ----------
raw = streamlit_js_eval(js_expressions="localStorage.getItem('emergency_my_contacts')", key="read_my_contacts")
my_contacts = []
if raw and raw != "null":
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):   # backwards-compat with old single-contact format
            my_contacts = [parsed]
        elif isinstance(parsed, list):
            my_contacts = parsed
    except Exception:
        my_contacts = []

# ---------- HAVERSINE ----------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# ---------- FIND NEAREST POLICE ----------
def find_police(lat, lon, radius=5000):
    query = f"""
    [out:json][timeout:10];
    (
      node["amenity"="police"](around:{radius},{lat},{lon});
      way["amenity"="police"](around:{radius},{lat},{lon});
    );
    out center;
    """
    try:
        res = requests.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query}, timeout=25
        ).json()
        elements = res.get("elements", [])
        if not elements:
            return None
        best, best_dist = None, float("inf")
        for el in elements:
            plat = el.get("lat") or el.get("center", {}).get("lat")
            plon = el.get("lon") or el.get("center", {}).get("lon")
            if plat is None or plon is None:
                continue
            dist = haversine(lat, lon, plat, plon)
            if dist < best_dist:
                best_dist = dist
                name = el.get("tags", {}).get("name", "Police Station")
                best = (plat, plon, name, best_dist)
        return best
    except Exception:
        return None

# ---------- SEND EMAIL ----------
def send_email(recipient_name, recipient_email, lat, lon, update_num=None, accuracy=None):
    maps_link = f"https://maps.google.com/?q={lat},{lon}"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    is_update = update_num is not None
    subject = (
        f"LIVE UPDATE #{update_num} - Emergency Alert - Urgent"
        if is_update else
        "Emergency Alert - Urgent Assistance Required"
    )
    acc_text = f"+-{accuracy:.0f}m" if accuracy else "N/A"

    plain = f"""{'LIVE TRACKING UPDATE #' + str(update_num) if is_update else 'EMERGENCY ALERT'}

Dear {recipient_name},

{'This is a LIVE LOCATION UPDATE. The person is moving.' if is_update else 'Someone triggered the Emergency Panic Button.'}

Call emergency services (999) immediately.

Location: {lat:.6f}, {lon:.6f}
Accuracy: {acc_text}
Google Maps: {maps_link}
Time: {timestamp}
"""

    html = f"""
    <html><body style="font-family:Arial,sans-serif;background:#f8f8f8;padding:20px;">
    <div style="max-width:500px;margin:auto;background:white;border-radius:10px;
                border-top:6px solid {'#8B0000' if is_update else 'red'};padding:30px;
                box-shadow:0 2px 8px rgba(0,0,0,0.1);">
        <h1 style="color:{'#8B0000' if is_update else 'red'};text-align:center;">
            {'LIVE UPDATE #' + str(update_num) if is_update else 'Emergency Alert'}
        </h1>
        <p>Dear <b>{recipient_name}</b>,</p>
        <p>
            {'<b>LIVE TRACKING ACTIVE</b> - Person is moving. Latest position below.' if is_update else 'Emergency Panic Button was activated.'}
            <br><br>Call emergency services (<b>999</b>) immediately.
        </p>
        <div style="background:#fff0f0;border-left:4px solid {'#8B0000' if is_update else 'red'};
                    padding:15px;border-radius:5px;margin:20px 0;">
            <p style="margin:0;font-size:15px;">
                Location:<br>
                Lat: <code>{lat:.6f}</code><br>
                Lon: <code>{lon:.6f}</code><br>
                <small>GPS Accuracy: {acc_text}</small><br>
                <small>Sent: {timestamp}</small>
                {f'<br><small style="color:#8B0000;font-weight:bold;">Update #{update_num} of ongoing tracking</small>' if is_update else ''}
            </p>
        </div>
        <a href="{maps_link}" style="display:block;text-align:center;
           background:{'#8B0000' if is_update else '#c0392b'};color:white;padding:14px 20px;
           border-radius:8px;text-decoration:none;font-size:16px;font-weight:bold;margin-top:10px;">
           Open Location on Google Maps
        </a>
    </div></body></html>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
        msg["To"] = recipient_email
        msg["Reply-To"] = SENDER_EMAIL
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="gmail.com")
        msg.attach(MIMEText(plain, "plain"))
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, recipient_email, msg.as_string())
        return True, ""
    except Exception as e:
        return False, str(e)

def send_to_all(lat, lon, contacts, update_num=None, accuracy=None):
    results = []
    for c in contacts:
        success, error = send_email(c["name"], c["email"], lat, lon, update_num, accuracy)
        results.append({"name": c["name"], "email": c["email"], "success": success, "error": error})
    return results

# ---------- BUILD CONTACT LIST ----------
all_contacts = list(DEFAULT_CONTACTS)
for c in my_contacts:
    if not any(x["email"].lower() == c["email"].lower() for x in all_contacts):
        all_contacts.append(c)

# ---------- MY CONTACT SECTION ----------
st.divider()
st.subheader("📋 My Emergency Contacts")

if my_contacts:
    st.success(f"{len(my_contacts)} personal contact(s) saved on this device.")
    for i, c in enumerate(my_contacts):
        col_name, col_email, col_del = st.columns([2, 3, 1])
        with col_name:
            st.write(f"**{c['name']}**")
        with col_email:
            st.write(c["email"])
        with col_del:
            if st.button("🗑️ Remove", key=f"remove_{i}"):
                updated = [x for j, x in enumerate(my_contacts) if j != i]
                escaped = json.dumps(updated).replace("'", "\\'")
                streamlit_js_eval(js_expressions=f"localStorage.setItem('emergency_my_contacts','{escaped}');true", key=f"del_contact_{i}")
                st.info("Removed. Refresh to confirm.")
else:
    st.info("No personal contacts saved yet. Add contacts below.")

st.markdown("##### ➕ Add a Contact")
with st.form("add_contact_form", clear_on_submit=True):
    col_n, col_e = st.columns(2)
    with col_n:
        reg_name = st.text_input("Name", placeholder="e.g. Sarah")
    with col_e:
        reg_email = st.text_input("Email", placeholder="e.g. sarah@gmail.com")
    if st.form_submit_button("Save Contact to This Device"):
        if reg_name and reg_email:
            if any(c["email"].lower() == reg_email.lower() for c in my_contacts):
                st.warning("A contact with that email already exists.")
            else:
                updated = my_contacts + [{"name": reg_name, "email": reg_email}]
                escaped = json.dumps(updated).replace("'", "\\'")
                streamlit_js_eval(js_expressions=f"localStorage.setItem('emergency_my_contacts','{escaped}');true", key="save_new_contact")
                st.success(f"Saved {reg_name}! Refresh to confirm.")
        else:
            st.warning("Please fill in both fields.")

# ===================================================================
# ---------- PANIC BUTTONS ----------
# ===================================================================
st.divider()
st.caption(f"Alert will be sent to {len(all_contacts)} contact(s).")

col1, col2 = st.columns(2)

# ---- STANDARD PANIC ----
with col1:
    if st.button("PANIC", use_container_width=True, type="primary",
                 disabled=st.session_state.extreme_active):
        loc = streamlit_js_eval(
            js_expressions="""
            new Promise(resolve => {
                navigator.geolocation.getCurrentPosition(
                    p => resolve([p.coords.latitude, p.coords.longitude]),
                    () => resolve(null)
                );
            })""",
            key="panic_location"
        )
        if loc:
            lat, lon = loc
            st.success(f"Location: {lat:.5f}, {lon:.5f}")
            results = send_to_all(lat, lon, all_contacts)
            for r in results:
                if r["success"]:
                    st.success(f"Sent to {r['name']}")
                else:
                    st.error(f"Failed - {r['name']}: {r['error']}")
            with st.spinner("Finding nearest police..."):
                police = find_police(lat, lon) or find_police(lat, lon, 15000)
            if police:
                plat, plon, name, dist = police
                st.success(f"{name} - {dist:.0f}m away")
                st.link_button("GO TO POLICE NOW", f"https://www.google.com/maps/dir/?api=1&destination={plat},{plon}")
            else:
                st.error("No police station found nearby.")
        else:
            st.error("Location unavailable - allow location access and refresh.")

# ---- EXTREME PANIC TOGGLE ----
with col2:
    if not st.session_state.extreme_active:
        if st.button("EXTREME PANIC - Live Tracking", use_container_width=True):
            st.session_state.extreme_active = True
            st.session_state.update_count = 0
            st.session_state.tracking_locations = []
            st.rerun()
    else:
        if st.button("STOP TRACKING", use_container_width=True, type="primary"):
            st.session_state.extreme_active = False
            st.success(f"Tracking stopped after {st.session_state.update_count} update(s).")
            st.rerun()

# ===================================================================
# ---------- EXTREME PANIC LIVE TRACKING ----------
# Safe pattern: JS fetches location once, Python does the 30s countdown
# with time.sleep(1) ticks - no JS setTimeout, no recursive JS promises
# ===================================================================
if st.session_state.extreme_active:
    st.divider()
    st.error("EXTREME PANIC ACTIVE - LIVE TRACKING ON")
    st.warning("Location sent every 30 seconds. Press STOP TRACKING above to end.")

    location_box = st.empty()
    result_box   = st.empty()
    trail_box    = st.empty()

    # Fetch fresh GPS fix - unique key per update prevents stale cached result
    fresh_loc = streamlit_js_eval(
        js_expressions="""
        new Promise(resolve => {
            navigator.geolocation.getCurrentPosition(
                p => resolve([p.coords.latitude, p.coords.longitude, p.coords.accuracy]),
                () => resolve(null),
                { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
            );
        })""",
        key=f"xloc_{st.session_state.update_count}"
    )

    if fresh_loc:
        lat      = fresh_loc[0]
        lon      = fresh_loc[1]
        accuracy = fresh_loc[2] if len(fresh_loc) > 2 else None
        acc_str  = f"+-{accuracy:.0f}m" if accuracy else "unknown"
        count    = st.session_state.update_count + 1
        ts       = datetime.now().strftime("%H:%M:%S")

        location_box.info(
            f"Update #{count} at {ts} | "
            f"{lat:.6f}, {lon:.6f} | accuracy {acc_str}"
        )

        with result_box.container():
            with st.spinner(f"Sending update #{count}..."):
                results = send_to_all(lat, lon, all_contacts, update_num=count, accuracy=accuracy)
            for r in results:
                if r["success"]:
                    st.success(f"Update #{count} sent to {r['name']}")
                else:
                    st.error(f"Failed - {r['name']}: {r['error']}")

        # Store in trail
        st.session_state.tracking_locations.append({
            "update": count, "lat": lat, "lon": lon,
            "accuracy": acc_str, "time": ts
        })
        st.session_state.update_count = count
        st.session_state.last_sent    = ts

        with trail_box.expander(f"Location trail ({len(st.session_state.tracking_locations)} updates)", expanded=False):
            for entry in reversed(st.session_state.tracking_locations):
                st.markdown(
                    f"**#{entry['update']}** at {entry['time']} - "
                    f"`{entry['lat']:.5f}, {entry['lon']:.5f}` ({entry['accuracy']}) "
                    f"[Maps](https://maps.google.com/?q={entry['lat']},{entry['lon']})"
                )

        # Countdown 30s with 1s ticks - safe, no JS timers
        countdown = st.empty()
        for remaining in range(30, 0, -1):
            if not st.session_state.extreme_active:
                countdown.empty()
                st.stop()
            countdown.info(f"Next update in {remaining} seconds... | Last sent: {ts}")
            time.sleep(1)
        countdown.empty()
        st.rerun()

    else:
        st.error("Could not get GPS location. Make sure location permission is granted.")
        retry_box = st.empty()
        for remaining in range(10, 0, -1):
            if not st.session_state.extreme_active:
                retry_box.empty()
                st.stop()
            retry_box.warning(f"Retrying in {remaining} seconds...")
            time.sleep(1)
        retry_box.empty()
        if st.session_state.extreme_active:
            st.rerun()
