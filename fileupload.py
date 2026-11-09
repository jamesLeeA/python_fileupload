"""파일 업로드 규칙 / 검증 / 저장.

규칙(UploadRules)은 화면(templates/_fileupload.html)과 서버 검증에 같이 쓰인다.
브라우저 검증은 편의용이고, 최종 검증은 항상 save_files()에서 서버가 한다.
"""
import os
import uuid
from dataclasses import dataclass, field
from typing import Optional

MB = 1024 * 1024


class UploadError(Exception):
    """검증 실패. errors 에 사용자에게 보여줄 메시지 목록이 있다."""

    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = errors


def _exts(values):
    return tuple(sorted({v.strip().lower().lstrip(".") for v in values if v and v.strip()}))


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n}B" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024


@dataclass(frozen=True)
class UploadRules:
    max_files: Optional[int] = None          # 최대 파일 수 (None = 무제한)
    max_file_size: Optional[int] = 10 * MB   # 파일당 최대 바이트
    max_total_size: Optional[int] = None     # 전체 최대 바이트
    allow: tuple = field(default_factory=tuple)  # 허용 확장자 (비면 전체 허용)
    deny: tuple = field(default_factory=tuple)   # 금지 확장자 (allow 보다 우선)
    multiple: bool = True
    required: bool = False

    def __post_init__(self):
        object.__setattr__(self, "allow", _exts(self.allow))
        object.__setattr__(self, "deny", _exts(self.deny))
        if not self.multiple:
            object.__setattr__(self, "max_files", 1)

    # --- 화면용 (templates/_fileupload.html 에서 사용) ---
    def attrs(self):
        """JS가 읽는 data-* 속성."""
        a = {"multiple": str(self.multiple).lower(), "required": str(self.required).lower(),
             "allow": ",".join(self.allow), "deny": ",".join(self.deny)}
        if self.max_files is not None:
            a["max-files"] = self.max_files
        if self.max_file_size is not None:
            a["max-file-size"] = self.max_file_size
        if self.max_total_size is not None:
            a["max-total-size"] = self.max_total_size
        return a

    def hint(self):
        """드롭 영역 아래 안내 문구."""
        parts = []
        if self.max_files:
            parts.append(f"최대 {self.max_files}개")
        if self.max_file_size:
            parts.append(f"파일당 {human_size(self.max_file_size)}")
        if self.max_total_size:
            parts.append(f"전체 {human_size(self.max_total_size)}")
        if self.allow:
            parts.append("허용 " + ", ".join(self.allow))
        if self.deny:
            parts.append("금지 " + ", ".join(self.deny))
        return " · ".join(parts)


def _size(f):
    pos = f.stream.tell()
    f.stream.seek(0, os.SEEK_END)
    size = f.stream.tell()
    f.stream.seek(pos)
    return size


def validate_files(files, rules):
    """빈 항목을 제거하고 규칙을 검증한다. 실패하면 UploadError."""
    files = [f for f in files if f and f.filename]
    errors = []

    if rules.required and not files:
        raise UploadError(["파일을 선택해 주세요."])
    if rules.max_files is not None and len(files) > rules.max_files:
        errors.append(f"파일은 최대 {rules.max_files}개까지 업로드할 수 있습니다.")

    total = 0
    for f in files:
        exts = [p for p in f.filename.lower().split(".")[1:] if p]
        denied = [e for e in exts if e in rules.deny]  # a.php.jpg 같은 이중 확장자도 검사
        if denied:
            errors.append(f"'{f.filename}': 업로드가 금지된 형식(.{denied[0]})입니다.")
            continue
        if rules.allow and (not exts or exts[-1] not in rules.allow):
            errors.append(f"'{f.filename}': 허용되지 않는 형식입니다. "
                          f"(허용: {', '.join('.' + e for e in rules.allow)})")
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


def save_files(files, rules, upload_dir):
    """검증 후 UUID 파일명으로 저장하고 메타데이터 목록을 반환한다."""
    files = validate_files(files, rules)
    os.makedirs(upload_dir, exist_ok=True)
    saved = []
    for f in files:
        stored = uuid.uuid4().hex + os.path.splitext(f.filename)[1].lower()
        path = os.path.join(upload_dir, stored)
        f.save(path)
        saved.append({"original_name": f.filename, "stored_name": stored,
                      "size": os.path.getsize(path), "content_type": f.mimetype})
    return saved
