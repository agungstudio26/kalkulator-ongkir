import streamlit as st
from supabase import create_client, Client
import pandas as pd

# --- VERSI APLIKASI ---
APP_VERSION = "v1.1 (Stable Fix)"

# --- KONFIGURASI HALAMAN ---
st.set_page_config(
    page_title="Kalkulator Ongkir Toko",
    page_icon="🚚",
    layout="centered"
)

# --- FUNGSI KONEKSI DATABASE ---
@st.cache_resource
def init_connection():
    """
    Inisialisasi koneksi ke Supabase dengan error handling
    """
    try:
        # 1. Cek apakah secrets ada
        if "supabase" not in st.secrets:
            st.error("❌ Konfigurasi 'secrets.toml' belum ditemukan di Streamlit Cloud.")
            st.stop()
            
        # 2. Ambil kredensial dan BERSIHKAN (strip) dari spasi tak terlihat
        url = st.secrets["supabase"]["url"].strip()
        key = st.secrets["supabase"]["key"].strip()

        # 3. Validasi format URL sederhana
        if not url.startswith("https://"):
            st.error(f"❌ Format URL salah. Harus diawali 'https://'. Saat ini: {url[:10]}...")
            st.stop()

        return create_client(url, key)
        
    except Exception as e:
        st.error(f"❌ Gagal menghubungkan aplikasi: {e}")
        return None

# Inisialisasi Client
supabase = init_connection()

# --- FUNGSI LOAD DATA (CACHED) ---
@st.cache_data(ttl=300)
def get_zones():
    try:
        response = supabase.table('master_shipping_zones').select("*").order('kecamatan').execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Gagal mengambil data Zona: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_rates():
    try:
        response = supabase.table('master_shipping_rates').select("*").order('tarif_per_km_lebih').execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Gagal mengambil data Tarif: {e}")
        return pd.DataFrame()

# --- SIDEBAR STATUS ---
with st.sidebar:
    st.write(f"**Versi:** {APP_VERSION}")
    if supabase:
        st.success("🟢 Database Terhubung")
    else:
        st.error("🔴 Database Putus")
    
    st.markdown("---")
    st.caption("Gunakan aplikasi ini untuk mengecek estimasi biaya kirim berdasarkan jarak.")

# --- UI UTAMA ---
st.title("🚚 Kalkulator Biaya Kirim")
st.markdown("---")

if supabase:
    # Load Data
    df_zones = get_zones()
    df_rates = get_rates()

    # Pastikan data tidak kosong sebelum lanjut
    if not df_zones.empty and not df_rates.empty:
        
        # 1. INPUT TUJUAN
        st.subheader("1. Tujuan Pengiriman")
        # Format label dropdown
        zone_options = df_zones.apply(lambda x: f"{x['kecamatan']} - {x['jarak_dari_toko_km']} KM", axis=1).tolist()
        selected_zone_label = st.selectbox("Pilih Wilayah:", options=zone_options)
        
        # Ekstrak data dari pilihan
        selected_zone_name = selected_zone_label.split(" - ")[0]
        zone_data = df_zones[df_zones['kecamatan'] == selected_zone_name].iloc[0]
        jarak_km = float(zone_data['jarak_dari_toko_km'])

        # 2. INPUT BARANG
        st.subheader("2. Pilih Barang")
        st.info("💡 Sistem otomatis memilih tarif kendaraan terbesar.")
        
        rate_options = df_rates['kategori_produk'].tolist()
        selected_items = st.multiselect("Checklist barang:", options=rate_options)

        st.markdown("---")

        # 3. LOGIKA HITUNG
        if selected_items:
            # Filter hanya rate yang dipilih
            selected_rates_df = df_rates[df_rates['kategori_produk'].isin(selected_items)]
            
            # AMBIL TARIF TERTINGGI (Logika Mobil > Motor)
            highest_rate_row = selected_rates_df.loc[selected_rates_df['tarif_per_km_lebih'].idxmax()]
            
            kendaraan = highest_rate_row['kendaraan']
            tarif_per_km = float(highest_rate_row['tarif_per_km_lebih'])

            # HITUNG
            batas_gratis = 7.0
            jarak_berbayar = max(0, jarak_km - batas_gratis)
            total_ongkir = jarak_berbayar * tarif_per_km

            # 4. HASIL (CARD STYLE)
            with st.container():
                st.markdown("### 🧾 Rincian Biaya")
                c1, c2 = st.columns(2)
                
                c1.metric("📍 Jarak", f"{jarak_km} KM")
                
                # Logic status text
                if jarak_km <= 7:
                    c2.metric("Status", "✅ GRATIS Ongkir")
                else:
                    c2.metric("Status", f"⚠️ Charge (+{jarak_berbayar} KM)")
                
                st.write(f"**Kendaraan:** {kendaraan}")
                st.caption(f"Rate Charge: Rp {tarif_per_km:,.0f}/km")
                
                st.divider()
                
                if total_ongkir == 0:
                    st.success("### TOTAL: Rp 0 (GRATIS)")
                else:
                    st.warning(f"### TOTAL: Rp {total_ongkir:,.0f}")

        else:
            st.write("👈 *Pilih minimal satu barang.*")
    
    else:
        st.warning("Data Master Kosong. Silakan isi database Supabase (Jalankan script SQL).")
else:
    st.error("Koneksi Database Gagal. Periksa Secrets di Streamlit Cloud.")
