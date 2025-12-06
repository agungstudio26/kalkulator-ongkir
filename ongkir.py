import streamlit as st
from supabase import create_client
import pandas as pd

# --- VERSI APLIKASI ---
APP_VERSION = "v3.0 (Excel Dashboard UI)"

st.set_page_config(page_title="Kalkulator Ship Cost GEM", page_icon="🚛", layout="wide")

# --- CUSTOM CSS (Agar mirip Excel) ---
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        border: 1px solid #d1d5db;
    }
    .big-total {
        font-size: 28px;
        font-weight: bold;
        color: #0f5132;
    }
    div[data-testid="stMetricValue"] {
        font-size: 18px;
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
st.caption(f"Versi Aplikasi: {APP_VERSION}")

if supabase:
    df_zones, df_rates = get_master_data()

    if not df_zones.empty and not df_rates.empty:
        
        # --- BAGIAN 1: HEADER & CONFIG (TOKO & ALAMAT) ---
        # Mirip bagian atas Excel
        with st.container():
            col_toko, col_alamat, col_tipe = st.columns([1.5, 1.5, 1])
            
            with col_toko:
                st.subheader("1. Toko Pengirim")
                store_map = {
                    "dist_banjaran": "Blibli Elektronik - Banjaran Bandung",
                    "dist_kopo": "Blibli Elektronik - Kopo Bandung",
                    "dist_kalimalang": "Dekoruma Elektronik - Kalimalang Bekasi"
                }
                # Mapping untuk kolom Min Charge
                min_charge_map = {
                    "dist_banjaran": "min_charge_banjaran",
                    "dist_kopo": "min_charge_kopo",
                    "dist_kalimalang": "min_charge_kalimalang"
                }
                
                selected_store_key = st.selectbox(
                    "Pilih Toko Asal:", 
                    options=list(store_map.keys()), 
                    format_func=lambda x: store_map[x]
                )

            with col_alamat:
                st.subheader("2. Alamat Pengiriman")
                # Filter Kota
                cities = sorted(df_zones['city'].unique())
                selected_city = st.selectbox("Kota / Kabupaten:", cities)

                # Filter Kode Pos
                filtered_zones = df_zones[df_zones['city'] == selected_city]
                
                # Handle null distance values with 0
                filtered_zones[selected_store_key] = filtered_zones[selected_store_key].fillna(0)
                
                # Dropdown Kode Pos
                zone_options = filtered_zones.apply(
                    lambda x: f"{x['postal_code']} (Dist: {x[selected_store_key]} km)", axis=1
                ).tolist()
                
                selected_zip_label = st.selectbox("Kode Pos Tujuan:", zone_options)

            with col_tipe:
                st.subheader("3. Tipe Pengiriman")
                # Ini ada di Excel, kita tambahkan sebagai statis dulu atau logic nanti
                st.selectbox("Tipe:", ["Trade In Delivery", "Regular Delivery", "Instant"])

        # --- DATA PROCESSING UNTUK LOGIC ---
        # Ambil detail zona yang dipilih
        if selected_zip_label:
            selected_zip = selected_zip_label.split(" (")[0]
            zone_data = filtered_zones[filtered_zones['postal_code'] == selected_zip].iloc[0]
            
            jarak_real = float(zone_data[selected_store_key])
            col_min_charge = min_charge_map[selected_store_key]
            min_charge_val = float(zone_data[col_min_charge]) if col_min_charge in zone_data else 0
            zone_name = zone_data['zone_name'] if 'zone_name' in zone_data else "-"
        else:
            jarak_real = 0
            min_charge_val = 0
            zone_name = "-"

        st.divider()

        # --- BAGIAN 2: TABEL INPUT BARANG (MENGGANTIKAN MULTISELECT) ---
        col_table, col_summary = st.columns([2, 1])

        with col_table:
            st.subheader("4. Rincian Barang (Isi QTY)")
            
            # Siapkan Dataframe untuk diedit user (Mirip Excel Grid)
            # Kita tambah kolom 'QTY' default 0
            if 'edited_df' not in st.session_state:
                df_input = df_rates[['kategori_produk', 'bobot_kategori']].copy()
                df_input['QTY'] = 0
                df_input['Keterangan'] = df_rates['tarif_per_km'].apply(lambda x: f"Rate: {x:,.0f}/km")
            else:
                df_input = df_rates[['kategori_produk', 'bobot_kategori']].copy()
                df_input['QTY'] = 0 # Reset visual logic handled by editor below
                df_input['Keterangan'] = df_rates['tarif_per_km'].apply(lambda x: f"Rate: {x:,.0f}/km")

            # Tampilkan Tabel Editable
            edited_df = st.data_editor(
                df_input,
                column_config={
                    "kategori_produk": "Kategori Produk",
                    "bobot_kategori": "Bobot",
                    "QTY": st.column_config.NumberColumn("QTY", min_value=0, max_value=100, step=1, format="%d"),
                    "Keterangan": "Info Rate"
                },
                disabled=["kategori_produk", "bobot_kategori", "Keterangan"],
                hide_index=True,
                use_container_width=True,
                key="item_editor"
            )

        # --- LOGIC HITUNG (REALTIME) ---
        # 1. Cek barang apa saja yang QTY > 0
        items_selected_rows = edited_df[edited_df['QTY'] > 0]
        has_items = not items_selected_rows.empty

        final_ongkir = 0
        status_msg = "Menunggu Input Barang..."
        detail_msg = ""
        kendaraan_info = ""

        if has_items:
            # Ambil item dari master rates yang cocok dengan input user
            # Kita perlu join ulang dengan master rate untuk dapat angkanya
            merged_selection = pd.merge(
                items_selected_rows, 
                df_rates, 
                on='kategori_produk', 
                how='left',
                suffixes=('', '_master')
            )
            
            # CARI MAX RATE (Logic Toko: Satu truk ikut harga barang termahal/terbesar)
            max_rate_val = merged_selection['tarif_per_km'].max()
            
            # Hitung Ongkir
            batas_gratis = 7.0
            
            if jarak_real <= batas_gratis:
                final_ongkir = 0
                status_msg = "FREE SHIPPING"
                detail_msg = f"Jarak {jarak_real} KM (Di bawah {batas_gratis} KM)"
            else:
                jarak_bayar = jarak_real - batas_gratis
                biaya_km = jarak_bayar * max_rate_val
                
                # Bandingkan dengan Min Charge Excel
                if min_charge_val > 0 and min_charge_val > biaya_km:
                    final_ongkir = min_charge_val
                    status_msg = "MINIMUM CHARGE ZONE"
                    detail_msg = f"Menggunakan Min. Charge Zona {zone_name}"
                else:
                    final_ongkir = biaya_km
                    status_msg = "DISTANCE CHARGE"
                    detail_msg = f"Lebih {jarak_bayar:.1f} KM x Rp {max_rate_val:,.0f}"

        # --- BAGIAN 3: DASHBOARD HASIL (SEBELAH KANAN) ---
        with col_summary:
            st.markdown('<div class="metric-card">', unsafe_allow_html=True)
            st.subheader("Ringkasan Biaya")
            
            # Baris Info Jarak & Zona
            c1, c2 = st.columns(2)
            c1.metric("Jarak", f"{jarak_real} KM")
            c2.metric("Zona", f"{zone_name}")
            
            st.divider()
            
            # Baris Minimum Charge Info
            st.caption(f"Min. Charge (Excel): Rp {min_charge_val:,.0f}")
            
            if has_items:
                st.write(f"**Status:** {status_msg}")
                st.caption(detail_msg)
            else:
                st.warning("Silakan isi QTY barang.")

            st.divider()
            
            # Total Besar
            st.markdown("### Total Biaya Kirim")
            if final_ongkir == 0 and has_items:
                st.markdown('<p class="big-total" style="color:green;">GRATIS (Rp 0)</p>', unsafe_allow_html=True)
            elif final_ongkir > 0:
                st.markdown(f'<p class="big-total" style="color:orange;">Rp {final_ongkir:,.0f}</p>', unsafe_allow_html=True)
            else:
                st.markdown('<p class="big-total">-</p>', unsafe_allow_html=True)
                
            st.markdown('</div>', unsafe_allow_html=True)

    else:
        st.warning("Database Kosong. Mohon import data CSV.")
else:
    st.error("Gagal koneksi database.")
