"""Local file-only reader. No URL/file-path resolution, OCR, macros or external assets."""
from dataclasses import asdict, dataclass
import io
import json
from pathlib import Path
import sys
import zipfile
from xml.etree import ElementTree

from .net import EngineError

MAX_FILE = 20 * 1024 * 1024
MAX_TEXT = 2_000_000
MAX_PAGES = 300
SUPPORTED = {".txt", ".md", ".csv", ".pdf", ".docx"}


@dataclass
class Block:
    text: str
    locator: dict


def text_blocks(filename, data):
    if not isinstance(filename, str) or not filename or len(filename) > 180 or any(c in filename for c in "/\\\x00\r\n"):
        raise EngineError("invalid_filename")
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED or not data or len(data) > MAX_FILE:
        raise EngineError("unsupported_or_oversize_document")
    if suffix in {".txt", ".md", ".csv"}:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeError:
            raise EngineError("text_requires_utf8") from None
        if "\x00" in text:
            raise EngineError("binary_text_rejected")
        blocks = [Block(text, {"type": "text", "section": 1})]
    elif suffix == ".docx":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                infos = archive.infolist()
                if len(infos) > 10000 or sum(i.file_size for i in infos) > 80 * 1024 * 1024:
                    raise EngineError("docx_expansion_limit")
                info = archive.getinfo("word/document.xml")
                if info.file_size > 12 * 1024 * 1024 or info.file_size > max(info.compress_size, 1) * 200:
                    raise EngineError("docx_expansion_limit")
                xml = archive.read(info)
                if b"\x00" in xml or b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
                    raise EngineError("xml_entities_forbidden")
                document = ElementTree.fromstring(xml)
                ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
                text = "\n".join("".join(t.text or "" for t in p.iter(ns + "t")) for p in document.iter(ns + "p"))
                blocks = [Block(text, {"type": "docx", "section": 1})]
        except EngineError:
            raise
        except Exception:
            raise EngineError("docx_parse_failed") from None
    else:
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data), strict=True)
            if reader.is_encrypted:
                raise EngineError("encrypted_pdf_not_supported")
            if len(reader.pages) > MAX_PAGES:
                raise EngineError("pdf_page_limit")
            blocks = [Block(page.extract_text() or "", {"type": "pdf", "page": i+1}) for i, page in enumerate(reader.pages)]
        except EngineError:
            raise
        except Exception:
            raise EngineError("pdf_parse_failed") from None
    if sum(len(b.text) for b in blocks) > MAX_TEXT:
        raise EngineError("document_text_limit")
    if not any(b.text.strip() for b in blocks):
        raise EngineError("no_extractable_text_ocr_not_included")
    return blocks


def chunks(blocks, size=700, overlap=80):
    if not (64 <= size <= 1200 and 0 <= overlap < size):
        raise ValueError("invalid chunk policy")
    result = []
    for block in blocks:
        text = block.text.replace("\r\n", "\n").replace("\r", "\n")
        start = 0
        while start < len(text):
            end = min(start + size, len(text))
            content = text[start:end]
            if content.strip():
                result.append({"content": content, "locator": {**block.locator, "start": start, "end": end}})
            if end == len(text):
                break
            start = end - overlap
    if not result or len(result) > 5000:
        raise EngineError("chunk_count_limit")
    return result


def worker():
    # Container parser child: limit address space/CPU; parent enforces wall time.
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CPU, (25, 25))
    except ImportError:
        pass
    import logging
    logging.disable(logging.CRITICAL)
    try:
        request = json.loads(sys.stdin.buffer.read(MAX_FILE * 2))
        import base64
        data = base64.b64decode(request["data"], validate=True)
        output = {"chunks": chunks(text_blocks(request["filename"], data))}
    except EngineError as error:
        output = {"error": error.code}
    except Exception:
        output = {"error": "local_parse_failed"}
    sys.stdout.write(json.dumps(output, ensure_ascii=True))


if __name__ == "__main__":
    worker()
