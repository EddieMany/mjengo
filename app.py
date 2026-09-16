import os
import psycopg2
from psycopg2.extras import DictCursor
import streamlit as st
import urllib.parse
from PIL import Image
import io

# Configure Page Layout
st.set_page_config(page_title="Mjengo App", page_icon="🏗️", layout="wide")


# --- SECURITY: PASSCODE FROM SECRETS / ENV ---
def get_admin_passcode():
    """
    Resolve the admin passcode securely.
    Priority: 1) .streamlit/secrets.toml  2) environment variable
    """
    try:
        secret = st.secrets.get("ADMIN_PASSCODE")
        if secret:
            return secret
    except Exception:
        pass
    return os.environ.get("ADMIN_PASSCODE", "")


# --- DATABASE CONNECTION UTILITY ---

# --- DATABASE CONNECTION UTILITY ---
def get_db_connection():
    """Establishes a connection to the hosted Supabase PostgreSQL instance securely using individual parameters."""
    try:
        # Check if individual parameters are set
        if "DB_HOST" in st.secrets:
            return psycopg2.connect(
                host=st.secrets["DB_HOST"],
                database=st.secrets["DB_NAME"],
                user=st.secrets["DB_USER"],
                password=st.secrets["DB_PASS"],
                port=st.secrets["DB_PORT"],
                sslmode="require"
            )
        
        # Fallback to absolute URL if present
        db_url = st.secrets.get("DATABASE_URL") or os.environ.get("DATABASE_URL")
        if db_url:
            return psycopg2.connect(db_url)
            
        st.error("Missing database connection parameter secrets!")
        st.stop()
    except Exception as e:
        st.error(f"🔌 Database Connection Failed: {str(e)}")
        st.stop()

#def get_db_connection():
#    """Establishes a connection to the hosted Supabase PostgreSQL instance securely."""
#    db_url = st.secrets.get("DATABASE_URL") or os.environ.get("DATABASE_URL")
#    if not db_url:
#        st.error("Missing DATABASE_URL secret parameter! Please check your configuration.")
#        st.stop()
#    return psycopg2.connect(db_url)


