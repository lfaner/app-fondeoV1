import os
import io
import csv
from datetime import date
from flask import (render_template, redirect, url_for, flash, request,
                   current_app, send_from_directory, send_file)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.fondeos import fondeos
from app.models import Comprobante, Multiplicador
from app.extensions import db

ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _multiplicadores_dict():
    return {m.tipo.lower(): float(m.valor) for m in Multiplicador.query.all()}


@fondeos.route('/')
@login_required
def dashboard():
    comprobantes = Comprobante.query.order_by(Comprobante.fecha_subida.desc()).all()
    mults = _multiplicadores_dict()
    hoy = date.today()

    datos = []
    for c in comprobantes:
        mult = mults.get(c.tipo_origen.lower(), 1.0)
        monto = float(c.monto)
        datos.append({
            'id': c.id,
            'usuario': c.usuario,
            'cuenta': c.cuenta,
            'tipo_origen': c.tipo_origen,
            'monto': monto,
            'monto_anual': monto * mult,
            'fecha_comprobante': c.fecha_comprobante,
            'fecha_expiracion': c.fecha_expiracion,
            'fecha_subida': c.fecha_subida,
            'estado': 'Activo' if c.fecha_expiracion >= hoy else 'Expirado',
            'archivo': c.nombre_archivo,
            'observaciones': c.observaciones or '',
        })

    total = len(datos)
    activos = sum(1 for d in datos if d['estado'] == 'Activo')
    cuentas_unicas = len(set(d['cuenta'] for d in datos))

    return render_template(
        'fondeos/dashboard.html',
        datos=datos,
        total=total,
        activos=activos,
        expirados=total - activos,
        cuentas=cuentas_unicas,
    )


@fondeos.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    multiplicadores = sorted(Multiplicador.query.all(), key=lambda m: m.tipo)

    if request.method == 'POST':
        cuenta = request.form.get('cuenta', '').strip()
        tipo_origen = request.form.get('tipo_origen', '').strip()
        monto_str = request.form.get('monto', '').strip()
        fecha_comprobante_str = request.form.get('fecha_comprobante', '').strip()
        fecha_expiracion_str = request.form.get('fecha_expiracion', '').strip()
        observaciones = request.form.get('observaciones', '').strip()
        file = request.files.get('file')

        if not all([cuenta, tipo_origen, monto_str, fecha_comprobante_str, fecha_expiracion_str]):
            flash('Completá todos los campos obligatorios.', 'error')
            return render_template('fondeos/upload.html', multiplicadores=multiplicadores)

        try:
            monto = float(monto_str.replace(',', '.'))
        except ValueError:
            flash('El monto debe ser un número válido.', 'error')
            return render_template('fondeos/upload.html', multiplicadores=multiplicadores)

        nombre_archivo = None
        if file and file.filename:
            if not allowed_file(file.filename):
                flash('Tipo de archivo no permitido. Solo PDF, PNG, JPG.', 'error')
                return render_template('fondeos/upload.html', multiplicadores=multiplicadores)

            filename = secure_filename(file.filename)
            folder = os.path.join(current_app.config['UPLOAD_FOLDER'], secure_filename(cuenta))
            os.makedirs(folder, exist_ok=True)
            file.save(os.path.join(folder, filename))
            nombre_archivo = filename

        comprobante = Comprobante(
            usuario=current_user.username,
            cuenta=cuenta,
            tipo_origen=tipo_origen.lower(),
            monto=monto,
            fecha_comprobante=date.fromisoformat(fecha_comprobante_str),
            fecha_expiracion=date.fromisoformat(fecha_expiracion_str),
            nombre_archivo=nombre_archivo,
            observaciones=observaciones,
        )
        db.session.add(comprobante)
        db.session.commit()

        flash('Comprobante cargado correctamente.', 'success')
        return redirect(url_for('fondeos.dashboard'))

    return render_template('fondeos/upload.html', multiplicadores=multiplicadores)


@fondeos.route('/download/<int:comprobante_id>')
@login_required
def download(comprobante_id):
    c = Comprobante.query.get_or_404(comprobante_id)
    if not c.nombre_archivo:
        flash('Este registro no tiene archivo adjunto.', 'error')
        return redirect(url_for('fondeos.dashboard'))
    folder = os.path.join(current_app.config['UPLOAD_FOLDER'], secure_filename(c.cuenta))
    return send_from_directory(folder, c.nombre_archivo, as_attachment=True)


@fondeos.route('/eliminar/<int:comprobante_id>', methods=['POST'])
@login_required
def eliminar(comprobante_id):
    c = Comprobante.query.get_or_404(comprobante_id)
    db.session.delete(c)
    db.session.commit()
    flash('Comprobante eliminado.', 'success')
    return redirect(url_for('fondeos.dashboard'))


@fondeos.route('/exportar')
@login_required
def exportar():
    comprobantes = Comprobante.query.order_by(Comprobante.cuenta).all()
    mults = _multiplicadores_dict()
    hoy = date.today()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Cuenta', 'Tipo Origen', 'Monto', 'Monto Anual',
        'Fecha Comprobante', 'Fecha Expiración', 'Estado',
        'Fecha Subida', 'Usuario', 'Observaciones',
    ])
    for c in comprobantes:
        mult = mults.get(c.tipo_origen.lower(), 1.0)
        monto = float(c.monto)
        writer.writerow([
            c.cuenta, c.tipo_origen, monto, round(monto * mult, 2),
            c.fecha_comprobante, c.fecha_expiracion,
            'Activo' if c.fecha_expiracion >= hoy else 'Expirado',
            c.fecha_subida, c.usuario, c.observaciones or '',
        ])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'comprobantes_{date.today()}.csv',
    )
