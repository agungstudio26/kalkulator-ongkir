import streamlit as st
from supabase import create_client
import pandas as pd

# --- VERSI APLIKASI ---
APP_VERSION = "v4.1 (Cascading Dropdown)"

st.set_page_config(page_title="Kalkulator Ship Cost GEM", page_icon="🚛", layout="wide")

# --- CUSTOM CSS ---
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
        # Ambil Zones
        zones = supabase.table('master_shipping_zones').select("*").execute()
        df_zones = pd.DataFrame(zones.data)
        
        # Ambil Rates Barang
        rates = supabase.table('master_shipping_rates').select("*").order('id').execute()
        df_rates = pd.DataFrame(rates.data)
        
        return df_zones, df_rates
    except Exception as e:
        st.error(f"Gagal memuat data master: {e}")
        return pd.DataFrame(), pd.DataFrame()

# --- UI UTAMA ---
st.title("🚛 Kalkulator - Biaya Kirim GEM")
st.caption(f"System Version: {APP_VERSION} | Logic Reference: Kalkulator Ship Cost 10 Oct 2025.xlsx")

if supabase:
    df_zones, df_rates = get_master_data()

    if not df_zones.empty and not df_rates.empty:
        
        # === BAGIAN 1: KONFIGURASI PENGIRIMAN ===
        with st.container():
            col1, col2, col3 = st.columns([1.5, 1.5, 1])
            
            # --- KOLOM 1: TOKO ---
            with col1:
                st.subheader("1. Toko Pengirim")
                store_config = {
                    "Kopo": {"col_dist": "dist_kopo", "col_min": "min_kopo", "free_km": 7.0, "label": "Blibli Elektronik - Kopo Bandung"},
                    "Banjaran": {"col_dist": "dist_banjaran", "col_min": "min_banjaran", "free_km": 7.0, "label": "Blibli Elektronik - Banjaran Bandung"},
                    "Bekasi": {"col_dist": "dist_kalimalang", "col_min": "min_kalimalang", "free_km": 10.0, "label": "Dekoruma Elektronik - Kalimalang Bekasi"}
                }
                
                selected_store_code = st.selectbox(
                    "Pilih Asal Toko:", 
                    options=list(store_config.keys()),
                    format_func=lambda x: store_config[x]["label"]
                )
                
                current_store = store_config[selected_store_code]
                st.info(f"ℹ️ Gratis Ongkir: **{current_store['free_km']} KM** pertama.")

            # --- KOLOM 2: ALAMAT (CASCADING FILTER) ---
            with col2:
                st.subheader("2. Alamat Tujuan")
                
                # A. PILIH KOTA (Unique Values)
                # Sortir nama kota agar A-Z
                if 'city' in df_zones.columns:
                    cities = sorted(df_zones['city'].dropna().unique())
                    selected_city = st.selectbox("Pilih Kota / Kabupaten:", cities)
                else:
                    st.error("Kolom 'city' tidak ditemukan di database.")
                    selected_city = None

                # B. FILTER KODE POS BERDASARKAN KOTA
                if selected_city:
                    # Filter dataframe hanya untuk kota yang dipilih
                    filtered_zones = df_zones[df_zones['city'] == selected_city].copy()
                    
                    # Urutkan Kode Pos
                    filtered_zones = filtered_zones.sort_values('postal_code')
                    
                    # Handle jika jarak kosong (NaN) ganti jadi 0
                    dist_col = current_store['col_dist']
                    filtered_zones[dist_col] = filtered_zones[dist_col].fillna(0)
                    
                    # Format Label Dropdown: "40229 (Jarak: 5.2 km)"
                    zone_options = filtered_zones.apply(
                        lambda x: f"{x['postal_code']} (Jarak: {x[dist_col]} km)", axis=1
                    ).tolist()
                    
                    if not zone_options:
                        st.warning(f"Tidak ada data kode pos untuk {selected_city}")
                        selected_zip_label = None
                    else:
                        selected_zip_label = st.selectbox("Pilih Kode Pos:", zone_options)
                else:
                    selected_zip_label = None

            # --- KOLOM 3: LAYANAN ---
            with col3:
                st.subheader("3. Layanan")
                st.selectbox("Tipe Pengiriman:", ["Regular Delivery", "Next Day", "Trade In"])

        # === DATA PROCESSING ===
        if selected_zip_label and selected_city:
            # Ambil kembali data detail berdasarkan Kode Pos yang dipilih
            # Kita split label "40229 (Jarak...)" untuk dapat kode pos murni
            selected_zip_code = selected_zip_label.split(" (")[0]
            
            # Ambil baris data yang cocok (Kota + Kode Pos)
            # Menggunakan .loc untuk keamanan
            zone_match = filtered_zones[filtered_zones['postal_code'] == selected_zip_code]
            
            if not zone_match.empty:
                zone_data = zone_match.iloc[0]
                jarak_real = float(zone_data[current_store['col_dist']])
                
                # Ambil Min Charge
                min_col = current_store['col_min']
                min_charge_val = float(zone_data[min_col]) if min_col in zone_data and pd.notna(zone_data[min_col]) else 0
            else:
                jarak_real = 0
                min_charge_val = 0
        else:
            jarak_real = 0
            min_charge_val = 0

        st.divider()

        # === BAGIAN 2: INPUT BARANG (TABLE EDITOR) ===
        col_input, col_result = st.columns([2, 1.2])

        with col_input:
            st.subheader("4. Input QTY Barang")
            
            # Setup struktur tabel input
            if 'edited_df' not in st.session_state:
                df_input = df_rates[['kategori_produk', 'bobot_kategori']].copy()
                df_input['QTY'] = 0
                df_input['Estimasi Rate'] = df_rates['tarif_per_km']
            else:
                df_input = df_rates[['kategori_produk', 'bobot_kategori']].copy()
                df_input['QTY'] = 0 
                df_input['Estimasi Rate'] = df_rates['tarif_per_km']

            edited_df = st.data_editor(
                df_input,
                column_config={
                    "kategori_produk": "Nama Barang",
                    "bobot_kategori": "Tipe",
                    "Estimasi Rate": st.column_config.NumberColumn("Rate/KM", format="Rp %d"),
                    "QTY": st.column_config.NumberColumn("QTY", min_value=0, max_value=100, step=1)
                },
                disabled=["kategori_produk", "bobot_kategori", "Estimasi Rate"],
                hide_index=True,
                use_container_width=True,
                height=400
            )

        # === BAGIAN 3: LOGIC HITUNG EXCEL ===
        with col_result:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.subheader("📝 Rincian Biaya")
            
            items_selected = edited_df[edited_df['QTY'] > 0]
            has_items = not items_selected.empty
            
            final_ongkir = 0
            logic_note = "-"
            calculation_detail = ""

            if has_items:
                merged = pd.merge(items_selected, df_rates, on='kategori_produk', how='left')
                max_rate = merged['tarif_per_km_y'].max()
                
                free_limit = current_store['free_km']
                
                # LOGIKA UTAMA
                if jarak_real <= free_limit:
                    final_ongkir = 0
                    logic_note = f"✅ FREE (Radius < {free_limit} KM)"
                    calculation_detail = f"Jarak {jarak_real} KM masih di bawah batas gratis."
                else:
                    jarak_bayar = jarak_real - free_limit
                    biaya_km = jarak_bayar * max_rate
                    
                    if min_charge_val > 0:
                        if min_charge_val > biaya_km:
                            final_ongkir = min_charge_val
                            logic_note = "📦 MINIMUM CHARGE ZONA"
                            calculation_detail = f"Biaya KM (Rp {biaya_km:,.0f}) < Min. Charge (Rp {min_charge_val:,.0f})."
                        else:
                            final_ongkir = biaya_km
                            logic_note = "🛣️ CHARGE BY KM"
                            calculation_detail = f"Lebih {jarak_bayar:.1f} KM x Rate Rp {max_rate:,.0f}"
                    else:
                        final_ongkir = biaya_km
                        logic_note = "🛣️ CHARGE BY KM"
                        calculation_detail = f"Lebih {jarak_bayar:.1f} KM x Rate Rp {max_rate:,.0f}"

            # TAMPILAN HASIL
            col_a, col_b = st.columns(2)
            col_a.metric("Jarak Tempuh", f"{jarak_real} KM")
            col_b.metric("Min. Charge DB", f"Rp {min_charge_val:,.0f}")
            
            st.divider()
            
            if has_items:
                st.markdown(f"**Metode:** <span class='status-badge'>{logic_note}</span>", unsafe_allow_html=True)
                st.caption(calculation_detail)
                
                st.markdown("### TOTAL BAYAR")
                if final_ongkir == 0:
                    st.markdown('<div class="big-total">GRATIS (Rp 0)</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="big-total">Rp {final_ongkir:,.0f}</div>', unsafe_allow_html=True)
            else:
                st.warning("⚠️ Silakan isi QTY barang.")
            
            st.markdown('</div>', unsafe_allow_html=True)

    else:
        st.error("Data kosong. Pastikan script SQL sudah dijalankan dan CSV diimport.")
else:
    st.error("Database Error.")
