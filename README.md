# Flask + Bootstrap 4.6.2 파일 업로드 공통 컴포넌트

- 여러 파일 / 단일 파일, 최대 파일 수, 파일당·전체 용량, 허용·금지 확장자
- 탐색기 파일 드래그 앤 드롭 + 클릭 선택, 개별 삭제, 이미지 썸네일
- 파일은 일반 폼 submit 시 함께 전송 (네이티브 `<input type=file>`에 동기화)
- 규칙(`UploadRules`) 하나로 화면과 서버 검증을 동시에 구성 (최종 검증은 서버)

## 실행
```bash
# Python 3.15 (.python-version), 기존 사이트와 동일한 고정 버전
pip install -r requirements-dev.txt   # 운영은 requirements.txt
python app.py        # http://127.0.0.1:5000
pytest
```

## 다른 페이지에서 사용
1. 앱 초기화: `fileupload.init_app(app)` (한 번)
2. 레이아웃 `<head>`에 `{{ file_upload_assets() }}` (한 번, Bootstrap 4.6.2 CSS 뒤)
3. 원하는 위치에 `{{ file_upload('필드명', rules) }}` (`<form enctype="multipart/form-data">` 안)
4. 서버: `save_files(request.files.getlist('필드명'), rules, UPLOAD_DIR)` → 메타데이터 리스트 반환, 실패 시 `UploadError`

```python
rules = UploadRules(max_files=3, max_file_size=5*MB, max_total_size=10*MB,
                    allow=["jpg", "png", "pdf"], deny=["exe"], multiple=True, required=False)
```
- `deny`가 `allow`보다 우선하며, `a.php.jpg` 같은 이중 확장자도 `deny`로 차단됩니다.
- 저장 파일명은 UUID, 원본 이름은 반환된 메타데이터(`original_name`)로 보관합니다.
