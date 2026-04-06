import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import os
from PIL import Image
import io
import base64 # Tambahkan library ini untuk render GIF bergerak


# --- 1. TARUH FUNGSI INI DI ATAS (LUAR BLOK APAPUN) ---
def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception as e:
        return None

# Fungsi ambil data dari DB
def jalankan_query(query):
    with sqlite3.connect('sampah.db') as conn:
        return pd.read_sql(query, conn)

st.set_page_config(page_title="Sistem Sampah Mobile", layout="wide")

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
from PIL import Image # Tambahkan library ini untuk memproses gambar
import io

# --- FUNGSI DATABASE (Sama seperti sebelumnya) ---
def jalankan_query(query):
    with sqlite3.connect('sampah.db') as conn:
        return pd.read_sql(query, conn)

def get_list_lokasi():
    with sqlite3.connect('sampah.db') as conn:
        df = pd.read_sql("SELECT nama_unit FROM lokasi", conn)
        return df['nama_unit'].tolist()

def hapus_laporan(id_laporan):
    conn = sqlite3.connect('sampah.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM laporan WHERE id = ?", (id_laporan,))
    conn.commit()
    conn.close()

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="MoniSam Brebes - DLH", layout="wide", page_icon="🚛")

# --- CUSTOM CSS UNTUK MENYAMAKAN UKURAN ---
st.markdown("""
    <style>
    .header-container {
        text-align: center;
        line-height: 1.1;
        margin-top: -10px;
    }
    /* Container khusus agar gambar & animasi punya tinggi yang sama */
    .media-box {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 200px; /* Tentukan tinggi maksimal di sini */
        width: 100%;
        overflow: hidden;
    }
    .media-box img {
        height: 100%; /* Memaksa tinggi gambar memenuhi container 200px */
        width: auto;   /* Lebar mengikuti secara proporsional agar tidak gepeng */
        object-fit: contain;
    }
    </style>
""", unsafe_allow_html=True)

# --- FUNGSI RENDER MEDIA (AGAR PASTI MUNCUL & SEJAJAR) ---
def render_media_fixed(nama_file, is_gif=True):
    path = os.path.join("assets", nama_file)
    if os.path.exists(path):
        with open(path, "rb") as f:
            data = f.read()
            base64_data = base64.b64encode(data).decode()
        
        mime = "image/gif" if is_gif else "image/jpeg"
        # CSS inline di sini untuk memastikan tinggi terkunci 200px
        st.markdown(f'''
            <div style="display: flex; align-items: center; justify-content: center; 
                        height: 200px; background: white; border-radius: 15px; 
                        box-shadow: 0 4px 6px rgba(0,0,0,0.05); overflow: hidden;">
                <img src="data:{mime};base64,{base64_data}" 
                     style="height: 100%; width: auto; object-fit: contain;">
            </div>
        ''', unsafe_allow_html=True)
    else:
        st.error(f"File {nama_file} tidak ada di /assets")

# --- CSS UNTUK JUDUL (TINGGI 200PX) ---
st.markdown("""
    <style>
    /* --- DESAIN UTAMA (LAPTOP / PC) --- */
    .header-container-elegan {
        text-align: center;
        background: linear-gradient(to bottom, #ffffff, #f1f8e9);
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border-bottom: 3px solid #2E7D32;
        height: 200px; 
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center; /* Menjaga logo tetap di tengah */
        line-height: 1.2;
    }

    /* --- DESAIN KHUSUS HP (OTOMATIS AKTIF DI LAYAR KECIL) --- */
    @media (max-width: 640px) {
        .header-container-elegan {
            height: auto !important; /* Biar kotak tidak kepanjangan di HP */
            min-height: 160px !important;
            padding: 15px 5px !important;
            margin-bottom: 10px !important;
        }
        
        .header-container-elegan img {
            width: 100px !important; /* Logo sedikit mengecil di HP agar proporsional */
            height: auto !important;
        }

        .header-container-elegan p {
            font-size: 11px !important; /* Teks dinas menyesuaikan layar HP */
        }
    }
    </style>
""", unsafe_allow_html=True)

