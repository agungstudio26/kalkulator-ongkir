import streamlit as st
from supabase import create_client
import pandas as pd

# --- VERSI APLIKASI ---
APP_VERSION = "v4.0 (Logic Hybrid Excel)"

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
        zones = supabase.table('master_shipping_zones').select("*").execute()
        df_zones = pd.DataFrame(zones.data)
        
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
            
            with col1:
                st.subheader("1. Toko Pengirim")
                # Mapping Toko ke Kolom DB & Aturan Radius
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
                
                # Ambil konfigurasi toko terpilih
                current_store = store_config[selected_store_code]
                st.info(f"ℹ️ Toko ini Gratis Ongkir **{current_store['free_km']} KM** pertama.")

            with col2:
                st.subheader("2. Alamat Tujuan")
                cities = sorted(df_zones['city'].unique())
                selected_city = st.selectbox("Kota / Kabupaten:", cities)

                # Filter Kode Pos
                filtered_zones = df_zones[df_zones['city'] == selected_city]
                
                # Format Dropdown: "KodePos (Jarak KM)"
                # Handle null/NaN dengan 0
                dist_col = current_store['col_dist']
                filtered_zones[dist_col] = filtered_zones[dist_col].fillna(0)
                
                zone_options = filtered_zones.apply(
                    lambda x: f"{x['postal_code']} (Jarak: {x[dist_col]} km)", axis=1
                ).tolist()
                
                selected_zip_label = st.selectbox("Kode Pos:", zone_options)

            with col3:
                st.subheader("3. Layanan")
                st.selectbox("Tipe Pengiriman:", ["Regular Delivery", "Next Day", "Trade In"])

        # === DATA PROCESSING ===
        if selected_zip_label:
            selected_zip = selected_zip_label.split(" (")[0]
            zone_data = filtered_zones[filtered_zones['postal_code'] == selected_zip].iloc[0]
            
            jarak_real = float(zone_data[current_store['col_dist']])
            
            # Ambil Min Charge (Handle jika kolom null)
            min_col = current_store['col_min']
            min_charge_val = float(zone_data[min_col]) if min_col in zone_data and pd.notna(zone_data[min_col]) else 0
        else:
            jarak_real = 0
            min_charge_val = 0

        st.divider()

        # === BAGIAN 2: INPUT BARANG (TABLE EDITOR) ===
        col_input, col_result = st.columns([2, 1.2])

        with col_input:
            st.subheader("4. Input QTY Barang")
            
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
                    "kategori_produk": "Item Name",
                    "bobot_kategori": "Type",
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
            
            # 1. Cek Barang Terpilih
            items_selected = edited_df[edited_df['QTY'] > 0]
            has_items = not items_selected.empty
            
            final_ongkir = 0
            logic_note = "-"
            calculation_detail = ""

            if has_items:
                # Ambil Rate Tertinggi (Max Vehicle Logic)
                # Join balik ke master untuk memastikan data akurat
                merged = pd.merge(items_selected, df_rates, on='kategori_produk', how='left')
                max_rate = merged['tarif_per_km_y'].max() # tarif_per_km_y dari master
                
                free_limit = current_store['free_km']
                
                # LOGIKA UTAMA (Sesuai Excel)
                if jarak_real <= free_limit:
                    # KONDISI 1: DALAM RADIUS GRATIS
                    final_ongkir = 0
                    logic_note = f"✅ FREE (Radius < {free_limit} KM)"
                    calculation_detail = f"Jarak {jarak_real} KM masih di bawah batas gratis."
                else:
                    # KONDISI 2: DI LUAR RADIUS
                    jarak_bayar = jarak_real - free_limit
                    biaya_km = jarak_bayar * max_rate
                    
                    # Cek Minimum Charge Database
                    if min_charge_val > 0:
                        # Logic: Ambil yang TERBESAR (Max of Calculated vs MinCharge)
                        # Agar mengcover biaya operasional zona jauh
                        if min_charge_val > biaya_km:
                            final_ongkir = min_charge_val
                            logic_note = "📦 MINIMUM CHARGE ZONA"
                            calculation_detail = f"Biaya hitung KM (Rp {biaya_km:,.0f}) lebih kecil dari Min. Charge Zona (Rp {min_charge_val:,.0f})."
                        else:
                            final_ongkir = biaya_km
                            logic_note = "🛣️ CHARGE BY KM"
                            calculation_detail = f"Lebih {jarak_bayar:.1f} KM x Rate Rp {max_rate:,.0f}"
                    else:
                        # Jika tidak ada data min charge, pakai hitungan KM murni
                        final_ongkir = biaya_km
                        logic_note = "🛣️ CHARGE BY KM"
                        calculation_detail = f"Lebih {jarak_bayar:.1f} KM x Rate Rp {max_rate:,.0f}"

            # UI DISPLAY HASIL
            col_a, col_b = st.columns(2)
            col_a.metric("Jarak Tempuh", f"{jarak_real} KM")
            col_a.caption(f"Batas Gratis: {current_store['free_km']} KM")
            
            col_b.metric("Min. Charge DB", f"Rp {min_charge_val:,.0f}")
            col_b.caption("Data Excel ShipTable")
            
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
                st.warning("⚠️ Silakan isi QTY barang di tabel sebelah kiri.")
            
            st.markdown('</div>', unsafe_allow_html=True)

    else:
        st.error("Database kosong. Mohon jalankan script SQL yang baru.")
else:
    st.error("Gagal koneksi database.")
