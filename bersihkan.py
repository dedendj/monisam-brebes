import sqlite3

def bersihkan_duplikat():
    # Pastikan nama file database sesuai
    conn = sqlite3.connect('sampah.db')
    cursor = conn.cursor()
    
    print("--- PROSES PEMBERSIHAN DUPLIKAT UNIT ---")
    
    # Query untuk menghapus baris dengan nama yang sama, sisakan satu ID terkecil
    query = """
    DELETE FROM lokasi 
    WHERE id NOT IN (
        SELECT MIN(id) 
        FROM lokasi 
        GROUP BY nama_unit
    )
    """
    
    try:
        cursor.execute(query)
        jumlah_terhapus = cursor.rowcount
        conn.commit()
        print(f"✅ Berhasil menghapus {jumlah_terhapus} baris duplikat.")
    except Exception as e:
        print(f"❌ Terjadi kesalahan: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    bersihkan_duplikat()