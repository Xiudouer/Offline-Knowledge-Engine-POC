"""Deterministic parser/retrieval smoke demo. It is explicitly NOT a live model test."""
import io
import zipfile

from .docreader import Block, chunks, text_blocks
from .engine import Engine
from .net import EngineError


def docx_fixture():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Backup runs every day at 02:00.</w:t></w:r></w:p></w:body></w:document>')
    return stream.getvalue()


def pdf_fixture():
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
    writer = PdfWriter(); page = writer.add_blank_page(width=300, height=300)
    stream = DecodedStreamObject(); stream.set_data(b"BT /F1 12 Tf 20 200 Td (Backup daily at 02:00) Tj ET")
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO(); writer.write(output); return output.getvalue()


class FixtureModel:
    def identity(self):
        return {"model": "fixture-only", "digest": "fixture", "dimensions": 8}

    def embed(self, texts):
        return [[1.0] + [0.0] * 7 for _ in texts]

    def answer(self, question, sources):
        return "演示来源写明：每日 02:00 执行备份。[S1]"


class MemoryFixtureStore:
    def __init__(self):
        self.items = []

    def initialize(self, identity):
        return {"pgvector": "NOT USED IN FIXTURE DEMO"}

    def check_identity(self, identity):
        pass

    def ingest(self, doc_id, filename, checksum, items, vectors):
        self.items = [{**item, "doc_id": doc_id, "filename": filename, "ordinal": i, "score": 1.0} for i, item in enumerate(items)]
        return {"id": doc_id, "chunks": len(items)}

    def search(self, vector):
        return [dict(item) for item in self.items]


def demo():
    blocks = text_blocks("example.docx", docx_fixture())
    assert "02:00" in blocks[0].text
    pdf = text_blocks("sample.pdf", pdf_fixture())
    assert "02:00" in pdf[0].text and pdf[0].locator["page"] == 1
    items = chunks(text_blocks("sample.md", "每日 02:00 执行备份。".encode()))
    engine = Engine(MemoryFixtureStore(), FixtureModel(), parser=lambda name, data: chunks(text_blocks(name, data)))
    engine.ready()
    engine.ingest("sample.md", "每日 02:00 执行备份。".encode())
    result = engine.ask("备份周期是什么？")
    assert result["grounded"] and result["sources"][0]["locator"]["start"] == 0
    return {"mode": "FIXTURE SELF-TEST, NOT OLLAMA OR PGVECTOR", "passed": 4,
            "checks": ["local UTF-8 and DOCX parsing", "PDF text layer and page locator", "source position preservation", "pipeline and citation guard"],
            "answer": result["answer"], "live_stack_required": "start.bat + Docker + prepared local assets"}
