from fastapi import FastAPI, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from app.database import get_connection

app = FastAPI()

# =========================================================
# ✅ CORS
# =========================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # en producción luego lo restringes
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# 🏠 HOME
# =========================================================
@app.get("/")
def home():
    return {"mensaje": "API ERP de comisiones 🚀"}

# =========================================================
# 📊 VENDEDORES
# =========================================================
@app.get("/vendedores")
def obtener_vendedores():
    conn = None
    try:
        conn = get_connection()
        if conn is None:
            return {"error": "sin conexión a BD"}

        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT vendedor_nombre
            FROM vw_comercial_base2
        """)

        data = [row[0] for row in cursor.fetchall()]
        return data

    except Exception as e:
        return {"error_real": str(e)}

    finally:
        if conn:
            conn.close()

# =========================================================
# 💰 CONFIG COMISIONES
# =========================================================
@app.post("/config-comision")
def guardar_comision(
    vendedor: str = Body(...),
    fecha_mes: str = Body(...),
    porcentaje: float = Body(...)
):
    conn = None
    try:
        if porcentaje < 0 or porcentaje > 0.1:
            return {"error": "Porcentaje inválido (0 - 10%)"}

        conn = get_connection()
        if conn is None:
            return {"error": "sin conexión a BD"}

        cursor = conn.cursor()

        cursor.execute("""
            IF EXISTS (
                SELECT 1 FROM comisiones_config
                WHERE vendedor_nombre = ? AND fecha_mes = ?
            )
            UPDATE comisiones_config
            SET porcentaje = ?
            WHERE vendedor_nombre = ? AND fecha_mes = ?
            ELSE
            INSERT INTO comisiones_config (vendedor_nombre, fecha_mes, porcentaje)
            VALUES (?, ?, ?)
        """, (vendedor, fecha_mes, porcentaje, vendedor, fecha_mes, vendedor, fecha_mes, porcentaje))

        conn.commit()
        return {"mensaje": "Comisión guardada"}

    except Exception as e:
        return {"error_real": str(e)}

    finally:
        if conn:
            conn.close()

# =========================================================
# 📊 LISTAR CONFIG
# =========================================================
@app.get("/config-comisiones")
def listar_config():
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT vendedor_nombre, fecha_mes, porcentaje
            FROM comisiones_config
            ORDER BY fecha_mes DESC
        """)

        return [
            {
                "vendedor": r[0],
                "mes": str(r[1]),
                "porcentaje": float(r[2])
            }
            for r in cursor.fetchall()
        ]

    except Exception as e:
        return {"error_real": str(e)}

    finally:
        if conn:
            conn.close()

# =========================================================
# 💰 COMISIONES
# =========================================================
@app.get("/comisiones-vendedor")
def comisiones_por_vendedor(
    vendedor: str = Query(None),
    mes: str = Query(None)
):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = """
        SELECT
            v.vendedor_nombre,
            v.fecha_mes,
            SUM(v.ventas_monto) AS total_ventas,
            ISNULL(c.porcentaje, 0.015) AS porcentaje
        FROM vw_comercial_base2 v
        INNER JOIN fact_ventas_erp f
            ON v.numero_factura = f.numero_factura
        LEFT JOIN comisiones_config c
            ON v.vendedor_nombre = c.vendedor_nombre
            AND v.fecha_mes = c.fecha_mes
        WHERE f.monto_cobrado >= f.monto_factura
        """

        params = []

        if vendedor:
            query += " AND v.vendedor_nombre = ?"
            params.append(vendedor)

        if mes:
            query += " AND CONVERT(VARCHAR(7), v.fecha_mes, 120) = ?"
            params.append(mes)

        query += """
        GROUP BY v.vendedor_nombre, v.fecha_mes, c.porcentaje
        ORDER BY v.fecha_mes DESC
        """

        cursor.execute(query, params)

        result = []

        for row in cursor.fetchall():
            total = float(row[2] or 0)
            porcentaje = float(row[3] or 0.015)

            base = total / 1.18
            comision = base * porcentaje

            result.append({
                "vendedor": row[0],
                "mes": str(row[1]),
                "ventas": round(total, 2),
                "base": round(base, 2),
                "porcentaje": porcentaje,
                "comision": round(comision, 2)
            })

        return result

    except Exception as e:
        return {"error_real": str(e)}

    finally:
        if conn:
            conn.close()

# =========================================================
# 📄 DETALLE FACTURA
# =========================================================
@app.get("/comisiones-detalle")
def comisiones_detalle(
    vendedor: str = Query(None),
    mes: str = Query(None)
):
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        query = """
        SELECT
            v.numero_factura,
            v.vendedor_nombre,
            v.fecha,
            v.fecha_mes,
            f.monto_factura,
            f.monto_cobrado
        FROM vw_comercial_base2 v
        INNER JOIN fact_ventas_erp f
            ON v.numero_factura = f.numero_factura
        WHERE f.monto_cobrado >= f.monto_factura
        """

        params = []

        if vendedor:
            query += " AND v.vendedor_nombre = ?"
            params.append(vendedor)

        if mes:
            query += " AND CONVERT(VARCHAR(7), v.fecha_mes, 120) = ?"
            params.append(mes)

        cursor.execute(query, params)

        return [
            {
                "factura": r[0],
                "vendedor": r[1],
                "fecha": str(r[2]),
                "mes": str(r[3]),
                "monto_factura": float(r[4]),
                "monto_cobrado": float(r[5]),
                "estado": "COBRADO"
            }
            for r in cursor.fetchall()
        ]

    except Exception as e:
        return {"error_real": str(e)}

    finally:
        if conn:
            conn.close()

# =========================================================
# 🧪 TEST CONEXIÓN
# =========================================================
@app.get("/test-connection")
def test_connection():
    conn = get_connection()
    if conn:
        conn.close()
        return {"status": "conexion exitosa"}
    return {"status": "fallo conexion"}