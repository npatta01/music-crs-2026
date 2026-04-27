from .base import PassthroughQU


def load_qu_module(qu_type: str):
    if qu_type == "passthrough":
        return PassthroughQU()
    else:
        raise ValueError(f"Unsupported QU type: {qu_type}")
