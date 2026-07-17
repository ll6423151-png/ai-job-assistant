from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from app.services.resume_parser import ResumeParseError, parse_resume


def test_docx_rejects_excessive_uncompressed_content():
    payload = BytesIO()
    with ZipFile(payload, "w", ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"A" * (33 * 1024 * 1024))

    with pytest.raises(ResumeParseError, match="解压后内容过大"):
        parse_resume("oversized.docx", payload.getvalue())


def test_resume_parser_rejects_unsupported_extension():
    with pytest.raises(ResumeParseError, match="仅支持"):
        parse_resume("resume.exe", b"not-a-resume")
