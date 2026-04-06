import sqlite3
import os

def inisialisasi_db():
    # Pastikan koneksi ke database di lokasi yang sama
    db_path = 'sampah.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Tabel User (Multi-User)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')

    # 2. Tabel Lokasi TPS3R/TPA (DIPERBARUI: Ditambah Kolom Kecamatan)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lokasi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama_unit TEXT UNIQUE,
            kecamatan TEXT,
            tipe TEXT,
            lat REAL,
            lon REAL
        )
    ''')

    # 3. Tabel Laporan Sampah
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS laporan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tanggal DATE,
            berat_kg REAL,
            kategori TEXT,
            admin_input TEXT,
            FOREIGN KEY (admin_input) REFERENCES lokasi (nama_unit)
        )
    ''')

    # --- FITUR MIGRASI AUTOMATIS ---
    # Jika tabel lokasi sudah ada tapi belum ada kolom kecamatan, kita tambahkan manual
    try:
        cursor.execute("ALTER TABLE lokasi ADD COLUMN kecamatan TEXT")
        print("Kolom 'kecamatan' berhasil ditambahkan ke tabel lokasi.")
    except sqlite3.OperationalError:
        # Error ini muncul jika kolom sudah ada, jadi kita abaikan saja
        pass

    # --- DATA DEFAULT ---
    # Isi User Default
    users_default = [
        ('super_admin', 'admin123', 'super_admin'),
        ('dinas_lh', 'lh2026', 'admin_lh')
    ]
    cursor.executemany("INSERT OR IGNORE INTO users VALUES (?,?,?)", users_default)

    # Contoh Pengisian Unit dengan Kecamatan (Opsional/Testing)
    # Ini akan memasukkan unit jika belum ada (Insert or Ignore)
    unit_contoh = [
        ('TPS3R Brebes Kota', 'Brebes', 'TPS3R', -6.871, 109.041),
        ('TPS3R Jatibarang Baru', 'Jatibarang', 'TPS3R', -6.965, 109.052)
    ]
    cursor.executemany("INSERT OR IGNORE INTO lokasi (nama_unit, kecamatan, tipe, lat, lon) VALUES (?,?,?,?,?)", unit_contoh)

    conn.commit()
    conn.close()
    print(f"Database '{db_path}' Berhasil Diperbarui dengan Kolom Kecamatan!")

if __name__ == "__main__":
    inisialisasi_db()