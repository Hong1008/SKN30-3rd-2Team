"""RunPod 서버리스 커스텀 워커 — 임베딩(dragonkue/BGE-m3-ko) + 리랭킹(dragonkue/bge-reranker-v2-m3-ko).

src/adapter/embedding_model.py 의 embedder·reranker 싱글톤을 그대로 재사용한다(Dockerfile이 빌드 시
복사). job input/output 스키마는 src/adapter/api_embedding_model.py(ApiEmbedder·ApiReranker)의
호출 규격과 정확히 맞춰져 있어, 해당 어댑터 코드는 무수정으로 이 워커를 호출할 수 있다.

worker-infinity-embedding(RunPod Hub) 대신 자체 구현을 쓰는 이유: 그 이미지는 rerank 응답을
JSON 직렬화하지 못하는 미해결 버그가 있다(runpod-workers/worker-infinity-embedding#37, #29).
"""
from typing import Any, Dict

import runpod

from service import handle_input


def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    return handle_input(job["input"])


runpod.serverless.start({"handler": handler})
