# Prompt Engineering — TwelveLabs Pegasus 1.2 for Ad Compliance

> TwelveLabs 공식 가이드의 베스트 프랙티스를 기반으로 설계된
> 비디오 광고 컴플라이언스 평가 프롬프트의 설계 분석 문서.

---

## Table of Contents

1. [Overview](#1-overview)
2. [TwelveLabs Best Practices 적용](#2-twelvelabs-best-practices-적용)
3. [Combined Prompt — 최종 버전](#3-combined-prompt--최종-버전)
4. [카테고리별 프롬프트 설계](#4-카테고리별-프롬프트-설계)
5. [JSON Schema Design](#5-json-schema-design)
6. [Model Interaction Flow](#6-model-interaction-flow)
7. [Prompt Design Decisions](#7-prompt-design-decisions)
8. [Individual Prompts (Legacy)](#8-individual-prompts-legacy)
9. [References](#9-references)

---

## 1. Overview

이 프로젝트는 TwelveLabs Pegasus 1.2 모델을 사용하여 비디오 광고의 컴플라이언스를 평가합니다. **단일 API 호출**로 영상 분석의 모든 결과를 구조화된 JSON으로 반환받는 것이 핵심 설계입니다.

### Model Specifications

| 항목 | 값 | 근거 |
|------|-----|------|
| Model | TwelveLabs Pegasus 1.2 | Multimodal video-to-text model |
| Video Input | 4초 ~ 1시간, max 2GB | Pegasus 공식 제약 |
| Output | Structured JSON (schema constraint) | `responseFormat.jsonSchema` |
| Temperature | 0.1 | 결정적 결과 우선 (v4.0에서 0.2→0.1 하향) |
| Max Output Tokens | 4,096 | Pegasus 최대값 |
| Language Support | English (full), KR/JP/CN/etc. (partial) | 공식 문서 기준 |

### Why Single-Call Design?

| 측면 | 개별 호출 (8 calls) | 통합 호출 (1 call) |
|------|---------------------|-------------------|
| API 비용 | 8x video processing | 1x video processing |
| 지연 시간 | 80-240초 | 10-60초 |
| 일관성 | 호출 간 context 불일치 가능 | 단일 context에서 일관된 분석 |
| TwelveLabs 일일 한도 | 6 video/day (50 req limit) | 50 video/day |

---

## 2. TwelveLabs Best Practices 적용

TwelveLabs 공식 [Prompt Engineering Guide](https://docs.twelvelabs.io/docs/guides/analyze-videos/prompt-engineering)의 8가지 베스트 프랙티스를 프롬프트에 적용한 내역:

### 2.1 Provide Context

**가이드:** 관련 배경 정보를 포함하여 정확한 응답을 유도한다.

**적용:**
```
"You are an expert ad compliance reviewer specializing in global beauty
and cosmetics advertising regulations, including FTC (US), ASA (UK),
EU Cosmetics Regulation, and East Asian standards (Korea MFDS, Japan
Yakujiho, China NMPA)."
```

화장품 업계의 주요 규제 기관을 명시적으로 나열하여 모델에 도메인 컨텍스트를 제공합니다. 일반적인 "content moderator" 대신 규제 전문가 역할을 부여합니다.

### 2.2 Be Specific

**가이드:** 분석할 비디오 측면을 정확히 명시하여 targeted 응답을 생성한다.

**적용:** 각 위반 카테고리에 구체적인 감지 항목과 severity 기준을 명시합니다:

```
### medical_cosmetic_claims
- Drug claims: "cures", "treats", "heals", "removes wrinkles" → critical
- False regulatory claims: "FDA approved" for cosmetics → critical
- Unsubstantiated efficacy: "clinically proven" without citing studies → high
```

기존 프롬프트는 감지 항목만 나열했으나, 개선된 버전은 **항목별 severity 기준**까지 명시하여 모델의 판단 일관성을 향상시킵니다.

### 2.3 Specify Format & Style

**가이드:** 원하는 길이, 스타일, 형식(JSON, 이메일 등)을 명확히 지정한다.

**적용:** TwelveLabs의 [Structured Responses](https://docs.twelvelabs.io/docs/guides/analyze-videos/structured-responses) 가이드에 따라 JSON Schema로 출력을 강제합니다.

> **"The schema takes precedence over the prompt."** — 스키마와 프롬프트가 불일치하면 스키마를 따른다.

이 원칙에 따라 프롬프트의 출력 지시와 `COMBINED_JSON_SCHEMA`의 구조를 정확히 일치시킵니다.

### 2.4 Choose Language

**가이드:** 필요 시 출력 언어를 명시적으로 지정한다.

**적용:**
```
- description: English explanation of the violation
- evidence: exact quote or visual description in English
- evidence_original: original-language text if non-English (omit if English)
```

영어를 기본 출력 언어로 지정하고, 비영어 콘텐츠는 `evidence_original` 필드에 원어를 보존합니다. Pegasus는 영어에 대해 full support, 한국어/일본어/중국어에 partial support를 제공합니다.

### 2.5 Tune Temperature

**가이드:** 정확성 중심 작업에는 낮은 temperature, 창의적 작업에는 높은 temperature를 사용한다.

**적용:** Temperature **0.1** 사용 (v4.0에서 0.2→0.1 하향).

[Temperature Tuning Guide](https://docs.twelvelabs.io/docs/guides/analyze-videos/tune-the-temperature)에 따르면:

- **0.1: focused, structured summaries (법 집행, 보고서)** ← 현재 설정
- 0.2: balanced accuracy with moderate variation
- 0.9: imaginative interpretations, creative elaboration

컴플라이언스 분석은 일관성과 정확성이 최우선이며, 동일 영상에 대한 비결정적 결과를 최소화하기 위해 0.1로 하향 조정.

### 2.6 Be Concise

**가이드:** 핵심 정보에 집중하여 처리 속도와 정밀도를 향상시킨다.

**적용:** 통합 프롬프트에서 불필요한 반복을 제거하고, 각 카테고리의 감지 항목을 bullet point로 간결하게 정리합니다. 출력 규칙은 프롬프트 끝에 한 번만 명시합니다.

### 2.7 Provide Examples

**가이드:** 참조 출력 예시를 제공하여 모호함을 줄인다.

**적용:** 각 카테고리에 구체적인 위반 예시를 포함합니다:
- `"cures", "treats", "heals"` — 약품 주장의 구체적 예시
- `"FDA approved" for cosmetics` — 허위 규제 주장 예시
- `씨발, 지랄` (Korean), `くそ, ファック` (Japanese) — 다국어 비속어 예시

### 2.8 Choose Prompt Type

**가이드:** 질문형(Q&A)과 서술형(description) 중 목적에 맞게 선택한다.

**적용:** 분석/보고서형 프롬프트를 선택합니다. "Your task: analyze this video ad and return a structured JSON assessment" — 모델에 명확한 태스크를 지시합니다.

---

## 3. Combined Prompt — 최종 버전

**파일:** `prompts/prompt_templates.py`
- `COMBINED_PROMPT` — 기본 프롬프트 (모든 지역 공통)
- `REGIONAL_PROMPT_CONTEXT` — 지역별 추가 context
- `get_regional_prompt(region)` — 기본 + 지역 context를 결합하여 최종 프롬프트 반환

### 3.1 프롬프트 전체 구조

```
[1. Role + Context]
  규제 전문가 역할 설정 + 주요 규제 기관 명시 (FTC, ASA, EU, MFDS, Yakujiho, NMPA)

[2. Task Definition]
  "analyze this video ad and return a structured JSON assessment"

[3. Section 1 — Campaign Relevance]
  - relevance_score 범위 설명 (0.0 = 무관, 1.0 = 완벽)
  - is_on_brief 기준 명시
  - product_visible 정의

[4. Section 2 — Video Description]
  - 2-5문장 팩트 기반 요약
  - 다국어 처리: 영어 + 괄호 안에 원어

[5. Section 3 — Policy Violations (6 Categories)]
  - 공통 severity 분류 가이드 (critical/high/medium/low 기준)
  - 카테고리별 감지 항목 + severity 매핑
  - 다국어 비속어 예시 포함

[6. Output Rules]
  - 위반 항목 필수 필드 정의
  - 다국어 처리 규칙
  - 빈 카테고리 처리

[7. Regional Context — 동적 추가] ← NEW
  - 사용자가 선택한 지역에 따라 추가되는 규제 context
  - 지역별 severity override 지시를 프롬프트에 직접 포함
```

### 3.2 지역별 동적 프롬프트 (Regional Prompt Context)

사용자가 선택한 지역에 따라 `COMBINED_PROMPT` 뒤에 지역별 context가 추가됩니다:

| 지역 | 프롬프트 크기 | 추가되는 핵심 지시 |
|------|-------------|-----------------|
| Global | 3,944자 (기본만) | 없음 — 공통 severity 가이드만 적용 |
| North America | +966자 | cannabis=HIGH, FDA approved=CRITICAL, FTC disclosure |
| Western Europe | +890자 | before/after=HIGH (ASA), #sponsored=INADEQUATE, EU 6 Criteria |
| East Asia | +1,305자 | drugs=CRITICAL (zero tolerance), mild profanity=HIGH, 药妆 banned |

#### Regional Context 예시: East Asia

```
## REGIONAL CONTEXT: East Asia (Korea MFDS / Japan Yakujiho / China NMPA)
You are evaluating this video for the East Asian market. Apply these region-specific rules:

- drugs_illegal: ZERO TOLERANCE across all three countries.
  ANY drug reference including cannabis, CBD → severity CRITICAL (not high).
- profanity_explicit / mild_profanity: mild expletives → severity HIGH (not medium).
- medical_cosmetic_claims / absolute_claims: China bans ALL absolute expressions → CRITICAL.
- ...
```

이 context는 모델이 지역별 규제 차이를 **분석 단계에서** 반영하도록 합니다.

### 3.3 기존 대비 개선 사항

| 항목 | 기존 프롬프트 | 개선된 프롬프트 |
|------|-------------|---------------|
| Role setting | "expert ad compliance reviewer for a global makeup and cosmetics brand campaign" | + 주요 규제 기관 명시 (FTC, ASA, EU, MFDS, Yakujiho, NMPA) |
| Task definition | 암시적 | "Your task: analyze this video ad and return a structured JSON assessment" 명시 |
| Severity 가이드 | 없음 (enum만 명시) | 공통 severity 분류 기준 + 카테고리별 severity 매핑 |
| 다국어 비속어 | "equivalents in any language including Korean/Japanese/Chinese" | 구체적 단어 예시: 씨발, 지랄, くそ, ファック, 他妈的, 操 |
| Relevance score | 범위 미설명 | 0.0 = completely unrelated, 1.0 = perfectly on-brief |
| Disclosure | 3가지 체크 | + 위치 부적절 (buried mid-video) → low 추가 |
| Cannabis/CBD | severity 미지정 | "critical in East Asia: zero tolerance" 명시 |
| 출력 규칙 | 프롬프트 내 3번 중복 | 끝에 1번만 간결하게 명시 |
| **지역 context** | **없음 — 모든 지역 동일 프롬프트** | **지역별 규제 context를 프롬프트에 동적 주입** |

---

## 4. 카테고리별 프롬프트 설계

### 4.1 hate_harassment

| 감지 대상 | Severity | 설계 의도 |
|-----------|----------|----------|
| 인종/민족 혐오 | critical | 즉시 법적 조치 유발 |
| 성차별, 유해 고정관념 | high | 콘텐츠 제거 필요 |
| 외모 비하, 조롱 | high | 화장품 업계 고유 리스크 |
| 피부톤 우월주의 | critical | 미백 광고의 implicit bias — 화장품 특화 |

### 4.2 profanity_explicit

| 감지 대상 | Severity | 설계 의도 |
|-----------|----------|----------|
| 강한 비속어 (F-word, C-word) | critical | 모든 지역에서 즉시 제거 |
| 다국어 강한 비속어 (씨발/くそ/他妈的) | critical | Pegasus partial support 활용 |
| 약한 비속어 (damn, hell) | medium | 인간 리뷰 대상 |
| 성적 콘텐츠 (explicit) | critical | 광고 플랫폼 정책 위반 |
| 성적 콘텐츠 (suggestive) | high | 콘텐츠 제거 검토 |

### 4.3 drugs_illegal

| 감지 대상 | Severity | 설계 의도 |
|-----------|----------|----------|
| 불법 약물 | critical | 모든 지역에서 zero tolerance |
| Cannabis/CBD | high (동아시아: critical) | 지역별 차이 명시 |
| 규제 물질 유래 화장품 성분 | high | v4.0 추가 — 성분명 다국어 식별 후 규제 물질 여부 평가 |
| 알코올 과다 | medium | 경계선 콘텐츠 |

v4.0에서 추가된 핵심 원칙:

- 화장품/스킨케어 제품에 규제 물질 유래 성분이 포함된 경우, 화장품 맥락이라도 drugs_illegal에서 면제되지 않음
- 모든 언어로 된 제품 성분명을 식별하고, 각 성분이 규제 약물 식물/물질에서 유래했는지 평가하도록 지시
- 특정 키워드를 나열하는 대신, 모델이 성분의 규제 물질 유래 여부를 맥락적으로 판단하도록 유도

### 4.4 unsafe_misleading_usage

| 감지 대상 | Severity | 설계 의도 |
|-----------|----------|----------|
| 안전하지 않은 사용 | high | 소비자 안전 직결 |
| 보정된 비포/애프터 | high (EU ASA: critical) | EU ASA L'Oreal/Maybelline 제재 사례 기반 |
| DIY 화장품 | medium | 안전 경고 부재 |
| 과도한 보정 | medium | 오도성 콘텐츠 |

### 4.5 medical_cosmetic_claims

가장 세분화된 카테고리 — 화장품(cosmetic)과 의약품(drug)의 경계가 핵심:

| 감지 대상 | Severity | 설계 의도 |
|-----------|----------|----------|
| 약품 주장 ("cures", "treats") | critical | cosmetic → drug 경계 침범 |
| "FDA approved" for cosmetics | critical | FDA는 화장품을 승인하지 않음 — 명시적 허위 주장 |
| "clinically proven" without studies | high | 근거 없는 효능 주장 |
| "100% effective", "guaranteed" | high | 절대적 주장 |
| "cosmeceutical", "medicated cosmetic" | high | 의약품 용어 남용 |
| "100% natural/organic" without cert | medium | 인증 없는 자연 주장 |
| 미백/화이트닝 과대 주장 | high | 화장품 범위 초과 |

### 4.6 disclosure

| 감지 대상 | Severity | 설계 의도 |
|-----------|----------|----------|
| "#ad" 등 광고 표시 부재 | medium | FTC/ASA 규제 대상 |
| "#sponsored" (UK에서 불충분) | medium | ASA 판례 직접 반영 |
| 지역별 표시 부재 (유료광고/広告/广告) | medium | 동아시아 규제 반영 |
| 표시 있으나 위치 부적절 | low | 경미한 위반 |

---

## 5. JSON Schema Design

### 5.1 Schema와 프롬프트 정렬

TwelveLabs [Structured Responses](https://docs.twelvelabs.io/docs/guides/analyze-videos/structured-responses) 가이드의 핵심 원칙:

> **"The schema takes precedence over the prompt."**

이 원칙에 따라 프롬프트의 모든 출력 지시가 `COMBINED_JSON_SCHEMA`와 정확히 매핑됩니다:

| 프롬프트 섹션 | Schema 필드 |
|-------------|------------|
| Section 1: Campaign Relevance | `relevance.{relevance_score, is_on_brief, product_visible, reasoning}` |
| Section 2: Video Description | `description` |
| Section 3: hate_harassment | `policy_violations.hate_harassment.{has_violation, severity, violations[]}` |
| Section 3: profanity_explicit | `policy_violations.profanity_explicit.{...}` |
| Section 3: drugs_illegal | `policy_violations.drugs_illegal.{...}` |
| Section 3: unsafe_misleading_usage | `policy_violations.unsafe_misleading_usage.{...}` |
| Section 3: medical_cosmetic_claims | `policy_violations.medical_cosmetic_claims.{...}` |
| Section 3: disclosure | `policy_violations.disclosure.{...}` |

### 5.2 Schema 구조

```json
{
  "relevance": {
    "relevance_score": "number (0.0-1.0)",
    "is_on_brief": "boolean",
    "product_visible": "boolean",
    "reasoning": "string"
  },
  "description": "string",
  "policy_violations": {
    "<category>": {
      "has_violation": "boolean",
      "severity": "enum [none|low|medium|high|critical]",
      "violations": [{
        "description": "string",
        "timestamp_start": "number",
        "timestamp_end": "number",
        "modality": "enum [visual|speech|text_on_screen]",
        "evidence": "string",
        "evidence_original": "string (optional)",
        "severity": "enum [low|medium|high|critical]"
      }]
    }
  }
}
```

### 5.3 Schema Design Decisions

| 결정 | 이유 |
|------|------|
| `relevance_score`를 number로 정의 | 0.5 threshold와 0.3 cutoff에 의한 3단계 분류 활용 |
| `severity`를 카테고리/위반 양쪽에 배치 | 카테고리 전체 심각도 + 개별 위반 심각도를 모두 캡처 |
| `evidence_original`을 required에서 제외 | 영어 콘텐츠에서는 불필요 — optional 처리 |
| `modality`를 3가지 enum으로 제한 | Pegasus의 멀티모달 분석 능력에 맞춤 (visual, speech, text) |
| 6개 카테고리 모두 required | 빈 카테고리도 명시적으로 반환하여 누락 방지 |

### 5.4 Truncation 방지

TwelveLabs 가이드 권장사항에 따라, 응답의 `finish_reason` 필드를 체크합니다:

- `finish_reason: "length"` → 응답이 `maxOutputTokens`에 도달하여 잘림
- 대응: API 클라이언트에서 warning 로그 출력

---

## 6. Model Interaction Flow

### 6.1 API 호출 과정

```
Video File (.mp4) + Region Selection (e.g., "east_asia")
    │
    ▼
[dashboard.py] analyze_uploaded_video()
    │  1. Save to temp file
    │  2. ffmpeg transcode → H.264/AAC
    │  3. Validate: duration ≥ 4s
    │
    ▼
[prompt_templates.py] get_regional_prompt(region)
    │  - COMBINED_PROMPT + REGIONAL_PROMPT_CONTEXT[region]
    │  - 지역별 규제 context가 프롬프트에 동적 추가
    │
    ▼
[TwelveLabs API] analyze()
    │  1. Upload video
    │  2. Send prompt + JSON schema
    │  3. Check finish_reason for truncation
    │
    ▼
[Pegasus 1.2]
    │  - 영상의 visual, audio, text 동시 분석
    │  - 지역 context를 반영한 severity 판단
    │  - JSON schema에 맞는 구조화된 응답 생성
    │
    ▼
[bedrock_analyzer.py] analyze_video_bedrock()
    │  - JSON 파싱 → Pydantic 모델 변환
    │  - relevance_score + is_on_brief → RelevanceLabel
    │  - 6 category violations → PolicyViolationResult[]
    │
    ▼
[decision.py] make_split_decision()
    │  - Axis 1: Compliance
    │    1. _match_sub_rule(): violation evidence ↔ regional keyword 매칭
    │    2. get_regional_severity(): 매칭된 sub_rule의 severity 조회
    │    3. severity upgrade (regional > model인 경우만)
    │  - Axis 2: Product (relevance label)
    │  - Axis 3: Disclosure (violation + keyword fallback)
    │  - Final: APPROVE / REVIEW / BLOCK
    │
    ▼
Compliance Report (JSON) → save to output/reports/
```

### 6.2 Prompt → Decision 매핑

프롬프트의 각 출력이 최종 결정에 어떻게 영향을 미치는지:

| 프롬프트 출력 | 후처리 | 결정 영향 |
|-------------|--------|----------|
| `relevance.relevance_score` < 0.3 | → OFF_BRIEF | → REVIEW |
| `relevance.is_on_brief` = false | → BORDERLINE or OFF_BRIEF | → REVIEW |
| `relevance.product_visible` = false | → NOT_VISIBLE | → REVIEW |
| `policy_violations.<cat>.severity` = high/critical | → regional upgrade 적용 | → BLOCK |
| `policy_violations.<cat>.severity` = low/medium | → regional upgrade 적용 | → REVIEW (or BLOCK if upgraded) |
| `policy_violations.disclosure.has_violation` = true | → MISSING | → REVIEW |
| `description` contains "no disclosure" keywords | → fallback 감지 → MISSING | → REVIEW |

---

## 7. Prompt Design Decisions

### 7.1 Role + Context Setting

기존:
```
"You are an expert ad compliance reviewer for a global makeup and cosmetics brand campaign."
```

개선:
```
"You are an expert ad compliance reviewer specializing in global beauty and cosmetics
advertising regulations, including FTC (US), ASA (UK), EU Cosmetics Regulation, and
East Asian standards (Korea MFDS, Japan Yakujiho, China NMPA)."
```

**변경 이유:** TwelveLabs "Provide Context" 원칙. 구체적인 규제 기관을 명시하여 모델이 해당 도메인 지식을 활성화하도록 유도.

### 7.2 Severity Classification Guide 추가

기존: severity enum만 명시 (`"critical" | "high" | "medium" | "low"`)

개선: 공통 기준 + 카테고리별 매핑 추가

```
### Severity classification guide:
- critical: content that would trigger immediate regulatory action or legal liability
- high: clear policy breach requiring content removal
- medium: borderline content requiring human review
- low: minor concern, unlikely to cause regulatory issues
```

**변경 이유:** TwelveLabs "Be Specific" 원칙. 모델이 severity를 일관되게 분류할 수 있도록 명확한 기준을 제공.

### 7.3 Temperature 0.2 → 0.1 (v4.0)

TwelveLabs [Temperature Guide](https://docs.twelvelabs.io/docs/guides/analyze-videos/tune-the-temperature)에 따라:

- 법 집행/보고서: 0.1 (가장 결정적)
- 컴플라이언스 분석: 0.2 (정확성 + 약간의 유연성)
- 마케팅 콘텐츠: 0.9 (창의적)

v4.0에서 0.2 → **0.1**로 하향 조정:

- drugs_illegal 등 위반 감지의 일관성 향상이 목적
- 동일 영상에 대해 실행할 때마다 결과가 달라지는 비결정적 문제 완화
- TwelveLabs API와 Bedrock API 양쪽 모두 temperature 0.1 적용

### 7.4 다국어 출력 전략

Pegasus 공식 언어 지원:
- **Full support:** English
- **Partial support:** Korean, Japanese, Chinese, etc.

전략: **영어 우선 출력 + 원어 보존** (`evidence_original` 필드)
- 영어 출력 품질이 가장 높으므로 기본 출력은 영어
- 비영어 콘텐츠의 감사/검증을 위해 원어 텍스트 보존

### 7.5 3단계 지역별 Severity 적용

```
[1단계] 프롬프트 지역 context 주입
  get_regional_prompt(region) → 모델이 지역 규제를 인식하고 severity 판단
  예: East Asia + cannabis → 모델이 프롬프트의 "ZERO TOLERANCE" 지시를 보고 "critical" 반환

[2단계] Sub-rule 키워드 매칭
  _match_sub_rule() → violation evidence 텍스트를 regional policy의 keywords와 매칭
  예: "cannabis CBD" → east_asia의 "illegal_drugs" sub-rule 매칭 (CRITICAL)
  예: "cannabis CBD" → north_america의 "cannabis_cbd" sub-rule 매칭 (HIGH)

[3단계] Severity 상향 조정 (upgrade only)
  get_regional_severity() → 매칭된 sub-rule의 severity가 모델 severity보다 높으면 상향
  예: 모델이 "high" 반환 + east_asia sub-rule "CRITICAL" → CRITICAL로 상향
```

이 3단계 접근의 장점:
- **1단계:** 모델이 지역 맥락을 이해하고 분석 — **감지 누락 방지**
- **2단계:** 코드 레벨에서 세부 규칙 매칭 — **정밀한 severity 적용**
- **3단계:** 최종 안전망 — **모델의 과소 평가를 regional policy로 보정**

기존 2단계(프롬프트 동일 + 코드 upgrade만)의 문제:
- 모델이 지역을 모르므로 동일한 base severity 판단
- 모델이 아예 감지하지 않는 경우 코드에서 보완 불가

개선된 3단계는 프롬프트와 코드 양쪽에서 지역별 차이를 반영합니다.

---

## 8. Individual Prompts (Legacy)

단일 통합 프롬프트 도입 이전의 개별 호출 구조. 현재 코드에 남아 있으나 사용되지 않음.

### 8.1 구성

| 프롬프트 | 용도 | 호출 수 |
|---------|------|--------|
| `RELEVANCE_PROMPT` | 제품 관련성 평가 | 1회 |
| `DESCRIPTION_PROMPT` | 영상 요약 | 1회 |
| `POLICY_PROMPTS` (6 categories) | 카테고리별 위반 감지 | 6회 |
| **합계** | | **8회** |

### 8.2 개별 vs 통합 비교

| 항목 | 개별 프롬프트 | 통합 프롬프트 |
|------|-------------|-------------|
| 카테고리당 프롬프트 길이 | ~150-200 words | ~80-120 words |
| Severity 분류 가이드 | 카테고리별 상세 기준 | 공통 기준 + 카테고리별 매핑 |
| 언어 감지 예시 | profanity에 구체적 단어 나열 | 구체적 단어 예시 유지 |
| 출력 정확도 | 높음 (집중된 context) | 양호 → 개선됨 (severity 가이드 추가) |

**활용 가능성:** 특정 카테고리의 정확도가 낮을 경우, 해당 카테고리만 개별 프롬프트로 2차 분석하는 하이브리드 접근 가능.

---

## 9. References

### TwelveLabs 공식 문서

| 문서 | 설명 |
|------|------|
| [Prompt Engineering Guide](https://docs.twelvelabs.io/docs/guides/analyze-videos/prompt-engineering) | 8가지 프롬프트 베스트 프랙티스, 반복 개선 프로세스 |
| [Structured Responses](https://docs.twelvelabs.io/docs/guides/analyze-videos/structured-responses) | JSON Schema 사용법, schema-prompt 우선순위, 지원 데이터 타입 |
| [Temperature Tuning](https://docs.twelvelabs.io/docs/guides/analyze-videos/tune-the-temperature) | Temperature 0~1 범위, 용도별 권장값, 출력 비교 |
| [Pegasus Model](https://docs.twelvelabs.io/docs/concepts/models/pegasus) | 모델 스펙, 영상 제약 (4s~1hr, max 2GB), 다국어 지원 현황 |
| [Analyze Videos](https://docs.twelvelabs.io/docs/guides/analyze-videos) | 영상 분석 API 가이드, 기본 사용법 |

### Amazon Bedrock

| 문서 | 설명 |
|------|------|
| [TwelveLabs on Bedrock](https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-twelvelabs.html) | Bedrock에서의 Pegasus 사용법, InvokeModel 파라미터 |
| [Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/) | Bedrock 모델별 가격 정보 |
