# Hub 워커가 깨졌을 때: RunPod handler를 직접 소유한 이유

> 프로젝트 저장소: [WorkShield — SKN30 3차 프로젝트](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN30-3rd-2Team)
> 이 글은 표준계약서 대비 검토 후보를 찾는 RAG MCP에서 임베딩과 리랭킹을 RunPod Serverless로 옮긴 기록이다. 특정 GPU 서비스가 항상 더 낫다는 일반론이 아니라, Hub 워커의 실제 실패를 만난 뒤 어떤 실행 경계를 직접 소유했는지를 다룬다.

처음 계획은 단순했다. RunPod Hub에서 임베딩·리랭킹 worker(요청을 받아 모델 추론을 수행하는 서버리스 실행 단위)를 골라 연결하면 될 것 같았다. 임베딩 요청은 실제로 성공했다. 그러나 rerank(검색 후보를 다시 채점해 순서를 정하는 작업) 요청은 응답을 돌려주는 마지막 단계에서 실패했다.

이 프로젝트에서 rerank는 선택적인 품질 개선 기능이 아니었다. 검색 후보의 RRF(여러 검색 순위를 결합하는 방식) 점수는 후보 순서용이고, 매칭 threshold(판정 임계값)와 비교할 점수는 reranker가 반환했다. rerank가 실패하면 임베딩이 동작해도 계약 조항의 매칭 경로는 완성되지 않는다.

그래서 문제를 다음처럼 다시 정의했다.

> 로컬에서 검증한 임베딩·리랭킹 코드를 외부 GPU에서도 같은 입출력 계약으로 실행하려면, 어떤 경계를 직접 소유해야 하는가?

이 글은 네 가지 실행 계약을 따라간다.

1. **코드 계약:** 실패한 handler(서버리스 job의 입력을 해석하고 결과를 반환하는 진입 함수)를 누가 수정·배포하는가
2. **데이터 계약:** 임베딩·rerank 요청과 응답을 어떤 형태로 주고받는가
3. **배포 계약:** 모델 가중치를 어디에 두고 어떤 이미지로 실행하는가
4. **운영 계약:** 동기 호출, 배치, timeout, worker 수를 어떻게 관리하는가

## 임베딩은 성공했지만 rerank는 JSON을 만들지 못했다

