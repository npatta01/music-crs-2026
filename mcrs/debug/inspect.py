"""Session and state inspection commands."""

from __future__ import annotations

import argparse

from . import runtime
from .artifacts import load_audit_index, load_prediction_index, trace_row, trace_turns
from .formatting import _print_block, _print_case, _print_json


def _cmd_session(args: argparse.Namespace) -> int:
    run = runtime._require_trace_run(args)
    session_id = runtime._resolve_session(run, args.session_id)
    turns = trace_turns(run.trace, session_id)
    audit = load_audit_index(run.audit)
    rows = [
        {
            "turn_number": turn,
            "latest_user_text": audit.get((session_id, turn), {}).get("latest_user_text", ""),
            "request_type": audit.get((session_id, turn), {}).get("request_type", ""),
        }
        for turn in turns
    ]
    if args.format == "json":
        _print_json({"run": run.name, "session_id": session_id, "turns": rows})
        return 0

    print(f"Run: {run.name}")
    print(f"Session: {session_id}")
    for row in rows:
        label = f"turn {row['turn_number']}"
        if row["request_type"]:
            label += f" | {row['request_type']}"
        if row["latest_user_text"]:
            label += f" | {row['latest_user_text']}"
        print(label)
    return 0

def _cmd_case(args: argparse.Namespace) -> int:
    run = runtime._require_trace_run(args)
    session_id = runtime._resolve_session(run, args.session_id)
    row = trace_row(run.trace, session_id, args.turn)
    key = (session_id, int(args.turn))
    audit_row = load_audit_index(run.audit).get(key, {})
    prediction_row = load_prediction_index(run.prediction).get(key, {})

    payload = {
        "run": run.name,
        "session_id": session_id,
        "turn_number": int(args.turn),
        "trace": row.get("trace") or {},
        "audit": audit_row,
        "prediction": prediction_row,
    }
    if args.format == "json":
        _print_json(payload)
        return 0

    _print_case(payload)
    return 0

def _cmd_state(args: argparse.Namespace) -> int:
    run = runtime._require_trace_run(args)
    session_id = runtime._resolve_session(run, args.session_id)
    row = trace_row(run.trace, session_id, args.turn)
    trace = row.get("trace") or {}
    payload = {
        "session_id": session_id,
        "turn_number": int(args.turn),
        "extracted_state": trace.get("extracted_state") or {},
        "compiled_state": trace.get("compiled_state") or {},
        "resolver": trace.get("resolver") or {},
        "routing_tags": trace.get("routing_tags") or {},
    }
    if args.format == "json":
        _print_json(payload)
        return 0

    print(f"Session: {session_id}")
    print(f"Turn: {args.turn}")
    _print_block("Extracted State", payload["extracted_state"])
    _print_block("Compiled State", payload["compiled_state"])
    _print_block("Resolver", payload["resolver"])
    _print_block("Routing Tags", payload["routing_tags"])
    return 0
