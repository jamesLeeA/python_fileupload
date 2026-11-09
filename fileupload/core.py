"""재사용 가능한 파일 업로드 규칙/검증/저장 모듈.

규칙(UploadRules) 하나로 화면(data-* 속성)과 서버 검증을 동시에 구성하므로
클라이언트 검증은 편의용이고, 최종 검증은 항상 서버에서 수행됩니다.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from typing import Iterable, Optional

from markupsafe import Markup
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

MB = 1024 * 1024


class UploadError(Exception):
    """검증 실패. errors 에 사용자에게 보여줄 메시지 목록이 담긴다."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def _norm_exts(exts: Optional[Iterable[str]]) -> tuple[str, ...]:
    return tuple(sorted({e.strip().lower().lstrip(".") for e in (exts or []) if e and e.strip()}))


@dataclass(frozen=True)
class UploadRules:
    max_files: Optional[int] = None          # 최대 파일 수 (None=무제한)
    max_file_size: Optional[int] = 10 * MB   # 파일당 최대 바이트
    max_total_size: Optional[int] = None     # 전체 최대 바이트
    allow: tuple[str, ...] = field(default_factory=tuple)  # 허용 확장자(비어있으면 전체 허용)
    deny: tuple[str, ...] = field(default_factory=tuple)   # 금지 확장자(allow 보다 우선)
    multiple: bool = True
    required: bool = False

    def __post_init__(self):
        object.__setattr__(self, "allow", _norm_exts(self.allow))
        object.__setattr__(self, "deny", _norm_exts(self.deny))
        if not self.multiple:
            object.__setattr__(self, "max_files", 1)

    def to_data_attrs(self) -> dict[str, str]:
        d = {
            "data-multiple": "true" if self.multiple else "false",
            "data-allow": ",".join(self.allow),
            "data-deny": ",".join(self.deny),
            "data-required": "true" if self.required else "false",
        }
        if self.max_files is not None:
            d["data-max-files"] = str(self.max_files)
        if self.max_file_size is not None:
            d["data-max-file-size"] = str(self.max_file_size)
        if self.max_total_size is not None:
            d["data-max-total-size"] = str(self.max_total_size)
        return d


def human_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{int(size)}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024


def _extensions(filename: str) -> list[str]:
    parts = filename.lower().split(".")[1:]
    return [p for p in parts if p]


def _size(f: FileStorage) -> int:
    pos = f.stream.tell()
    f.stream.seek(0, os.SEEK_END)
    size = f.stream.tell()
    f.stream.seek(pos)
    return size


def validate_files(files: Iterable[FileStorage], rules: UploadRules) -> list[FileStorage]:
    """빈 항목을 제거하고 규칙을 검증한다. 실패 시 UploadError."""
    files = [f for f in files if f and f.filename]
    errors: list[str] = []

    if rules.required and not files:
        raise UploadError(["파일을 선택해 주세요."])
    if rules.max_files is not None and len(files) > rules.max_files:
        errors.append(f"파일은 최대 {rules.max_files}개까지 업로드할 수 있습니다.")

    total = 0
    for f in files:
        exts = _extensions(f.filename)
        last = exts[-1] if exts else ""
        # 금지 확장자는 이중 확장자(shell.php.jpg)까지 검사
        bad = [e for e in exts if e in rules.deny]
        if bad:
            errors.append(f"'{f.filename}': 업로드가 금지된 형식(.{bad[0]})입니다.")
            continue
        if rules.allow and last not in rules.allow:
            errors.append(
                f"'{f.filename}': 허용되지 않는 형식입니다. (허용: {', '.join('.' + e for e in rules.allow)})"
            )
            continue
        size = _size(f)
        total += size
        if rules.max_file_size is not None and size > rules.max_file_size:
            errors.append(f"'{f.filename}': 파일당 최대 {human_size(rules.max_file_size)}까지 가능합니다.")

    if rules.max_total_size is not None and total > rules.max_total_size:
        errors.append(f"전체 용량은 최대 {human_size(rules.max_total_size)}까지 가능합니다.")

    if errors:
        raise UploadError(errors)
    return files


def save_files(files: Iterable[FileStorage], rules: UploadRules, upload_dir: str) -> list[dict]:
    """검증 후 UUID 파일명으로 저장하고 메타데이터 목록을 반환한다."""
    files = validate_files(files, rules)
    os.makedirs(upload_dir, exist_ok=True)
    saved = []
    for f in files:
        ext = os.path.splitext(f.filename)[1].lower()
        stored = f"{uuid.uuid4().hex}{ext}"
        f.save(os.path.join(upload_dir, stored))
        saved.append(
            {
                "original_name": f.filename,
                "safe_name": secure_filename(f.filename) or stored,
                "stored_name": stored,
                "size": os.path.getsize(os.path.join(upload_dir, stored)),
                "content_type": f.mimetype,
            }
        )
    return saved


def init_app(app) -> None:
    """Flask 앱에 공통 컴포넌트를 등록한다 (정적 파일 + 템플릿 헬퍼)."""
    from flask import Blueprint, render_template

    bp = Blueprint(
        "fileupload",
        __name__,
        template_folder="templates",
        static_folder="static",
        static_url_path="/fileupload-static",
    )
    app.register_blueprint(bp)

    @app.template_global()
    def file_upload(name: str, rules: Optional[UploadRules] = None, **opts):
        """{{ file_upload('attachments', rules) }} 로 어디서나 삽입."""
        rules = rules or UploadRules()
        html = render_template(
            "fileupload/_component.html",
            name=name,
            rules=rules,
            attrs=rules.to_data_attrs(),
            label=opts.get("label", "파일을 여기로 드래그하거나 클릭하여 선택하세요"),
            input_id=opts.get("id", f"fu-{name}"),
            human=human_size,
        )
        return Markup(html)

    @app.template_global()
    def file_upload_assets():
        """<head>/<body> 끝에 한 번만: CSS+JS 포함."""
        return Markup(render_template("fileupload/_assets.html"))
