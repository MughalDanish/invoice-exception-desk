"""Deterministic provenance/fact checks; semantic entailment still needs review."""

import re
from decimal import Decimal, InvalidOperation

from app.modules.investigation.live_schemas import LiveDraft
from app.modules.investigation.routing import mandatory_plan


def _pointer(data, path):
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("Invalid JSON pointer")
    current = data
    for token in path[1:].split("/"):
        if re.search(r"~(?![01])", token):
            raise ValueError("Invalid JSON pointer escape")
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            current = current[token]
        elif isinstance(current, list | tuple) and re.fullmatch(r"0|[1-9][0-9]*", token):
            current = current[int(token)]
        else:
            raise KeyError(path)
    return current


def available_paths(data, limit=64):
    """Bounded RFC 6901 leaf catalogue; no financial values in repair guidance."""
    paths = []

    def visit(value, path):
        if len(paths) >= limit:
            return
        if isinstance(value, dict):
            for key, child in value.items():
                escaped = str(key).replace("~", "~0").replace("/", "~1")
                visit(child, path + "/" + escaped)
        elif isinstance(value, list | tuple):
            for index, child in enumerate(value):
                visit(child, path + "/" + str(index))
        elif path and len(path) <= 250:
            paths.append(path)

    visit(data, "")
    return paths


def normalize_references(draft, delivered):
    """Strip one envelope prefix only when the literal pointer does not exist.

    Never change an evidence ID, value, currency or an already resolving path.
    In particular, two resolving paths cannot trigger a guessed replacement.
    All normalized assertions still pass the complete deterministic policy gate.
    """
    manifest = evidence_manifest(delivered)
    findings, changes = [], 0
    for finding in draft.findings:
        assertions = []
        for assertion in finding.assertions:
            corrected = assertion
            data = manifest.get(assertion.evidence_id)
            if data is not None and assertion.field_path.startswith("/data/"):
                try:
                    _pointer(data, assertion.field_path)
                except (KeyError, IndexError, TypeError, ValueError):
                    path = assertion.field_path[5:]
                    try:
                        _pointer(data, path)
                    except (KeyError, IndexError, TypeError, ValueError):
                        pass
                    else:
                        corrected = assertion.model_copy(update={"field_path": path})
                        changes += 1
            assertions.append(corrected)
        findings.append(finding.model_copy(update={"assertions": tuple(assertions)}))
    return draft.model_copy(update={"findings": tuple(findings)}), changes


def reference_feedback(draft, delivered):
    """Private bounded model feedback, never operational telemetry or invoice values."""
    manifest = evidence_manifest(delivered)
    issues = []
    for finding_index, finding in enumerate(draft.findings):
        relevant = []
        for identifier in finding.evidence_ids:
            data = manifest.get(identifier, {})
            for path in ("/policy_found", "/policy", "/has_sources"):
                try:
                    value = _pointer(data, path)
                except (KeyError, IndexError, TypeError, ValueError):
                    continue
                if value is None or isinstance(value, bool):
                    relevant.append({"evidence_id": identifier, "field_path": path, "value": value})
        if finding.status == "SUPPORTED" and not finding.assertions:
            issues.append(
                {
                    "finding_index": finding_index,
                    "reason": "SUPPORTED_ASSERTIONS_MISSING",
                    "relevant_evidence": relevant,
                    "instruction": "Cite claim-relevant evidence, or mark INSUFFICIENT.",
                }
            )
        for assertion in finding.assertions:
            reason = None
            if assertion.evidence_id not in finding.evidence_ids:
                reason = "ASSERTION_REFERENCE_MISSING"
            elif assertion.evidence_id not in manifest:
                reason = "EVIDENCE_NOT_DELIVERED"
            else:
                try:
                    actual = _pointer(manifest[assertion.evidence_id], assertion.field_path)
                    if isinstance(actual, dict | list | tuple):
                        reason = "ASSERTION_EXPECTS_SCALAR_LEAF"
                    elif type(actual) is not type(assertion.value) or actual != assertion.value:
                        reason = "ASSERTION_VALUE_MISMATCH"
                except (KeyError, IndexError, TypeError, ValueError):
                    reason = "ASSERTION_PATH_INVALID"
            if reason:
                issues.append(
                    {
                        "finding_index": finding_index,
                        "relevant_evidence": relevant,
                        "evidence_id": assertion.evidence_id,
                        "rejected_path": assertion.field_path,
                        "reason": reason,
                        "valid_available_paths": available_paths(manifest[assertion.evidence_id], 8)
                        if assertion.evidence_id in manifest
                        else [],
                        "valid_evidence_ids": list(manifest)[:8]
                        if assertion.evidence_id not in manifest
                        else [],
                    }
                )
            if len(issues) >= 6:
                return issues
    return issues


def _sources(value):
    if isinstance(value, dict):
        if "source_id" in value and "version" in value:
            yield value
        for child in value.values():
            yield from _sources(child)
    elif isinstance(value, list | tuple):
        for child in value:
            yield from _sources(child)


