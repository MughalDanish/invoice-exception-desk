"""Fenced, durable live-call reservations. Unknown provider usage never becomes zero."""

import json
import random
import time
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select

from app.db.models import InvestigationRun
from app.modules.investigation.queue import database_now, event, owned


class LiveLimitError(Exception):
    """A bounded live run cannot continue; no financial fallback is permitted."""

    def __init__(self, code, *, resource=None):
        super().__init__(code)
        self.resource = resource


class LiveBudget:
    def __init__(self, factory, claim, settings):
        self.factory, self.claim, self.settings = factory, claim, settings

    def _run(self, session):
        run = session.scalar(
            select(InvestigationRun)
            .where(InvestigationRun.id == self.claim.run_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not owned(run, self.claim, database_now(session)):
            raise LiveLimitError("INVESTIGATION_OWNERSHIP_LOST")
        return run

    def remaining(self):
        with self.factory.begin() as session:
            run = self._run(session)
            now = database_now(session)
            data = dict(run.budget_metadata or {})
            if "deadline" not in data:
                data["deadline"] = (
                    now + timedelta(seconds=self.settings.investigation_deadline_seconds)
                ).isoformat()
                run.budget_metadata = data
            if "limits" not in data:
                data["limits"] = {
                    k: getattr(self.settings, k)
                    for k in (
                        "investigation_max_model_steps",
                        "investigation_max_http_attempts",
                        "investigation_max_tool_calls",
                        "investigation_token_budget",
                        "investigation_max_output_tokens",
                    )
                }
                run.budget_metadata = data
            seconds = (datetime.fromisoformat(data["deadline"]) - now).total_seconds()
            if seconds <= 0:
                raise LiveLimitError("INVESTIGATION_DEADLINE")
            return seconds

    def reserve(self, kind, input_bytes, *, logical=True):
        self.remaining()
        with self.factory.begin() as session:
            run = self._run(session)
            data = dict(run.budget_metadata or {})
            calls = list(data.get("calls", []))
            steps = data.get("steps", 0) + int(logical)
            limits = data["limits"]
            reserve = input_bytes + limits["investigation_max_output_tokens"]
            consumed = sum(c["charged"] for c in calls)
            if (
                steps > limits["investigation_max_model_steps"]
                or len(calls) >= limits["investigation_max_http_attempts"]
                or consumed + reserve > limits["investigation_token_budget"]
            ):
                resource = (
                    "model_steps"
                    if steps > limits["investigation_max_model_steps"]
                    else "http_attempts"
                    if len(calls) >= limits["investigation_max_http_attempts"]
                    else "tokens"
                )
                raise LiveLimitError("INVESTIGATION_MODEL_BUDGET", resource=resource)
            call_id = uuid.uuid4().hex
            calls.append(
                {
                    "id": call_id,
                    "kind": kind,
                    "reserved": reserve,
                    "charged": reserve,
                    "usage": None,
                    "status": "PENDING",
                }
            )
            data.update(calls=calls, steps=steps)
            run.budget_metadata = data
            event(
                session,
                run,
                "MODEL_STARTED",
                call_id=call_id,
                kind=kind,
                attempt=len(calls),
                reserved_tokens=reserve,
            )
            return call_id

    def observe(self, event_type, **details):
        """Code-controlled metadata only; references and model contents stay private."""
        with self.factory.begin() as session:
            event(session, self._run(session), event_type, **details)

    def reconcile(
        self,
        call_id,
        *,
        usage=None,
        latency_ms=0,
        error=None,
        finish=None,
        provider_error_code=None,
        provider_diagnostics=None,
    ):
        with self.factory.begin() as session:
            run = self._run(session)
            data = dict(run.budget_metadata)
            calls = [dict(c) for c in data.get("calls", [])]
            call = next(c for c in calls if c["id"] == call_id)
            call.update(
                status="FAILED" if error else "COMPLETED", latency_ms=latency_ms, error=error
            )
            if provider_diagnostics:
                call["provider_diagnostics"] = provider_diagnostics
            if usage is not None:
                call["usage"] = usage
                total = usage.get("total_tokens")
                if isinstance(total, int) and total >= 0:
                    call["charged"] = total
            data["calls"] = calls
            run.budget_metadata = data
            event(
                session,
                run,
                "MODEL_FAILED" if error else "MODEL_COMPLETED",
                call_id=call_id,
                latency_ms=latency_ms,
                usage=call["usage"],
                error_type=error,
                finish_reason=finish,
                provider_error_code=provider_error_code,
                **({"provider_diagnostics": provider_diagnostics} if provider_diagnostics else {}),
            )

    def tool(self, name):
        self.remaining()
        with self.factory.begin() as session:
            run = self._run(session)
            data = dict(run.budget_metadata or {})
            count = data.get("tool_calls", 0) + 1
            if count > data["limits"]["investigation_max_tool_calls"]:
                raise LiveLimitError("INVESTIGATION_TOOL_BUDGET")
            data["tool_calls"] = count
            run.budget_metadata = data
            event(session, run, "TOOL_STARTED", tool=name, call=count)

    def tool_done(self, name, result, latency_ms, cache_hit=False):
        from app.modules.approvals.service import payload_hash

        with self.factory.begin() as session:
            run = self._run(session)
            event(
                session,
                run,
                "TOOL_COMPLETED",
                tool=name,
                latency_ms=latency_ms,
                result_hash=payload_hash(result.model_dump(mode="json")),
                cache_hit=cache_hit,
            )

    def call(self, kind, payload, operation, authorize, estimator=None):
        # UTF-8 byte length is deliberately conservative for ordinary serialized
        # inputs. Unknown/ambiguous usage retains the full reservation. Provider
        # billing is not promised to be exact, including opaque thinking tokens.
        input_bytes = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
        if estimator is not None:
            authorize()
            input_bytes = estimator(payload, timeout_seconds=min(10, self.remaining()))
            with self.factory.begin() as session:
                run = self._run(session)
                event(session, run, "TOKENS_COUNTED", kind=kind, reserved_input_tokens=input_bytes)
        for attempt in range(3):
            authorize()
            remaining = self.remaining()
            try:
                call_id = self.reserve(kind, input_bytes, logical=attempt == 0)
            except LiveLimitError as exc:
                if exc.resource is not None:
                    self.observe("BUDGET_EXHAUSTED", resource=exc.resource, kind=kind)
                raise
            with self.factory() as session:
                output_limit = self._run(session).budget_metadata["limits"][
                    "investigation_max_output_tokens"
                ]
            started = time.monotonic()
            try:
                result = operation(min(60, remaining), output_limit)
            except Exception as exc:
                usage = getattr(exc, "usage", None)
                from app.modules.investigation.gemini_provider import GeminiInvestigationError

                self.reconcile(
                    call_id,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    error=type(exc).__name__,
                    usage=usage.model_dump(mode="json") if usage else None,
                    provider_error_code=exc.code
                    if isinstance(exc, GeminiInvestigationError)
                    else None,
                    provider_diagnostics=exc.diagnostics
                    if isinstance(exc, GeminiInvestigationError)
                    else None,
                )
                import httpx
                from google.genai import errors

                transient = (
                    getattr(exc, "retryable", False)
                    or isinstance(exc, httpx.TransportError)
                    or (
                        isinstance(exc, errors.APIError)
                        and getattr(exc, "code", None) in (429, 500, 502, 503, 504)
                    )
                )
                if not transient or attempt == 2:
                    raise
                delay = 2**attempt + random.uniform(0, 0.25)
                if self.remaining() <= delay:
                    raise LiveLimitError("INVESTIGATION_DEADLINE") from None
                self.observe(
                    "MODEL_RETRY_SCHEDULED",
                    call_id=call_id,
                    kind=kind,
                    failed_attempt=attempt + 1,
                    next_attempt=attempt + 2,
                    backoff_seconds=round(delay, 3),
                )
                time.sleep(delay)
            else:
                usage = result.usage.model_dump(mode="json")
                self.reconcile(
                    call_id, usage=usage, latency_ms=result.latency_ms, finish=result.finish_reason
                )
                authorize()
                self.remaining()
                with self.factory.begin() as session:
                    run = self._run(session)
                    if (
                        sum(c["charged"] for c in run.budget_metadata["calls"])
                        > (run.budget_metadata["limits"]["investigation_token_budget"])
                    ):
                        raise LiveLimitError("INVESTIGATION_TOKEN_BUDGET")
                return result
        raise LiveLimitError("INVESTIGATION_RETRIES_EXHAUSTED")
