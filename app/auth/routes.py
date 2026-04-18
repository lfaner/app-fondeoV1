from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from app.auth import auth
from app.models import User
from app.extensions import db, mail

TOKEN_MAX_AGE = 3600  # 1 hora


def _serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


def _send_verification_email(user):
    token = _serializer().dumps(user.email, salt='verificar-email')
    link = url_for('auth.verificar_email', token=token, _external=True)
    msg = Message(
        subject='Verificá tu email — CGB Fondeos',
        recipients=[user.email],
        html=(
            f'<p>Hola <strong>{user.username}</strong>,</p>'
            f'<p>Hacé clic en el siguiente enlace para verificar tu email:</p>'
            f'<p><a href="{link}">{link}</a></p>'
            f'<p>El enlace expira en 1 hora.</p>'
        ),
    )
    mail.send(msg)


def _send_reset_email(user):
    token = _serializer().dumps(user.email, salt='reset-password')
    link = url_for('auth.reset_password', token=token, _external=True)
    msg = Message(
        subject='Restablecer contraseña — CGB Fondeos',
        recipients=[user.email],
        html=(
            f'<p>Hola <strong>{user.username}</strong>,</p>'
            f'<p>Hacé clic en el siguiente enlace para restablecer tu contraseña:</p>'
            f'<p><a href="{link}">{link}</a></p>'
            f'<p>El enlace expira en 1 hora. Si no solicitaste esto, ignorá este mensaje.</p>'
        ),
    )
    mail.send(msg)


# ── Login ────────────────────────────────────────────────────────────────────

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('fondeos.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()

        if not user or not user.check_password(password):
            flash('Usuario o contraseña incorrectos.', 'error')
            return render_template('auth/login.html')

        # Usuarios con email deben tenerlo verificado
        if user.email and not user.email_verificado:
            flash('Debés verificar tu email antes de ingresar. Revisá tu bandeja de entrada.', 'warning')
            return render_template('auth/login.html')

        if not user.aprobado:
            flash('Tu cuenta aún no fue aprobada. Contactá al administrador.', 'warning')
            return render_template('auth/login.html')

        login_user(user)
        next_page = request.args.get('next')
        return redirect(next_page or url_for('fondeos.dashboard'))

    return render_template('auth/login.html')


# ── Register ─────────────────────────────────────────────────────────────────

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('fondeos.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not username or not email or not password:
            flash('Todos los campos son obligatorios.', 'error')
            return render_template('auth/register.html')

        if password != confirm:
            flash('Las contraseñas no coinciden.', 'error')
            return render_template('auth/register.html')

        if len(password) < 6:
            flash('La contraseña debe tener al menos 6 caracteres.', 'error')
            return render_template('auth/register.html')

        if User.query.filter_by(username=username).first():
            flash('El nombre de usuario ya existe.', 'error')
            return render_template('auth/register.html')

        if User.query.filter_by(email=email).first():
            flash('Ya existe una cuenta con ese email.', 'error')
            return render_template('auth/register.html')

        user = User(username=username, email=email, email_verificado=False)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        try:
            _send_verification_email(user)
        except Exception:
            db.session.delete(user)
            db.session.commit()
            flash('No se pudo enviar el mail de verificación. Revisá la configuración SMTP.', 'error')
            return render_template('auth/register.html')

        return redirect(url_for('auth.verificar_email_enviado'))

    return render_template('auth/register.html')


# ── Verificación de email ─────────────────────────────────────────────────────

@auth.route('/verificar-email-enviado')
def verificar_email_enviado():
    return render_template('auth/verificar_email_enviado.html')


@auth.route('/verificar-email/<token>')
def verificar_email(token):
    try:
        email = _serializer().loads(token, salt='verificar-email', max_age=TOKEN_MAX_AGE)
    except SignatureExpired:
        flash('El enlace de verificación expiró. Registrate nuevamente.', 'error')
        return redirect(url_for('auth.register'))
    except BadSignature:
        flash('Enlace de verificación inválido.', 'error')
        return redirect(url_for('auth.register'))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash('Usuario no encontrado.', 'error')
        return redirect(url_for('auth.register'))

    if user.email_verificado:
        flash('Tu email ya estaba verificado. Podés ingresar cuando el administrador apruebe tu cuenta.', 'info')
        return redirect(url_for('auth.login'))

    user.email_verificado = True
    db.session.commit()

    return render_template('auth/email_verificado.html')


# ── Forgot / Reset password ───────────────────────────────────────────────────

@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('fondeos.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()
        # Siempre mostramos el mismo mensaje para no revelar si el email existe
        if user and user.email_verificado:
            try:
                _send_reset_email(user)
            except Exception:
                flash('No se pudo enviar el mail. Intentá de nuevo más tarde.', 'error')
                return render_template('auth/forgot_password.html')

        flash('Si existe una cuenta verificada con ese email, te enviamos un enlace para restablecer tu contraseña.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')


@auth.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('fondeos.dashboard'))

    try:
        email = _serializer().loads(token, salt='reset-password', max_age=TOKEN_MAX_AGE)
    except SignatureExpired:
        flash('El enlace para restablecer contraseña expiró. Solicitá uno nuevo.', 'error')
        return redirect(url_for('auth.forgot_password'))
    except BadSignature:
        flash('Enlace inválido.', 'error')
        return redirect(url_for('auth.forgot_password'))

    user = User.query.filter_by(email=email).first()
    if not user:
        flash('Usuario no encontrado.', 'error')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not password or len(password) < 6:
            flash('La contraseña debe tener al menos 6 caracteres.', 'error')
            return render_template('auth/reset_password.html', token=token)

        if password != confirm:
            flash('Las contraseñas no coinciden.', 'error')
            return render_template('auth/reset_password.html', token=token)

        user.set_password(password)
        db.session.commit()
        flash('Contraseña actualizada. Ya podés ingresar.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)


# ── Logout ────────────────────────────────────────────────────────────────────

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
