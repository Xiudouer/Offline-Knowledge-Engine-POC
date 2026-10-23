import base64
from contextlib import contextmanager
import io
import json
import math
from pathlib import Path
import socket
import threading
import unittest
from unittest.mock import patch
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from offlineknowledge.docreader import Block, chunks, text_blocks
from offlineknowledge.engine import Engine, parse_local, select_sources
from offlineknowledge.manager import configuration, verify_assets
from offlineknowledge.net import EngineError, Ollama, private_address, validate_vector
from offlineknowledge.selftest import FixtureModel, MemoryFixtureStore, docx_fixture, demo
from offlineknowledge.store import Store, literal


class ParserTests(unittest.TestCase):
    def test_01_utf8_chinese_text_and_bom(self):
        self.assertEqual(text_blocks("中文.md", b'\xef\xbb\xbf' + "内网知识".encode())[0].text, "内网知识")

    def test_02_docx_text_only_no_external_fetch(self):
        with patch("socket.create_connection", side_effect=AssertionError("network forbidden")):
            self.assertIn("02:00", text_blocks("sample.docx", docx_fixture())[0].text)

    def test_03_filename_path_url_and_type_rejected(self):
        for name in ("../secret.txt", "a\\secret.txt", "https://example.com/a.txt", "x.html", "x.exe", "x\x00.txt"):
            with self.assertRaises(EngineError):
                text_blocks(name, b"hello")

    def test_04_binary_empty_wrong_encoding_rejected(self):
        for data in (b"", b"a\x00b", b"\xff\xff"):
            with self.assertRaises(EngineError):
                text_blocks("x.txt", data)

    def test_05_docx_entities_and_zip_expansion_rejected(self):
        for xml in ('<!DOCTYPE x [<!ENTITY x "boom">]><x/>', "x" * 100000):
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("word/document.xml", xml)
            with self.assertRaises(EngineError):
                text_blocks("x.docx", stream.getvalue())

    def test_06_pdf_text_page_locator_and_empty_scan(self):
        from pypdf import PdfWriter
        from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        writer = PdfWriter()
        page = writer.add_blank_page(width=300, height=300)
        stream = DecodedStreamObject()
        stream.set_data(b"BT /F1 12 Tf 20 200 Td (Backup daily at 02:00) Tj ET")
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        page[NameObject("/Contents")] = writer._add_object(stream)
        target = io.BytesIO(); writer.write(target)
        blocks = text_blocks("sample.pdf", target.getvalue())
        self.assertEqual(blocks[0].locator["page"], 1)
        self.assertIn("02:00", blocks[0].text)
        blank = PdfWriter(); blank.add_blank_page(width=100, height=100); out=io.BytesIO(); blank.write(out)
        with self.assertRaises(EngineError):
            text_blocks("scan.pdf", out.getvalue())

    def test_07_chunks_preserve_offsets_overlap_and_pages(self):
        text = "甲乙丙丁" * 600
        result = chunks([Block(text, {"type": "pdf", "page": 7})])
        for item in result:
            locator = item["locator"]
            self.assertEqual(item["content"], text[locator["start"]:locator["end"]])
            self.assertEqual(locator["page"], 7)
        self.assertEqual(result[1]["locator"]["start"], 620)
        self.assertEqual(result[-1]["locator"]["end"], len(text))

    def test_08_bounded_subprocess_parser(self):
        self.assertEqual(parse_local("x.md", b"Local reader text")[0]["content"], "Local reader text")


