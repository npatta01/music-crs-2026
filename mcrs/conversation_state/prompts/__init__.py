"""Versioned ConversationState extractor prompts.

`current` is the production prompt. `previous` is kept as the single reference
prompt for comparison and rollback.
"""

from mcrs.conversation_state.prompts import current, previous

__all__ = ["current", "previous"]
