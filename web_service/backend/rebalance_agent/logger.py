# JSONL 실행 로거 + Tool 반복/실패 가드레일 상태 관리
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agents import RunHooks


LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
RESULT_DIR = Path(__file__).resolve().parent.parent / "result"
TRACE_DIR = Path(__file__).resolve().parent.parent / "traces"


SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "password",
    "payment_info",
    "secret",
    "token",
}
EXCLUDED_KEYS = {
    "address",
    "card_number",
    "credit_card",
    "GEMINI_API_KEY",
    "OPENAI_API_KEY",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def mask_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        masked: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if key in EXCLUDED_KEYS or lowered in EXCLUDED_KEYS:
                continue
            if lowered in SENSITIVE_KEYS or any(part in lowered for part in ("api_key", "token", "secret")):
                masked[key] = "***"
            else:
                masked[key] = mask_sensitive(item)
        return masked
    if isinstance(value, list):
        return [mask_sensitive(item) for item in value]
    return value


class AgentStopRequested(Exception):
    """반복 호출 / 연속 실패 / max_tool_calls 초과 시 raise."""

    def __init__(self, stop_reason: str, detail: str = "") -> None:
        super().__init__(f"{stop_reason}: {detail}")
        self.stop_reason = stop_reason
        self.detail = detail


@dataclass
class GuardrailState:
    MAX_TOOL_CALLS: int = 7
    MAX_CONSECUTIVE_FAILURES: int = 3

    tool_call_count: int = 0
    logged_step: int = 0
    consecutive_failures: int = 0
    seen_tool_call_keys: dict[str, int] = field(default_factory=dict)
    stop_reason: str | None = None
    last_partial_output: dict[str, Any] | None = None

    def reset(self) -> None:
        self.tool_call_count = 0
        self.logged_step = 0
        self.consecutive_failures = 0
        self.seen_tool_call_keys = {}
        self.stop_reason = None
        self.last_partial_output = None

    def record_tool_call(self, tool_name: str, args: dict[str, Any]) -> None:
        # Tool wrapper 진입 시점에서 호출. 한도/반복 위반 시 AgentStopRequested raise.
        self.tool_call_count += 1
        if self.tool_call_count > self.MAX_TOOL_CALLS:
            self.stop_reason = "max_tool_calls"
            raise AgentStopRequested("max_tool_calls", f"tool_call_count={self.tool_call_count}")
        key = f"{tool_name}:{json.dumps(args, sort_keys=True, default=str)}"
        self.seen_tool_call_keys[key] = self.seen_tool_call_keys.get(key, 0) + 1
        if self.seen_tool_call_keys[key] >= 2:
            self.stop_reason = "repeated_tool_call"
            raise AgentStopRequested("repeated_tool_call", key)

    def record_tool_result(self, ok: bool) -> None:
        if ok:
            self.consecutive_failures = 0
            return
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
            self.stop_reason = "tool_failure_limit"
            raise AgentStopRequested(
                "tool_failure_limit", f"consecutive_failures={self.consecutive_failures}"
            )


# 전역 singleton — Tool wrapper와 RunHooks가 공유한다.
guardrail_state = GuardrailState()


class ToolResultRecorder:
    """result/{run_id}/에 Tool input/output JSON 스냅샷을 저장한다."""

    def __init__(self) -> None:
        self.run_id: str | None = None
        self.result_dir: Path | None = None
        self.sequence: int = 0

    def start(self, run_id: str) -> None:
        self.run_id = run_id
        self.sequence = 0
        self.result_dir = RESULT_DIR / run_id

    def stop(self) -> None:
        self.run_id = None
        self.result_dir = None
        self.sequence = 0

    def record(self, tool_name: str, inputs: dict[str, Any], output: dict[str, Any]) -> dict[str, Any]:
        trace_recorder.attach_tool_io(tool_name, inputs, output)
        if self.result_dir is None:
            return output
        self.result_dir.mkdir(parents=True, exist_ok=True)
        self.sequence += 1
        record = {
            "run_id": self.run_id,
            "sequence": self.sequence,
            "tool": tool_name,
            "input": inputs,
            "output": output,
            "ok": output.get("ok"),
            "source": output.get("source"),
            "fallback_used": output.get("fallback_used"),
            "fallback_reason": output.get("fallback_reason"),
        }
        path = self.result_dir / f"{self.sequence:03d}_{tool_name}.json"
        with path.open("w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2, default=str)
        return output


tool_result_recorder = ToolResultRecorder()


class TraceRecorder:
    """Single-run JSON trace used by the Week 8 observability UI."""

    def __init__(self) -> None:
        self.trace_id: str | None = None
        self.path: Path | None = None
        self.trace: dict[str, Any] | None = None
        self._started_perf: float | None = None
        self._pending_by_name: dict[str, list[dict[str, Any]]] = {}

    def start(
        self,
        trace_id: str,
        request: dict[str, Any],
        prompt: str,
        model: str,
        prompt_version: str = "week8-observability-v1",
    ) -> None:
        TRACE_DIR.mkdir(parents=True, exist_ok=True)
        self.trace_id = trace_id
        self.path = TRACE_DIR / f"{trace_id}.json"
        self._started_perf = time.perf_counter()
        self._pending_by_name = {}
        self.trace = {
            "trace_id": trace_id,
            "started_at": utc_now_iso(),
            "ended_at": None,
            "request": mask_sensitive(request),
            "prompt": {
                "version": prompt_version,
                "text": mask_sensitive(prompt),
            },
            "model": {
                "provider": "openai",
                "name": model,
            },
            "steps": [],
            "final_answer": None,
            "chart_data": None,
            "is_saved": False,
            "stop_reason": None,
            "metrics": {
                "total_latency_ms": None,
                "step_count": 0,
                "tool_call_count": 0,
                "tool_error_count": 0,
                "fallback_count": 0,
            },
            "safety": {
                "masked_fields": sorted(SENSITIVE_KEYS),
                "excluded_fields": sorted(EXCLUDED_KEYS),
                "notes": "API keys, tokens, secrets, addresses, and payment fields are masked or excluded.",
            },
        }
        self._write()

    def stop(
        self,
        final_answer: str,
        chart_data: dict[str, Any] | None,
        is_saved: bool,
        stop_reason: str | None,
    ) -> None:
        if not self.trace:
            return
        self.trace["ended_at"] = utc_now_iso()
        self.trace["final_answer"] = final_answer
        self.trace["chart_data"] = mask_sensitive(chart_data)
        self.trace["is_saved"] = is_saved
        self.trace["stop_reason"] = stop_reason or "final_answer"
        if self._started_perf is not None:
            self.trace["metrics"]["total_latency_ms"] = round((time.perf_counter() - self._started_perf) * 1000, 2)
        self._refresh_metrics()
        self._write()
        self.trace_id = None
        self.path = None
        self.trace = None
        self._started_perf = None
        self._pending_by_name = {}

    def fail(self, stop_reason: str, detail: str = "") -> None:
        if not self.trace:
            return
        self.add_instant_step(
            step_type="error",
            name=stop_reason,
            result=None,
            error={"code": stop_reason, "message": detail},
        )

    def start_step(self, step_type: str, name: str, **fields: Any) -> dict[str, Any] | None:
        if not self.trace:
            return None
        step = {
            "step": len(self.trace["steps"]) + 1,
            "type": step_type,
            "name": name,
            "arguments": mask_sensitive(fields.get("arguments")),
            "result": None,
            "error": None,
            "started_at": utc_now_iso(),
            "ended_at": None,
            "latency_ms": None,
            "_started_perf": time.perf_counter(),
        }
        for key, value in fields.items():
            if key != "arguments":
                step[key] = mask_sensitive(value)
        self.trace["steps"].append(step)
        self._pending_by_name.setdefault(name, []).append(step)
        self._write()
        return step

    def finish_step(
        self,
        step: dict[str, Any] | None,
        result: Any = None,
        error: dict[str, Any] | None = None,
    ) -> None:
        if not self.trace or step is None:
            return
        started = step.pop("_started_perf", None)
        step["ended_at"] = utc_now_iso()
        step["latency_ms"] = round((time.perf_counter() - started) * 1000, 2) if started else None
        if result is not None:
            step["result"] = mask_sensitive(result)
        if error is not None:
            step["error"] = mask_sensitive(error)
        self._refresh_metrics()
        self._write()

    def add_instant_step(
        self,
        step_type: str,
        name: str,
        arguments: Any = None,
        result: Any = None,
        error: dict[str, Any] | None = None,
    ) -> None:
        step = self.start_step(step_type, name, arguments=arguments)
        self.finish_step(step, result=result, error=error)

    def attach_tool_io(self, tool_name: str, inputs: dict[str, Any], output: dict[str, Any]) -> None:
        if not self.trace:
            return
        queue = self._pending_by_name.get(tool_name) or []
        step = next((item for item in reversed(queue) if item.get("type") == "tool_call" and item.get("result") is None), None)
        if step is None:
            step = self.start_step("tool_call", tool_name)
        if step is None:
            return
        step["arguments"] = mask_sensitive(inputs)
        step["result"] = mask_sensitive(output)
        if output.get("ok") is False:
            step["error"] = mask_sensitive(output.get("error") or output.get("original_error"))
        self._refresh_metrics()
        self._write()

    def _refresh_metrics(self) -> None:
        if not self.trace:
            return
        steps = self.trace["steps"]
        tool_steps = [step for step in steps if step.get("type") == "tool_call"]
        self.trace["metrics"]["step_count"] = len(steps)
        self.trace["metrics"]["tool_call_count"] = len(tool_steps)
        self.trace["metrics"]["tool_error_count"] = sum(1 for step in tool_steps if step.get("error"))
        self.trace["metrics"]["fallback_count"] = sum(
            1
            for step in tool_steps
            if isinstance(step.get("result"), dict) and step["result"].get("fallback_used")
        )

    def _write(self) -> None:
        if not self.path or not self.trace:
            return
        serializable = json.loads(json.dumps(self.trace, ensure_ascii=False, default=str))
        for step in serializable.get("steps", []):
            step.pop("_started_perf", None)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2, default=str)


trace_recorder = TraceRecorder()


class JsonlLogger:
    """logs/{ISO}.jsonl에 Agent run 이벤트를 append."""

    def __init__(self, run_id: str | None = None, log_dir: Path | None = None) -> None:
        self.log_dir = log_dir or LOG_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.run_id = run_id or ts
        self.path = self.log_dir / f"{self.run_id}.jsonl"
        self._tool_events: list[dict[str, Any]] = []

    def log(self, event_type: str, **fields: Any) -> None:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
            **fields,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        if event_type in ("tool_call", "tool_result"):
            self._tool_events.append(record)

    def summarize(self) -> dict[str, Any]:
        tools_used: dict[str, int] = {}
        fallback_count = 0
        ok_false_count = 0
        for rec in self._tool_events:
            if rec["type"] == "tool_call":
                t = rec.get("tool", "?")
                tools_used[t] = tools_used.get(t, 0) + 1
            elif rec["type"] == "tool_result":
                if rec.get("fallback_used"):
                    fallback_count += 1
                if rec.get("ok") is False:
                    ok_false_count += 1
        return {
            "run_id": self.run_id,
            "tools_used": tools_used,
            "fallback_count": fallback_count,
            "ok_false_count": ok_false_count,
            "tool_call_count": guardrail_state.tool_call_count,
            "logged_step": guardrail_state.logged_step,
            "stop_reason": guardrail_state.stop_reason,
        }


class LoggingAndGuardrailHooks(RunHooks):
    """OpenAI Agents SDK RunHooks 구현. JSONL 로깅 + Tool 결과 ok=false 카운트.

    SDK 0.16의 on_tool_start는 tool 객체만 받고, args는 ToolContext.tool_arguments를 통해서만
    노출된다. 단순화를 위해 args 기반의 반복 감지는 각 Tool wrapper 내부의
    guardrail_state.record_tool_call(...) 호출로 일원화한다.
    """

    def __init__(self, logger: JsonlLogger) -> None:
        super().__init__()
        self.logger = logger

    def _step(self) -> int:
        guardrail_state.logged_step += 1
        return guardrail_state.logged_step

    async def on_agent_start(self, context, agent) -> None:
        self.logger.log("agent_start", step=self._step(), agent=agent.name)
        trace_recorder.add_instant_step("agent", "agent_start", result={"agent": agent.name})

    async def on_agent_end(self, context, agent, output) -> None:
        self.logger.log(
            "agent_end",
            step=self._step(),
            agent=agent.name,
            output_type=type(output).__name__,
        )
        trace_recorder.add_instant_step(
            "agent",
            "agent_end",
            result={"agent": agent.name, "output_type": type(output).__name__},
        )

    async def on_llm_start(self, context, agent, system_prompt, input_items) -> None:
        self.logger.log("llm_start", step=self._step())
        trace_recorder.start_step("llm", "llm_call", input_items=input_items)

    async def on_llm_end(self, context, agent, response) -> None:
        self.logger.log("llm_end", step=self._step())
        queue = trace_recorder._pending_by_name.get("llm_call", [])
        step = next((item for item in reversed(queue) if item.get("ended_at") is None), None)
        trace_recorder.finish_step(step, result={"response_type": type(response).__name__})

    async def on_tool_start(self, context, agent, tool) -> None:
        self.logger.log("tool_call", step=self._step(), tool=tool.name)
        trace_recorder.start_step("tool_call", tool.name)

    async def on_tool_end(self, context, agent, tool, result) -> None:
        ok: bool | None = None
        source: str | None = None
        fallback_used = False
        fallback_reason: str | None = None
        try:
            parsed = json.loads(result) if isinstance(result, str) else dict(result)
            ok = parsed.get("ok")
            source = parsed.get("source")
            fallback_used = bool(parsed.get("fallback_used"))
            fallback_reason = parsed.get("fallback_reason")
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        self.logger.log(
            "tool_result",
            step=self._step(),
            tool=tool.name,
            ok=ok,
            source=source,
            fallback_used=fallback_used,
            fallback_reason=fallback_reason,
        )
        queue = trace_recorder._pending_by_name.get(tool.name, [])
        step = next((item for item in reversed(queue) if item.get("type") == "tool_call" and item.get("ended_at") is None), None)
        error = None
        if ok is False:
            try:
                parsed = json.loads(result) if isinstance(result, str) else dict(result)
                error = parsed.get("error") or parsed.get("original_error")
            except (json.JSONDecodeError, TypeError, ValueError):
                error = {"code": "TOOL_ERROR", "message": "Tool returned an unparseable error payload."}
        trace_recorder.finish_step(step, error=error)
        try:
            guardrail_state.record_tool_result(ok if ok is not None else True)
        except AgentStopRequested as e:
            self.logger.log("guardrail_stop", step=self._step(), stop_reason=e.stop_reason, detail=e.detail)
            trace_recorder.fail(e.stop_reason, e.detail)
            raise
