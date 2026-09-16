"""
PdfTextExtractor reads a PDF file
and returns text from each page.
"""

from dataclasses import dataclass

from pypdf import PdfReader


@dataclass
class ExtractedPage:
    page_number: int
    text: str


class PdfTextExtractor:

    def extract(self, file_path: str) -> list[ExtractedPage]:
        reader = PdfReader(file_path)

        pages: list[ExtractedPage] = []

        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text()

            if not text:
                continue

            pages.append(
                ExtractedPage(
                    page_number=index,
                    text=text,
                )
            )

        return pages