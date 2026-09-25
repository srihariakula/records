"""
Builds `Content-Disposition: attachment` headers from caller-supplied file
names (Factory/DownloadDocument's `fileName`, an uploaded document's name,
convert/to-pdf's upload filename).

Interpolating those raw into `filename="..."` let a `"` close the quoted
string and inject extra parameters, passed CR/LF straight into the header,
and 500'd on any non-Latin-1 character (HTTP headers are Latin-1 encoded).
Per RFC 6266 this emits an ASCII-only `filename=` fallback plus a
percent-encoded UTF-8 `filename*=` that modern browsers prefer, so a name
like "報告.pdf" still downloads under its real name.
"""
import re
import unicodedata
from urllib.parse import quote

_UNSAFE_ASCII_RE = re.compile(r"[^A-Za-z0-9._ ()+-]")


def _basename(filename: str) -> str:
    return filename.replace("\\", "/").rsplit("/", 1)[-1]


def attachment(filename: str, fallback: str = "download") -> str:
    name = _basename(filename)
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C").strip()  # drop CR/LF/controls
    if not name or name in (".", ".."):
        name = fallback

    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    ascii_name = _UNSAFE_ASCII_RE.sub("_", ascii_name).strip() or fallback

    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name, safe='')}"
