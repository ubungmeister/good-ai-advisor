from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim


model = SentenceTransformer(
    "intfloat/multilingual-e5-small"
)


documents = [
    "passage: Baggage insurance covers loss, theft and damage to personal belongings.",
    "passage: Medical expenses insurance covers necessary treatment during travel abroad.",
    "passage: Liability insurance covers damage caused by the insured person to another person.",
]


query = "query: Is my suitcase covered if it is stolen?"


document_embeddings = model.encode(documents)
query_embedding = model.encode(query)


print("Document vector shape:")
print(document_embeddings.shape)

print("\nQuery vector shape:")
print(query_embedding.shape)


scores = cos_sim(
    query_embedding,
    document_embeddings,
)[0]


for document, score in zip(documents, scores):
    print()
    print("Score:", float(score))
    print("Document:", document)