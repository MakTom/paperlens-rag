"""Small contract that today's Ollama client already satisfies."""
from typing import Protocol


class TextGenerator(Protocol):
    def generate(self, prompt: str, *, system: str | None = None) -> str:
        """Return generated text, or raise a service error."""
        ...
