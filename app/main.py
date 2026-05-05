from fastapi import FastAPI, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from app.database import get_connection

app = FastAPI()

# =========================================================
# ✅ CORS
# =========================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restringir en producción
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
# 🧪 TEST
# =========================================================
@app.get("/ping")
def ping():
    return {"status": "ok"}

@app.get("/test-connection")
def test_connection():
    conn = get_connection()
    if conn:
        conn.close()
        return {"status": "conexion exitosa"}
    return {"status": "fallo conexion"}

# =========================================================
# 📊 VENDEDORES (DINÁMICO DESDE SQL)
# =========================================================
@app.get("/vendedores")
def obtener_vendedores():
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
        SELECT DISTINCT
            CASE 
                WHEN c.Vendedor = 155 THEN 'JOHN'
                WHEN c.Vendedor = 1023 THEN 'NEYRA'
                WHEN c.Vendedor = 944 THEN 'PATRICIA'
                WHEN c.Vendedor = 268 THEN 'JAVIER'
                WHEN c.Vendedor = 935 THEN 'ALEX'
                WHEN c.Vendedor IN (3,1043) THEN 'FREDDY'
                WHEN c.Vendedor = 978 THEN 'SOFÍA'
                ELSE 'SIN ASIGNAR'
            END AS vendedor
        FROM [ServidorLectura].db_a40d06_plastic.dbo.CM_Documento c
        """)

        return [row[0] for row in cursor.fetchall()]

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
        cursor = conn.cursor()

        cursor.execute("""
        IF EXISTS (
            SELECT 1 FROM comisiones_config
            WHERE vendedor_nombre = %s AND fecha_mes = %s
        )
            UPDATE comisiones_config
            SET porcentaje = %s
            WHERE vendedor_nombre = %s AND fecha_mes = %s
        ELSE
            INSERT INTO comisiones_config (vendedor_nombre, fecha_mes, porcentaje)
            VALUES (%s, %s, %s)
        """, (vendedor, fecha_mes, porcentaje,
              vendedor, fecha_mes,
              vendedor, fecha_mes, porcentaje))

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
# 💰 COMISIONES (OPTIMIZADO)
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
        WITH base AS (
            SELECT
                CONCAT(c.TipoDocumento,'-',c.NumeroDocumento) AS factura,
                CAST(c.FechaDocumento AS DATE) AS fecha,
                DATEFROMPARTS(YEAR(c.FechaDocumento), MONTH(c.FechaDocumento), 1) AS fecha_mes,
                d.MontoFinal AS monto,

                CASE 
                    WHEN c.Vendedor = 155 THEN 'JOHN'
                    WHEN c.Vendedor = 1023 THEN 'NEYRA'
                    WHEN c.Vendedor = 944 THEN 'PATRICIA'
                    WHEN c.Vendedor = 268 THEN 'JAVIER'
                    WHEN c.Vendedor = 935 THEN 'ALEX'
                    WHEN c.Vendedor IN (3,1043) THEN 'FREDDY'
                    WHEN c.Vendedor = 978 THEN 'SOFÍA'
                    ELSE 'SIN ASIGNAR'
                END AS vendedor

            FROM [ServidorLectura].db_a40d06_plastic.dbo.CM_DocumentoDetalle d
            INNER JOIN [ServidorLectura].db_a40d06_plastic.dbo.CM_Documento c
                ON d.Compania=c.Compania
               AND d.TipoDocumento=c.TipoDocumento
               AND d.NumeroDocumento=c.NumeroDocumento
        )

        SELECT
            vendedor,
            fecha_mes,
            SUM(monto) AS total,
            ISNULL(cfg.porcentaje, 0.015) AS porcentaje
        FROM base b
        LEFT JOIN comisiones_config cfg
            ON b.vendedor = cfg.vendedor_nombre
           AND b.fecha_mes = cfg.fecha_mes
        WHERE 1=1
        """

        params = []

        if vendedor:
            query += " AND vendedor = %s"
            params.append(vendedor)

        if mes:
            query += " AND CONVERT(VARCHAR(7), fecha_mes, 120) = %s"
            params.append(mes)

        query += """
        GROUP BY vendedor, fecha_mes, cfg.porcentaje
        ORDER BY fecha_mes DESC
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
# 📄 DETALLE FACTURAS COBRADAS
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
            CONCAT(c.TipoDocumento,'-',c.NumeroDocumento) AS factura,
            CAST(c.FechaDocumento AS DATE) AS fecha,

            CASE 
                WHEN c.Vendedor = 155 THEN 'JOHN'
                WHEN c.Vendedor = 1023 THEN 'NEYRA'
                WHEN c.Vendedor = 944 THEN 'PATRICIA'
                WHEN c.Vendedor = 268 THEN 'JAVIER'
                WHEN c.Vendedor = 935 THEN 'ALEX'
                WHEN c.Vendedor IN (3,1043) THEN 'FREDDY'
                WHEN c.Vendedor = 978 THEN 'SOFÍA'
                ELSE 'SIN ASIGNAR'
            END AS vendedor,

            d.MontoFinal AS monto

        FROM [ServidorLectura].db_a40d06_plastic.dbo.CM_DocumentoDetalle d
        INNER JOIN [ServidorLectura].db_a40d06_plastic.dbo.CM_Documento c
            ON d.Compania=c.Compania
           AND d.TipoDocumento=c.TipoDocumento
           AND d.NumeroDocumento=c.NumeroDocumento
        WHERE 1=1
        """

        params = []

        if vendedor:
            query += " AND c.Vendedor = %s"
            params.append(vendedor)

        if mes:
            query += " AND CONVERT(VARCHAR(7), c.FechaDocumento, 120) = %s"
            params.append(mes)

        cursor.execute(query, params)

        return [
            {
                "factura": r[0],
                "fecha": str(r[1]),
                "vendedor": r[2],
                "monto": float(r[3])
            }
            for r in cursor.fetchall()
        ]

    except Exception as e:
        return {"error_real": str(e)}

    finally:
        if conn:
            conn.close()