import streamlit as st
from supabase import create_client
import pandas as pd
import io

# --- VERSI APLIKASI ---
APP_VERSION = "v7.0 (Fitur Download Template)"

st.set_page_config(page_title="Kalkulator Ship Cost GEM", page_icon="🚛", layout="wide")

# --- CSS STYLING ---
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 20px;
    }
    .big-total {
        font-size: 32px;
        font-weight: 800;
        color: #198754;
        margin-top: 10px;
    }
    .status-badge {
        background-color: #e9ecef;
        padding: 5px 10px;
        border-radius: 4px;
        font-weight: bold;
        font-size: 14px;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNGSI GENERATE TEMPLATE ---
def get_template_csv():
    # Membuat Dataframe Kosong dengan Header yang Benar
    data = {
        'Province': ['Jawa Barat', 'Jawa Barat (Contoh)'],
        'City': ['Kab. Bandung', 'Kota Bekasi (Contoh)'],
        'Postal Code': ['40377', '17145'],
        'dist_banjaran': [3.5, 0],
        'dist_kopo': [15.0, 0],
        'dist_bekasi': [0, 1.8],
        'min_banjaran': [0, 0],
        'min_kopo': [50000, 0],
        'min_bekasi': [0, 0]
    }
    df = pd.DataFrame(data)
    return df.to_csv(index=False).encode('utf-8')

# --- SIDEBAR: ADMIN TOOLS ---
with st.sidebar:
    st.title("⚙️ Admin Tools")
    st.write(f"Versi: {APP_VERSION}")
    
    st.markdown("### 1. Download Template")
    st.caption("Download file ini, buka di Excel, isi data, lalu upload ke Supabase.")
    
    csv_file = get_template_csv()
    st.download_button(
        label="📥 Download Template CSV",
        data=csv_file,
        file_name="Template_Master_Ongkir_GEM.csv",
        mime="text/csv",
    )
    
    st.markdown("### 2. Reset Aplikasi")
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
        zones = supabase.table('master_shipping_zones').select("*").execute()
        df_zones = pd.DataFrame(zones.data)
        
        if not df_zones.empty:
            df_zones.columns = df_zones.columns.str.lower().str.strip()

        rates = supabase.table('master_shipping_rates').select("*").order('id').execute()
        df_rates = pd.DataFrame(rates.data)
        
        return df_zones, df_rates
    except Exception as e:
        st.error(f"Gagal memuat data: {e}")
        return pd.DataFrame(), pd.DataFrame()

# --- UI UTAMA ---
st.title("🚛 Kalkulator - Biaya Kirim GEM")

if supabase:
    df_zones, df_rates = get_master_data()

    # --- DEBUG VIEW ---
    with st.expander("🔍 Cek Data Database (Debug)"):
        if df_zones.empty:
            st.warning("Data Kosong. Silakan download template di sidebar, isi, dan upload ke Supabase.")
        else:
            st.write("5 Data Teratas:")
            st.dataframe(df_zones.head())

    if not df_zones.empty and not df_rates.empty:
        
        with st.container():
            col1, col2, col3 = st.columns([1.5, 1.5, 1])
            
            # 1. TOKO
            with col1:
                st.subheader("1. Toko Pengirim")
                store_config = {
                    "Banjaran": {"label": "Blibli Elektronik - Banjaran", "col_dist": "dist_banjaran", "col_min": "min_banjaran", "free_km": 7.0},
                    "Kopo": {"label": "Blibli Elektronik - Kopo", "col_dist": "dist_kopo", "col_min": "min_kopo", "free_km": 7.0},
                    "Bekasi": {"label": "Dekoruma - Kalimalang", "col_dist": "dist_bekasi", "col_min": "min_bekasi", "free_km": 10.0}
                }
                
                selected_store_key = st.selectbox(
                    "Pilih Asal Toko:", 
                    options=list(store_config.keys()),
                    format_func=lambda x: store_config[x]["label"],
                    index=0
                )
                current_store = store_config[selected_store_key]
                st.info(f"ℹ️ Gratis Ongkir: **{current_store['free_km']} KM** pertama.")

            # 2. ALAMAT
            with col2:
                st.subheader("2. Alamat Tujuan")
                
                # Filter Jabar
                if 'province' in df_zones.columns:
                    df_jabar = df_zones[df_zones['province'].astype(str).str.contains('jawa barat', case=False, na=False)]
                    df_target = df_jabar if not df_jabar.empty else df_zones
                else:
                    df_target = df_zones

                cities = sorted(df_target['city'].dropna().unique())
                selected_city = st.selectbox("Pilih Kota / Kabupaten:", cities)

                selected_zip_label = None
                if selected_city:
                    city_data = df_target[df_target['city'] == selected_city].copy()
                    dist_col = current_store['col_dist']
                    
                    if dist_col in city_data.columns:
                        city_data[dist_col] = city_data[dist_col].fillna(0)
                        city_data = city_data.sort_values('postal_code')
                        
                        zone_options = city_data.apply(
                            lambda x: f"{x['postal_code']} (Jarak: {float(x[dist_col]):.2f} km)", axis=1
                        ).tolist()
                        selected_zip_label = st.selectbox("Pilih Kode Pos:", zone_options)
                    else:
                        st.error(f"Kolom '{dist_col}' hilang. Gunakan template admin.")

            # 3. LAYANAN
            with col3:
                st.subheader("3. Layanan")
                st.selectbox("Tipe Pengiriman:", ["Nextday Delivery", "Trade In Delivery", "Lite Install Delivery"])

        # PROCESS
        jarak_real = 0
        min_charge_val = 0
        if selected_zip_label and selected_city:
            zip_code = selected_zip_label.split(" (")[0]
            match = df_target[(df_target['city'] == selected_city) & (df_target['postal_code'] == zip_code)]
            
            if not match.empty:
                row = match.iloc[0]
                jarak_real = float(row[current_store['col_dist']])
                min_col = current_store['col_min']
                if min_col in row and pd.notna(row[min_col]):
                    min_charge_val = float(row[min_col])

        st.divider()

        # 4. INPUT BARANG
        col_input, col_result = st.columns([2, 1.2])
        with col_input:
            st.subheader("4. Input QTY Barang")
            if 'edited_df' not in st.session_state:
                df_input = df_rates[['kategori_produk', 'bobot_kategori']].copy()
                df_input['QTY'] = 0
                df_input['Rate/KM'] = df_rates['tarif_per_km']
            else:
                df_input = df_rates[['kategori_produk', 'bobot_kategori']].copy()
                df_input['QTY'] = 0 
                df_input['Rate/KM'] = df_rates['tarif_per_km']

            edited_df = st.data_editor(
                df_input,
                column_config={
                    "kategori_produk": "Item",
                    "bobot_kategori": "Tipe",
                    "Rate/KM": st.column_config.NumberColumn("Rate/KM", format="Rp %d"),
                    "QTY": st.column_config.NumberColumn("Jml", min_value=0, max_value=100, step=1)
                },
                disabled=["kategori_produk", "bobot_kategori", "Rate/KM"],
                hide_index=True,
                use_container_width=True
            )

        # 5. HASIL
        with col_result:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.subheader("📝 Rincian Biaya")
            
            items_selected = edited_df[edited_df['QTY'] > 0]
            final_ongkir = 0
            note = "-"
            detail = ""

            if not items_selected.empty:
                merged = pd.merge(items_selected, df_rates, on='kategori_produk', how='left')
                max_rate = merged['tarif_per_km_y'].max()
                free_limit = current_store['free_km']
                
                if jarak_real <= free_limit:
                    final_ongkir = 0
                    note = f"✅ FREE (< {free_limit} KM)"
                    detail = f"Jarak {jarak_real} KM masuk gratis ongkir."
                else:
                    jarak_bayar = jarak_real - free_limit
                    biaya_km = jarak_bayar * max_rate
                    
                    if min_charge_val > 0 and min_charge_val > biaya_km:
                        final_ongkir = min_charge_val
                        note = "📦 MINIMUM CHARGE"
                        detail = f"Menggunakan standar minimum zona."
                    else:
                        final_ongkir = biaya_km
                        note = "🛣️ CHARGE PER-KM"
                        detail = f"Lebih {jarak_bayar:.1f} KM x Rate Rp {max_rate:,.0f}"

            c1, c2 = st.columns(2)
            c1.metric("Jarak", f"{jarak_real} KM")
            c2.metric("Min. Charge", f"Rp {min_charge_val:,.0f}")
            
            st.divider()
            
            if not items_selected.empty:
                st.markdown(f"**Metode:** <span class='status-badge'>{note}</span>", unsafe_allow_html=True)
                st.caption(detail)
                
                st.markdown("### TOTAL")
                if final_ongkir == 0:
                    st.markdown('<div class="big-total">GRATIS (Rp 0)</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="big-total">Rp {final_ongkir:,.0f}</div>', unsafe_allow_html=True)
            else:
                st.warning("Isi QTY barang dulu.")
            st.markdown('</div>', unsafe_allow_html=True)
            
    else:
        st.warning("Database Kosong. Silakan download template di Sidebar.")
else:
    st.error("Database Error.")