def evidence_manifest(delivered):
    """Only actually returned evidence IDs and source IDs become admissible."""
    manifest = {}
    for result in delivered:
        manifest[result.evidence_id] = result.data
        for source in _sources(result.data):
            digest = source.get("content_sha256")
            if digest:
                identifier = f"source:{source['source_id']}:v{source['version']}:{digest}"
                manifest[identifier] = source
    return manifest


def validate_live_draft(snapshot, draft, delivered):
    """Return safe codes, never values. Code rejection cannot be overruled by LLM.

    JSON Pointer equality validates recorded claims, not authenticity of documents
    or arbitrary prose. No inferred financial arithmetic is accepted here.
    """
    draft = LiveDraft.model_validate(draft)
    errors = set()
    mandatory = {name for task in mandatory_plan(snapshot).tasks for name in task.tools}
    used = {r.name for r in delivered}
    if not mandatory <= used:
        errors.add("MANDATORY_TOOLS_MISSING")
    manifest = evidence_manifest(delivered)
    expected_sources = {}
    for source in snapshot.documents.items if snapshot.documents else ():
        expected_sources[(str(source.source_id), source.version)] = (
            source.content_sha256,
            source.text,
        )
    for source in snapshot.retrieval.hits if snapshot.retrieval else ():
        expected_sources[(str(source.source_id), source.version)] = (
            source.content_sha256,
            source.excerpt,
        )
    for result in delivered:
        for source in _sources(result.data):
            expected = expected_sources.get((str(source["source_id"]), source["version"]))
            excerpt = source.get("excerpt", source.get("text"))
            if expected is None or expected != (source.get("content_sha256"), excerpt):
                errors.add("SOURCE_INTEGRITY_INVALID")
            if source.get("invoice_id") not in (None, str(snapshot.invoice_id)):
                errors.add("SOURCE_SCOPE_INVALID")
    for finding in draft.findings:
        if len(set(finding.evidence_ids)) != len(finding.evidence_ids):
            errors.add("DUPLICATE_REFERENCE")
        if not set(finding.evidence_ids) <= set(manifest):
            errors.add("EVIDENCE_NOT_DELIVERED")
        if finding.status == "SUPPORTED" and not finding.assertions:
            errors.add("SUPPORTED_ASSERTIONS_MISSING")
        for assertion in finding.assertions:
            if assertion.evidence_id not in finding.evidence_ids:
                errors.add("ASSERTION_REFERENCE_MISSING")
                continue
            try:
                data = manifest[assertion.evidence_id]
                actual = _pointer(data, assertion.field_path)
            except (KeyError, IndexError, TypeError, ValueError):
                errors.add("ASSERTION_PATH_INVALID")
                continue
            # bool/int equality must not silently validate a numeric assertion.
            if type(actual) is not type(assertion.value) or actual != assertion.value:
                errors.add("ASSERTION_VALUE_MISMATCH")
            monetary_field = assertion.field_path.rsplit("/", 1)[-1] in {
                "amount",
                "total",
                "subtotal",
                "tax",
                "tax_amount",
                "unit_price",
                "expected_amount",
                "observed_amount",
                "amount_limit",
            }
            if monetary_field and actual is not None and assertion.currency is None:
                errors.add("ASSERTION_CURRENCY_MISSING")
            if assertion.currency is not None:
                parent_path = assertion.field_path.rsplit("/", 1)[0]
                parent = _pointer(data, parent_path) if parent_path else data
                currency = parent.get("currency") if isinstance(parent, dict) else None
                if currency is None and isinstance(data, dict):
                    currency = data.get("currency")
                if currency != assertion.currency:
                    errors.add("ASSERTION_CURRENCY_MISMATCH")
                try:
                    if (
                        not isinstance(assertion.value, str)
                        or not Decimal(assertion.value).is_finite()
                    ):
                        errors.add("ASSERTION_DECIMAL_INVALID")
                except InvalidOperation:
                    errors.add("ASSERTION_DECIMAL_INVALID")
        if finding.status == "HYPOTHESIS" and not draft.uncertainties:
            errors.add("HYPOTHESIS_UNCERTAINTY_MISSING")
    # Prose is qualitative; exact financial values are rendered exclusively from
    # validated assertions. This is an output-format restriction, not a truth test
    # or an attempt to detect arbitrary numeric hallucinations using regex.
    prose = [
        draft.summary,
        draft.resolution_rationale,
        *draft.uncertainties,
        *draft.limitations,
        *(f.claim for f in draft.findings),
    ]
    if any(re.search(r"\d", value) for value in prose):
        errors.add("NUMERIC_PROSE_FORBIDDEN")
    unsafe = re.compile(
        r"\b(?:I|we|system|agent)\s+(?:have\s+)?(?:approved|authorized|posted|paid)\b", re.I
    )
    if any(unsafe.search(value) for value in prose):
        errors.add("UNSAFE_AUTHORITY_CLAIM")
    return tuple(sorted(errors))


def render_assertion(assertion):
    """Stable exact financial presentation; no binary-float conversion."""
    value = "Not recorded" if assertion.value is None else str(assertion.value)
    return f"{assertion.field_path}: {value}" + (
        f" {assertion.currency}" if assertion.currency else ""
    )
