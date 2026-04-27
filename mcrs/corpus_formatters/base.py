class DefaultFormatter:
    """Formats track metadata as `field: value\\n` lines (original behavior)."""

    name = "default"

    def format(self, metadata: dict, corpus_types: list[str]) -> str:
        parts = []
        for corpus_type in corpus_types:
            entity = metadata[corpus_type]
            if isinstance(entity, list):
                entity = ", ".join(entity)
            parts.append(f"{corpus_type}: {entity}")
        return "\n".join(parts) + "\n"
