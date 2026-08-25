# AI Intelligence Hub

The first vertical slice ingests the [Hugging Face blog Atom feed](https://huggingface.co/blog/feed.xml), stores normalized entries in PostgreSQL, and exposes them via FastAPI.

## Run

Copy `.env.example` to `.env` in this same folder (the file name starts with a dot, so Finder hides it). Put your Gemini key in `.env`. Then:

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
- `POST /documents/{document_id}/fetch-content`: fetches one article page, stores its raw HTML in `article_html`, and extracts readable text into `article_text`.
- `POST /documents/{document_id}/analyze`: sends `article_text` to the configured model and stores a summary, context, topics, and importance score. Repeat calls for the same document and article text reuse Redis instead of calling the model again. PostgreSQL remains the source of truth.

Ingestion applies a small relevance filter before storing a document. It recognizes terms across models, agents, infrastructure, applications, and industry signals such as funding or revenue. Dated entries must be within the last 30 days, while entries without a publication date are allowed through. The project does not score traction because the Hugging Face feed does not provide that signal.

The project keeps both the original page in `article_html` and a cleaned version in `article_text`. The Hugging Face feed currently supplies metadata (title, URL, author, and publication time), so we do not add an unused summary field. The project currently uses `Base.metadata.create_all()` rather than migrations, so after this schema change a local database volume needs to be recreated before restarting the API.

Analysis uses the Gemini API with structured JSON. Copy `.env.example` to `.env`, set `GEMINI_API_KEY` there, and do not commit `.env`. The endpoint is manual, so no model request happens during startup or ingestion. Redis is a cache only: it has no volume, so a Redis restart just means the next analyze call pays for the model again and then refills the cache.
