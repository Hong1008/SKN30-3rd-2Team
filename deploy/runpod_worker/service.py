"""임베딩·리랭킹 요청을 처리하는 Serverless/Pod 공용 서비스 계층."""

from typing import Any

from embedding_model import embedder, reranker


def _handle_embedding(job_input: dict[str, Any]) -> dict[str, Any]:
    texts = job_input["input"]
    if isinstance(texts, str):
        texts = [texts]
    embeddings = embedder.embed_documents(texts)
    return {
        "object": "list",
        "model": job_input.get("model"),
        "data": [
            {"object": "embedding", "embedding": embedding, "index": index}
            for index, embedding in enumerate(embeddings)
        ],
    }


def _handle_rerank(job_input: dict[str, Any]) -> dict[str, Any]:
    query = job_input["query"]
    docs = job_input["docs"]
    scores = reranker.compute_scores(query, docs)
    if job_input.get("return_docs"):
        return {"docs": docs, "scores": scores}
    return {"scores": scores}


def _handle_rerank_many(job_input: dict[str, Any]) -> dict[str, Any]:
    queries = job_input["queries"]
    docs_per_query = job_input["docs_per_query"]
    scores_per_query = reranker.compute_scores_many(queries, docs_per_query)
    return {"scores_per_query": scores_per_query}


def _module_device(module: Any) -> str:
    """nn.Module이 실제로 어느 device(cpu/cuda)에 올라가 있는지 반환한다."""
    try:
        return str(next(module.parameters()).device)
    except AttributeError:
        return str(next(module.model.parameters()).device)


def _handle_debug(_job_input: dict[str, Any]) -> dict[str, Any]:
    """GPU 실사용 여부 진단용으로 모델을 한 번 로드·추론한다."""
    import torch

    embedder.embed_query("디버그")
    reranker.compute_scores("디버그", ["디버그"])
    return {
        "cuda_available": torch.cuda.is_available(),
        "cuda_device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "embed_model_device": _module_device(embedder.model),
        "rerank_model_device": _module_device(reranker.model),
    }


def handle_input(job_input: dict[str, Any]) -> dict[str, Any]:
    """Serverless job input과 Pod HTTP input에 공통으로 사용하는 라우터."""
    if job_input.get("debug"):
        return _handle_debug(job_input)
    if "queries" in job_input:
        return _handle_rerank_many(job_input)
    if "query" in job_input:
        return _handle_rerank(job_input)
    if "input" in job_input:
        return _handle_embedding(job_input)
    raise ValueError(f"지원하지 않는 job input 형식입니다: {job_input}")
