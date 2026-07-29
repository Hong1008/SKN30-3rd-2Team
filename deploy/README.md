# deploy/ — 임베딩·리랭커 RunPod 배포

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

`runpodctl`을 설치하고 로컬 전용 RunPod 관리 키로 인증한다. 이 관리 키는
`RUNPOD_MANAGEMENT_API_KEY`라는 비추적 로컬 변수로 구분하고 MCP runtime이나 GitHub에는
주입하지 않는다. Pod proxy는 인터넷에 공개되므로
별도 워커 API 키를 반드시 요구한다. 생성 스크립트는 `EMBED_API_KEY`를 컨테이너에
주입하고, 로컬 모드에서는 같은 값을 `mcp/.env`의 `RUNPOD_EMBED_API_KEY`로만 저장한다.
부모 저장소 모드에서는 생성·삭제 스크립트 모두 `--no-env-file --output json`과
`RUNPOD_EMBED_API_KEY`를 사용하며, 스크립트는 AWS나 환경 파일을 변경하지 않는다.

```env
RUNPOD_MANAGEMENT_API_KEY=<RunPod management API key>
```

Pod 템플릿은 `maqkz41mly`로 고정되어 있으며, `Pod.Dockerfile`의 실행 구성에 추가 파라미터는 필요하지 않다. 기본 GPU는 `NVIDIA RTX 2000 Ada`이며, 필요한 경우 GPU만 인자로 지정한다.

```text
just deploy_embed_pod
just deploy_embed_pod "NVIDIA RTX A5000"
just embed-pod-status
just embed-pod-plan
```

생성에 성공하면 `mcp/.env`의 아래 값을 자동으로 갱신한다.

```env
RUNPOD_EMBED_POD_ID=<pod-id>
RUNPOD_POD_BASE_URL=https://<pod-id>-8000.proxy.runpod.net
RUNPOD_EMBED_API_KEY=<worker API key>
RUNPOD_EMBED_POD_TEMPLATE_ID=maqkz41mly
RUNPOD_EMBED_POD_NAME=workshield-prod-embed
RUNPOD_EMBED_POD_GPU_ID=NVIDIA RTX 2000 Ada
```

`RUNPOD_POD_BASE_URL`이 설정되면 `RUNPOD_ENDPOINT_ID`보다 우선하며, 요청은
`<RUNPOD_POD_BASE_URL>/runsync`로 전송된다. Pod가 떠 있는 동안 GPU 비용이 계속 발생하므로
작업이 끝난 뒤에는 반드시 `just rm_embed_pod`를 실행한다. 이 명령은 Pod를 삭제하고
`mcp/.env`의 Pod 연결 정보를 함께 제거한다.

Pod 이미지는 이 저장소의 `Publish Embed/Rerank Pod image` workflow를 수동 실행해 게시한다.
workflow는 `deploy/runpod_worker/Pod.Dockerfile`을 한 번 빌드하여 commit SHA tag를 먼저
게시하고, 그 digest를 `latest`로 승격한다. 이미지 게시 자체는 Pod나 Template을 변경하지
않으므로 실행 중인 Pod 교체는 별도 lifecycle 명령에서 명시적으로 수행한다.

| 파일 | 역할 |
| --- | --- |
| `service.py` | Serverless handler와 Pod HTTP 서버가 공유하는 입력 라우터 |
| `pod_server.py` | Bearer 인증을 요구하는 `/runsync`, `/health` HTTP 서버 |
| `Pod.Dockerfile` | Pod proxy 포트 8000을 노출하는 GPU 이미지 |
| `deploy_embed_pod.py` | 고정 Template으로 Pod 생성 및 연결 환경변수 갱신 |
| `rm_embed_pod.py` | 생성된 Pod 삭제 및 연결 환경변수 정리 |
