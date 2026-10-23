"""Parameterised pgvector storage; embedding identity is part of the index contract."""
import json
from contextlib import contextmanager

from .net import EngineError, private_address, validate_vector


def literal(vector, dimensions):
    return "[" + ",".join(format(x, ".9g") for x in validate_vector(vector, dimensions)) + "]"


class Store:
    def __init__(self, *, host="db", port=5432, dbname="offlineknowledge", user="oke", password,
                 dimensions=1024, connect=None):
        self.options = dict(host=host, port=port, dbname=dbname, user=user, password=password)
        self.dimensions, self.connect_override = dimensions, connect
        if type(dimensions) is not int or not 8 <= dimensions <= 2000:
            raise EngineError("unsupported_embedding_dimensions")

    @contextmanager
    def connection(self):
        if self.connect_override:
            with self.connect_override() as tx:
                yield tx
            return
        import psycopg
        address = private_address(self.options["host"], self.options["port"])
        try:
            with psycopg.connect(**self.options, hostaddr=address, connect_timeout=5,
                                options="-c search_path=oke,public -c statement_timeout=30000") as tx:
                yield tx
        except EngineError:
            raise
        except Exception:
            raise EngineError("local_database_unavailable", 503) from None

    def initialize(self, identity):
        with self.connection() as tx:
            extension = tx.execute("SELECT extversion FROM pg_extension WHERE extname='vector'").fetchone()
            if not extension:
                raise EngineError("pgvector_extension_missing", 503)
            tx.execute("CREATE TABLE IF NOT EXISTS oke.settings (key text PRIMARY KEY, value jsonb NOT NULL)")
            tx.execute("INSERT INTO oke.settings VALUES ('embedding',%s::jsonb) ON CONFLICT DO NOTHING", (json.dumps(identity),))
            previous = tx.execute("SELECT value FROM oke.settings WHERE key='embedding'").fetchone()[0]
            if previous != identity:
                raise EngineError("embedding_model_changed_reindex_required", 409)
            tx.execute("CREATE TABLE IF NOT EXISTS oke.documents (id text PRIMARY KEY, filename text NOT NULL, checksum text NOT NULL, created_at timestamptz DEFAULT now())")
            # Only validated integer configuration enters DDL; never request input.
            tx.execute(f"CREATE TABLE IF NOT EXISTS oke.chunks (doc_id text REFERENCES oke.documents(id) ON DELETE CASCADE, ordinal integer, content text NOT NULL, locator jsonb NOT NULL, embedding vector({self.dimensions}) NOT NULL, PRIMARY KEY(doc_id,ordinal))")
            tx.execute("CREATE INDEX IF NOT EXISTS oke_chunks_embedding_idx ON oke.chunks USING hnsw (embedding vector_cosine_ops)")
        return {"pgvector": extension[0]}

    def check_identity(self, identity):
        with self.connection() as tx:
            row = tx.execute("SELECT value FROM oke.settings WHERE key='embedding'").fetchone()
            if not row or row[0] != identity:
                raise EngineError("embedding_model_changed_reindex_required", 409)

    def ingest(self, doc_id, filename, checksum, items, vectors):
        if len(items) != len(vectors):
            raise EngineError("embedding_count_invalid", 503)
        with self.connection() as tx:
            # Serialise same-document replacement; a failed transaction leaves the old document intact.
            tx.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (doc_id,))
            old = tx.execute("SELECT id FROM oke.documents WHERE id=%s", (doc_id,)).fetchone()
            if old:
                return {"id": doc_id, "chunks": tx.execute("SELECT count(*) FROM oke.chunks WHERE doc_id=%s", (doc_id,)).fetchone()[0], "duplicate": True}
            count = tx.execute("SELECT count(*) FROM oke.chunks").fetchone()[0]
            if count + len(items) > 20000:
                raise EngineError("poc_chunk_capacity_reached", 409)
            tx.execute("INSERT INTO oke.documents(id,filename,checksum) VALUES(%s,%s,%s)", (doc_id, filename, checksum))
            for index, (item, vector) in enumerate(zip(items, vectors)):
                tx.execute("INSERT INTO oke.chunks VALUES (%s,%s,%s,%s::jsonb,%s::vector)",
                           (doc_id, index, item["content"], json.dumps(item["locator"]), literal(vector, self.dimensions)))
        return {"id": doc_id, "chunks": len(items), "duplicate": False}

    def search(self, vector, limit=12):
        with self.connection() as tx:
            rows = tx.execute("SELECT d.id,d.filename,c.ordinal,c.content,c.locator,1-(c.embedding <=> %s::vector) AS score "
                "FROM oke.chunks c JOIN oke.documents d ON d.id=c.doc_id ORDER BY c.embedding <=> %s::vector LIMIT %s",
                (literal(vector, self.dimensions), literal(vector, self.dimensions), limit)).fetchall()
        return [{"doc_id": r[0], "filename": r[1], "ordinal": r[2], "content": r[3], "locator": r[4], "score": float(r[5])} for r in rows]

    def documents(self):
        with self.connection() as tx:
            rows = tx.execute("SELECT d.id,d.filename,count(c.ordinal) FROM oke.documents d LEFT JOIN oke.chunks c ON d.id=c.doc_id GROUP BY d.id ORDER BY d.created_at DESC LIMIT 200").fetchall()
        return [{"id": r[0], "filename": r[1], "chunks": r[2]} for r in rows]

    def delete(self, doc_id):
        if not isinstance(doc_id, str) or len(doc_id) != 64 or any(c not in "0123456789abcdef" for c in doc_id):
            raise EngineError("invalid_document_id")
        with self.connection() as tx:
            tx.execute("DELETE FROM oke.documents WHERE id=%s", (doc_id,))
        return {"deleted": True}
