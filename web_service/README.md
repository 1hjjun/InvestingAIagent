# Mind Investing AI Web Service

투자 리밸런싱 Agent를 제품형 구조로 옮기기 위한 FastAPI + Next.js 웹서비스 초안입니다.

## 구조

```text
web_service/
  backend/
    main.py              # FastAPI API
    requirements.txt
    rebalance_agent/     # 기존 ETF 리밸런싱 Agent 백엔드

  frontend/
    src/app/page.tsx            # 기존 ETF 리밸런싱 실행 화면
    src/app/portfolio/page.tsx  # 포트폴리오 이미지 분석 작업대
    src/app/macro/page.tsx      # YouTube 기반 매크로 분석 작업대
    src/app/dev/page.tsx        # 기존 trace/dev 화면
    src/app/dashboard/page.tsx  # 포트폴리오/대화 노트 대시보드
```

## 실행 방법

가장 쉬운 방법은 프로젝트 루트에서 개발 서버 통합 스크립트를 실행하는 것입니다.

```bash
./scripts/dev_web.sh
```

이 스크립트는 아래 두 서버를 함께 실행합니다.

```text
FastAPI 백엔드: http://127.0.0.1:8000
Next.js 프론트: http://127.0.0.1:3000
```

코드를 수정하면 자동 반영됩니다.

- 백엔드 Python 코드를 수정하면 `uvicorn --reload`가 FastAPI를 다시 로드합니다.
- 프론트 React/Next 코드를 수정하면 `next dev`가 화면을 자동 갱신합니다.
- 종료는 터미널에서 `Ctrl+C`를 누르면 됩니다.

처음 한 번은 의존성을 설치해야 합니다.

```bash
source .venv/bin/activate
pip install -r web_service/backend/requirements.txt

cd web_service/frontend
npm install
cd ../..
```

수동으로 따로 실행하고 싶다면 아래처럼 실행합니다.

프로젝트 루트에서 백엔드를 실행합니다.

```bash
source .venv/bin/activate
pip install -r web_service/backend/requirements.txt
uvicorn web_service.backend.main:app --reload --port 8000
```

다른 터미널에서 프론트를 실행합니다.

```bash
cd web_service/frontend
npm install
npm run dev
```

브라우저에서 엽니다.

```text
http://127.0.0.1:3000
```

라우트:

```text
/           기존 ETF 리밸런싱 실행 화면
/portfolio  포트폴리오 이미지 분석 화면
/macro      YouTube 최대 3개 기반 매크로 분석 화면
/dev        기존 trace 확인 화면
/dashboard  포트폴리오 대시보드와 날짜별 대화 노트
```

배포용 빌드 확인은 아래 명령으로 합니다.

```bash
cd web_service/frontend
npm run build
```

개발 서버(`npm run dev`)가 켜져 있을 때 `npm run build`를 동시에 실행하면 Next.js의 `.next` 캐시가 섞여 CSS가 깨져 보일 수 있습니다. 빌드 확인은 개발 서버를 종료한 뒤 실행하세요.

## 현재 연결된 기능

- 기존 ETF 리밸런싱 Agent 실행: `POST /api/runs`
- 기존 ETF 리밸런싱 Agent 이미지 업로드 실행: `POST /api/runs/upload`
- 기존 trace 목록/상세: `GET /api/runs`, `GET /api/runs/{trace_id}`
- 포트폴리오 조회: `GET /api/portfolio`
- 포트폴리오 분석: `GET /api/portfolio/analytics`
- 대화 메모리 조회: `GET /api/memory`
- 날짜별 대화 노트 조회: `GET /api/journals`

## 주의

- `.env`, `data/`, `images/`는 개인 투자정보와 API 키가 포함될 수 있으므로 GitHub에 올리지 않습니다.
- 현재 버전은 로컬 개발용 초안입니다. 로그인, DB, 파일 업로드, 결제/권한, 백업은 다음 단계에서 추가합니다.
- 프론트는 빌드 안정성을 위해 `Next 14.2.35 + React 18.3.1` 조합으로 고정했습니다.
