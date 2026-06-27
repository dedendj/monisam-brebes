import streamlit as st
import pandas as pd
from datetime import datetime
import os
import io
import base64
import bcrypt  # Pastikan sudah install: pip install bcrypt
import folium
from streamlit_folium import st_folium

# Driver PostgreSQL
import psycopg2
from psycopg2.extras import RealDictCursor

# ==============================================================================
# INISIALISASI STREAMLIT SESSION STATE (Taruh di bagian paling atas app.py)
# ==============================================================================
if 'auth' not in st.session_state:
    st.session_state['auth'] = False

if 'role' not in st.session_state:
    st.session_state['role'] = None

if 'username' not in st.session_state:
    st.session_state['username'] = ""

if 'nama_user' not in st.session_state:
    st.session_state['nama_user'] = 'Pengunjung'

# ==============================================================================
# DATA MASTER GLOBAL
# ==============================================================================
LIST_KECAMATAN = ["Brebes", "Wanasari", "Bulakamba", "Tanjung", "Losari", "Kersana", "Ketanggungan", "Larangan", "Banjarharjo", "Salem", "Bantarkawung", "Bumiayu", "Sirampog", "Tonjong", "Songgom", "Jatibarang", "Paguyangan"]
LIST_TIPE = ["TPS3R", "TPA", "TPST", "Bank Sampah Induk", "Bank Sampah Unit"]

# Pemetaan Kategori & Sub-Kategori sesuai instruksi
DIKTI_KATEGORI = {
    "Organik": ["Sisa Makanan", "Sampah Taman", "Kertas atau Karton", "Karet dan Kulit"],
    "Anorganik": ["Plastik Keras", "Plastik Elastis", "Kain atau Textile", "Logam"],
    "Residu": [],
    "B3": [],
    "Lainnya": []
}

# ==============================================================================
# 1. INITIAL CONFIGURATION & BASE FUNCTIONS (POSTGRESQL CENTRIC)
# ==============================================================================
st.set_page_config(page_title="MoniSa Brebes - DLH", layout="wide", page_icon="🚛")

def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception:
        return None

def jalankan_query(query, params=None, ambil_data=True):
    """Fungsi universal untuk menjalankan query PostgreSQL menggunakan Streamlit Secrets"""
    db_url = st.secrets["postgres"]["url"]
    conn = None
    
    # Proteksi otomatis jika params yang dimasukkan bukan berbentuk tuple/list
    if params is not None and not isinstance(params, (tuple, list)):
        params = (params,)
        
    try:
        conn = psycopg2.connect(db_url)
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params or ())
            if ambil_data:
                if cur.description:
                    hasil = cur.fetchall()
                    conn.commit()
                    return pd.DataFrame(hasil)
                else:
                    conn.commit()
                    return pd.DataFrame()
            else:
                conn.commit()
                return None
    except Exception as e:
        st.error(f"❌ Eror Database: {e}")
        if conn:
            conn.rollback()
        return pd.DataFrame()
    finally:
        if conn:
            conn.close()

def get_list_lokasi_by_kecamatan(kecamatan):
    df = jalankan_query("SELECT nama_unit FROM lokasi WHERE kecamatan = %s ORDER BY nama_unit ASC", (kecamatan,))
    if not df.empty:
        return df['nama_unit'].tolist()
    return []

def render_ikhtisar_sampah():
    """Fungsi helper untuk menampilkan KPI ringkasan sampah di atas peta"""
    st.markdown("#### 📊 Ikhtisar Pengelolaan Sampah Kabupaten Brebes")
    
    df_summary = jalankan_query("SELECT COUNT(id) as total_laporan, SUM(berat_kg) as total_berat FROM laporan")
    df_kategori = jalankan_query("SELECT kategori, SUM(berat_kg) as berat FROM laporan GROUP BY kategori")
    df_lokasi_count = jalankan_query("SELECT COUNT(id) as total_lokasi FROM lokasi")
    
    total_laporan = df_summary['total_laporan'].iloc[0] if not df_summary.empty else 0
    total_berat_kg = df_summary['total_berat'].iloc[0] if not df_summary.empty and df_summary['total_berat'].iloc[0] is not None else 0
    total_berat_ton = total_berat_kg / 1000.0
    total_lokasi = df_lokasi_count['total_lokasi'].iloc[0] if not df_lokasi_count.empty else 0
    
    organik, anorganik, residu, b3, lainnya = 0, 0, 0, 0, 0
    if not df_kategori.empty:
        for _, row in df_kategori.iterrows():
            kat = str(row['kategori']).strip()
            if kat == 'Organik': organik = row['berat']
            elif kat == 'Anorganik': anorganik = row['berat']
            elif kat == 'Residu': residu = row['berat']
            elif kat == 'B3': b3 = row['berat']
            else: lainnya += row['berat']
            
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1: st.metric(label="♻️ Total Sampah Terkelola", value=f"{total_berat_ton:,.2f} Ton")
    with col_m2: st.metric(label="📍 Unit Infrastruktur Aktif", value=f"{total_lokasi} Titik")
    with col_m3: st.metric(label="📋 Total Laporan Masuk", value=f"{total_laporan} Data")
        
    st.markdown("<small style='color:gray;'><b>🗂️ Komposisi Sampah Berdasarkan Jenis Utama:</b></small>", unsafe_allow_html=True)
    col_c1, col_c2, col_c3, col_c4, col_c5 = st.columns(5)
    with col_c1: st.metric(label="🍏 Organik", value=f"{organik:,.1f} Kg")
    with col_c2: st.metric(label="🍾 Anorganik", value=f"{anorganik:,.1f} Kg")
    with col_c3: st.metric(label="🗑️ Residu", value=f"{residu:,.1f} Kg")
    with col_c4: st.metric(label="🚨 B3", value=f"{b3:,.1f} Kg")
    with col_c5: st.metric(label="📦 Lainnya", value=f"{lainnya:,.1f} Kg")
    st.write("---")

