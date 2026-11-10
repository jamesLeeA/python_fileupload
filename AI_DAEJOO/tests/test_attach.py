import io
import os
import sys

import pytest
from flask import render_template_string, request

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app import create_app  # noqa: E402
from app.attach import (MB, AttachConfig, AttachError, attach_create, attach_delete_all,  # noqa: E402
                        attach_list, attach_update, attach_validate, attach_view)


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "ATTACH_DIR": str(tmp_path / "up"), "ATTACH_DB": str(tmp_path / "t.db")})


def rq(app, files=(), delete=(), field="attach"):
    """파일/삭제 id 가 담긴 POST multipart 요청 컨텍스트."""
    data = {field: [(io.BytesIO(c), n) for n, c in files]}
    if delete:
        data[field + "_delete"] = [str(i) for i in delete]
    return app.test_request_context("/", method="POST", data=data, content_type="multipart/form-data")


def disk(app):
    d = app.config["ATTACH_DIR"]
    return sorted(os.listdir(d)) if os.path.isdir(d) else []


def state(app):
    return disk(app), attach_list(("n", 1))


def create(app, cfg, files, ref=("n", 1)):
    with rq(app, files, field=cfg.field):
        return attach_create(cfg, ref, request)


def errors_of(app, cfg, files, ref=None, delete=()):
    with rq(app, files, delete, field=cfg.field):
        with pytest.raises(AttachError) as e:
            attach_validate(cfg, request, ref)
    return e.value.errors


# 1. enabled=False
def test_disabled_does_nothing(app):
    cfg = AttachConfig(enabled=False)
    with app.test_request_context():
        assert attach_view(cfg) is None
    with rq(app, [("a.php", b"x")]):
        attach_validate(cfg, request)
        assert attach_create(cfg, ("n", 1), request) == []
        assert attach_update(cfg, ("n", 1), request) == []
    with app.test_request_context():
        assert attach_delete_all(("n", 1)) == 0
        assert disk(app) == []


# 2. 확장자 정규화, ui 검증
def test_normalize_and_ui():
    cfg = AttachConfig(allow=(".JPG", "jpg", " Png "), deny=("EXE", ".exe"))
    assert cfg.allow == ("jpg", "png") and cfg.deny == ("exe",)
    with pytest.raises(ValueError):
        AttachConfig(ui="popup")


# 3. 확장자 규칙
@pytest.mark.parametrize("name,msg", [
    ("a.txt", "허용되지 않는 형식"),
    ("a.exe", "첨부할 수 없는"),
    ("a.php.jpg", "첨부할 수 없는"),
    ("noext", "확장자가 없는"),
])
def test_extension_rules(app, name, msg):
    cfg = AttachConfig(allow=("jpg",))
    errs = errors_of(app, cfg, [(name, b"x")])
    assert len(errs) == 1 and msg in errs[0] and name in errs[0]


def test_all_errors_collected(app):
    cfg = AttachConfig(allow=("jpg",))
    assert len(errors_of(app, cfg, [("a.txt", b"x"), ("b.exe", b"x")])) == 2


# 4. 용량/개수 초과 + 실패 시 변경 없음
@pytest.mark.parametrize("cfg,files,msg", [
    (AttachConfig(max_file_size=5), [("a.txt", b"123456")], "파일당 최대"),
    (AttachConfig(max_files=1), [("a.txt", b"1"), ("b.txt", b"1")], "최대 1개"),
    (AttachConfig(max_total_size=5), [("a.txt", b"123"), ("b.txt", b"123")], "전체 용량"),
])
def test_limits_leave_no_trace(app, cfg, files, msg):
    with rq(app, files):
        with pytest.raises(AttachError) as e:
            attach_create(cfg, ("n", 1), request)
    assert any(msg in m for m in e.value.errors)
    with app.test_request_context():
        assert state(app) == ([], [])


def test_failure_during_save_cleans_files(app, monkeypatch):
    import app.attach.core as core
    monkeypatch.setattr(core, "_write", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("db down")))
    with rq(app, [("a.txt", b"1"), ("b.txt", b"1")]):
        with pytest.raises(RuntimeError):
            attach_create(AttachConfig(), ("n", 1), request)
    with app.test_request_context():
        assert disk(app) == []


