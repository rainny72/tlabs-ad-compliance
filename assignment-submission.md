# Ad Compliance & Brand Safety — Submission

## Project Overview

비디오 광고 컴플라이언스 자동 검토 시스템입니다. TwelveLabs Pegasus 1.2 또는 Amazon Bedrock을 통해 단일 API 호출로 영상을 분석하고, 구조화된 컴플라이언스 리포트를 생성합니다.

**Live Demo:** [AWS Amplify Demo](https://main.d1mjnmpj9lc6js.amplifyapp.com/)
**Local Demo:** `streamlit run app/dashboard.py`
**Repository:** [github.com/rainny72/tlabs-ad-compliance](https://github.com/rainny72/tlabs-ad-compliance)
**Demo Video:** [ad-compliance-demo-2x.mp4](demo/ad-compliance-demo-2x.mp4)

---

## Table of Contents

1. [How Decisions Are Made](#1-how-decisions-are-made)
2. [Why Outputs Are Trustworthy](#2-why-outputs-are-trustworthy)
3. [How This Would Scale](#3-how-this-would-scale-in-a-real-ads-system)
4. [Appendix: 프로덕션 구현 예시](#appendix-프로덕션-구현-예시)

---

## 1. How Decisions Are Made

### 1.1 단일 API 호출 기반 분석

비디오 분석은 TwelveLabs Pegasus 1.2 모델에 대한 **단일 API 호출**로 수행됩니다. 하나의 호출에서 다음 정보를 모두 요구합니다:

| 요구 정보 | 설명 | 출력 필드 |
| --- | --- | --- |
| Campaign Relevance | 제품이 적절히 광고되는지 평가 | `relevance_score`, `is_on_brief`, `product_visible` |
| Video Description | 영상 내용 2-5문장 팩트 기반 요약 | `description` |
| Policy Violations | 6개 정책 카테고리별 위반 검사 | `policy_violations` (카테고리별 `severity`, `violations[]`) |

이 설계의 핵심 이점은 비디오를 한 번만 처리하므로 API 비용이 선형적이고, 단일 context에서 분석하여 카테고리 간 일관성이 유지된다는 점입니다.

### 1.2 3축 평가 시스템

AI 모델의 응답은 3개의 독립적인 축으로 평가됩니다:

```text
Video → Pegasus 1.2 / Bedrock (단일 API 호출) → Structured JSON
                                              │
                    ┌─────────────────────────┼──────────────────────────┐
                    ▼                         ▼                          ▼
            축 1: Compliance          축 2: Product              축 3: Disclosure
            (5개 카테고리,            (캠페인 관련성)            (광고 라벨)
             disclosure 제외)
                    │                         │                          │
                    ▼                         ▼                          ▼
            PASS / REVIEW / BLOCK     ON-BRIEF / BORDERLINE     PRESENT / MISSING
                                      / NOT_VISIBLE / OFF_BRIEF
                    │                         │                          │
                    └─────────────────────────┼──────────────────────────┘
                                              ▼
                                   APPROVE / REVIEW / BLOCK
```

**축 1: Compliance** — 5개 정책 카테고리(`hate_harassment`, `profanity_explicit`, `drugs_illegal`, `unsafe_misleading_usage`, `medical_cosmetic_claims`)에 대해 위반을 검사합니다. 각 위반에는 severity(CRITICAL/HIGH/MEDIUM/LOW/NONE)가 부여되며, 감지된 모든 위반 중 가장 높은 severity가 compliance 결과를 결정합니다.

| Severity | Compliance 결과 |
| --- | --- |
| CRITICAL / HIGH | BLOCK |
| MEDIUM / LOW | REVIEW |
| NONE | PASS |

**축 2: Product Relevance** — AI 모델이 반환한 `relevance_score`(0.0~1.0), `is_on_brief`, `product_visible` 플래그를 조합하여 평가합니다. 임계값 0.5 미만이면 BORDERLINE/OFF_BRIEF로 분류되어 REVIEW를 트리거합니다.

**축 3: Disclosure** — 광고 공개 라벨(`#ad`, `유료광고`, `広告` 등)의 존재 여부를 검사합니다. 모델의 위반 플래그, severity 전용 감지, 비디오 설명 텍스트의 키워드 분석 등 3가지 방법으로 감지합니다.

### 1.3 최종 판정 규칙

판정 우선순위는 BLOCK > REVIEW > APPROVE입니다:

```text
START
  │
  ├─ Compliance 위반 (HIGH/CRITICAL)?
  │    YES → BLOCK
  │
  ├─ Compliance 위반 (LOW/MEDIUM)?
  │    YES → REVIEW (사유: 컴플라이언스 우려)
  │
  ├─ 제품이 ON_BRIEF가 아닌가?
  │    YES → REVIEW (사유: off-brief / borderline / not visible)
  │
  ├─ Disclosure MISSING?
  │    YES → REVIEW (사유: disclosure 누락)
  │
  └─ 모두 통과 → APPROVE
```

복수의 REVIEW 사유는 결합됩니다 (예: "REVIEW: Product: OFF-BRIEF | Disclosure: MISSING").

### 1.4 3단계 지역별 Severity 보정

지역별 규제 차이를 반영하기 위해 3단계 보정 메커니즘을 적용합니다:

```text
[1단계] 프롬프트 지역 context 주입
  get_regional_prompt(region) → 모델이 지역 규제를 인식하고 severity 판단
  예: East Asia + cannabis → 모델이 "ZERO TOLERANCE" 지시를 보고 "critical" 반환

[2단계] Sub-rule 키워드 매칭
  _match_sub_rule() → violation evidence 텍스트를 regional policy keywords와 매칭
  예: "cannabis CBD" → east_asia의 "illegal_drugs" sub-rule 매칭 (CRITICAL)

[3단계] Severity 상향 조정 (upgrade only, 하향 불가)
  get_regional_severity() → 매칭된 sub-rule severity가 모델 severity보다 높으면 상향
  예: 모델이 "high" 반환 + east_asia sub-rule "CRITICAL" → CRITICAL로 상향
```

이 접근의 장점:

- 1단계에서 모델이 지역 맥락을 이해하여 감지 누락 방지
- 2단계에서 코드 레벨 세부 규칙 매칭으로 정밀한 severity 적용
- 3단계에서 모델의 과소 평가를 regional policy로 안전망 보정

Global 지역은 모든 지역 중 가장 엄격한 severity를 적용하여, Global-safe 콘텐츠가 모든 시장에서 안전하도록 보장합니다.

---

## 2. Why Outputs Are Trustworthy

출력의 신뢰성은 일관된 응답 생성, 구조화된 출력 강제, 다층 검증 메커니즘의 세 가지 축으로 확보합니다.

### 2.1 결정적 출력을 위한 API Parameter 설정

| Parameter | 값 | 목적 |
| --- | --- | --- |
| `temperature` | 0.1 | 동일 영상에 대한 비결정적 결과 최소화 |
| `maxOutputTokens` | 4,096 | Pegasus 최대값으로 응답 truncation 방지 |
| `responseFormat` | JSON Schema | 구조화된 출력 강제, 자유 텍스트 배제 |
| `stream` | false | 완전한 응답을 한 번에 수신 |

Temperature 0.1은 TwelveLabs 공식 Temperature Tuning Guide에서 "법 집행, 보고서" 용도로 권장하는 가장 결정적인 설정입니다. 컴플라이언스 분석은 동일 영상에 대해 실행할 때마다 동일한 결과를 반환해야 하므로, 창의성보다 일관성을 우선합니다. 또한 단일 API 호출 설계로 비결정성이 1회만 발생하며, 단일 context 내에서 카테고리 간 상호참조가 가능하여 일관된 분석 결과를 보장합니다.

### 2.2 JSON Schema 기반 구조화된 출력

TwelveLabs의 Structured Responses 가이드의 핵심 원칙을 적용합니다:

> "The schema takes precedence over the prompt." — 스키마와 프롬프트가 불일치하면 스키마를 따른다.

이 원칙에 따라 `COMBINED_JSON_SCHEMA`로 출력 구조를 강제합니다:

- 6개 정책 카테고리 모두 `required`로 지정하여 누락 방지
- `severity`를 `enum [none|low|medium|high|critical]`로 제한하여 임의 값 배제
- `modality`를 `enum [visual|speech|text_on_screen]`으로 제한하여 감지 채널 명확화
- `relevance_score`를 `number (0.0-1.0)`로 정의하여 정량적 평가 보장

스키마와 프롬프트의 출력 지시를 정확히 일치시켜, 모델이 스키마를 따르면서도 프롬프트의 의도를 반영하도록 설계했습니다.

### 2.3 프롬프트 엔지니어링을 통한 일관성 확보

TwelveLabs 공식 Prompt Engineering Guide의 8가지 베스트 프랙티스를 체계적으로 적용합니다:

**역할 및 도메인 컨텍스트 설정** — 일반적인 "content moderator" 대신 FTC, ASA, EU Cosmetics Regulation, MFDS, Yakujiho, NMPA 등 구체적인 규제 기관을 명시하여 모델의 도메인 지식을 활성화합니다.

**Severity 분류 가이드 명시** — 단순히 severity enum만 제공하는 대신, 각 레벨의 의미를 명확히 정의합니다:

- `critical`: 즉각적인 규제 조치 또는 법적 책임을 유발하는 콘텐츠
- `high`: 명확한 정책 위반으로 콘텐츠 제거가 필요한 경우
- `medium`: 경계선 콘텐츠로 인간 리뷰가 필요한 경우
- `low`: 경미한 우려, 규제 이슈 가능성 낮음

**카테고리별 severity 매핑** — 각 위반 유형에 대해 기대되는 severity를 프롬프트에 직접 명시합니다 (예: `"FDA approved" for cosmetics → critical`). 이를 통해 모델이 동일한 위반에 대해 일관된 severity를 반환하도록 유도합니다.

### 2.4 다층 검증 메커니즘

모델 출력의 신뢰성을 코드 레벨에서 추가로 검증합니다:

**Truncation 감지** — API 응답의 `finishReason` 필드를 확인하여, `"length"`인 경우 응답이 잘렸음을 경고합니다. 잘린 응답은 불완전한 JSON을 포함할 수 있으므로 즉시 감지합니다.

**Regional Policy 안전망** — 모델이 지역별 규제를 과소 평가하더라도, 코드 레벨의 `_match_sub_rule()` + `get_regional_severity()`가 evidence 텍스트를 regional policy keywords와 매칭하여 severity를 상향 보정합니다. 이 보정은 상향만 가능(하향 불가)하여 false negative를 방지합니다.

**Disclosure 다중 감지** — Disclosure 누락은 단일 방법에 의존하지 않고 3가지 경로로 감지합니다:

1. 모델의 명시적 위반 플래그
2. Severity 전용 감지 (상세 위반 없이 severity만 부여된 경우)
3. 비디오 설명 텍스트의 키워드 분석 ("no disclosure", "missing #ad" 등)

---

## 3. How This Would Scale in a Real Ads System

### 3.1 실제 광고 시스템의 규모 요구사항

대형 광고 플랫폼은 하루 수십만~수백만 건의 광고 콘텐츠를 처리해야 합니다. 이를 위해 다음과 같은 확장 요구사항이 존재합니다:

| 요구사항 | 현재 시스템 | 프로덕션 확장 |
| --- | --- | --- |
| 일일 처리량 | 수십 건 (데모) | 수십만~수백만 건 |
| 응답 시간 | 10-60초/건 | SLA 기반 (우선순위별 차등) |
| 지역 정책 | 4개 지역 (코드) | 수십 개 지역 (Policy DB) |
| 리뷰 워크플로우 | 대시보드 표시 | 티어별 자동 라우팅 |
| 모니터링 | CloudWatch Logs | 실시간 메트릭 + 드리프트 감지 |

### 3.2 확장 아키텍처 설계

현재 시스템의 핵심 설계 원칙이 대규모 확장을 자연스럽게 지원합니다:

**단일 API 호출 = 선형 비용 확장** — 비디오당 1회 호출로 모든 분석을 완료하므로, 처리량이 10배 증가해도 비용이 10배만 증가합니다. 카테고리별 개별 호출(8회) 대비 비용 효율이 8배 높습니다.

**상태 없는 워커 = 수평 확장** — Worker는 상태를 보유하지 않으므로, 동시 실행 수를 늘리는 것만으로 처리량을 확장할 수 있습니다. 워커 간 조정 오버헤드가 없습니다.

**정책 as 코드 = 모델 재학습 불필요** — 새로운 지역이나 규제가 추가될 때 정책 파일만 추가하면 됩니다. AI 모델을 재학습하거나 재배포할 필요가 없습니다.

프로덕션 확장 시 다음과 같은 아키텍처로 진화할 수 있습니다:

```text
Ad Platform API → SQS Queue → Worker Fleet → Results DB → Review Dashboard
                      │
                 ┌────┴────┐
                 │ Worker 1 │  (Bedrock API call)
                 │ Worker 2 │  (Bedrock API call)
                 │ Worker N │  (Bedrock API call)
                 └──────────┘
```

### 3.3 티어별 처리 전략

실제 광고 시스템에서는 모든 콘텐츠를 동일하게 처리하지 않습니다. 판정 결과에 따라 차등 처리합니다:

| 티어 | 판정 | 처리 방식 | 예상 비율 |
| --- | --- | --- | --- |
| Auto-approve | APPROVE (높은 confidence) | 자동 승인, 인간 리뷰 불필요 | 60-70% |
| Auto-block | BLOCK (CRITICAL severity) | 자동 차단, 광고주 알림 | 5-10% |
| Human review | REVIEW | 리뷰어 큐에 라우팅 | 20-35% |

이 티어 분류를 통해 인간 리뷰어의 부담을 60-70% 줄이면서도, 위험한 콘텐츠는 즉시 차단할 수 있습니다.

### 3.4 품질 관리와 Human-in-the-Loop

시스템의 핵심 목표는 Ads Compliance 팀의 리뷰를 자동화하는 것입니다. 하루 수십만 건의 광고를 처리하려면 AI가 1차 판정을 자동으로 수행하고, 판정 근거를 명확히 제공해야 합니다. Human-in-the-Loop는 전수 리뷰가 아닌, 모델 품질을 지속적으로 검증하고 개선하기 위한 샘플링 기반 감사(audit) 역할을 합니다.

```text
AI 자동 판정 (100%)
  ├─ APPROVE (60-70%) → 자동 승인
  ├─ BLOCK (5-10%)    → 자동 차단 + 판정 근거 제공
  └─ REVIEW (20-35%)  → 판정 근거와 함께 큐에 라우팅
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
            샘플링 감사 (QA)     에스컬레이션 리뷰
            (무작위 추출,        (경계선 케이스,
             정확도 측정)         광고주 이의 제기)
                    │                   │
                    └─────────┬─────────┘
                              ▼
                    피드백 → 프롬프트/정책 보정
```

**자동 판정 + 판정 근거 제공** — BLOCK/REVIEW 판정 시 위반 카테고리, severity, evidence(감지 modality와 구체적 내용)를 구조화된 형태로 제공합니다. 이는 "Clear explanations for any blocked or reviewed ads" 요구사항을 충족하며, 광고주가 차단/리뷰 사유를 즉시 확인할 수 있게 합니다.

**샘플링 기반 품질 감사** — 전체 판정 중 일정 비율을 무작위 추출하여 인간 감사자가 검증합니다. 오탐(false positive)과 미탐(false negative) 비율을 측정하고, 특정 카테고리의 정확도가 임계값 이하로 떨어지면 프롬프트 또는 regional policy를 조정합니다.

**드리프트 감지** — 시간에 따른 판정 분포(APPROVE/REVIEW/BLOCK 비율) 변화를 추적합니다. 분포가 급변하면 모델 동작 변화 또는 새로운 유형의 콘텐츠 유입을 의미하며, 정책 조정이 필요한 시점을 알려줍니다.

**지역별 정책 업데이트** — 규제 변경 시 정책 파일만 업데이트하면 즉시 반영됩니다. 코드 기반 정책 관리(`shared/regional_policies/`)를 Policy DB + Admin UI로 확장하면, 컴플라이언스 담당자가 직접 정책을 관리할 수 있습니다.

### 3.5 Serverless 아키텍처 기반 확장 방향

현재 데모 시스템의 Serverless 구조를 기반으로, 대규모 확장 시 다음과 같은 방향으로 진화할 수 있습니다:

```text
현재:  API Gateway → Dispatcher Lambda → Worker Lambda → DynamoDB
확장:  API Gateway → Dispatcher Lambda → SQS Queue → Worker Lambda Fleet
                                              │
                                         Dead Letter Queue
                                         (실패 작업 재처리)
```

- **SQS Queue 도입**: Dispatcher가 직접 Worker를 호출하는 대신 SQS에 메시지를 발행하여 배압(backpressure) 제어와 재시도를 자동으로 처리
- **Reserved Concurrency**: Worker Lambda의 동시 실행 수를 제한하여 Bedrock API 호출 한도를 초과하지 않도록 제어
- **Dead Letter Queue**: 분석 실패 시 DLQ에 저장하여 재처리하거나 수동 검토
- **Step Functions**: 복잡한 워크플로우(분석 → 리뷰 라우팅 → 알림)를 오케스트레이션

이 Serverless 아키텍처의 핵심 이점은 인프라 관리 부담 없이 트래픽에 따라 자동으로 확장/축소되며, 사용한 만큼만 비용을 지불한다는 점입니다.

---

## Appendix: 프로덕션 구현 예시

> 설계 사고를 검증하기 위해 실제 프로덕션 배포를 구현했습니다. 시스템 아키텍처, 보안 설계, CDK 인프라 등 상세 내용은 아래 문서를 참조하세요.

상세 문서: [Application Architecture](docs/application_architecture.md) — 이중 배포 구조(Streamlit/Amplify), Dispatcher/Worker 비동기 패턴, CDK 인프라 스택, Lambda 함수 구조, 보안 설계(Cognito 인증, S3 퍼블릭 차단, 최소 권한 원칙) 포함

---
