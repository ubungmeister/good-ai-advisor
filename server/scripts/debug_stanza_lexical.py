import stanza

from app.db.database import SessionLocal
from app.repositories.document_chunk_repository import (
    DocumentChunkRepository,
)


SEARCH_LIMIT = 200


# We keep only words that usually carry useful meaning
# for lexical retrieval.
#
# NOUN  -> zavazadlo, pas, protokol
# PROPN -> names / proper nouns
# VERB  -> poškodit, opravit, nahlásit
# ADJ   -> cestovní, policejní
# NUM   -> 6, 15, 8, etc.
KEEP_POS = {
    "NOUN",
    "PROPN",
    "VERB",
    "ADJ",
    "NUM",
}

NOISE_LEMMAS = {
    "být",
    "muset",
    "moci",

    "pojištění",
    "pojištěný",
    "pojišťovna",
    "pojistitel",

    "postupovat",
    "možný",
    "rámec",
}


TEST_CASES = [
    {
        "id": "baggage_theft_police_report",
        "expected_article": 37,
        "question": (
            "Musím krádež zavazadla v zahraničí "
            "nahlásit policii a doložit policejní protokol?"
        ),
    },
    {
        "id": "baggage_damage_repair",
        "expected_article": 38,
        "question": (
            "Jak pojišťovna postupuje, když se moje "
            "zavazadlo poškodí a je možné ho opravit?"
        ),
    },
    {
        "id": "baggage_passport_exclusion",
        "expected_article": 39,
        "question": (
            "Je cestovní pas pojištěný v rámci "
            "pojištění zavazadel?"
        ),
    },
]


def get_article_number(chunk) -> int | None:
    """
    Read article number from DocumentChunk.
    """

    article_number = getattr(
        chunk,
        "article_number",
        None,
    )

    if article_number is None:
        return None

    try:
        return int(article_number)

    except (TypeError, ValueError):
        return None


def find_article_rank(
    results,
    expected_article: int,
):
    """
    Find rank of expected article in retrieval results.
    """

    for rank, (
        chunk,
        score,
    ) in enumerate(
        results,
        start=1,
    ):
        article_number = get_article_number(
            chunk
        )

        if article_number == expected_article:
            return rank, score

    return None, None


def print_article_rank(
    label: str,
    results,
    expected_article: int,
):
    """
    Print article rank and score.
    """

    rank, score = find_article_rank(
        results=results,
        expected_article=expected_article,
    )

    if rank is None:
        print(
            f"{label}: "
            f"Article {expected_article} -> NOT FOUND"
        )

        return

    print(
        f"{label}: "
        f"Article {expected_article} "
        f"-> rank={rank}, "
        f"score={score:.4f}"
    )


def build_stanza_query(
    nlp,
    question: str,
) -> str:
    """
    Convert Czech natural-language question
    into a shorter lemmatized lexical query.

    Example idea:

    "zavazadlo poškodí a je možné ho opravit"

    could become:

    "zavazadlo poškodit možný opravit"
    """

    document = nlp(question)

    lemmas = []

    print()
    print("--- STANZA TOKENS ---")

    for sentence in document.sentences:

        for word in sentence.words:

            lemma = word.lemma or ""
            upos = word.upos or ""

            print(
                f"{word.text:20} "
                f"lemma={lemma:20} "
                f"pos={upos}"
            )

            # Ignore words such as:
            #
            # je
            # se
            # v
            # a
            # moje
            #
            # because they usually do not help
            # lexical retrieval.

            if upos not in KEEP_POS:
                continue

            if not lemma:
                continue

            normalized_lemma = (
                lemma
                .lower()
                .strip()
            )

            if normalized_lemma in NOISE_LEMMAS:
                continue

            if len(normalized_lemma) < 2:
                continue

            lemmas.append(
                normalized_lemma
            )

    # Remove duplicates but keep original order.
    #
    # Example:
    #
    # ["pas", "zavazadlo", "pas"]
    #
    # ->
    #
    # ["pas", "zavazadlo"]

    unique_lemmas = list(
        dict.fromkeys(
            lemmas
        )
    )

    lexical_query = " ".join(
        unique_lemmas
    )

    # Safety fallback:
    # if Stanza removed everything,
    # use original question.
    if not lexical_query:
        return question

    return lexical_query


def print_top_results(
    label: str,
    results,
    limit: int = 10,
):
    """
    Show which articles are ranked above
    our expected article.
    """

    print()
    print(
        f"--- {label} TOP {limit} ---"
    )

    for rank, (
        chunk,
        score,
    ) in enumerate(
        results[:limit],
        start=1,
    ):
        article_number = get_article_number(
            chunk
        )

        print(
            f"#{rank:02d} "
            f"Article {article_number} "
            f"score={score:.4f}"
        )


def main():

    print()
    print(
        "========================================"
    )
    print(
        "STANZA LEXICAL QUERY DEBUG"
    )
    print(
        "========================================"
    )

    # ------------------------------------------
    # Load Czech Stanza model ONCE.
    #
    # We do not want to initialize NLP model
    # separately for every question.
    # ------------------------------------------

    print()
    print("Loading Czech Stanza model...")

    nlp = stanza.Pipeline(
        lang="cs",
        processors="tokenize,pos,lemma",
        use_gpu=False,
        verbose=False,
    )

    print("Stanza model loaded.")

    repository = DocumentChunkRepository()

    db = SessionLocal()

    try:

        for case in TEST_CASES:

            question = case["question"]

            expected_article = (
                case["expected_article"]
            )

            print()
            print()
            print(
                "=" * 70
            )

            print(
                f"CASE: {case['id']}"
            )

            print(
                f"EXPECTED ARTICLE: "
                f"{expected_article}"
            )

            print()
            print(
                "ORIGINAL QUESTION:"
            )

            print(
                question
            )

            # ==========================================
            # Build Stanza lexical query
            # ==========================================

            stanza_query = (
                build_stanza_query(
                    nlp=nlp,
                    question=question,
                )
            )

            print()
            print(
                "STANZA LEXICAL QUERY:"
            )

            print(
                stanza_query
            )

            # ==========================================
            # Variant 1:
            # current lexical search using
            # full natural-language question
            # ==========================================

            original_results = list(
                repository.search_lexical(
                    db=db,
                    question=question,
                    limit=SEARCH_LIMIT,
                )
            )

            # ==========================================
            # Variant 2:
            # lexical search using Stanza query
            # ==========================================

            stanza_results = list(
                repository.search_lexical(
                    db=db,
                    question=stanza_query,
                    limit=SEARCH_LIMIT,
                )
            )

            # ==========================================
            # Compare expected article ranks
            # ==========================================

            print()
            print(
                "--- RANK COMPARISON ---"
            )

            print_article_rank(
                label="Original lexical",
                results=original_results,
                expected_article=expected_article,
            )

            print_article_rank(
                label="Stanza lexical",
                results=stanza_results,
                expected_article=expected_article,
            )

            # ==========================================
            # Optional:
            # show top results for both variants
            # ==========================================

            print_top_results(
                label="ORIGINAL",
                results=original_results,
                limit=10,
            )

            print_top_results(
                label="STANZA",
                results=stanza_results,
                limit=10,
            )

        print()
        print()
        print(
            "========================================"
        )
        print(
            "DEBUG FINISHED"
        )
        print(
            "========================================"
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()