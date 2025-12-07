import streamlit as st
from supabase import create_client, Client
import pandas as pd
import io

# --- CONFIG & VERSION ---
APP_VERSION = "v9.1 (Smart Importer - Auto Clean Mixed Data)"
st.set_page_config(page_title="Kalkulator Ongkir GEM", layout="wide")

# --- CSS ---
st.markdown("""
<style>
    .big-font { font-size:24px !important; font-weight: bold; } 
    .success-font { font-size:24px !important; font-weight: bold; color: green; }
    .stNumberInput input { text-align: center; }
</style>
""", unsafe_allow_html=True)

# --- KONEKSI DATABASE ---
@st.cache_resource
def init_connection():
    try:
        if "SUPABASE_URL" in st.secrets:
            url = st.secrets["SUPABASE_URL"]
            key = st.secrets["SUPABASE_KEY"]
        else:
            url = st.secrets["supabase"]["url"]
            key = st.secrets["supabase"]["key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Koneksi Gagal: {e}")
        return None

supabase = init_connection()

# --- FUNGSI SMART CLEANING (PENTING) ---
def clean_and_upload(df_raw):
    """
    Fungsi ini memecahkan masalah kolom yang tercampur Angka & Huruf (ZONE 1 vs Harga).
    """
    # 1. Standarisasi Header (Hapus spasi & lowercase)
    df_raw.columns = df_raw.columns.str.strip().str.lower()
    
    clean_data = []
    
    # Progress Bar
    progress_bar = st.progress(0)
    total_rows = len(df_raw)

    for index, row in df_raw.iterrows():
        # Update progress setiap 100 baris biar tidak berat
        if index % 100 == 0:
            progress_bar.progress(min(index / total_rows, 1.0))

        # --- LOGIKA PEMBERSIHAN DATA ---
        
        # A. Ambil Data Dasar
        province = row.get('province', '')
        city = row.get('city', '')
        postal_code = str(row.get('postal_code', '')).replace('.0', '') # Hapus .0 di kode pos
        
        # B. Mapping Jarak (Pastikan angka)
        # Cari kolom jarak yang sesuai di CSV upload-an user
        # (User harus memastikan nama header di CSV sesuai/mirip)
        try:
            d_banjaran = float(row.get('dist_banjaran', 0))
        except: d_banjaran = 0
        
        try:
            d_kopo = float(row.get('dist_kopo', 0))
        except: d_kopo = 0
            
        try:
            d_bekasi = float(row.get('dist_kalimalang', 0) or row.get('dist_bekasi', 0))
        except: d_bekasi = 0

        # C. SMART SPLIT: ZONE vs MIN CHARGE
        # Masalah: Kolom 'min_charge_banjaran' di Excel kadang isi "ZONE 1", kadang Angka.
        
        # Helper kecil untuk cek apakah nilai itu angka atau teks
        def split_value(val):
            val_str = str(val).upper().strip()
            if "ZONE" in val_str:
                return val_str, 0 # Kembali (Zone, Harga 0)
            else:
                try:
                    # Coba konversi ke float
                    harga = float(val)
                    return "ZONE 2", harga # Default Zone 2, Harga sesuai angka
                except:
                    return "ZONE 2", 0

        # Terapkan ke 3 Toko (Ambil kolom raw dari Excel user)
        # Asumsi user menamai kolomnya: 'min_banjaran', 'min_kopo', 'min_bekasi'
        # Atau 'min_charge_banjaran' dst.
        
        raw_min_banjaran = row.get('min_banjaran', row.get('min_charge_banjaran', 0))
        zone_banjaran, cost_banjaran = split_value(raw_min_banjaran)
        
        raw_min_kopo = row.get('min_kopo', row.get('min_charge_kopo', 0))
        zone_kopo, cost_kopo = split_value(raw_min_kopo)
        
        # Logic Prioritas Zona: Jika salah satu toko ZONE 1, kita anggap lokasi itu ZONE 1
        final_zone = "ZONE 1" if (zone_banjaran == "ZONE 1" or zone_kopo == "ZONE 1") else "ZONE 2"
        
        # D. Masukkan ke List Bersih
        clean_data.append({
            "city": city,
            "postal_code": postal_code,
            "dist_banjaran": d_banjaran,
            "dist_kopo": d_kopo,
            "dist_kalimalang": d_bekasi,
            "min_charge_banjaran": cost_banjaran,
            "min_charge_kopo": cost_kopo,
            "min_charge_kalimalang": 0, # Sesuaikan jika ada datanya
            "zone_category": final_zone
        })
    
    progress_bar.empty()
    return pd.DataFrame(clean_data)

