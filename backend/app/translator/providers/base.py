from abc import ABC, abstractmethod
from typing import Dict, Optional


class BaseTranslationProvider(ABC):
    """Abstract interface for translation providers."""

    name: str = "base"

    @abstractmethod
    async def translate(
        self,
        text: str,
        source_language: str = "auto",
        target_language: str = "vi",
        glossary: Optional[Dict[str, str]] = None,
        context_hint: Optional[str] = "",
    ) -> str:
        """
        Translates text to target language with glossary and preceding context.
        Raises an exception if translation fails.
        """
        pass
