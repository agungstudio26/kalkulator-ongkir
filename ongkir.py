import streamlit as st
from supabase import create_client, Client
import pandas as pd
import io

# --- CONFIG & VERSION ---
APP_VERSION = "v9.0 (Production Logic + Admin Tools)"
st.set_page_config(page_title="Kalkulator Ongkir GEM", layout="wide")

# --- CSS STYLING ---
st.markdown("""
<style>
    .big-font { font-size:24px !important; font-weight: bold; } 
    .success-font { font-size:24px !important; font-weight: bold; color: green; }
    .stNumberInput input { text-align: center; }
</style>
""", unsafe_allow_html=True)

# --- FUNGSI DOWNLOAD TEMPLATE (SESUAI STRUKTUR BARU) ---
def get_template_excel():
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # SHEET 1: LOKASI (Shipping Rates)
        df_loc = pd.DataFrame({
            'city': ['Kab. Bandung', 'Kota Bekasi'],
            'postal_code': ['40377', '17145'],
            'dist_banjaran': [3.5, 0], 'dist_kopo': [15.0, 0], 'dist_kalimalang': [0, 1.8],
            'min_charge_banjaran': [0, 0], 'min_charge_kopo': [50000, 0], 'min_charge_kalimalang': [0, 0],
            'zone_category': ['ZONE 1', 'ZONE 2'] # Penting untuk validasi
        })
        df_loc.to_excel(writer, index=False, sheet_name='Lokasi (Shipping Rates)')
        
        # SHEET 2: BARANG (Item Rates)
        df_item = pd.DataFrame({
            'category_name': ['TV 43 Inch', 'Kulkas Side by Side'],
            'nextday_rate': [50000, 150000],      # Tarif Regular
            'tradein_rate': [75000, 250000],      # Tarif Tukar Tambah
            'lite_install_rate': [100000, 0]      # Tarif Pasang (0/Kosong jika tidak bisa)
        })
        df_item.to_excel(writer, index=False, sheet_name='Barang (Item Rates)')
        
    return output.getvalue()

