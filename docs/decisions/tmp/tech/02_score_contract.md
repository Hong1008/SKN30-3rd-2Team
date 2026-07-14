# 점수 계약: RRF·재정렬기(reranker)·임계값(threshold)을 같은 숫자로 취급하면 생기는 문제

> 프로젝트 저장소: [WorkShield — SKN30 3차 프로젝트](https://github.com/SKNETWORKS-FAMILY-AICAMP/SKN30-3rd-2Team)  
> 이 글은 위 프로젝트에서 표준계약서 대비 검토 후보를 찾는 RAG MCP를 구현하며 실제로 겪은 점수 계약 오류를 정리한 글이다. 법률적 판단이 아니라 검색 점수의 역할과 인터페이스 설계를 다룬다.

RAG(Retrieval-Augmented Generation, 검색 증강 생성)는 먼저 관련 문서를 찾고 그 결과를 다음 처리에 전달하는 구조다. MCP(Model Context Protocol)는 이 기능을 외부 클라이언트가 호출할 수 있게 제공하는 인터페이스다.

전체 발전 과정은 [검색 점수는 의미가 같다는 증거가 아니었다](https://velog.io/@hong1008/ai-camp-3rd-project-2)에서 다뤘다. 이 글에서는 그중 RRF(순위 결합 점수), reranker(후보 재정렬기), threshold(판정 임계값), 테스트 fake(가짜 구현)의 관계만 좁혀 본다.

문제는 RRF 공식을 몰랐다는 데만 있지 않았다. 서로 다른 단계의 출력을 모두 `score`로 취급했고, 테스트 fake(실행을 흉내 내는 가짜 구현)가 실제 실행에는 없는 reranker 결과를 미리 제공하면서 파이프라인(처리 단계 연결) 누락을 가렸다. 따라서 이 글은 “RRF 점수의 범위를 몰라서 생긴 실수”보다 점수 계약이 코드와 테스트에 드러나지 않았던 사례에 가깝다.

본문에서 query는 질의, candidate는 후보, top-k는 상위 k개 후보를 뜻한다. Recall@k는 상위 k개 안에 정답이 포함된 비율인 재현율이고, MRR(Mean Reciprocal Rank, 평균 역순위)은 정답이 얼마나 앞에 나왔는지를 나타내는 지표다.

## 모든 조항이 `NO_MATCH`가 되었다

실제 계약서를 파이프라인에 넣자 사용자 조항은 전부 `NO_MATCH`, 표준조항은 전부 `MISSING`으로 나왔다. 비교할 표준조항이 없었던 것이 아니라, 후보를 찾은 뒤 매칭 여부를 판단하는 숫자를 잘못 사용한 결과였다.

당시 흐름은 다음과 같았다.

```text
dense 검색 + BM25 검색
          ↓
       RRF 결합
          ↓
   fusion_score 비교
          ↓
   match_threshold = 0.5
```

RRF(Reciprocal Rank Fusion, 순위 역순 결합)는 검색 결과의 순위를 합치는 방식이다. 당시 설정은 검색기 두 개, 가중치 1, `k=60`이었다. 따라서 두 검색 결과가 모두 1위여도 `fusion_score`는 대략 다음 수준이었다.

```text
1 / 61 + 1 / 61 ≈ 0.0328
```

이 값을 `0.5`와 비교하면 어떤 후보도 threshold(판정 임계값)를 넘을 수 없다. 검색이 실패한 것이 아니라 서로 다른 점수 계약을 직접 비교한 것이다.

이 값은 RRF의 보편적인 상한이 아니다. 검색기 수, 가중치, `k` 설정이 달라지면 범위도 달라진다. 중요한 것은 숫자를 외우는 것이 아니라, 현재 설정에서 생성되는 점수의 범위를 threshold 계약과 함께 확인하는 일이다.

## 세 숫자는 서로 다른 질문에 답한다

| 값 | 생성 과정 | 답하는 질문 | 사용 위치 |
| --- | --- | --- | --- |
| `fusion_score` | dense(의미 벡터 검색)와 BM25(단어 빈도 검색)의 순위 결합 | 어떤 후보를 먼저 볼 것인가? | 후보 확보 |
| `rerank_score` | 질의·후보 쌍의 재평가 | 어떤 후보를 앞에 둘 것인가? | 후보 재정렬·매칭 신호 |
| `match_threshold` | 파이프 설정 | 어떤 점수 이상을 대응 후보로 볼 것인가? | 특정 점수와 비교 |

둘 다 실수형이지만 계약은 다르다.

```python
fusion_score = 0.0328
rerank_score = 0.95
```

`fusion_score`는 후보를 고르는 순위 신호이고, `rerank_score`는 후보쌍을 다시 비교하는 신호다. 여기서 `0.5` threshold가 유효한 이유도 reranker 일반의 속성이 아니라, 이 프로젝트의 reranker 어댑터(외부 모델을 연결하는 구현)가 최종적으로 0~1 범위의 점수를 반환한다는 계약에 있다. 원시 logit(모델의 변환 전 점수)을 반환하는 모델이라면 같은 threshold를 그대로 사용할 수 없다.

중요한 것은 어느 값이 더 좋은지가 아니라 각 값이 어떤 질문에 답하도록 만들어졌는지를 고정하는 일이다.

## 변경 전: `score`라는 이름이 계약을 숨겼다

초기 코드는 후보의 점수를 그대로 threshold에 넣었다.

```python
candidates = retriever.search(query, top_k=5)
best, score = select_best_match(candidates)

if score >= match_threshold:
    deviation = Deviation.NONE
else:
    deviation = Deviation.NO_MATCH
```

이 코드만 보면 `score`가 RRF인지 reranker인지, 이미 정규화(비교 가능한 범위로 변환)됐는지 알 수 없다. 설계에서 전제한 reranker 단계도 실제 파이프라인에서는 빠져 있었다.

## 테스트 fake가 결함을 숨긴 방식

테스트용 fake(가짜 구현)는 이미 높은 reranker 점수를 반환했다.

```python
class FakeRetriever:
    def search(self, query, top_k=5):
        return [{
            "clause_id": "sw_freelance-2020-art20",
            "fusion_score": 0.02,
            "rerank_score": 0.95,
        }]
```

돌이켜 보면 `FakeRetriever`가 `rerank_score`까지 반환한다는 사실 자체가 계약 위반의 신호였다. Retriever(후보 검색기)는 후보를 검색하고, reranker는 그 후보를 재정렬해야 하는데 두 단계의 결과가 하나의 fake 안에 섞여 있었기 때문이다.

테스트는 `0.95 >= 0.5`인 분기를 통과했다. 하지만 실제 파이프에서는 reranker가 호출되지 않았으므로 `0.95`는 실제 실행에서 만들어진 점수가 아니었다.

테스트가 놓친 것은 다음 네 가지였다.

- 실제 검색 점수의 범위
- reranker 호출 여부
- threshold가 소비하는 필드
- 검색과 재정렬 단계의 경계

테스트는 결과 형태와 분기를 검증했지만 점수의 생성·변환·소비 계약은 검증하지 않았다.

> fake가 현실적인 숫자를 반환하는 것만으로는 부족하다. 그 숫자가 실제 어느 단계에서 생성되는지도 재현해야 한다.

## 변경 후: 후보 확보와 매칭 판정을 분리했다

```text
사용자 조항
    ↓
dense + BM25 검색
    ↓
RRF로 후보 확보
    ↓
reranker로 후보 재정렬
    ↓
rerank_score를 사용해 후보 판정
```

후보 선택과 threshold 판정을 별도 함수로 나눴다.

```python
def select_best_match(candidates):
    if not candidates:
        return None, 0.0
    best = max(candidates, key=lambda item: item.rerank_score)
    return best.standard_clause, best.rerank_score


def classify_clause_deviation(matched_standard, score, match_threshold):
    if matched_standard is None:
        return Deviation.NO_MATCH
    return (
        Deviation.NONE
        if score >= match_threshold
        else Deviation.EXTRA
    )
```

`select_best_match`는 “무엇이 가장 가까운가?”만 답한다. threshold(판정 임계값)는 `rerank_score`에만 적용한다. 후보는 있지만 점수가 낮으면 `NO_MATCH`로 숨기지 않고 `EXTRA`로 구분하며, `EXTRA`에도 가장 가까운 표준 후보를 남긴다.

실제 구현에서는 필드명을 구분하는 수준까지 반영했다. 장기적으로는 검색 후보와 재정렬 후보의 타입을 `RetrievedCandidate`와 `RerankedCandidate`처럼 분리해, reranker를 거치지 않은 객체가 판정 함수에 전달되지 않도록 만드는 개선도 가능하다.

## 점수 흐름을 테스트하는 방법

변경 후에는 높은 RRF가 높은 매칭을 보장하지 않는 경로를 고정했다.

```python
def test_threshold_uses_rerank_score_not_fusion_score():
    standard = StandardClause(clause_id="art20")
    candidate = Candidate(
        standard_clause=standard,
        fusion_score=0.99,
        rerank_score=0.10,
    )

    result = classify_clause_deviation(
        matched_standard=candidate.standard_clause,
        score=candidate.rerank_score,
        match_threshold=0.5,
    )

    assert result == Deviation.EXTRA
```

함께 검증할 계약은 다음과 같다.

- 후보가 없으면 `NO_MATCH`
- 후보가 있고 rerank 점수가 threshold 이상이면 `NONE`
- 후보가 있지만 점수가 낮으면 `EXTRA`
- `EXTRA`에도 `matched_standard` 보존
- reranker가 실제 파이프라인에서 호출됨
- 이미 정규화된 모델 점수에 sigmoid를 다시 적용하지 않음

## 평가는 모델 점수가 아니라 질문 단위로 나눴다

“reranker 점수가 높다”는 말만으로는 시스템이 좋아졌다고 판단할 수 없다.

| 질문 | 평가 단위 | 지표 |
| --- | --- | --- |
| 정답 표준조항을 후보에 넣었는가? | 사용자 조항 | 재현율(Recall@k), 평균 역순위(MRR) |
| reranker가 순위를 개선했는가? | 후보 목록 | 재정렬 전후 순위 |
| 매칭 경계가 적절한가? | 사용자 조항 | NONE/EXTRA 혼동행렬 |
| 후보 자체가 없는가? | 사용자 조항 | NO_MATCH 사례 |
| 표준조항이 계약 전체에서 누락됐는가? | 계약 문서 | MISSING 재현율(recall) |

검색 성능이 좋은데 매칭 판정이 무너지는 상황과, 검색은 실패했는데 threshold만 조절하는 상황을 분리하려면 질문 단위 평가가 필요하다.

## 변경 전과 변경 후

| 항목 | 변경 전 | 변경 후 |
| --- | --- | --- |
| 후보 확보 | RRF 검색 | RRF 검색 |
| 재정렬 | 설계상 존재하지만 파이프에서 누락 | 필수 reranker 호출 |
| threshold 입력 | 모호한 `score` | 명시적인 `rerank_score` |
| 후보 없음 | 실패가 `NO_MATCH`로 수렴 | 후보 없음만 `NO_MATCH` |
| 후보 미달 | 근거 없이 `NO_MATCH` | `EXTRA`와 근접 후보 보존 |
| 테스트 fake | 높은 점수 반환 | 점수 출처·호출·범위 검증 |

## 내가 배운 설계 원칙

점수의 값보다 그 점수가 답하는 질문을 먼저 정의해야 한다. RRF는 후보를 모으고, reranker는 후보를 재정렬한다.

threshold는 독립적인 숫자가 아니다. 어떤 점수를 어떤 범위와 변환 상태로 소비하는지까지 포함한 계약이다.

fake는 편리한 숫자를 반환하는 도구가 아니라 실제 어댑터의 계약을 모사해야 한다. 호출되지 않은 reranker 점수를 fake가 제공하면 테스트는 핵심 누락을 숨길 수 있다.

평가는 모델 점수의 크기가 아니라 후보 검색, 재정렬, 매칭 경계, 계약 전체 누락이라는 질문별로 나눠야 한다.

점수의 의미를 설명할 수 없다면 threshold를 튜닝하기 전에 인터페이스를 의심해야 한다. 숫자를 조정하기 전에 그 숫자가 어느 단계의 어떤 질문에 답하는지 고정하는 일이 먼저다.
