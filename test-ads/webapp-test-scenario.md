# Webapp 검증 시나리오

## 사전 조건

- Webapp URL: `https://main.d1mjnmpj9lc6js.amplifyapp.com`
- Demo 계정: `admin@adcompliance.com` / `Admin1234!`
- 분석 대기 시간: 약 1~3분 (TwelveLabs는 indexing 포함으로 더 오래 걸릴 수 있음)
- 검증 리전 기본값: Global
- API Gateway 타임아웃: 29초 (이 시간 내에 Lambda 응답이 없으면 504 발생)

## 알려진 제한사항

- API Gateway REST API의 최대 통합 타임아웃은 29초입니다.
- TwelveLabs API는 영상 indexing + analyze 과정이 포함되어 파일 크기가 큰 경우 29초를 초과할 수 있습니다.
- 504 Gateway Timeout 발생 시: 동일 파일로 재시도하면 TwelveLabs 쪽에서 이미 indexing이 완료되어 빠르게 응답할 수 있습니다.

## 테스트 파일 목록

| 파일명 | 유형 | 설명 |
| ------ | ---- | ---- |
| `normal-us.mp4` | 정상 광고 | APPROVE 예상 |
| `compliance-hate.mp4` | 위반 - 혐오 표현 | BLOCK 예상 |
| `compliance-unsafe.mp4` | 위반 - 안전하지 않은 사용 | BLOCK 예상 |
| `compliance-drug.mp4` | 위반 - 약물 관련 | BLOCK 예상 |
| `compliance-profanity.mp4` | 위반 - 비속어/욕설 | BLOCK 예상 |

## 파일 업로드 팁

파일 탐색기 팝업이 닫히지 않는 경우, Chrome DevTools `upload_file` 명령을 사용합니다:

1. Webapp 페이지의 snapshot을 찍어 file input 요소의 uid를 확인
2. `upload_file` 도구에 해당 uid와 로컬 파일 경로를 전달
3. 파일 탐색기 팝업 없이 바로 업로드 완료

## 시나리오 (TwelveLabs API 먼저, 이후 Bedrock API 반복)

### 1단계: 로그인 및 Backend 설정

1. Webapp 접속
2. Demo Account 배너의 "Use Demo Account" 클릭
3. 로그인 성공 확인 (Analyze 페이지 이동)
4. Settings 페이지 이동 → Backend를 "TwelveLabs" 로 변경
5. TwelveLabs API Key 입력 후 저장

### 2단계: 정상 광고 검증

1. Analyze 페이지에서 `normal-us.mp4` 업로드
2. Region: Global
3. 분석 실행 → 결과 대기 (최대 1분, timeout=60000ms)
4. 결과가 표시되면 10초 대기 (결과 확인 시간 확보)
5. 기대 결과: Decision = APPROVE, Compliance = PASS, Disclosure = PRESENT
6. 다음 테스트로 진행

### 3단계: Compliance 위반 검증

순서대로 수행하며, 각 테스트는 아래 니다:

1. 파일 업로드 → Upload 클릭 → "Uploaded" 확인
2. "Run Analysis" 클릭 → 결과 대기 (최대 1분, timeout=60000ms)
3. 결과가 표시되면 10초 대기 (결과 확인 시간 확보)
4. 504 Gateway Timeout 발생 시: 동일 파일로 재업로드 후 재시도 (최대 2회)
5. 결과 기록 후 다음 테스트로 진행

#### 3-1. 혐오 표현 (compliance-hate.mp4)

1. `compliance-hate.mp4` 업로드, Region: Global
2. 분석 실행 → 결과 대기
3. 결과 표시 후 10초 대기
4. 기대 결과: Decision = BLOCK, hate_harassment (CRITICAL) 포함

#### 3-2. 안전하지 않은 사용 (compliance-unsafe.mp4)

