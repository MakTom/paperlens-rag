"""Evaluate the same RagService as the API; never supply gold labels to the model."""
from time import perf_counter

from src.evaluation.metrics import retrieval_metrics, summarize
from src.schemas.api.ask import AskRequest
from src.schemas.api.search import SearchRequest
from src.services.ollama import ModelServiceError
from src.services.rag import RagService
from src.services.search.client import SearchServiceError


class TimedRetriever:
    def __init__(self, inner):
        self.inner = inner
        self.result = None
        self.elapsed_ms = None

    def search(self, request):
        start = perf_counter()
        try:
            self.result = self.inner.search(request)
            return self.result
        finally:
            self.elapsed_ms = (perf_counter() - start) * 1000


class TimedGenerator:
    def __init__(self, inner):
        self.inner = inner
        self.elapsed_ms = None

    def generate(self, prompt, *, system=None):
        start = perf_counter()
        try:
            return self.inner.generate(prompt, system=system)
        finally:
            self.elapsed_ms = (perf_counter() - start) * 1000


def evaluate(cases, retriever, generator, *, retrieval_only=False):
    rows = []
    for case in cases:
        search, model = TimedRetriever(retriever), TimedGenerator(generator)
        row = dict(id=case.id, query=case.query, supported=case.supported,
                   kind=case.kind, categories=case.categories, error=None)
        start = perf_counter()
        try:
            request = AskRequest(query=case.query, categories=case.categories, top_k=5)
            if retrieval_only:
                search.search(SearchRequest(query=request.query, top_k=5, categories=request.categories))
            else:
                row["response"] = RagService(search, model).answer(request).model_dump(mode="json")
        except (SearchServiceError, ModelServiceError) as exc:
            row["error"] = type(exc).__name__
        elapsed = (perf_counter() - start) * 1000
        hits = search.result.hits if search.result else []
        row["retrieved"] = [h.model_dump(mode="json") for h in hits]
        row["metrics"] = retrieval_metrics([h.arxiv_id for h in hits], case.relevant_paper_ids)
        row["timings_ms"] = {"retrieval": search.elapsed_ms, "generation": model.elapsed_ms, "total": elapsed}
        row["retrieval_completed"] = search.result is not None
        row["retrieval_backend_took_ms"] = search.result.took_ms if search.result else None
        rows.append(row)
    return rows, summarize(rows)
