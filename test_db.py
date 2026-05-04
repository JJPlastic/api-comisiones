from app.database import get_connection_local

conn = get_connection_local()

if conn:
    cursor = conn.cursor()
    cursor.execute("SELECT TOP 5 * FROM INFORMATION_SCHEMA.TABLES")
    
    for row in cursor.fetchall():
        print(row)