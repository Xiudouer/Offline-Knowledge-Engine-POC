"""Synthetic live-stack acceptance check. No knowledge content is printed or exported."""
import json
import subprocess
import urllib.request


def run(root):
    token = (root / "private-state/access-token.txt").read_text().strip()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(path, data=None, headers=None):
        req = urllib.request.Request("http://127.0.0.1:18787" + path, data=data,
            headers={"Authorization": "Bearer " + token, **(headers or {})})
        with opener.open(req, timeout=600) as response:
            return json.load(response)

    assert request("/api/status")["ready"]
    document = request("/api/ingest", (root / "examples/backup-policy.md").read_bytes(), {"X-Filename": "backup-policy.md"})
    answer = request("/api/ask", json.dumps({"question": "示例制度的备份周期和保留时间是什么？"}).encode(),
                     {"Content-Type": "application/json"})
    assert any(source["doc_id"] == document["id"] for source in answer["sources"])
    config = root / "private-state/compose.json"
    flags = subprocess.CREATE_NO_WINDOW if __import__("os").name == "nt" else 0

    def command(*args):
        return subprocess.check_output(["docker", *map(str, args)], text=True, creationflags=flags)

    def compose(*args):
        return command("compose", "-f", config, *args)

    probe = """import socket,sys
failed=[]
for host,port in [('1.1.1.1',443),('8.8.8.8',53)]:
 try:
  sock=socket.create_connection((host,port),timeout=2);sock.close();failed.append('egress_allowed')
 except OSError:pass
try:socket.getaddrinfo('example.com',443);failed.append('external_dns_resolved')
except OSError:pass
print('isolated' if not failed else ','.join(failed))
sys.exit(bool(failed))
"""
    assert compose("exec", "-T", "app", "python", "-c", probe).strip() == "isolated"
    containers = compose("ps", "-q").split()
    assert len(containers) == 3
    for container in containers:
        networks = json.loads(command("inspect", container))[0]["NetworkSettings"]["Networks"]
        assert len(networks) == 1
        for network in networks:
            assert json.loads(command("network", "inspect", network))[0]["Internal"] is True
    return {"synthetic_document_pgvector_ingest": "passed", "local_model_retrieval": "passed",
            "model_citation_guard_accepted": answer["grounded"], "app_external_tcp_and_dns_rejected": "passed",
            "all_services_internal_network_only": "passed",
            "note": "Citation validity alone is not a factual accuracy test."}