1. `compliance-unsafe.mp4` 업로드, Region: Global
2. 분석 실행 → 결과 대기 (파일 크기 8.5MB, 504 타임아웃 가능성 있음)
3. 504 발생 시 재업로드 후 재시도
4. 결과 표시 후 10초 대기
5. 기대 결과: Decision = BLOCK, unsafe_misleading_usage (HIGH) 포함

#### 3-3. 약물 관련 (compliance-drug.mp4)

1. `compliance-drug.mp4` 업로드, Region: Global
2. 분석 실행 → 결과 대기
3. 결과 표시 후 10초 대기
4. 기대 결과: Decision = BLOCK, drugs_illegal 포함

#### 3-4. 비속어/욕설 (compliance-profanity.mp4)

1. `compliance-profanity.mp4` 업로드, Region: Global
2. 분석 실행 → 결과 대기
3. 결과 표시 후 10초 대기
4. 기대 결과: Decision = BLOCK, profanity_explicit 포함

### 4단계: Bedrock API로 동일 테스트 반복

1. Settings 페이지 이동 → Backend를 "Amazon Bedrock" 으로 변경 후 저장
2. 2단계~3단계를 동일하게 반복 수행
3. TwelveLabs 결과와 Bedrock 결과를 비교

## 검증 결과 기록 (프롬프트 개선 후 - v3.0)

### TwelveLabs API (프롬프트 개선 후)

#### TwelveLabs 2단계: normal-us.mp4 (Global)

- Decision: APPROVE
- Compliance: PASS
- Product: ON_BRIEF (1.00)
- Disclosure: PRESENT
- 결과: PASS

#### TwelveLabs 3-1단계: compliance-hate.mp4 (Global)

- Decision: BLOCK
- 위반: hate_harassment (CRITICAL), medical_cosmetic_claims (CRITICAL), disclosure (MEDIUM) - 3건
- 결과: PASS

#### TwelveLabs 3-2단계: compliance-unsafe.mp4 (Global)

- Decision: BLOCK
- 위반: unsafe_misleading_usage (HIGH), disclosure (MEDIUM) - 2건
- 결과: PASS

#### TwelveLabs 3-3단계: compliance-drug.mp4 (Global)

- Decision: REVIEW
- 위반: disclosure (MEDIUM) - 1건
- 비고: hemp/chanvre를 drugs_illegal로 분류하지 못함. 이전 테스트에서는 drugs_illegal (HIGH) + disclosure (MEDIUM) 2건이었음
- 결과: PARTIAL (BLOCK 기대했으나 REVIEW 판정)

### Bedrock API (프롬프트 개선 후 - Pegasus 1.2)

#### Bedrock 2단계: normal-us.mp4 (Global)

- Decision: APPROVE
- Compliance: PASS
- Product: ON_BRIEF (1.00)
- Disclosure: PRESENT
- 비고: 프롬프트 개선 효과 확인 - 이전 REVIEW/MISSING에서 APPROVE/PRESENT로 개선
- 결과: PASS

#### Bedrock 3-1단계: compliance-hate.mp4 (Global)

- Decision: BLOCK
- 위반: hate_harassment (CRITICAL), medical_cosmetic_claims (CRITICAL) - 2건
- Disclosure: MISSING
- 결과: PASS

#### Bedrock 3-2단계: compliance-unsafe.mp4 (Global)

- Decision: BLOCK
- 위반: unsafe_misleading_usage (HIGH), medical_cosmetic_claims (HIGH), disclosure (MEDIUM) - 3건
- Disclosure: MISSING
- 결과: PASS

#### Bedrock 3-3단계: compliance-drug.mp4 (Global)

- Decision: BLOCK
- 위반: medical_cosmetic_claims (LOW), disclosure (MEDIUM) - 2건
- Disclosure: MISSING
- 비고: Bedrock은 hemp/chanvre 성분을 drugs_illegal로 분류하지 못함. medical_cosmetic_claims로 대체 감지하여 BLOCK 판정은 유지
- 결과: PASS (BLOCK 판정은 동일)

### 프롬프트 개선 전후 비교

