"""첨부 모듈 데모 (/attach-demo). 복사 대상이 아니다. 글은 메모리 dict 로 대체한다."""
from itertools import count

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.attach import (MB, AttachConfig, AttachError, attach_create, attach_delete_all, attach_list,
                        attach_update, attach_validate, attach_view)

bp = Blueprint("attach_demo", __name__)

DROP = AttachConfig(field="files", ui="drop", max_files=5, max_file_size=5 * MB, max_total_size=15 * MB)
BTN = AttachConfig(field="extra", ui="button", max_files=1, max_file_size=2 * MB, allow=("pdf", "txt"))
CONFIGS = (DROP, BTN)

POSTS = {}
_ids = count(1)


def _form(post, post_id=None):
    ref = ("demo", post_id) if post_id else None
    return render_template("demo/form.html", post=post, post_id=post_id,
                           attach_drop=attach_view(DROP, ref), attach_btn=attach_view(BTN, ref))


def _validate_all(ref=None):
    """모든 첨부 설정을 검증하고 오류를 모아서 flash. 통과하면 True."""
    errors = []
    for cfg in CONFIGS:
        try:
            attach_validate(cfg, request, ref)
        except AttachError as e:
            errors += e.errors
    for m in errors:
        flash(m, "danger")
    return not errors


@bp.get("/")
def home():
    return redirect(url_for("attach_demo.index"))


@bp.get("/attach-demo")
def index():
    posts = [dict(p, id=i, files=attach_list(("demo", i))) for i, p in POSTS.items()]
    return render_template("demo/list.html", posts=posts)


@bp.route("/attach-demo/new", methods=["GET", "POST"])
def new():
    if request.method == "GET":
        return _form({"title": "", "content": ""})
    post = {"title": request.form["title"], "content": request.form["content"]}
    if not _validate_all():                       # 1) 첨부 먼저 검증
        return _form(post)
    pid = next(_ids)
    POSTS[pid] = post                             # 2) 글 저장
    for cfg in CONFIGS:                           # 3) 첨부 저장
        attach_create(cfg, ("demo", pid), request)
    flash("등록했습니다.", "success")
    return redirect(url_for("attach_demo.index"))


@bp.route("/attach-demo/<int:pid>/edit", methods=["GET", "POST"])
def edit(pid):
    if pid not in POSTS:
        return redirect(url_for("attach_demo.index"))
    if request.method == "GET":
        return _form(POSTS[pid], pid)
    post = {"title": request.form["title"], "content": request.form["content"]}
    if not _validate_all(("demo", pid)):          # 검증 실패 시 아무것도 바뀌지 않음
        return _form(post, pid)
    POSTS[pid] = post
    for cfg in CONFIGS:
        attach_update(cfg, ("demo", pid), request)
    flash("수정했습니다.", "success")
    return redirect(url_for("attach_demo.index"))


@bp.post("/attach-demo/<int:pid>/delete")
def delete(pid):
    POSTS.pop(pid, None)
    attach_delete_all(("demo", pid))
    flash("삭제했습니다.", "success")
    return redirect(url_for("attach_demo.index"))
