import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import os
import io
import base64
import bcrypt  # Pastikan sudah install: pip install bcrypt
import folium
from streamlit_folium import st_folium

# ==============================================================================
# INISIALISASI STREAMLIT SESSION STATE (Taruh di bagian paling atas app.py)
# ==============================================================================
if 'auth' not in st.session_state:
    st.session_state['auth'] = False

if 'role' not in st.session_state:
    st.session_state['role'] = None

# TAMBAHKAN BARIS INI UNTUK MENYELAMATKAN HALAMAN PROFIL
if 'username' not in st.session_state:
    st.session_state['username'] = ""

# ==============================================================================
# 1. INITIAL CONFIGURATION & BASE FUNCTIONS
# ==============================================================================
st.set_page_config(page_title="MoniSa Brebes - DLH", layout="wide", page_icon="🚛")

def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except Exception:
        return None

def jalankan_query(query):
    with sqlite3.connect('sampah.db') as conn:
        return pd.read_sql(query, conn)

def get_list_lokasi():
    with sqlite3.connect('sampah.db') as conn:
        df = pd.read_sql("SELECT nama_unit FROM lokasi", conn)
        return df['nama_unit'].tolist()

# ==============================================================================
# 2. SISTEM AUTENTIKASI & DATABASE USER (BERBASIS SQLITE)
# ==============================================================================
# ==============================================================================
# SINKRONISASI OTOMATIS: INISIALISASI STRUKTUR TABEL (Taruh di Bagian 2)
# ==============================================================================
def init_db_otomatis():
    with sqlite3.connect('sampah.db') as conn:
        cursor = conn.cursor()
        
        # ----------------------------------------------------------------------
        # [PENYELAMATAN UTAMA] 1. Buat Tabel Lokasi (Agar Kueri Peta Tidak Crash)
        # ----------------------------------------------------------------------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS lokasi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama_unit TEXT NOT NULL,
            lat REAL,
            lon REAL,
            tipe TEXT,
            kecamatan TEXT
        )
        """)
        conn.commit()
        
        # ----------------------------------------------------------------------
        # [PENYELAMATAN KEDUA] 2. Buat Tabel Laporan (Agar Riwayat Input Tidak Crash)
        # ----------------------------------------------------------------------
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS laporan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tanggal TEXT,
            berat_kg REAL,
            kategori TEXT,
            admin_input TEXT,
            foto_path TEXT
        )
        """)
        conn.commit()
        
        # 3. Buat tabel user baru sementara dengan struktur ID Auto-Increment yang sempurna
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users_baru (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
        """)
        conn.commit()
        
        # 4. Migrasi data dari tabel lama jika tabel 'users' sudah pernah ada sebelumnya
        try:
            # Cek apakah tabel users lama ada isinya
            cursor.execute("SELECT username, password_hash, role, nama_lengkap, nip_atau_id, no_hp, alamat, status, foto_profil FROM users")
            users_lama = cursor.fetchall()
            
            # Pindahkan data lama ke tabel baru secara aman
            for user in users_lama:
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO users_baru (username, password_hash, role, nama_lengkap, nip_atau_id, no_hp, alamat, status, foto_profil)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, user)
                except Exception:
                    pass
            conn.commit()
        except sqlite3.OperationalError:
            # Jika tabel 'users' lama belum ada, tidak masalah (berarti instalasi pertama)
            pass

        # 5. Hapus tabel lama dan ganti nama tabel baru menjadi 'users'
        try:
            cursor.execute("DROP TABLE IF EXISTS users")
            cursor.execute("ALTER TABLE users_baru RENAME TO users")
            conn.commit()
        except sqlite3.OperationalError:
            pass
        
        # 6. 🛡️ AMANKAN DATA ADMIN: Buat baru jika belum ada sama sekali
        password_resmi = "lh2026!".encode('utf-8')
        hashed_password = bcrypt.hashpw(password_resmi, bcrypt.gensalt()).decode('utf-8')
        
        cursor.execute("SELECT password_hash FROM users WHERE username = 'dinas_lh'")
        user_eksisting = cursor.fetchone()
        
        if not user_eksisting:
            cursor.execute("""
                INSERT INTO users (username, nama_lengkap, password_hash, role, nip_atau_id, no_hp, alamat, status) 
                VALUES (?, ?, ?, ?, ?, ?, ?, 'approved')
            """, ('dinas_lh', 'Admin Dinas LH', hashed_password, 'admin_lh', '198501012010011001', '08123456789', 'Kantor DLH Kabupaten Brebes'))
            conn.commit()
        elif user_eksisting[0] is None or user_eksisting[0] == "":
            cursor.execute("""
                UPDATE users 
                SET password_hash = ?, role = ?, status = ?, nama_lengkap = ? 
                WHERE username = 'dinas_lh'
            """, (hashed_password, 'admin_lh', 'approved', 'Admin Dinas LH'))
            conn.commit()

# Jalankan fungsi perbaikan database otomatis
init_db_otomatis()
def register_user_with_pending(username, nama, password, role, nip_atau_id, no_hp, alamat):
    # 1. Bersihkan spasi liar di awal/akhir dan paksa huruf kecil agar konsisten
    username_clean = str(username).strip().lower()
    nama_clean = str(nama).strip()
    nip_clean = str(nip_atau_id).strip()
    no_hp_clean = str(no_hp).strip()
    alamat_clean = str(alamat).strip()
    
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    with sqlite3.connect('sampah.db') as conn:
        cursor = conn.cursor()
        
        # --- STRATEGI JAMINAN: Pastikan kolom tambahan aman ---
        for col_name in ["no_hp", "alamat"]:
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} TEXT")
            except sqlite3.OperationalError:
                pass 
                
        # 2. Lakukan pengecekan username secara manual sebelum INSERT dijalankan
        cursor.execute("SELECT id FROM users WHERE username = ?", (username_clean,))
        if cursor.fetchone() is not None:
            st.error("⚠️ Username sudah terdaftar! Silakan gunakan username lain.")
            return False
            
        try:
            # Jalankan insert data dengan variabel yang sudah dibersihkan
            cursor.execute("""
                INSERT INTO users (username, nama_lengkap, password_hash, role, nip_atau_id, no_hp, alamat, status) 
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
            """, (username_clean, nama_clean, hashed_password, role, nip_clean, no_hp_clean, alamat_clean))
            conn.commit()
            return True
        except sqlite3.IntegrityError as e:
            # Jika lolos cek manual di atas tapi tetap IntegrityError, berarti ada kolom lain yang bermasalah (constraint violation)
            st.error(f"⚠️ Gagal mendaftar karena batasan data (Integrity Error): {e}")
            return False
        except Exception as e:
            st.error(f"❌ Gagal menyimpan ke database: {e}")
            return False

def proses_login(username, password):
    with sqlite3.connect('sampah.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash, role, status, nama_lengkap FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        
    if user:
        hashed, role, status, nama_lengkap = user
        if bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8')):
            if status != 'approved':
                st.error("⚠️ Akun Anda belum disetujui oleh Admin Dinas LH. Silakan hubungi admin.")
                return None
            return {"role": role, "nama": nama_lengkap}
    st.error("❌ Username atau Password salah.")
    return None

def get_pending_users():
    # Membuka koneksi baru yang fresh khusus untuk Pandas agar kolom baru langsung terbaca
    with sqlite3.connect('sampah.db') as conn:
        try:
            query = "SELECT id, username, nama_lengkap, role, nip_atau_id, no_hp, alamat FROM users WHERE status = 'pending'"
            df = pd.read_sql(query, conn)
            return df
        except Exception as e:
            # Jika masih sempat membaca cache lama, kembalikan dataframe kosong agar aplikasi tidak crash
            return pd.DataFrame(columns=['id', 'username', 'nama_lengkap', 'role', 'nip_atau_id', 'no_hp', 'alamat'])
    
def get_active_operators():
    with sqlite3.connect('sampah.db') as conn:
        # Mengambil user yang sudah disetujui (approved)
        df = pd.read_sql("""
            SELECT id, username, nama_lengkap, role, nip_atau_id, no_hp, alamat 
            FROM users 
            WHERE status = 'approved'
            ORDER BY nama_lengkap ASC
        """, conn)
    return df.values.tolist()

def update_user_status(user_id, status_baru):
    with sqlite3.connect('sampah.db') as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET status = ? WHERE id = ?", (status_baru, user_id))
        conn.commit()
        
def get_user_profile(username):
    with sqlite3.connect('sampah.db') as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT nama_lengkap, nip_atau_id, no_hp, alamat, role 
            FROM users WHERE username = ?
        """, (username,))
        return cursor.fetchone()

