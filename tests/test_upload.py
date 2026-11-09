import io
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import app as appmod  # noqa: E402
from fileupload import MB  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "UPLOAD_DIR", str(tmp_path))
    a = appmod.create_app()
    a.config["TESTING"] = True
    return a.test_client(), tmp_path


def f(name, size=10):
    return (io.BytesIO(b"x" * size), name)


def post(c, docs=(), single=None):
    data = {"docs": list(docs)}
    data["single"] = [single or f("ok.txt")]
    return c.post("/upload", data=data, content_type="multipart/form-data", follow_redirects=True)


def test_index_renders_component(client):
    c, _ = client
    html = c.get("/").get_data(as_text=True)
    assert "data-fileupload" in html and 'data-max-files="5"' in html and "bootstrap@4.6.2" in html


def test_success_saves_uuid_names(client):
    c, tmp = client
    r = post(c, [f("a.png"), f("b.pdf")])
    assert r.status_code == 200 and len(os.listdir(tmp)) == 3
    assert "a.png" in r.get_data(as_text=True)


def test_max_files(client):
    c, tmp = client
    r = post(c, [f(f"{i}.png") for i in range(6)])
    assert "최대 5개" in r.get_data(as_text=True) and not os.listdir(tmp)


def test_disallowed_ext(client):
    c, _ = client
    assert "허용되지 않는 형식" in post(c, [f("a.txt")]).get_data(as_text=True)


def test_denied_double_extension(client):
    c, _ = client
    assert "금지된 형식" in post(c, single=f("evil.php.jpg")).get_data(as_text=True)


def test_file_size(client):
    c, _ = client
    assert "파일당 최대" in post(c, [f("a.png", 6 * MB)]).get_data(as_text=True)


def test_total_size(client):
    c, _ = client
    r = post(c, [f(f"{i}.png", 4 * MB) for i in range(4)])
    assert "전체 용량" in r.get_data(as_text=True)


def test_required(client):
    c, _ = client
    r = c.post("/upload", data={"docs": []}, content_type="multipart/form-data", follow_redirects=True)
    assert "파일을 선택" in r.get_data(as_text=True)