# ==============================================================================
# 2. SINKRONISASI DATABASE POSTGRESQL AUTOMATIC INITIALIZATION
# ==============================================================================
def init_db_otomatis_postgres():
    # 1. Buat Tabel Lokasi
    jalankan_query("""
    CREATE TABLE IF NOT EXISTS lokasi (
        id SERIAL PRIMARY KEY,
        nama_unit TEXT NOT NULL,
        lat DOUBLE PRECISION,
        lon DOUBLE PRECISION,
        tipe TEXT,
        kecamatan TEXT
    )
    """, ambil_data=False)
    
    # 2. Buat Tabel Laporan (Ditambah kolom sub_kategori)
    jalankan_query("""
    CREATE TABLE IF NOT EXISTS laporan (
        id SERIAL PRIMARY KEY,
        tanggal DATE,
        berat_kg DOUBLE PRECISION,
        kategori TEXT,
        sub_kategori TEXT,
        admin_input TEXT,
        foto_path TEXT
    )
    """, ambil_data=False)
    
    # Pastikan kolom sub_kategori eksis jika tabel sudah dibuat sebelumnya
    try:
        jalankan_query("ALTER TABLE laporan ADD COLUMN IF NOT EXISTS sub_kategori TEXT", ambil_data=False)
    except Exception:
        pass
    
    # 3. Buat Tabel Users Baru
    jalankan_query("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT,
        role TEXT,
        nama_lengkap TEXT,
        nip_atau_id TEXT,
        no_hp TEXT,
        alamat TEXT,
        status TEXT DEFAULT 'pending',
        foto_profil TEXT
    )
    """, ambil_data=False)
    
    # 4. Amankan Data Master Admin Utama Dinas LH (lh2026!)
    password_resmi = "lh2026!".encode('utf-8')
    hashed_password = bcrypt.hashpw(password_resmi, bcrypt.gensalt()).decode('utf-8')
    
    df_admin = jalankan_query("SELECT password_hash FROM users WHERE username = 'dinas_lh'")
    
    if df_admin.empty:
        jalankan_query("""
            INSERT INTO users (username, nama_lengkap, password_hash, role, nip_atau_id, no_hp, alamat, status) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'approved')
        """, ('dinas_lh', 'Admin Dinas LH', hashed_password, 'admin_lh', '198501012010011001', '08123456789', 'Kantor DLH Kabupaten Brebes'), ambil_data=False)

# Eksekusi Inisialisasi Cloud DB
init_db_otomatis_postgres()

def register_user_with_pending(username, nama, password, role, nip_atau_id, no_hp, alamat):
    username_clean = str(username).strip().lower()
    nama_clean = str(nama).strip()
    nip_clean = str(nip_atau_id).strip()
    no_hp_clean = str(no_hp).strip()
    alamat_clean = str(alamat).strip()
    
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    df_check = jalankan_query("SELECT id FROM users WHERE username = %s", (username_clean,))
    if not df_check.empty:
        st.error("⚠️ Username sudah terdaftar! Silakan gunakan username lain.")
        return False
        
    try:
        jalankan_query("""
            INSERT INTO users (username, nama_lengkap, password_hash, role, nip_atau_id, no_hp, alamat, status) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
        """, (username_clean, nama_clean, hashed_password, role, nip_clean, no_hp_clean, alamat_clean), ambil_data=False)
        return True
    except Exception as e:
        st.error(f"❌ Gagal menyimpan ke database cloud: {e}")
        return False

def proses_login(username, password):
    df_user = jalankan_query("SELECT password_hash, role, status, nama_lengkap FROM users WHERE username = %s", (username.strip().lower(),))
    
    if not df_user.empty:
        hashed = df_user['password_hash'].iloc[0]
        role = df_user['role'].iloc[0]
        status = df_user['status'].iloc[0]
        nama_lengkap = df_user['nama_lengkap'].iloc[0]
        
        if bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8')):
            if status != 'approved':
                st.error("⚠️ Akun Anda belum disetujui oleh Admin Dinas LH. Silakan hubungi admin.")
                return None
            return {"role": role, "nama": nama_lengkap}
    st.error("❌ Username atau Password salah.")
    return None

def get_pending_users():
    return jalankan_query("SELECT id, username, nama_lengkap, role, nip_atau_id, no_hp, alamat FROM users WHERE status = 'pending'")
    
def update_user_status(user_id, status_baru):
    jalankan_query("UPDATE users SET status = %s WHERE id = %s", (status_baru, int(user_id)), ambil_data=False)

# ==============================================================================
# 3. CUSTOM STYLING & MEDIA RENDERERS
# ==============================================================================
st.markdown("""
    <style>
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
        align-items: center;
        line-height: 1.2;
    }
    </style>
