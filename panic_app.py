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

st.set_page_config(page_title="Emergency Panic", layout="centered")
st.title("🚨 One-Click Emergency Panic Button")

# ==============================
# GMAIL CONFIG (Move to secrets in production)
# ==============================
SENDER_EMAIL = "shathia190304@gmail.com"
SENDER_APP_PASSWORD = "YOUR_APP_PASSWORD_HERE"
SENDER_NAME = "Emergency Alert"

# ==============================
# DEFAULT CONTACT
# ==============================
DEFAULT_CONTACTS = [
    {"name": "Admin", "email": "shathia190304@gmail.com"},
]

# ==============================
# SESSION STATE INIT
# ==============================
for key, default in [
    ("extreme_active", False),
    ("update_count", 0),
    ("tracking_locations", []),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ==============================
# READ SAVED CONTACTS
# ==============================
raw = streamlit_js_eval(
    js_expressions="localStorage.getItem('emergency_my_contacts')",
    key="read_contacts"
)

my_contacts = []
if raw and raw != "null":
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            my_contacts = parsed
    except:
        my_contacts = []

# ==============================
# HAVERSINE FUNCTION
# ==============================
def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# ==============================
# FIND NEAREST POLICE
# ==============================
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
            if not plat or not plon:
                continue

            dist = haversine(lat, lon, plat, plon)
            if dist < best_dist:
                best_dist = dist
                name = el.get("tags", {}).get("name", "Police Station")
                best = (plat, plon, name, best_dist)

        return best

    except:
        return None

# ==============================
# EMAIL SENDER
# ==============================
def send_email(name, email, lat, lon, update_num=None, accuracy=None):

    maps_link = f"https://maps.google.com/?q={lat},{lon}"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    subject = (
        f"LIVE UPDATE #{update_num} - Emergency Alert"
        if update_num else
        "Emergency Alert - Urgent"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    msg["To"] = email
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="gmail.com")

    body = f"""
Emergency Alert

Dear {name},

Emergency panic button was activated.

Location:
Latitude: {lat}
Longitude: {lon}
Accuracy: {accuracy if accuracy else "N/A"}

Google Maps:
{maps_link}

Time: {timestamp}
"""

    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, email, msg.as_string())
        return True
    except Exception as e:
        return False

def send_to_all(lat, lon, contacts, update_num=None, accuracy=None):
    results = []
    for c in contacts:
        success = send_email(c["name"], c["email"], lat, lon, update_num, accuracy)
        results.append((c["name"], success))
    return results

# ==============================
# BUILD CONTACT LIST
# ==============================
all_contacts = list(DEFAULT_CONTACTS)
for c in my_contacts:
    if not any(x["email"].lower() == c["email"].lower() for x in all_contacts):
        all_contacts.append(c)

st.caption(f"Alerts will be sent to {len(all_contacts)} contact(s).")

# ==============================
# PANIC BUTTONS
# ==============================
col1, col2 = st.columns(2)

# -------- NORMAL PANIC --------
with col1:
    if st.button("PANIC", use_container_width=True, type="primary",
                 disabled=st.session_state.extreme_active):

        loc = streamlit_js_eval(
            js_expressions="""
            new Promise(resolve => {
                navigator.geolocation.getCurrentPosition(
                    p => resolve([p.coords.latitude, p.coords.longitude, p.coords.accuracy]),
                    err => resolve("ERROR:" + err.message),
                    { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
                );
            })
            """,
            key="panic_location"
        )

        if isinstance(loc, list):
            lat, lon = loc[0], loc[1]
            accuracy = loc[2] if len(loc) > 2 else None

            st.success(f"Location: {lat:.6f}, {lon:.6f}")

            results = send_to_all(lat, lon, all_contacts)

            for name, success in results:
                if success:
                    st.success(f"Sent to {name}")
                else:
                    st.error(f"Failed to send to {name}")

            police = find_police(lat, lon)
            if police:
                plat, plon, pname, dist = police
                st.success(f"{pname} - {dist:.0f}m away")
                st.link_button("GO TO POLICE",
                               f"https://www.google.com/maps/dir/?api=1&destination={plat},{plon}")

        elif isinstance(loc, str):
            st.error(loc)
        else:
            st.error("Location unavailable. Please allow location access.")

# -------- EXTREME PANIC --------
with col2:
    if not st.session_state.extreme_active:
        if st.button("EXTREME PANIC - Live Tracking", use_container_width=True):
            st.session_state.extreme_active = True
            st.session_state.update_count = 0
            st.session_state.tracking_locations = []
            st.rerun()
    else:
        if st.button("STOP TRACKING", use_container_width=True):
            st.session_state.extreme_active = False
            st.success("Tracking stopped.")
            st.rerun()

# ==============================
# EXTREME TRACKING LOOP
# ==============================
if st.session_state.extreme_active:

    st.error("EXTREME PANIC ACTIVE - LIVE TRACKING")

    loc = streamlit_js_eval(
        js_expressions="""
        new Promise(resolve => {
            navigator.geolocation.getCurrentPosition(
                p => resolve([p.coords.latitude, p.coords.longitude, p.coords.accuracy]),
                err => resolve(null),
                { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
            );
        })
        """,
        key=f"extreme_loc_{st.session_state.update_count}"
    )

    if isinstance(loc, list):
        lat, lon = loc[0], loc[1]
        accuracy = loc[2] if len(loc) > 2 else None

        st.session_state.update_count += 1

        send_to_all(lat, lon, all_contacts,
                    update_num=st.session_state.update_count,
                    accuracy=accuracy)

        st.info(f"Update #{st.session_state.update_count} sent")

    for i in range(30, 0, -1):
        if not st.session_state.extreme_active:
            st.stop()
        st.info(f"Next update in {i} seconds...")
        time.sleep(1)

    st.rerun()
