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
if "extreme_panic_active" not in st.session_state:
    st.session_state.extreme_panic_active = False
if "extreme_panic_update_count" not in st.session_state:
    st.session_state.extreme_panic_update_count = 0
if "extreme_panic_last_sent" not in st.session_state:
    st.session_state.extreme_panic_last_sent = None

# ---------- READ THIS DEVICE'S SAVED CONTACT FROM BROWSER localStorage ----------
raw = streamlit_js_eval(
    js_expressions="localStorage.getItem('emergency_my_contact')",
    key="read_my_contact"
)

my_contact = None
if raw and raw != "null":
    try:
        my_contact = json.loads(raw)
    except Exception:
        my_contact = None

# ---------- GET LOCATION (standard) ----------
location = streamlit_js_eval(
    js_expressions="""
    new Promise((resolve, reject) => {
        navigator.geolocation.getCurrentPosition(
            pos => resolve([pos.coords.latitude, pos.coords.longitude]),
            err => resolve(null)
        );
    })
    """,
    key="get_location"
)

# ---------- GET HIGH-ACCURACY LIVE LOCATION (for Extreme Panic) ----------
# This JS returns the current position with high accuracy enabled
extreme_location = streamlit_js_eval(
    js_expressions="""
    new Promise((resolve) => {
        navigator.geolocation.getCurrentPosition(
            pos => resolve([pos.coords.latitude, pos.coords.longitude, pos.coords.accuracy]),
            err => resolve(null),
            { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
        );
    })
    """,
    key=f"extreme_location_{st.session_state.extreme_panic_update_count}"
)

# ---------- HAVERSINE ----------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
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
            data={"data": query},
            timeout=25
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
    except Exception as e:
        st.error(f"Overpass error: {e}")
        return None