""", unsafe_allow_html=True)

def render_media_fixed(nama_file, is_gif=True):
    path = os.path.join("assets", nama_file)
    if os.path.exists(path):
        with open(path, "rb") as f:
            data = f.read()
            base64_data = base64.b64encode(data).decode()
        mime = "image/gif" if is_gif else "image/jpeg"
        st.markdown(f'''
            <div style="display: flex; align-items: center; justify-content: center; 
                        height: 200px; background: white; border-radius: 15px; 
                        box-shadow: 0 4px 6px rgba(0,0,0,0.05); overflow: hidden;">
                <img src="data:{mime};base64,{base64_data}" style="height: 100%; width: auto; object-fit: contain;">
            </div>
        ''', unsafe_allow_html=True)
    else:
        st.error(f"File {nama_file} tidak ada di /assets")

# ==============================================================================
# 4. VIEWS & SYSTEM PAGES
# ==============================================================================
def halaman_registrasi():
    st.subheader("📝 Pendaftaran Akun Operator Baru")
    st.write("Silakan ajukan akun baru. Pendaftaran memerlukan verifikasi internal dari Dinas Lingkungan Hidup.")
    
    with st.form("form_registrasi", clear_on_submit=False):
        col_reg1, col_reg2 = st.columns(2)
        with col_reg1:
            nama_lengkap = st.text_input("Nama Lengkap")
            nip_atau_id = st.text_input("NIP / NIK / ID Petugas")
            no_hp = st.text_input("No. HP / WhatsApp (Aktif)")
        with col_reg2:
            username = st.text_input("Username (untuk login)")
            password = st.text_input("Password", type="password")
            role_pilih = st.selectbox("Mendaftar Sebagai", ["petugas_lapangan", "admin_lh"],
                                      format_func=lambda x: "Petugas Lapangan (Input Data)" if x == "petugas_lapangan" else "Admin Dinas (Monitoring & Master Data)")
        
        alamat_domisili = st.text_area("Alamat Domisili Sekarang")
        submit_reg = st.form_submit_button("Ajukan Pendaftaran")
        
        if submit_reg:
            if not nama_lengkap or not username or not password or not nip_atau_id or not no_hp or not alamat_domisili:
                st.warning("⚠️ Semua kolom wajib diisi!")
            else:
                sukses = register_user_with_pending(username, nama_lengkap, password, role_pilih, nip_atau_id, no_hp, alamat_domisili)
                if sukses:
                    st.success("🎉 Pengajuan berhasil! Akun berstatus 'Pending' menunggu verifikasi Admin Dinas LH.")

def halaman_approval_admin():
    st.subheader("👥 Verifikasi & Persetujuan Akun Operator Baru")
    pendaftar_pending = get_pending_users()
    
    if pendaftar_pending.empty:
        st.info("ℹ️ Tidak ada pengajuan akun baru saat ini.")
    else:
        for index, row in pendaftar_pending.iterrows():
            u_id = row['id']
            u_username = row['username']
            u_nama = row['nama_lengkap']
            u_role = row['role']
            u_nip = row['nip_atau_id']
            u_no_hp = row['no_hp'] if pd.notnull(row['no_hp']) else "—"
            u_alamat = row['alamat'] if pd.notnull(row['alamat']) else "—"
            
            with st.container(key=f"container_pending_{u_id}"):
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.markdown(f"**Nama:** {u_nama} (`{u_username}`)")
                    st.markdown(f"📱 **No. HP/WA:** {u_no_hp} | 🏠 **Alamat:** {u_alamat}")
                    st.caption(f"NIP/ID: {u_nip} | Peran: {u_role}")
                with col2:
                    if st.button("Setujui ✔️", key=f"app_{u_id}", type="primary", use_container_width=True):
                        update_user_status(u_id, 'approved')
                        st.success(f"Akun {u_username} disetujui!")
                        st.rerun()
                with col3:
                    if st.button("Tolak ❌", key=f"rej_{u_id}", type="secondary", use_container_width=True):
                        update_user_status(u_id, 'rejected')
                        st.warning(f"Akun {u_username} ditolak.")
                        st.rerun()
            st.markdown("---")

    st.write("#") 
    st.subheader("🗂️ Kendali Status & Daftar Operator MoniSa")
    
    operator_data = jalankan_query("SELECT id, username, nama_lengkap, role, nip_atau_id, no_hp, alamat, status FROM users WHERE status = 'approved' ORDER BY nama_lengkap ASC")
    
    if operator_data.empty:
        st.warning("⚠️ Belum ada petugas atau operator yang terdaftar di sistem.")
    else:
        for index, row in operator_data.iterrows():
            status_current = str(row['status']).lower()
            is_aktif = status_current in ['approved', 'aktif']
            border_color = "🟢" if is_aktif else "🔴"
            status_text = "Aktif" if is_aktif else "Non-Aktif (Ditangguhkan)"
            
            with st.container(border=True):
                c_info, c_status, c_aksi = st.columns([3, 1, 1])
                with c_info:
                    st.markdown(f"**{row['nama_lengkap']}** (`{row['username']}`)")
                    st.caption(f"NIP/NIK: {row['nip_atau_id']} | Peran: **{row['role']}**")
                with c_status:
                    st.write("")
                    if is_aktif: st.success(f"{border_color} {status_text}")
                    else: st.error(f"{border_color} {status_text}")
                with c_aksi:
                    st.write("")
                    if is_aktif:
                        if st.button("🛑 Tangguhkan", key=f"suspend_{row['id']}", type="secondary", use_container_width=True):
                            jalankan_query("UPDATE users SET status = 'nonaktif' WHERE id = %s", (int(row['id']),), ambil_data=False)
                            st.warning(f"Akses untuk {row['username']} dinonaktifkan!")
                            st.rerun()
                    else:
                        if st.button("🟢 Aktifkan", key=f"reactivate_{row['id']}", type="primary", use_container_width=True):
                            jalankan_query("UPDATE users SET status = 'approved' WHERE id = %s", (int(row['id']),), ambil_data=False)
                            st.success(f"Akses untuk {row['username']} diaktifkan kembali!")
                            st.rerun()
                            
                    if st.button("🔑 Reset Pass", key=f"reset_pass_{row['id']}", use_container_width=True):
                        pass_default_bytes = "123456".encode('utf-8')
                        hashed_default = bcrypt.hashpw(pass_default_bytes, bcrypt.gensalt()).decode('utf-8')
                        jalankan_query("UPDATE users SET password_hash = %s WHERE id = %s", (hashed_default, int(row['id'])), ambil_data=False)
                        st.info(f"🔑 Password {row['username']} di-reset menjadi: 123456")

def halaman_profil_user():
    st.subheader("👤 Profil Pengguna")
    username_aktif = st.session_state.get('username', '')
    
    if not username_aktif:
        st.error("❌ Sesi login tidak terbaca. Silakan login kembali.")
        return

    df_user = jalankan_query("SELECT username, nama_lengkap, role, status, foto_profil, no_hp, alamat FROM users WHERE username = %s", (username_aktif,))
    
    if not df_user.empty:
        user_data = df_user.iloc[0]
        no_hp_sekarang = user_data['no_hp'] if pd.notnull(user_data['no_hp']) else "-"
        alamat_sekarang = user_data['alamat'] if pd.notnull(user_data['alamat']) else "-"
        
        col_foto, col_data = st.columns([1, 3])
        with col_foto:
            foto_db = user_data.get('foto_profil')
            avatar_default = "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"
            if foto_db and pd.notnull(foto_db) and os.path.exists(os.path.join("data_profil", foto_db)):
                st.image(os.path.join("data_profil", foto_db), width=130)
            else:
                st.image(avatar_default, width=130)
            
        with col_data:
            st.markdown(f"### **{user_data['nama_lengkap']}**")
            st.text(f"ID Akun / Username : {user_data['username']}")
            st.markdown(f"Tingkat Akses : `{user_data['role']}`")
            st.markdown(f"📞 **No. HP :** {no_hp_sekarang}")
            st.markdown(f"🏠 **Alamat :** {alamat_sekarang}")
            st.success("🟢 Akun Terverifikasi & Aktif")

        st.write("---")
        with st.expander("📝 Edit Informasi Profil & Foto"):
            with st.form("form_edit_profil", clear_on_submit=False):
                nama_baru = st.text_input("Nama Lengkap Baru", value=user_data['nama_lengkap'])
                no_hp_baru = st.text_input("Nomor HP Baru", value=no_hp_sekarang if no_hp_sekarang != "-" else "")
                alamat_baru = st.text_area("Alamat Lengkap Baru", value=alamat_sekarang if alamat_sekarang != "-" else "")
                file_foto = st.file_uploader("Pilih Foto (Maks 500 KB)", type=["jpg", "jpeg", "png"])
                
                btn_simpan = st.form_submit_button("💾 Simpan Perubahan")
                if btn_simpan:
                    nama_file_foto = user_data.get('foto_profil')
                    if file_foto is not None and file_foto.size <= 500 * 1024:
                        if not os.path.exists("data_profil"): os.makedirs("data_profil")
                        ekstensi = file_foto.name.split('.')[-1]
                        nama_file_foto = f"profile_{username_aktif}.{ekstensi}"
                        with open(os.path.join("data_profil", nama_file_foto), "wb") as f:
                            f.write(file_foto.getvalue())
                    
                    jalankan_query("""
                        UPDATE users SET nama_lengkap = %s, no_hp = %s, alamat = %s, foto_profil = %s WHERE username = %s
                    """, (nama_baru.strip(), no_hp_baru.strip(), alamat_baru.strip(), nama_file_foto, username_aktif), ambil_data=False)
                    st.session_state['nama_user'] = nama_baru.strip()
                    st.success("✅ Profil berhasil diperbarui!")
                    st.rerun()

        st.write("---")
        if st.button("🚪 Keluar dari Aplikasi (Log Out)", key="btn_logout_profile", type="primary"):
            st.session_state['auth'] = False
            st.session_state['role'] = 'publik'
            st.session_state['nama_user'] = 'Pengunjung'
            st.session_state['username'] = ""
            st.rerun()

# ==============================================================================
# 5. CORE NAVIGATOR CONTROL & HEADER RENDERING
# ==============================================================================
try:
    col_judul, col_pejabat, col_animasi = st.columns([3, 3, 3])
    with col_judul:
        img_base64 = get_base64_image("assets/logo_monisa.jpg")
        if img_base64:
            st.markdown(f"""
                <div style="text-align: center; height: 200px; display: flex; flex-direction: column; justify-content: center; align-items: center; background: white; border-radius: 15px;">
                    <img src="data:image/jpeg;base64,{img_base64}" width="150">
                    <p style="margin: 5px 0 0 0; font-size: 14px; color: #1B5E20; font-style: italic; font-weight: 800;">Dinas Lingkungan Hidup Kab. Brebes</p>
                </div>
            """, unsafe_allow_html=True)
    with col_pejabat: render_media_fixed('bupati.jpg', is_gif=False)
    with col_animasi: render_media_fixed('animasi_sampah.gif', is_gif=True)
except Exception as e:
    st.error(f"Header Error: {e}")

st.divider()
with st.expander("📝 Klik untuk Membaca Sambutan Kepala Dinas"):
    col_kadis_foto, col_teks_sambutan = st.columns([1, 5])
    with col_kadis_foto: render_media_fixed('kadin.jpg', is_gif=False)
    with col_teks_sambutan:
        st.markdown("<p style='font-style: italic; font-size: 16px;'>\"Melalui Aplikasi MoniSa, kita wujudkan Brebes yang bersih dan terdigitalisasi...\"</p>", unsafe_allow_html=True)

# ==============================================================================
# 6. SIDEBAR CONTROLLER (SISTEM LOGIN & LUPA PASSWORD)
# ==============================================================================
with st.sidebar:
    st.header("🔑 Akses Sistem")
    if not st.session_state['auth']:
        opsi_auth = st.radio("Menu Log", ["Login Masuk", "Daftar Akun Baru", "Lupa Password?"])
        
        if opsi_auth == "Login Masuk":
            user = st.text_input("Username")
            pw = st.text_input("Password", type="password")
            if st.button("Login"):
                hasil = proses_login(user, pw)
                if hasil:
                    st.session_state['auth'] = True
                    st.session_state['role'] = hasil['role']
                    st.session_state['nama_user'] = hasil['nama']
                    st.session_state['username'] = user.strip().lower()
                    st.rerun()
                    
        elif opsi_auth == "Daftar Akun Baru":
            st.info("Form pendaftaran ditampilkan di layar utama.")
            
        elif opsi_auth == "Lupa Password?":
            st.markdown("⚠️ **Reset Password Mandiri**")
            f_user = st.text_input("Masukkan Username Anda")
            f_hp = st.text_input("Masukkan No. HP/WA Terdaftar")
            f_pw_baru = st.text_input("Masukkan Password Baru", type="password")
            
            if st.button("🔄 Reset Password Sekarang", use_container_width=True):
                if not f_user or not f_hp or not f_pw_baru:
                    st.error("Semua kolom wajib diisi!")
                else:
                    df_cek = jalankan_query("SELECT id FROM users WHERE username = %s AND no_hp = %s", (f_user.strip().lower(), f_hp.strip()))
                    if not df_cek.empty:
                        hashed_password_str = bcrypt.hashpw(f_pw_baru.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                        jalankan_query("UPDATE users SET password_hash = %s WHERE username = %s", (hashed_password_str, f_user.strip().lower()), ambil_data=False)
                        st.success("✅ Password berhasil diubah! Silakan beralih ke menu 'Login Masuk'.")
                    else:
                        st.error("❌ Data verifikasi tidak cocok.")
    else:
        st.success(f"Login: {st.session_state['nama_user']}")
        if st.button("Logout"):
            st.session_state['auth'] = False
            st.session_state['role'] = 'publik'
            st.session_state['username'] = ""
            st.rerun()

# ==============================================================================
# 7. ROUTING MENU UTAMA & MAP/REPORT RENDERING
# ==============================================================================
if not st.session_state['auth'] and opsi_auth == "Daftar Akun Baru":
    halaman_registrasi()

else:
    # Set Menu Tabs
    daftar_tabs = ["📍 Lokasi TPS3R/TPA", "📊 Laporan Berkala"]
    if st.session_state['auth']:
        daftar_tabs.append("📝 Input Data")
        if st.session_state['role'] in ['admin_lh', 'dinas_lh']:
            daftar_tabs.append("⚙️ Manajemen Master")
            daftar_tabs.append("👥 Approval Akun")
        daftar_tabs.append("👤 Profil Saya")
        
    tabs = st.tabs(daftar_tabs)
    
    for i, nama_tab in enumerate(daftar_tabs):
        if nama_tab == "📍 Lokasi TPS3R/TPA":
            with tabs[i]:
                st.subheader("📍 Peta Sebaran Lokasi Infrastruktur & Bank Sampah Kabupaten Brebes")
                render_ikhtisar_sampah()
                
                # Menggunakan SPLIT_PART agar aman di PostgreSQL
                df_peta = jalankan_query("""
                    SELECT l.nama_unit, l.lat, l.lon, l.tipe, l.kecamatan,
                           COALESCE(SUM(lap.berat_kg), 0) / 1000.0 as total_ton
                    FROM lokasi l
                    LEFT JOIN laporan lap ON SPLIT_PART(lap.admin_input, ' | ', 1) = l.nama_unit
                    GROUP BY l.id, l.nama_unit, l.lat, l.lon, l.tipe, l.kecamatan
                """)

                if not df_peta.empty:
                    # Amankan koordinat kosong atau bernilai NaN agar folium tidak crash
                    df_peta = df_peta.dropna(subset=['lat', 'lon'])
                    
                    m = folium.Map(location=[-6.9700, 108.9200], zoom_start=11)
                    def get_color(tipe):
                        if tipe == 'TPA': return '#FF0000'
                        elif tipe == 'TPST': return '#FFA500'
                        elif tipe == 'TPS3R': return '#228B22'
                        elif tipe == 'Bank Sampah Unit': return '#87CEEB'
                        elif tipe == 'Bank Sampah Induk': return '#00008B'
                        else: return '#808080'

                    for index, row in df_peta.iterrows():
                        warna_titik = get_color(row['tipe'])
                        isi_popup = f"<div style='font-family: Arial;'><b>{row['tipe']} {row['nama_unit']}</b><br><small>Total: {row['total_ton']:.2f} Ton</small></div>"
                        folium.CircleMarker(
                            location=[row['lat'], row['lon']], radius=9,
                            popup=folium.Popup(isi_popup, max_width=250),
                            color=warna_titik, fill=True, fill_color=warna_titik, fill_opacity=0.7
                        ).add_to(m)

                    st_folium(m, width=1200, height=500, returned_objects=[])
                    st.dataframe(df_peta[['nama_unit', 'kecamatan', 'tipe', 'total_ton']], use_container_width=True)

        elif nama_tab == "📊 Laporan Berkala":
            with tabs[i]:
                st.subheader("📊 Laporan Pengelolaan Sampah Berkala")
                
                # Menggunakan SPLIT_PART yang jauh lebih aman & efisien di PostgreSQL
                # Serta mengubah % menjadi %% agar tidak dibaca sebagai variabel input oleh psycopg2
                df_all = jalankan_query("""
                    SELECT l.id, 
                           l.tanggal, 
                           l.berat_kg, 
                           l.kategori, 
                           COALESCE(l.sub_kategori, '-') as sub_kategori,
                           SPLIT_PART(l.admin_input, ' | ', 1) AS lokasi,
                           CASE 
                               WHEN l.admin_input LIKE '%% | %%' THEN SPLIT_PART(l.admin_input, ' | ', 2)
                               ELSE 'Petugas Lapangan' 
                           END AS petugas,
                           loc.kecamatan 
                    FROM laporan l
                    JOIN lokasi loc ON SPLIT_PART(l.admin_input, ' | ', 1) = loc.nama_unit
                """)
                
                if not df_all.empty:
                    df_all['tanggal'] = pd.to_datetime(df_all['tanggal'])
                    df_all['bulan'] = df_all['tanggal'].dt.month_name()
                    df_all['tahun'] = df_all['tanggal'].dt.year

                    col_f1, col_f2, col_f3 = st.columns(3)
                    with col_f1: sel_kec = st.selectbox("📍 Pilih Wilayah", ["Semua Kecamatan"] + sorted(df_all['kecamatan'].unique().tolist()))
                    with col_f2: sel_bulan = st.selectbox("📅 Pilih Bulan", df_all['bulan'].unique())
                    with col_f3: sel_tahun = st.selectbox("🗓️ Pilih Tahun", sorted(df_all['tahun'].unique(), reverse=True))

                    df_filtered = df_all[(df_all['bulan'] == sel_bulan) & (df_all['tahun'] == sel_tahun)]
                    if sel_kec != "Semua Kecamatan": df_filtered = df_filtered[df_filtered['kecamatan'] == sel_kec]
                        
                    st.metric(f"Total Sampah ({sel_kec})", f"{df_filtered['berat_kg'].sum():,.1f} Kg")
                    st.dataframe(df_filtered[['tanggal', 'kecamatan', 'lokasi', 'petugas', 'kategori', 'sub_kategori', 'berat_kg']], use_container_width=True, hide_index=True)
                else:
                    st.info("ℹ️ Belum ada data laporan berkala yang sinkron dengan master data lokasi unit.")
                    
        elif nama_tab == "📝 Input Data":
            with tabs[i]:
                st.subheader("📝 Form Input Sampah Harian")
                
                # CASCADING DROPDOWN PART 1: Pilih Kecamatan Terlebih Dahulu
                kec_pilih = st.selectbox("📍 Langkah 1: Pilih Kecamatan Fasilitas", LIST_KECAMATAN, key="input_kecamatan")
                
                # Ambil daftar lokasi terfilter berdasarkan kecamatan yang dipilih
                list_lokasi_terfilter = get_list_lokasi_by_kecamatan(kec_pilih)
                
                if not list_lokasi_terfilter:
                    st.warning(f"⚠️ Belum ada data master lokasi unit/fasilitas sampah di Kecamatan {kec_pilih}. Silakan tambahkan dulu di Manajemen Master.")
                else:
                    # Menggunakan form tanpa mengganggu state dinamis kategori
                    with st.form("form_sampah_lokasi", clear_on_submit=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            lokasi_pilih = st.selectbox("🚛 Langkah 2: Pilih Nama Unit / Fasilitas Sampah", list_lokasi_terfilter)
                            tgl = st.date_input("Tanggal Operasional", datetime.now())
                            berat = st.number_input("Berat Masuk (Kg)", min_value=0.0, step=1.0)
                        
                        with col2:
                            # STRUKTUR KATEGORI & SUB KATEGORI BARU
                            kategori = st.selectbox("Kategori Utama Sampah", list(DIKTI_KATEGORI.keys()), key="form_kategori_utama")
                            
                            # Logika penentuan sub-kategori dinamis di form
                            sub_kategori_final = "-"
                            if kategori in ["Organik", "Anorganik"]:
                                sub_pilihan = st.selectbox("Sub Kategori", DIKTI_KATEGORI[kategori])
                                sub_kategori_final = sub_pilihan
                            elif kategori == "Lainnya":
                                text_manual = st.text_input("Ketik Kategori Manual", placeholder="Misal: Sampah Kain Saja, dsb.")
                                sub_kategori_final = text_manual if text_manual.strip() else "Lainnya (Manual)"
                            else:
                                st.info("ℹ️ Kategori ini tidak membutuhkan spesifikasi sub-kategori.")
                                sub_kategori_final = "-"
                        
                        uploaded_file = st.file_uploader("📷 Ambil Foto Kondisi TPS (Maksimal 1 MB)", type=["jpg", "png", "jpeg"])
                        submit = st.form_submit_button("Simpan Laporan & Foto")
                        
                        if submit:
                            if berat <= 0 or uploaded_file is None:
                                st.error("Berat harus > 0 dan wajib unggah foto!")
                            elif len(uploaded_file.getvalue()) / (1024 * 1024) > 1.0:
                                st.error("❌ Foto maksimal 1.00 MB!")
                            else:
                                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                nama_foto_baru = f"{lokasi_pilih}_{kategori}_{timestamp}.jpg"
                                username_aktif = st.session_state.get('username', 'unknown')
                                data_input_gabungan = f"{lokasi_pilih} | {username_aktif}"
                                
                                # Simpan ke database Postgres dengan menyertakan nilai sub_kategori
                                jalankan_query("""
                                    INSERT INTO laporan (tanggal, berat_kg, kategori, sub_kategori, admin_input, foto_path) 
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                """, (tgl, berat, kategori, sub_kategori_final, data_input_gabungan, nama_foto_baru), ambil_data=False)
                                
                                if not os.path.exists("data_foto"): os.makedirs("data_foto")
                                with open(os.path.join("data_foto", nama_foto_baru), "wb") as f:
                                    f.write(uploaded_file.getvalue())
                                st.success("✅ Data berhasil disimpan!")
                                st.rerun()

                st.divider()
                st.subheader("🕒 Riwayat Input Terakhir")
                query_riwayat = "SELECT id, tanggal, berat_kg, kategori, COALESCE(sub_kategori, '-') as sub_kategori, admin_input as lokasi, foto_path FROM laporan ORDER BY id DESC LIMIT 5"
                df_riwayat = jalankan_query(query_riwayat)
                
                if not df_riwayat.empty:
                    for index, row in df_riwayat.iterrows():
                        string_input = row['lokasi']
                        lokasi_tampil = string_input.split(" | ")[0] if " | " in string_input else string_input
                        
                        with st.expander(f"Data {lokasi_tampil} - {row['tanggal']} ({row['kategori']} / {row['sub_kategori']})"):
                            st.write(f"Berat: {row['berat_kg']} Kg")
                            if row['foto_path'] and os.path.exists(os.path.join("data_foto", row['foto_path'])):
                                st.image(os.path.join("data_foto", row['foto_path']), width=300)
                            
                            if st.button(f"Hapus ID {row['id']}", key=f"hapus_{row['id']}"):
                                jalankan_query("DELETE FROM laporan WHERE id = %s", (int(row['id']),), ambil_data=False)
                                st.warning(f"Data ID {row['id']} telah dihapus.")
                                st.rerun()

        elif nama_tab == "⚙️ Manajemen Master":
            with tabs[i]:
                st.subheader("⚙️ Manajemen Master Data Lokasi Unit")
                
                # UPLOAD CSV MASSAL
                with st.expander("📥 Upload Massal Data Lokasi (via CSV)"):
                    uploaded_file = st.file_uploader("Pilih file CSV data lokasi", type=["csv"])
                    if uploaded_file is not None:
                        try:
                            df_csv = pd.read_csv(uploaded_file, sep=None, engine='python')
                            df_csv.columns = df_csv.columns.str.replace(r'^\ufeff', '', regex=True).str.strip().str.lower()
                            
                            df_csv['lat'] = pd.to_numeric(df_csv['lat'].astype(str).str.replace("'", "").str.replace('"', '').str.strip(), errors='coerce')
                            df_csv['lon'] = pd.to_numeric(df_csv['lon'].astype(str).str.replace("'", "").str.replace('"', '').str.strip(), errors='coerce')
                            df_csv = df_csv.dropna(subset=['lat', 'lon'])
                            
                            st.dataframe(df_csv)
                            if st.button("💾 Konfirmasi & Masukkan Data Massal"):
                                for _, row in df_csv.iterrows():
                                    nama_clean = str(row['nama_unit']).strip()
                                    df_dup = jalankan_query("SELECT id FROM lokasi WHERE nama_unit = %s", (nama_clean,))
                                    if df_dup.empty:
                                        jalankan_query("INSERT INTO lokasi (nama_unit, kecamatan, tipe, lat, lon) VALUES (%s, %s, %s, %s, %s)", 
                                                       (nama_clean, str(row['kecamatan']).strip(), str(row['tipe']).strip(), float(row['lat']), float(row['lon'])), ambil_data=False)
                                st.success("🎉 Data CSV Massal berhasil diproses!")
                                st.rerun()
                        except Exception as e: st.error(f"Eror CSV: {e}")
                
                # TAMBAH LOKASI MANUAL
                with st.expander("➕ Tambah Titik Lokasi Baru"):
                    with st.form("form_tambah_master_lokasi", clear_on_submit=True):
                        f_nama_unit = st.text_input("Nama Unit/Lokasi")
                        f_kecamatan = st.selectbox("Kecamatan", LIST_KECAMATAN)
                        f_tipe = st.selectbox("Tipe / Kategori Lokasi", LIST_TIPE)
                        f_lat = st.number_input("Latitude", format="%.6f", value=-6.870000)
                        f_lon = st.number_input("Longitude", format="%.6f", value=109.040000)
                        
                        if st.form_submit_button("💾 Daftarkan Lokasi Baru"):
                            if f_nama_unit.strip():
                                jalankan_query("INSERT INTO lokasi (nama_unit, kecamatan, tipe, lat, lon) VALUES (%s, %s, %s, %s, %s)", 
                                               (f_nama_unit.strip(), f_kecamatan, f_tipe, f_lat, f_lon), ambil_data=False)
                                st.success("🎉 Lokasi baru didaftarkan!")
                                st.rerun()
                
                # EDIT DATA LOKASI VIA DATA EDITOR
                st.write("---")
                df_lokasi_edit = jalankan_query("SELECT id, nama_unit, kecamatan, tipe, lat, lon FROM lokasi ORDER BY id ASC")
                if not df_lokasi_edit.empty:
                    df_lokasi_edit.insert(0, 'No', range(1, len(df_lokasi_edit) + 1))
                    edited_df = st.data_editor(df_lokasi_edit, hide_index=True, use_container_width=True, key="editor_lokasi_pg")
                    
                    if st.button("💾 Simpan Perubahan Data Editor"):
                        for index, row in edited_df.iterrows():
                            jalankan_query("UPDATE lokasi SET nama_unit=%s, kecamatan=%s, tipe=%s, lat=%s, lon=%s WHERE id=%s", 
                                           (row['nama_unit'], row['kecamatan'], row['tipe'], float(row['lat']), float(row['lon']), int(row['id'])), ambil_data=False)
                        st.success("✅ Perubahan database berhasil disimpan!")
                        st.rerun()

        elif nama_tab == "👥 Approval Akun":
            with tabs[i]: halaman_approval_admin()
        elif nama_tab == "👤 Profil Saya":
            with tabs[i]: halaman_profil_user()
