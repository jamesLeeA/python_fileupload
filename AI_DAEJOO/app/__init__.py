import os

from flask import Flask, flash, redirect, url_for

from app.routers.fileupload import MB


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
    # 업로드 저장 폴더 (프로젝트 루트/uploads)
    app.config["UPLOAD_DIR"] = os.path.join(os.path.dirname(app.root_path), "uploads")
    # 요청 전체 상한 (각 업로드 규칙의 합계보다 넉넉하게)
    app.config["MAX_CONTENT_LENGTH"] = 100 * MB

    from app.routers.upload import bp as upload_bp
    app.register_blueprint(upload_bp)

    @app.errorhandler(413)
    def too_large(_):
        flash("요청 용량이 너무 큽니다.", "danger")
        return redirect(url_for("upload.index"))

    return app