# --- RENDER HEADER TIGA KOLOM ---
try:
    # Rasio 3:3:3 agar kotak-kotaknya seimbang
    col_judul, col_pejabat , col_animasi = st.columns([3, 3, 3])

    # PINDAHKAN BARIS DEBUG KE SINI (Harus menjorok ke dalam blok try)
    # st.write(f"Lokasi saat ini: {os.getcwd()}") 

    with col_judul:
        path_logo = "assets/logo_monisam.jpg"
        img_base64 = get_base64_image(path_logo)

        if img_base64:
            # PENTING: Perhatikan huruf f sebelum kutip tiga dan posisi unsafe_allow_html
            st.markdown(
                f"""
                <div style="text-align: center; height: 200px; display: flex; flex-direction: column; justify-content: center; align-items: center; background: white; border-radius: 15px;">
                    <img src="data:image/jpeg;base64,{img_base64}" width="150" style="margin-bottom: 10px;">
                    <div style="height: 3px; width: 60px; background-color: #FFA000; margin: 5px auto;"></div>
                    <p style="margin: 5px 0 0 0; font-size: 14px; color: #1B5E20; font-style: italic; font-weight: 800; line-height: 1.2;">
                        Dinas Lingkungan Hidup<br>Kabupaten Brebes
                    </p>
                </div>
                """, 
                unsafe_allow_html=True
            )
        else:
            st.error("Logo tidak ditemukan")
            
       
    with col_pejabat:
        # Panggil Foto Bupati
        render_media_fixed('bupati.jpg', is_gif=False)

    with col_animasi:
        # Gunakan fungsi yang sudah Anda buat
        render_media_fixed('animasi_sampah.gif', is_gif=True)

    

except Exception as e:
    st.error(f"Terjadi kesalahan pada Header: {e}")

# --- PEMBATAS ---
st.divider()

# --- BARIS SAMBUTAN ---
with st.expander("📝 Klik untuk Membaca Sambutan Kepala Dinas", expanded=False):
    # Rasio kolom disesuaikan agar foto tidak terlalu besar (1 untuk foto, 5 untuk teks)
    col_kadis_foto, col_teks_sambutan = st.columns([1, 5])
    
    with col_kadis_foto:
        # Panggil fungsi render media yang sudah Bapak buat di atas
        # Gunakan height yang sama dengan header (200px) agar serasi
        # Atau jika ingin lebih kecil, kita buat height khusus 150px
        # (Silakan sesuaikan height di fungsi ini jika perlu)
        
        # Opsi A: Menggunakan fungsi yang sudah ada (Tinggi 200px)
        render_media_fixed('kadin.jpg', is_gif=False)
        
        # Opsi B (Manual): Jika ingin fotonya lebih kecil (misal: 120px)
        # st.markdown(f'''
        #     <div style="display: flex; align-items: center; justify-content: center; 
        #                 height: 120px; border-radius: 50%; overflow: hidden; border: 3px solid #2E7D32;">
        #         <img src="data:image/jpeg;base64,{base64.b64encode(open("assets/kadis.jpg", "rb").read()).decode()}" 
        #              style="height: 100%; width: auto; object-fit: cover;">
        #     </div>
        # ''', unsafe_allow_html=True)
        
    with col_teks_sambutan:
        # Gunakan CSS inline untuk mengatur perataan teks agar lurus di tengah foto
        st.markdown("""
            <div style="display: flex; flex-direction: column; justify-content: center; height: 100%; min-height: 150px; padding-left: 15px;">
                <p style="font-style: italic; color: #333; font-size: 16px; margin: 0 0 10px 0;">
                    "Melalui MoniSam, kita wujudkan Brebes yang bersih dan terdigitalisasi.<br>
                    Data sampah yang akurat adalah langkah awal pelestarian lingkungan."
                </p>
                <p style="font-weight: bold; margin: 0; color: #1B5E20; font-size: 15px;">
                    - Kepala Dinas Lingkungan Hidup Kab. Brebes -
                </p>
            </div>
        """, unsafe_allow_html=True)
        
