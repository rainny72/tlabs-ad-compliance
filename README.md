# Ad Compliance & Brand Safety

비디오 광고 컴플라이언스 자동 검토 시스템입니다. TwelveLabs Pegasus 1.2 또는 Amazon Bedrock을 통해 영상을 분석합니다.

---

## 프로젝트 구조

```
ad-compliance/
├── app/                          # Streamlit 로컬 앱
│   └── dashboard.py
├── core/                         # 분석 엔진 (공유 모듈)
│   ├── bedrock_client.py
│   ├── bedrock_analyzer.py
│   ├── decision.py
│   └── evidence_extractor.py
├── prompts/                      # AI 프롬프트 템플릿
├── shared/                       # 공유 상수/스키마
│   └── regional_policies/        # 지역별 정책
├── deployment/
│   ├── cdk/                      # AWS CDK 인프라
│   ├── frontend/                 # React SPA (Amplify)
│   └── lambda/                   # Lambda 핸들러
├── docs/                         # 문서
└── demo/                         # 데모 비디오/스크린샷
```

---

## 설치 및 실행

### 사전 요구사항

- Python 3.11+
- Node.js 18+ (CDK/Frontend 배포 시)
- ffmpeg (비디오 트랜스코딩)
- AWS CLI (CDK 배포 시)

### 1. Streamlit 로컬 앱

```bash
# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# 앱 실행
streamlit run app/dashboard.py
```

Settings 페이지에서 TwelveLabs API 키 또는 AWS 자격 증명을 설정합니다.

### 2. CDK 인프라 배포

```bash
# CDK 디렉토리 이동 및 의존성 설치
cd deployment/cdk
npm install

# CDK Bootstrap (최초 1회)
npx cdk bootstrap

# 스택 배포
npx cdk deploy --all
```

CDK 스택 구성:

| 스택 | 리소스 |
| --- | --- |
| Auth | Cognito User Pool |
| Storage | S3 Bucket + DynamoDB Tables |
| Api | API Gateway + Lambda Functions |
| Frontend | Amplify Hosting |

### 3. Frontend 빌드

```bash
cd deployment/frontend

# 의존성 설치
npm install

# 환경 변수 설정
cp .env.example .env
# .env 파일에 API URL, Cognito 설정 입력

# 로컬 개발
npm run dev

# 프로덕션 빌드
npm run build
```

---

## 주요 의존성

### Python (requirements.txt)

| 패키지 | 용도 |
| --- | --- |
| streamlit | 로컬 데모 UI |
| boto3 | AWS SDK (Bedrock, S3, DynamoDB) |
| pydantic | 데이터 모델 검증 |
| python-dotenv | 환경 변수 관리 |

### CDK (deployment/cdk)

| 패키지 | 용도 |
| --- | --- |
| aws-cdk-lib ^2.150.0 | AWS CDK 코어 |
| constructs ^10.3.0 | CDK Constructs |
| typescript ~5.4.5 | TypeScript 컴파일러 |

### Frontend (deployment/frontend)

| 패키지 | 용도 |
| --- | --- |
| react ^18.2.0 | UI 프레임워크 |
| aws-amplify ^6.0.0 | Cognito 인증 |
| @mui/material ^7.3.9 | UI 컴포넌트 |
| vite ^5.0.0 | 빌드 도구 |

---

## 문서

| 문서 | 설명 |
| --- | --- |
| [Submission](assignment-submission.md) | 의사결정 방식, 출력 신뢰성, 확장 설계 |
| [Application Architecture](docs/application_architecture.md) | 시스템 아키텍처, Lambda 구조, 보안 설계 |
| [Code Analysis](docs/code_analysis.md) | 모듈별 구현 분석, 데이터 흐름 |
| [Prompt Engineering](docs/prompt_engineering.md) | 프롬프트 설계, JSON Schema 전략 |
| [Evaluation Criteria](docs/evaluation_criteria.md) | 3축 평가 규칙, 지역별 규제 |
