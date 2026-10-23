import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
import mcp_server as server


class OcrMcpTests(unittest.TestCase):
    def test_image_calls_existing_pipeline_and_returns_unicode(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.png"
            Image.new("RGB", (10, 10)).save(path)
            with patch.object(server, "_require_credentials"), patch.object(server, "_pipeline") as pipeline:
                pipeline.return_value.process_page.return_value = (1, "한글 OCR 결과")
                result = server.ocr_image(str(path))
                self.assertEqual(result["text"], "한글 OCR 결과")
                pipeline.return_value.process_page.assert_called_once()

    def test_invalid_pdf_pages_do_not_call_pipeline(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.pdf"
            path.write_bytes(b"%PDF-1.4")
            with patch.object(server, "_pipeline") as pipeline:
                for pages in ([], [0], [1, 1], list(range(1, 12))):
                    with self.assertRaises(ValueError):
                        server.ocr_pdf_pages(str(path), pages)
                pipeline.assert_not_called()

    def test_pdf_pages_preserve_page_ids_and_validate_before_cloud(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.pdf"
            path.write_bytes(b"%PDF-1.4")
            with patch("pdf2image.pdfinfo_from_path", return_value={"Pages": 3}), patch("pdf2image.convert_from_path") as render, patch.object(server, "_require_credentials"), patch.object(server, "_pipeline") as pipeline:
                render.side_effect = lambda *args, **kwargs: [Image.new("RGB", (10, 10))]
                pipeline.return_value.process_page.side_effect = lambda image, page: (page, str(page))
                result = server.ocr_pdf_pages(str(path), [3, 1])
                self.assertEqual(result["pages"], [{"page": 3, "text": "3"}, {"page": 1, "text": "1"}])
                with self.assertRaises(ValueError):
                    server.ocr_pdf_pages(str(path), [4])
                self.assertEqual(pipeline.return_value.process_page.call_count, 2)

    def test_pipeline_error_is_not_returned_as_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.png"
            Image.new("RGB", (10, 10)).save(path)
            with patch.object(server, "_require_credentials"), patch.object(server, "_pipeline") as pipeline:
                pipeline.return_value.process_page.side_effect = RuntimeError("OCR failed")
                with self.assertRaisesRegex(RuntimeError, "OCR failed"):
                    server.ocr_image(str(path))


if __name__ == "__main__":
    unittest.main()
