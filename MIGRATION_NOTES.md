# Migration Notes

This project now uses `1hjjun/InvestingAIagent` as the GitHub target repository.

## What Was Merged

- The original ETF rebalancing agent from `week-7/1hjjun/src` was moved into:
  - `web_service/backend/rebalance_agent/`
- The original Next.js rebalancing UI was moved into:
  - `web_service/frontend/src/app/page.tsx`
  - `web_service/frontend/src/app/dev/page.tsx`
- The new investing assistant service was added around it:
  - portfolio dashboard
  - portfolio image analysis page
  - macro YouTube analysis page
  - FastAPI integration layer

## Not Directly Copied

These files from the original repository were not copied as-is because the app structure changed:

- `week-7/1hjjun/tests/`
- `week-7/1hjjun/examples/`
- `week-7/1hjjun/submission/`
- `week-7/1hjjun/architecture.md`
- `week-7/1hjjun/design.md`
- `week-7/1hjjun/WEEK8_OBSERVABILITY.md`
- `week-8/`

The main runtime functionality from those submissions is represented in the new `web_service/` structure.

## Private Data Excluded From Git

The following are intentionally excluded:

- `.env`
- `.venv/`
- local data directories
- local image directories
- `external/`
- generated Next.js build/cache files
- backend traces, logs, result, uploads, cache

This keeps API keys, private captures, generated analysis output, local DB files, and personal portfolio data out of GitHub.
