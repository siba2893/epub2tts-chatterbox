"""Shared pytest fixtures for the epub2tts_chatterbox test suite."""
import nltk
import pytest


@pytest.fixture(scope="session", autouse=True)
def _ensure_punkt():
    """Ensure NLTK punkt tokenizer data is available before any test runs."""
    for resource in ("tokenizers/punkt", "tokenizers/punkt_tab"):
        try:
            nltk.data.find(resource)
        except LookupError:
            nltk.download(resource.split("/", 1)[1], quiet=True)
