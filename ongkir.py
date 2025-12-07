import streamlit as st
import pandas as pd

# Konfigurasi Halaman
st.set_page_config(page_title="Kalkulator Logistik Pro", layout="wide", initial_sidebar_state="expanded")

# CSS untuk styling kartu
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border: 1px solid #e9ecef;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
    }
    .best-price {
        background-color: #d4edda;
        border-color: #c3e6cb;
    }
    .best-dist {
        background-color: #fff3cd;
        border-color: #ffeeba;
    }
</style>
""", unsafe_allow_html=True)

st.title("🚛 Kalkulator Logistik & Ongkir")

# Sidebar untuk memilih Mode
mode = st.sidebar.radio("Pilih Mode Aplikasi:", ["🏠 Cari dari Database (CSV)", "🧮 Hitung Manual"])

# Fungsi Helper untuk menampilkan hasil perbandingan
def show_comparison(city_name, data_dict):
    st.markdown(f"### Hasil Analisis: {city_name}")
    
    # Cari nilai minimum (abaikan 0)
    valid_costs = [v['cost'] for k, v in data_dict.items() if v['cost'] > 0]
    valid_dists = [v['dist'] for k, v in data_dict.items() if v['dist'] > 0]
    
    min_cost = min(valid_costs) if valid_costs else 0
    min_dist = min(valid_dists) if valid_dists else 0
    
    cols = st.columns(3)
    origins = list(data_dict.keys()) # ['Banjaran', 'Kopo', 'Kalimalang']
    
    for idx, origin in enumerate(origins):
        vals = data_dict[origin]
        is_cheapest = (vals['cost'] == min_cost and vals['cost'] > 0)
        is_closest = (vals['dist'] == min_dist and vals['dist'] > 0)
        
        # Tentukan styling kartu
        card_class = "metric-card"
        badges = []
        if is_cheapest:
            card_class += " best-price"
            badges.append("✅ TERMURAH")
        if is_closest:
            card_class += " best-dist"
            badges.append("⚡ TERDEKAT")
            
        with cols[idx]:
            # Render HTML custom untuk kartu
            st.markdown(f"""
            <div class="{card_class}">
                <h4 style="margin:0;">{origin}</h4>
                <div style="margin-top:5px; font-size:0.8em; font-weight:bold; color:#555;">
                    {' '.join(badges)}
                </div>
                <hr style="margin:10px 0;">
                <p style="margin:5px 0;">📏 Jarak: <b>{vals['dist']} km</b></p>
                <p style="margin:5px 0;">💰 Biaya: <b>Rp {vals['cost']:,.0f}</b></p>
            </div>
            """, unsafe_allow_html=True)


# --- MODE 1: DATABASE (CSV) ---
if mode == "🏠 Cari dari Database (CSV)":
    st.write("Upload database tarif (CSV) untuk mencari berdasarkan Kota atau Kode Pos.")
    
    uploaded_file = st.file_uploader("Upload file CSV", type=['csv'])
    
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file, sep=';')
            
            # Sanitasi nama kolom agar tidak error jika ada spasi
            df.columns = df.columns.str.strip()

            # Input Pencarian
            search_term = st.text_input("🔍 Cari Kota / Kode Pos", "")
            
            if search_term:
                # Filter Data
                mask = (
                    df['city'].astype(str).str.contains(search_term, case=False, na=False) | 
                    df['postal_code'].astype(str).str.contains(search_term, case=False, na=False)
                )
                results = df[mask]
                
                st.info(f"Ditemukan {len(results)} lokasi.")
                
                for index, row in results.iterrows():
                    # Siapkan data dictionary untuk fungsi comparison
                    # Menggunakan .get() untuk handle jika kolom tidak ada (fallback 0)
                    comparison_data = {
                        "Banjaran": {
                            "dist": pd.to_numeric(row.get('dist_banjaran', 0), errors='coerce') or 0,
                            "cost": pd.to_numeric(row.get('min_charge_banjaran', 0), errors='coerce') or 0
                        },
                        "Kopo": {
                            "dist": pd.to_numeric(row.get('dist_kopo', 0), errors='coerce') or 0,
                            "cost": pd.to_numeric(row.get('min_charge_kopo', 0), errors='coerce') or 0
                        },
                        "Kalimalang": {
                            "dist": pd.to_numeric(row.get('dist_kalimalang', 0), errors='coerce') or 0,
                            "cost": pd.to_numeric(row.get('min_charge_kalimalang', 0), errors='coerce') or 0
                        }
                    }
                    
                    st.markdown("---")
                    st.subheader(f"📍 {row.get('city', 'Unknown City')} ({row.get('postal_code', '-')})")
                    show_comparison(row.get('city'), comparison_data)
            
            else:
                st.write("👆 Ketik nama kota di kolom pencarian di atas.")
                
        except Exception as e:
            st.error(f"Gagal membaca CSV. Pastikan format delimiter adalah titik koma (;). Error: {e}")

# --- MODE 2: HITUNG MANUAL ---
else:
    st.header("🧮 Hitung Manual")
    st.caption("Masukkan data jarak dan biaya secara manual untuk membandingkan opsi pengiriman.")
    
    col_input1, col_input2 = st.columns(2)
    
    with col_input1:
        target_city = st.text_input("Nama Kota Tujuan", "Bandung")
    
    st.subheader("Input Parameter Asal")
    
    c1, c2, c3 = st.columns(3)
    
    # Input Banjaran
    with c1:
        st.markdown("##### 🏭 Banjaran")
        d_banjaran = st.number_input("Jarak (km)", min_value=0.0, value=22.0, key="d_b")
        c_banjaran = st.number_input("Biaya (Rp)", min_value=0.0, value=1390000.0, key="c_b")
        
    # Input Kopo
    with c2:
        st.markdown("##### 🏭 Kopo")
        d_kopo = st.number_input("Jarak (km)", min_value=0.0, value=15.0, key="d_k")
        c_kopo = st.number_input("Biaya (Rp)", min_value=0.0, value=1600000.0, key="c_k")
        
    # Input Kalimalang
    with c3:
        st.markdown("##### 🏭 Kalimalang")
        d_kalimalang = st.number_input("Jarak (km)", min_value=0.0, value=0.0, key="d_km")
        c_kalimalang = st.number_input("Biaya (Rp)", min_value=0.0, value=705000.0, key="c_km")
    
    # Tombol Hitung
    if st.button("Bandingkan Opsi", type="primary"):
        manual_data = {
            "Banjaran": {"dist": d_banjaran, "cost": c_banjaran},
            "Kopo": {"dist": d_kopo, "cost": c_kopo},
            "Kalimalang": {"dist": d_kalimalang, "cost": c_kalimalang}
        }
        st.markdown("---")
        show_comparison(target_city, manual_data)