처음 사용한 것은 RunPod Hub의 [`worker-infinity-embedding`](https://github.com/runpod-workers/worker-infinity-embedding)이었다. 임베딩과 rerank를 함께 제공했고, 기존 HTTP 어댑터가 기대하는 형태와도 가까워 보였다.

그러나 실제 rerank 요청은 모델 점수 계산이 아니라 응답 직렬화 단계에서 막혔다. worker의 `handler.py`가 rerank 결과인 Pydantic 객체를 JSON으로 바꿔야 하는데, 객체 자체를 반환하는 경로가 있었다. 당시 Hub의 README 예제 요청도 같은 방식으로 실패했고, 같은 증상을 기록한 이슈도 해결되지 않은 상태였다.[#37](https://github.com/runpod-workers/worker-infinity-embedding/issues/37) [#29](https://github.com/runpod-workers/worker-infinity-embedding/issues/29)

```text
변경 전

WorkShield
  → RunPod Hub worker
      → rerank 모델 추론
      → Pydantic 결과 객체
      → JSON 직렬화 실패
```

이 문제는 재시도 횟수나 timeout을 늘려 해결할 성격이 아니었다. 매칭 경로에 필요한 기능이 worker 내부 결함으로 항상 실패했고, 우리 쪽에서는 해당 handler를 수정할 수 없었다.

여기서 판단 기준은 Hub worker의 기능 수가 아니었다.

> 핵심 요청이 실패했을 때, 원인 코드와 입출력 계약을 내가 고칠 수 있는가?

한 줄 패치의 크기보다 이후 어떤 코드베이스의 수명주기를 떠안아야 하는지가 더 중요했다.

## 먼저 worker의 최소 계약을 고정했다

대안을 고르기 전에 WorkShield가 외부 GPU에 요구하는 최소 계약을 정리했다.

| 요구사항                     | 필요한 이유                       |
| ------------------------ | ---------------------------- |
| 임베딩과 rerank 모두 지원        | 후보 생성과 매칭 점수 계산이 모두 필요하다.    |
| 로컬·운영에서 같은 모델 래퍼와 전처리 사용 | 구현 차이로 점수 계약이 달라질 위험을 줄인다.   |
| 단일·배치 rerank 지원          | 조항 수만큼 네트워크 왕복이 늘어나는 것을 막는다. |
| 명시적인 JSON 입출력            | 어댑터와 worker의 내부 구현을 분리한다.    |
| 실패를 예외로 전달               | 빈 벡터나 빈 점수로 조용히 성공하지 않게 한다.  |

worker가 받는 요청은 세 종류로 제한했다.

```json
{
  "model": "dragonkue/BGE-m3-ko",
  "input": ["조항 A", "조항 B"]
}
```

```json
{
  "model": "dragonkue/bge-reranker-v2-m3-ko",
  "query": "사용자 조항",
  "docs": ["후보 1", "후보 2"],
  "return_docs": false
}
```

```json
{
  "model": "dragonkue/bge-reranker-v2-m3-ko",
  "queries": ["질의 1", "질의 2"],
  "docs_per_query": [["후보 A", "후보 B"], ["후보 C"]]
}
```

다중 질의 응답은 입력 순서와 같은 구조를 유지한다.

```json
{
  "scores_per_query": [[0.99, 0.12], [0.87]]
}
```

worker는 모델 래퍼에서 받은 점수를 추가로 정렬하거나 threshold를 적용하지 않고 입력 순서대로 반환한다. `top_k`와 매칭 threshold는 기존 파이프라인의 책임으로 남겼다.

현재 요청의 `model` 필드는 실제 모델 선택기가 아니다. 모델은 이미지 빌드 시점에 고정되고, 호출 측 어댑터도 고정된 ID만 보낸다. 따라서 다른 모델 ID를 보내도 실행 모델이 바뀌지 않는 인터페이스 부채가 남아 있다. embedding 응답의 `model` 값도 실행 모델 식별자가 아니라 요청값을 그대로 반사한다. 운영 API로 확장한다면 `model` 필드를 제거하거나, 허용된 모델 ID인지 검증해야 한다.

또한 같은 Python 래퍼를 사용한다고 CPU·GPU, 라이브러리 버전, dtype(수치 자료형), 모델 revision(특정 모델 저장소 버전), batch size(한 번에 추론하는 입력 수)가 다른 환경에서 완전히 같은 점수가 보장되는 것은 아니다. 같은 코드를 재사용한 목적은 출력 동일성을 보장하는 것이 아니라, 전처리·정렬·응답 변환을 환경마다 다르게 구현할 위험을 줄이는 데 있었다.

## Hub worker, Pod, vLLM은 같은 층위의 대안이 아니었다

Hub worker가 실패한 뒤 Pod와 vLLM도 검토했다. 하지만 셋은 같은 문제에 대한 대안이 아니었다.

* Hub worker와 custom worker는 **handler의 소유권**
* Pod와 Serverless는 **실행 방식**
* vLLM은 **추론 엔진**

### Hub worker: 가장 빠른 시작이 가장 짧은 복구 경로는 아니었다

Hub worker는 이미지와 handler를 바로 사용할 수 있다는 점에서 빠른 선택이었다. 그러나 핵심 rerank 경로를 직접 고칠 수 없었다.

```text
우리 코드 → 외부 worker의 고정 handler → 직렬화 결함
                         ↑
                      수정 권한 없음
```

worker를 포크해 직렬화 코드를 고칠 수도 있었다. 하지만 그러면 유지보수가 사실상 멈춘 외부 worker의 구조와 의존성을 계속 따라가야 한다.

| 선택             | 직접 유지할 범위                   | 장점               | 부담                   |
| -------------- | --------------------------- | ---------------- | -------------------- |
| Hub worker 포크  | 외부 worker 구조와 의존성           | 초기 수정량이 작다       | 업스트림 구조와 버전에 계속 결합한다 |
| custom handler | handler·Dockerfile·기존 모델 모듈 | 검증한 로컬 구현을 재사용한다 | 이미지와 배포를 직접 관리한다     |
| 별도 serving 엔진  | API·모델 호환성·배포 단위            | 처리량 최적화 여지가 크다   | 이번 문제보다 큰 설계 범위를 연다  |

여기서 “작은 변경”은 코드 줄 수가 아니라 직접 유지해야 할 의존 구조를 뜻한다. 이 프로젝트에서는 이미 소유한 로컬 추론 코드를 연장하는 편이 외부 worker 전체를 새로 떠안는 것보다 예측 가능했다.

### Pod: 서버리스 이미지를 계속 실행한다고 문제가 해결되지는 않았다

Pod(계속 실행되는 GPU 인스턴스) 전환도 검토했다. 당시 아시아 지역 GPU 재고가 부족해 다른 지역 GPU를 사용했고, 네트워크 지연이 커 보였다.

그러나 Hub worker는 HTTP 포트를 여는 서비스가 아니라 `runpod.serverless.start()`로 job queue를 처리하는 서버리스 worker였다. Pod에서 사용하려면 이미지를 계속 실행하는 것만으로는 부족했다.

```text
Serverless worker
  RunPod job queue → handler(job) → 결과

Pod 서비스
  HTTP 포트 → 웹 서버 → 모델 서버 → 결과
```

Pod로 바꿔도 rerank 직렬화 결함이나 handler 소유권은 해결되지 않는다. 이번 문제는 인스턴스를 계속 켜 둘지보다, 핵심 요청을 처리하는 코드를 누가 고칠 수 있는지에 가까웠다.

### vLLM: 가능한 선택이지만 이번 경로의 최소 변경은 아니었다

vLLM은 GPU 추론을 효율적으로 제공하는 엔진이다. 다만 이 프로젝트의 요구는 생성 API가 아니라 임베딩과 cross-encoder(질의와 문서를 함께 넣어 관련성 점수를 계산하는 모델) rerank를 같은 경로에서 제공하는 것이었다.

검토 당시 RunPod의 vLLM worker는 생성 중심의 입출력에 맞춰져 있었다. 임베딩과 rerank를 제공하려면 API, 모델별 호환성, 배포 단위와 handler를 새로 설계해야 했다.

```text
vLLM 경로

추론 엔진 선정
  → 임베딩 API 설계
  → rerank API 설계
  → 모델 호환성 검증
  → 배포 단위 구현

기존 코드 재사용 경로

검증한 Sentence Transformers 코드
  → 얇은 RunPod handler
  → 기존 어댑터와 연결
```

vLLM이 부적절하다는 뜻은 아니다. 모델 수가 늘거나 생성 요청을 함께 대규모로 처리한다면 다시 비교할 수 있다. 이번 목표는 새로운 모델 serving(모델을 네트워크 요청으로 제공하는 운영 방식)을 설계하는 것이 아니라, 이미 검증한 매칭 경로를 외부 GPU로 옮기는 것이었다.

## 기존 추론 코드를 재사용하는 custom handler를 만들었다

최종적으로 `deploy/runpod_worker/handler.py`에 custom handler를 두고, 로컬에서 사용하던 `Bgem3Embedder`와 `BgeReranker`를 재사용했다.

```text
WorkShield
  → ApiEmbedder / ApiReranker
      → POST /runsync
          → custom handler
              → 기존 embedder / reranker
                  → JSON 응답
```

handler는 모델 판단을 새로 구현하지 않는다. 요청 형태를 구분해 기존 구현체로 전달하고, 결과를 JSON으로 변환한다.

```python
def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    job_input = job["input"]

    if job_input.get("debug"):
        return _handle_debug(job_input)
    if "queries" in job_input:
        return _handle_rerank_many(job_input)
    if "query" in job_input:
        return _handle_rerank(job_input)
    if "input" in job_input:
        return _handle_embedding(job_input)

    raise ValueError(f"지원하지 않는 job input 형식입니다: {job_input}")
```

현재 라우팅은 키 존재 여부에 의존한다. 내부 프로젝트에서 세 종류의 요청을 처리하기에는 충분했지만, 공개 API 계약으로는 약하다. `query`와 `input`이 함께 들어오는 모순된 요청을 명시적으로 거부하지 못하기 때문이다.

운영 범위가 넓어진다면 다음처럼 `task`를 명시하고 task별 스키마를 검증하는 편이 안전하다.

```json
{
  "task": "rerank_many",
  "queries": ["질의 1", "질의 2"],
  "docs_per_query": [["후보 A"], ["후보 B"]]
}
```

임베딩 응답은 `index`로 입력 순서를 보존한다.

```python
return {
    "object": "list",
    "model": job_input.get("model"),
    "data": [
        {"object": "embedding", "embedding": emb, "index": i}
        for i, emb in enumerate(embeddings)
    ],
}
```

호출 측 어댑터는 `index`를 기준으로 다시 정렬한다.

```python
data.sort(key=lambda d: d["index"])
return [d["embedding"] for d in data]
```

이 계약 덕분에 애플리케이션 코드 관점에서는 로컬과 운영 환경의 차이를 전송 방식으로 좁힐 수 있었다.

| 계층           | 로컬                   | 운영                |
| ------------ | -------------------- | ----------------- |
| 모델 계산        | `embedding_model.py` | 같은 모듈을 컨테이너에서 실행  |
| 조립           | 환경에 따라 로컬 구현 선택      | API 어댑터 선택        |
| 전송           | 프로세스 내부 호출           | RunPod `/runsync` |
| 정렬·threshold | 기존 파이프라인             | 같은 파이프라인          |

실패 응답은 아직 구조화된 오류 코드가 아니라 플랫폼 상태와 Python 예외로 전달한다.

```python
if body.get("status") != "COMPLETED":
    raise RuntimeError(
        f"RunPod 작업 미완료: status={body.get('status')}"
    )

output = body.get("output")
if output is None:
    raise RuntimeError("RunPod 응답에 output 키가 없습니다")
```

호출 측 어댑터에서는 네트워크 오류, job 실패, 출력 누락을 모두 `RuntimeError` 계열로 처리한다. handler 내부의 잘못된 입력은 `ValueError` 등으로 실패한 뒤 job 실패 상태로 전달된다. 공개 범위가 커지면 입력 오류, 지원하지 않는 모델, 출력 불일치, GPU 자원 오류를 구분하는 오류 코드가 필요하다.

## 모델을 런타임에 받지 않고 이미지에 포함했다

handler를 만든 뒤에도 한 번 더 배포 실패를 겪었다. 처음에는 네트워크 볼륨에 Hugging Face 캐시를 두는 방식을 시도했다.

```text
worker 시작
  → /runpod-volume의 모델 캐시 사용 시도
  → worker EXITED
```

서버리스 endpoint에 네트워크 볼륨이 연결되지 않은 상태에서는 `/runpod-volume`을 안정적인 모델 경로로 가정할 수 없었다. 모델 가용성이 이미지와 endpoint 설정에 나뉘어 있었다.

그래서 모델 가중치를 컨테이너 빌드 시점에 내려받아 이미지에 포함했다.

```dockerfile
ENV HF_HOME=/app/models

RUN python -c "\
from sentence_transformers import SentenceTransformer, CrossEncoder; \
SentenceTransformer('dragonkue/BGE-m3-ko'); \
CrossEncoder('dragonkue/bge-reranker-v2-m3-ko')"
```

```text
Docker build
  → 모델 다운로드
  → 이미지에 가중치 포함

worker 시작
  → 이미지 안의 모델 로드
  → 런타임 다운로드와 볼륨에 의존하지 않음
```

이 방식은 이미지가 커지고 build·push 시간이 늘어난다. 대신 worker가 시작될 때마다 모델을 다운로드하거나 볼륨 경로를 확인하지 않아도 된다.

정확히 말하면 cold start 전체를 없앤 것은 아니다.

| 제거한 의존성               | 여전히 남는 지연           |
| --------------------- | ------------------- |
| Hugging Face 런타임 다운로드 | worker 노드의 이미지 pull |
| 네트워크 볼륨과 캐시 가용성       | 컨테이너 시작             |
| 시작 시점의 모델 파일 획득 실패    | 모델 역직렬화와 GPU 메모리 적재 |
|                       | CUDA context 초기화    |

이 선택은 cold start 제거가 아니라, 실행 시점의 모델 다운로드와 볼륨 의존을 빌드 시점으로 옮긴 것이다.

현재는 모델 revision, Python 의존성 lock, base image digest까지 고정하지 않았다. 따라서 런타임 의존은 줄였지만 같은 Dockerfile의 재빌드 결과까지 완전히 재현된다고 말할 수는 없다.

## 배치 rerank의 네트워크 왕복을 줄였다

초기 `ApiReranker.rerank_many()`는 여러 질의를 받았지만 내부적으로 질의마다 `rerank()`를 호출했다.

```text
질의 1 → /runsync
질의 2 → /runsync
질의 3 → /runsync

총 네트워크 호출: N회
```

custom handler를 소유한 뒤 `queries`와 `docs_per_query`를 한 요청에 넣는 경로를 추가했다.

```python
def _handle_rerank_many(job_input: Dict[str, Any]) -> Dict[str, Any]:
    queries = job_input["queries"]
    docs_per_query = job_input["docs_per_query"]

    scores_per_query = reranker.compute_scores_many(
        queries,
        docs_per_query,
    )
    return {"scores_per_query": scores_per_query}
```

```text
질의 1, 2, 3 + 후보 묶음
  → /runsync 1회
  → scores_per_query

총 네트워크 호출: 1회
```

로컬 reranker는 `(질의, 후보 문서)` 쌍을 펼쳐 `predict()`에 전달하고 결과를 질의별 배열로 되돌린다. 애플리케이션 레벨에서는 한 번 호출하지만, 실제 모델 추론은 내부 batch size에 따라 여러 묶음으로 실행될 수 있다.

worker는 입력 순서대로 점수만 반환한다. 각 질의 내부의 정렬과 `top_k` 적용은 어댑터와 기존 파이프라인에 남겼다.

다만 네트워크 호출을 한 번으로 줄였다고 입력을 무제한으로 합칠 수 있는 것은 아니다. 질의 100개에 후보 100개를 넣으면 10,000개의 pair가 만들어진다.

현재는 최대 질의 수, 전체 pair 수, token 수와 요청 크기 상한이 없다. 따라서 이번 변경은 N회의 네트워크 왕복을 1회로 줄인 제한된 개선이다. 운영 부하를 받는 API로 확장한다면 입력 상한과 chunking(작은 묶음으로 나누어 처리하는 방식) 정책이 필요하다.

## `/runsync`는 시연을 위한 동기 계약이었다

호출 측은 RunPod의 `/runsync`를 사용한다.

```python
resp = requests.post(
    url,
    json={"input": payload},
    timeout=_TIMEOUT,
)
```

시연·평가 단계에서는 job ID를 저장하고 polling하는 비동기 흐름보다, 요청 하나가 끝날 때까지 응답을 기다리는 단순한 경로를 선택했다.

```text
현재
클라이언트 → /runsync → 완료 응답 또는 timeout

확장 시
클라이언트 → /run → job ID
클라이언트 → polling → 완료 결과
```

동기 호출은 긴 cold start나 큰 batch에서 요청을 오래 점유한다. HTTP timeout 이후에도 플랫폼에서 job이 계속 실행 중인지 호출 측만으로는 알기 어렵고, 재시도하면 같은 작업이 중복 실행될 수도 있다.

긴 작업과 재시도 안전성이 중요해지면 비동기 job과 idempotency key(같은 요청의 중복 실행을 막는 식별자)가 필요하다.

## Serverless의 켜짐과 꺼짐을 운영 정책으로 다뤘다

모델이 이미지 안에 있어도 `workers-min=0`인 endpoint의 첫 요청에는 worker 생성과 모델 로딩 시간이 남는다. 처음에는 timeout을 60초로 두었고, cold start(중지된 worker가 이미지·모델을 준비해 첫 요청을 처리하기까지의 지연) 중에 HTTP 클라이언트가 먼저 실패했다.

```python
_TIMEOUT = 180
```

timeout을 늘리는 것만으로 시연 중의 지연을 제거할 수는 없었다. 그래서 작업 세션 전후에 `workers-min`을 명시적으로 전환했다.

```bash
# 평가·시연 전
runpodctl serverless update <endpoint-id> --workers-min 1

# 작업 종료 후
runpodctl serverless update <endpoint-id> --workers-min 0
```

```text
평상시
workers-min = 0
  → 유휴 GPU 비용 최소화
  → 첫 요청 cold start 가능

평가·시연 전
workers-min = 1
  → worker 유지
  → 기동 지연 감소
```

이는 자동 확장 정책을 완성한 것이 아니다. 시연과 평가라는 사용 패턴에서 비용과 준비 시간을 사람이 명시적으로 전환한 운영 절차다.

## 검증한 것과 남은 한계

배포 성공과 운영 설계 전체의 검증은 같은 주장이 아니다.

| 확인한 것           | 방법                            |
| --------------- | ----------------------------- |
| 임베딩 endpoint 동작 | 실제 endpoint에서 1024차원 벡터 반환 확인 |
| 단일 rerank       | 질의·후보 점수 반환 확인                |
| 배치 rerank       | 질의 2개가 RunPod 호출 1회로 처리되는지 확인 |
| 순서 보존           | 반환 점수가 입력 질의·문서 순서와 대응하는지 확인  |
| 공통 애플리케이션 경로    | 같은 모델 래퍼·전처리·정렬 코드 사용         |
| cold start 대응   | timeout 상향과 `workers-min` 전환  |

남아 있는 한계도 분명하다.

* `model` 필드가 실제 모델 선택과 일치하지 않는다.
* 키 기반 요청 라우팅과 오류 응답이 공개 API 수준으로 구조화되지 않았다.
* 모델 revision, 의존성 lock, base image digest를 고정하지 않았다.
* 배치 입력 크기와 GPU 메모리 상한이 없다.
* `/runsync`의 중복 재시도 안전성을 보장하지 않는다.
* 임베딩과 reranker를 한 worker에 함께 적재해 이미지와 GPU 메모리가 커진다.
* vLLM과 처리량·비용을 같은 조건에서 비교하지 않았다.
* 다중 worker 장기 부하 환경을 검증하지 않았다.
* CPU·GPU와 라이브러리 조건에 따른 점수 차이를 별도로 회귀 검증하지 않았다.

이 구현은 모든 모델 serving 문제의 정답이 아니다. rerank가 반드시 필요한 작은 시연 시스템에서, 수정할 수 없는 Hub worker 결함을 피하고 기존 추론 경로를 외부 GPU로 옮기기 위한 선택이었다.

## 내가 배운 설계 원칙

* 외부 GPU 도입에서는 모델 성능뿐 아니라 실패한 handler를 직접 수정할 수 있는지 확인해야 한다.
* Hub worker, Pod, 추론 엔진은 서로 다른 층위의 선택지다.
* handler는 입력 라우팅과 JSON 변환을 맡고 검색·판정 정책은 기존 파이프라인에 남기는 편이 안전하다.
* 로컬 모델 래퍼와 전처리를 재사용하면 구현 차이로 점수 계약이 달라질 위험을 줄일 수 있다.
* 모델 가중치의 위치는 cold start와 재현성에 영향을 주는 실행 계약이다.
* 배치는 모델 추론뿐 아니라 네트워크 왕복 횟수도 줄여야 한다.
* 배치 요청에는 pair 수·token 수·메모리 상한이 필요하다.
* 동기 `/runsync`는 단순한 시연 흐름에는 맞지만 긴 작업과 재시도 안전성을 해결하지 않는다.
* `workers-min`(최소 유지 worker 수)과 timeout은 비용·대기 시간·준비 상태를 전환하는 운영 정책이다.
* 배포 성공, 실제 endpoint 검증, 장기 운영 검증은 서로 다른 주장이다.

처음에는 외부 GPU를 모델을 돌릴 장소로만 생각했다. 실제로는 handler, image, 모델 캐시, 요청 스키마와 worker 수가 함께 하나의 실행 계약을 이뤘다.

custom worker를 만든 이유는 외부 플랫폼을 대체하기 위해서가 아니었다. 모델 계산은 기존 코드에 남기고, 실패와 입출력을 직접 고칠 수 있는 가장 얇은 경계만 소유하기 위해서였다.
