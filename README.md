# 📊 공시 분석 AI

DART 공시문서를 AI로 분석하여 요약과 질의응답을 제공하는 시스템입니다.

## ✨ 주요 기능

### 🎯 Progressive Disclosure UX
- **1단계**: 공시문서 자동 요약 생성
- **2단계**: 맥락 기반 구체적 질문 유도
- **3단계**: 정교한 AI 분석 답변 제공

### 🔧 핵심 기능
- **하이브리드 청킹**: 구조화된 데이터와 일반 텍스트를 구분하여 처리
- **의미적 검색**: OpenAI 임베딩 기반 유사도 검색 + 키워드 리랭킹
- **멀티 에이전트**: 요약 전문가, 분석 전문가 분리
- **실시간 뉴스**: 네이버 뉴스 API 연동으로 최신 정보 반영

## 🏗️ 시스템 아키텍처

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI       │    │   LangGraph     │    │   ChromaDB      │
│   (REST API)    │───▶│   (Workflow)    │───▶│   (Vector DB)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   OpenAI API    │    │   Naver API     │
                       │   (GPT-4/임베딩) │    │   (뉴스검색)     │
                       └─────────────────┘    └─────────────────┘
```

## 📦 설치 및 실행

### 1. 프로젝트 클론
```bash
git clone <repository-url>
cd disclosure-analysis-ai
```

### 2. 가상환경 생성 및 활성화
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate  # Windows
```

### 3. 의존성 설치
```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정
```bash
cp .env.example .env
# .env 파일을 열고 API 키들을 설정하세요
```

필수 API 키:
- **OPENAI_API_KEY**: OpenAI API 키
- **DART_API_KEY**: DART API 키 ([신청](https://opendart.fss.or.kr/))
- **NAVER_CLIENT_ID**: 네이버 개발자 센터에서 발급
- **NAVER_CLIENT_SECRET**: 네이버 개발자 센터에서 발급

### 5. 서버 실행
```bash
python main.py
```

서버가 실행되면 다음 URL에서 API 문서를 확인할 수 있습니다:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🚀 사용 방법

### 1️⃣ 기본 워크플로우

#### Step 1: 기업 검색
```bash
curl "http://localhost:8000/api/v1/companies/search?query=삼성전자&limit=5"
```

#### Step 2: 공시문서 검색
```bash
curl -X POST "http://localhost:8000/api/v1/companies/documents/search" \
  -H "Content-Type: application/json" \
  -d '{
    "corp_code": "00126380",
    "report_types": ["A001", "A003"]
  }'
```

#### Step 3: 문서 인덱싱 요청
```bash
curl -X POST "http://localhost:8000/api/v1/documents/index" \
  -H "Content-Type: application/json" \
  -d '{
    "rcept_no": "20231114000123",
    "corp_name": "삼성전자"
  }'
```

#### Step 4: 인덱싱 상태 확인
```bash
curl "http://localhost:8000/api/v1/documents/index/{task_id}/status"
```

#### Step 5: 요약 확인
```bash
curl "http://localhost:8000/api/v1/documents/20231114000123/summary"
```

#### Step 6: 질의응답
```bash
curl -X POST "http://localhost:8000/api/v1/query/" \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "20231114000123",
    "question": "올해 3분기 매출액과 영업이익은 얼마인가요?",
    "include_news": true
  }'
```

### 2️⃣ 고급 기능

#### 문서 내 검색
```bash
curl "http://localhost:8000/api/v1/query/20231114000123/search?query=반도체&top_k=3"
```

#### 배치 질의
```bash
curl -X POST "http://localhost:8000/api/v1/query/batch?document_id=20231114000123" \
  -H "Content-Type: application/json" \
  -d '{
    "questions": [
      "매출액이 전년 대비 얼마나 증가했나요?",
      "주요 위험 요인은 무엇인가요?",
      "신규 투자 계획이 있나요?"
    ],
    "include_news": true
  }'
