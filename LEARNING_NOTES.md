# AI Intelligence Hub — Learning Notes

## Learning preference

This project is both a portfolio/resume project and a learning project. Explain the purpose behind each decision, connect commands to the system architecture, and use small verification steps. Avoid generating unexplained code or adding infrastructure before it is needed.

## Progress so far

1. The project started empty, so we created a minimal Python/FastAPI service with PostgreSQL in Docker.
2. We chose the Hugging Face Blog Atom feed as the first real source. A feed gives structured entries (title, URL, author, publication time, and content) without scraping HTML.
3. The `Source` table stores where data comes from. The `Document` table stores normalized items from that source. The relationship is one source to many documents.
4. The API creates the tables and seeds the first source when it starts.
5. Docker Compose runs two containers: PostgreSQL (`db`) and FastAPI (`api`). The API connects to PostgreSQL using the service name `db`, not `localhost`.
6. `GET /health` checks that FastAPI is alive. `GET /sources` confirmed that FastAPI could read PostgreSQL and that the initial source exists.
7. `GET /documents` returned `[]` because ingestion had not run yet. The next command is `POST /sources/1/fetch`, which fetches the Atom feed, normalizes entries, and inserts or updates documents by URL.

## Next lesson

Trigger ingestion, inspect the response counters (`fetched`, `created`, `updated`), then query `/documents`. After that, inspect one document and trace it through: feed entry → normalized Python values → SQLAlchemy model → PostgreSQL row → JSON API response.

## Prototype completion updates

- Added `GET /documents/{document_id}` with a clear 404 response for missing records.
- Added ingestion logging with fetched/created/updated counters.
- Added unit tests for feed content fallback and publication-date parsing.
- Full article-body fetching remains the next ingestion enhancement because the feed currently provides metadata but not `content` for these entries.
