import streamlit as st
import requests
import math
import smtplib
import uuid
import json
import os
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

# ---------- PERSISTENT CONTACTS FILE ----------
CONTACTS_FILE = "saved_contacts.json"

def load_saved_contacts():
    if os.path.exists(CONTACTS_FILE):
        try:
            with open(CONTACTS_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_contacts_to_file(contacts):
    try:
        with open(CONTACTS_FILE, "w") as f:
            json.dump(contacts, f, indent=2)
    except Exception as e:
        st.error(f"Failed to save contacts: {e}")

# ---------- GET LOCATION ----------
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
def send_email(recipient_name, recipient_email, lat, lon):
    maps_link = f"https://maps.google.com/?q={lat},{lon}"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    plain_body = f"""Emergency Alert — Please Read Immediately

Dear {recipient_name},

This is an automated emergency alert sent from the Emergency Panic Button app.

Someone needs your help right now. Please contact them or call emergency services (999) immediately.

Their current location:
  Latitude:  {lat:.6f}
  Longitude: {lon:.6f}
  Google Maps: {maps_link}

Time sent: {timestamp}

---
This message was sent automatically via Emergency Panic Button App.
If you believe this was sent in error, please disregard.
"""

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f8f8f8; padding: 20px;">
        <div style="max-width: 500px; margin: auto; background: white; border-radius: 10px;
                    border-top: 6px solid red; padding: 30px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
            <h1 style="color: red; text-align: center;">Emergency Alert</h1>
            <p style="font-size: 16px;">Dear <b>{recipient_name}</b>,</p>
            <p style="font-size: 16px;">
                This is an automated emergency alert sent from the Emergency Panic Button app.<br><br>
                <b>Someone needs your help immediately.</b><br>
                Please contact them or call emergency services (<b>999</b>) right away.
            </p>
            <div style="background-color: #fff3f3; border-left: 4px solid red;
                        padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p style="margin: 0; font-size: 15px;">
                    📍 <b>Live Location:</b><br>
                    Latitude: <code>{lat:.6f}</code><br>
                    Longitude: <code>{lon:.6f}</code><br>
                    <small style="color:#888;">Sent at: {timestamp}</small>
                </p>
            </div>
            <a href="{maps_link}" style="display: block; text-align: center;
               background-color: #c0392b; color: white; padding: 14px 20px;
               border-radius: 8px; text-decoration: none; font-size: 16px;
               font-weight: bold; margin-top: 10px;">
               View Location on Google Maps
            </a>
            <p style="font-size: 12px; color: #999; text-align: center; margin-top: 20px;">
                This alert was sent automatically via Emergency Panic Button App.<br>
                If you believe this was sent in error, please disregard this message.
            </p>
        </div>
    </body>
    </html>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Emergency Alert - Urgent Assistance Required"
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

def send_email_to_all(lat, lon, contacts):
    results = []
    for contact in contacts:
        success, error = send_email(contact["name"], contact["email"], lat, lon)
        results.append({
            "name": contact["name"],
            "email": contact["email"],
            "success": success,
            "error": error
        })
    return results

# ---------- SIDEBAR: MANAGE CONTACTS ----------
ADMIN_PASSWORD = "admin123"   # ← change this to your own password

st.sidebar.header("📋 Emergency Contacts")

# Load saved contacts from file on first run only
if "extra_contacts" not in st.session_state:
    st.session_state.extra_contacts = load_saved_contacts()

total = len(DEFAULT_CONTACTS) + len(st.session_state.extra_contacts)
st.sidebar.success(f"✅ {total} contact(s) saved — details hidden for privacy.")

st.sidebar.divider()

# Password-protected admin panel to add/remove contacts
with st.sidebar.expander("🔒 Manage Contacts (Admin Only)"):
    pwd = st.text_input("Enter admin password", type="password", key="admin_pwd")

    if pwd == ADMIN_PASSWORD:
        st.caption("Default contacts (fixed):")
        for c in DEFAULT_CONTACTS:
            st.write(f"✅ {c['name']} — {c['email']}")

        st.divider()
        st.caption("Saved extra contacts:")

        if st.session_state.extra_contacts:
            for i, c in enumerate(st.session_state.extra_contacts):
                col1, col2 = st.columns([3, 1])
                col1.write(f"➕ {c['name']} — {c['email']}")
                if col2.button("🗑️", key=f"del_{i}"):
                    st.session_state.extra_contacts.pop(i)
                    save_contacts_to_file(st.session_state.extra_contacts)
                    st.rerun()
        else:
            st.info("No extra contacts saved yet.")

        st.divider()
        st.caption("Add new contact:")
        with st.form("add_contact_form", clear_on_submit=True):
            new_name = st.text_input("Name", placeholder="e.g. Sister")
            new_email = st.text_input("Email", placeholder="e.g. sister@gmail.com")
            add_btn = st.form_submit_button("➕ Add & Save Contact")
            if add_btn:
                if new_name and new_email:
                    st.session_state.extra_contacts.append({
                        "name": new_name,
                        "email": new_email
                    })
                    save_contacts_to_file(st.session_state.extra_contacts)
                    st.success(f"✅ {new_name} saved!")
                else:
                    st.warning("Please fill in both fields.")
    elif pwd != "":
        st.error("❌ Incorrect password.")

# ---------- PANIC BUTTON ----------
st.divider()
all_contacts = DEFAULT_CONTACTS + st.session_state.extra_contacts
st.caption(f"📧 Alert email will be sent to {len(all_contacts)} contact(s) when PANIC is pressed.")

if st.button("🚨 PANIC", use_container_width=True, type="primary"):
    if location:
        lat, lon = location
        st.success(f"📍 Location detected: {lat:.5f}, {lon:.5f}")

        st.info("📤 Sending emergency emails...")
        results = send_email_to_all(lat, lon, all_contacts)

        for r in results:
            if r["success"]:
                st.success(f"✅ Email sent to {r['name']} ({r['email']})")
            else:
                st.error(f"❌ Failed to send to {r['name']} — {r['error']}")

        with st.spinner("🔍 Locating nearest police station..."):
            police = find_police(lat, lon, radius=5000)

        if not police:
            st.warning("Widening search to 15km...")
            police = find_police(lat, lon, radius=15000)

        if police:
            plat, plon, name, dist = police
            st.success(f"🚔 Nearest Police Station: **{name}** ({dist:.0f}m away)")
            nav = f"https://www.google.com/maps/dir/?api=1&destination={plat},{plon}"
            st.link_button("🚓 GO TO POLICE NOW", nav)
        else:
            st.error("No police station found in the area.")

    else:
        st.error("⚠️ Location not available — refresh the page and allow location permission.")
