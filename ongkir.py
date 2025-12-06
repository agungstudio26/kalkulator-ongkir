import streamlit as st
from supabase import create_client
import pandas as pd
import io

# --- VERSI APLIKASI ---
APP_VERSION = "v8.0 (Service & Item Handling Fee)"

st.set_page_config(page_title="Kalkulator Ship Cost GEM", page_icon="🚛", layout="wide")

# --- CSS STYLING ---
st.markdown("""
<style>
    .metric-card {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .big-total {
        font-size: 36px;
        font-weight: 800;
        color: #198754;
        margin-top: 5px;
    }
    .cost-row {
        display: flex;
        justify-content: space-between;
        margin-bottom: 8px;
        font-size: 15px;
    }
    .cost-row.total {
        border-top: 1px dashed #ccc;
        padding-top: 10px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNGSI GENERATE TEMPLATE EXCEL (MULTI SHEET) ---
def get_template_excel():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # SHEET 1: ZONA (Ongkir Jarak)
        df_zones = pd.DataFrame({
            'province': ['Jawa Barat'], 'city': ['Kab. Bandung'], 'postal_code': ['40377'],
            'dist_banjaran': [3.5], 'dist_kopo': [15.0], 'dist_bekasi': [0],
            'min_banjaran': [0], 'min_kopo': [50000], 'min_bekasi': [0]
        })
        df_zones.to_excel(writer, index=False, sheet_name='Zones')
        
        # SHEET 2: BARANG (Handling Fee)
        df_rates = pd.DataFrame({
            'kategori_produk': ['Kulkas Side by Side', 'TV 43 Inch'],
            'bobot_kategori': ['Big', 'Medium'],
            'tarif_per_km': [15000, 10000],
            'handling_fee': [50000, 0] # Biaya tambahan per unit
        })
        df_rates.to_excel(writer, index=False, sheet_name='Products')

        # SHEET 3: LAYANAN (Service Fee)
        df_services = pd.DataFrame({
            'service_name': ['Nextday Delivery', 'Lite Install', 'Trade In'],
            'service_fee': [0, 50000, 25000]
        })
        df_services.to_excel(writer, index=False, sheet_name='Services')
        
    return output.getvalue()

# --- SIDEBAR TOOLS ---
with st.sidebar:
    st.title("⚙️ Admin Tools")
    st.caption(f"Ver: {APP_VERSION}")
    
    # Download Template
    excel_file = get_template_excel()
    st.download_button(
        label="📥 Download Template Full (.xlsx)",
        data=excel_file,
        file_name="Template_Master_Ongkir_v8.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        help="Berisi 3 Sheet: Zones, Products, Services"
    )
    st.caption("Gunakan template ini untuk mengisi ulang database jika perlu.")
    
    if st.button("🔄 Refresh Data Cache"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

# --- KONEKSI DATABASE ---
@st.cache_resource
def init_connection():
    try:
        if "supabase" not in st.secrets:
            st.error("Secrets belum disetting.")
            st.stop()
        url = st.secrets["supabase"]["url"].strip()
        key = st.secrets["supabase"]["key"].strip()
        return create_client(url, key)
    except Exception as e:
        st.error(f"Koneksi Gagal: {e}")
        return None

supabase = init_connection()

# --- LOAD DATA ---
@st.cache_data(ttl=600)
def get_master_data():
    try:
        # 1. Zones
        zones = supabase.table('master_shipping_zones').select("*").execute()
        df_zones = pd.DataFrame(zones.data)
        if not df_zones.empty: df_zones.columns = df_zones.columns.str.lower().str.strip()

        # 2. Rates (Barang)
        rates = supabase.table('master_shipping_rates').select("*").order('id').execute()
        df_rates = pd.DataFrame(rates.data)

        # 3. Services (Layanan)
        services = supabase.table('master_services').select("*").order('id').execute()
        df_services = pd.DataFrame(services.data)
        
        return df_zones, df_rates, df_services
    except Exception as e:
        st.error(f"Gagal memuat data: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# --- UI UTAMA ---
st.title("🚛 Kalkulator - Biaya Kirim GEM")

if supabase:
    df_zones, df_rates, df_services = get_master_data()

    if not df_zones.empty:
        
        # === FORM INPUT ===
        with st.container():
            c1, c2, c3 = st.columns([1.2, 1.2, 1])
            
            # 1. TOKO
            with c1:
                st.subheader("1. Asal Toko")
                store_config = {
                    "Banjaran": {"label": "Blibli - Banjaran", "col_dist": "dist_banjaran", "col_min": "min_banjaran", "free_km": 7.0},
                    "Kopo": {"label": "Blibli - Kopo", "col_dist": "dist_kopo", "col_min": "min_kopo", "free_km": 7.0},
                    "Bekasi": {"label": "Dekoruma - Bekasi", "col_dist": "dist_bekasi", "col_min": "min_bekasi", "free_km": 10.0}
                }
                store_key = st.selectbox("Pilih Toko:", list(store_config.keys()), format_func=lambda x: store_config[x]["label"], index=0)
                curr_store = store_config[store_key]
                st.caption(f"Free Radius: {curr_store['free_km']} KM")

            # 2. ALAMAT
            with c2:
                st.subheader("2. Tujuan")
                # Filter Provinsi Jabar (Optional logic)
                df_target = df_zones
                if 'province' in df_zones.columns:
                     df_jabar = df_zones[df_zones['province'].astype(str).str.contains('jawa barat', case=False, na=False)]
                     if not df_jabar.empty: df_target = df_jabar

                cities = sorted(df_target['city'].dropna().unique())
                city = st.selectbox("Kota/Kab:", cities)

                zip_label = None
                if city:
                    city_df = df_target[df_target['city'] == city].copy()
                    dist_col = curr_store['col_dist']
                    if dist_col in city_df.columns:
                        city_df[dist_col] = city_df[dist_col].fillna(0)
                        city_df = city_df.sort_values('postal_code')
                        opts = city_df.apply(lambda x: f"{x['postal_code']} ({float(x[dist_col]):.1f} km)", axis=1).tolist()
                        zip_label = st.selectbox("Kode Pos:", opts)

            # 3. LAYANAN (DARI DATABASE)
            with c3:
                st.subheader("3. Layanan")
                # Dropdown ambil dari tabel master_services
                if not df_services.empty:
                    service_opts = df_services['service_name'].tolist()
                    selected_service_name = st.selectbox("Tipe:", service_opts)
                    
                    # Ambil Biaya Layanan
                    service_row = df_services[df_services['service_name'] == selected_service_name].iloc[0]
                    service_fee = float(service_row['service_fee'])
                else:
                    st.warning("Data layanan kosong")
                    service_fee = 0

        st.divider()

        # === INPUT BARANG ===
        c_input, c_result = st.columns([1.8, 1.2])
        
        with c_input:
            st.subheader("4. Barang")
            if 'df_cart' not in st.session_state:
                # Prepare input DF
                d = df_rates[['kategori_produk', 'bobot_kategori', 'tarif_per_km', 'handling_fee']].copy()
                d['QTY'] = 0
                st.session_state['df_cart'] = d
            
            # Reset logic basic
            df_input = st.session_state['df_cart']

            edited_df = st.data_editor(
                df_input,
                column_config={
                    "kategori_produk": "Item",
                    "bobot_kategori": "Type",
                    "tarif_per_km": st.column_config.NumberColumn("Rate/KM", format="Rp %d"),
                    "handling_fee": st.column_config.NumberColumn("Extra Fee/Unit", format="Rp %d", help="Biaya angkut/pasang per barang"),
                    "QTY": st.column_config.NumberColumn("Jml", min_value=0, max_value=50, step=1)
                },
                disabled=["kategori_produk", "bobot_kategori", "tarif_per_km", "handling_fee"],
                hide_index=True,
                use_container_width=True
            )

        # === KALKULASI TOTAL ===
        with c_result:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.subheader("🧾 Rincian Biaya")

            # 1. Parsing Jarak
            jarak_real = 0
            min_charge = 0
            if zip_label and city:
                code = zip_label.split(" (")[0]
                row = df_target[(df_target['city']==city) & (df_target['postal_code']==code)].iloc[0]
                jarak_real = float(row[curr_store['col_dist']])
                if pd.notna(row[curr_store['col_min']]):
                    min_charge = float(row[curr_store['col_min']])

            # 2. Hitung Item
            cart = edited_df[edited_df['QTY'] > 0]
            
            ongkir_jarak = 0
            total_handling = 0
            ongkir_final = 0
            
            if not cart.empty:
                # A. Ongkir Jarak (Ambil Rate Tertinggi)
                max_rate = cart['tarif_per_km'].max()
                
                if jarak_real <= curr_store['free_km']:
                    ongkir_jarak = 0
                    note_jarak = "Gratis (Radius)"
                else:
                    dist_pay = jarak_real - curr_store['free_km']
                    ongkir_jarak = dist_pay * max_rate
                    # Cek Min Charge
                    if min_charge > 0 and min_charge > ongkir_jarak:
                        ongkir_jarak = min_charge
                        note_jarak = "Min. Charge Zone"
                    else:
                        note_jarak = f"{dist_pay:.1f} KM x Rate"

                # B. Handling Fee Barang (Total QTY * Fee per Item)
                # Rumus: Sum(QTY * handling_fee)
                cart['subtotal_handling'] = cart['QTY'] * cart['handling_fee']
                total_handling = cart['subtotal_handling'].sum()
                
                # C. Total Final
                ongkir_final = ongkir_jarak + service_fee + total_handling

                # --- DISPLAY ---
                st.markdown(f"""
                <div class="cost-row">
                    <span>Jarak ({jarak_real} km)</span>
                    <span>Rp {ongkir_jarak:,.0f}</span>
                </div>
                <div style="font-size:12px; color:grey; margin-top:-5px; margin-bottom:10px;">Metode: {note_jarak}</div>
                
                <div class="cost-row">
                    <span>Biaya Layanan ({selected_service_name})</span>
                    <span>Rp {service_fee:,.0f}</span>
                </div>
                
                <div class="cost-row">
                    <span>Extra Handling Barang</span>
                    <span>Rp {total_handling:,.0f}</span>
                </div>
                """, unsafe_allow_html=True)
                
                st.divider()
                
                st.markdown(f"""
                <div class="cost-row total">
                    <span>TOTAL ESTIMASI</span>
                </div>
                <div class="big-total">Rp {ongkir_final:,.0f}</div>
                """, unsafe_allow_html=True)

            else:
                st.info("👈 Masukkan jumlah barang di tabel samping.")
                st.markdown(f"""
                <div class="cost-row">
                    <span>Jarak Tempuh</span>
                    <span>{jarak_real} KM</span>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown('</div>', unsafe_allow_html=True)

    else:
        st.warning("Database Kosong. Silakan Import Template.")
else:
    st.error("Gagal Koneksi DB")
