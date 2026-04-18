from datetime import date, datetime
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required
from sqlalchemy import func
from app.casos import casos
from app.models import Caso, Comprobante, Movimiento, Multiplicador
from app.extensions import db


@casos.route('/casos')
@login_required
def lista_casos():
    abiertos = Caso.query.filter_by(estado='Abierto').order_by(Caso.fecha_creacion.desc()).all()
    return render_template('casos/abiertos.html', casos=abiertos)


@casos.route('/casos/cerrados')
@login_required
def casos_cerrados():
    cerrados = Caso.query.filter_by(estado='Cerrado').order_by(Caso.fecha_cierre.desc()).all()
    return render_template('casos/cerrados.html', casos=cerrados)


@casos.route('/casos/crear', methods=['POST'])
@login_required
def crear_casos():
    mults = {m.tipo.lower(): float(m.valor) for m in Multiplicador.query.all()}

    rows = db.session.query(
        Comprobante.cuenta, Comprobante.tipo_origen, Comprobante.monto
    ).filter(Comprobante.fecha_expiracion >= date.today()).all()

    montos_anuales = {}
    for cuenta, tipo, monto in rows:
        mult = mults.get(tipo.lower(), 1.0)
        montos_anuales[cuenta] = montos_anuales.get(cuenta, 0.0) + float(monto) * mult

    dep_rows = db.session.query(
        Movimiento.cuenta,
        func.sum(Movimiento.monto_ars).label('total')
    ).filter(Movimiento.tipo_operacion == 'Depósito').group_by(Movimiento.cuenta).all()
    depositos = {r.cuenta: float(r.total or 0) for r in dep_rows}

    cuentas = set(montos_anuales.keys()) | set(depositos.keys())
    creados = 0
    for cuenta in cuentas:
        diff = montos_anuales.get(cuenta, 0.0) + depositos.get(cuenta, 0.0)
        if diff < 0:
            if not Caso.query.filter_by(cuenta=cuenta, estado='Abierto').first():
                db.session.add(Caso(cuenta=cuenta, monto_excedido=abs(diff)))
                creados += 1

    db.session.commit()
    categoria = 'success' if creados > 0 else 'info'
    flash(f'{creados} caso(s) creado(s).', categoria)
    return redirect(url_for('casos.lista_casos'))


@casos.route('/casos/cerrar/<int:caso_id>', methods=['POST'])
@login_required
def cerrar_caso(caso_id):
    caso = Caso.query.get_or_404(caso_id)
    caso.estado = 'Cerrado'
    caso.observaciones = request.form.get('observacion', '').strip()
    caso.fecha_cierre = datetime.utcnow()
    db.session.commit()
    flash('Caso cerrado correctamente.', 'success')
    return redirect(url_for('casos.lista_casos'))
