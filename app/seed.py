from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Source


INITIAL_SOURCE = {
    "name": "Hugging Face Blog",
    "type": "atom",
    "base_url": "https://huggingface.co/blog/feed.xml",
}


def ensure_initial_source(session: Session) -> None:
    existing = session.scalar(select(Source).where(Source.name == INITIAL_SOURCE["name"]))
    if existing is None:
        session.add(Source(**INITIAL_SOURCE))
        session.commit()
