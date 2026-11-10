import os

from flask import Flask


def create_app(config=None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
    app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 요청 전체 상한
    app.config.update(config or {})

    from app.attach.routes import bp as attach_bp  # 첨부 다운로드 (선택)
    app.register_blueprint(attach_bp)

    from app.routers.attach_demo import bp as demo_bp  # 데모 (복사 대상 아님)
    app.register_blueprint(demo_bp)
    return app
