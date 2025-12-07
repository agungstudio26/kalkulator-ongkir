import streamlit as st
from supabase import create_client, Client
import pandas as pd
import io

# --- CONFIG & VERSION ---
APP_VERSION = "v9.2 (Fitur Download CSV Bersih)"
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
        # Support variable secrets lama atau baru
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
def clean_and_fix_data(df_raw):
    """
    Memisahkan data 'ZONE 1' (Teks) dari Harga (Angka) agar Supabase tidak menolak.
    """
    df_raw.columns = df_raw.columns.str.strip().str.lower()
    clean_data = []
    
    # Progress UI
    progress_text = "Operation in progress. Please wait."
    my_bar = st.progress(0, text=progress_text)
    total_len = len(df_raw)

    for index, row in df_raw.iterrows():
        # Update progress
        if index % 50 == 0:
            my_bar.progress(min(index/total_len, 1.0), text=f"Memproses baris {index} dari {total_len}")

        # 1. Ambil Data Lokasi
        city = row.get('city', '')
        postal = str(row.get('postal_code', '')).replace('.0', '').strip()
        
        # 2. Ambil Jarak (Paksa jadi Float, kalau error jadi 0)
        def to_float(val):
            try: return float(val)
            except: return 0.0
            
        d_banjaran = to_float(row.get('dist_banjaran', row.get('distance from blibli elektronik - banjaran bandung', 0)))
        d_kopo = to_float(row.get('dist_kopo', row.get('distance from blibli elektronik - kopo bandung', 0)))
        d_bekasi = to_float(row.get('dist_kalimalang', row.get('distance from dekoruma elektronik - kalimalang bekasi', 0)))

        # 3. SMART SPLIT: ZONE vs MIN CHARGE
        # Fungsi ini yang menyelamatkan data Bapak dari error Supabase
        def split_zone_price(val):
            val_str = str(val).upper().strip()
            if "ZONE" in val_str:
                return val_str, 0.0 # Jika isinya "ZONE 1", Harganya 0
            else:
                return "ZONE 2", to_float(val) # Jika Angka, Zonanya Default, Harganya sesuai angka

        # Cek 3 Kolom Min Charge (Bisa jadi header CSV Bapak masih nama panjang)
        raw_ban = row.get('min_banjaran', row.get('minimum charge blibli elektronik - banjaran bandung', 0))
        z_ban, p_ban = split_zone_price(raw_ban)
        
        raw_kop = row.get('min_kopo', row.get('minimum charge blibli elektronik - kopo bandung', 0))
        z_kop, p_kop = split_zone_price(raw_kop)
        
        raw_bek = row.get('min_kalimalang', row.get('minimum charge dekoruma elektronik - kalimalang bekasi', 0))
        z_bek, p_bek = split_zone_price(raw_bek)
        
        # Logic Final Zone
        final_zone = "ZONE 1" if (z_ban == "ZONE 1" or z_kop == "ZONE 1" or z_bek == "ZONE 1") else "ZONE 2"

        clean_data.append({
            "city": city,
            "postal_code": postal,
            "dist_banjaran": d_banjaran,
            "dist_kopo": d_kopo,
            "dist_kalimalang": d_bekasi,
            "min_charge_banjaran": p_ban,
            "min_charge_kopo": p_kop,
            "min_charge_kalimalang": p_bek,
            "zone_category": final_zone
        })
        
    my_bar.empty()
    return pd.DataFrame(clean_data)

# --- SIDEBAR TOOLS ---
with st.sidebar:
    st.title("⚙️ Admin Tools")
    st.caption(f"Ver: {APP_VERSION}")
    
    st.markdown("### 1. Fix Data Error (Zone vs Harga)")
    st.info("Upload CSV yang ditolak Supabase di sini. Sistem akan memisahkan 'ZONE 1' dari Angka Rupiah.")
    
    upl_file = st.file_uploader("Upload CSV Asli", type=['csv'])
    
    if upl_file:
        df_dirty = pd.read_csv(upl_file)
        
        if st.button("🚀 Proses Pembersihan Data"):
            # Proses Cleaning
            df_clean = clean_and_fix_data(df_dirty)
            
            # Simpan ke Session State biar gak ilang
            st.session_state['df_clean'] = df_clean
            st.success("Data berhasil dibersihkan! Silakan pilih metode upload di bawah.")

        # Jika sudah ada data bersih, tampilkan opsi
        if 'df_clean' in st.session_state:
            df_final = st.session_state['df_clean']
            st.write(f"Total Baris Bersih: {len(df_final)}")
            
            # OPSI A: Upload Otomatis
            if st.button("⬆️ Upload Langsung ke Database"):
                try:
                    # Hapus data lama (biar gak duplikat)
                    supabase.table('shipping_rates').delete().neq("id", 0).execute()
                    
                    # Insert Batching
                    data_dict = df_final.to_dict(orient='records')
                    batch_size = 100
                    
                    prog_text = "Uploading to Cloud..."
                    bar_up = st.progress(0, text=prog_text)
                    
                    for i in range(0, len(data_dict), batch_size):
                        batch = data_dict[i:i+batch_size]
                        supabase.table('shipping_rates').insert(batch).execute()
                        bar_up.progress(min(i/len(data_dict), 1.0))
                        
                    bar_up.empty()
                    st.success("✅ BERHASIL! Data sudah masuk Database.")
                    st.cache_data.clear()
                    
                except Exception as e:
                    st.error(f"Gagal Upload Otomatis: {e}")
                    st.warning("Coba gunakan Opsi B di bawah.")

            # OPSI B: Download Manual (Solusi Paling Ampuh)
            st.markdown("---")
            st.write("**Opsi B (Manual):** Download file bersih ini, lalu Import 'via CSV' di Dashboard Supabase.")
            
            csv_buffer = df_final.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download CSV Bersih",
                data=csv_buffer,
                file_name="Shipping_Rates_Cleaned_Ready.csv",
                mime="text/csv"
            )

    st.markdown("---")
    if st.button("🔄 Refresh Aplikasi"):
        st.rerun()

