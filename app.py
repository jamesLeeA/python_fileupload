import os

from flask import Flask, flash, redirect, render_template, request, url_for

from fileupload import MB, UploadError, UploadRules, save_files

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

# 규칙은 서버에서 정의 -> 화면 렌더링과 서버 검증에 동일하게 사용
RULES_MULTI = UploadRules(
    max_files=5,
    max_file_size=5 * MB,
    max_total_size=15 * MB,
    allow=["jpg", "jpeg", "png", "gif", "pdf"],
)
RULES_SINGLE = UploadRules(
    multiple=False,
    required=True,
    max_file_size=20 * MB,
    deny=["exe", "bat", "cmd", "sh", "php", "js", "msi", "dll"],
)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
    # 요청 전체 상한 (규칙 합계보다 넉넉하게)
    app.config["MAX_CONTENT_LENGTH"] = 100 * MB

    @app.get("/")
    def index():
        return render_template("index.html", rules_multi=RULES_MULTI, rules_single=RULES_SINGLE, saved=None)

    @app.post("/upload")
    def upload():
        try:
            saved = save_files(request.files.getlist("docs"), RULES_MULTI, UPLOAD_DIR)
            saved += save_files(request.files.getlist("single"), RULES_SINGLE, UPLOAD_DIR)
        except UploadError as e:
            for msg in e.errors:
                flash(msg, "danger")
            return redirect(url_for("index"))
        return render_template(
            "index.html", rules_multi=RULES_MULTI, rules_single=RULES_SINGLE, saved=saved
        )

    @app.errorhandler(413)
    def too_large(_):
        flash("요청 용량이 너무 큽니다.", "danger")
        return redirect(url_for("index"))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
