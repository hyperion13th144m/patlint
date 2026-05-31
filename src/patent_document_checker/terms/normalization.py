from __future__ import annotations

import re
import unicodedata

DASH_CHARS = "‐‑‒–—―−－～〜~"
DASH_TRANSLATION = str.maketrans({char: "-" for char in DASH_CHARS})


def normalize_term_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.translate(DASH_TRANSLATION).replace("’", "'")
    return re.sub(r"\s+", "", normalized)
