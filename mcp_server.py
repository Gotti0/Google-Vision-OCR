"""Text-only MCP access to the existing Google Cloud Vision OCR pipeline."""
from __future__ import annotations

import contextlib
import os
from pathlib import Path
import shutil
import sys

from mcp.server.fastmcp import FastMCP

ROOT = Path(__file__).resolve().parent
mcp = FastMCP(
    "google-vision-ocr",
    instructions=(
        "Use the user's existing OCR pipeline. OCR sends selected pages/images to "
        "Google Cloud Vision and may incur charges. Results are text only, never "
        "images for a multimodal model. Use ocr_status before processing. "
        "PDF pages are explicit, 1-based, at most 10 per call."
    ),
)


def _input_file(value: str, suffixes: set[str]) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError("Provide an absolute input path")
    path = path.resolve(strict=True)
    if not path.is_file() or path.suffix.lower() not in suffixes:
        raise ValueError("Unsupported input file")
    return path


def _pipeline():
    # 기존 모듈의 출력이 stdio MCP 프로토콜을 오염시키지 않게 한다.
    with contextlib.redirect_stdout(sys.stderr):
        import ocr_service
    return ocr_service


def _require_credentials() -> None:
    value = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not value or not Path(value).is_file():
        raise ValueError("Configure GOOGLE_APPLICATION_CREDENTIALS with a local key file")


@mcp.tool()
def ocr_status() -> dict:
    """Check local dependencies and credential-file presence; no paid API call."""
    _pipeline()
    value = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    return {
        "pipeline": "Google-Vision-OCR/ocr_service.py",
        "credentials_file_present": bool(value and Path(value).is_file()),
        "pdfinfo_available": bool(shutil.which("pdfinfo")),
        "pdftoppm_available": bool(shutil.which("pdftoppm")),
        "max_pages_per_call": 10,
        "cloud_authentication_tested": False,
        "output": "text_only",
    }


@mcp.tool()
def ocr_pdf_pages(input_path: str, pages: list[int], dpi: int = 200) -> dict:
    """OCR selected 1-based PDF pages via the user's pipeline (paid cloud API)."""
    path = _input_file(input_path, {".pdf"})
    if (not pages or len(pages) > 10 or len(set(pages)) != len(pages)
            or any(type(page) is not int or page < 1 for page in pages)):
        raise ValueError("Specify 1 to 10 unique positive integer page numbers")
    if not 72 <= dpi <= 300:
        raise ValueError("dpi must be between 72 and 300")
    from pdf2image import convert_from_path, pdfinfo_from_path

    count = int(pdfinfo_from_path(str(path), timeout=30)["Pages"])
    if any(page > count for page in pages):
        raise ValueError(f"Page exceeds PDF page count ({count})")
    _require_credentials()
    pipeline = _pipeline()
    results = []
    for page in pages:
        images = convert_from_path(
            str(path), dpi=dpi, first_page=page, last_page=page, timeout=60
        )
        try:
            if len(images) != 1:
                raise ValueError("Expected exactly one rendered PDF page")
            with contextlib.redirect_stdout(sys.stderr):
                _, text = pipeline.process_page(images[0], page)
            results.append({"page": page, "text": text})
        finally:
            for image in images:
                image.close()
    return {"input_path": str(path), "page_count": count, "pages": results}


@mcp.tool()
def ocr_image(input_path: str) -> dict:
    """OCR one local image via the existing preprocessing and cloud OCR pipeline."""
    path = _input_file(input_path, {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"})
    _require_credentials()
    from PIL import Image

    with Image.open(path) as source:
        if getattr(source, "n_frames", 1) != 1:
            raise ValueError("Multi-frame images are unsupported; provide one frame")
        with source.convert("RGB") as rgb:
            with contextlib.redirect_stdout(sys.stderr):
                _, text = _pipeline().process_page(rgb, 1)
    return {"input_path": str(path), "text": text}


if __name__ == "__main__":
    os.chdir(ROOT)
    if os.environ.get("OCR_POPPLER_BIN"):
        os.environ["PATH"] = os.environ["OCR_POPPLER_BIN"] + os.pathsep + os.environ.get("PATH", "")
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    _pipeline()
    mcp.run(transport="stdio")
