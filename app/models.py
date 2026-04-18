from datetime import datetime, date
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db, login_manager


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    email_verificado = db.Column(db.Boolean, default=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='user')   # 'admin' | 'user'
    aprobado = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == 'admin'


class Comprobante(db.Model):
    __tablename__ = 'comprobantes'

    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(80), nullable=False)
    cuenta = db.Column(db.String(50), nullable=False, index=True)
    tipo_origen = db.Column(db.String(100), nullable=False)
    monto = db.Column(db.Numeric(15, 2), nullable=False)
    fecha_comprobante = db.Column(db.Date, nullable=False)
    fecha_expiracion = db.Column(db.Date, nullable=False, index=True)
    nombre_archivo = db.Column(db.String(255))
    fecha_subida = db.Column(db.Date, default=date.today)
    observaciones = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def activo(self):
        return self.fecha_expiracion >= date.today()


class Multiplicador(db.Model):
    __tablename__ = 'multiplicadores'

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(100), unique=True, nullable=False)
    valor = db.Column(db.Numeric(10, 2), nullable=False)


class Movimiento(db.Model):
    __tablename__ = 'movimientos'

    id = db.Column(db.Integer, primary_key=True)
    cuenta = db.Column(db.String(50), nullable=False, index=True)
    fecha = db.Column(db.Date, nullable=False, index=True)
    tipo_operacion = db.Column(db.String(50))
    especie = db.Column(db.String(10))
    cantidad = db.Column(db.Numeric(15, 2))
    monto_ars = db.Column(db.Numeric(15, 2))
    concepto = db.Column(db.String(10))


class Caso(db.Model):
    __tablename__ = 'casos'

    id = db.Column(db.Integer, primary_key=True)
    cuenta = db.Column(db.String(50), nullable=False, index=True)
    monto_excedido = db.Column(db.Numeric(15, 2))
    estado = db.Column(db.String(20), default='Abierto', index=True)
    observaciones = db.Column(db.Text)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_cierre = db.Column(db.DateTime)


class ConfigSistema(db.Model):
    __tablename__ = 'config_sistema'

    clave = db.Column(db.String(50), primary_key=True)
    valor = db.Column(db.Text)
