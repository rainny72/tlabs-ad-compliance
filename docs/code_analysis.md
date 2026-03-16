# Code Analysis — Ad Compliance & Brand Safety System

> 모듈별 코드 분석 및 데이터 흐름 문서

---

## Table of Contents

1. [모듈 의존성 맵](#1-모듈-의존성-맵)
2. [공유 모듈 (shared/)](#2-공유-모듈-shared)
3. [분석 코어 (core/)](#3-분석-코어-core)
4. [Lambda 함수 (deployment/lambda/)](#4-lambda-함수-deploymentlambda)
5. [React 프론트엔드 (deployment/frontend/)](#5-react-프론트엔드-deploymentfrontend)
6. [CDK 인프라 (deployment/cdk/)](#6-cdk-인프라-deploymentcdk)
7. [Streamlit 대시보드 (app/)](#7-streamlit-대시보드-app)
8. [데이터 흐름 추적](#8-데이터-흐름-추적)
9. [에러 처리 패턴](#9-에러-처리-패턴)

---

## TL;DR

- **Core 모듈**: Bedrock/TwelveLabs 클라이언트, 3축 평가 엔진, 증거 추출기
- **Lambda**: Dispatcher/Worker 비동기 패턴으로 15분 분석 지원
- **Frontend**: React + MUI + Amplify Authenticator, 폴링 기반 상태 조회
- **CDK**: 4개 스택 (Auth, Storage, Api, Frontend) 분리 구성

---

## 1. 모듈 의존성 맵

```text
shared/constants.py ──────────────────────────────────────┐
shared/schemas.py ─────────────────────────┐              │
shared/regional_policies/ ──┐              │              │
                            │              │              │
                            ▼              ▼              ▼
                    core/decision.py    core/bedrock_analyzer.py
                            │                   │
                            │                   ▼
                            │          core/bedrock_client.py
                            │          core/twelvelabs_client.py
                            │                   │
                            ▼                   ▼
                    ┌───────────────────────────────────┐
                    │     deployment/lambda/analyze/    │
                    │     - dispatcher.py               │
                    │     - worker.py                   │
                    └───────────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────────────┐
                    │     deployment/frontend/src/      │
                    │     - services/api.ts             │
                    │     - pages/AnalyzePage.tsx       │
                    └───────────────────────────────────┘
```

---

## 2. 공유 모듈 (shared/)

### 2.1 constants.py — Enum 및 상수

| Enum | 값 | 용도 |
| --- | --- | --- |
| `Region` | global, north_america, western_europe, east_asia | 컴플라이언스 지역 |
| `Severity` | none, low, medium, high, critical | 위반 심각도 |
| `Decision` | APPROVE, REVIEW, BLOCK | 최종 판정 |
| `PolicyCategory` | 6개 카테고리 | 정책 위반 분류 |
| `RelevanceLabel` | ON_BRIEF, OFF_BRIEF, BORDERLINE | 제품 관련성 |
| `Modality` | visual, speech, text_on_screen | 위반 감지 방식 |

핵심 상수:

```python
SEVERITY_PRIORITY = {CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1, NONE: 0}
RELEVANCE_THRESHOLD = 0.5
```

### 2.2 schemas.py — Pydantic 데이터 모델

주요 모델:

- `ViolationEvidence`: 개별 위반 증거 (타임스탬프, 모달리티, 증거 텍스트)
- `PolicyViolationResult`: 카테고리별 위반 결과
- `CampaignRelevanceResult`: 제품 관련성 평가 결과
- `ComplianceReport`: 최종 분석 리포트

### 2.3 regional_policies/ — 지역별 정책

지역별 심각도 규칙 정의:

- `north_america.py`: FTC, FDA, MoCRA 규정
- `western_europe.py`: EU Cosmetics Reg, ASA 규정
- `east_asia.py`: MFDS, PMDA, NMPA 규정 (마약류 무관용)

---

## 3. 분석 코어 (core/)

### 3.1 bedrock_client.py — Bedrock API 클라이언트

`BedrockAnalyzer` 클래스:

- boto3 Bedrock Runtime 래퍼
- 비디오 base64 인코딩 전송
- JSON 스키마 기반 구조화된 응답

### 3.2 twelvelabs_client.py — TwelveLabs API 클라이언트

TwelveLabs Pegasus 1.2 모델 호출:

- 비디오 업로드 및 인덱싱
- 분석 API 호출
- 8 req/min 레이트 리미터

### 3.3 decision.py — 3축 평가 엔진

`make_split_decision()` 함수:

1. `_evaluate_compliance()`: 5개 정책 카테고리 평가 → PASS/REVIEW/BLOCK
2. `_evaluate_product()`: 제품 관련성 평가 → ON_BRIEF/BORDERLINE/OFF_BRIEF
3. `_evaluate_disclosure()`: 광고 공개 여부 → PRESENT/MISSING

최종 판정 로직:

```text
BLOCK if compliance.status == "BLOCK"
REVIEW if any axis has issues
APPROVE if all clear
```

지역별 심각도 업그레이드:

- 모델이 할당한 심각도보다 지역 정책이 더 높으면 업그레이드 (다운그레이드 불가)
- Global 지역: 모든 지역 중 가장 엄격한 심각도 적용
- 서브룰 키워드 매칭으로 세분화된 심각도 결정

### 3.4 evidence_extractor.py — 증거 추출

BLOCK 판정 시 ffmpeg으로 증거 추출:

- 썸네일: 위반 타임스탬프 중간점 JPEG 프레임
- 클립: ±1초 패딩 MP4 클립

---

## 4. Lambda 함수 (deployment/lambda/)

### 4.1 upload/handler.py — 업로드 핸들러

S3 presigned URL 생성:

- 파일 확장자 검증: mp4, mov, avi, mkv
- 파일 크기 제한: 25MB
- S3 키: `uploads/{user_id}/{timestamp}_{filename}`
- URL 유효 시간: 15분 (900초)

### 4.2 analyze/dispatcher.py — 디스패처

POST /analyze:

1. JWT claims에서 user_id 추출
2. s3Key, region 검증
3. job_id 생성 (UUID v4)
4. Jobs 테이블에 PENDING 저장
5. Worker Lambda 비동기 호출 (`InvocationType: Event`)
6. HTTP 202 반환

GET /analyze/{jobId}:

1. Jobs 테이블 조회
2. user_id 일치 확인 (정보 유출 방지)
3. 상태별 응답 (COMPLETED → result, FAILED → error)

### 4.3 analyze/worker.py — 워커

비동기 분석 수행 (최대 900초):

```text
1. Jobs 상태 → PROCESSING
2. Settings 테이블 → 백엔드 설정 조회
3. S3 비디오 다운로드 → /tmp/
4. ffmpeg 전처리 (mjpeg 썸네일 스트림 제거)
5. Bedrock 또는 TwelveLabs 분석
6. description_audit 후처리 (누락 위반 스캔)
7. make_split_decision 3축 평가
8. ComplianceReport → Reports 테이블
9. Jobs 상태 → COMPLETED + result
```

에러 매핑:

| 예외 | 사용자 메시지 |
| --- | --- |
| S3 NoSuchKey/AccessDenied | 비디오 파일 다운로드 실패 |
| Unprocessable video | 지원하지 않는 비디오 형식 |
| TwelveLabs API key 미설정 | Settings에서 API 키 설정 필요 |
| TimeoutError | 분석 시간 초과 |
| Bedrock 서비스 불가 | 일시적 서비스 불가 |

### 4.4 reports/handler.py — 리포트 핸들러

GET /reports: 사용자별 분석 이력 조회 (최신순)
GET /reports/{id}: 특정 리포트 상세 조회

### 4.5 settings/handler.py — 설정 핸들러

GET /settings: 사용자 설정 조회 (backend, API 키)
PUT /settings: 사용자 설정 저장

허용 백엔드: `bedrock`, `twelvelabs`

### 4.6 Shared Layer

Lambda Layer로 공유 모듈 배포:

- `shared_layer/`: core/, shared/, prompts/ 모듈 포함
- `ffmpeg_layer/`: ffmpeg 정적 바이너리 (비디오 전처리용)

---

## 5. React 프론트엔드 (deployment/frontend/)

### 5.1 기술 스택

- React 18 + TypeScript
- Vite 빌드
- Material-UI (MUI) 컴포넌트
- AWS Amplify UI React (Authenticator)
- React Router v6

### 5.2 페이지 컴포넌트

| 파일 | 경로 | 기능 |
| --- | --- | --- |
| AnalyzePage.tsx | /analyze | 비디오 업로드 및 분석 |
| HistoryPage.tsx | /history | 분석 이력 조회 |
| SettingsPage.tsx | /settings | 백엔드 설정 |

### 5.3 UI 컴포넌트

| 컴포넌트 | 역할 |
| --- | --- |
| VideoUploader | 비디오 파일 업로드 UI |
| ComplianceResult | 분석 결과 표시 (3축 평가) |
| ViolationCard | 개별 위반 사항 카드 |

### 5.4 API 클라이언트 (services/api.ts)

인증 토큰 자동 주입:

```typescript
async function authFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = await getAuthToken(); // Amplify fetchAuthSession
  return fetch(`${API_URL}${path}`, {
    ...options,
    headers: { Authorization: token, ... },
  });
}
```

폴링 기반 분석 완료 대기:

```typescript
async function analyzeVideo(request, onStatusChange, signal): Promise<AnalyzeResponse> {
  const { jobId } = await submitAnalysis(request);
  // 5초 간격, 최대 60회 (5분) 폴링
  for (let i = 0; i < MAX_POLLS; i++) {
    const job = await getJobStatus(jobId);
    if (job.status === 'COMPLETED') return job.result;
    if (job.status === 'FAILED') throw new ApiError(500, job.error);
  }
}
```

snake_case → camelCase 자동 변환:

```typescript
function snakeToCamel(obj: any): any {
  // API 응답의 snake_case 키를 camelCase로 변환
}
```

### 5.5 테스트

- 단위 테스트: `*.test.tsx` (Vitest + React Testing Library)
- Property 테스트: `*.property.test.tsx` (fast-check)

---

## 6. CDK 인프라 (deployment/cdk/)

### 6.1 스택 구성

`bin/app.ts`에서 4개 스택 생성:

```typescript
const authStack = new AuthStack(app, `${stackPrefix}-Auth`, { envName });
const storageStack = new StorageStack(app, `${stackPrefix}-Storage`, { envName });
const apiStack = new ApiStack(app, `${stackPrefix}-Api`, {
  envName, userPool, videoBucket, reportsTable, settingsTable, jobsTable,
});
new FrontendStack(app, `${stackPrefix}-Frontend`, {
  envName, api, userPool, userPoolClient,
});
```

환경 설정은 `cdk.json` context에서 로드 (`-c env=dev|prod`).

### 6.2 스택 간 의존성

```text
AuthStack ──────────────────────────────────────┐
    │ userPool, userPoolClient                   │
    ▼                                            │
StorageStack                                     │
    │ videoBucket, reportsTable,                 │
    │ settingsTable, jobsTable                   │
    ▼                                            ▼
ApiStack ──────────────────────────────> FrontendStack
    │ api (REST API)                     │ amplifyApp
    │                                    │ (환경변수: API URL,
    │                                    │  Cognito 설정)
    ▼
Lambda Functions (5개)
```

---

## 7. Streamlit 대시보드 (app/)

### 7.1 dashboard.py

로컬 개발/데모용 Streamlit 앱:

- 3개 페이지: Upload & Analyze, Analysis History, Settings
- 직접 core/ 모듈 호출 (Lambda 경유 없음)
- `.credentials.json` 파일 기반 인증 정보 관리
- ffmpeg 비디오 전처리 및 증거 추출

---

## 8. 데이터 흐름 추적

### 8.1 프로덕션 앱 분석 흐름

```text
React App
    │ 1. getUploadUrl() → POST /upload-url
    │ 2. PUT presigned URL → S3
    │ 3. submitAnalysis() → POST /analyze
    ▼
Dispatcher Lambda
    │ 4. Jobs 테이블 PENDING 저장
    │ 5. Worker Lambda 비동기 호출
    │ 6. HTTP 202 {jobId} 반환
    ▼
Worker Lambda
    │ 7. S3 비디오 다운로드
    │ 8. ffmpeg 전처리
    │ 9. Bedrock/TwelveLabs 분석
    │ 10. description_audit 후처리
    │ 11. make_split_decision 3축 평가
    │ 12. Reports 테이블 저장
    │ 13. Jobs 테이블 COMPLETED 업데이트
    ▼
React App (폴링)
    │ 14. getJobStatus() → GET /analyze/{jobId}
    │ 15. status === COMPLETED → result 표시
    ▼
ComplianceResult 컴포넌트
    │ 16. 3축 평가 결과 렌더링
    │ 17. ViolationCard 위반 상세 표시
```

### 8.2 Streamlit 앱 분석 흐름

```text
Streamlit Dashboard
    │ 1. 비디오 업로드 (st.file_uploader)
    │ 2. ffmpeg H.264 트랜스코딩
    │ 3. core/ 모듈 직접 호출
    │ 4. 응답 파싱 → 3축 평가
    │ 5. BLOCK 시 증거 추출
    │ 6. 결과 표시 + JSON 저장
```

---

## 9. 에러 처리 패턴

### 9.1 Lambda 에러 처리

모든 Lambda 핸들러 공통 패턴:

```python
try:
    # 비즈니스 로직
except ValidationError as e:
    return _build_response(400, {"error": str(e)})
except ClientError as e:
    if error_code in ("ThrottlingException", "ServiceUnavailableException"):
        return _build_response(503, {"error": "Service temporarily unavailable"})
    return _build_response(500, {"error": "Internal server error"})
except Exception:
    return _build_response(500, {"error": "Internal server error"})
```

### 9.2 프론트엔드 에러 처리

`ApiError` 클래스로 HTTP 상태 코드 기반 에러 분류:

```typescript
export class ApiError extends Error {
  constructor(public readonly statusCode: number, message: string) {
    super(message);
  }
}
```

### 9.3 Worker 에러 매핑

Worker Lambda는 예외를 사용자 친화적 메시지로 변환하여 Jobs 테이블에 저장합니다. 프론트엔드는 이 메시지를 그대로 표시합니다.
