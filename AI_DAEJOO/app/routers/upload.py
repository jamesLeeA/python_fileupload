"""파일 업로드 데모 라우트. 다른 페이지에 붙일 때 참고용."""
from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from app.routers.fileupload import MB, UploadError, UploadRules, save_files

bp = Blueprint("upload", __name__)

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


def _render(saved=None):
    return render_template("common/index.html", rules_multi=RULES_MULTI,
                           rules_single=RULES_SINGLE, saved=saved)


@bp.get("/")
def index():
    return _render()


@bp.post("/upload")
def upload():
    upload_dir = current_app.config["UPLOAD_DIR"]
    try:
        saved = save_files(request.files.getlist("docs"), RULES_MULTI, upload_dir)
        saved += save_files(request.files.getlist("single"), RULES_SINGLE, upload_dir)
    except UploadError as e:
        for msg in e.errors:
            flash(msg, "danger")
        return redirect(url_for("upload.index"))
    return _render(saved)
