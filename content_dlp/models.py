from dataclasses import dataclass, field, asdict
import json


@dataclass
class ContentMetadata:
    content_id: str
    source_type: str
    url: str
    title: str
    description: str | None = None
    author: str | None = None
    published_date: str | None = None
    duration_seconds: int | None = None
    tags: list[str] = field(default_factory=list)
    thumbnail_url: str | None = None
    fetched_at: str = ""
    extras: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)
