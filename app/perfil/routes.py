import io
import csv
from datetime import date
from flask import render_template, request, send_file
from flask_login import login_required
from sqlalchemy import func
from app.perfil import perfil
from app.models import Comprobante, Multiplicador, Movimiento, ConfigSistema
from app.extensions import db


def _calcular_perfiles(cuenta_filtro, fecha_inicio, fecha_fin):
    mults = {m.tipo.lower(): float(m.valor) for m in Multiplicador.query.all()}

    # Cupos anuales (comprobantes activos)
    q = db.session.query(
        Comprobante.cuenta, Comprobante.tipo_origen, Comprobante.monto
    ).filter(Comprobante.fecha_expiracion >= date.today())
    if cuenta_filtro:
        q = q.filter(Comprobante.cuenta == cuenta_filtro)

    montos_anuales = {}
    for cuenta, tipo, monto in q.all():
        mult = mults.get(tipo.lower(), 1.0)
        montos_anuales[cuenta] = montos_anuales.get(cuenta, 0.0) + float(monto) * mult

    # Depósitos
    q_mov = db.session.query(
        Movimiento.cuenta,
        func.sum(Movimiento.monto_ars).label('total')
    ).filter(Movimiento.tipo_operacion == 'Depósito')
    if fecha_inicio:
        q_mov = q_mov.filter(Movimiento.fecha >= fecha_inicio)
    if fecha_fin:
        q_mov = q_mov.filter(Movimiento.fecha <= fecha_fin)
    if cuenta_filtro:
        q_mov = q_mov.filter(Movimiento.cuenta == cuenta_filtro)

    depositos = {
        r.cuenta: float(r.total or 0)
        for r in q_mov.group_by(Movimiento.cuenta).all()
    }

    cuentas = sorted(set(montos_anuales.keys()) | set(depositos.keys()))
    data = []
    for cuenta in cuentas:
        cupo = montos_anuales.get(cuenta, 0.0)
        dep = depositos.get(cuenta, 0.0)
        diff = cupo + dep
        data.append({
            'cuenta': cuenta,
            'cupo_anual': cupo,
            'depositos': dep,
            'diferencia': diff,
            'estado': 'Excedido' if diff < 0 else 'Ok',
        })
    return data


@perfil.route('/perfil-transaccional')
@login_required
def perfil_transaccional():
    cuenta_filtro = request.args.get('cuenta', '').strip()
    fecha_inicio = request.args.get('fecha_inicio', '')
    fecha_fin = request.args.get('fecha_fin', '')

    data = _calcular_perfiles(cuenta_filtro, fecha_inicio, fecha_fin)

    # Fechas extremas de movimientos disponibles
    fechas = db.session.query(
        func.min(Movimiento.fecha),
        func.max(Movimiento.fecha)
    ).filter(Movimiento.tipo_operacion == 'Depósito').first()
    fecha_min = fechas[0].strftime('%Y-%m-%d') if fechas and fechas[0] else '—'
    fecha_max = fechas[1].strftime('%Y-%m-%d') if fechas and fechas[1] else '—'

    cfg = ConfigSistema.query.get('ultima_actualizacion')
    ultima_actualizacion = cfg.valor if cfg else '—'

    todas_cuentas = sorted({
        c.cuenta for c in
        db.session.query(Comprobante.cuenta).distinct().all()
    })

    excedidas = sum(1 for d in data if d['estado'] == 'Excedido')

    return render_template(
        'perfil/index.html',
        data=data,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        cuenta_filtro=cuenta_filtro,
        fecha_min=fecha_min,
        fecha_max=fecha_max,
        ultima_actualizacion=ultima_actualizacion,
        excedidas=excedidas,
        ok_count=len(data) - excedidas,
        todas_cuentas=todas_cuentas,
    )


@perfil.route('/perfil-transaccional/exportar')
@login_required
def exportar():
    cuenta_filtro = request.args.get('cuenta', '').strip()
    fecha_inicio = request.args.get('fecha_inicio', '')
    fecha_fin = request.args.get('fecha_fin', '')

    data = _calcular_perfiles(cuenta_filtro, fecha_inicio, fecha_fin)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Cuenta', 'Cupo Anual', 'Depósitos ARS', 'Diferencia', 'Estado'])
    for d in data:
        writer.writerow([
            d['cuenta'], round(d['cupo_anual'], 2),
            round(d['depositos'], 2), round(d['diferencia'], 2),
            d['estado'],
        ])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'perfil_transaccional_{date.today()}.csv',
    )