```

#### 후속 질문 제안
```bash
curl -X POST "http://localhost:8000/api/v1/query/20231114000123/follow-up" \
  -H "Content-Type: application/json" \
  -d '"이번 분기 실적은 어땠나요?"'
```

## 📁 프로젝트 구조

```
project/
├── main.py                 # FastAPI 메인 애플리케이션
├── config.py              # 설정 및 환경변수
├── workflow.py            # LangGraph 워크플로우
├── requirements.txt       # Python 의존성
├── .env.example          # 환경변수 예제
├── README.md             # 이 파일
├── models/
│   ├── schemas.py        # Pydantic 스키마
│   └── state.py         # LangGraph 상태 정의
├── agents/
│   ├── summary_agent.py  # 문서 요약 에이전트
│   └── analysis_agent.py # 질의응답 에이전트
├── services/
│   ├── news_service.py   # 네이버 뉴스 서비스
│   └── embedding_service.py # 임베딩 및 벡터 검색
├── utils/
│   └── chunking.py       # 하이브리드 문서 청킹
└── api/
    ├── documents.py      # 문서 인덱싱 API
    └── query.py         # 질의응답 API
```

## 🎨 UX 설계 원칙

### Progressive Disclosure (점진적 정보 공개)
복잡한 금융 정보를 단계적으로 제공하여 사용자의 이해도를 향상시킵니다.

1. **요약본 제공**: AI가 생성한 구조화된 요약
2. **맥락 파악**: 사용자가 문서 내용을 이해
3. **구체적 질문**: 맥락 기반의 정교한 질의
4. **정밀한 답변**: 컨텍스트를 활용한 상세 분석

### 하이브리드 청킹 전략
- **구조화된 데이터**: 재무제표 → 테이블 단위 청킹
- **일반 텍스트**: 사업 현황 → 의미 단위 청킹
- **긴 섹션**: 토큰 제한 고려한 오버랩 청킹

## ⚙️ 주요 설정

### 모델 설정
- **GPT-4**: 요약 및 분석 생성
- **text-embedding-3-small**: 벡터 임베딩
- **ChromaDB**: 벡터 저장소

### 청킹 설정
- **CHUNK_SIZE**: 800토큰
- **CHUNK_OVERLAP**: 200토큰
- **MAX_TOKENS_PER_CHUNK**: 1000토큰

### 성능 제한
- **요약 생성**: 최대 60초
- **동시 청킹**: 최대 5개
- **임베딩 배치**: 10개씩

## 🔧 모니터링 및 디버깅

### 헬스 체크
```bash
curl "http://localhost:8000/health"
```

### API 정보 조회
```bash
curl "http://localhost:8000/api/v1/info"
```

### 벡터 DB 통계
```bash
curl "http://localhost:8000/api/v1/documents/stats"
```

### 문서 청크 조회 (디버깅용)
```bash
curl "http://localhost:8000/api/v1/documents/20231114000123/chunks"
```

## 🚨 주의사항

### API 사용량 관리
- OpenAI API: 토큰 사용량에 따른 과금
- DART API: 일일 요청 제한 확인
- 네이버 API: 일일 25,000건 제한

### 성능 최적화
- 문서 크기가 클수록 처리 시간 증가
- 임베딩 생성은 배치 단위로 처리
- ChromaDB는 로컬 디스크에 영구 저장

### 에러 처리
- 요약 생성 시간 초과: 60초 제한
- 문서 다운로드 실패: DART API 상태 확인
- 임베딩 생성 실패: OpenAI API 키 및 할당량 확인

## 🤝 기여 가이드

1. 이슈 등록 또는 기능 제안
2. 브랜치 생성: `git checkout -b feature/amazing-feature`
3. 변경사항 커밋: `git commit -m 'Add amazing feature'`
4. 브랜치 푸시: `git push origin feature/amazing-feature`
5. Pull Request 생성

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 🙋‍♂️ 지원

문제가 발생하거나 질문이 있으시면 GitHub Issues를 통해 문의해주세요.

---