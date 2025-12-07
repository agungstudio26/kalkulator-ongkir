import streamlit as st
from supabase import create_client, Client
import pandas as pd
import io

# --- CONFIG & VERSION ---
APP_VERSION = "v9.4 (Diagnosa & Auto-Fix)"
st.set_page_config(page_title="Kalkulator Ongkir GEM", layout="wide")

# --- CSS STYLING ---
st.markdown("""
<style>
    .big-font { font-size:24px !important; font-weight: bold; } 
    .success-font { font-size:24px !important; font-weight: bold; color: green; }
    .warning-box { background-color: #fff3cd; padding: 15px; border-radius: 5px; border: 1px solid #ffeeba; }
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
        return None

supabase = init_connection()

# --- FUNGSI PEMBERSIH DATA (SUPER ROBUST) ---
def clean_and_fix_data(df_raw):
    # Standarisasi Header: Hapus spasi, lowercase, ganti simbol aneh
    df_raw.columns = df_raw.columns.str.strip().str.lower().str.replace('\n', ' ').str.replace('.', '')
    
    clean_data = []
    progress_text = "Sedang memperbaiki format data..."
    my_bar = st.progress(0, text=progress_text)
    total_len = len(df_raw)

    for index, row in df_raw.iterrows():
        if index % 50 == 0:
            my_bar.progress(min(index/total_len, 1.0))

        # 1. Cari Kolom Kota & Kode Pos (Fuzzy Search Sederhana)
        city = row.get('city', row.get('kota', row.get('kabupaten', '')))
        postal = str(row.get('postal_code', row.get('kode pos', row.get('postal code', '')))).replace('.0', '').strip()
        
        # Jika kode pos kosong, skip baris ini (data sampah)
        if not postal or postal == 'nan':
            continue

        # 2. Fungsi Aman Konversi Angka
        def to_float(val):
            try: return float(val)
            except: return 0.0
            
        # Cari kolom jarak dengan berbagai kemungkinan nama
        d_banjaran = 0
        d_kopo = 0
        d_bekasi = 0
        
        for col in df_raw.columns:
            if 'banjaran' in col and 'dist' in col: d_banjaran = to_float(row[col])
            if 'kopo' in col and 'dist' in col: d_kopo = to_float(row[col])
            if ('kalimalang' in col or 'bekasi' in col) and 'dist' in col: d_bekasi = to_float(row[col])

        # 3. Smart Split Zone vs Price
        def split_zone_price(val):
            val_str = str(val).upper().strip()
            if "ZONE" in val_str: return val_str, 0.0
            else: return "ZONE 2", to_float(val)

        p_ban, p_kop, p_bek = 0, 0, 0
        z_ban, z_kop, z_bek = "ZONE 2", "ZONE 2", "ZONE 2"

        for col in df_raw.columns:
            if 'min' in col and 'charge' in col:
                z_temp, p_temp = split_zone_price(row[col])
                if 'banjaran' in col: z_ban, p_ban = z_temp, p_temp
                if 'kopo' in col: z_kop, p_kop = z_temp, p_temp
                if 'kalimalang' in col or 'bekasi' in col: z_bek, p_bek = z_temp, p_temp

        # Logic Final Zone
        final_zone = "ZONE 1" if (z_ban == "ZONE 1" or z_kop == "ZONE 1" or z_bek == "ZONE 1") else "ZONE 2"

        clean_data.append({
            "city": city, "postal_code": postal,
            "dist_banjaran": d_banjaran, "dist_kopo": d_kopo, "dist_kalimalang": d_bekasi,
            "min_charge_banjaran": p_ban, "min_charge_kopo": p_kop, "min_charge_kalimalang": p_bek,
            "zone_category": final_zone
        })
        
    my_bar.empty()
    return pd.DataFrame(clean_data)

# --- SIDEBAR TOOLS ---
with st.sidebar:
    st.title("⚙️ Admin Panel")
    st.caption(f"Ver: {APP_VERSION}")
    
    # STATUS DATABASE
    if supabase:
        try:
            count_res = supabase.table('shipping_rates').select('*', count='exact', head=True).execute()
            count_loc = count_res.count
            st.metric("Total Data Database", f"{count_loc} Baris")
            
            if count_loc == 0:
                st.error("DATABASE KOSONG!")
                st.markdown("👉 **Wajib Upload Data di bawah ini**")
            else:
                st.success("Database Aktif ✅")
                if st.button("🗑️ Hapus Semua Data (Reset)"):
                    supabase.table('shipping_rates').delete().neq("id", 0).execute()
                    st.warning("Data dihapus.")
                    st.rerun()
        except:
            st.error("Gagal koneksi. Cek RLS!")

    st.markdown("---")
    st.markdown("### 🔧 Perbaiki & Upload Data")
    upl_file = st.file_uploader("Upload CSV Excel", type=['csv'])
    
    if upl_file:
        df_dirty = pd.read_csv(upl_file)
        if st.button("1. Bersihkan Data"):
            st.session_state['df_clean'] = clean_and_fix_data(df_dirty)
            st.success("Data Siap!")

        if 'df_clean' in st.session_state:
            df_final = st.session_state['df_clean']
            st.write(f"Data Bersih: {len(df_final)} Baris")
            
            if st.button("2. 🚀 UPLOAD KE DATABASE"):
                try:
                    # Hapus lama
                    supabase.table('shipping_rates').delete().neq("id", 0).execute()
                    # Upload baru (Batch)
                    data_dict = df_final.to_dict(orient='records')
                    batch_size = 100
                    prog = st.progress(0)
                    for i in range(0, len(data_dict), batch_size):
                        supabase.table('shipping_rates').insert(data_dict[i:i+batch_size]).execute()
                        prog.progress(min(i/len(data_dict), 1.0))
                    prog.empty()
                    st.success("✅ BERHASIL MASUK DATABASE!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal Upload: {e}")

# --- UI UTAMA ---
st.title("🚛 Kalkulator Biaya Kirim GEM")

if not supabase:
    st.error("Koneksi Database Gagal. Cek secrets.toml")
    st.stop()

# --- DIAGNOSA AWAL ---
# Cek apakah data lokasi ada
try:
    loc_check = supabase.table('shipping_rates').select('city').limit(1).execute()
    if not loc_check.data:
        st.markdown("""
        <div class="warning-box">
            <h3>⚠️ Database Lokasi Masih Kosong</h3>
            <p>Dropdown Tujuan tidak akan muncul karena belum ada data.</p>
            <ol>
                <li>Buka Sidebar (panah kiri atas)</li>
                <li>Upload file CSV Anda di menu 'Admin Panel'</li>
                <li>Klik tombol 'Bersihkan Data' lalu 'UPLOAD KE DATABASE'</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)
        st.stop() # Berhenti di sini agar user fix dulu
