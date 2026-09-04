import math
import re


def _terms(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z0-9]+|[\u4e00-\u9fff]", text.lower()))


class LocalRetriever:
    def __init__(self, documents: list[dict]):
        self.documents = documents

    def search(self, question: str, limit: int = 3) -> list[dict]:
        query_terms = _terms(question)
        ranked = []
        for document in self.documents:
            chunks = document.get("samples", [])
            for index, chunk in enumerate(chunks, start=1):
                text = f"{document['name']} {chunk}"
                terms = _terms(text)
                shared = query_terms & terms
                score = len(shared) / math.sqrt(max(1, len(query_terms) * len(terms)))
                if score:
                    ranked.append({"document": document["name"], "chunk": index, "content": chunk, "score": round(score, 3)})
        return sorted(ranked, key=lambda item: item["score"], reverse=True)[:limit]
