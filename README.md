# AI Intelligence Hub — Prototype

The first vertical slice ingests the [Hugging Face blog Atom feed](https://huggingface.co/blog/feed.xml), stores normalized entries in PostgreSQL, and exposes them via FastAPI.

## Run

```bash
docker compose up --build
```

The source is created automatically on startup. Fetch it with:

```bash
curl -X POST http://localhost:8000/sources/1/fetch
curl http://localhost:8000/documents
```

Repeat the fetch safely: documents are upserted using their URL rather than duplicated.

## API

- `GET /health` — confirms the service is running.
- `GET /sources` — lists registered sources.
- `POST /sources/{source_id}/fetch` — synchronously fetches and stores the source feed.
- `GET /documents?limit=20&offset=0` — returns newest stored documents.
- `GET /documents/{document_id}` — returns one stored document.

This prototype intentionally has no scheduler, queue, LLM processing, or frontend. A later scheduler can call the existing fetch endpoint or service function without changing the data model.
