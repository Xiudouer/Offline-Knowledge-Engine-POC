"""Bounded local RAG pipeline; sources remain explicit and prompt text is never a tool."""
import base64
import hashlib
import json
import re
import subprocess
import sys
import threading

from .docreader import MAX_FILE
from .net import EngineError


def parse_local(filename, data):
    if len(data) > MAX_FILE:
        raise EngineError("document_too_large", 413)
    request = json.dumps({"filename": filename, "data": base64.b64encode(data).decode()}).encode()
    try:
        result = subprocess.run([sys.executable, "-m", "offlineknowledge.docreader"], input=request,
                                capture_output=True, timeout=35, check=False)
    except subprocess.TimeoutExpired:
        raise EngineError("local_parser_timeout", 422) from None
    if result.returncode != 0 or len(result.stdout) > 24 * 1024 * 1024:
        raise EngineError("local_parser_failed", 422)
    try:
        output = json.loads(result.stdout)
    except ValueError:
        raise EngineError("local_parser_failed", 422) from None
    if "error" in output:
        raise EngineError(output["error"], 422)
    return output["chunks"]


def select_sources(candidates, question, top_k=5, budget=5000):
    # Cosine is the primary candidate gate; lexical overlap only reorders those candidates.
    terms = set(re.findall(r"[A-Za-z0-9_]{2,}|[\u4e00-\u9fff]{2}", question.lower()))
    for hit in candidates:
        text = hit["content"].lower()
        hit["rank"] = hit["score"] + (0.08 * sum(term in text for term in terms) / max(len(terms), 1))
    result, used = [], 0
    for hit in sorted(candidates, key=lambda h: h["rank"], reverse=True):
        if hit["score"] < 0.2:
            continue
        if used + len(hit["content"]) > budget:
            continue
        result.append({**hit, "citation": "S" + str(len(result) + 1)})
        used += len(hit["content"])
        if len(result) == top_k:
            break
    return result


class Engine:
    def __init__(self, store, model, parser=parse_local):
        self.store, self.model, self.parser = store, model, parser
        self.lock = threading.Lock()

    def ready(self):
        identity = self.model.identity()
        database = self.store.initialize(identity)
        return {"ready": True, "embedding": identity, **database}

    def ingest(self, filename, data):
        with self.lock:
            self.store.check_identity(self.model.identity())
            items = self.parser(filename, data)
            checksum = hashlib.sha256(data).hexdigest()
            doc_id = hashlib.sha256(filename.encode("utf8") + b"\0" + data).hexdigest()
            vectors = []
            for start in range(0, len(items), 16):
                vectors.extend(self.model.embed([item["content"] for item in items[start:start+16]]))
            return self.store.ingest(doc_id, filename, checksum, items, vectors)

    def ask(self, question):
        if not isinstance(question, str) or not question.strip() or len(question) > 2000:
            raise EngineError("invalid_question")
        with self.lock:
            self.store.check_identity(self.model.identity())
            vector = self.model.embed([question])[0]
            sources = select_sources(self.store.search(vector), question)
            if not sources:
                return {"answer": "证据不足：当前知识库中没有达到检索门槛的来源。", "sources": [], "grounded": False}
            answer = self.model.answer(question, sources)
            citations = set(re.findall(r"\[S(\d+)\]", answer))
            allowed = {str(i+1) for i in range(len(sources))}
            grounded = bool(citations) and citations <= allowed
            if not grounded:
                answer = "模型未提供有效的来源引用，请查看下方检索片段。"
            return {"answer": answer, "sources": sources, "grounded": grounded,
                    "note": "引用编号校验不等于事实正确性或逻辑蕴含证明。"}
