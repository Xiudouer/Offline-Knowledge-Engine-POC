"""HTTP boundary checks with a labelled fixture model/store; no live model claims."""
import json
import os
import queue
import secrets
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import http.client

from offlineknowledge.engine import Engine
from offlineknowledge.selftest import FixtureModel, MemoryFixtureStore
import offlineknowledge.server as application


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.token=secrets.token_hex(32)
        created=queue.Queue()
        class InspectServer(ThreadingHTTPServer):
            def __init__(self, address, handler):
                super().__init__(("127.0.0.1",0),handler);created.put(self)
        class FixtureStore(MemoryFixtureStore):
            def documents(self):return []
            def delete(self,doc_id):return {"deleted":True}
        def engine(store,model):return Engine(FixtureStore(),FixtureModel())
        cls.patches=[patch.object(application,"ThreadingHTTPServer",InspectServer),
                     patch.object(application,"Engine",engine),
                     patch.dict(os.environ,{"OKE_ACCESS_TOKEN":cls.token,"OKE_DB_PASSWORD":"p"*64})]
        for item in cls.patches:item.start()
        cls.thread=threading.Thread(target=application.main,daemon=True);cls.thread.start()
        cls.server=created.get(timeout=10)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(5)
        for item in reversed(cls.patches):item.stop()

    def request(self,path="/api/status",method="GET",body=None,headers=None):
        connection=http.client.HTTPConnection("127.0.0.1",self.server.server_port,timeout=10)
        connection.request(method,path,body,{"Host":"127.0.0.1:8080",**(headers or {})})
        response=connection.getresponse();data=response.read();result=(response.status,dict(response.getheaders()),data)
        connection.close();return result

    def test_27_authentication_required_and_token_not_embedded_in_ui(self):
        self.assertEqual(self.request()[0],401)
        status,headers,body=self.request("/")
        self.assertEqual(status,200);self.assertNotIn(self.token.encode(),body)
        self.assertIn("default-src 'self'",headers["Content-Security-Policy"])
        self.assertEqual(headers["Cache-Control"],"no-store")
        self.assertEqual(self.request(headers={"Authorization":"Bearer "+self.token})[0],200)

    def test_28_origin_and_dns_rebinding_host_rejected(self):
        self.assertEqual(self.request(headers={"Authorization":"Bearer "+self.token,"Origin":"https://evil.invalid"})[0],403)
        self.assertEqual(self.request(headers={"Authorization":"Bearer "+self.token,"Host":"evil.invalid"})[0],400)

    def test_29_bounded_upload_json_and_local_parser(self):
        auth={"Authorization":"Bearer "+self.token,"X-Filename":"policy.md"}
        self.assertEqual(self.request("/api/ingest","POST",b"Backup every day at 02:00.",auth)[0],200)
        self.assertEqual(self.request("/api/ingest","POST",b"x",{**auth,"X-Filename":"..%2Fx.txt"})[0],422)
        self.assertEqual(self.request("/api/ask","POST",b'{"url":"http://example.com"}',{**auth,"Content-Type":"application/json"})[0],400)

    def test_30_ui_has_no_external_assets_or_html_injection_sink(self):
        self.assertEqual(self.request("/app.js")[0],200)
        js=self.request("/app.js")[2].decode()
        self.assertNotIn("innerHTML",js)
        self.assertNotIn("localStorage",js)
        html=self.request("/")[2].decode()
        self.assertNotIn('src="http',html);self.assertNotIn('href="http',html)


if __name__=="__main__":unittest.main(verbosity=2)
