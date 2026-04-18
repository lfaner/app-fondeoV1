import os
from flask import Flask
from app.config import config
from app.extensions import db, migrate, login_manager, mail


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')

    app = Flask(__name__, template_folder='templates')
    app.config.from_object(config[config_name])

    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    mail.init_app(app)

    # Blueprints
    from app.auth import auth as auth_bp
    app.register_blueprint(auth_bp)

    from app.fondeos import fondeos as fondeos_bp
    app.register_blueprint(fondeos_bp)

    from app.perfil import perfil as perfil_bp
    app.register_blueprint(perfil_bp)

    from app.casos import casos as casos_bp
    app.register_blueprint(casos_bp)

    from app.admin import admin as admin_bp
    app.register_blueprint(admin_bp)

    return app
