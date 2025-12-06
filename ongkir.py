import streamlit as st
from supabase import create_client
import pandas as pd

# --- VERSI APLIKASI ---
APP_VERSION = "v2.0 (Excel Standard)"

st.set_page_config(page_title="Kalkulator Ongkir HO", page_icon="🚛", layout="centered")

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
    """Load semua data referensi sekaligus"""
    try:
        # Ambil Zones
        zones = supabase.table('master_shipping_zones').select("*").execute()
        df_zones = pd.DataFrame(zones.data)
        
        # Ambil Rates Barang
        rates = supabase.table('master_shipping_rates').select("*").execute()
        df_rates = pd.DataFrame(rates.data)
        
        return df_zones, df_rates
    except Exception as e:
        st.error(f"Gagal memuat data master: {e}")
        return pd.DataFrame(), pd.DataFrame()

# --- LOGIKA HITUNG ---
def calculate_shipping(jarak, items_selected, df_rates, min_charge_zone):
    """
    Logika Hybrid: 
    1. Hitung base cost berdasarkan rate kendaraan/barang tertinggi per KM.
    2. Bandingkan dengan Minimum Charge dari Excel (jika ada).
    """
    if not items_selected:
        return 0, "Pilih Barang", 0

    # 1. Cari Rate Tertinggi dari barang yang dipilih
    selected_rates = df_rates[df_rates['kategori_produk'].isin(items_selected)]
    max_rate_row = selected_rates.loc[selected_rates['tarif_per_km'].idxmax()]
    
    tarif_per_km = float(max_rate_row['tarif_per_km'])
    kategori_max = max_rate_row['bobot_kategori']

    # 2. Rumus Jarak (Gratis 7KM pertama)
    jarak_berbayar = max(0, jarak - 7.0)
    biaya_by_km = jarak_berbayar * tarif_per_km

    # 3. Logika Final (Ambil Min Charge Excel jika jarak sangat jauh/luar kota)
    # Asumsi: Jika jarak dekat (<20km), pakai hitungan KM. Jika luar kota, pakai Min Charge Excel.
    # Namun untuk safety, kita ambil nilai MAXIMUM antara hitungan KM vs Min Charge
    # TAPI: Jika jarak < 7km, tetap GRATIS (kecuali ada aturan minimum khusus)
    
    final_ongkir = 0
    metode = ""

    if jarak <= 7:
        final_ongkir = 0
        metode = "✅ Free Shipping (< 7KM)"
    else:
        # Jika Min Charge di database ada isinya (>0), kita jadikan pembanding
        if min_charge_zone > 0:
            if min_charge_zone > biaya_by_km:
                final_ongkir = min_charge_zone
                metode = "📦 Minimum Charge Zona (Excel)"
            else:
                final_ongkir = biaya_by_km
                metode = f"🛣️ Hitungan KM ({jarak_berbayar:.1f} km x {tarif_per_km/1000:.0f}rb)"
        else:
            final_ongkir = biaya_by_km
            metode = f"🛣️ Hitungan KM ({jarak_berbayar:.1f} km x {tarif_per_km/1000:.0f}rb)"

    return final_ongkir, metode, tarif_per_km

# --- UI UTAMA ---
st.header("🚛 Kalkulator Ongkir (Data Pusat)")
st.caption(f"Versi: {APP_VERSION} | Mengacu pada file: Kalkulator Ship Cost 10 Oct 2025")

if supabase:
    df_zones, df_rates = get_master_data()

    if not df_zones.empty:
        # 1. PILIH TOKO PENGIRIM (Sesuai kolom CSV Distance)
        store_map = {
            "dist_banjaran": "Blibli Elektronik - Banjaran",
            "dist_kopo": "Blibli Elektronik - Kopo",
            "dist_kalimalang": "Dekoruma - Bekasi"
        }
        # Mapping kolom min charge juga
        min_charge_map = {
            "dist_banjaran": "min_charge_banjaran",
            "dist_kopo": "min_charge_kopo",
            "dist_kalimalang": "min_charge_kalimalang"
        }

        selected_store_key = st.selectbox(
            "📍 Toko Pengirim:", 
            options=list(store_map.keys()), 
            format_func=lambda x: store_map[x]
        )

        st.divider()

        # 2. PILIH TUJUAN (Filter Kota dulu biar ringan)
        # Ambil daftar kota unik
        cities = sorted(df_zones['city'].unique())
        selected_city = st.selectbox("Kota / Kabupaten:", cities)

        # Filter Kode Pos berdasarkan kota
        filtered_zones = df_zones[df_zones['city'] == selected_city]
        
        # Format tampilan dropdown: "Kode Pos (Jarak KM)"
        # Kita ambil jarak sesuai toko yang dipilih di atas
        
        # Handle jika data jarak null/kosong
        filtered_zones[selected_store_key] = filtered_zones[selected_store_key].fillna(0)
        
        zone_options = filtered_zones.apply(
            lambda x: f"{x['postal_code']} (Jarak: {x[selected_store_key]} KM)", axis=1
        ).tolist()
        
        selected_zip_label = st.selectbox("Kode Pos Tujuan:", zone_options)

        # Ambil data detail zona terpilih
        selected_zip = selected_zip_label.split(" (")[0]
        zone_data = filtered_zones[filtered_zones['postal_code'] == selected_zip].iloc[0]
        
        jarak_real = float(zone_data[selected_store_key])
        # Ambil min charge sesuai toko yang dipilih
        col_min_charge = min_charge_map[selected_store_key]
        min_charge_val = float(zone_data[col_min_charge]) if col_min_charge in zone_data else 0

        st.divider()

        # 3. PILIH BARANG (Sesuai File Kalkulator.csv)
        st.subheader("📦 Barang Kiriman")
        item_list = df_rates['kategori_produk'].tolist()
        
        # Multiselect sederhana
        selected_items = st.multiselect("Pilih Item:", item_list)

        # 4. HASIL PERHITUNGAN
        if selected_items:
            ongkir, metode, rate_used = calculate_shipping(jarak_real, selected_items, df_rates, min_charge_val)
            
            with st.container():
                st.markdown("### 🧾 Estimasi Biaya")
                
                col1, col2 = st.columns(2)
                col1.metric("Jarak Toko", f"{jarak_real} KM")
                col2.metric("Min. Charge DB", f"Rp {min_charge_val:,.0f}")
                
                st.info(f"**Metode Kalkulasi:** {metode}")
                
                st.markdown("---")
                if ongkir == 0:
                    st.success("## TOTAL: GRATIS")
                else:
                    st.warning(f"## TOTAL: Rp {ongkir:,.0f}")
        
    else:
        st.warning("Database kosong. Silakan import data CSV 'ShipTable' ke tabel 'master_shipping_zones'.")
else:
    st.error("Koneksi Database bermasalah.")
