# Next Plan: Mind Investing AI 인수인계

## 현재 상태

이 프로젝트는 `1hjjun/InvestingAIagent` 저장소의 `main` 브랜치 기준으로 작업 중이다.

최근 변경분은 GitHub에 푸쉬 완료했다.

```text
latest pushed commit: 3d59aec Apply WDS base styling
remote: https://github.com/1hjjun/InvestingAIagent.git
branch: main
```

현재 앱은 FastAPI 백엔드 + Next.js 프론트 구조다.

```text
web_service/
  backend/
    main.py
    rebalance_agent/

  frontend/
    src/app/
      page.tsx        # 리밸런싱 AI agent
      portfolio/      # 포트폴리오 이미지/대시보드
      macro/          # YouTube 기반 매크로 분석
      RAG/            # 투자 RAG
      journal/        # 날짜별 대화 노트
      dev/            # trace 확인
```

## 실행

루트에서 백엔드:

```bash
source .venv/bin/activate
uvicorn web_service.backend.main:app --reload --port 8000
```

프론트:

```bash
cd web_service/frontend
npx pnpm@10 install
npx pnpm@10 dev
```

브라우저:

```text
http://127.0.0.1:3000
```

## 중요한 보안/데이터 주의사항

- PDF 캡쳐본 이미지, 원본 OCR 결과, 개인 포트폴리오 데이터는 GitHub에 올리면 안 된다.
- `data/`, `images/`, `images_by_topic/`, `.env`는 ignore 대상이다.
- GitHub Packages 토큰은 절대 채팅이나 파일에 넣지 않는다.
- `@wanteddev/wds` 설치에는 GitHub Packages 접근 토큰이 필요하다.
- `.npmrc`는 아래처럼 환경변수만 참조한다.

```ini
@wanteddev:registry=https://npm.pkg.github.com/
//npm.pkg.github.com/:_authToken=${GITHUB_TOKEN}
```

## 최근 완료한 일

### 1. 리밸런싱 AI agent

- `/` 페이지를 ChatGPT 비슷한 대화형 화면으로 변경했다.
- 입력창은 placeholder 방식으로 바꿔서 예시 문구를 매번 지우지 않아도 된다.
- `Enter` 입력 시 전송, `Shift+Enter`는 줄바꿈이다.
- 대화창 높이를 고정하고 내부 스크롤을 사용하도록 바꿨다.
- 대화는 SQLite 기반으로 서버에 저장된다.
- 다른 페이지를 갔다 와도 `/` 대화가 복원된다.

관련 파일:

```text
web_service/frontend/src/app/page.tsx
src/conversation_store.py
web_service/backend/main.py
```

### 2. 저장된 포트폴리오 컨텍스트

- 이미지가 없어도 저장된 포트폴리오와 analytics를 agent가 읽는다.
- 현재 포트폴리오, 총 시드, 현금 비중, 테마 배분이 agent 프롬프트에 들어간다.
- 이미지가 없다는 이유로 답변을 거절하지 않도록 프롬프트를 수정했다.

관련 파일:

```text
web_service/backend/main.py
web_service/backend/rebalance_agent/agent.py
web_service/backend/rebalance_agent/prompts.py
web_service/backend/rebalance_agent/schema.py
```

### 3. 답변 자유도 조정

- 답변 형식을 고정하지 않도록 바꿨다.
- 유튜브 요약만 요청하면 요약 중심으로 답한다.
- 매크로 분석이면 지표 해석 중심, 리밸런싱이면 포트폴리오 판단 중심으로 답한다.
- 단, 핵심 판단과 이유는 반드시 도구 결과 또는 입력 컨텍스트에 근거해야 한다.

관련 파일:

```text
web_service/backend/rebalance_agent/prompts.py
```

### 4. 페이지 구조 변경

- `/chat`은 `/RAG`로 이동했다.
- `/chat`은 `/RAG`로 redirect 한다.
- 화면 이름은 `투자 RAG`다.
- `/dashboard`는 `/journal`로 이동했다.
- `/dashboard`는 `/journal`로 redirect 한다.
- `/journal`은 오늘 날짜 카드를 가운데 두고 앞뒤 2일씩 총 5개 카드를 보여준다.
- 선택한 카드의 글 내용은 아래에 표시된다.

