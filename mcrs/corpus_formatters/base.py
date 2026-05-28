def format_field_value(value) -> str:
    """Render a single track-metadata field value as a flat string.

    The dataset schema mixes `list[str]` fields (track_name, artist_name, ...)
    with scalar fields (release_date is `str`). Anywhere we render a field
    value into a human/LLM/BM25-facing string must go through this helper so
    a scalar str isn't accidentally character-tokenized via ", ".join("...").
    """
    if isinstance(value, list):
        return ", ".join(value)
    return str(value)


class DefaultFormatter:
    """Formats track metadata as `field: value\\n` lines (original behavior)."""

    name = "default"

    def format(self, metadata: dict, corpus_types: list[str]) -> str:
        parts = [
            f"{corpus_type}: {format_field_value(metadata[corpus_type])}"
            for corpus_type in corpus_types
        ]
        return "\n".join(parts) + "\n"
