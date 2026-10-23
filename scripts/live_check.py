"""Run after start.bat: synthetic live pgvector/Ollama test and container egress checks."""
import json
from pathlib import Path
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
token = (ROOT / "private-state/access-token.txt").read_text().strip()
base = "http://127.0.0.1:18787"
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def request(path, data=None, headers=None):
    req = urllib.request.Request(base + path, data=data, headers={
        "Authorization": "Bearer " + token, **(headers or {})})
    with opener.open(req, timeout=600) as response:
        return json.load(response)


status = request("/api/status")
assert status["ready"]
data = (ROOT / "examples/backup-policy.md").read_bytes()
document = request("/api/ingest", data, {"X-Filename": "backup-policy.md"})
result = request("/api/ask", json.dumps({"question": "示例制度的备份周期和保留时间是什么？"}).encode(),
                 {"Content-Type": "application/json"})
assert result["sources"]
assert any(source["doc_id"] == document["id"] for source in result["sources"])
config = ROOT / "private-state/compose.json"


def docker(*args):
    return subprocess.check_output(["docker", "compose", "-f", str(config), *args], text=True)


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
assert docker("exec", "-T", "app", "python", "-c", probe).strip() == "isolated"
ids = docker("ps", "-q").split()
assert len(ids) == 3
for container in ids:
    inspect = json.loads(subprocess.check_output(["docker", "inspect", container], text=True))[0]
    networks = inspect["NetworkSettings"]["Networks"]
    assert len(networks) == 1
    for network in networks:
        info = json.loads(subprocess.check_output(["docker", "network", "inspect", network], text=True))[0]
        assert info["Internal"] is True
report = {"live_status": "passed", "synthetic_document_pgvector_ingest": "passed",
          "ollama_retrieval": "passed", "model_citation_guard_accepted": result["grounded"],
          "app_external_tcp_and_dns_rejected": "passed", "all_services_internal_network_only": "passed"}
print(json.dumps(report, indent=2))
if not result["grounded"]:
    print("Model did not produce valid citations; retrieved evidence is available but generation quality needs review.")
