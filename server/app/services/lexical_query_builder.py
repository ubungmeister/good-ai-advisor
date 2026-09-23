import stanza


class LexicalQueryBuilder:
    """
    Prepares a focused Czech query for lexical search.

    Pipeline:
    question
        -> Stanza
        -> lemma + POS filtering
        -> noise filtering
        -> synonym expansion
        -> lexical query
    """

    KEEP_POS = {
        "NOUN",
        "PROPN",
        "VERB",
        "ADJ",
        "NUM",
    }

    NOISE_LEMMAS = {
        # Generic/modal verbs
        "být",
        "muset",
        "moci",

        # Generic insurance vocabulary
        "pojištění",
        "pojištěný",
        "pojištěná",
        "pojištěné",
        "pojišťovna",
        "pojistitel",

        # Generic structural words
        "postupovat",
        "možný",
        "rámec",
    }

    # Domain lexical expansion.
    #
    # User and insurance document may describe
    # the same thing using different words.
    #
    # Example:
    # user:     nahlásit policii
    # document: oznámit policejnímu orgánu
    SYNONYMS = {
        "nahlásit": [
            "oznámit",
        ],
        "doložit": [
            "předložit",
        ],
        "protokol": [
            "dokument",
        ],
    }

    def __init__(self):
        self.nlp = stanza.Pipeline(
            lang="cs",
            processors="tokenize,pos,lemma",
            use_gpu=False,
            verbose=False,
        )

    def build(
        self,
        question: str,
    ) -> str:

        document = self.nlp(question)

        terms = []

        for sentence in document.sentences:
            for word in sentence.words:

                if word.upos not in self.KEEP_POS:
                    continue

                if not word.lemma:
                    continue

                lemma = (
                    word.lemma
                    .lower()
                    .strip()
                )

                if lemma in self.NOISE_LEMMAS:
                    continue

                if len(lemma) < 2:
                    continue

                # Keep original lemma.
                terms.append(
                    lemma
                )

                # Add known domain synonyms.
                synonyms = self.SYNONYMS.get(
                    lemma,
                    [],
                )

                terms.extend(
                    synonyms
                )

        # Remove duplicates,
        # but preserve original order.
        unique_terms = list(
            dict.fromkeys(
                terms
            )
        )

        lexical_query = " ".join(
            unique_terms
        )

        if not lexical_query:
            return question.strip()

        return lexical_query