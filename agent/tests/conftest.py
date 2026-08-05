"""Test configuration.

The agent service validates its settings at startup and fails loudly on a
missing key, which is right for a service and wrong for a unit test. These
dummy values let the pure-logic modules import without an Azure account —
none of the tests here make a network call.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://example.services.ai.azure.com")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-key")
os.environ.setdefault("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-5-mini")
os.environ.setdefault("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
os.environ.setdefault("AZURE_SEARCH_ENDPOINT", "https://example.search.windows.net")
os.environ.setdefault("AZURE_SEARCH_API_KEY", "test-key")
