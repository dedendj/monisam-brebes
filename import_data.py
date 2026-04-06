import sqlite3
import csv
import os

def import_csv_ke_db(file_csv):
    # Koneksi ke database
    conn = sqlite3.connect('sampah.db')
    cursor = conn.cursor()

    # Cek apakah file CSV ada
    if not os.path.exists(file_csv):
        print(f"❌ File {file_csv} tidak ditemukan!")
        return

    print("=== PROSES IMPORT DATA TITIK SAMPAH ===")
    
    with open(file_csv, mode='r', encoding='utf-8') as f:
        # Gunakan delimiter ';' sesuai format data Anda
        reader = csv.DictReader(f, delimiter=';')
        
        for row in reader:
            nama = row['nama']
            tipe = row['tipe']
            lat = row['lat']
            lon = row['lon']
            
            # Meminta input kecamatan secara manual di terminal
            print(f"\n📍 Unit: {nama} ({tipe})")
            kec = input(f"   Masukkan nama kecamatan untuk {nama}: ")

            # Masukkan ke Database (Update jika sudah ada)
            cursor.execute("""
                INSERT OR REPLACE INTO lokasi (nama_unit, tipe, lat, lon, kecamatan) 
                VALUES (?, ?, ?, ?, ?)
            """, (nama, tipe, lat, lon, kec))
            
        conn.commit()
    conn.close()
    print("\n✅ SELESAI! Semua data berhasil masuk ke Database 'sampah.db'.")

if __name__ == "__main__":
    # Menjalankan fungsi dengan file CSV Anda
    import_csv_ke_db('titik_sampah.csv')