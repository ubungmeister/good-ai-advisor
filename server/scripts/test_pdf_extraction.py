from app.services.pdf_text_extractor import PdfTextExtractor


def main():
    extractor = PdfTextExtractor()

    pages = extractor.extract(
        "data/knowledge/travel_insurance_vpp.pdf"
    )

    print(f"Extracted pages: {len(pages)}")

    for page in pages[:2]:
        print("\n" + "=" * 80)
        print(f"PAGE {page.page_number}")
        print("=" * 80)
        print(page.text[:2000])


if __name__ == "__main__":
    main()