# ---------- SEND EMAIL ----------
def send_email(recipient_name, recipient_email, lat, lon, update_num=None, accuracy=None):
    maps_link = f"https://maps.google.com/?q={lat},{lon}"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    is_update = update_num is not None
    subject_prefix = f"🔴 LIVE UPDATE #{update_num} — " if is_update else ""
    subject = f"{subject_prefix}Emergency Alert - Urgent Assistance Required"

    accuracy_text = f"±{accuracy:.0f}m accuracy" if accuracy else ""

    plain_body = f"""{'⚠️ LIVE TRACKING UPDATE #' + str(update_num) if is_update else 'Emergency Alert'} — Please Read Immediately

Dear {recipient_name},

{'This is a LIVE LOCATION UPDATE. The person is moving — this is their latest tracked position.' if is_update else 'This is an automated emergency alert sent from the Emergency Panic Button app.'}

Someone needs your help right now. Please contact them or call emergency services (999) immediately.

Current Location:
  Latitude:  {lat:.6f}
  Longitude: {lon:.6f}
  {accuracy_text}
  Google Maps: {maps_link}

Time: {timestamp}
{'Update #' + str(update_num) + ' — Location updates sent every 30 seconds.' if is_update else ''}

---
This message was sent automatically via Emergency Panic Button App.
"""

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f8f8f8; padding: 20px;">
        <div style="max-width: 500px; margin: auto; background: white; border-radius: 10px;
                    border-top: 6px solid {'#8B0000' if is_update else 'red'}; padding: 30px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
            <h1 style="color: {'#8B0000' if is_update else 'red'}; text-align: center;">
                {'🔴 LIVE UPDATE #' + str(update_num) if is_update else '🚨 Emergency Alert'}
            </h1>
            <p style="font-size: 16px;">Dear <b>{recipient_name}</b>,</p>
            <p style="font-size: 16px;">
                {'<b>⚠️ LIVE TRACKING ACTIVE</b> — This person is moving. This is their most recent location.' if is_update else 'This is an automated emergency alert.'}
                <br><br>
                <b>Immediate help is needed.</b><br>
                Please contact them or call emergency services (<b>999</b>) right away.
            </p>
            <div style="background-color: {'#fff0f0' if is_update else '#fff3f3'}; border-left: 4px solid {'#8B0000' if is_update else 'red'};
                        padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p style="margin: 0; font-size: 15px;">
                    📍 <b>{'Latest ' if is_update else ''}Live Location:</b><br>
                    Latitude: <code>{lat:.6f}</code><br>
                    Longitude: <code>{lon:.6f}</code><br>
                    {f'<small>Accuracy: {accuracy_text}</small><br>' if accuracy else ''}
                    <small style="color:#888;">Sent at: {timestamp}</small>
                    {f'<br><small style="color:#8B0000;">Update #{update_num} — new location every 30 sec</small>' if is_update else ''}
                </p>
            </div>
            <a href="{maps_link}" style="display: block; text-align: center;
               background-color: {'#8B0000' if is_update else '#c0392b'}; color: white; padding: 14px 20px;
               border-radius: 8px; text-decoration: none; font-size: 16px;
               font-weight: bold; margin-top: 10px;">
               📍 {'Track Latest Location' if is_update else 'View Location on Google Maps'}
            </a>
            <p style="font-size: 12px; color: #999; text-align: center; margin-top: 20px;">
                Sent automatically via Emergency Panic Button App.
            </p>
        </div>
    </body>
    </html>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
        msg["To"] = recipient_email
        msg["Reply-To"] = SENDER_EMAIL
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid(domain="gmail.com")

        msg.attach(MIMEText(plain_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, recipient_email, msg.as_string())

        return True, ""
    except Exception as e:
        return False, str(e)

def send_email_to_all(lat, lon, contacts, update_num=None, accuracy=None):
    results = []
    for contact in contacts:
        success, error = send_email(contact["name"], contact["email"], lat, lon, update_num, accuracy)
        results.append({
            "name": contact["name"],
            "email": contact["email"],
            "success": success,
            "error": error
        })
    return results

# ---------- BUILD CONTACT LIST ----------
all_contacts = list(DEFAULT_CONTACTS)
if my_contact:
    already = any(c["email"].lower() == my_contact["email"].lower() for c in all_contacts)
    if not already:
        all_contacts.append(my_contact)

# ---------- MY CONTACT SECTION ----------
st.divider()
st.subheader("👤 My Emergency Contact")

if my_contact:
    st.success(f"✅ Saved on this device: **{my_contact['name']}** — alerts will be sent to your registered email.")
    if st.button("🗑️ Remove my contact from this device"):
        streamlit_js_eval(
            js_expressions="localStorage.removeItem('emergency_my_contact'); true",
            key="remove_contact"
        )
        st.info("Contact removed. Refresh the page to confirm.")
else:
    st.info("No contact saved on this device yet. Register below — your details stay only on this device.")
    with st.form("register_form", clear_on_submit=True):
        reg_name = st.text_input("Your Name", placeholder="e.g. Sarah")
        reg_email = st.text_input("Your Email", placeholder="e.g. sarah@gmail.com")
        reg_btn = st.form_submit_button("💾 Save to This Device")
        if reg_btn:
            if reg_name and reg_email:
                contact_json = json.dumps({"name": reg_name, "email": reg_email})
                contact_json_escaped = contact_json.replace("'", "\\'")
                streamlit_js_eval(
                    js_expressions=f"localStorage.setItem('emergency_my_contact', '{contact_json_escaped}'); true",
                    key="save_contact"
                )
                st.success(f"✅ Saved! Refresh the page to confirm, {reg_name}.")
            else:
                st.warning("Please fill in both your name and email.")

# ---------- PANIC BUTTONS ----------
st.divider()
st.caption(f"📧 Alert will be sent to {len(all_contacts)} contact(s) when PANIC is pressed.")

col1, col2 = st.columns(2)

# ---- STANDARD PANIC ----
with col1:
    if st.button("🚨 PANIC", use_container_width=True, type="primary"):
        if location:
            lat, lon = location
            st.success(f"📍 Location: {lat:.5f}, {lon:.5f}")
            st.info("📤 Sending emergency emails...")
            results = send_email_to_all(lat, lon, all_contacts)
            for r in results:
                if r["success"]:
                    st.success(f"✅ Sent to {r['name']}")
                else:
                    st.error(f"❌ Failed to send to {r['name']} — {r['error']}")
            with st.spinner("🔍 Locating nearest police station..."):
                police = find_police(lat, lon, radius=5000)
            if not police:
                st.warning("Widening search to 15km...")
                police = find_police(lat, lon, radius=15000)
            if police:
                plat, plon, name, dist = police
                st.success(f"🚔 Nearest: **{name}** ({dist:.0f}m away)")
                nav = f"https://www.google.com/maps/dir/?api=1&destination={plat},{plon}"
                st.link_button("🚓 GO TO POLICE NOW", nav)
            else:
                st.error("No police station found nearby.")
        else:
            st.error("⚠️ Location unavailable — allow location access and refresh.")

# ---- EXTREME PANIC ----
with col2:
    if not st.session_state.extreme_panic_active:
        if st.button("🆘 EXTREME PANIC\n*(Live Tracking)*", use_container_width=True):
            st.session_state.extreme_panic_active = True
            st.session_state.extreme_panic_update_count = 0
            st.rerun()
    else:
        if st.button("🛑 STOP TRACKING", use_container_width=True):
            st.session_state.extreme_panic_active = False
            st.session_state.extreme_panic_update_count = 0
            st.success("✅ Live tracking stopped.")
            st.rerun()

# ---------- EXTREME PANIC LOGIC ----------
if st.session_state.extreme_panic_active:
    st.divider()
    st.error("🔴 **EXTREME PANIC ACTIVE — LIVE TRACKING ON**")
    st.warning("📡 Your location is being tracked and emailed every 30 seconds. Press **STOP TRACKING** to end.")

    count = st.session_state.extreme_panic_update_count

    if extreme_location:
        lat = extreme_location[0]
        lon = extreme_location[1]
        accuracy = extreme_location[2] if len(extreme_location) > 2 else None

        maps_link = f"https://maps.google.com/?q={lat},{lon}"
        acc_text = f" (±{accuracy:.0f}m)" if accuracy else ""

        st.info(f"📍 Update #{count + 1} — Location: `{lat:.6f}, {lon:.6f}`{acc_text}")
        st.markdown(f"[🗺️ Open in Google Maps]({maps_link})")

        with st.spinner(f"📤 Sending location update #{count + 1} to all contacts..."):
            results = send_email_to_all(lat, lon, all_contacts, update_num=count + 1, accuracy=accuracy)

        for r in results:
            if r["success"]:
                st.success(f"✅ Update #{count + 1} sent to {r['name']}")
            else:
                st.error(f"❌ Failed to send to {r['name']} — {r['error']}")

        st.session_state.extreme_panic_update_count += 1
        st.session_state.extreme_panic_last_sent = datetime.now().strftime("%H:%M:%S")

        # Show countdown and auto-refresh after 30 seconds
        st.info(f"⏱️ Next location update in 30 seconds... (Last sent: {st.session_state.extreme_panic_last_sent})")

        # Auto-rerun after 30 seconds using JS
        streamlit_js_eval(
            js_expressions="new Promise(resolve => setTimeout(() => resolve('refresh'), 30000))",
            key=f"auto_refresh_{count}"
        )
        st.rerun()

    else:
        st.error("⚠️ Could not get location. Make sure location permissions are granted. Retrying in 10 seconds...")
        streamlit_js_eval(
            js_expressions="new Promise(resolve => setTimeout(() => resolve('retry'), 10000))",
            key=f"retry_location_{count}"
        )
        st.rerun()