class PolicyTests(unittest.TestCase):
    def test_09_public_cloud_metadata_endpoints_rejected(self):
        for host in ("example.com", "api.openai.com", "169.254.169.254", "8.8.8.8"):
            with self.assertRaises(EngineError): private_address(host, 11434)
        with patch("socket.getaddrinfo", return_value=[(socket.AF_INET,socket.SOCK_STREAM,0,"",("8.8.8.8",11434))]):
            with self.assertRaises(EngineError): private_address("ollama",11434)

    def test_10_remote_and_malformed_model_urls_rejected(self):
        for url in ("https://cloud.example.com", "http://user:password@localhost:11434", "http://localhost:11434/prefix", "http://localhost:11434?x=1"):
            with self.assertRaises(EngineError): Ollama(url)
        with self.assertRaises(EngineError): Ollama(chat_model="qwen-cloud")

    def test_11_embedding_validation_finite_shape_nonzero(self):
        self.assertAlmostEqual(sum(v*v for v in validate_vector([1.0]*8,8)),1)
        for value in ([0.0]*8, [1.0]*7, [float("nan")]*8, [float("inf")]*8, [True]*8):
            with self.assertRaises(EngineError): validate_vector(value,8)

    def test_12_compose_internal_loopback_no_pull_no_host_sockets(self):
        config=configuration(Path("."),"t"*64,"p"*64,"a"*64)
        self.assertTrue(config["networks"]["offline"]["internal"])
        for name, service in config["services"].items():
            self.assertEqual(service["pull_policy"],"never")
            self.assertEqual(set(service["networks"]),{"offline"})
            self.assertEqual(service["dns"],["127.0.0.1"])
            self.assertEqual(service["environment"]["HTTP_PROXY"],"")
            self.assertEqual(service["environment"]["HTTPS_PROXY"],"")
            self.assertEqual(service["environment"]["ALL_PROXY"],"")
            self.assertEqual(service["environment"]["NO_PROXY"],"*")
            self.assertNotIn("docker.sock",json.dumps(service))
            if name!="app": self.assertNotIn("ports",service)
        self.assertEqual(config["services"]["app"]["ports"],["127.0.0.1:18787:8080"])
        self.assertEqual(config["services"]["ollama"]["environment"]["OLLAMA_NO_CLOUD"],"1")

    def test_13_missing_assets_do_not_silently_go_online(self):
        missing = Path(__file__).resolve().parent / "not-a-prepared-bundle"
        with self.assertRaises(RuntimeError): verify_assets(missing)


