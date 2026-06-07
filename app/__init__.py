import eventlet

eventlet.monkey_patch()

from dotenv import load_dotenv

load_dotenv()

from flask import Flask
from flask_cors import CORS

from celery_app import create_celery_app
from config import DevelopmentConfig


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates", static_url_path="/demo")
    app.config.from_object(DevelopmentConfig)

    # SECRET_KEY 미주입 시 임시 키를 생성한다(개발 편의). 운영에서는 환경 변수로 고정해야 한다.
    if not app.config.get("SECRET_KEY"):
        import secrets

        app.logger.warning("SECRET_KEY가 설정되지 않아 임시 키를 생성합니다. 운영에서는 반드시 고정 키를 주입하세요.")
        app.config["SECRET_KEY"] = secrets.token_hex(32)

    # CORS는 명시된 origin에만 허용한다(미설정 시 동일 출처).
    cors_origins = app.config.get("CORS_ORIGINS") or []
    if cors_origins:
        CORS(app, origins=cors_origins, supports_credentials=True)

    from app.apis.auth import bp_auth
    from app.apis.common import bp_common
    from app.apis.external import bp_external
    from app.apis.files import bp_file
    from app.apis.page import bp_page

    app.register_blueprint(bp_common)
    app.register_blueprint(bp_auth)
    app.register_blueprint(bp_external)
    app.register_blueprint(bp_page)
    app.register_blueprint(bp_file)

    create_celery_app(app)
    return app


app = create_app()
