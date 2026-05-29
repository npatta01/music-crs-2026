from .base import DefaultFormatter, format_field_value


def load_corpus_formatter(formatter_type: str):
    if formatter_type == "default":
        return DefaultFormatter()
    else:
        raise ValueError(f"Unsupported corpus formatter type: {formatter_type}")