# --- SIDEBAR: SMART IMPORTER ---
with st.sidebar:
    st.title("⚙️ Admin Tools")
    st.write(f"Ver: {APP_VERSION}")
    
    st.markdown("### 1. Smart Import (Fix Error)")
    st.info("Upload file CSV asli Bapak di sini. Sistem akan otomatis memisahkan Teks 'ZONE 1' dan Angka Harga.")
    
    uploaded_file = st.file_uploader("Upload CSV Data", type=["csv"])
    
    if uploaded_file is not None:
        if st.button("🚀 Proses & Upload ke Database"):
            with st.spinner("Sedang membersihkan data..."):
                try:
                    # 1. Baca CSV
                    df_upload = pd.read_csv(uploaded_file)
                    
                    # 2. Clean Data
                    df_clean = clean_and_upload(df_upload)
                    
                    # 3. Hapus Data Lama (Opsional, biar bersih)
                    supabase.table('shipping_rates').delete().neq("id", 0).execute()
                    
                    # 4. Upload Data Bersih (Batching biar gak timeout)
                    data_to_insert = df_clean.to_dict(orient='records')
                    
                    # Insert per 100 baris
                    batch_size = 100
                    for i in range(0, len(data_to_insert), batch_size):
                        batch = data_to_insert[i:i + batch_size]
                        supabase.table('shipping_rates').insert(batch).execute()
                        
                    st.success(f"✅ Sukses! {len(data_to_insert)} baris data berhasil diperbaiki dan diupload.")
                    st.cache_data.clear()
                    
                except Exception as e:
                    st.error(f"Gagal Proses: {e}")
                    st.write("Tips: Pastikan nama header kolom di CSV adalah: city, postal_code, dist_banjaran, dist_kopo, min_banjaran, min_kopo")

    st.markdown("---")
    if st.button("🔄 Refresh Aplikasi"):
        st.rerun()

# --- UI UTAMA (Sama seperti v9.0) ---
st.title("🚛 Kalkulator Biaya Kirim GEM")

if not supabase:
    st.stop()

# --- INPUT USER ---
col_toko, col_kota, col_service = st.columns(3)

with col_toko:
    asal_gudang = st.selectbox("Toko Asal", ["Blibli Elektronik - Kopo Bandung", "Blibli Elektronik - Banjaran Bandung", "Dekoruma Elektronik - Kalimalang Bekasi"])

with col_kota:
    try:
        kota_response = supabase.table('shipping_rates').select('city', 'postal_code').execute()
        if kota_response.data:
            list_opsi = sorted(list(set([f"{item['city']} - {item['postal_code']}" for item in kota_response.data])))
            tujuan_input = st.selectbox("Alamat Tujuan", list_opsi)
        else:
            st.warning("⚠️ Database Kosong. Silakan Upload CSV di Sidebar.")
            tujuan_input = ""
    except:
        tujuan_input = ""

with col_service:
    jenis_layanan = st.selectbox("Layanan", ["Nextday Delivery", "Trade In Delivery", "Lite Install Delivery"])

# --- HITUNG ---
st.write("---")
st.subheader("📦 Barang")

try:
    items_data = supabase.table('item_shipping_rates').select('*').order('id').execute().data
except: items_data = []

input_items = {} 
if items_data:
    cols = st.columns(3)
    for i, item in enumerate(items_data):
        with cols[i % 3]:
            qty = st.number_input(f"{item['category_name']}", min_value=0, value=0, key=f"q_{item['id']}")
            if qty > 0: input_items[item['category_name']] = {'qty': qty, 'rates': item}

st.markdown("---")
if st.button("Hitung Biaya", type="primary", use_container_width=True):
    if not tujuan_input or not input_items:
        st.error("Lengkapi data tujuan dan barang.")
        st.stop()

    # Ambil Data
    code = tujuan_input.split(" - ")[1]
    loc = supabase.table('shipping_rates').select('*').eq('postal_code', code).execute().data[0]
    
    # Init Var
    jarak, min_charge, free_limit = 0, 0, 0
    
    if "Kopo" in asal_gudang:
        jarak = float(loc['dist_kopo'] or 0)
        min_charge = float(loc['min_charge_kopo'] or 0)
        free_limit = 7
    elif "Banjaran" in asal_gudang:
        jarak = float(loc['dist_banjaran'] or 0)
        min_charge = float(loc['min_charge_banjaran'] or 0)
        free_limit = 7
    else:
        jarak = float(loc['dist_kalimalang'] or 0)
        min_charge = float(loc['min_charge_kalimalang'] or 0)
        free_limit = 10
        
    is_free = jarak <= free_limit
    zone = loc.get('zone_category', 'ZONE 2')
    
    # Hitung
    total_goods = 0
    tabel = []
    valid = True
    err_msg = ""
    
    for name, info in input_items.items():
        qty, rates = info['qty'], info['rates']
        price = 0
        
        if jenis_layanan == "Nextday Delivery": price = float(rates['nextday_rate'] or 0)
        elif jenis_layanan == "Trade In Delivery":
            if "ZONE 1" not in str(zone).upper():
                valid, err_msg = False, f"Trade In hanya untuk ZONE 1 (Lokasi: {zone})"
                break
            price = float(rates['tradein_rate'] or 0)
        elif jenis_layanan == "Lite Install Delivery":
            if "ZONE 1" not in str(zone).upper():
                valid, err_msg = False, f"Install hanya untuk ZONE 1 (Lokasi: {zone})"
                break
            if not rates['lite_install_rate']:
                valid, err_msg = False, f"{name} tidak bisa di-install."
                break
            price = float(rates['lite_install_rate'])
            
        sub = price * qty
        total_goods += sub
        tabel.append({"Barang": name, "Qty": qty, "Harga": f"{price:,.0f}", "Subtotal": f"{sub:,.0f}"})
        
    if not valid:
        st.error(f"❌ {err_msg}")
    else:
        st.table(pd.DataFrame(tabel))
        st.info(f"📍 Jarak: {jarak} km | Zona: {zone} | Min Charge: Rp {min_charge:,.0f}")
        
        if is_free:
            st.success("🎉 FREE SHIPPING")
        else:
            final = max(total_goods, min_charge)
            st.markdown(f"### Total: Rp {final:,.0f}")
            st.caption("(Min Charge)" if final == min_charge else "(Total Barang)")