def update_user_profile(username, nama, nip_id, no_hp, alamat):
    try:
        with sqlite3.connect('sampah.db') as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users 
                SET nama_lengkap = ?, nip_atau_id = ?, no_hp = ?, alamat = ? 
                WHERE username = ?
            """, (nama, nip_id, no_hp, alamat, username))
            conn.commit()
        return True
    except Exception as e:
        st.error(f"❌ Gagal memperbarui profil: {e}")
        return False

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
    @media (max-width: 640px) {
        .header-container-elegan {
            height: auto !important;
            min-height: 160px !important;
            padding: 15px 5px !important;
            margin-bottom: 10px !important;
        }
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
    
    with st.form("form_registrasi", clear_on_submit=False): # Set False dulu untuk debugging jika gagal
        col_reg1, col_reg2 = st.columns(2)
        
        with col_reg1:
            nama_lengkap = st.text_input("Nama Lengkap")
            nip_atau_id = st.text_input("NIP / NIK / ID Petugas")
            no_hp = st.text_input("No. HP / WhatsApp (Aktif)", placeholder="Contoh: 081234567xxx")
            
        with col_reg2:
            username = st.text_input("Username (untuk login)")
            password = st.text_input("Password", type="password")
            role_pilih = st.selectbox("Mendaftar Sebagai", ["petugas_lapangan", "admin_lh"],
                                      format_func=lambda x: "Petugas Lapangan (Input Data)" if x == "petugas_lapangan" else "Admin Dinas (Monitoring & Master Data)")
        
        # Alamat ditaruh di bawah kolom agar spacenya luas
        alamat_domisili = st.text_area("Alamat Domisili Sekarang", placeholder="Tuliskan alamat lengkap Anda...")
        
        st.write("")
        submit_reg = st.form_submit_button("Ajukan Pendaftaran")
        
        if submit_reg:
            # Validasi pastikan tidak ada data yang kosong saat diklik
            if not nama_lengkap or not username or not password or not nip_atau_id or not no_hp or not alamat_domisili:
                st.warning("⚠️ Semua kolom wajib diisi! Mohon lengkapi No. HP dan Alamat Domisili Anda.")
            else:
                sukses = register_user_with_pending(
                    username=username, 
                    nama=nama_lengkap, 
                    password=password, 
                    role=role_pilih, 
                    nip_atau_id=nip_atau_id, 
                    no_hp=no_hp, 
                    alamat=alamat_domisili
                )
                if sukses:
                    st.success("🎉 Pengajuan berhasil! Akun Petugas Lapangan Anda berstatus 'Pending' menunggu verifikasi Admin Dinas LH.")

def halaman_approval_admin():
    # ==========================================================================
    # BAGIAN A: VERIFIKASI AKUN PENDING (YANG BARU MENDAFTAR)
    # ==========================================================================
    st.subheader("👥 Verifikasi & Persetujuan Akun Operator Baru")
    pendaftar_pending = get_pending_users()
    
    if pendaftar_pending.empty:
        st.info("ℹ️ Tidak ada pengajuan akun baru saat ini.")
    else:
        # [PERBAIKAN UTAMA] Menggunakan .iterrows() agar iterasi baris demi baris DataFrame aman & stabil
        for index, row in pendaftar_pending.iterrows():
            u_id = row['id']
            u_username = row['username']
            u_nama = row['nama_lengkap']
            u_role = row['role']
            u_nip = row['nip_atau_id']
            u_no_hp = row['no_hp']
            u_alamat = row['alamat']
            
            tampilan_hp = u_no_hp if pd.notnull(u_no_hp) and u_no_hp != "" else "Tidak dicantumkan (Akun Lama)"
            tampilan_alamat = u_alamat if pd.notnull(u_alamat) and u_alamat != "" else "Tidak dicantumkan (Akun Lama)"
            
            # Gunakan key unik pada container agar Streamlit tidak kebingungan me-render komponen
            with st.container(key=f"container_pending_{u_id}"):
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.markdown(f"**Nama:** {u_nama} (`{u_username}`)")
                    st.markdown(f"📱 **No. HP/WA:** {tampilan_hp} | 🏠 **Alamat:** {tampilan_alamat}")
                    
                    role_bersih = str(u_role).replace('_', ' ').title() if u_role else "Petugas"
                    st.caption(f"NIP/ID: {u_nip} | Diajukan sebagai: **{role_bersih}**")
                with col2:
                    if st.button("Setujui ✔️", key=f"app_{u_id}", type="primary", use_container_width=True):
                        update_user_status(u_id, 'approved')
                        st.success(f"Akun {u_username} disetujui!")
                        st.cache_data.clear() # Bersihkan cache agar data fresh kembali
                        st.rerun()
                with col3:
                    if st.button("Tolak ❌", key=f"rej_{u_id}", type="secondary", use_container_width=True):
                        update_user_status(u_id, 'rejected')
                        st.warning(f"Akun {u_username} ditolak.")
                        st.cache_data.clear() # Bersihkan cache agar data fresh kembali
                        st.rerun()
            st.markdown("---")

    # ==========================================================================
    # BAGIAN B: KONTROL STATUS & DAFTAR OPERATOR (AKTIF & NON-AKTIF)
    # ==========================================================================
    st.write("#") 
    st.subheader("🗂️ Kontrol Status & Daftar Operator MoniSa")
    
   # 🔒 PROTEKSI DOSIS TINGGI: Menyaring agar role dinas_lh, admin_lh, dan super_admin 
    # TIDAK AKAN PERNAH muncul di daftar kontrol penangguhan akun.
    query_all_operators = "SELECT id, username, nama_lengkap, role, nip_atau_id, no_hp, alamat, status FROM users WHERE status = 'approved'"
    # Gunakan koneksi mandiri agar Pandas membaca struktur kolom terbaru dari PC lokal Anda
    with sqlite3.connect('sampah.db') as conn_baru:
        try:
            operator_data = pd.read_sql(query_all_operators, conn_baru)
        except Exception:
            # Cadangan aman jika dataframe gagal dimuat
            operator_data = pd.DataFrame(columns=['id', 'username', 'nama_lengkap', 'role', 'nip_atau_id', 'no_hp', 'alamat', 'status'])
    
    if operator_data.empty:
        st.warning("⚠️ Belum ada petugas atau operator yang terdaftar di sistem.")
    else:
        # Loop interaktif untuk kontrol status petugas
        for index, row in operator_data.iterrows():
            status_current = str(row['status']).lower()
            
            # Pengkondisian warna border/latar berdasarkan status
            is_aktif = status_current in ['approved', 'aktif']
            border_color = "🟢" if is_aktif else "🔴"
            status_text = "Aktif" if is_aktif else "Non-Aktif (Ditangguhkan)"
            
            with st.container(border=True):
                c_info, c_status, c_aksi = st.columns([3, 1, 1])
                
                with c_info:
                    st.markdown(f"**{row['nama_lengkap']}** (`{row['username']}`)")
                    # 📝 PERBAIKAN: Mengubah row['nip'] menjadi row['nip_atau_id']
                    st.caption(f"NIP/NIK: {row['nip_atau_id']} | Peran: **{str(row['role']).replace('_', ' ').title()}**")
                    hp_val = row['no_hp'] if pd.notnull(row['no_hp']) and row['no_hp'] != "" else "—"
                    almt_val = row['alamat'] if pd.notnull(row['alamat']) and row['alamat'] != "" else "—"
                    st.markdown(f"<small>📞 {hp_val} | 🏠 {almt_val}</small>", unsafe_allow_html=True)
                
                with c_status:
                    st.write("") 
                    if is_aktif:
                        st.success(f"{border_color} {status_text}")
                    else:
                        st.error(f"{border_color} {status_text}")
                        
                with c_aksi:
                    st.write("")
                    if is_aktif:
                        if st.button("🛑 Tangguhkan", key=f"suspend_{row['id']}", type="secondary", use_container_width=True):
                            with sqlite3.connect('sampah.db') as conn:
                                conn.execute("UPDATE users SET status = 'nonaktif' WHERE id = ?", (int(row['id']),))
                                conn.commit()
                            st.warning(f"Akses untuk {row['username']} telah dimatikan!")
                            st.cache_data.clear()
                            st.rerun()
                    else:
                        if st.button("🟢 Aktifkan", key=f"reactivate_{row['id']}", type="primary", use_container_width=True):
                            with sqlite3.connect('sampah.db') as conn:
                                conn.execute("UPDATE users SET status = 'approved' WHERE id = ?", (int(row['id']),))
                                conn.commit()
                            st.success(f"Akses untuk {row['username']} diaktifkan kembali!")
                            st.cache_data.clear()
                            st.rerun()
                            
                    # 🟢 PERBAIKAN: Tombol Reset Password oleh Admin LH menggunakan Bcrypt
                    if st.button("🔑 Reset Pass", key=f"reset_pass_{row['id']}", use_container_width=True, help="Setel ulang password menjadi '123456'"):
                        try:
                            import bcrypt
                            # Enkripsi password default '123456'
                            pass_default_bytes = "123456".encode('utf-8')
                            salt_default = bcrypt.gensalt()
                            hashed_default = bcrypt.hashpw(pass_default_bytes, salt_default).decode('utf-8')
                            
                            with sqlite3.connect('sampah.db') as conn:
                                conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hashed_default, int(row['id'])))
                                conn.commit()
                            st.info(f"🔑 Password {row['username']} di-reset menjadi: 123456")
                        except Exception as e:
                            st.error(f"Gagal melakukan reset password: {e}")

def halaman_profil_user():
    st.subheader("👤 Profil Pengguna")
    
    # 1. Ambil username aktif dari session state
    username_aktif = st.session_state.get('username', '')
    
    if not username_aktif:
        st.error("❌ Sesi login tidak terbaca. Silakan log out lalu log in kembali.")
        return

    # 2. Query data lengkap user (Termasuk no_hp dan alamat)
    query_profil = f"SELECT username, nama_lengkap, role, status, foto_profil, no_hp, alamat FROM users WHERE username = '{username_aktif}'"
    df_user = jalankan_query(query_profil)
    
    if not df_user.empty:
        user_data = df_user.iloc[0]
        
        # Ambil nilai awal data tambahan agar tidak error jika kosong (None)
        no_hp_sekarang = user_data['no_hp'] if pd.notnull(user_data['no_hp']) else "-"
        alamat_sekarang = user_data['alamat'] if pd.notnull(user_data['alamat']) else "-"
        
        # Tampilan Profil
        col_foto, col_data = st.columns([1, 3])
        
        with col_foto:
            foto_db = user_data.get('foto_profil')
            avatar_default = "https://cdn-icons-png.flaticon.com/512/3135/3135715.png"
            
            if foto_db and pd.notnull(foto_db):
                foto_path = os.path.join("data_profil", foto_db)
                if os.path.exists(foto_path):
                    st.image(foto_path, width=130)
                else:
                    st.image(avatar_default, width=130)
            else:
                st.image(avatar_default, width=130)
            
        with col_data:
            st.markdown(f"### **{user_data['nama_lengkap']}**")
            st.text(f"ID Akun / Username : {user_data['username']}")
            
            role_display = str(user_data['role']).replace('_', ' ').title()
            st.markdown(f"Tingkat Akses : `{role_display}`")
            
            # Tampilkan informasi kontak tambahan
            st.markdown(f"📞 **No. HP :** {no_hp_sekarang}")
            st.markdown(f"🏠 **Alamat :** {alamat_sekarang}")
            
            status_user = str(user_data['status']).lower()
            if status_user in ['aktif', 'approved', '1']:
                st.success("🟢 Akun Terverifikasi & Aktif")
            else:
                st.warning("🟡 Menunggu Verifikasi Admin")

        # ======================================================================
        # FITUR EDIT PROFIL (NAMA, NO HP, ALAMAT & FOTO)
        # ======================================================================
        st.write("---")
        with st.expander("📝 Edit Informasi Profil & Foto"):
            with st.form("form_edit_profil", clear_on_submit=False):
                st.markdown("##### Perbarui Data Diri")
                
                # Form input teks
                nama_baru = st.text_input("Nama Lengkap Baru", value=user_data['nama_lengkap'])
                
                # Mengisi nilai default form dengan data yang sudah ada (jika bukan "-")
                default_hp = no_hp_sekarang if no_hp_sekarang != "-" else ""
                default_alamat = alamat_sekarang if alamat_sekarang != "-" else ""
                
                no_hp_baru = st.text_input("Nomor HP Baru", value=default_hp)
                alamat_baru = st.text_area("Alamat Lengkap Baru", value=default_alamat)
                
                st.markdown("##### Perbarui Foto Profil")
                file_foto = st.file_uploader("Pilih Foto (Format JPG/PNG, Maks 500 KB)", type=["jpg", "jpeg", "png"])
                
                # Cek Ukuran Foto
                ukuran_aman = True
                if file_foto is not None:
                    if file_foto.size > 500 * 1024:
                        st.error("⚠️ Ukuran file terlalu besar! Silakan gunakan foto di bawah 500 KB.")
                        ukuran_aman = False
                
                btn_simpan = st.form_submit_button("💾 Simpan Perubahan")
                
                if btn_simpan:
                    if not nama_baru.strip():
                        st.error("Nama lengkap tidak boleh kosong!")
                    elif not ukuran_aman:
                        st.error("Gagal menyimpan, periksa kembali ukuran foto Anda.")
                    else:
                        nama_file_foto = user_data.get('foto_profil')
                        
                        if file_foto is not None:
                            if not os.path.exists("data_profil"):
                                os.makedirs("data_profil")
                                
                            ekstensi = file_foto.name.split('.')[-1]
                            nama_file_foto = f"profile_{username_aktif}.{ekstensi}"
                            filepath_simpan = os.path.join("data_profil", nama_file_foto)
                            
                            with open(filepath_simpan, "wb") as f:
                                f.write(file_foto.getvalue())
                        
                        # Query UPDATE untuk 4 data sekaligus
                        try:
                            with sqlite3.connect('sampah.db') as conn:
                                conn.execute("""
                                    UPDATE users 
                                    SET nama_lengkap = ?, no_hp = ?, alamat = ?, foto_profil = ? 
                                    WHERE username = ?
                                """, (nama_baru.strip(), no_hp_baru.strip(), alamat_baru.strip(), nama_file_foto, username_aktif))
                                conn.commit()
                            
                            st.session_state['nama_user'] = nama_baru.strip()
                            st.success("✅ Profil berhasil diperbarui!")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Gagal memperbarui database: {e}")

        # Tombol Log Out
        st.write("---")
        if st.button("🚪 Keluar dari Aplikasi (Log Out)", key="btn_logout_profile", type="primary"):
            st.session_state['auth'] = False
            st.session_state['role'] = 'publik'
            st.session_state['nama_user'] = 'Pengunjung'
            st.session_state['username'] = ""
            st.rerun()
            
    else:
        st.error(f"❌ Gagal memuat data profil untuk username: '{username_aktif}'")
        
# ==============================================================================
# 5. CORE NAVIGATOR CONTROL (MAIN ALUR SYSTEM)
# ==============================================================================
if 'auth' not in st.session_state:
    st.session_state['auth'] = False
    st.session_state['role'] = 'publik'
    st.session_state['nama_user'] = 'Pengunjung'

# --- RENDERING ELEMEN HEADER ---
try:
    col_judul, col_pejabat, col_animasi = st.columns([3, 3, 3])
    with col_judul:
        path_logo = "assets/logo_monisa.jpg"
        img_base64 = get_base64_image(path_logo)
        if img_base64:
            st.markdown(f"""
                <div style="text-align: center; height: 200px; display: flex; flex-direction: column; justify-content: center; align-items: center; background: white; border-radius: 15px;">
                    <img src="data:image/jpeg;base64,{img_base64}" width="150" style="margin-bottom: 10px;">
                    <div style="height: 3px; width: 60px; background-color: #FFA000; margin: 5px auto;"></div>
                    <p style="margin: 5px 0 0 0; font-size: 14px; color: #1B5E20; font-style: italic; font-weight: 800; line-height: 1.2;">
                        Dinas Lingkungan Hidup<br>Kabupaten Brebes
                    </p>
                </div>
            """, unsafe_allow_html=True)
        else:
            st.error("Logo tidak ditemukan")
            
    with col_pejabat:
        render_media_fixed('bupati.jpg', is_gif=False)
    with col_animasi:
        render_media_fixed('animasi_sampah.gif', is_gif=True)
except Exception as e:
    st.error(f"Terjadi kesalahan pada Header: {e}")

st.divider()

# --- EXPANDER SAMBUTAN KADIS ---
with st.expander("📝 Klik untuk Membaca Sambutan Kepala Dinas", expanded=False):
    col_kadis_foto, col_teks_sambutan = st.columns([1, 5])
    with col_kadis_foto:
        render_media_fixed('kadin.jpg', is_gif=False)
    with col_teks_sambutan:
        st.markdown("""
            <div style="display: flex; flex-direction: column; justify-content: center; height: 100%; min-height: 150px; padding-left: 15px;">
                <p style="font-style: italic; color: #333; font-size: 16px; margin: 0 0 10px 0;">
                    "Melalui Aplikasi MoniSa (Monitoring Sampah), kita wujudkan Brebes yang bersih dan terdigitalisasi.<br>
                    Data sampah yang akurat adalah langkah awal pelestarian lingkungan."
                </p>
                <p style="font-weight: bold; margin: 0; color: #1B5E20; font-size: 15px;">
                    - Kepala Dinas Lingkungan Hidup Kab. Brebes -
                </p>
            </div>
        """, unsafe_allow_html=True)

# ==============================================================================
# 6. SIDEBAR CONTROLLER (SISTEM AUTENTIKASI BARU)
# ==============================================================================
with st.sidebar:
    st.header("🔑 Akses Sistem")
    if not st.session_state['auth']:
        # Tambahkan opsi "Lupa Password?" ke dalam menu radio
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
                    st.session_state['username'] = user 
                    st.rerun()
                    
        elif opsi_auth == "Daftar Akun Baru":
            st.info("Form pendaftaran ditampilkan di layar utama silakan isi berkas pengajuan.")
            
       # ======================================================================
        # PERBAIKAN: RESET PASSWORD MANDIRI VIA SIDEBAR (DENGAN BCRYPT)
        # ======================================================================
        elif opsi_auth == "Lupa Password?":
            st.markdown("⚠️ **Reset Password Mandiri**")
            st.caption("Masukkan data akun Anda yang terdaftar untuk verifikasi.")
            
            f_user = st.text_input("Masukkan Username Anda", key="forget_user")
            f_hp = st.text_input("Masukkan No. HP/WA Terdaftar", key="forget_hp")
            f_pw_baru = st.text_input("Masukkan Password Baru", type="password", key="forget_pw")
            
            if st.button("🔄 Reset Password Sekarang", use_container_width=True):
                if not f_user or not f_hp or not f_pw_baru:
                    st.error("Semua kolom verifikasi wajib diisi!")
                else:
                    query_cek = f"SELECT id FROM users WHERE username = '{f_user.strip()}' AND no_hp = '{f_hp.strip()}'"
                    df_cek = jalankan_query(query_cek)
                    
                    if not df_cek.empty:
                        try:
                            # 🟢 LANGKAH PENYELAMAT: Enkripsi password baru dengan Bcrypt sebelum disimpan
                            import bcrypt
                            
                            # Mengubah password teks menjadi bytes, lalu di-hash
                            password_bytes = f_pw_baru.encode('utf-8')
                            salt = bcrypt.gensalt()
                            hashed_password = bcrypt.hashpw(password_bytes, salt)
                            
                            # Ubah kembali hasil hash bytes ke string agar bisa disimpan di SQLite
                            hashed_password_str = hashed_password.decode('utf-8')
                            
                            with sqlite3.connect('sampah.db') as conn:
                                # Simpan variabel hashed_password_str, BUKAN f_pw_baru langsung
                                conn.execute("UPDATE users SET password_hash = ? WHERE username = ?", (hashed_password_str, f_user.strip()))
                                conn.commit()
                                
                            st.success("✅ Password berhasil diubah dengan aman! Silakan pilih menu 'Login Masuk'.")
                        except Exception as e:
                            st.error(f"Gagal memperbarui database: {e}")
                    else:
                        st.error("❌ Data tidak cocok! Username atau Nomor HP salah.")
                        
    else:
        st.success(f"Login: {st.session_state['nama_user']}")
        st.caption(f"Role: {st.session_state['role'].replace('_',' ').title()}")
        if st.button("Logout"):
            st.session_state['auth'] = False
            st.session_state['role'] = 'publik'
            st.session_state['nama_user'] = 'Pengunjung'
            st.session_state['username'] = "" 
            st.rerun()

# ==============================================================================
# # 7. ROUTING MENU UTAMA & TAB VIEW CONTROL
# ==============================================================================

# KONDISI 1: JIKA USER MEMILIH DAFTAR AKUN BARU DI SIDEBAR
if not st.session_state['auth'] and opsi_auth == "Daftar Akun Baru":
    halaman_registrasi()

# KONDISI 2: JIKA USER BELUM LOGIN (MENAMPILKAN MENU PUBLIK)
elif not st.session_state['auth']:
    # Set tab untuk publik saja
    daftar_tabs = ["📍 Lokasi TPS3R/TPA", "📊 Laporan Berkala"]
    tabs = st.tabs(daftar_tabs)
    
    # Routing Konten Publik
    for i, nama_tab in enumerate(daftar_tabs):
        if nama_tab == "📍 Lokasi TPS3R/TPA":
            with tabs[i]:
                # 📝 DISESUAIKAN: Judul subheader mencakup infrastruktur baru
                st.subheader("📍 Peta Sebaran Lokasi Infrastruktur & Bank Sampah Kabupaten Brebes")
                df_peta = jalankan_query("""
                    SELECT l.nama_unit, l.lat, l.lon, l.tipe, l.kecamatan,
                    COALESCE(SUM(lap.berat_kg), 0) / 1000.0 as total_ton
                    FROM lokasi l
                    LEFT JOIN laporan lap ON lap.admin_input = l.nama_unit
                    GROUP BY l.id
                """)

                if not df_peta.empty:
                    m = folium.Map(location=[-6.9700, 108.9200], zoom_start=11, tiles="OpenStreetMap")
                    
                    # 🟢 SINKRONISASI UTAMA: Menambahkan penentuan warna BSU dan BSI untuk publik
                    def get_color(tipe):
                        if tipe == 'TPA': return '#FF0000'         # Merah
                        elif tipe == 'TPST': return '#FFA500'       # Oranye
                        elif tipe == 'TPS3R': return '#228B22'      # Hijau
                        elif tipe == 'Bank Sampah Unit': return '#87CEEB'   # 🔵 Biru Muda
                        elif tipe == 'Bank Sampah Induk': return '#00008B'  # 🔷 Biru Tua
                        else: return '#808080'                      # Abu-abu

                    for index, row in df_peta.iterrows():
                        warna_titik = get_color(row['tipe'])
                        # Format tampilan popup disamakan persis dengan setelah login
                        isi_popup = f"""
                            <div style='font-family: Arial; width: 180px;'>
                                <b style='color:{warna_titik};'>{row['tipe']} {row['nama_unit']}</b><br>
                                <small>Kecamatan: {row['kecamatan']}</small><hr>
                                <total style='font-size: 12px;'>Total Terkelola: <b>{row['total_ton']:.2f} Ton</b></total>
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
                    
                    df_tampilan = df_peta[['nama_unit', 'kecamatan', 'tipe', 'total_ton']].copy()
                    df_tampilan.insert(0, 'No', range(1, len(df_tampilan) + 1))
                    st.dataframe(
                        df_tampilan, use_container_width=True, hide_index=True,
                        column_config={
                            "No": st.column_config.Column("No", width=20),
                            "nama_unit": st.column_config.Column("Nama Unit/Lokasi", width="large"),
                            "kecamatan": st.column_config.Column("Kecamatan", width="medium"),
                            "tipe": st.column_config.Column("Tipe", width="small"),
                            "total_ton": st.column_config.NumberColumn("Total (Ton)", width="small", format="%.2f")
                        }
                    )

        elif nama_tab == "📊 Laporan Berkala":
            with tabs[i]:
                st.subheader("📊 Laporan Pengelolaan Sampah Berkala")
                df_all = jalankan_query("""
                    SELECT l.id, l.tanggal, l.berat_kg, l.kategori, l.admin_input as lokasi, loc.kecamatan 
                    FROM laporan l
                    JOIN lokasi loc ON l.admin_input = loc.nama_unit
                """)
                
                if not df_all.empty:
                    df_all['tanggal'] = pd.to_datetime(df_all['tanggal'])
                    df_all['bulan'] = df_all['tanggal'].dt.month_name()
                    df_all['tahun'] = df_all['tanggal'].dt.year

                    col_f1, col_f2, col_f3 = st.columns(3)
                    with col_f1:
                        list_kec_raw = df_all['kecamatan'].dropna().unique().tolist()
                        list_kec = ["Semua Kecamatan"] + sorted([str(k) for k in list_kec_raw])
                        sel_kec = st.selectbox("📍 Pilih Wilayah", list_kec)
                    with col_f2:
                        sel_bulan = st.selectbox("📅 Pilih Bulan", df_all['bulan'].unique())
                    with col_f3:
                        sel_tahun = st.selectbox("🗓️ Pilih Tahun", sorted(df_all['tahun'].unique(), reverse=True))

                    df_filtered = df_all[(df_all['bulan'] == sel_bulan) & (df_all['tahun'] == sel_tahun)]
                    if sel_kec != "Semua Kecamatan":
                        df_filtered = df_filtered[df_filtered['kecamatan'] == sel_kec]
                        
                    st.write("---")
                    total_berat = df_filtered['berat_kg'].sum()
                    st.metric(f"Total Sampah ({sel_kec})", f"{total_berat:,.1f} Kg")
                    st.dataframe(df_filtered[['tanggal', 'kecamatan', 'lokasi', 'kategori', 'berat_kg']], 
                                 use_container_width=True, hide_index=True)
                else:
                    st.info("Belum ada data laporan untuk periode ini.")

