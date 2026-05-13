# Mind Investing AI

개인 포트폴리오와 시장 자료를 함께 보며 투자 판단을 정리하는 로컬 AI 투자 리서치 서비스입니다.

현재 버전은 FastAPI 백엔드와 Next.js 프론트엔드로 구성되어 있으며, 포트폴리오 이미지 분석, YouTube 기반 매크로 분석, 투자 대시보드, Agent 실행 기록 확인 화면을 제공합니다.

## 주요 기능

- 포트폴리오 이미지 기반 보유 자산 분석
- YouTube 영상 최대 3개 기반 매크로 환경 분석
- 현재 포트폴리오 대시보드
- 날짜별 투자 대화/실행 기록 요약
- Agent 실행 trace 확인
- FastAPI + Next.js 분리 구조

## 폴더 구조

```text
mindInvesting/
  web_service/
    backend/
      main.py
      requirements.txt
      rebalance_agent/

    frontend/
      src/app/
        page.tsx
        portfolio/page.tsx
        macro/page.tsx
        dashboard/page.tsx
        dev/page.tsx

  src/
    memory_store.py
    portfolio_analytics.py
    profile_store.py

```

## 실행 방법

먼저 Python 가상환경을 만들고 백엔드 의존성을 설치합니다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r web_service/backend/requirements.txt
```

프론트엔드 의존성을 설치합니다.

```bash
cd web_service/frontend
npm install
cd ../..
```

환경변수 파일을 만듭니다.

```bash
cp .env.example .env
```

`.env` 파일에 API 키를 입력합니다.

```env
OPENAI_API_KEY=your_api_key_here
```

개발 서버를 실행합니다.

터미널 1에서 백엔드를 실행합니다.

```bash
source .venv/bin/activate
uvicorn web_service.backend.main:app --reload --port 8000
```

터미널 2에서 프론트엔드를 실행합니다.

```bash
cd web_service/frontend
npm run dev
```

브라우저에서 아래 주소를 엽니다.

```text
http://127.0.0.1:3000
```

## 화면

```text
/           리밸런싱 Agent 실행
/portfolio  포트폴리오 이미지 분석
/macro      YouTube 기반 매크로 분석
/dashboard  포트폴리오 대시보드와 기록 요약
/dev        Agent trace 확인
```

## 개발 메모

- 백엔드는 `uvicorn --reload`로 자동 갱신됩니다.
- 프론트엔드는 `next dev`로 자동 갱신됩니다.
- API 키와 개인 투자 데이터는 Git에 올리지 않습니다.
- 로컬 실행 결과, 업로드 파일, 캐시, 로그는 `.gitignore`로 제외합니다.

## 검증

프론트엔드 타입 체크:

```bash
cd web_service/frontend
npx tsc --noEmit
```

백엔드 문법 체크:

```bash
.venv/bin/python -m py_compile web_service/backend/main.py
```
