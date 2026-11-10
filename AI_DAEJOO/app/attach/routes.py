"""첨부 다운로드 Blueprint (선택 사용). app.register_blueprint(bp) 한 줄로 등록."""
from flask import Blueprint, abort, current_app, send_from_directory

from .core import _dir, get_file

bp = Blueprint("attach", __name__)


@bp.get("/attach/<int:file_id>")
def download(file_id):
    row = get_file(file_id)
    if row is None:
        abort(404)
    can = current_app.config.get("ATTACH_CAN_DOWNLOAD")  # (row) -> bool, 선택 사항
    if can and not can(row):
        abort(403)
    return send_from_directory(_dir(), row["stored_name"], as_attachment=True,
                               download_name=row["original_name"])
