import os
import sqlite3
import streamlit as st
import urllib.parse
from PIL import Image
import io

# Configure Page Layout
st.set_page_config(page_title="Mjengo App", page_icon="🏗️", layout="wide")


# --- SECURITY: PASSCODE FROM SECRETS / ENV (NO PLAINTEXT IN CODE) ---
def get_admin_passcode():
    """
    Resolve the admin passcode securely.
    Priority: 1) .streamlit/secrets.toml  2) environment variable
    Broad exception catch is intentional for cross-version compatibility
    (older Streamlit raises FileNotFoundError if no secrets file exists).
    """
    try:
        secret = st.secrets.get("ADMIN_PASSCODE")
        if secret:
            return secret
    except Exception:
        pass
    return os.environ.get("ADMIN_PASSCODE", "")


# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect("mjengo.db")
    c = conn.cursor()

    # 1. Contractors Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS contractors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            profession TEXT NOT NULL,
            certifications TEXT,
            fee TEXT,
            location TEXT,
            phone TEXT,
            total_score REAL DEFAULT 0,
            review_count INTEGER DEFAULT 0,
            portfolio_image BLOB
        )
    ''')

    # 2. Materials Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_name TEXT NOT NULL,
            item_name TEXT NOT NULL,
            price TEXT NOT NULL,
            quantity TEXT NOT NULL,
            location TEXT NOT NULL,
            phone TEXT NOT NULL
        )
    ''')

    # Seed default baseline data if empty
    c.execute("SELECT COUNT(*) FROM contractors")
    if c.fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO contractors (name, profession, certifications, fee, location, phone, total_score, review_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("Eng. John Kamau", "Civil Engineer", "NCA Reg 1, Bsc. Civil Eng", "KES 5,000 / Hr", "Nairobi", "+254700000000", 24.5, 5),
                ("Alice Omwamba", "Architect", "BORAQS Registered Professional", "KES 50,000 / Plan", "Kisumu", "+254711111111", 19.2, 4),
                ("David Ochieng", "Mason / Fundi", "NITA Grade 1 Certified Mason", "KES 2,500 / Day", "Mombasa", "+254722222222", 13.5, 3),
                ("Ben Wekesa", "Electrical Contractor", "EPRA Class A Licensed", "KES 3,500 / Day", "Kakamega", "+254733333333", 4.8, 1)
            ]
        )

    c.execute("SELECT COUNT(*) FROM materials")
    if c.fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO materials (supplier_name, item_name, price, quantity, location, phone) VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("Apex Hardware Ltd", "Cement (50KG Bag)", "KES 850", "500 Bags", "Nairobi", "+254744444444"),
                ("Western Quarry Suppliers", "River Sand (per Tonne)", "KES 3,500", "40 Tonnes", "Kakamega", "+254755555555"),
                ("Coast Steel & Iron", "Reinforcement Steel Bars (D12)", "KES 1,200 / Pc", "150 Pieces", "Mombasa", "+254766666666")
            ]
        )
    conn.commit()
    conn.close()


# Helper: wa.me requires digits only (no "+", spaces or dashes)
def clean_phone(phone):
    return "".join(ch for ch in (phone or "") if ch.isdigit())


# --- DATABASE OPERATIONS ---
def get_ranked_contractors(profession_filter="All", search_city=""):
    conn = sqlite3.connect("mjengo.db")
    c = conn.cursor()
    query = "SELECT id, name, profession, certifications, fee, location, phone, total_score, review_count, portfolio_image FROM contractors WHERE 1=1"
    params = []

    if profession_filter != "All":
        query += " AND profession = ?"
        params.append(profession_filter)
    if search_city:
        query += " AND location LIKE ?"
        params.append(f"%{search_city}%")

    c.execute(query, params)
    rows = c.fetchall()
    conn.close()

    contractors = []
    for r in rows:
        cid, name, prof, certs, fee, loc, phone, total_score, review_count, img_blob = r
        avg_rating = round(total_score / review_count, 1) if review_count > 0 else 0.0

        contractors.append({
            "id": cid, "name": name, "profession": prof, "certifications": certs,
            "fee": fee, "location": loc, "phone": phone, "avg_rating": avg_rating,
            "reviews": review_count, "image": img_blob
        })
    return sorted(contractors, key=lambda x: (x["avg_rating"], x["reviews"]), reverse=True)