class RetrievalTests(unittest.TestCase):
    def engine(self, model=None):
        return Engine(MemoryFixtureStore(),model or FixtureModel(),lambda name,data:chunks(text_blocks(name,data)))

    def test_14_pipeline_citations_and_source_offsets(self):
        engine=self.engine(); engine.ingest("policy.md","每日 02:00 备份".encode())
        result=engine.ask("何时备份？")
        self.assertTrue(result["grounded"])
        self.assertEqual(result["sources"][0]["filename"],"policy.md")

    def test_15_no_sources_never_invokes_generation(self):
        model=FixtureModel(); model.answer=lambda *args: (_ for _ in ()).throw(AssertionError("should not generate"))
        result=self.engine(model).ask("unknown")
        self.assertFalse(result["grounded"])
        self.assertEqual(result["sources"],[])

    def test_16_invented_or_missing_citation_is_rejected(self):
        for answer in ("invented [S999]", "No citations"):
            model=FixtureModel(); model.answer=lambda *args,a=answer:a
            engine=self.engine(model); engine.ingest("x.txt",b"Local evidence")
            self.assertFalse(engine.ask("question")["grounded"])

    def test_17_low_similarity_and_budget(self):
        candidates=[{"score":0.1,"content":"x"*100,"filename":"x","locator":{}}]
        self.assertEqual(select_sources(candidates,"x"),[])
        candidates[0]["score"]=0.9
        self.assertEqual(select_sources(candidates,"x",budget=50),[])

    def test_18_failed_embedding_does_not_call_storage(self):
        model=FixtureModel(); model.embed=lambda _: (_ for _ in ()).throw(EngineError("failed",503))
        engine=self.engine(model)
        with self.assertRaises(EngineError): engine.ingest("x.txt",b"sample")
        self.assertEqual(engine.store.items,[])

    def test_19_model_identity_mismatch_stops_query_before_embeddings(self):
        engine=self.engine()
        engine.store.check_identity=lambda _:(_ for _ in ()).throw(EngineError("reindex_required",409))
        engine.model.embed=lambda _: (_ for _ in ()).throw(AssertionError("must not run"))
        with self.assertRaises(EngineError): engine.ask("query")

    def test_20_question_and_vector_sql_input_limits(self):
        engine=self.engine()
        for question in ("",None,"x"*2001):
            with self.assertRaises(EngineError): engine.ask(question)
        with self.assertRaises(EngineError): Store(password="p",dimensions=0)
        self.assertTrue(literal([1.0]*8,8).startswith("["))


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seen=[]; cls.response={}; cls.status=200
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self): self.handle_request()
            def do_POST(self): self.handle_request()
            def handle_request(self):
                size=int(self.headers.get("Content-Length",0)); body=self.rfile.read(size)
                cls.seen.append((self.path,json.loads(body) if body else None))
                self.send_response(cls.status)
                if cls.status==302: self.send_header("Location","http://example.com/forbidden")
                self.end_headers();self.wfile.write(json.dumps(cls.response).encode())
            def log_message(self,*args):pass
        cls.server=ThreadingHTTPServer(("127.0.0.1",0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()

    def setUp(self):
        type(self).status=200;type(self).response={};type(self).seen=[]
        self.model=Ollama(f"http://127.0.0.1:{self.server.server_port}",dimensions=8)

    def test_21_real_http_embedding_no_proxy_and_no_truncate(self):
        type(self).response={"embeddings":[[1.0]*8]}
        with patch.dict("os.environ",{"HTTP_PROXY":"http://127.0.0.1:1","ALL_PROXY":"http://127.0.0.1:1"}):
            result=self.model.embed(["synthetic public text"])
        self.assertEqual(len(result[0]),8)
        self.assertFalse(self.seen[-1][1]["truncate"])

    def test_22_redirect_not_followed(self):
        type(self).status=302
        with self.assertRaises(EngineError):self.model.request("/api/tags")
        self.assertEqual(len(self.seen),1)

    def test_23_cloud_and_missing_models_rejected(self):
        with patch.object(self.model,"request",return_value={"models":[]}):
            with self.assertRaises(EngineError):self.model.identity()
        def response(path,payload=None):
            if path=="/api/tags":return {"models":[{"name":n,"digest":"x"} for n in (self.model.embed_model,self.model.chat_model)]}
            return {"remote_host":"https://cloud.example.com"}
        with patch.object(self.model,"request",side_effect=response):
            with self.assertRaises(EngineError):self.model.identity()

    def test_24_forbidden_model_route_and_bad_embedding_count(self):
        with self.assertRaises(EngineError):self.model.request("/api/pull",{})
        type(self).response={"embeddings":[]}
        with self.assertRaises(EngineError):self.model.embed(["test"])

    def test_25_sql_parameterization_and_failed_transaction_contract(self):
        class Fake:
            def __init__(self):self.calls=[];self.answer=None
            def execute(self,query,args=None):
                self.calls.append((query,args))
                if "count(*)" in query:self.answer=(0,)
                else:self.answer=None
                return self
            def fetchone(self):return self.answer
        connection=Fake()
        @contextmanager
        def connect():yield connection
        store=Store(password="test",dimensions=8,connect=connect)
        malicious="x');DROP TABLE documents;--.txt"
        store.ingest("a"*64,malicious,"b"*64,[{"content":"private text","locator":{}}],[[1.0]*8])
        self.assertTrue(any(malicious in (args or ()) for _,args in connection.calls))
        self.assertTrue(all(malicious not in query for query,_ in connection.calls))

    def test_26_fixture_demo_is_explicitly_labelled(self):
        result=demo();self.assertEqual(result["passed"],4)
        self.assertIn("NOT OLLAMA OR PGVECTOR",result["mode"])


if __name__=="__main__":unittest.main(verbosity=2)
