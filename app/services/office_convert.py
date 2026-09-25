"""
Office-document -> PDF conversion.

LEADTOOLS uses its own DocumentConverter engine (DocumentFactory.loadFromStream +
DocumentConverter), which is closed-source and license-gated. The realistic open-source
equivalent for turning arbitrary office documents (docx, xlsx, pptx, rtf, odt, ...) into
PDF is LibreOffice running headless -- the same approach tools like Gotenberg use. It is
an external binary, not a pip package, so it must be installed separately:

    macOS:  brew install --cask libreoffice
    Debian: apt-get install libreoffice
"""
import shutil
import subprocess
import tempfile
from pathlib import Path

from app.services.errors import ConversionError

SOFFICE_TIMEOUT_SECONDS = 120


def _find_soffice() -> str:
    for candidate in ("soffice", "libreoffice"):
        path = shutil.which(candidate)
        if path:
            return path
    mac_path = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    if Path(mac_path).exists():
        return mac_path
    raise ConversionError(
        "LibreOffice is not installed or not on PATH. Install it (e.g. "
        "`brew install --cask libreoffice` on macOS) to enable document-to-PDF conversion."
    )


def convert_bytes_to_pdf(source_bytes: bytes, source_filename: str) -> bytes:
    """Convert an in-memory office document to PDF bytes via headless LibreOffice."""
    soffice = _find_soffice()
    suffix = Path(source_filename).suffix or ".docx"

    with tempfile.TemporaryDirectory() as tmp_dir:
        input_path = Path(tmp_dir) / f"input{suffix}"
        input_path.write_bytes(source_bytes)

        try:
            result = subprocess.run(
                [soffice, "--headless", "--norestore", "--convert-to", "pdf",
                 "--outdir", tmp_dir, str(input_path)],
                capture_output=True,
                timeout=SOFFICE_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ConversionError(
                f"PDF can not be generated: LibreOffice timed out after {SOFFICE_TIMEOUT_SECONDS}s converting {source_filename}"
            ) from exc
        output_path = input_path.with_suffix(".pdf")
        if result.returncode != 0 or not output_path.exists():
            raise ConversionError(f"PDF can not be generated: {_failure_reason(result, suffix)}")
        return output_path.read_bytes()


# LibreOffice ships per-application packages; a missing one makes every file
# of that kind fail with the same unhelpful "source file could not be loaded".
_COMPONENT_FOR_SUFFIX = {
    **dict.fromkeys([".xls", ".xlsx", ".xlsm", ".ods", ".csv", ".tsv"], "libreoffice-calc"),
    **dict.fromkeys([".ppt", ".pptx", ".pps", ".ppsx", ".odp", ".key"], "libreoffice-impress"),
    **dict.fromkeys([".svg", ".vsd", ".vsdx", ".odg", ".cdr", ".wmf", ".emf", ".eps"], "libreoffice-draw"),
}


def _failure_reason(result: "subprocess.CompletedProcess", suffix: str) -> str:
    output = (result.stderr + result.stdout).decode(errors="replace")
    lines = [l.strip() for l in output.splitlines() if l.strip() and "javaldx" not in l]  # javaldx warning is noise
    detail = "; ".join(lines) or "unknown LibreOffice error"
    if "could not be loaded" in detail:
        component = _COMPONENT_FOR_SUFFIX.get(suffix.lower(), "libreoffice-writer")
        detail = (f"LibreOffice could not open this {suffix or 'extension-less'} file -- either the format is not "
                  f"supported or the {component} component is not installed")
    return detail


def convert_path_to_pdf(docx_path: str, pdf_file_name: str) -> str:
    """Convert a file already on disk to PDF, writing the result alongside it.

    Mirrors DocumentConverterHelper.convertDocxToPdf(DocumentConverterRequest): the
    input path is server-local (this is a lift of the original file-path-based API,
    not something to expose to untrusted clients without path validation).
    """
    source = Path(docx_path)
    if not source.is_file():
        raise ConversionError(f"PDF can not be generated: source file not found: {docx_path}")

    pdf_bytes = convert_bytes_to_pdf(source.read_bytes(), source.name)
    dest = source.parent / pdf_file_name
    dest.write_bytes(pdf_bytes)
    return str(dest)
