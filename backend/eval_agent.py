"""Compare language models on the same questions, using the real OpenRouter key.

This spends budget, a few cents per model. Each check is decided by code from what the tools
returned, not by reading the answer by eye.

    uv run python eval_agent.py openai/gpt-5-mini anthropic/claude-haiku-5.5 qwen/qwen3.7-flash
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Callable

import httpx

from app.agent import TurnResult, build_chat_model, run_turn
from app.config import BACKEND_DIR, settings

RESULTS_PATH = BACKEND_DIR / "eval" / "results.json"


def statuses(result: TurnResult, tool: str | None = None) -> list[str]:
    return [
        call["output"].get("status") if isinstance(call["output"], dict) else "text"
        for call in result.debug["tool_calls"]
        if tool is None or call["name"] == tool
    ]


def first_product(result: TurnResult, role: str) -> str | None:
    return next((p["part_number"] for p in result.products if p["role"] == role), None)


def looked_up(result: TurnResult, part_number: str) -> bool:
    return any(
        call["name"] == "get_actuator_specs" and part_number in str(call["args"].get("identifier", ""))
        for call in result.debug["tool_calls"]
    )


@dataclass
class Case:
    name: str
    turns: list[str]
    check: Callable[[TurnResult], bool]
    expectation: str


CASES = [
    Case("lookup", ["What is the output torque of 762A00-11300000/A?"],
         lambda r: first_product(r, "specs") == "762A00-11300000/A" and "150" in r.answer,
         "looks up the model and states 150 Nm"),
    Case("follow_up", ["¿Cuánto torque da el 762A00-11300000/A en On/Off?", "¿Y cuánta potencia consume?"],
         lambda r: looked_up(r, "762A00-11300000/A") and "40" in r.answer,
         "looks the model up again and states 40 W"),
    Case("follow_up_alias", ["What torque does the 2A give at 110 V?", "And its full load current at 60 Hz?"],
         lambda r: looked_up(r, "762A00-11300000/A") and "2.3" in r.answer,
         "resolves the 2A at 110 V and states 2.3 A"),
    Case("ambiguous_alias", ["Tell me about the 1A"],
         lambda r: r.needs_clarification and "ambiguous" in statuses(r),
         "shows the 3 options or asks which one"),
    Case("mistyped", ["Specs for 761800-11300000/A"],
         lambda r: "not_found" in statuses(r) and "761B00-11300000/A" in r.answer,
         "says it does not exist and suggests 761B00-11300000/A"),
    Case("summary_example", ["Give me the data of 761A00-11380000/A"],
         lambda r: "not_found" in statuses(r) and not any(p["role"] == "specs" for p in r.products),
         "says it is not in the tables"),
    Case("na_model", ["What is the torque of 761A00-11330C00/A?"],
         lambda r: "no_data" in statuses(r),
         "says the table lists it as N/A"),
    Case("recommend", ["Recommend an On/Off weatherproof actuator at 110 V with at least 500 Nm"],
         lambda r: first_product(r, "match") == "763B00-11300000/A",
         "recommends 763B00-11300000/A first"),
    Case("impossible", ["I need an explosionproof, 3-phase actuator with at least 400 Nm"],
         lambda r: "no_matches" in statuses(r) and "763Y30" in r.answer,
         "says none qualifies and offers 763Y30"),
    Case("three_phase", ["Necesito un actuador modulating de 3 fases con al menos 400 Nm"],
         lambda r: first_product(r, "match") == "763B00-11330C00/A" and "odulat" in r.answer,
         "offers 763B00-11330C00/A with the 3-phase warning"),
    Case("missing_unit", ["I need an actuator with 500 of torque"],
         lambda r: not any(c["args"].get("torque_unit") for c in r.debug["tool_calls"]),
         "asks for the unit instead of assuming one"),
    Case("converted_unit", ["I need 70 ft-lb, On/Off, weatherproof, 110 V"],
         lambda r: first_product(r, "match") == "761B00-11300000/A",
         "passes ft-lb to the tool and gets 761B00-11300000/A"),
    Case("off_topic", ["What is the capital of France?"],
         lambda r: not r.debug["tool_calls"] and "Paris" not in r.answer,
         "redirects without calling tools or answering"),
    Case("follow_up_without_context", ["And how much power does it draw?"],
         lambda r: not r.products,
         "asks which model"),
]


def openrouter_usage() -> float:
    response = httpx.get(
        f"{settings.openrouter_base_url}/key",
        headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
        timeout=30,
    )
    response.raise_for_status()
    return float(response.json()["data"]["usage"])


def run_case(case: Case) -> dict:
    history: list[dict] = []
    result = None
    latency_ms = 0
    for query in case.turns:
        result = run_turn(query, history, build_chat_model())
        latency_ms += result.debug["latency_ms"]
        history += [
            {"role": "user", "content": query, "part_numbers": []},
            {"role": "assistant", "content": result.answer, "part_numbers": result.debug["part_numbers_consulted"]},
        ]
    return {
        "case": case.name,
        "expectation": case.expectation,
        # An empty or cut answer fails whatever the tools returned: the user would see nothing useful.
        "passed": case.check(result) and not result.debug["empty_answer"] and result.debug["finish_reason"] != "length",
        "finish_reason": result.debug["finish_reason"],
        "marker_removed": result.debug["marker_removed"],
        "markdown_table": result.debug["markdown_table"],
        "answer": result.answer,
        "tools": [{"name": c["name"], "args": c["args"]} for c in result.debug["tool_calls"]],
        "unverified_numbers": result.debug["unverified_numbers"],
        "latency_ms": latency_ms,
    }


def evaluate(model: str) -> dict:
    settings.llm_model = model
    spent_before = openrouter_usage()
    started = time.monotonic()
    cases = []
    for case in CASES:
        try:
            outcome = run_case(case)
        except Exception as error:  # A failing model is a result, not a reason to stop the comparison.
            outcome = {"case": case.name, "expectation": case.expectation, "passed": False, "error": repr(error)[:300]}
        cases.append(outcome)
        mark = "pass" if outcome["passed"] else "FAIL"
        print(f"  {mark}  {case.name}: {outcome.get('error') or outcome['answer'][:110]!r}")
    time.sleep(5)  # OpenRouter updates usage with a short delay.
    return {
        "model": model,
        "passed": sum(c["passed"] for c in cases),
        "total": len(cases),
        "unverified_numbers": sum(len(c.get("unverified_numbers", [])) for c in cases),
        "answers_cut": sum(c.get("finish_reason") == "length" for c in cases),
        "markers_removed": sum(bool(c.get("marker_removed")) for c in cases),
        "markdown_tables": sum(bool(c.get("markdown_table")) for c in cases),
        "cost_usd": round(openrouter_usage() - spent_before, 5),
        "seconds": round(time.monotonic() - started),
        # Per question, as the app would wait for it. Questions with two turns add both; failed ones are left out.
        "median_seconds": round(statistics.median([c["latency_ms"] for c in cases if "latency_ms" in c] or [0]) / 1000, 1),
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("models", nargs="+")
    parser.add_argument("--out", type=Path, default=RESULTS_PATH, help="Where to save the details.")
    args = parser.parse_args()
    if not settings.has_openrouter_key():
        print("Set OPENROUTER_API_KEY in .env to compare models.")
        return 2

    print(f"LLM_MAX_TOKENS={settings.llm_max_tokens}, LLM_TEMPERATURE={settings.llm_temperature}")
    results = []
    for model in args.models:
        print(f"\n{model}")
        results.append(evaluate(model))

    args.out.parent.mkdir(exist_ok=True)
    args.out.write_text(json.dumps(results, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\n{'model':32} passed  unverified  cut  markers  tables  cost USD  median s  total s")
    for r in results:
        print(
            f"{r['model']:32} {r['passed']:>2}/{r['total']}  {r['unverified_numbers']:>10}  {r['answers_cut']:>3}"
            f"  {r['markers_removed']:>7}  {r['markdown_tables']:>6}  {r['cost_usd']:>8}  {r['median_seconds']:>8}  {r['seconds']:>7}"
        )
    print(f"\nDetails -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