# --- SIDEBAR TOOLS ---
with st.sidebar:
    st.title("⚙️ Admin Tools")
    st.caption(f"Ver: {APP_VERSION}")
    
    excel_file = get_template_excel()
    st.download_button(
        label="📥 Download Template Admin (.xlsx)",
        data=excel_file,
        file_name="Template_Master_v9.xlsx",
        help="Gunakan file ini untuk mengisi data Lokasi dan Harga Barang"
    )
    
    if st.button("🔄 Refresh Data Cache"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

# --- KONEKSI DATABASE ---
@st.cache_resource
def init_connection():
    try:
        # Support kedua jenis nama secrets (lama/baru)
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

# --- UI UTAMA ---
st.title("🚛 Kalkulator Biaya Kirim GEM")

if not supabase:
    st.stop()

# --- INPUT USER ---
col_toko, col_kota, col_service = st.columns(3)

with col_toko:
    asal_gudang = st.selectbox(
        "Toko / Gudang Asal", 
        ["Blibli Elektronik - Kopo Bandung", "Blibli Elektronik - Banjaran Bandung", "Dekoruma Elektronik - Kalimalang Bekasi"]
    )

with col_kota:
    try:
        kota_response = supabase.table('shipping_rates').select('city', 'postal_code').execute()
        if kota_response.data:
            # Membuat list unik "Kota - Kode Pos"
            list_opsi = sorted(list(set([f"{item['city']} - {item['postal_code']}" for item in kota_response.data])))
            tujuan_input = st.selectbox("Alamat Pengiriman (Kota - Kode Pos)", list_opsi)
        else:
            st.warning("⚠️ Database Lokasi Kosong. Silakan Import via Admin Tools.")
            tujuan_input = ""
    except:
        tujuan_input = ""

with col_service:
    jenis_layanan = st.selectbox(
        "Tipe Pengiriman", 
        ["Nextday Delivery", "Trade In Delivery", "Lite Install Delivery"]
    )

# --- INPUT BARANG ---
st.write("---")
st.subheader("📦 Daftar Barang")

try:
    items_response = supabase.table('item_shipping_rates').select('*').order('id').execute()
    items_data = items_response.data
except:
    items_data = []

input_items = {} 
if items_data:
    cols = st.columns(3)
    for i, item in enumerate(items_data):
        with cols[i % 3]:
            # Input Qty untuk setiap barang
            qty = st.number_input(f"{item['category_name']}", min_value=0, value=0, key=f"qty_{item['id']}")
            if qty > 0:
                input_items[item['category_name']] = {'qty': qty, 'rates': item}
else:
    st.info("💡 Data Barang belum ada. Gunakan template admin untuk upload.")

# --- LOGIKA HITUNG (CORE LOGIC) ---
st.markdown("---")
if st.button("Hitung Total Biaya Kirim", type="primary", use_container_width=True):
    
    # 1. Validasi
    if not tujuan_input:
        st.error("Pilih alamat tujuan.")
        st.stop()
    if not input_items:
        st.warning("Masukkan jumlah barang.")
        st.stop()

    # 2. Ambil Data Lokasi
    postal_code_pilih = tujuan_input.split(" - ")[1]
    loc_data = supabase.table('shipping_rates').select('*').eq('postal_code', postal_code_pilih).execute()
    
    if not loc_data.data:
        st.error("Data lokasi detail tidak ditemukan.")
        st.stop()
        
    lokasi = loc_data.data[0]
    user_zone = lokasi.get('zone_category') or 'ZONE 2' 
    
    # 3. Parameter Gudang
    jarak = 0
    min_charge_lokasi = 0
    batas_free = 0
    
    if "Kopo" in asal_gudang:
        jarak = float(lokasi['dist_kopo'] or 0)
        min_charge_lokasi = float(lokasi['min_charge_kopo'] or 0)
        batas_free = 7
    elif "Banjaran" in asal_gudang:
        jarak = float(lokasi['dist_banjaran'] or 0)
        min_charge_lokasi = float(lokasi['min_charge_banjaran'] or 0)
        batas_free = 7
    else: # Kalimalang
        jarak = float(lokasi['dist_kalimalang'] or 0)
        min_charge_lokasi = float(lokasi['min_charge_kalimalang'] or 0)
        batas_free = 10 

    is_free = True if jarak <= batas_free else False

    # 4. Hitung Barang
    total_biaya_barang = 0
    rincian_tabel = []
    validasi_sukses = True
    pesan_error = ""

    for nama_barang, info in input_items.items():
        qty = info['qty']
        rates = info['rates']
        harga_satuan = 0
        
        # Logic Harga Berdasarkan Layanan
        if jenis_layanan == "Nextday Delivery":
            harga_satuan = float(rates['nextday_rate'] or 0)
            
        elif jenis_layanan == "Trade In Delivery":
            if "ZONE 1" not in str(user_zone).upper():
                validasi_sukses = False
                pesan_error = f"Layanan Trade In HANYA berlaku untuk ZONE 1. Lokasi Anda: {user_zone}"
                break
            harga_satuan = float(rates['tradein_rate'] or 0)
                
        elif jenis_layanan == "Lite Install Delivery":
            if "ZONE 1" not in str(user_zone).upper():
                validasi_sukses = False
                pesan_error = f"Layanan Lite Install HANYA berlaku untuk ZONE 1. Lokasi Anda: {user_zone}"
                break
            if not rates['lite_install_rate'] or rates['lite_install_rate'] == 0:
                validasi_sukses = False
                pesan_error = f"Layanan Lite Install TIDAK TERSEDIA untuk barang: {nama_barang}"
                break
            harga_satuan = float(rates['lite_install_rate'])

        subtotal = harga_satuan * qty
        total_biaya_barang += subtotal
        rincian_tabel.append({
            "Produk": nama_barang, "Qty": qty, 
            "Harga Satuan": f"Rp {harga_satuan:,.0f}", "Subtotal": f"Rp {subtotal:,.0f}"
        })

    # 5. Hasil Akhir
    st.info(f"📍 Jarak: {jarak} Km | Zona: {user_zone} | Min Charge Lokasi: Rp {min_charge_lokasi:,.0f}")

    if not validasi_sukses:
        st.error(f"❌ {pesan_error}")
    else:
        st.table(pd.DataFrame(rincian_tabel))
        st.divider()
        
        if is_free:
            st.markdown('<p class="success-font">🎉 FREE SHIPPING</p>', unsafe_allow_html=True)
            st.caption(f"Jarak {jarak} km masuk radius gratis.")
        else:
            final_cost = max(total_biaya_barang, min_charge_lokasi)
            ket = " (Min Charge)" if final_cost == min_charge_lokasi else " (Total Barang)"
            
            st.markdown(f'<p class="big-font">Total: Rp {final_cost:,.0f}</p>', unsafe_allow_html=True)
            st.caption(f"Metode: Ambil Terbesar {ket}")
