# Verification record — 2026-10-20

## Completed

- **30 source tests passed** on Windows x64 / CPython 3.12.14, with the project
  and pinned pure-Python dependencies only (`python -S`).
- Real local TXT/MD/CSV text and DOCX XML parsing; PDF text extraction and page
  locator; empty/scanned PDF rejection; path/URL/type/encoding/size restrictions;
  XML entity and zip expansion guards; bounded child parser process.
- Character offsets and chunk overlap; finite vector shape and nonzero checks;
  local endpoint and DNS address policy; cloud/missing model rejection.
- Real localhost HTTP adapter requests against a fixture Ollama protocol server:
  no proxy use, no redirects, truncate=false, response shape checks and no pull API.
- Pipeline candidate budgets, no-evidence abstention, invented/missing citation
  rejection, embedding failure before persistence and model-identity mismatch.
- SQL parameterization through a recording connection; this does **not** replace
  a PostgreSQL transaction/pgvector integration test.
- HTTP access-token, Origin and Host checks; no token embedded in UI; bounded
  upload, local parser integration, no external frontend assets or innerHTML.
- Docker Compose configuration successfully validated by `docker compose config`.
- Browser workflow with fixture store/model: connect, real local file upload and
  child parser, document list, ask, source display. Fixture screenshot is labelled
  as such; its answer is not a live Ollama result.

## Package-level checks

RELEASE-INFO.json records the release metadata and the scope of what was
verified. Complete offline resource hashes, the Docker image archive, the frozen
Windows demo and ZIP manifest/CRC checks belong to the separately distributed
offline package; they are not part of this source repository. In that package
the EXE demo is explicitly labelled FIXTURE SELF-TEST and includes real PDF,
DOCX and UTF-8 parsing; its vector store and answer generator are deterministic
fixtures, not PostgreSQL/Ollama substitutes in the actual application.

## Not completed on the build machine

The sandbox cannot access the installed Docker Desktop Linux engine named pipe.
Therefore **docker load/start of the final image set, real pgvector queries,
actual Qwen model generation and runtime outbound-network denial were not
validated here**. Static archive/hash checks are not a substitute for these.

Run `check.bat` / `OfflineKnowledgeEngine.exe check` on the target machine before
using real documents, in addition to inspecting the returned source text and
checking host/network egress. This check uses only the bundled fictional policy.

No independent security audit, compliance certification, model accuracy
benchmark, load test, OCR test or Linux live-container soak test was performed.
The package is a POC candidate with these limits stated, not a production
readiness or absolute data-sovereignty certification.
