"""Optional Umami Cloud analytics injection for HTML responses."""

from __future__ import annotations

import os
from html import escape


def umami_head_snippet() -> str:
    """Return a deferred Umami script tag when both env vars are set."""
    script_url = os.environ.get("UMAMI_SCRIPT_URL", "").strip()
    website_id = os.environ.get("UMAMI_WEBSITE_ID", "").strip()
    if not script_url or not website_id:
        return ""
    return (
        f'<script defer src="{escape(script_url, quote=True)}" '
        f'data-website-id="{escape(website_id, quote=True)}"></script>\n'
    )


def inject_before_head_close(html: str, snippet: str) -> str:
    """Insert ``snippet`` immediately before the first ``</head>``."""
    if not snippet:
        return html
    marker = "</head>"
    idx = html.lower().find(marker)
    if idx == -1:
        return html
    return html[:idx] + snippet + html[idx:]
