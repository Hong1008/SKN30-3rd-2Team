# =================================================================
# WorkShield 임베딩/리랭커 RunPod Pod 이미지
# - Serverless worker와 동일한 모델·서비스 계층을 사용한다.
# - /runsync HTTP 외피만 Pod proxy 연결을 위해 pod_server.py가 제공한다.
# =================================================================
FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime

WORKDIR /app

RUN pip install --no-cache-dir "sentence-transformers>=5.6.0" python-dotenv

COPY src/config.py ./config.py
COPY src/adapter/embedding_model.py ./embedding_model.py
COPY deploy/runpod_worker/service.py ./service.py
COPY deploy/runpod_worker/pod_server.py ./pod_server.py

ENV HF_HOME=/app/models \
    POD_HOST=0.0.0.0 \
    POD_PORT=8000
RUN python -c "\
from sentence_transformers import SentenceTransformer, CrossEncoder; \
SentenceTransformer('dragonkue/BGE-m3-ko'); \
CrossEncoder('dragonkue/bge-reranker-v2-m3-ko')"

EXPOSE 8000

CMD ["python", "-u", "pod_server.py"]
