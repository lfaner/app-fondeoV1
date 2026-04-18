import os
import json
import subprocess
from datetime import datetime
from functools import wraps
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app.admin import admin
from app.models import User, Multiplicador, ConfigSistema
from app.extensions import db

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash('Acceso restringido a administradores.', 'error')
            return redirect(url_for('fondeos.dashboard'))
        return f(*args, **kwargs)
    return decorated


# ── Usuarios ────────────────────────────────────────────────────────────────

@admin.route('/usuarios')
@admin_required
def usuarios():
    pendientes = User.query.filter_by(aprobado=False).order_by(User.created_at.desc()).all()
    aprobados = User.query.filter_by(aprobado=True).order_by(User.username).all()
    return render_template('admin/usuarios.html', pendientes=pendientes, aprobados=aprobados)


@admin.route('/usuarios/aprobar/<int:user_id>', methods=['POST'])
@admin_required
def aprobar_usuario(user_id):
    user = User.query.get_or_404(user_id)
    user.aprobado = True
    db.session.commit()
    flash(f'Usuario "{user.username}" aprobado.', 'success')
    return redirect(url_for('admin.usuarios'))


@admin.route('/usuarios/rechazar/<int:user_id>', methods=['POST'])
@admin_required
def rechazar_usuario(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash('Usuario eliminado.', 'success')
    return redirect(url_for('admin.usuarios'))


# ── Multiplicadores ──────────────────────────────────────────────────────────

@admin.route('/multiplicadores', methods=['GET', 'POST'])
@admin_required
def multiplicadores():
    if request.method == 'POST':
        tipo = request.form.get('tipo', '').strip().lower()
        valor_str = request.form.get('valor', '').strip()

        if not tipo or not valor_str:
            flash('Todos los campos son obligatorios.', 'error')
        else:
            try:
                valor = float(valor_str.replace(',', '.'))
                existente = Multiplicador.query.filter_by(tipo=tipo).first()
                if existente:
                    existente.valor = valor
                    flash(f'Multiplicador "{tipo}" actualizado.', 'success')
                else:
                    db.session.add(Multiplicador(tipo=tipo, valor=valor))
                    flash(f'Multiplicador "{tipo}" agregado.', 'success')
                db.session.commit()
            except ValueError:
                flash('El valor debe ser un número válido.', 'error')

        return redirect(url_for('admin.multiplicadores'))

    mults = Multiplicador.query.order_by(Multiplicador.tipo).all()
    return render_template('admin/multiplicadores.html', multiplicadores=mults)


@admin.route('/multiplicadores/eliminar/<int:mult_id>', methods=['POST'])
@admin_required
def eliminar_multiplicador(mult_id):
    m = Multiplicador.query.get_or_404(mult_id)
    db.session.delete(m)
    db.session.commit()
    flash(f'Multiplicador "{m.tipo}" eliminado.', 'success')
    return redirect(url_for('admin.multiplicadores'))


# ── Actualizar depósitos ─────────────────────────────────────────────────────

@admin.route('/depositos', methods=['GET', 'POST'])
@admin_required
def actualizar_depositos():
    if request.method == 'POST':
        fecha_desde = request.form.get('fecha_desde', '')
        fecha_hasta = request.form.get('fecha_hasta', '')

        if not fecha_desde or not fecha_hasta:
            flash('Debés ingresar ambas fechas.', 'error')
            return redirect(url_for('admin.actualizar_depositos'))

        config_path = os.path.join(BASE_DIR, 'fechas_config.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump({'fecha_desde': fecha_desde, 'fecha_hasta': fecha_hasta}, f)

        script_path = os.path.join(BASE_DIR, 'scripts', 'actualizar_movimientos.py')
        try:
            subprocess.run(['python', script_path], check=True, timeout=300)

            cfg = ConfigSistema.query.get('ultima_actualizacion')
            ahora = datetime.now().strftime('%Y-%m-%d %H:%M')
            if cfg:
                cfg.valor = ahora
            else:
                db.session.add(ConfigSistema(clave='ultima_actualizacion', valor=ahora))
            db.session.commit()

            flash('Depósitos actualizados correctamente.', 'success')
        except subprocess.CalledProcessError as e:
            flash(f'Error al ejecutar el script: {e}', 'error')
        except subprocess.TimeoutExpired:
            flash('El proceso tardó demasiado y fue cancelado.', 'error')

        return redirect(url_for('admin.actualizar_depositos'))

    cfg = ConfigSistema.query.get('ultima_actualizacion')
    return render_template('admin/depositos.html', ultima_actualizacion=cfg.valor if cfg else '—')
