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
            port=1433  # puerto SQL Server estándar
        )
        return conn

    except Exception as e:
        print("❌ ERROR CONEXIÓN:", e)
        return None
    
    