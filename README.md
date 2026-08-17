# AI Intelligence Hub

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

- `GET /health`: confirms the service is running.
- `GET /sources`: lists registered sources.
- `POST /sources/{source_id}/fetch`: synchronously fetches and stores the source feed.
- `GET /documents?limit=20&offset=0`: returns newest stored documents.
- `GET /documents/{document_id}`: returns one stored document.
- `POST /documents/{document_id}/fetch-content`: fetches one article page and stores its raw HTML in `article_html`.

Ingestion applies a small relevance filter before storing a document: the title must contain an AI-related keyword, and dated entries must be within the last 30 days. Entries without a publication date are allowed through. The project does not score traction because the Hugging Face feed does not provide that signal.

The project stores the article page separately in `article_html`. The Hugging Face feed currently supplies metadata (title, URL, author, and publication time), so we do not add an unused summary field. The project currently uses `Base.metadata.create_all()` rather than migrations, so after this schema change a local database volume needs to be recreated before restarting the API.
