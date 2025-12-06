import streamlit as st
from supabase import create_client, Client
import pandas as pd

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Kalkulator Ongkir", page_icon="🚚")

# --- KONEKSI SUPABASE ---
# Sebaiknya simpan ini di st.secrets untuk keamanan, 
# tapi untuk file standalone bisa ditaruh sini.
SUPABASE_URL = "https://ganti-dengan-url-project-anda.supabase.co"
SUPABASE_KEY = "ganti-dengan-anon-key-anda"

@st.cache_resource
def init_connection():
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"Gagal koneksi database: {e}")
        return None

supabase = init_connection()

# --- FUNGSI LOAD DATA ---
@st.cache_data(ttl=300) # Cache data selama 5 menit agar cepat
def get_zones():
    response = supabase.table('master_shipping_zones').select("*").order('kecamatan').execute()
    return pd.DataFrame(response.data)

@st.cache_data(ttl=300)
def get_rates():
    response = supabase.table('master_shipping_rates').select("*").order('tarif_per_km_lebih').execute()
    return pd.DataFrame(response.data)

# --- UI APLIKASI ---
st.markdown("## 🚚 Kalkulator Biaya Kirim")
st.markdown("---")

# Load data dari DB
if supabase:
    df_zones = get_zones()
    df_rates = get_rates()

    # 1. INPUT TUJUAN (Dropdown dengan Info Jarak)
    st.subheader("1. Tujuan Pengiriman")
    
    # Membuat label format: "Nama Kecamatan (X KM)"
    zone_options = df_zones.apply(lambda x: f"{x['kecamatan']} - {x['jarak_dari_toko_km']} KM", axis=1).tolist()
    selected_zone_label = st.selectbox("Pilih Kecamatan/Wilayah:", options=zone_options)
    
    # Ambil data detail dari pilihan user
    selected_zone_name = selected_zone_label.split(" - ")[0]
    zone_data = df_zones[df_zones['kecamatan'] == selected_zone_name].iloc[0]
    jarak_km = float(zone_data['jarak_dari_toko_km'])

    # 2. INPUT BARANG (Multiselect)
    st.subheader("2. Pilih Kategori Barang")
    st.info("💡 Jika pilih banyak barang, tarif otomatis mengikuti kendaraan terbesar.")
    
    # Opsi barang ditampilkan beserta jenis kendaraannya
    rate_options = df_rates['kategori_produk'].tolist()
    selected_items = st.multiselect("Checklist barang yang dibeli:", options=rate_options)

    st.markdown("---")

    # --- LOGIKA PERHITUNGAN ---
    if selected_items:
        # A. Tentukan Rate Tertinggi (Logika Campuran)
        # Filter dataframe berdasarkan item yang dipilih user
        selected_rates_df = df_rates[df_rates['kategori_produk'].isin(selected_items)]
        
        # Ambil row dengan tarif tertinggi (Max Vehicle Logic)
        highest_rate_row = selected_rates_df.loc[selected_rates_df['tarif_per_km_lebih'].idxmax()]
        
        kendaraan_terpakai = highest_rate_row['kendaraan']
        tarif_per_km = float(highest_rate_row['tarif_per_km_lebih'])

        # B. Hitung Jarak Berbayar
        batas_gratis = 7.0
        jarak_berbayar = max(0, jarak_km - batas_gratis)
        
        # C. Hitung Total Ongkir
        total_ongkir = jarak_berbayar * tarif_per_km

        # --- OUTPUT CARD HASIL ---
        with st.container():
            st.markdown("### 🧾 Rincian Ongkos Kirim")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Jarak Tempuh", f"{jarak_km} KM")
                st.caption(f"Kecamatan: {selected_zone_name}")
            
            with col2:
                # Logika status radius
                if jarak_km <= 7:
                    status_text = "✅ Dalam Radius Gratis"
                else:
                    status_text = f"⚠️ Lebih {jarak_berbayar} KM"
                st.metric("Status Jarak", status_text)

            # Info Kendaraan
            st.write(f"**Kendaraan:** {kendaraan_terpakai}")
            st.caption(f"Menggunakan tarif: Rp {tarif_per_km:,.0f}/km (untuk kelebihan jarak)")

            st.markdown("---")
            
            # Tampilan Total Besar
            if total_ongkir == 0:
                st.success("### TOTAL: GRATIS (Rp 0)")
            else:
                st.warning(f"### TOTAL: Rp {total_ongkir:,.0f}")
                
    else:
        st.write("👈 *Silakan pilih minimal satu barang untuk melihat harga.*")

else:
    st.error("Gagal memuat database.")