# 5. 신규 등록
def test_create_uses_uuid_and_keeps_original_name(app):
    with app.test_request_context():
        metas = create(app, AttachConfig(), [("보고서.PDF", b"hello")])
        assert metas[0]["original_name"] == "보고서.PDF"
        stored = metas[0]["stored_name"]
        assert stored != "보고서.PDF" and stored.endswith(".pdf") and len(stored) == 36
        assert disk(app) == [stored]
        f = attach_list(("n", 1))[0]
        assert f["original_name"] == "보고서.PDF" and f["size"] == 5


# 6. 수정: 합산 검증
def test_update_counts_kept_plus_new(app):
    cfg = AttachConfig(max_files=2)
    with app.test_request_context():
        create(app, cfg, [("a.txt", b"1"), ("b.txt", b"1")])
        a, b = attach_list(("n", 1))
        with rq(app, [("c.txt", b"1")]):  # 기존 2 + 신규 1 > 2
            with pytest.raises(AttachError):
                attach_update(cfg, ("n", 1), request)
        assert len(attach_list(("n", 1))) == 2
        with rq(app, [("c.txt", b"1")], delete=[a["id"]]):  # 2 - 1 + 1 = 2
            attach_update(cfg, ("n", 1), request)
        names = [f["original_name"] for f in attach_list(("n", 1))]
        assert names == ["b.txt", "c.txt"] and len(disk(app)) == 2


def test_update_total_size_counts_existing(app):
    cfg = AttachConfig(max_total_size=5)
    with app.test_request_context():
        create(app, cfg, [("a.txt", b"1234")])
        with rq(app, [("b.txt", b"12")]):
            with pytest.raises(AttachError):
                attach_update(cfg, ("n", 1), request)


# 7. 다른 ref 의 id 는 지워지지 않음
def test_cannot_delete_other_ref(app):
    cfg = AttachConfig()
    with app.test_request_context():
        create(app, cfg, [("mine.txt", b"1")], ref=("n", 1))
        create(app, cfg, [("other.txt", b"1")], ref=("n", 2))
        other = attach_list(("n", 2))[0]["id"]
        with rq(app, delete=[other]):
            attach_update(cfg, ("n", 1), request)
        assert len(attach_list(("n", 2))) == 1 and len(disk(app)) == 2


# 8. 글 삭제
def test_delete_all(app):
    cfg = AttachConfig()
    with app.test_request_context():
        create(app, cfg, [("a.txt", b"1"), ("b.txt", b"1")])
        os.remove(os.path.join(app.config["ATTACH_DIR"], disk(app)[0]))  # 이미 없는 파일
        assert attach_delete_all(("n", 1)) == 2
        assert attach_list(("n", 1)) == [] and disk(app) == []
        assert attach_delete_all(("n", 1)) == 0


# 9. 다운로드
def test_download(app):
    with app.test_request_context():
        create(app, AttachConfig(), [("report.pdf", b"data")])
        fid = attach_list(("n", 1))[0]["id"]
    c = app.test_client()
    r = c.get(f"/attach/{fid}")
    assert r.status_code == 200 and r.data == b"data"
    assert "attachment" in r.headers["Content-Disposition"] and "report.pdf" in r.headers["Content-Disposition"]
    assert c.get("/attach/9999").status_code == 404
    app.config["ATTACH_CAN_DOWNLOAD"] = lambda row: False
    assert c.get(f"/attach/{fid}").status_code == 403


# 10. 매크로
def test_macro_markup(app):
    tpl = '{% from "attach/_attach.html" import attach_field %}{{ attach_field(attach) }}'
    with app.test_request_context():
        create(app, AttachConfig(), [("a.pdf", b"123")])
        drop = render_template_string(tpl, attach=attach_view(
            AttachConfig(ui="drop", max_files=3, allow=("pdf",)), ("n", 1)))
        btn = render_template_string(tpl, attach=attach_view(AttachConfig(ui="button"), ("n", 1)))
        assert render_template_string(tpl, attach=None).strip() == ""
    assert 'data-ui="drop"' in drop and "attach-drop" in drop and "attach-btn" not in drop
    assert 'data-max-files="3"' in drop and 'data-allow="pdf"' in drop and 'accept=".pdf"' in drop
    assert 'data-ui="button"' in btn and "attach-btn" in btn and "attach-drop" not in btn
    assert 'data-id="' in drop and 'data-size="3"' in drop and "a.pdf" in drop and "/attach/" in drop
    assert 'name="attach"' in drop and "<form" not in drop