# KONDISI 3: JIKA USER SUDAH BERHASIL LOGIN (MENAMPILKAN SEMUA MENU INTERNAL)
else:
    # Mengumpulkan tab lengkap internal
    daftar_tabs = ["📍 Lokasi TPS3R/TPA", "📊 Laporan Berkala", "📝 Input Data"]
    
    # Validasi penambahan hak akses menu admin
    if st.session_state['role'] in ['admin_lh', 'super_admin', 'dinas_lh'] or 'admin' in str(st.session_state['role']).lower():
        daftar_tabs.append("⚙️ Manajemen Master")
        daftar_tabs.append("👥 Approval Akun")
        
    # Profil ditempatkan paling kanan setelah login sukses
    daftar_tabs.append("👤 Profil Saya")
    
    tabs = st.tabs(daftar_tabs)

    # Routing Konten Akun Terautentikasi
    for i, nama_tab in enumerate(daftar_tabs):
        
        # --- TAB: PETA SEBARAN LOKASI ---
        if nama_tab == "📍 Lokasi TPS3R/TPA":
            with tabs[i]:
                # Update judul subheader agar mencakup Bank Sampah
                st.subheader("📍 Peta Sebaran Lokasi Infrastruktur & Bank Sampah Kabupaten Brebes")
                df_peta = jalankan_query("""
                    SELECT l.nama_unit, l.lat, l.lon, l.tipe, l.kecamatan,
                    COALESCE(SUM(lap.berat_kg), 0) / 1000.0 as total_ton
                    FROM lokasi l
                    LEFT JOIN laporan lap ON lap.admin_input = l.nama_unit
                    GROUP BY l.id
                """)

                if not df_peta.empty:
                    m = folium.Map(location=[-6.9700, 108.9200], zoom_start=11, tiles="OpenStreetMap")
                    
                    # ⚙️ MODIFIKASI: Menambahkan logika warna HEX untuk BSU dan BSI
                    def get_color(tipe):
                        if tipe == 'TPA': return '#FF0000'         # Merah
                        elif tipe == 'TPST': return '#FFA500'       # Oranye
                        elif tipe == 'TPS3R': return '#228B22'      # Hijau
                        elif tipe == 'Bank Sampah Unit': return '#87CEEB'   # 🔵 Biru Muda
                        elif tipe == 'Bank Sampah Induk': return '#00008B'  # 🔷 Biru Tua
                        else: return '#808080'                      # Abu-abu (Cadangan)

                    for index, row in df_peta.iterrows():
                        warna_titik = get_color(row['tipe'])
                        isi_popup = f"""
                            <div style='font-family: Arial; width: 180px;'>
                                <b style='color:{warna_titik};'>{row['tipe']} {row['nama_unit']}</b><br>
                                <small>Kecamatan: {row['kecamatan']}</small><hr>
                                <total style='font-size: 12px;'>Total Terkelola: <b>{row['total_ton']:.2f} Ton</b></total>
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
                    
                    df_tampilan = df_peta[['nama_unit', 'kecamatan', 'tipe', 'total_ton']].copy()
                    df_tampilan.insert(0, 'No', range(1, len(df_tampilan) + 1))
                    st.dataframe(
                        df_tampilan, use_container_width=True, hide_index=True,
                        column_config={
                            "No": st.column_config.Column("No", width=20),
                            "nama_unit": st.column_config.Column("Nama Unit/Lokasi", width="large"),
                            "kecamatan": st.column_config.Column("Kecamatan", width="medium"),
                            "tipe": st.column_config.Column("Tipe", width="small"),
                            "total_ton": st.column_config.NumberColumn("Total (Ton)", width="small", format="%.2f")
                        }
                    )

        # --- TAB: LAPORAN BERKALA ---
        elif nama_tab == "📊 Laporan Berkala":
            with tabs[i]:
                st.subheader("📊 Laporan Pengelolaan Sampah Berkala")
                df_all = jalankan_query("""
                    SELECT l.id, l.tanggal, l.berat_kg, l.kategori, l.admin_input as lokasi, loc.kecamatan 
                    FROM laporan l
                    JOIN lokasi loc ON l.admin_input = loc.nama_unit
                """)
                
                if not df_all.empty:
                    df_all['tanggal'] = pd.to_datetime(df_all['tanggal'])
                    df_all['bulan'] = df_all['tanggal'].dt.month_name()
                    df_all['tahun'] = df_all['tanggal'].dt.year

                    col_f1, col_f2, col_f3 = st.columns(3)
                    with col_f1:
                        list_kec_raw = df_all['kecamatan'].dropna().unique().tolist()
                        list_kec = ["Semua Kecamatan"] + sorted([str(k) for k in list_kec_raw])
                        sel_kec = st.selectbox("📍 Pilih Wilayah", list_kec)
                    with col_f2:
                        sel_bulan = st.selectbox("📅 Pilih Bulan", df_all['bulan'].unique())
                    with col_f3:
                        sel_tahun = st.selectbox("🗓️ Pilih Tahun", sorted(df_all['tahun'].unique(), reverse=True))

                    df_filtered = df_all[(df_all['bulan'] == sel_bulan) & (df_all['tahun'] == sel_tahun)]
                    if sel_kec != "Semua Kecamatan":
                        df_filtered = df_filtered[df_filtered['kecamatan'] == sel_kec]
                        
                    st.write("---")
                    total_berat = df_filtered['berat_kg'].sum()
                    st.metric(f"Total Sampah ({sel_kec})", f"{total_berat:,.1f} Kg")
                    st.dataframe(df_filtered[['tanggal', 'kecamatan', 'lokasi', 'kategori', 'berat_kg']], 
                                 use_container_width=True, hide_index=True)
                else:
                    st.info("Belum ada data laporan untuk periode ini.")

        # --- TAB: INPUT DATA ---
        elif nama_tab == "📝 Input Data":
            with tabs[i]:
                st.subheader("📝 Form Input Sampah Harian & Foto Kondisi")
                list_lokasi = get_list_lokasi()
                
                if not list_lokasi:
                    st.warning("⚠️ Belum ada lokasi TPS3R/TPA di database.")
                else:
                    with st.form("form_sampah_lokasi", clear_on_submit=True):
                        col1, col2 = st.columns(2)
                        with col1:
                            lokasi_pilih = st.selectbox("Pilih Lokasi Unit", list_lokasi)
                            tgl = st.date_input("Tanggal Operasional", datetime.now())
                        with col2:
                            kategori = st.selectbox("Kategori Sampah", ["Organik", "Anorganik", "Residu/B3"])
                            berat = st.number_input("Berat Masuk (Kg)", min_value=0.0, step=1.0)
                        
                        # Label diubah untuk menginformasikan batas maksimal ukuran
                        uploaded_file = st.file_uploader("📷 Ambil Foto Kondisi TPS (Maksimal 1 MB)", type=["jpg", "png", "jpeg"])
                        submit = st.form_submit_button("Simpan Laporan & Foto")
                        
                        if submit:
                            if berat <= 0:
                                st.error("Berat sampah harus lebih dari 0!")
                            elif uploaded_file is None:
                                st.error("⚠️ Wajib mengunggah foto kondisi TPS!")
                            else:
                                # ==================================================================
                                # VALDASI UKURAN FILE: Batasi Maksimal 1 MB
                                # ==================================================================
                                ukuran_file_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
                                
                                if ukuran_file_mb > 1.0:
                                    st.error(f"❌ Ukuran file foto terlalu besar ({ukuran_file_mb:.2f} MB)! Maksimal ukuran yang diperbolehkan adalah 1.00 MB. Silakan kecilkan resolusi kamera Anda.")
                                else:
                                    # Jika lolos validasi ukuran, kueri database dilanjutkan
                                    conn = sqlite3.connect('sampah.db')
                                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                    nama_foto_baru = f"{lokasi_pilih}_{kategori}_{timestamp}.jpg"
                                    try:
                                        conn.execute("""
                                            INSERT INTO laporan (tanggal, berat_kg, kategori, admin_input, foto_path) 
                                            VALUES (?, ?, ?, ?, ?)
                                        """, (tgl, berat, kategori, lokasi_pilih, nama_foto_baru))
                                        conn.commit()
                                    
                                        if not os.path.exists("data_foto"):
                                            os.makedirs("data_foto")
                                        
                                        filepath_simpan = os.path.join("data_foto", nama_foto_baru)
                                        with open(filepath_simpan, "wb") as f:
                                            f.write(uploaded_file.getvalue())
                                        
                                        st.success(f"✅ Data sampah di {lokasi_pilih} berhasil disimpan!")
                                        st.cache_data.clear()
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Gagal menyimpan: {e}")
                                    finally:
                                        conn.close()

                # --- RIWAYAT INPUT ---
                st.divider()
                st.subheader("🕒 Riwayat Input Terakhir")
                
                # 1. Ambil informasi user yang sedang login dari session state
                username_aktif = st.session_state.get('username', '')
                role_aktif = st.session_state.get('role', '')
                
                # 2. Atur kueri SQL berdasarkan hak akses (Role)
                if role_aktif == 'admin_lh':
                    # Admin Dinas LH berhak melihat seluruh data masuk terbaru
                    query_riwayat = "SELECT id, tanggal, berat_kg, kategori, admin_input as lokasi, foto_path FROM laporan ORDER BY id DESC LIMIT 5"
                else:
                    # Petugas biasa hanya melihat data berdasarkan lokasi unit yang sedang diurusi saat ini
                    # (Menghindari petugas mengintip data milik TPS3R/BSU lain)
                    query_riwayat = f"SELECT id, tanggal, berat_kg, kategori, admin_input as lokasi, foto_path FROM laporan WHERE admin_input = '{lokasi_pilih}' ORDER BY id DESC LIMIT 5"
                
                # 3. Jalankan kueri yang sudah difilter
                df_riwayat = jalankan_query(query_riwayat)
                
                if not df_riwayat.empty:
                    for index, row in df_riwayat.iterrows():
                        with st.expander(f"Data {row['lokasi']} - {row['tanggal']} ({row['kategori']})"):
                            st.write(f"Berat: {row['berat_kg']} Kg")
                            if row['foto_path'] and pd.notnull(row['foto_path']):
                                foto_full_path = os.path.join("data_foto", row['foto_path'])
                                if os.path.exists(foto_full_path):
                                    st.image(foto_full_path, width=300)
                            
                            if st.button(f"Hapus ID {row['id']}", key=f"hapus_{row['id']}"):
                                with sqlite3.connect('sampah.db') as conn:
                                    conn.execute("DELETE FROM laporan WHERE id = ?", (row['id'],))
                                    conn.commit()
                                st.warning(f"Data ID {row['id']} telah dihapus.")
                                st.rerun()
                else:
                    st.info("Belum ada riwayat input untuk lokasi ini.")

        # --- TAB: MANAJEMEN MASTER ---
        elif nama_tab == "⚙️ Manajemen Master":
            LIST_KECAMATAN = ["Brebes", "Wanasari", "Bulakamba", "Tanjung", "Losari", "Kersana", 
                              "Ketanggungan", "Larangan", "Banjarharjo", "Salem", "Bantarkawung", 
                              "Bumiayu", "Sirampog", "Tonjong", "Songgom", "Jatibarang", "Paguyangan"]
            
            # Tambahkan kategori baru ke list tipe untuk form & editor
            LIST_TIPE = ["TPS3R", "TPA", "TPST", "Bank Sampah Induk", "Bank Sampah Unit"]
            
            with tabs[i]:
                st.subheader("⚙️ Manajemen Master Data Lokasi Unit")
                
                # ======================================================================
                # 🟢 FITUR BARU: UPLOAD MASSAL DATA LOKASI VIA CSV
                # ======================================================================
                with st.expander("📥 Upload Massal Data Lokasi (via CSV)", expanded=False):
                    st.markdown("""
                    ##### 📄 Panduan Format CSV:
                    Buat file di Excel/Google Sheets dengan **5 nama kolom (header)** berikut, lalu simpan sebagai `.csv`:
                    * `nama_unit` : Nama fasilitas (Contoh: *TPS3R Berhias*)
                    * `kecamatan` : Harus sesuai daftar kecamatan di Brebes (Contoh: *Brebes, Bulakamba*)
                    * `tipe`      : Isi dengan: *TPS3R, TPA, TPST, Bank Sampah Induk,* atau *Bank Sampah Unit*
                    * `lat`       : Koordinat Latitude menggunakan desimal titik (Contoh: *-6.8721*)
                    * `lon`       : Koordinat Longitude menggunakan desimal titik (Contoh: *109.0421*)
                    """)
                    
                    uploaded_file = st.file_uploader("Pilih file CSV data lokasi", type=["csv"], key="uploader_csv_lokasi")
                    
                    if uploaded_file is not None:
                        try:
                            # Membaca data CSV
                            import pandas as pd
                            # [PERBAIKAN 1] Menggunakan sep=None & engine='python' agar otomatis mengenali pembatas koma (,) atau titik koma (;) dari Excel
                            df_csv = pd.read_csv(uploaded_file, sep=None, engine='python')
            
                            # [PERBAIKAN 2] Bersihkan spasi atau karakter BOM (\ufeff) tersembunyi pada nama kolom, lalu paksa huruf kecil semua
                            df_csv.columns = df_csv.columns.str.replace(r'^\ufeff', '', regex=True).str.strip().str.lower()
                                                        
                            # Validasi nama kolom wajib
                            kolom_wajib = {'nama_unit', 'kecamatan', 'tipe', 'lat', 'lon'}
                            if not kolom_wajib.issubset(df_csv.columns):
                                st.error(f"❌ Format kolom salah! Kolom terdeteksi: {list(df_csv.columns)}")
                                st.info("Pastikan nama kolom pada baris pertama adalah: nama_unit, kecamatan, tipe, lat, lon")
                            else:
                                # [PERBAIKAN 3] Bersihkan data teks umum dari spasi luar
                                df_csv['nama_unit'] = df_csv['nama_unit'].astype(str).str.strip()
                                df_csv['kecamatan'] = df_csv['kecamatan'].astype(str).str.strip()
                                df_csv['tipe'] = df_csv['tipe'].astype(str).str.strip()
                
                                # [PERBAIKAN 4] MENJINAKKAN TANDA PETIK SATU (') DI KOLOM LAT & LON
                                # Mengubah data ke string, membuang tanda petik satu atau dua, lalu dikonversi menjadi angka desimal
                                df_csv['lat'] = df_csv['lat'].astype(str).str.replace("'", "", regex=False).str.replace('"', '', regex=False).str.strip()
                                df_csv['lon'] = df_csv['lon'].astype(str).str.replace("'", "", regex=False).str.replace('"', '', regex=False).str.strip()

                                df_csv['lat'] = pd.to_numeric(df_csv['lat'], errors='coerce')
                                df_csv['lon'] = pd.to_numeric(df_csv['lon'], errors='coerce')
                
                                # Hapus baris jika ada koordinat yang gagal dikonversi (misal baris kosong)
                                df_csv = df_csv.dropna(subset=['lat', 'lon'])
            
                                st.write("👀 **Pratinjau Data CSV:**")
                                st.dataframe(df_csv, use_container_width=True)
                                
                                btn_simpan_csv = st.button("💾 Konfirmasi & Masukkan Data Massal", type="primary")
                                if btn_simpan_csv:
                                    jumlah_sukses = 0
                                    jumlah_duplikat = 0
                                    
                                    with sqlite3.connect('sampah.db') as conn:
                                        cursor = conn.cursor()
                                        
                                        # Pastikan tabel lokasi sudah terbuat
                                        cursor.execute("""
                                            CREATE TABLE IF NOT EXISTS lokasi (
                                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                nama_unit TEXT NOT NULL,
                                                kecamatan TEXT NOT NULL,
                                                tipe TEXT NOT NULL,
                                                lat REAL NOT NULL,
                                                lon REAL NOT NULL
                                            )
                                        """)
                                        
                                        # Proses looping insert data
                                        for _, row in df_csv.iterrows():
                                            nama_clean = str(row['nama_unit']).strip()
                                            
                                            # Cek pencegahan data ganda
                                            cursor.execute("SELECT id FROM lokasi WHERE nama_unit = ?", (nama_clean,))
                                            if cursor.fetchone() is None:
                                                cursor.execute("""
                                                    INSERT INTO lokasi (nama_unit, kecamatan, tipe, lat, lon)
                                                    VALUES (?, ?, ?, ?, ?)
                                                """, (nama_clean, str(row['kecamatan']).strip(), str(row['tipe']).strip(), float(row['lat']), float(row['lon'])))
                                                jumlah_sukses += 1
                                            else:
                                                jumlah_duplikat += 1
                                                
                                        conn.commit()
                                    
                                    # Output notifikasi hasil upload
                                    if jumlah_sukses > 0:
                                        st.success(f"🎉 Sukses! Berhasil menambahkan {jumlah_sukses} titik lokasi baru.")
                                        if jumlah_duplikat > 0:
                                            st.warning(f"⚠️ {jumlah_duplikat} data dilewati karena nama unit sudah ada di database.")
                                        st.cache_data.clear()
                                        st.rerun()
                                    else:
                                        st.warning("⚠️ Tidak ada data baru yang masuk. Semua nama unit di CSV sudah terdaftar.")
                                        
                        except Exception as e:
                            st.error(f"❌ Terjadi kesalahan pembacaal file: {e}")
                
                # ======================================================================
                # 🔵 FORM TAMBAH LOKASI MANUALE (BAWAAN ASLI)
                # ======================================================================
                with st.expander("➕ Tambah Titik Lokasi Baru (TPA / TPS3R / Bank Sampah)", expanded=False):
                    with st.form("form_tambah_master_lokasi", clear_on_submit=True):
                        st.markdown("##### 📍 Formulir Data Infrastruktur")
                        
                        f_nama_unit = st.text_input("Nama Unit/Lokasi", placeholder="Contoh: BSU Berkah Jaya / TPS3R Kelurahan")
                        f_kecamatan = st.selectbox("Kecamatan", LIST_KECAMATAN)
                        f_tipe = st.selectbox("Tipe / Kategori Lokasi", LIST_TIPE)
                        
                        col_lat, col_lng = st.columns(2)
                        with col_lat:
                            f_lat = st.number_input("Koordinat Latitude (Lat)", format="%.6f", value=-6.870000)
                        with col_lng:
                            f_lon = st.number_input("Koordinat Longitude (Lon)", format="%.6f", value=109.040000)
                            
                        btn_simpan_lokasi = st.form_submit_button("💾 Daftarkan Lokasi Baru")
                        
                        if btn_simpan_lokasi:
                            if not f_nama_unit.strip():
                                st.error("❌ Gagal! Nama unit/lokasi wajib diisi.")
                            else:
                                try:
                                    with sqlite3.connect('sampah.db') as conn:
                                        conn.execute("""
                                            INSERT INTO lokasi (nama_unit, kecamatan, tipe, lat, lon)
                                            VALUES (?, ?, ?, ?, ?)
                                        """, (f_nama_unit.strip(), f_kecamatan, f_tipe, f_lat, f_lon))
                                        conn.commit()
                                        
                                    st.success(f"🎉 Sukses! [{f_tipe}] baru '{f_nama_unit}' berhasil didaftarkan.")
                                    st.cache_data.clear()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Gagal menyimpan ke database: {e}")
                
                st.write("---")
                st.markdown("### 🗂️ Daftar & Edit Data Lokasi Terdaftar")
                
                # Mengambil data dari tabel 'lokasi'
                df_lokasi_edit = jalankan_query("SELECT id, nama_unit, kecamatan, tipe, lat, lon FROM lokasi")
                
                if not df_lokasi_edit.empty:
                    # Menyisipkan nomor urut 1, 2, 3... di kolom paling awal
                    df_lokasi_edit.insert(0, 'No', range(1, len(df_lokasi_edit) + 1))
                    
                    edited_df = st.data_editor(
                        df_lokasi_edit,
                        column_config={
                            "No": st.column_config.Column("No", width=40, disabled=True),
                            "id": None, # Menyembunyikan kolom ID
                            "nama_unit": st.column_config.Column("Nama Unit/Lokasi"),
                            "kecamatan": st.column_config.SelectboxColumn("Kecamatan", options=LIST_KECAMATAN, required=True),
                            "tipe": st.column_config.SelectboxColumn("Tipe", options=LIST_TIPE, required=True),
                        },
                        hide_index=True, use_container_width=True, key="editor_lokasi"
                    )
                    
                    if st.button("💾 Simpan Perubahan"):
                        with sqlite3.connect('sampah.db') as conn:
                            for index, row in edited_df.iterrows():
                                conn.execute("UPDATE lokasi SET nama_unit=?, kecamatan=?, tipe=?, lat=?, lon=? WHERE id=?", 
                                             (row['nama_unit'], row['kecamatan'], row['tipe'], row['lat'], row['lon'], row['id']))
                            conn.commit()
                        st.success("✅ Perubahan data lokasi berhasil disimpan!")
                        st.cache_data.clear()
                        st.rerun()

        # --- TAB: APPROVAL AKUN ---
        elif nama_tab == "👥 Approval Akun":
            with tabs[i]:
                halaman_approval_admin()

        # --- TAB: PROFIL SAYA ---
        elif nama_tab == "👤 Profil Saya":
            with tabs[i]:
                halaman_profil_user()