def get_materials(search_city=""):
    conn = sqlite3.connect("mjengo.db")
    c = conn.cursor()
    query = "SELECT id, supplier_name, item_name, price, quantity, location, phone FROM materials WHERE 1=1"
    params = []

    if search_city:
        query += " AND location LIKE ?"
        params.append(f"%{search_city}%")

    c.execute(query, params)
    rows = c.fetchall()
    conn.close()

    return [
        {
            "id": r[0], "supplier": r[1], "item": r[2],
            "price": r[3], "qty": r[4], "location": r[5], "phone": r[6]
        } for r in rows
    ]


# --- APP LAYOUT INTERFACE ---
init_db()
st.title("🏗️ Mjengo Premium Platform")

st.sidebar.header("🧭 Navigation Menu")
page = st.sidebar.radio("Go to Options:", ["Find Contractors", "Materials Store", "Project Budget Estimator", "Join Marketplace", "Admin Panel"])

st.sidebar.markdown("---")
st.sidebar.subheader("📍 Quick Location Search")
city_query = st.sidebar.text_input("Filter by Town/City:", value="").strip()

# --- PAGE 1: FIND CONTRACTORS ---
if page == "Find Contractors":
    st.write("### 👷 Top Rated Professionals")
    selected_prof = st.selectbox("Discipline Subcategory:", ["All", "Civil Engineer", "Architect", "Electrical Contractor", "Mason / Fundi", "Plumber"])

    contractors = get_ranked_contractors(selected_prof, city_query)

    if not contractors:
        st.info("No verified contractors listed here yet.")

    for rank, con in enumerate(contractors, start=1):
        with st.container():
            col_img, col_main, col_action = st.columns([1.2, 2.5, 1.5])

            with col_img:
                if con["image"]:
                    # FIXED: width="stretch" replaces deprecated use_container_width
                    # (requires Streamlit >= 1.49)
                    st.image(Image.open(io.BytesIO(con["image"])), caption="Work Sample Portfolio", width="stretch")
                else:
                    st.warning("📸 No portfolio image uploaded.")

            with col_main:
                st.markdown(f"#### #{rank} {con['name']} — `{con['profession']}`")
                st.write(f"📜 **Credentials:** {con['certifications']}")
                st.write(f"💰 **Rates:** {con['fee']} | 📍 **Location:** {con['location']}")

                star_display = "⭐" * int(round(con['avg_rating'])) if con['avg_rating'] > 0 else "Unrated"
                st.write(f"📈 **Score:** {con['avg_rating']} / 5 ({star_display}) — ({con['reviews']} reviews)")

                msg = urllib.parse.quote(f"Hello {con['name']}, I viewed your Mjengo profile and would love to consult on a project.")
                st.markdown(f'''
                    <a href="https://wa.me/{clean_phone(con['phone'])}?text={msg}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:8px 14px; border-radius:4px; cursor:pointer; font-weight:bold; margin-right:8px;">💬 WhatsApp Pitch</button></a>
                    <a href="tel:{con['phone']}"><button style="background-color:#0078D4; color:white; border:none; padding:8px 14px; border-radius:4px; cursor:pointer; font-weight:bold;">📞 Direct Call</button></a>
                ''', unsafe_allow_html=True)

            with col_action:
                st.write("**Rate Experience:**")
                score = st.slider("Select Stars", 1, 5, 5, key=f"s_{con['id']}")
                if st.button("Submit Rating", key=f"b_{con['id']}"):
                    conn = sqlite3.connect("mjengo.db")
                    c = conn.cursor()
                    c.execute("UPDATE contractors SET total_score = total_score + ?, review_count = review_count + 1 WHERE id = ?", (score, con['id']))
                    conn.commit()
                    conn.close()
                    st.success("Rating submitted successfully!")
                    st.rerun()
            st.divider()

