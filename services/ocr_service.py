"""
OCR Service (Mock)

Reads text from images (JPG, PNG) and scanned PDFs using an OCR backend.
Currently uses a **mock API** — swap in the real model/endpoint later.

When ready to integrate a real OCR model, replace ``_call_ocr_api`` with
the actual HTTP call or local inference.
"""

import asyncio
import logging
import base64
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Supported image extensions
SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
SUPPORTED_DOC_EXTS = {".pdf"}
SUPPORTED_EXTS = SUPPORTED_IMAGE_EXTS | SUPPORTED_DOC_EXTS

# Default output directory for OCR results
OCR_OUTPUT_DIR = Path("data/ocr_results")


class OCRServiceError(Exception):
    """OCR Service related errors."""
    pass


class OCRService:
    """
    Mock OCR Service.

    Public async API:
      - ``ocr_file(file_path)`` → extract text from a single file
      - ``ocr_batch(file_paths)`` → batch extraction
      - ``get_result(result_id)`` → retrieve a cached result

    Results are cached in-memory and optionally saved to disk.
    """

    _instance: Optional["OCRService"] = None

    def __new__(cls) -> "OCRService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._results: Dict[str, Dict[str, Any]] = {}
        # Replace with a real URL when the model is ready
        self._api_url = os.getenv("OCR_API_URL", "")
        self._api_key = os.getenv("OCR_API_KEY", "")
        OCR_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self._initialized = True
        logger.info("OCRService initialized (mock mode)" if not self._api_url else
                     f"OCRService initialized – API: {self._api_url}")

    # -------------------------------------------------------- #
    # Public API
    # -------------------------------------------------------- #

    async def ocr_file(self, file_path: str, save_result: bool = True) -> Dict[str, Any]:
        """
        Run OCR on a single file (image or PDF).

        Returns:
            {
                "result_id": str,
                "file": str,
                "text": str,
                "confidence": float,
                "pages": int,
                "mock": bool,
                "timestamp": str,
            }
        """
        path = Path(file_path)
        if not path.exists():
            raise OCRServiceError(f"File not found: {file_path}")

        ext = path.suffix.lower()
        if ext not in SUPPORTED_EXTS:
            raise OCRServiceError(
                f"Unsupported file type: {ext}. "
                f"Supported: {', '.join(sorted(SUPPORTED_EXTS))}"
            )

        # Read file bytes
        loop = asyncio.get_event_loop()
        file_bytes = await loop.run_in_executor(None, path.read_bytes)

        # Call the OCR backend (mock or real)
        ocr_result = await self._call_ocr_api(file_bytes, ext, path.name)

        result_id = str(uuid.uuid4())[:8]
        result = {
            "result_id": result_id,
            "file": str(path.resolve()),
            "filename": path.name,
            "text": ocr_result["text"],
            "confidence": ocr_result["confidence"],
            "pages": ocr_result["pages"],
            "mock": ocr_result["mock"],
            "timestamp": datetime.now().isoformat(),
        }

        self._results[result_id] = result

        if save_result:
            await self._save_result(result_id, result)

        logger.info(f"OCR completed: {path.name} → {len(result['text'])} chars (id={result_id})")
        return result

    async def ocr_batch(self, file_paths: List[str], save_results: bool = True) -> Dict[str, Any]:
        """Run OCR on multiple files."""
        results = []
        errors = []
        for fp in file_paths:
            try:
                r = await self.ocr_file(fp, save_result=save_results)
                results.append(r)
            except Exception as e:
                errors.append({"file": fp, "error": str(e)})
        return {"results": results, "errors": errors, "total": len(results)}

    async def get_result(self, result_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a cached OCR result by ID."""
        return self._results.get(result_id)

    async def list_results(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List recent OCR results."""
        items = list(self._results.values())
        items.sort(key=lambda x: x["timestamp"], reverse=True)
        return items[:limit]

    # -------------------------------------------------------- #
    # OCR backend (mock / real)
    # -------------------------------------------------------- #

    async def _call_ocr_api(
        self, file_bytes: bytes, ext: str, filename: str
    ) -> Dict[str, Any]:
        """
        Call the OCR backend.

        If ``OCR_API_URL`` is configured → POST to the real API.
        Otherwise → return mock data.
        """
        if self._api_url:
            return await self._call_real_api(file_bytes, ext, filename)

        # ---------- MOCK MODE ----------
        return self._mock_ocr(file_bytes, ext, filename)

    async def _call_real_api(
        self, file_bytes: bytes, ext: str, filename: str
    ) -> Dict[str, Any]:
        """
        POST to a real OCR API.

        Expected API contract (customise to your model):
            POST /ocr
            Content-Type: multipart/form-data
            Body: file=<bytes>
            Response JSON: {"text": str, "confidence": float, "pages": int}
        """
        try:
            import aiohttp
            b64 = base64.b64encode(file_bytes).decode()
            payload = {
                "file": b64,
                "filename": filename,
                "format": ext.lstrip("."),
            }
            headers = {}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._api_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        raise OCRServiceError(f"OCR API error {resp.status}: {body}")
                    data = await resp.json()
                    return {
                        "text": data.get("text", ""),
                        "confidence": data.get("confidence", 0.0),
                        "pages": data.get("pages", 1),
                        "mock": False,
                    }
        except ImportError:
            logger.warning("aiohttp not installed – falling back to mock OCR")
            return self._mock_ocr(file_bytes, ext, filename)
        except Exception as e:
            logger.error(f"Real OCR API call failed: {e}")
            raise OCRServiceError(f"OCR API call failed: {e}")

    @staticmethod
    def _mock_ocr(file_bytes: bytes, ext: str, filename: str) -> Dict[str, Any]:
        """
        Return realistic-looking mock OCR output.

        Replace this entire method body when integrating a real model.
        """
        size_kb = len(file_bytes) / 1024
        is_pdf = ext in SUPPORTED_DOC_EXTS
        pages = max(1, int(size_kb / 50)) if is_pdf else 1

        mock_text_lines = [
            f"[OCR Mock Result for: {filename}]",
            f"File size: {size_kb:.1f} KB | Pages: {pages}",
            "",
            "--- Extracted Text (mock) ---",
            "Invoice No: INV-2024-00123",
            "Date: 2024-01-15",
            "Company: Acme Trading Ltd.",
            "",
            "Item          Qty   Unit Price   Amount",
            "Widget A       10     $50.00     $500.00",
            "Widget B        5    $120.00     $600.00",
            "Service Fee     1    $200.00     $200.00",
            "",
            "Subtotal:  $1,300.00",
            "Tax (10%):   $130.00",
            "Total:     $1,430.00",
            "",
            "Payment Terms: Net 30",
            "--- End of OCR Mock ---",
        ]

        return {
            "text": "\n".join(mock_text_lines),
            "confidence": 0.95,
            "pages": pages,
            "mock": True,
        }

    # -------------------------------------------------------- #
    # Persistence helpers
    # -------------------------------------------------------- #

    async def _save_result(self, result_id: str, result: Dict[str, Any]) -> None:
        import json
        loop = asyncio.get_event_loop()
        out_path = OCR_OUTPUT_DIR / f"{result_id}.json"
        await loop.run_in_executor(
            None,
            lambda: out_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8"),
        )
