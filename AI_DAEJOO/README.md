# Flask + Bootstrap 4.6.2 파일 업로드 공통 컴포넌트

여러 파일/단일 파일, 최대 파일 수, 파일당·전체 용량, 허용·금지 확장자, 탐색기 드래그 앤 드롭.
파일은 일반 폼 submit 시 함께 전송됩니다. 최종 검증은 항상 서버에서 합니다.

## 파일 구성 (프로젝트: AI_DAEJOO)
```
AI_DAEJOO/
├─ run.py                                   실행 진입점
├─ app/
│  ├─ __init__.py                           create_app()
│  ├─ routers/
│  │  ├─ fileupload.py                      규칙(UploadRules)·검증·저장 (공통 모듈)
│  │  └─ upload.py                          데모 라우트(Blueprint)
│  ├─ templates/common/
│  │  ├─ _fileupload.html                   file_upload 매크로 (공통 화면 조각)
│  │  ├─ base.html, index.html              데모 레이아웃/페이지
│  └─ static/assets/
│     ├─ js/mcit/fileupload.js
│     └─ css/mcit/fileupload.css
├─ tests/test_upload.py
└─ uploads/                                 저장 폴더
```

## 실행
```bash
cd AI_DAEJOO
pip install -r requirements-dev.txt   # 운영은 requirements.txt
python run.py        # http://127.0.0.1:5000
python -m pytest
```

## 다른 페이지에 붙이기
1. 레이아웃 `<head>`에 (한 번)
   ```html
   <link rel="stylesheet" href="{{ url_for('static', filename='assets/css/mcit/fileupload.css') }}">
   <script src="{{ url_for('static', filename='assets/js/mcit/fileupload.js') }}" defer></script>
   ```
2. 페이지 템플릿 (`<form enctype="multipart/form-data">` 안)
   ```jinja
   {% from "common/_fileupload.html" import file_upload %}
   {{ file_upload('attachments', rules) }}
   ```
3. 서버
   ```python
   rules = UploadRules(max_files=3, max_file_size=5*MB, max_total_size=10*MB,
                       allow=["jpg", "png", "pdf"], deny=["exe"])
   # 화면: render_template(..., rules=rules)
   # 저장: saved = save_files(request.files.getlist("attachments"), rules, UPLOAD_DIR)
   ```
   실패하면 `UploadError`(`e.errors` 메시지 목록)가 발생합니다. 화면과 저장에 같은 규칙을 넘기세요.

`deny`가 `allow`보다 우선하며 `a.php.jpg` 같은 이중 확장자도 막습니다. 저장 파일명은 UUID이고 원본 이름은 반환값의 `original_name`에 있습니다.