관련 파일:

```text
web_service/frontend/src/app/RAG/page.tsx
web_service/frontend/src/app/chat/page.tsx
web_service/frontend/src/app/journal/page.tsx
web_service/frontend/src/app/dashboard/page.tsx
web_service/frontend/src/app/layout.tsx
```

### 5. pnpm 전환

- 프론트 패키지 매니저를 pnpm 기준으로 전환했다.
- `package-lock.json` 제거.
- `pnpm-lock.yaml` 생성.
- `packageManager`는 `pnpm@10.33.4`.
- 로컬에 전역 pnpm이 없으면 `npx pnpm@10 ...`을 사용한다.

관련 파일:

```text
web_service/frontend/package.json
web_service/frontend/pnpm-lock.yaml
web_service/README.md
```

### 6. Wanted WDS 적용

- `@wanteddev/wds`, `@wanteddev/wds-icon`, `@wanteddev/wds-nextjs` 설치 완료.
- `@wanteddev/wds/global.css` 로드.
- Pretendard font 로드.
- `AppRouterCacheProvider` 연결.
- 전역 스타일과 메인 agent 화면을 더 제품형 톤으로 정리했다.

주의:

- WDS `ThemeProvider`를 붙이면 현재 Next 14 빌드에서 `Unexpected end of JSON input` 빌드 오류가 난다.
- 그래서 지금은 `ThemeProvider`는 제외하고 `AppRouterCacheProvider`만 사용한다.
- `pnpm build`는 현재 통과한다.

관련 파일:

```text
web_service/frontend/src/app/providers.tsx
web_service/frontend/src/app/layout.tsx
web_service/frontend/src/app/globals.css
web_service/frontend/tailwind.config.js
web_service/frontend/next.config.mjs
web_service/frontend/src/app/page.tsx
```

## 검증 상태

최근 검증:

```bash
cd web_service/frontend
GITHUB_TOKEN=dummy npx pnpm@10 build
```

결과:

```text
Next.js build passed
```

## 다음에 하면 좋은 일

1. 전체 페이지를 WDS 톤으로 통일
   - 현재는 메인 agent 화면 위주로 정리됨.
   - `/portfolio`, `/macro`, `/RAG`, `/journal`, `/dev`도 같은 톤으로 다듬으면 좋다.

2. WDS 컴포넌트 직접 적용 검토
   - `Button`, `TextArea`, `TextField`, `Card`, `ScrollArea` 등을 점진 적용.
   - 단, `ThemeProvider` 빌드 이슈를 먼저 해결하거나 우회해야 한다.

3. active nav 상태 추가
   - 현재 상단 nav는 hover만 있고 현재 페이지 표시가 없다.
   - client component nav를 만들어 pathname 기반 active 스타일을 넣으면 좋다.

4. agent tool 진행 상태를 실제 trace 기반으로 표시
   - 현재 `/` 진행 상태는 프론트에서 예상 tool plan을 보여주는 방식이다.
   - 향후 SSE/WebSocket 또는 polling으로 실제 tool call을 보여주면 더 좋다.

5. 대화 저장 구조 확장
   - 현재는 `default` 사용자와 `rebalance-agent` 대화방 하나만 사용.
   - 로그인 도입 시 `user_id`, `conversation_id`를 실제 계정 기준으로 분리해야 한다.

6. 배포 준비
   - FastAPI/Next 분리 배포 구조 정리.
   - DB를 SQLite에서 Postgres 등으로 전환.
   - 업로드 파일 저장소, 백업, 인증, 권한, 결제 설계.

## Codex 작업 원칙

- 사용자는 푸쉬를 원할 때만 푸쉬한다.
- 평소에는 로컬 커밋만 한다.
- PDF 관련 이미지/데이터는 절대 GitHub에 올리지 않는다.
- `.env`와 토큰은 절대 커밋하지 않는다.
- 변경 후 가능하면 `npx pnpm@10 build` 또는 최소 `npx pnpm@10 exec tsc --noEmit`으로 확인한다.