# --- LOGIN SYSTEM & MENU TAB (Lanjutkan kode app.py Anda yang sudah ada di sini) ---
# (Pastikan variable 'auth' session state tetap berjalan)

# Fungsi untuk mengambil daftar nama lokasi dari tabel 'lokasi'
def get_list_lokasi():
    with sqlite3.connect('sampah.db') as conn:
        df = pd.read_sql("SELECT nama_unit FROM lokasi", conn)
        return df['nama_unit'].tolist()

# Fungsi hapus
def hapus_laporan(id_laporan):
    conn = sqlite3.connect('sampah.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM laporan WHERE id = ?", (id_laporan,))
    conn.commit()
    conn.close()

# --- LOGIN SYSTEM ---
if 'auth' not in st.session_state:
    st.session_state['auth'] = False
    st.session_state['role'] = 'publik'

with st.sidebar:
    st.header("🔑 Akses Sistem")
    if not st.session_state['auth']:
        user = st.text_input("Username")
        pw = st.text_input("Password", type="password")
        if st.button("Login"):
            res = jalankan_query(f"SELECT role FROM users WHERE username='{user}' AND password='{pw}'")
            if not res.empty:
                st.session_state['auth'] = True
                st.session_state['role'] = res['role'][0]
                st.rerun()
            else:
                st.error("Login Gagal")
    else:
        st.success(f"Login: {st.session_state['role']}")
        if st.button("Logout"):
            st.session_state['auth'] = False
            st.session_state['role'] = 'publik'
            st.rerun()

# --- HALAMAN UTAMA ---
# --- st.title("🚛 Monitoring Pengelolaan Sampah")

tab1, tab2, tab3 = st.tabs(["📍 Lokasi TPS3R/TPA", "📊 Laporan Berkala", "📝 Input Data"])

import folium
from streamlit_folium import st_folium

with tab1:
    st.subheader("📍 Peta Sebaran Lokasi TPA, TPS3R, & TPST")
    
    # QUERY DIPERBARUI: Menambahkan loc.kecamatan
    df_peta = jalankan_query("""
        SELECT l.nama_unit, l.lat, l.lon, l.tipe, l.kecamatan,
        COALESCE(SUM(lap.berat_kg), 0) / 1000.0 as total_ton
        FROM lokasi l
        LEFT JOIN laporan lap ON lap.admin_input = l.nama_unit
        GROUP BY l.id
    """)

    if not df_peta.empty:
        m = folium.Map(location=[-6.9700, 108.9200], zoom_start=11, tiles="OpenStreetMap")

        def get_color(tipe):
            if tipe == 'TPA': return '#FF0000'
            elif tipe == 'TPST': return '#FFA500'
            elif tipe == 'TPS3R': return '#228B22'
            else: return '#808080'

        for index, row in df_peta.iterrows():
            warna_titik = get_color(row['tipe'])
            
            # POPUP DIPERBARUI: Menampilkan Nama Kecamatan
            isi_popup = f"""
                <div style='font-family: Arial; width: 180px;'>
                    <b style='color:{warna_titik};'>{row['tipe']} {row['nama_unit']}</b><br>
                    <small>Kecamatan: {row['kecamatan']}</small>
                    <hr>
                    Total Terkelola: <b>{row['total_ton']:.2f} Ton</b>
                </div>
            """
            
            folium.CircleMarker(
                location=[row['lat'], row['lon']],
                radius=9,
                popup=folium.Popup(isi_popup, max_width=250),
                color=warna_titik,
                fill=True,
                fill_color=warna_titik,
                fill_opacity=0.7
            ).add_to(m)

        st_folium(m, width=1200, height=500, returned_objects=[])
        
        # 1. Siapkan data dengan kolom nomor
        df_tampilan = df_peta[['nama_unit', 'kecamatan', 'tipe', 'total_ton']].copy()
        df_tampilan.insert(0, 'No', range(1, len(df_tampilan) + 1))

        # 2. Tampilkan dengan konfigurasi lebar kolom (column_config)
        st.dataframe(
            df_tampilan,
            use_container_width=True,
            hide_index=True,
            column_config={
                "No": st.column_config.Column(
                    "No",
                    width=20,  # Menggunakan angka piksel (sangat ramping)
                    help="Nomor Urut"
                ),
                "nama_unit": st.column_config.Column(
                    "Nama Unit/Lokasi",
                    width="large",  # Nama lokasi biasanya panjang, jadi dibuat paling lebar
                ),
                "kecamatan": st.column_config.Column(
                    "Kecamatan",
                    width="medium", # Ukuran sedang untuk nama kecamatan
                ),
                "tipe": st.column_config.Column(
                    "Tipe",
                    width="small",  # TPA/TPS3R teksnya pendek
                ),
                "total_ton": st.column_config.NumberColumn(
                    "Total (Ton)",
                    width="small",  # Angka dibuat pas dengan teksnya
                    format="%.2f"   # Dua angka di belakang koma
                )
            }
        )

with tab2:
    st.subheader("📊 Laporan Pengelolaan Sampah Berkala")
    
    # Query gabungan
    df_all = jalankan_query("""
        SELECT l.id, l.tanggal, l.berat_kg, l.kategori, l.admin_input as lokasi, loc.kecamatan 
        FROM laporan l
        JOIN lokasi loc ON l.admin_input = loc.nama_unit
    """)
    
    if not df_all.empty:
        df_all['tanggal'] = pd.to_datetime(df_all['tanggal'])
        df_all['bulan'] = df_all['tanggal'].dt.month_name()
        df_all['tahun'] = df_all['tanggal'].dt.year

        # --- PERBAIKAN DI SINI (Pastikan menjorok ke dalam) ---
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            # Ambil data kecamatan, buang yang kosong, lalu urutkan
            list_kec_raw = df_all['kecamatan'].dropna().unique().tolist()
            list_kec = ["Semua Kecamatan"] + sorted([str(k) for k in list_kec_raw])
            sel_kec = st.selectbox("📍 Pilih Wilayah", list_kec)
            
        with col_f2:
            sel_bulan = st.selectbox("📅 Pilih Bulan", df_all['bulan'].unique())
            
        with col_f3:
            sel_tahun = st.selectbox("🗓️ Pilih Tahun", sorted(df_all['tahun'].unique(), reverse=True))

        # Filter Logic (Juga harus menjorok)
        df_filtered = df_all[(df_all['bulan'] == sel_bulan) & (df_all['tahun'] == sel_tahun)]
        if sel_kec != "Semua Kecamatan":
            df_filtered = df_filtered[df_filtered['kecamatan'] == sel_kec]
            
        # Tampilkan Metric
        st.write("---")
        total_berat = df_filtered['berat_kg'].sum()
        st.metric(f"Total Sampah ({sel_kec})", f"{total_berat:,.1f} Kg")
        
        # Tabel Data
        st.dataframe(df_filtered[['tanggal', 'kecamatan', 'lokasi', 'kategori', 'berat_kg']], 
                     use_container_width=True, hide_index=True)
    else:
        st.info("Belum ada data laporan untuk periode ini.")

with tab3:
    if st.session_state['role'] in ['admin_lh', 'super_admin']:
        st.subheader("📝 Form Input Sampah Harian & Foto Kondisi")
        
        # Mengambil daftar lokasi asli dari Database
        list_lokasi = get_list_lokasi()
        
        if not list_lokasi:
            st.warning("⚠️ Belum ada lokasi TPS3R/TPA di database. Silakan import data lokasi terlebih dahulu.")
        else:
            with st.form("form_sampah_lokasi", clear_on_submit=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    lokasi_pilih = st.selectbox("Pilih Lokasi Unit", list_lokasi)
                    tgl = st.date_input("Tanggal Operasional", datetime.now())
                
                with col2:
                    kategori = st.selectbox("Kategori Sampah", ["Organik", "Anorganik", "Residu/B3"])
                    berat = st.number_input("Berat Masuk (Kg)", min_value=0.0, step=1.0) # Gunakan step bulat agar lebih cepat di HP
                
                # --- KOMPONEN BARU: INPUT FOTO ---
                # Di HP, ini otomatis membuka Kamera atau Galeri
                uploaded_file = st.file_uploader("📷 Ambil Foto Kondisi TPS", type=["jpg", "png", "jpeg"])
                
                submit = st.form_submit_button("Simpan Laporan & Foto")
                
                if submit:
                    if berat <= 0:
                        st.error("Berat sampah harus lebih dari 0!")
                    elif uploaded_file is None:
                        st.error("⚠️ Wajib mengunggah foto kondisi TPS!")
                    else:
                        # 1. Simpan Laporan ke Database
                        conn = sqlite3.connect('sampah.db')
                        # Kita gunakan waktu saat ini (timestamp) untuk nama file foto agar unik
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        nama_foto_baru = f"{lokasi_pilih}_{kategori}_{timestamp}.jpg"
                        
                        try:
                            conn.execute("""
                                INSERT INTO laporan (tanggal, berat_kg, kategori, admin_input, foto_path) 
                                VALUES (?, ?, ?, ?, ?)
                            """, (tgl, berat, kategori, lokasi_pilih, nama_foto_baru))
                            
                            conn.commit()
                            
                            # 2. Simpan File Foto ke Folder 'data_foto'
                            filepath_simpan = os.path.join("data_foto", nama_foto_baru)
                            with open(filepath_simpan, "wb") as f:
                                f.write(uploaded_file.getvalue())
                                
                            st.success(f"✅ Data sampah di {lokasi_pilih} dan foto berhasil disimpan!")
                            # Hapus cache grafik agar update
                            st.cache_data.clear()
                            
                        except Exception as e:
                            st.error(f"❌ Gagal menyimpan: {e}")
                        finally:
                            conn.close()

        # --- RIWAYAT INPUT (Updated with Foto Preview) ---
        st.divider()
        st.subheader("🕒 Riwayat Input Terakhir")
        df_riwayat = jalankan_query("SELECT id, tanggal, berat_kg, kategori, admin_input as lokasi, foto_path FROM laporan ORDER BY id DESC LIMIT 5")
        
        if not df_riwayat.empty:
            # Kita gunakan expander agar riwayat tidak menumpuk di HP
            for index, row in df_riwayat.iterrows():
                with st.expander(f"Data {row['lokasi']} - {row['tanggal']} ({row['kategori']})"):
                    st.write(f"Berat: {row['berat_kg']} Kg")
                    # Tampilkan preview foto jika ada
                    if row['foto_path']:
                        # Pastikan row['foto_path'] tidak kosong dan tipenya adalah string
                        if pd.notnull(row['foto_path']) and isinstance(row['foto_path'], str):
                            foto_full_path = os.path.join("data_foto", row['foto_path'])
                            # ... lanjut proses menampilkan foto ...
                        else:
                            foto_full_path = None
                            # Anda bisa tambahkan aksi lain jika foto tidak ada, misal tampilkan gambar default
                    else:
                        st.info("Tidak ada foto.")
                    
                    # Tombol hapus (Opsional, gunakan ID)
                    if st.button(f"Hapus ID {row['id']}", key=f"hapus_{row['id']}"):
                        conn = sqlite3.connect('sampah.db')
                        conn.execute("DELETE FROM laporan WHERE id = ?", (row['id'],))
                        conn.commit()
                        conn.close()
                        st.warning(f"Data ID {row['id']} telah dihapus.")
                        st.rerun()
        else:
            st.info("Belum ada riwayat input.")
    else:
        st.warning("Akses Terbatas.")
        
# --- DAFTAR KECAMATAN UNTUK DROPDOWN ---
LIST_KECAMATAN = ["Brebes", "Wanasari", "Bulakamba", "Tanjung", "Losari", "Kersana", 
                  "Ketanggungan", "Larangan", "Banjarharjo", "Salem", "Bantarkawung", 
                  "Bumiayu", "Sirampog", "Tonjong", "Songgom", "Jatibarang", "Paguyangan"]

if st.session_state['role'] in ['admin_lh', 'super_admin']:
    st.divider()
    st.subheader("⚙️ Manajemen Master Data Lokasi (TPS3R/TPA)")
    
    # 1. TAMPILAN EDIT & HAPUS (Live Editor)
    st.write("**Double klik pada sel untuk mengedit data, lalu klik 'Simpan Perubahan'**")
    df_lokasi_edit = jalankan_query("SELECT id, nama_unit, kecamatan, tipe, lat, lon FROM lokasi")
    
    if not df_lokasi_edit.empty:
        # Menggunakan data_editor agar bisa diedit langsung seperti Excel
        edited_df = st.data_editor(
            df_lokasi_edit,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "kecamatan": st.column_config.SelectboxColumn("Kecamatan", options=LIST_KECAMATAN, required=True),
                "tipe": st.column_config.SelectboxColumn("Tipe", options=["TPS3R", "TPA", "TPST", "Pengepul"], required=True),
            },
            hide_index=True,
            use_container_width=True,
            key="editor_lokasi"
        )

        col_save, col_del = st.columns([1, 4])
        with col_save:
            if st.button("💾 Simpan Perubahan"):
                conn = sqlite3.connect('sampah.db')
                for index, row in edited_df.iterrows():
                    conn.execute("""
                        UPDATE lokasi SET nama_unit=?, kecamatan=?, tipe=?, lat=?, lon=? WHERE id=?
                    """, (row['nama_unit'], row['kecamatan'], row['tipe'], row['lat'], row['lon'], row['id']))
                conn.commit()
                conn.close()
                st.success("✅ Perubahan data lokasi berhasil disimpan!")
                st.rerun()

        with col_del:
            # Fitur Hapus Spesifik
            id_hapus = st.number_input("Masukkan ID Unit yang ingin dihapus", min_value=0, step=1)
            if st.button("🗑️ Hapus Unit Permanen"):
                if id_hapus > 0:
                    conn = sqlite3.connect('sampah.db')
                    conn.execute("DELETE FROM lokasi WHERE id = ?", (id_hapus,))
                    conn.commit()
                    conn.close()
                    st.warning(f"⚠️ Unit dengan ID {id_hapus} telah dihapus.")
                    st.rerun()
    
    st.write("---")
    
    # 2. FORM TAMBAH LOKASI BARU
    with st.expander("➕ Tambah Unit Baru (Manual)", expanded=False):
        with st.form("form_tambah_manual"):
            c1, c2 = st.columns(2)
            with c1:
                n_nama = st.text_input("Nama Unit")
                n_kec = st.selectbox("Kecamatan", LIST_KECAMATAN)
            with c2:
                n_tipe = st.selectbox("Tipe Fasilitas", ["TPS3R", "TPA", "TPST"])
                n_koordinat = st.text_input("Koordinat (Contoh: -6.8, 109.0)")

            if st.form_submit_button("Simpan Unit Baru"):
                if n_nama:
                    n_lat, n_lon = 0.0, 0.0
                    if n_koordinat:
                        try: n_lat, n_lon = map(float, n_koordinat.split(','))
                        except: pass
                    
                    conn = sqlite3.connect('sampah.db')
                    conn.execute("""
                        INSERT INTO lokasi (nama_unit, kecamatan, tipe, lat, lon) 
                        VALUES (?, ?, ?, ?, ?)
                    """, (n_nama, n_kec, n_tipe, n_lat, n_lon))
                    conn.commit()
                    conn.close()
                    st.success(f"✅ {n_nama} berhasil ditambahkan!")
                    st.rerun()
        