# --- PAGE 2: MATERIALS STORE ---
elif page == "Materials Store":
    st.write("### 🧱 Direct-to-Site Material Procurement")
    materials_list = get_materials(city_query)

    if not materials_list:
        st.info("No materials available matching the active location filter.")

    for mat in materials_list:
        with st.container():
            col_info, col_contact = st.columns([3, 1])
            with col_info:
                st.markdown(f"#### 📦 {mat['item']}")
                st.write(f"🏢 **Supplier:** {mat['supplier']} | 📍 **Depot:** {mat['location']}")
                st.markdown(f"💰 Wholesale Rate: **{mat['price']}** | 🔢 Quantity: `{mat['qty']}`")
            with col_contact:
                mat_msg = urllib.parse.quote(f"Hello {mat['supplier']}, I want to purchase '{mat['item']}' via Mjengo.")
                st.write("**Purchase Channels:**")
                st.markdown(f'''
                    <a href="https://wa.me/{clean_phone(mat['phone'])}?text={mat_msg}" target="_blank"><button style="background-color:#25D366; color:white; border:none; padding:8px 12px; border-radius:4px; cursor:pointer; font-weight:bold; width:100%; margin-bottom:6px;">💬 Buy via WhatsApp</button></a>
                    <a href="tel:{mat['phone']}"><button style="background-color:#0078D4; color:white; border:none; padding:8px 12px; border-radius:4px; cursor:pointer; font-weight:bold; width:100%;">📞 Call Supplier</button></a>
                ''', unsafe_allow_html=True)
            st.divider()

# --- PAGE 3: PROJECT BUDGET ESTIMATOR ---
elif page == "Project Budget Estimator":
    st.write("### 🧮 Material Estimator Dashboard")
    st.write("Estimate flooring concrete screed batches based on standard architectural rules-of-thumb.")

    col_dim1, col_dim2 = st.columns(2)
    with col_dim1:
        length = st.number_input("Room Length (Meters):", min_value=1.0, value=4.0, step=0.5)
    with col_dim2:
        width = st.number_input("Room Width (Meters):", min_value=1.0, value=3.5, step=0.5)

    thickness = st.number_input("Screed Thickness (mm):", min_value=10, max_value=100, value=50, step=5)
    floor_area = length * width
    volume_cubic_meters = floor_area * (thickness / 100)
    cement_bags = int(round(volume_cubic_meters * 9.5))
    sand_tonnes = round(volume_cubic_meters * 1.1, 2)
    st.success(f"📈 Total Floor Footprint Target Area: {floor_area:.2f} Square Meters")

    c1, c2 = st.columns(2)
    c1.metric("Estimated Cement Bags (50KG)", f"{max(1, cement_bags)} Bags")
    c2.metric("Estimated River Sand Volume", f"{max(0.5, sand_tonnes)} Tonnes")
    st.info("💡 Note: Standard 1:3 mortar density factors applied. Logistics parameters may vary locally by supplier.")

