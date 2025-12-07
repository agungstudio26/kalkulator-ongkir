import streamlit as st
import pandas as pd

# Konfigurasi Halaman
st.set_page_config(page_title="Cek Logistik & Ongkir", layout="wide")

st.title("📦 Cek Logistik & Ongkir (Python)")
st.markdown("Analisis jarak dan biaya pengiriman multi-origin")

# 1. Upload File
uploaded_file = st.file_uploader("Upload file distance.csv", type=['csv'])

if uploaded_file is not None:
    try:
        # Membaca CSV dengan delimiter titik koma (;)
        df = pd.read_csv(uploaded_file, sep=';')

        # Pastikan kolom numerik dibaca sebagai angka (handling error parsing)
        numeric_cols = [
            'dist_banjaran', 'dist_kopo', 'dist_kalimalang',
            'min_charge_banjaran', 'min_charge_kopo', 'min_charge_kalimalang'
        ]
        
        for col in numeric_cols:
            if col in df.columns:
                # Mengubah non-numeric jadi NaN, lalu diisi 0
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # 2. Search Bar
        search_term = st.text_input("🔍 Cari Kota atau Kode Pos...", "")

        # Filter Data
        if search_term:
            # Cari di kolom city atau postal_code (case insensitive)
            mask = (
                df['city'].astype(str).str.contains(search_term, case=False, na=False) | 
                df['postal_code'].astype(str).str.contains(search_term, case=False, na=False)
            )
            filtered_df = df[mask]
        else:
            filtered_df = df.head(20) # Tampilkan 20 data awal jika tidak mencari

        st.success(f"Menampilkan {len(filtered_df)} hasil")

        # 3. Tampilkan Data Cards
        for index, row in filtered_df.iterrows():
            with st.container():
                st.markdown("---")
                
                # Header Kartu
                col_info, col_zone = st.columns([4, 1])
                with col_info:
                    st.subheader(f"📍 {row['city']}")
                    st.caption(f"Kode Pos: {row['postal_code']}")
                with col_zone:
                    st.info(f"{row.get('zone_category', '-')}")

                # Logika Mencari Termurah & Terdekat
                origins = ['banjaran', 'kopo', 'kalimalang']
                
                # Ambil nilai biaya & jarak
                costs = {org: row[f'min_charge_{org}'] for org in origins}
                dists = {org: row[f'dist_{org}'] for org in origins}
                
                # Hitung minimum (abaikan nilai 0)
                valid_costs = [c for c in costs.values() if c > 0]
                min_cost = min(valid_costs) if valid_costs else 0
                
                valid_dists = [d for d in dists.values() if d > 0]
                min_dist = min(valid_dists) if valid_dists else 0

                # Tampilkan 3 Kolom Asal
                c1, c2, c3 = st.columns(3)

                def show_metric(col, label, key_suffix):
                    val_cost = costs[key_suffix]
                    val_dist = dists[key_suffix]
                    
                    is_cheapest = (val_cost == min_cost and val_cost > 0)
                    is_closest = (val_dist == min_dist)
                    
                    with col:
                        # Styling sederhana
                        border_color = "green" if is_cheapest else "grey"
                        if is_cheapest:
                            st.success(f"**{label}** (Termurah)")
                        elif is_closest:
                            st.warning(f"**{label}** (Terdekat)")
                        else:
                            st.write(f"**{label}**")
                            
                        st.write(f"📏 Jarak: {val_dist} km")
                        st.write(f"💰 Rp {val_cost:,.0f}")

                show_metric(c1, "Banjaran", "banjaran")
                show_metric(c2, "Kopo", "kopo")
                show_metric(c3, "Kalimalang", "kalimalang")

    except Exception as e:
        st.error(f"Error membaca file CSV: {e}")
        st.write("Pastikan format file CSV menggunakan pemisah titik koma (;)")
else:
    st.info("Silakan upload file `distance.csv` untuk memulai.")
