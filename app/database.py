import pymssql
import os
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    try:
        conn = pymssql.connect(
            server=os.getenv("DB_SERVER"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_DATABASE"),
            port=int(os.getenv("DB_PORT", 1433)),
            login_timeout=10,
            timeout=30,
            as_dict=False  # puedes cambiar a True si quieres dict automático
        )
        return conn

    except Exception as e:
        print("❌ ERROR CONEXIÓN:", str(e))
        return None
    