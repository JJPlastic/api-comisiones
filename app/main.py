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
        FROM db_a40d06_plastic.dbo.CM_Documento c
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

            FROM db_a40d06_plastic.dbo.CM_DocumentoDetalle d
            INNER JOIN db_a40d06_plastic.dbo.CM_Documento c
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

        FROM db_a40d06_plastic.dbo.CM_DocumentoDetalle d
        INNER JOIN db_a40d06_plastic.dbo.CM_Documento c
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

@app.get("/comercial-base")
def comercial_base(
    vendedor: str = Query(None),
    mes: str = Query(None)
):
    conn = None
    try:
        conn = get_connection()
        if not conn:
            return {"error": "No hay conexión"}

        cursor = conn.cursor()

        query = """
        WITH pagos AS (
            SELECT
                dt.Compania,
                dt.TipoDocumento,
                dt.NumeroDocumento,
                MAX(t.Fecha) AS fecha_pago,
                SUM(dt.Monto) AS monto_cobrado_documento
            FROM db_a40d06_plastic.dbo.CM_DocumentoTransaccion dt
            INNER JOIN db_a40d06_plastic.dbo.CM_Transaccion t
                ON dt.UnidadReplicacion = t.UnidadReplicacion
               AND dt.Transaccion = t.Transaccion
            WHERE t.Estado <> 'A'
            GROUP BY dt.Compania, dt.TipoDocumento, dt.NumeroDocumento
        )

        SELECT 
            v.Compania,

            CASE 
                WHEN v.Compania = '01' THEN 'Tinki'
                WHEN v.Compania = '02' THEN 'JJPlastic'
                ELSE 'Otra'
            END AS empresa,

            v.cliente_id,
            dc.Nombre AS cliente,

            -- 🔥 VENDEDOR
            CASE 
                WHEN c.Vendedor = 155 THEN 'JOHN'
                WHEN c.Vendedor = 1023 THEN 'NEYRA'
                WHEN c.Vendedor = 944 THEN 'PATRICIA'
                WHEN c.Vendedor = 268 THEN 'JAVIER'
                WHEN c.Vendedor = 935 THEN 'ALEX'
                WHEN c.Vendedor IN (3,1043) THEN 'FREDDY'
                WHEN c.Vendedor = 978 THEN 'SOFÍA'
                ELSE 'SIN ASIGNAR'
            END AS vendedor_nombre,

            CASE 
                WHEN c.Vendedor IN (3,1043) THEN 3
                ELSE c.Vendedor
            END AS vendedor_codigo,

            v.fecha,
            DATEFROMPARTS(YEAR(v.fecha), MONTH(v.fecha), 1) AS fecha_mes,

            v.numero_factura,
            v.producto_id,
            dp.Descripcion AS producto,

            v.cantidad_ajustada,
            v.total_linea_original AS ventas,
            ISNULL(v.monto_cobrado_linea,0) AS cobrado,

            CASE
                WHEN v.total_linea_original = 0 THEN 'Sin facturar'
                WHEN ISNULL(v.monto_cobrado_linea,0) = 0 THEN 'Pendiente'
                WHEN v.monto_cobrado_linea < v.total_linea_original THEN 'Parcial'
                ELSE 'Cobrado'
            END AS estado

        FROM (

            SELECT 
                d.Compania,
                CONCAT(c.TipoDocumento,'-',c.NumeroDocumento) AS numero_factura,
                c.Cliente AS cliente_id,
                CAST(c.FechaDocumento AS DATE) AS fecha,
                d.Articulo AS producto_id,

                CASE 
                    WHEN YEAR(c.FechaDocumento)=2026 AND d.Unidad='UND'
                    THEN ABS(d.Cantidad)/12.0
                    ELSE d.Cantidad
                END AS cantidad_ajustada,

                d.MontoFinal AS total_linea_original,

                ISNULL(p.monto_cobrado_documento,0) AS monto_cobrado_documento,

                d.MontoFinal * 1.0 /
                SUM(d.MontoFinal) OVER (
                    PARTITION BY d.Compania,d.TipoDocumento,d.NumeroDocumento
                ) * ISNULL(p.monto_cobrado_documento,0)
                AS monto_cobrado_linea

            FROM db_a40d06_plastic.dbo.CM_DocumentoDetalle d

            INNER JOIN db_a40d06_plastic.dbo.CM_Documento c
                ON d.Compania=c.Compania
               AND d.TipoDocumento=c.TipoDocumento
               AND d.NumeroDocumento=c.NumeroDocumento

            LEFT JOIN pagos p
                ON c.Compania=p.Compania
               AND c.TipoDocumento=p.TipoDocumento
               AND c.NumeroDocumento=p.NumeroDocumento

            WHERE d.TipoDocumento IN ('BV','FA','NC','RC')

        ) v

        LEFT JOIN db_a40d06_plastic.dbo.Persona dc
            ON v.cliente_id = dc.Persona

        LEFT JOIN db_a40d06_plastic.dbo.LG_Articulo dp
            ON v.producto_id = dp.Articulo

        INNER JOIN db_a40d06_plastic.dbo.CM_Documento c
            ON v.numero_factura =
               CONCAT(c.TipoDocumento,'-',c.NumeroDocumento)

        WHERE 1=1
        """

        params = []

        if vendedor:
            query += " AND (CASE WHEN c.Vendedor=155 THEN 'JOHN' WHEN c.Vendedor=1023 THEN 'NEYRA' WHEN c.Vendedor=944 THEN 'PATRICIA' WHEN c.Vendedor=268 THEN 'JAVIER' WHEN c.Vendedor=935 THEN 'ALEX' WHEN c.Vendedor IN (3,1043) THEN 'FREDDY' WHEN c.Vendedor=978 THEN 'SOFÍA' ELSE 'SIN ASIGNAR' END) = %s"
            params.append(vendedor)

        if mes:
            query += " AND CONVERT(VARCHAR(7), v.fecha, 120) = %s"
            params.append(mes)

        cursor.execute(query, params)

        columns = [col[0] for col in cursor.description]

        data = [
            dict(zip(columns, row))
            for row in cursor.fetchall()
        ]

        return data

    except Exception as e:
        return {"error_real": str(e)}

    finally:
        if conn:
            conn.close()