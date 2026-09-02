from flask import Flask
from config import Config
from app.extensions import db, login_manager, csrf
from app.i18n import t, get_locale


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    @app.context_processor
    def inject_i18n():
        return dict(t=t, current_lang=get_locale())

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    login_manager.login_view = "auth.login"
    login_manager.session_protection = "strong"

    from app.main.routes import main_bp
    from app.auth.routes import auth_bp
    from app.campaigns.routes import campaigns_bp
    from app.payments.routes import payments_bp
    from app.exports.excel import exports_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(campaigns_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(exports_bp)

    return app