| 항목 | 이전 (v2.1) | 개선 후 (v3.0) | 변화 |
| ---- | ----------- | -------------- | ---- |
| Bedrock normal-us Decision | REVIEW | APPROVE | 개선 |
| Bedrock normal-us Disclosure | MISSING | PRESENT | 개선 |
| Bedrock compliance-hate | BLOCK | BLOCK | 동일 |
| Bedrock compliance-unsafe | BLOCK | BLOCK | 동일 |
| Bedrock compliance-drug | BLOCK (unsafe_misleading_usage) | BLOCK (medical_cosmetic_claims) | 위반 카테고리 변경, BLOCK 유지 |
| TwelveLabs compliance-drug | BLOCK (drugs_illegal) | REVIEW (disclosure만) | 퇴보 |

### 결론 (v3.0)

- Bedrock 프롬프트 개선 효과: normal-us.mp4에서 Disclosure 감지 성공 (MISSING -> PRESENT), Decision도 APPROVE로 정상화
- TwelveLabs compliance-drug.mp4: 이번 테스트에서 drugs_illegal 미감지 (비결정적 결과 - LLM 특성)
- 양쪽 모두 compliance-drug.mp4의 hemp/chanvre 성분을 drugs_illegal로 일관되게 분류하지 못하는 한계 존재

---

## 검증 결과 기록 (drugs_illegal 프롬프트 강화 후 - v4.0)

v4.0 프롬프트 변경사항:
- drugs_illegal 섹션에 "성분 분석 관점" 추가: 화장품 맥락이라도 규제 물질 유래 성분은 면제 아님
- 모든 언어로 성분명 식별 후 규제 물질 여부 평가 지시 추가
- temperature 0.2 → 0.1 하향 (TwelveLabs + Bedrock 양쪽)

### Bedrock API (v4.0 프롬프트)

#### Bedrock compliance-drug.mp4 (Global) - v4.0

- Decision: REVIEW
- Compliance: PASS (위반 없음)
- 위반: disclosure (MEDIUM) - 1건
- Disclosure: MISSING
- 비고: hemp/chanvre를 drugs_illegal로 분류하지 못함. v3.0에서는 medical_cosmetic_claims(LOW)로 대체 감지하여 BLOCK이었으나, v4.0에서는 그것도 없어 REVIEW로 하락
- 결과: FAIL (BLOCK 기대했으나 REVIEW 판정)

### TwelveLabs API (v4.0 프롬프트)

#### TwelveLabs compliance-drug.mp4 (Global) - v4.0

- Decision: REVIEW
- Compliance: PASS (위반 없음)
- 위반: disclosure (MEDIUM) - 1건
- Disclosure: MISSING
- Description: "hemp-infused lifting cream", "crème liftante au chanvre" 정확히 인식
- 비고: 모델이 hemp/chanvre를 정확히 인식하면서도 drugs_illegal로 분류하지 않음
- 결과: FAIL (BLOCK 기대했으나 REVIEW 판정)

### v3.0 → v4.0 비교 (compliance-drug.mp4만)

| 항목 | v3.0 Bedrock | v4.0 Bedrock | v3.0 TwelveLabs | v4.0 TwelveLabs |
| ---- | ------------ | ------------ | --------------- | --------------- |
| Decision | BLOCK | REVIEW | REVIEW | REVIEW |
| drugs_illegal | 미감지 | 미감지 | 미감지 | 미감지 |
| 대체 감지 | medical_cosmetic_claims (LOW) | 없음 | disclosure만 | disclosure만 |
| 결과 | PASS (BLOCK 유지) | FAIL | PARTIAL | FAIL |

### 결론 (v4.0)

