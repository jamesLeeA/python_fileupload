"""첨부파일 공통 모듈: 설정 / 검증 / 저장 / 조회 / 삭제 (SQLite + 로컬 폴더).

첨부는 항상 (ref_type, ref_id) 로 게시글에 묶인다. 예: ("notice", 12)
검증이 실패하면 파일과 DB 어느 쪽도 바뀌지 않는다. 서버 검증이 최종 판단이다.
"""
from __future__ import annotations

import os
import re
import sqlite3
import uuid
from dataclasses import dataclass

from flask import current_app, url_for

MB = 1024 * 1024
DEFAULT_DENY = ("exe", "bat", "cmd", "sh", "php", "jsp", "asp", "aspx", "js", "msi", "dll", "com", "scr")

SCHEMA = """
CREATE TABLE IF NOT EXISTS attach_file (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  ref_type      TEXT    NOT NULL,
  ref_id        TEXT    NOT NULL,
  field         TEXT    NOT NULL,
  original_name TEXT    NOT NULL,
  stored_name   TEXT    NOT NULL UNIQUE,
  size          INTEGER NOT NULL,
  content_type  TEXT,
  created_at    TEXT    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_attach_ref ON attach_file(ref_type, ref_id);
"""


class AttachError(Exception):
    """검증 실패. errors 에 사용자에게 보여줄 한국어 메시지 목록이 있다."""

    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = list(errors)


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n}B" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024


def _norm(values):
    out = []
    for v in values:
        v = (v or "").strip().lower().lstrip(".")
        if v and v not in out:
            out.append(v)
    return tuple(out)


@dataclass(frozen=True)
class AttachConfig:
    """첨부 필드 하나의 설정. 화면 렌더링과 서버 검증에 같은 객체를 넘긴다."""
    enabled: bool = True               # False 면 화면도 서버 처리도 건너뜀
    field: str = "attach"              # <input name> 및 폼 필드 이름
    ui: str = "drop"                   # "button" | "drop"
    max_files: int | None = 5          # 최대 개수 (기존 + 신규)
    max_file_size: int | None = 10 * MB    # 파일 1개 최대 바이트
    max_total_size: int | None = 30 * MB   # 전체 최대 바이트 (기존 + 신규)
    allow: tuple = ()                  # 허용 확장자 (비면 전체 허용)
    deny: tuple = DEFAULT_DENY         # 금지 확장자 (allow 보다 우선)

    def __post_init__(self):
        if self.ui not in ("button", "drop"):
            raise ValueError(f'ui 는 "button" 또는 "drop" 이어야 합니다: {self.ui!r}')
        object.__setattr__(self, "allow", _norm(self.allow))
        object.__setattr__(self, "deny", _norm(self.deny))

    # --- 화면용 (templates/attach/_attach.html) ---
    def attrs(self):
        a = {"allow": ",".join(self.allow), "deny": ",".join(self.deny)}
        for key, val in (("max-files", self.max_files), ("max-file-size", self.max_file_size),
                         ("max-total-size", self.max_total_size)):
            if val is not None:
                a[key] = val
        return a

    def accept(self):
        return ",".join("." + e for e in self.allow)

    def hint(self):
        parts = []
        if self.max_files is not None:
            parts.append(f"최대 {self.max_files}개")
        if self.max_file_size is not None:
            parts.append(f"파일당 {human_size(self.max_file_size)}")
        if self.max_total_size is not None:
            parts.append(f"전체 {human_size(self.max_total_size)}")
        if self.allow:
            parts.append("허용 " + ", ".join(self.allow))
        return " · ".join(parts)


# ---------------------------------------------------------------- 저장소 (DB 를 바꾸면 이 함수들만 고친다)
def _dir():
    d = current_app.config.get("ATTACH_DIR") or os.path.join(os.path.dirname(current_app.root_path), "uploads")
    os.makedirs(d, exist_ok=True)
    return d


def _db():
    path = current_app.config.get("ATTACH_DB") or os.path.join(_dir(), "attach.db")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)  # 테이블 자동 생성
    return con


def _rows(sql, args=()):
    con = _db()
    try:
        return [dict(r) for r in con.execute(sql, args)]
    finally:
        con.close()


def _write(metas=(), delete_ids=()):
    """새 행 추가 + 행 삭제를 한 트랜잭션으로 처리."""
    con = _db()
    try:
        with con:
            for m in metas:
                con.execute(
                    "INSERT INTO attach_file (ref_type, ref_id, field, original_name, stored_name, size, content_type)"
                    " VALUES (:ref_type, :ref_id, :field, :original_name, :stored_name, :size, :content_type)", m)
            for i in delete_ids:
                con.execute("DELETE FROM attach_file WHERE id = ?", (i,))
    finally:
        con.close()


# ---------------------------------------------------------------- 디스크
def _path(name):
    """저장 폴더 밖으로 나가지 않는 경로만 허용 (path traversal 방지)."""
    base = os.path.normcase(os.path.realpath(_dir()))
    p = os.path.normcase(os.path.realpath(os.path.join(base, name)))
    if os.path.commonpath([base, p]) != base:
        raise ValueError("잘못된 저장 경로")
    return os.path.join(_dir(), name)


def _unlink(names):
    for n in names:
        try:
            os.remove(_path(n))
        except FileNotFoundError:
            pass


def _size(f):
    pos = f.stream.tell()
    f.stream.seek(0, os.SEEK_END)
    n = f.stream.tell()
    f.stream.seek(pos)
    return n