# --- DATABASE SETUP ---
def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    # 1. Contractors Table (PostgreSQL Serial + Bytea types)
    c.execute('''
        CREATE TABLE IF NOT EXISTS contractors (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            profession TEXT NOT NULL,
            certifications TEXT,
            fee TEXT,
            location TEXT,
            phone TEXT,
            total_score REAL DEFAULT 0,
            review_count INTEGER DEFAULT 0,
            portfolio_image BYTEA
        )
    ''')

    # 2. Materials Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS materials (
            id SERIAL PRIMARY KEY,
            supplier_name TEXT NOT NULL,
            item_name TEXT NOT NULL,
            price TEXT NOT NULL,
            quantity TEXT NOT NULL,
            location TEXT NOT NULL,
            phone TEXT NOT NULL
        )
    ''')
    conn.commit()

    # Seed baseline data if table is fresh
    c.execute("SELECT COUNT(*) FROM contractors;")
    if c.fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO contractors (name, profession, certifications, fee, location, phone, total_score, review_count) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            [
                ("Eng. John Kamau", "Civil Engineer", "NCA Reg 1, Bsc. Civil Eng", "KES 5,000 / Hr", "Nairobi", "+254700000000", 24.5, 5),
                ("Alice Omwamba", "Architect", "BORAQS Registered Professional", "KES 50,000 / Plan", "Kisumu", "+254711111111", 19.2, 4),
                ("David Ochieng", "Mason / Fundi", "NITA Grade 1 Certified Mason", "KES 2,500 / Day", "Mombasa", "+254722222222", 13.5, 3),
                ("Ben Wekesa", "Electrical Contractor", "EPRA Class A Licensed", "KES 3,500 / Day", "Kakamega", "+254733333333", 4.8, 1)
            ]
        )

    c.execute("SELECT COUNT(*) FROM materials;")
    if c.fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO materials (supplier_name, item_name, price, quantity, location, phone) VALUES (%s, %s, %s, %s, %s, %s)",
            [
                ("Apex Hardware Ltd", "Cement (50KG Bag)", "KES 850", "500 Bags", "Nairobi", "+254744444444"),
                ("Western Quarry Suppliers", "River Sand (per Tonne)", "KES 3,500", "40 Tonnes", "Kakamega", "+254755555555"),
                ("Coast Steel & Iron", "Reinforcement Steel Bars (D12)", "KES 1,200 / Pc", "150 Pieces", "Mombasa", "+254766666666")
            ]
        )
    conn.commit()
    c.close()
    conn.close()


# Helper: wa.me requires digits only (no "+", spaces or dashes)
def clean_phone(phone):
    return "".join(ch for ch in (phone or "") if ch.isdigit())


# --- DATABASE OPERATIONS ---
def get_ranked_contractors(profession_filter="All", search_city=""):
    conn = get_db_connection()
    c = conn.cursor(cursor_factory=DictCursor)
    query = "SELECT id, name, profession, certifications, fee, location, phone, total_score, review_count, portfolio_image FROM contractors WHERE 1=1"
    params = []

    if profession_filter != "All":
        query += " AND profession = %s"
        params.append(profession_filter)
    if search_city:
        query += " AND location ILIKE %s"  # PostgreSQL Case-Insensitive Matching
        params.append(f"%{search_city}%")

    c.execute(query, params)
    rows = c.fetchall()
    c.close()
    conn.close()

    contractors = []
    for r in rows:
        avg_rating = round(r["total_score"] / r["review_count"], 1) if r["review_count"] > 0 else 0.0
        # Convert memoryview/bytea data to usable raw Python bytes if layout exists
        img_blob = bytes(r["portfolio_image"]) if r["portfolio_image"] else None

        contractors.append({
            "id": r["id"], "name": r["name"], "profession": r["profession"], "certifications": r["certifications"],
            "fee": r["fee"], "location": r["location"], "phone": r["phone"], "avg_rating": avg_rating,
            "reviews": r["review_count"], "image": img_blob
        })
    return sorted(contractors, key=lambda x: (x["avg_rating"], x["reviews"]), reverse=True)


def get_materials(search_city=""):
    conn = get_db_connection()
    c = conn.cursor(cursor_factory=DictCursor)
    query = "SELECT id, supplier_name, item_name, price, quantity, location, phone FROM materials WHERE 1=1"
    params = []

    if search_city:
        query += " AND location ILIKE %s"
        params.append(f"%{search_city}%")

    c.execute(query, params)
    rows = c.fetchall()
    c.close()
    conn.close()

    return [
        {
            "id": r["id"], "supplier": r["supplier_name"], "item": r["item_name"],
            "price": r["price"], "qty": r["quantity"], "location": r["location"], "phone": r["phone"]
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
                    st.image(Image.open(io.BytesIO(con["image"])), caption="Work Sample Portfolio", use_container_width=True)
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
                    conn = get_db_connection()
                    c = conn.cursor()
                    c.execute("UPDATE contractors SET total_score = total_score + %s, review_count = review_count + 1 WHERE id = %s", (score, con['id']))
                    conn.commit()
                    c.close()
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
            col_info, col_contact = st.columns([3, 1])  #  Fixed Explicit Weights#with st.container():
            #col_info, col_contact = st.columns()
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
        with st.form("con_reg", clear_on_submit=False):
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
                
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("INSERT INTO contractors (name, profession, certifications, fee, location, phone, portfolio_image) VALUES (%s, %s, %s, %s, %s, %s, %s)", 
                          (name, prof, certs, fee, loc, phone, psycopg2.Binary(img_blob) if img_blob else None))
                conn.commit()
                c.close()
                conn.close()
                st.success("Your professional Mjengo profile is now live!")
            else:
                st.error("Missing mandatory fields: Name, Location, and Phone Number.")
                
    else:
        with st.form("mat_reg", clear_on_submit=False):
            sup_name = st.text_input("Supplier / Hardware Name:")
            item = st.text_input("Building Material Description (e.g., Cement Bags):")
            price = st.text_input("Price tag per unit:")
            qty = st.text_input("In-Stock Volume:")
            loc = st.text_input("Supply Base Town/City:")
            phone = st.text_input("Sales Desk Mobile Phone:")
            submit_mat = st.form_submit_button("Publish Store Inventory")
            
        if submit_mat:
            if sup_name and item and price and loc and phone:
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("INSERT INTO materials (supplier_name, item_name, price, quantity, location, phone) VALUES (%s, %s, %s, %s, %s, %s)", 
                          (sup_name, item, price, qty, loc, phone))
                conn.commit()
                c.close()
                conn.close()
                st.success("Item inventory listed successfully!")
            else:
                st.error("Missing mandatory fields: Supplier, Item, Price, Location, and Phone.")


# --- PAGE 5: ADMIN PANEL ---
elif page == "Admin Panel":
    st.write("### 🛡️ Platform Moderation Panel")
    pwd = st.text_input("Enter System Master Passcode to access listing logs:", type="password")
    
    if pwd and pwd == get_admin_passcode():
        st.success("Authorized Access Granted.")
        conn = get_db_connection()
        c = conn.cursor(cursor_factory=DictCursor)
        
        st.write("#### 👷 Registered Contractors Listing Management")
        c.execute("SELECT id, name, profession, location FROM contractors")
        cons_list = c.fetchall()
        for con_row in cons_list:
            col_txt, col_del = st.columns([4, 1])  #  Fixed Explicit Weights
            #col_txt, col_del = st.columns()
            col_txt.write(f"ID: {con_row['id']} | {con_row['name']} ({con_row['profession']}) - {con_row['location']}")
            if col_del.button("🗑️ Delete Contractor", key=f"del_c_{con_row['id']}"):
                sub_conn = get_db_connection()
                sub_c = sub_conn.cursor()
                sub_c.execute("DELETE FROM contractors WHERE id = %s", (con_row['id'],))
                sub_conn.commit()
                sub_c.close()
                sub_conn.close()
                st.warning(f"Profile {con_row['name']} removed.")
                st.rerun()
                
        st.write("#### 🧱 Active Supply Catalog Management")
        c.execute("SELECT id, supplier_name, item_name, location FROM materials")
        mats_list = c.fetchall()
        for mat_row in mats_list:
            col_m_txt, col_m_del = st.columns([4, 1])  #  Fixed Explicit Weights
            #col_m_txt, col_m_del = st.columns()
            col_m_txt.write(f"ID: {mat_row['id']} | {mat_row['item_name']} by {mat_row['supplier_name']} ({mat_row['location']})")
            if col_m_del.button("🗑️ Remove Listing", key=f"del_m_{mat_row['id']}"):
                sub_conn = get_db_connection()
                sub_c = sub_conn.cursor()
                sub_c.execute("DELETE FROM materials WHERE id = %s", (mat_row['id'],))
                sub_conn.commit()
                sub_c.close()
                sub_conn.close()
                st.warning("Material listing purged.")
                st.rerun()
                
        c.close()
        conn.close()
    elif pwd != "":
        st.error("Incorrect administrative credentials. Access denied.")