except Exception as e:
    st.error(f"Error Database (RLS Mungkin Aktif): {e}")
    st.stop()

# --- INPUT SECTION ---
c1, c2, c3 = st.columns(3)
with c1:
    gudang = st.selectbox("Toko Asal", ["Blibli - Kopo", "Blibli - Banjaran", "Dekoruma - Kalimalang"])

with c2:
    # Ambil Data Lokasi
    res = supabase.table('shipping_rates').select('city, postal_code').execute()
    # Buat format "Kota - Kode Pos" dan Sortir
    opts = sorted(list(set([f"{r['city']} - {r['postal_code']}" for r in res.data])))
    dest = st.selectbox("Tujuan Pengiriman", opts)

with c3:
    service = st.selectbox("Layanan", ["Nextday Delivery", "Trade In Delivery", "Lite Install Delivery"])

st.markdown("---")
st.subheader("📦 Barang")

# Cek Data Barang
try:
    items = supabase.table('item_shipping_rates').select('*').order('id').execute().data
except: items = []

if not items:
    st.warning("⚠️ Data Barang Kosong. Upload pakai template admin.")

cart = {}
if items:
    cols = st.columns(3)
    for i, it in enumerate(items):
        with cols[i%3]:
            q = st.number_input(it['category_name'], 0, key=it['id'])
            if q > 0: cart[it['category_name']] = {'qty': q, 'rates': it}

st.markdown("---")
if st.button("Hitung Estimasi", type="primary", use_container_width=True):
    if not dest:
        st.error("Pilih Tujuan dulu.")
        st.stop()
    if not cart:
        st.error("Pilih Barang dulu.")
        st.stop()
        
    # Logic Hitung
    code = dest.split(" - ")[1]
    loc = supabase.table('shipping_rates').select('*').eq('postal_code', code).execute().data[0]
    
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
    
    total_cost = 0
    rows = []
    valid = True
    err = ""
    
    for name, info in cart.items():
        q, r = info['qty'], info['rates']
        price = 0
        if service == "Nextday Delivery": price = float(r['nextday_rate'] or 0)
        elif service == "Trade In Delivery":
            if "ZONE 1" not in str(zone).upper(): valid, err = False, f"Trade In hanya ZONE 1 (Lokasi: {zone})"; break
            price = float(r['tradein_rate'] or 0)
        elif service == "Lite Install Delivery":
            if "ZONE 1" not in str(zone).upper(): valid, err = False, f"Install hanya ZONE 1 (Lokasi: {zone})"; break
            if not r['lite_install_rate']: valid, err = False, f"{name} tidak bisa install."; break
            price = float(r['lite_install_rate'])
            
        sub = price * q
        total_cost += sub
        rows.append({"Barang": name, "Qty": q, "Harga": f"{price:,.0f}", "Subtotal": f"{sub:,.0f}"})
        
    st.info(f"📍 Jarak: {dist} km | Zona: {zone} | Min Charge: Rp {min_chg:,.0f}")
    
    if not valid: st.error(err)
    else:
        st.table(pd.DataFrame(rows))
        if is_free:
            st.success("🎉 FREE SHIPPING (Masuk Radius)")
        else:
            final = max(total_cost, min_chg)
            lbl = "(Min Charge)" if final == min_chg else "(Total Barang)"
            st.markdown(f"### Total: Rp {final:,.0f} {lbl}")