- 프롬프트의 "성분 분석 관점" 접근과 temperature 하향(0.1)만으로는 Pegasus 1.2가 hemp/chanvre를 drugs_illegal로 분류하도록 유도하기 어려움
- Pegasus 1.2 모델의 근본적 한계: hemp을 화장품 성분으로 인식하면 규제 물질로 분류하지 않는 경향
- v4.0에서 오히려 medical_cosmetic_claims 대체 감지도 사라져 v3.0보다 퇴보
- 향후 대안 검토 필요:
  1. 후처리(post-processing) 단계에서 키워드 기반 drugs_illegal 감지 추가 (hemp, chanvre, cannabis 등)
  2. 개별 프롬프트(POLICY_PROMPTS["drugs_illegal"])로 2차 분석 하이브리드 접근
  3. 지역별 context (East Asia) 적용 시 재테스트

---

## 검증 결과 기록 (새 영상 - 영어 버전 compliance-drug.mp4 - v5.0)

v5.0 변경사항:
- 테스트 영상 교체: 프랑스어(chanvre) → 영어(hemp cream) 버전으로 변경
- 프롬프트/코드 변경 없음 (v4.0 프롬프트 그대로 사용)
- 파일 크기: 4.2MB → 4.1MB

### TwelveLabs API (v5.0 - 새 영상)

#### TwelveLabs compliance-drug.mp4 (Global) - v5.0

- Decision: BLOCK
- 위반: medical_cosmetic_claims (HIGH), disclosure (MEDIUM) - 2건
- Disclosure: MISSING
- Description: "hemp cream gives a natural, healthy glow and elasticity, not just covering wrinkles" (영어 음성 정확히 인식)
- 비고: drugs_illegal은 여전히 미감지이나, medical_cosmetic_claims(HIGH)로 BLOCK 판정 달성. anti-aging 효과 주장이 cosmetic 범위 초과로 판단됨
- 결과: PASS (BLOCK 판정 달성, 단 drugs_illegal이 아닌 medical_cosmetic_claims로 감지)

### Bedrock API (v5.0 - 새 영상)

#### Bedrock compliance-drug.mp4 (Global) - v5.0

- Decision: BLOCK
- 위반: drugs_illegal (HIGH→CRITICAL upgrade), medical_cosmetic_claims (HIGH), disclosure (MEDIUM) - 3건
- Disclosure: MISSING
- Description: "hemp cream, which may contain regulated substance-derived ingredients" (drugs_illegal 감지 성공)
- 비고: Bedrock이 영어 "hemp cream"을 drugs_illegal로 성공적으로 감지. 모델 출력은 HIGH였으나 decision 로직에서 CRITICAL로 upgrade
- 결과: PASS (drugs_illegal 감지 성공 + BLOCK 판정)

### v4.0 → v5.0 비교 (compliance-drug.mp4 - 영상 교체)

| 항목 | v4.0 Bedrock (프랑스어) | v5.0 Bedrock (영어) | v4.0 TwelveLabs (프랑스어) | v5.0 TwelveLabs (영어) |
| ---- | ---------------------- | ------------------- | ------------------------ | --------------------- |
| Decision | REVIEW | BLOCK | REVIEW | BLOCK |
| drugs_illegal | 미감지 | HIGH (→CRITICAL) | 미감지 | 미감지 |
| medical_cosmetic_claims | 없음 | HIGH | 없음 | HIGH |
| disclosure | MEDIUM | MEDIUM | MEDIUM | MEDIUM |
| 결과 | FAIL | PASS | FAIL | PASS |

### 결론 (v5.0)

- 영어 영상으로 교체 후 양쪽 모두 BLOCK 판정 달성
- Bedrock: drugs_illegal 감지 성공 (영어 "hemp cream" → 규제 물질 유래 성분으로 판단)
- TwelveLabs: drugs_illegal은 미감지이나 medical_cosmetic_claims(HIGH)로 BLOCK 달성
- 핵심 발견: Pegasus 1.2는 영어 콘텐츠에서 drugs_illegal 감지 능력이 프랑스어보다 우수 (Bedrock 경유 시)
- TwelveLabs 직접 API는 영어에서도 drugs_illegal 미감지 — Bedrock과 TwelveLabs 간 동일 모델이지만 감지 차이 존재

