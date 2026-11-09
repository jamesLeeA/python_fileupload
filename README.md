# Flask + Bootstrap 4.6.2 파일 업로드 공통 컴포넌트

여러 파일/단일 파일, 최대 파일 수, 파일당·전체 용량, 허용·금지 확장자, 탐색기 드래그 앤 드롭.
파일은 일반 폼 submit 시 함께 전송됩니다. 최종 검증은 항상 서버에서 합니다.

## 파일 구성
| 파일 | 역할 |
|---|---|
| `fileupload.py` | 규칙(`UploadRules`), 검증, 저장 (서버) |
| `templates/_fileupload.html` | 화면 조각 (`file_upload` 매크로) |
| `static/fileupload.js`, `static/fileupload.css` | 브라우저 동작/모양 |
| `app.py`, `templates/base.html`, `templates/index.html` | 사용 예시(데모) |

## 실행
```bash
pip install -r requirements-dev.txt   # 운영은 requirements.txt
python app.py        # http://127.0.0.1:5000
python -m pytest
```

## 다른 페이지에 붙이기
1. 레이아웃 `<head>`에 (한 번)
   ```html
   <link rel="stylesheet" href="{{ url_for('static', filename='fileupload.css') }}">
   <script src="{{ url_for('static', filename='fileupload.js') }}" defer></script>
   ```
2. 페이지 템플릿 (`<form enctype="multipart/form-data">` 안)
   ```jinja
   {% from "_fileupload.html" import file_upload %}
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
