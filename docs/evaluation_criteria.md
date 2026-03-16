# Ad Compliance 평가 기준

> 코드베이스 기반 자동 생성 — `shared/constants.py`, `core/decision.py`, `shared/regional_policies/`

---

## Table of Contents

- [1. Campaign Decision (최종 판정)](#1-campaign-decision-최종-판정)
- [2. 평가 축 1: Compliance](#2-평가-축-1-compliance)
- [3. 평가 축 2: Product Relevance](#3-평가-축-2-product-relevance)
- [4. 평가 축 3: Disclosure](#4-평가-축-3-disclosure)
- [5. 지역별 정책 변동](#5-지역별-정책-변동)
- [6. 다국어 지원](#6-다국어-지원)
- [7. 아키텍처 개요](#7-아키텍처-개요)
- [8. Decision Flow 요약](#8-decision-flow-요약)

---

## TL;DR

- **What**: 비디오 광고의 컴플라이언스 위반을 3축(Compliance/Product/Disclosure)으로 평가
- **Why**: 지역별 규제 차이를 반영한 자동화된 광고 심사 기준 제공
- **How**: AI 모델 분석 → 5개 정책 카테고리 검사 → 지역별 severity 상향 → 최종 판정
- **Key**: Global 지역은 모든 지역 중 가장 엄격한 기준 적용, BLOCK > REVIEW > APPROVE 우선순위

---

## 1. Campaign Decision (최종 판정)

모든 비디오는 단일 캠페인 판정을 받습니다: **APPROVE**, **REVIEW**, 또는 **BLOCK**.

이 판정은 3개의 독립적인 평가 축에서 도출됩니다:

| 판정 | 조건 |
| --- | --- |
| **BLOCK** | 명확한 컴플라이언스 위반 감지 (HIGH 또는 CRITICAL severity) |
| **REVIEW** | 컴플라이언스 위반 불확실 (LOW 또는 MEDIUM severity) |
|  | 제품이 적절히 광고되지 않음 (off-brief, borderline, not visible) |
|  | 광고 공개 표시 누락 |
| **APPROVE** | 컴플라이언스 이슈 없음 + 제품 on-brief + disclosure 존재 |

판정 우선순위: BLOCK > REVIEW > APPROVE. 어떤 축이든 REVIEW를 트리거하고 BLOCK이 없으면 최종 판정은 REVIEW입니다.

---

## 2. 평가 축 1: Compliance

5개 정책 카테고리에 대해 콘텐츠를 평가합니다. **Disclosure는 제외**되며 별도 축(Axis 3)에서 평가합니다.

### 2.1 Severity 레벨

| Severity | 우선순위 | Compliance 결과 |
| --- | --- | --- |
| **CRITICAL** | 4 | BLOCK |
| **HIGH** | 3 | BLOCK |
| **MEDIUM** | 2 | REVIEW |
| **LOW** | 1 | REVIEW |
| **NONE** | 0 | PASS |

감지된 모든 위반 중 **가장 높은 severity**가 compliance 결과를 결정합니다. 지역 정책은 severity를 **상향만** 가능합니다 (하향 불가).

### 2.2 정책 카테고리

#### 2.2.1 Hate & Harassment (`hate_harassment`)

보호 대상 특성에 기반한 차별, 혐오, 비하를 조장하는 콘텐츠입니다.

| 하위 카테고리 | 설명 |
| --- | --- |
| 인종/민족 비하 | 인종 비하 발언, 민족 비하 용어 |
| 성별 차별 | 성별 기반 차별, 성차별적 언어 |
| 외모/신체 비하 | 외모 비하, 체형 조롱, 장애 조롱 |
| 피부톤 우월주의 | 밝은 피부가 "더 좋다"는 암시 |
| 괴롭힘/희롱 | 모든 형태의 괴롭힘 또는 희롱 |

#### 2.2.2 Profanity & Explicit Content (`profanity_explicit`)

| 하위 카테고리 | 설명 |
| --- | --- |
| 강한 비속어 | F-word, C-word 및 모든 언어의 동등 표현 |
| 약한 비속어 | damn, hell, crap, ass 및 동등 표현 |
| 성적 콘텐츠 | 성적으로 노골적이거나 암시적인 콘텐츠 |
| 저속한 콘텐츠 | 저속하거나 조잡한 언어 |

다국어 감지: 한국어 (씨발, 젠장), 일본어 (ファック, くそ), 중국어 (他妈的, 该死).

#### 2.2.3 Drugs & Illegal Activity (`drugs_illegal`)

| 하위 카테고리 | 설명 |
| --- | --- |
| 불법 약물 | 약물 사용, 약물 도구, 약물 언급 |
| 대마/CBD | 대마초, 마리화나, CBD 제품 사용 또는 홍보 |
| 처방약 오용 | 처방약 오용 또는 홍보 |
| 알코올 미화 | 과도한 음주 또는 알코올 미화 |

#### 2.2.4 Unsafe & Misleading Usage (`unsafe_misleading_usage`)

| 하위 카테고리 | 설명 |
| --- | --- |
| 눈 주변 오용 | 눈 안전 인증 없는 제품을 눈 주변에 사용 |
| DIY 화장품 | 안전 경고 없는 DIY 화장품 |
| 허위 비포/애프터 | 비교 이미지에서 명백한 디지털 보정 |
| 금지/제한 성분 | 금지 또는 제한 물질이 포함된 제품 |
| 과도한 보정 | 과도한 피부 보정, 체형 변형 필터 |

#### 2.2.5 Medical & Cosmetic Claims (`medical_cosmetic_claims`)

| 하위 카테고리 | 설명 |
| --- | --- |
| 약품 주장 | "치료한다", "낫게 한다", "주름을 제거한다" |
| 허위 규제 주장 | 화장품에 "FDA 승인" (FDA는 화장품을 승인하지 않음) |
| 근거 없는 효능 | 연구 인용 없이 "임상적으로 입증됨" |
| 절대적 주장 | "100% 효과", "결과 보장" |
| 코스메슈티컬 주장 | "코스메슈티컬", "약용 화장품" |
| 미백 주장 | 화장품 범위를 초과하는 미백 주장 |
| 천연/유기농 주장 | 인증 없이 "100% 천연/유기농" |

---

## 3. 평가 축 2: Product Relevance

비디오가 의도된 제품(뷰티/화장품 캠페인)을 적절히 광고하는지 평가합니다.

| 상태 | 조건 | 캠페인 판정 |
| --- | --- | --- |
| **ON_BRIEF** | 제품이 명확히 식별되고 사용/시연됨 | (이슈 없음) |
| **BORDERLINE** | 부분적으로 관련, 제품이 두드러지지 않음 | REVIEW |
| **NOT_VISIBLE** | 일부 관련성에도 제품이 시각적으로 보이지 않음 | REVIEW |
| **OFF_BRIEF** | 광고 제품과 무관한 비디오 (클릭베이트 등) | REVIEW |

평가는 AI 모델의 라벨 (`ON_BRIEF` / `OFF_BRIEF` / `BORDERLINE`)과 `product_visible` 플래그, `relevance_score` (0.0~1.0)를 조합하여 수행합니다.

Relevance 임계값: **0.5** (이 값 미만은 BORDERLINE/OFF_BRIEF 경향).

---

## 4. 평가 축 3: Disclosure

비디오에 적절한 광고 공개 라벨이 포함되어 있는지 평가합니다.

| 상태 | 조건 | 캠페인 판정 |
| --- | --- | --- |
| **PRESENT** | 광고 공개 라벨 발견 또는 불필요 | (이슈 없음) |
| **MISSING** | 광고 공개 미감지 | REVIEW |

### 감지 방법

1. **위반 결과** — 모델이 disclosure 위반을 명시적으로 플래그
2. **Severity 전용** — 모델이 상세 위반 없이 disclosure 카테고리에 severity 부여
3. **설명 분석** — 비디오 설명 텍스트에서 키워드 감지:
   - "no disclosure", "lacks disclosure", "missing disclosure"
   - "no #ad", "missing #ad", "undisclosed"
   - "without disclosure", "without any disclosure"

### 지역별 허용 Disclosure 라벨

| 지역 | 허용 라벨 |
| --- | --- |
| Global | `#ad`, `Ad`, `Advertisement`, `Paid partnership` |
| North America | `#ad`, `Paid partnership`, `Sponsored` |
| Western Europe | `#ad`, `Ad`, `Advertisement` 만 허용 (UK: `#sponsored`는 **불충분**) |
| East Asia (KR) | `유료광고`, `광고포함`, `#ad` |
| East Asia (JP) | `PR`, `広告`, `#ad` |
| East Asia (CN) | `广告`, `#ad` |

---

## 5. 지역별 정책 변동

AI 모델의 기본 severity는 지역별 정책에 의해 **상향**될 수 있습니다. 각 지역은 고유한 규제 프레임워크와 severity 오버라이드를 정의합니다.

### 5.1 North America

**규제 기관:** FTC, FDA, MoCRA (2023), Ad Standards Canada

| 카테고리 | 기본 Severity | 주요 규칙 |
| --- | --- | --- |
| hate_harassment | CRITICAL | 보호 대상: 인종, 피부색, 종교, 성별, 출신국, 장애, 연령 |
| profanity_explicit | HIGH | 강한 비속어 = CRITICAL, 약한 비속어 = MEDIUM |
| drugs_illegal | CRITICAL | 대마: 연방법상 Schedule I; CBD 광고 제한 |
| unsafe_misleading | HIGH | MoCRA (2023): 부작용 보고 의무화 |
| medical_cosmetic_claims | HIGH | 약품 주장 = CRITICAL; 화장품 "FDA 승인" = CRITICAL |
| disclosure | MEDIUM | FTC Endorsement Guide (2023): 위반 시 최대 $50,000 벌금 |

### 5.2 Western Europe

**규제 기관:** EU Cosmetics Regulation (EC 1223/2009), ASA (UK), ARPP (France), EU Unfair Commercial Practices Directive

| 카테고리 | 기본 Severity | 주요 규칙 |
| --- | --- | --- |
| hate_harassment | CRITICAL | DE: Volksverhetzung법; FR: 인종 차별 = 형사 처벌; ASA: 성별 고정관념 금지 (2019) |
| profanity_explicit | HIGH | ASA: 'generally offensive' 기준 |
| drugs_illegal | CRITICAL | CBD: Novel Food Regulation (EU 2015/2283) 광고 제한 |
| unsafe_misleading | HIGH | ASA: 보정된 비포/애프터 금지 (L'Oreal, Maybelline 판례); EU CPSR 의무 |
| medical_cosmetic_claims | HIGH | EU 6 Common Criteria; 근거 없이 "임상 입증" = HIGH |
| disclosure | HIGH | ASA: `#ad`/`Ad`/`Advertisement`만 허용; `#sponsored`는 **부적절** 판정 |

### 5.3 East Asia

**규제 기관:** Korea MFDS/KFTC, Japan PMDA/Yakujiho/JARO, China NMPA/NRTA

| 카테고리 | 기본 Severity | 주요 규칙 |
| --- | --- | --- |
| hate_harassment | CRITICAL | CN: 민족 단결 훼손 = 형사 처벌; KR: 외모 차별 규제 |
| profanity_explicit | HIGH | **가장 엄격한 지역**: 약한 비속어 = HIGH (MEDIUM 아님); CN: 광범위한 "저속 콘텐츠" 금지 |
| drugs_illegal | CRITICAL | 3개국 모두 **무관용 원칙** |
| unsafe_misleading | HIGH | CN 2021: 모든 수입 화장품 등록 의무 |
| medical_cosmetic_claims | HIGH | CN: 절대적 표현 금지, 의학 용어 금지, '药妆' 명시적 금지; KR: 기능성 화장품 MFDS 승인 필요; JP: 56개 허용 표현만 가능 |
| disclosure | MEDIUM | KR: KFTC '뒷광고' 과징금; JP: 스텔스 마케팅 금지 (2023.10~); CN: 광고법 제14조 |

### 5.4 지역별 Severity 비교

Global은 각 카테고리에 대해 **모든 지역 중 가장 엄격한 severity**를 적용하여, Global-safe로 표시된 콘텐츠가 모든 시장에서 안전하도록 보장합니다.

| 카테고리 | Global (최엄격) | North America | Western Europe | East Asia |
| --- | --- | --- | --- | --- |
| hate_harassment | CRITICAL | CRITICAL | CRITICAL | CRITICAL |
| profanity (강한) | CRITICAL | CRITICAL | CRITICAL | CRITICAL |
| profanity (약한) | **HIGH** | MEDIUM | MEDIUM | **HIGH** |
| drugs_illegal | CRITICAL | CRITICAL | CRITICAL | CRITICAL |
| cannabis/CBD | **CRITICAL** | HIGH | HIGH | **CRITICAL** |
| unsafe_misleading | HIGH | HIGH | HIGH | HIGH |
| 보정된 비포/애프터 | **HIGH** | MEDIUM | **HIGH** | MEDIUM |
| 의학적 약품 주장 | CRITICAL | CRITICAL | CRITICAL | CRITICAL |
| 근거 없는 효능 | **HIGH** | MEDIUM | **HIGH** | HIGH |
| 절대적 주장 | **CRITICAL** | HIGH | HIGH | **CRITICAL** |
| 코스메슈티컬 용어 | HIGH | HIGH | HIGH | HIGH |
| disclosure (누락) | **HIGH** | MEDIUM | **HIGH** | MEDIUM |

주요 엄격도 차이는 **굵게** 표시되어 있습니다.

---

## 6. 다국어 지원

### 출력 언어

- 모든 `description` 및 `evidence` 필드는 **영어**로 작성됩니다
- 원본 비디오 언어가 영어가 아닌 경우, 원어 텍스트가 `evidence_original`에 제공됩니다

### 예시

```json
{
  "description": "The video claims the cream cures acne completely",
  "evidence": "This cream cures acne and removes all blemishes",
  "evidence_original": "이 크림은 여드름을 완치하고 모든 잡티를 제거합니다"
}
```

### 감지 언어

- 한국어: 씨발, 젠장, 유료광고, 미백, 뒷광고, 외모 비하
- 일본어: ファック, くそ, 広告, 薬機法, シミを消す
- 중국어: 他妈的, 该死, 广告, 药妆, 美白, 100%有效

---

## 7. 아키텍처 개요

두 가지 배포 형태를 지원합니다:

- **Streamlit 로컬 앱**: 로컬 개발/데모용, 동기 처리 (최대 5분)
- **AWS Amplify 프로덕션 앱**: React SPA + API Gateway + Lambda, 비동기 처리 (최대 15분)

```text
Video Upload (S3 presigned URL)
    │
    ▼
┌─────────────────────────────┐
│  Dispatcher Lambda (30s)     │
│  → Jobs 테이블 PENDING 저장  │
│  → Worker Lambda 비동기 호출 │
│  → HTTP 202 {jobId} 반환     │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│  Worker Lambda (900s)        │
│  Bedrock / TwelveLabs        │
│                              │
│  단일 API 호출로 반환:       │
│  - relevance 평가            │
│  - 비디오 설명               │
│  - 6개 정책 위반 검사        │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│  Decision Engine             │
│                              │
│  축 1: Compliance            │
│  (5개 카테고리, disclosure   │
│   제외)                      │
│  + 지역별 severity 상향      │
│                              │
│  축 2: Product Relevance     │
│  (on-brief / off-brief)      │
│                              │
│  축 3: Disclosure            │
│  (광고 라벨 검사)            │
│                              │
│  ─────────────────────────── │
│  최종: APPROVE/REVIEW/BLOCK  │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│  DynamoDB                    │
│  Reports + Jobs 테이블 저장  │
└─────────────────────────────┘
```

---

## 8. Decision Flow 요약

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
