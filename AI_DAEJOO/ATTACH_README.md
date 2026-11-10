# 첨부파일 공통 모듈 적용 방법

Flask + Jinja2 + Bootstrap 4.6.2 + 순수 JS(ES5). 파일은 `uploads/`, 메타데이터는 SQLite(`attach_file` 테이블, 자동 생성)에 저장합니다.
함수 한 번(서버) + 매크로 한 줄(화면)로 붙이고, 쓰지 않는 페이지는 `enabled=False` 하나로 끕니다.

## 1단계. 파일 복사
```
app/attach/            (__init__.py, core.py, routes.py)
app/templates/attach/_attach.html
app/static/attach/     (attach.js, attach.css)
```
`app/routers/attach_demo.py`, `templates/demo/` 는 데모라서 복사하지 않아도 됩니다.

## 2단계. 등록 한 줄 + 레이아웃 링크
```python
from app.attach.routes import bp as attach_bp      # 다운로드 라우트 (선택)
app.register_blueprint(attach_bp)
# 선택: app.config["ATTACH_DIR"] / ["ATTACH_DB"] (기본: <프로젝트>/uploads, uploads/attach.db)
# 선택: app.config["ATTACH_CAN_DOWNLOAD"] = lambda row: True   # False 면 403
```
```html
<link rel="stylesheet" href="{{ url_for('static', filename='attach/attach.css') }}">
<script src="{{ url_for('static', filename='attach/attach.js') }}" defer></script>
```
(Bootstrap 4.6.2 CSS 가 먼저 로드돼 있어야 합니다.)

## 3단계. 설정 객체 + 함수 호출 + 매크로 한 줄
```python
from app.attach import (AttachConfig, MB, AttachError, attach_view, attach_validate,
                        attach_create, attach_update, attach_delete_all)

NOTICE_ATTACH = AttachConfig(ui="drop", max_files=5, max_file_size=10*MB,
                             max_total_size=30*MB, allow=("jpg", "png", "pdf"))
QNA_ATTACH    = AttachConfig(ui="button", max_files=1, max_file_size=5*MB)
FAQ_ATTACH    = AttachConfig(enabled=False)                # 첨부 미사용

# 등록 화면 / 수정 화면
render_template("notice/form.html", attach=attach_view(NOTICE_ATTACH))                       # 신규
render_template("notice/form.html", attach=attach_view(NOTICE_ATTACH, ("notice", pid)))      # 수정

# 신규 저장: 글 저장 전에 첨부를 먼저 검증
attach_validate(NOTICE_ATTACH, request)                    # 실패 시 AttachError (e.errors: 한국어 메시지 목록)
post_id = save_post(request.form)
attach_create(NOTICE_ATTACH, ("notice", post_id), request)

# 수정 저장: 삭제 표시한 기존 파일 + 신규 파일 합계로 검증 (실패하면 아무것도 바뀌지 않음)
attach_update(NOTICE_ATTACH, ("notice", pid), request)

# 글 삭제
attach_delete_all(("notice", pid))
```
```jinja
{% from "attach/_attach.html" import attach_field %}
<form method="post" enctype="multipart/form-data">
  ...
  {{ attach_field(attach) }}      {# attach 가 None(enabled=False)이면 아무것도 그리지 않음 #}
</form>
```

## 참고
- 첨부는 `(ref_type, ref_id)` 로 글에 묶입니다. 한 글에 필드가 여러 개면 `AttachConfig(field="...")` 를 서로 다르게 줍니다.
- `deny` 는 `allow` 보다 우선하고, `a.php.jpg` 같은 이중 확장자도 막습니다. 서버 검증이 최종 판단입니다.
- `enabled=False` 면 모든 함수가 아무 일도 하지 않고 `[]`/`0`/`None` 을 돌려줘서 호출부에 if 분기가 필요 없습니다.
- 데모: `python run.py` 후 http://127.0.0.1:5000/attach-demo . 테스트: `python -m pytest`.
- 설치: `pip install -r requirements-dev.txt` (운영은 `requirements.txt`).
