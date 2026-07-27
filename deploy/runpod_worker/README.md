# deploy/runpod_worker/ — 임베딩·리랭커 RunPod 서버리스 워커

`src/adapter/api_embedding_model.py`(ApiEmbedder·ApiReranker)가 호출하는 RunPod 서버리스
엔드포인트의 실제 구현체. RunPod Hub의 `worker-infinity-embedding`은 rerank 응답을 JSON
직렬화하지 못하는 미해결 버그가 있어([#37](https://github.com/runpod-workers/worker-infinity-embedding/issues/37),
[#29](https://github.com/runpod-workers/worker-infinity-embedding/issues/29)) 대신 자체 구현을 쓴다.

`handler.py`는 `src/adapter/embedding_model.py`(sentence-transformers 기반 `embedder`/`reranker`
싱글톤)를 그대로 재사용한다 — 로컬 실행 경로와 동일한 코드가 컨테이너 안에서 돈다.

모델 가중치는 `--model-reference`(네트워크 볼륨/`/runpod-volume` 캐시 의존)가 아니라
**빌드 타임에 이미지 안에 직접 구워 넣는다**([RunPod 공식 커스텀 템플릿 가이드](https://docs.runpod.io/pods/templates/create-custom-template)
방식). 네트워크 볼륨을 안 붙인 서버리스 GPU 워커는 `/runpod-volume`이 실제 쓰기 가능한 디스크가
아닐 수 있어(`volumeInGb: 0`) 런타임 다운로드가 실패할 수 있음 — 이미지에 굽는 쪽이 더 안전하다.

## 빌드 · 배포

```bash
# 1. 이미지 빌드 (컨텍스트는 리포지토리 루트여야 함)
docker build -f deploy/runpod_worker/Dockerfile -t <registry>/<repo>:<tag> .

# 2. 로컬 스모크 테스트 (GPU 없으면 CPU로 느리게 동작 — 정상 응답만 확인)
docker run --rm <registry>/<repo>:<tag> python -u handler.py --test_input test_input.json

# 3. 레지스트리 push
docker push <registry>/<repo>:<tag>

# 4. RunPod 템플릿 생성 (최초 1회) — 이후 이 템플릿으로 서버리스 엔드포인트를 만들거나 갱신
runpodctl template create --name workshield-embed-rerank --image <registry>/<repo>:<tag> --serverless

# 5. 서버리스 엔드포인트 생성/갱신 (모델이 이미지에 이미 구워져 있어 --model-reference 불필요)
runpodctl serverless create \
  --name workshield-embed-rerank \
  --template-id <template-id> \
  --gpu-id "NVIDIA RTX A4000" \
  --workers-min 0 --workers-max 1 --idle-timeout 60
```

## 운영

작업 세션 전후로 콜드스타트를 피하려면 `workers-min`만 토글한다(과금은 워커가 떠 있는 동안만 발생):

```bash
runpodctl serverless update <endpoint-id> --workers-min 1   # 작업 시작 전
runpodctl serverless update <endpoint-id> --workers-min 0   # 작업 종료 후
```

## job input/output 스키마

`src/adapter/api_embedding_model.py`와 1:1로 맞춰져 있다. 스키마를 바꾸면 그쪽 코드도 같이 바꿔야 한다.

| 요청 | 응답 |
| --- | --- |
| `{"model": "...", "input": "text" \| ["text", ...]}` | `{"data": [{"embedding": [...], "index": 0}, ...]}` |
| `{"model": "...", "query": "...", "docs": [...], "return_docs": false}` | `{"scores": [0.9, 0.1, ...]}` |
| `{"model": "...", "queries": [...], "docs_per_query": [[...], ...]}` | `{"scores_per_query": [[...], ...]}` (정렬 없음, 입력 순서 유지) |

`queries`(복수형)를 배치 rerank 라우트로 쓴다 — 질의 N개를 네트워크 호출 1번으로 채점해
`ApiReranker.rerank_many`가 질의마다 순차 호출하던 방식(N회 왕복)을 대체한다.

## 파일

| 파일 | 역할 |
| --- | --- |
| `handler.py` | `runpod.serverless.start()` 진입점. job 라우팅만 담당(순수 I/O, 판단 로직 없음) |
| `Dockerfile` | `src/config.py`, `src/adapter/embedding_model.py` 를 빌드 시 그대로 복사해 재사용 |
| `test_input.json` | 로컬 스모크 테스트용 샘플 임베딩 요청 |

## RunPod Pod 대체 경로

Serverless 워커가 기동하지 않거나 콜드스타트가 허용되지 않는 환경에서는 Pod를 사용한다.
`Pod.Dockerfile`은 같은 모델 가중치와 `service.py` 라우터를 사용하지만, Pod proxy로 직접
호출할 수 있도록 `pod_server.py`가 `POST /runsync`를 제공한다. 이 경로의 요청·응답 외피는
Serverless와 같으므로 `ApiEmbedder`와 `ApiReranker`는 변경하지 않는다.

`mcp/.env`에 다음 값을 설정한다. Pod 경로는 로컬 검증·비용 절감용이며 별도 인증을 적용하지 않는다.

```env
RUNPOD_API_KEY=<RunPod API key>
RUNPOD_EMBED_POD_IMAGE=ghcr.io/<owner>/workshield-embed-rerank-pod:<tag>
```

이미지를 build·push한 뒤 Template과 Pod를 순서대로 만든다.

```text
just embed-pod-image-build
just embed-pod-image-push
just embed-pod-template-create
# 출력된 Template ID를 RUNPOD_EMBED_POD_TEMPLATE_ID에 기록
just embed-pod-create
# 출력된 Pod ID를 RUNPOD_EMBED_POD_ID에 기록
```

생성 결과의 Pod ID가 `abc123`이면 MCP 실행 환경에는 다음을 추가한다.

```env
APP_ENV=prod
RUNPOD_POD_BASE_URL=https://abc123-8000.proxy.runpod.net
```

`RUNPOD_POD_BASE_URL`이 설정되면 `RUNPOD_ENDPOINT_ID`보다 우선하며, 요청은
`<RUNPOD_POD_BASE_URL>/runsync`로 전송된다. Pod가 떠 있는 동안 GPU 비용이 계속 발생하므로
작업이 끝난 뒤에는 반드시 `just embed-pod-delete`를 실행한다. `stop`은 GPU 실행만 멈추며
Pod 상태·저장소 비용이 남을 수 있다.

| 파일 | 역할 |
| --- | --- |
| `service.py` | Serverless handler와 Pod HTTP 서버가 공유하는 입력 라우터 |
| `pod_server.py` | 공개 `/runsync`, `/health` HTTP 서버 |
| `Pod.Dockerfile` | Pod proxy 포트 8000을 노출하는 GPU 이미지 |
| `manage_pod.py` | 이미지·Template·Pod 생성, 조회, 중지, 삭제 명령 구현 |
