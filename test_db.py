from database import get_connection

try:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sys.tables")
    print("BAGLANTI BASARILI. Tablolar:")
    for row in cur.fetchall():
        print(" -", row[0])
    conn.close()
except Exception as e:
    print("BAGLANTI HATASI:")
    print(e)