# --- UI UTAMA ---
st.title("🚛 Kalkulator Biaya Kirim GEM")

if not supabase: st.stop()

# --- INPUT SECTION ---
c1, c2, c3 = st.columns(3)
with c1:
    gudang = st.selectbox("Toko Asal", ["Blibli - Kopo", "Blibli - Banjaran", "Dekoruma - Kalimalang"])
with c2:
    try:
        res = supabase.table('shipping_rates').select('city, postal_code').execute()
        opts = sorted(list(set([f"{r['city']} - {r['postal_code']}" for r in res.data]))) if res.data else []
        dest = st.selectbox("Tujuan", opts) if opts else st.selectbox("Tujuan", ["Data Kosong"])
    except: dest = ""
with c3:
    service = st.selectbox("Layanan", ["Nextday Delivery", "Trade In Delivery", "Lite Install Delivery"])

st.markdown("---")
st.subheader("📦 Barang")

try:
    items = supabase.table('item_shipping_rates').select('*').order('id').execute().data
except: items = []

cart = {}
if items:
    cols = st.columns(3)
    for i, it in enumerate(items):
        with cols[i%3]:
            q = st.number_input(it['category_name'], 0, key=it['id'])
            if q > 0: cart[it['category_name']] = {'qty': q, 'rates': it}

st.markdown("---")
if st.button("Hitung", type="primary", use_container_width=True):
    if not dest or not cart:
        st.error("Data belum lengkap.")
        st.stop()
        
    # Logic
    code = dest.split(" - ")[1]
    loc = supabase.table('shipping_rates').select('*').eq('postal_code', code).execute().data[0]
    
    # Init Param
    dist, min_chg, free_lim = 0,0,0
    if "Kopo" in gudang:
        dist = float(loc['dist_kopo'] or 0)
        min_chg = float(loc['min_charge_kopo'] or 0)
        free_lim = 7
    elif "Banjaran" in gudang:
        dist = float(loc['dist_banjaran'] or 0)
        min_chg = float(loc['min_charge_banjaran'] or 0)
        free_lim = 7
    else:
        dist = float(loc['dist_kalimalang'] or 0)
        min_chg = float(loc['min_charge_kalimalang'] or 0)
        free_lim = 10
        
    is_free = dist <= free_lim
    zone = loc.get('zone_category', 'ZONE 2')
    
    total_item_cost = 0
    rows = []
    valid = True
    err = ""
    
    for name, info in cart.items():
        q, r = info['qty'], info['rates']
        price = 0
        if service == "Nextday Delivery": price = float(r['nextday_rate'] or 0)
        elif service == "Trade In Delivery":
            if "ZONE 1" not in str(zone).upper(): valid, err = False, f"Trade In hanya ZONE 1. (Lokasi: {zone})"; break
            price = float(r['tradein_rate'] or 0)
        elif service == "Lite Install Delivery":
            if "ZONE 1" not in str(zone).upper(): valid, err = False, f"Install hanya ZONE 1. (Lokasi: {zone})"; break
            if not r['lite_install_rate']: valid, err = False, f"{name} tidak bisa diinstall."; break
            price = float(r['lite_install_rate'])
            
        sub = price * q
        total_item_cost += sub
        rows.append({"Barang": name, "Qty": q, "Harga": f"{price:,.0f}", "Subtotal": f"{sub:,.0f}"})
        
    st.info(f"📍 Jarak: {dist} km | Zona: {zone} | Min Charge: Rp {min_chg:,.0f}")
    
    if not valid: st.error(err)
    else:
        st.table(pd.DataFrame(rows))
        if is_free:
            st.success("🎉 FREE SHIPPING")
        else:
            final = max(total_item_cost, min_chg)
            lbl = "(Min Charge)" if final == min_chg else "(Total Barang)"
            st.markdown(f"### Total: Rp {final:,.0f} {lbl}")