# --- PAGE 4: JOIN MARKETPLACE ---
elif page == "Join Marketplace":
    st.write("### 📝 Register Professional Services or Material Inventory")
    reg_type = st.radio("Account Category:", ["Contractor / Specialist", "Material Supplier Company"])
    if reg_type == "Contractor / Specialist":
        with st.form("con_reg", clear_on_submit=False):  # FIXED: keep input on validation errors
            name = st.text_input("Professional / Company Name:")
            prof = st.selectbox("Discipline Subcategory:", ["Civil Engineer", "Architect", "Electrical Contractor", "Mason / Fundi", "Plumber"])
            certs = st.text_area("Accreditations & Work Experience Details:")
            fee = st.text_input("Standard Service Rates (e.g. KES 3,500 / Day):")
            loc = st.text_input("Core Town/City Base:")
            phone = st.text_input("Mobile Contact (e.g. +2547XXXXXXXX):")
            uploaded_file = st.file_uploader("Upload Past Project Photo or Certificate (JPG/PNG):", type=["jpg", "jpeg", "png"])
            submit_con = st.form_submit_button("Launch Public Profile")
        if submit_con:
            if name and loc and phone:
                img_blob = None
                if uploaded_file is not None:
                    img_blob = uploaded_file.read()
                conn = sqlite3.connect("mjengo.db")
                c = conn.cursor()
                c.execute("INSERT INTO contractors (name, profession, certifications, fee, location, phone, portfolio_image) VALUES (?, ?, ?, ?, ?, ?, ?)", (name, prof, certs, fee, loc, phone, img_blob))
                conn.commit()
                conn.close()
                st.success("Your professional Mjengo profile is now live!")
            else:
                st.error("Missing mandatory fields: Name, Location, and Phone Number.")
    else:
        with st.form("mat_reg", clear_on_submit=False):  # FIXED: keep input on validation errors
            sup_name = st.text_input("Supplier / Hardware Name:")
            item = st.text_input("Building Material Description (e.g., Cement Bags):")
            price = st.text_input("Price tag per unit:")
            qty = st.text_input("In-Stock Volume:")
            loc = st.text_input("Supply Base Town/City:")
            phone = st.text_input("Sales Desk Mobile Phone:")
            submit_mat = st.form_submit_button("Publish Store Inventory")
        if submit_mat:
            if sup_name and item and price and loc and phone:
                conn = sqlite3.connect("mjengo.db")
                c = conn.cursor()
                c.execute("INSERT INTO materials (supplier_name, item_name, price, quantity, location, phone) VALUES (?, ?, ?, ?, ?, ?)", (sup_name, item, price, qty, loc, phone))
                conn.commit()
                conn.close()
                st.success("Item inventory listed successfully!")
            else:
                st.error("Missing mandatory fields: Supplier, Item, Price, Location, and Phone.")

# --- PAGE 5: ADMIN PANEL ---
elif page == "Admin Panel":
    st.write("### 🛡️ Platform Moderation Panel")
    pwd = st.text_input("Enter System Master Passcode to access listing logs:", type="password")
    # FIXED: passcode resolved via st.secrets / environment variable — nothing hardcoded
    if pwd and pwd == get_admin_passcode():
        st.success("Authorized Access Granted.")
        conn = sqlite3.connect("mjengo.db")
        c = conn.cursor()
        st.write("#### 👷 Registered Contractors Listing Management")
        c.execute("SELECT id, name, profession, location FROM contractors")
        cons_list = c.fetchall()
        for cid, cname, cprof, cloc in cons_list:
            col_txt, col_del = st.columns([4, 1])
            col_txt.write(f"ID: {cid} | {cname} ({cprof}) - {cloc}")
            if col_del.button("🗑️ Delete Contractor", key=f"del_c_{cid}"):
                c.execute("DELETE FROM contractors WHERE id = ?", (cid,))
                conn.commit()
                st.warning(f"Profile {cname} removed.")
                st.rerun()
        st.write("#### 🧱 Active Supply Catalog Management")
        c.execute("SELECT id, supplier_name, item_name, location FROM materials")
        mats_list = c.fetchall()
        for mid, msup, mitem, mloc in mats_list:
            col_m_txt, col_m_del = st.columns([4, 1])
            col_m_txt.write(f"ID: {mid} | {mitem} by {msup} ({mloc})")
            if col_m_del.button("🗑️ Remove Listing", key=f"del_m_{mid}"):
                c.execute("DELETE FROM materials WHERE id = ?", (mid,))
                conn.commit()
                st.warning("Material listing purged.")
                st.rerun()
        conn.close()
    elif pwd != "":
        st.error("Incorrect administrative credentials. Access denied.")