# ---------------------------------------------------------------- 검증
def _check(cfg, files, keep_count=0, keep_size=0):
    errors, total = [], keep_size
    if cfg.max_files is not None and keep_count + len(files) > cfg.max_files:
        errors.append(f"파일은 최대 {cfg.max_files}개까지 첨부할 수 있습니다.")
    for f in files:
        exts = [p for p in f.filename.lower().split(".")[1:] if p]
        denied = [e for e in exts if e in cfg.deny]  # a.php.jpg 도 차단
        if denied:
            errors.append(f"'{f.filename}': 첨부할 수 없는 형식(.{denied[0]})입니다.")
            continue
        if cfg.allow and not exts:
            errors.append(f"'{f.filename}': 확장자가 없는 파일은 첨부할 수 없습니다.")
            continue
        if cfg.allow and exts[-1] not in cfg.allow:
            errors.append(f"'{f.filename}': 허용되지 않는 형식입니다. (허용: {', '.join('.' + e for e in cfg.allow)})")
            continue
        n = _size(f)
        total += n
        if cfg.max_file_size is not None and n > cfg.max_file_size:
            errors.append(f"'{f.filename}': 파일당 최대 {human_size(cfg.max_file_size)}까지 가능합니다.")
    if cfg.max_total_size is not None and total > cfg.max_total_size:
        errors.append(f"전체 용량은 최대 {human_size(cfg.max_total_size)}까지 가능합니다.")
    if errors:
        raise AttachError(errors)


def _ref(ref):
    return ref[0], str(ref[1])


def _plan(cfg, request, ref):
    """검증만 수행하고 (저장할 파일, 삭제할 기존 행) 을 돌려준다. 아무것도 바꾸지 않는다."""
    files = [f for f in request.files.getlist(cfg.field) if f and f.filename]
    keep, drop = [], []
    if ref:
        rows = _rows("SELECT * FROM attach_file WHERE ref_type=? AND ref_id=? AND field=?", (*_ref(ref), cfg.field))
        ids = {int(i) for i in request.form.getlist(cfg.field + "_delete") if i.isdigit()}
        drop = [r for r in rows if r["id"] in ids]  # 이 ref 소속만 삭제 대상
        keep = [r for r in rows if r["id"] not in ids]
    _check(cfg, files, len(keep), sum(r["size"] for r in keep))
    return files, drop


def _save(cfg, ref, files, drop=()):
    metas, written = [], []
    try:
        for f in files:
            ext = re.sub(r"[^a-z0-9]", "", os.path.splitext(f.filename)[1].lower())
            name = uuid.uuid4().hex + ("." + ext if ext else "")
            f.save(_path(name))
            written.append(name)
            metas.append({"ref_type": ref[0], "ref_id": str(ref[1]), "field": cfg.field,
                          "original_name": f.filename, "stored_name": name,
                          "size": os.path.getsize(_path(name)), "content_type": f.mimetype})
        _write(metas, [r["id"] for r in drop])
    except Exception:
        _unlink(written)  # 이번 호출에서 쓴 파일만 정리
        raise
    _unlink([r["stored_name"] for r in drop])
    return metas


# ---------------------------------------------------------------- 공개 API
def attach_list(ref, field=None):
    sql, args = "SELECT * FROM attach_file WHERE ref_type=? AND ref_id=?", list(_ref(ref))
    if field:
        sql, args = sql + " AND field=?", args + [field]
    has_url = "attach.download" in current_app.view_functions
    return [{"id": r["id"], "original_name": r["original_name"], "size": r["size"],
             "content_type": r["content_type"],
             "url": url_for("attach.download", file_id=r["id"]) if has_url else None,
             "ext": os.path.splitext(r["original_name"])[1].lstrip(".").lower(),
             "size_text": human_size(r["size"])}
            for r in _rows(sql + " ORDER BY id", args)]


def attach_view(cfg, ref=None):
    """템플릿에 넘길 {cfg, files}. 사용 안 함(enabled=False)이면 None."""
    if not cfg.enabled:
        return None
    return {"cfg": cfg, "files": attach_list(ref, cfg.field) if ref else []}


def attach_validate(cfg, request, ref=None):
    """저장 없이 검증만. 실패하면 AttachError."""
    if cfg.enabled:
        _plan(cfg, request, ref)


def attach_create(cfg, ref, request):
    """신규 등록: 검증 후 저장하고 메타 목록을 돌려준다."""
    if not cfg.enabled:
        return []
    files, _ = _plan(cfg, request, None)
    return _save(cfg, ref, files)


def attach_update(cfg, ref, request):
    """수정: (남는 기존 + 신규) 합계로 검증 -> 신규 저장 -> 삭제 대상 제거."""
    if not cfg.enabled:
        return []
    files, drop = _plan(cfg, request, ref)
    return _save(cfg, ref, files, drop)


def attach_delete_all(ref):
    """글 삭제: 해당 ref 의 모든 첨부를 DB 와 디스크에서 지우고 개수를 돌려준다."""
    rows = _rows("SELECT * FROM attach_file WHERE ref_type=? AND ref_id=?", _ref(ref))
    _write(delete_ids=[r["id"] for r in rows])
    _unlink([r["stored_name"] for r in rows])
    return len(rows)


def get_file(file_id):
    """다운로드 라우트용 단건 조회 (공개 API 아님)."""
    rows = _rows("SELECT * FROM attach_file WHERE id=?", (file_id,))
    return rows[0] if rows else None
