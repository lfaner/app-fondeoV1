"""
Descarga movimientos desde la API de Aunesa y los guarda en PostgreSQL.
Reemplaza los registros del período seleccionado para evitar duplicados.
"""
import os
import sys
import json
import requests
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

# Cargar .env desde la raíz del proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

# ── Configuración ────────────────────────────────────────────────────────────
USERNAME = os.environ.get('AUNESA_USERNAME', '')
PASSWORD = os.environ.get('AUNESA_PASSWORD', '')
HOST = os.environ.get('AUNESA_HOST', 'https://becerra.aunesa.com/Irmo')
CLIENT_ID = os.environ.get('AUNESA_CLIENT_ID', '')
DATABASE_URL = os.environ.get('DATABASE_URL', '')
USD_MEP = float(os.environ.get('USD_MEP', 1168))

# ── Fechas ───────────────────────────────────────────────────────────────────
config_path = os.path.join(BASE_DIR, 'fechas_config.json')
try:
    with open(config_path, encoding='utf-8') as f:
        fechas = json.load(f)
    fecha_desde = fechas.get('fecha_desde', '')
    fecha_hasta = fechas.get('fecha_hasta', '')
except FileNotFoundError:
    print('❌ fechas_config.json no encontrado.')
    sys.exit(1)

try:
    fecha_desde_api = datetime.strptime(fecha_desde, '%Y-%m-%d').strftime('%d/%m/%Y')
    fecha_hasta_api = datetime.strptime(fecha_hasta, '%Y-%m-%d').strftime('%d/%m/%Y')
except ValueError as e:
    print(f'❌ Error en formato de fechas: {e}')
    sys.exit(1)

# ── Cuentas ──────────────────────────────────────────────────────────────────
cuentas_path = os.path.join(BASE_DIR, 'cuentas.txt')
try:
    with open(cuentas_path) as f:
        cuentas = [l.strip() for l in f if l.strip() and not l.startswith('#')]
except FileNotFoundError:
    print('❌ cuentas.txt no encontrado.')
    sys.exit(1)

print(f'🗓️  Procesando {len(cuentas)} cuenta(s): {fecha_desde_api} → {fecha_hasta_api}')

# ── Login API ─────────────────────────────────────────────────────────────────
resp = requests.post(
    f'{HOST}/api/login',
    json={'clientId': CLIENT_ID, 'username': USERNAME, 'password': PASSWORD},
    timeout=30,
)
resp.raise_for_status()
token = resp.json()['token']
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}


# ── Procesar cuenta ───────────────────────────────────────────────────────────
def procesar_cuenta(id_cuenta):
    url = f'{HOST}/api/cuentas/{id_cuenta}/movimientos'
    params = {'fechaDesde': fecha_desde_api, 'fechaHasta': fecha_hasta_api}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        filtrados = []
        for m in r.json():
            tipo = (m.get('tipoOperacion') or '').strip()
            concepto = m.get('concepto', '')
            especie = m.get('especie', '')
            if concepto == 'F' and tipo in ('Depósito', 'Extracción') and especie in ('ARS', 'USD'):
                cantidad = m.get('cantidad', 0) or 0
                monto_ars = cantidad * USD_MEP if especie == 'USD' else cantidad
                filtrados.append((
                    m.get('cuenta', id_cuenta),
                    m.get('fecha', '')[:10],   # YYYY-MM-DD
                    tipo,
                    especie,
                    cantidad,
                    monto_ars,
                    concepto,
                ))
        return filtrados
    except Exception as e:
        print(f'⚠️  Error en cuenta {id_cuenta}: {e}')
        return []


# ── Fetch en paralelo ─────────────────────────────────────────────────────────
with ThreadPoolExecutor(max_workers=5) as pool:
    resultados = list(pool.map(procesar_cuenta, cuentas))

movimientos = [item for sublist in resultados for item in sublist]
print(f'✅ {len(movimientos)} movimiento(s) encontrado(s).')

if not movimientos:
    sys.exit(0)

# ── Guardar en PostgreSQL ─────────────────────────────────────────────────────
conn = psycopg2.connect(DATABASE_URL)
try:
    with conn:
        with conn.cursor() as cur:
            # Eliminar registros del período para evitar duplicados
            cur.execute(
                'DELETE FROM movimientos WHERE fecha >= %s AND fecha <= %s',
                (fecha_desde, fecha_hasta),
            )
            execute_values(
                cur,
                '''INSERT INTO movimientos
                   (cuenta, fecha, tipo_operacion, especie, cantidad, monto_ars, concepto)
                   VALUES %s''',
                movimientos,
            )
    print(f'✅ Base de datos actualizada con {len(movimientos)} registro(s).')
finally:
    conn.close()
