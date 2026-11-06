"""The agent: the LLM reads the question, picks a tool and writes the answer.

Numbers never come from the LLM. They come from the tools, and the code builds the product
list, decides whether the user must clarify something and checks the numbers in the answer.
"""

import json
import re
import time
from dataclasses import dataclass, field

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.numbers import unverified_numbers
from app.products import complete, focus_from, roles_from
from app.tools import TOOLS

SYSTEM_PROMPT = """You are the technical assistant for Series 76 electric actuators, used by plant engineers to look up
data and choose models. Answer in the language the user writes in.

Numbers
- State a technical value only if a tool returned it in this turn. Never answer from memory or from earlier
  messages. For a follow-up question, call the tool again.
- Earlier answers end with "[Part numbers consulted: ...]". When the user refers to a model from earlier,
  call get_actuator_specs with that exact part number.
- Pass torque to the tools in the unit the user stated. Never convert units yourself.
- If the user gives a torque without a unit, ask for the unit before searching.

How to answer
- Be brief. The app shows every value of each model in a table, so mention only what was asked and what
  matters to decide.
- Always write full part numbers, such as 762A00-11300000/A.
- Several models match a part number or alias: list them briefly and ask which voltage or service is meant.
- A part number is not in the tables: say so plainly and offer the suggested ones as a question. Never assume.
- A model is listed as N/A: say the table gives no values for it, and mention the alternatives.
- No model meets every requirement: say so first. Then present the closest models and explain each
  difference.
- A model qualifies only under some service or frequency: say under which.
- A rating with service "unspecified" comes from the 3-phase table, which does not say whether it applies to
  On/Off or Modulating. Say so whenever you present one, for example: "Note: the table does not say whether
  this value applies to Modulating."
- Repeat any note a tool includes, such as sizes 6 and 7 not being CSA certified.
- A follow-up with no model mentioned earlier: ask for the part number.
- Questions unrelated to Series 76 actuators: do not answer them; say politely that you can only help with
  Series 76 actuators.
- Never mention tools, functions, JSON or other internal details, and never write a "[Part numbers consulted]"
  line: the system adds it.

Context
- Weatherproof enclosures are for general industrial use. Explosionproof enclosures are for hazardous areas
  with flammable gases or dust.
- On/Off actuators move fully open or fully closed. Modulating actuators can stop at any point of their 90 degree
  turn, for precise flow control.
- Duty cycle: share of time the actuator can run without overheating. Operating speed: seconds for a 90 degree
  turn. FLA: current at maximum rated load. LRA: current at startup, with the rotor locked."""

CONSULTED_PREFIX = "[Part numbers consulted: "
# Models imitate the marker they see in earlier answers. It is internal, so code removes it.
CONSULTED_LINE = re.compile(r"\s*\[Part numbers consulted:[^\]]*\]")
EMPTY_ANSWER = "I could not finish the answer. Please ask again."
MAX_CONSULTED = 8
CLARIFICATION_STATUSES = {"ambiguous", "not_found", "needs_requirements", "invalid"}


@dataclass
class TurnResult:
    answer: str
    products: list[dict]
    needs_clarification: bool
    focus: dict = field(default_factory=dict)
    debug: dict = field(default_factory=dict)


def build_chat_model() -> BaseChatModel:
    options = {"temperature": settings.llm_temperature} if settings.llm_temperature is not None else {}
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout_sec,
        max_retries=1,
        default_headers={"X-Title": "Series 76 Technical Assistant"},
        **options,
    )


def history_messages(history: list[dict]) -> list[BaseMessage]:
    """Earlier turns as text, plus the part numbers each answer looked up. Never their old tool data."""
    messages: list[BaseMessage] = []
    for turn in history:
        if turn["role"] == "user":
            messages.append(HumanMessage(turn["content"]))
        else:
            text = turn["content"]
            if turn["part_numbers"]:
                text += f"\n{CONSULTED_PREFIX}{', '.join(turn['part_numbers'])}]"
            messages.append(AIMessage(text))
    return messages


def _parse(content: str) -> object:
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return content


def _text(message: AIMessage) -> str:
    if isinstance(message.content, str):
        return message.content
    return "".join(block.get("text", "") for block in message.content if isinstance(block, dict))


def run_turn(query: str, history: list[dict], model: BaseChatModel | None = None) -> TurnResult:
    started = time.monotonic()
    agent = create_agent(model or build_chat_model(), TOOLS, system_prompt=SYSTEM_PROMPT)
    previous = history_messages(history)
    state = agent.invoke(
        {"messages": [*previous, HumanMessage(query)]},
        config={"recursion_limit": settings.agent_max_steps},
    )
    new_messages = state["messages"][len(previous) + 1:]

    outputs = {m.tool_call_id: _parse(m.content) for m in new_messages if isinstance(m, ToolMessage)}
    tool_calls = [
        {"name": call["name"], "args": call["args"], "output": outputs.get(call["id"])}
        for m in new_messages if isinstance(m, AIMessage)
        for call in m.tool_calls
    ]
    final = next((m for m in reversed(new_messages) if isinstance(m, AIMessage) and not m.tool_calls), None)
    raw_answer = _text(final).strip() if final else ""
    answer = CONSULTED_LINE.sub("", raw_answer).strip() or EMPTY_ANSWER

    found: list[dict] = []
    for call in tool_calls:
        for product in roles_from(call["output"]):
            if all(p["part_number"] != product["part_number"] for p in found):
                found.append(product)
    # Only models the tools returned in full: those are what a follow-up question can refer to.
    consulted = [p["part_number"] for p in found if "electrical_ratings" in p][:MAX_CONSULTED]
    products = complete(found)

    # Only the last call to each tool counts: if the model corrected an argument in the same turn,
    # the first failed call no longer needs anything from the user.
    last_calls = {call["name"]: call for call in tool_calls if call["output"] is not None}
    needs_clarification = any(
        isinstance(call["output"], str) or call["output"].get("status") in CLARIFICATION_STATUSES
        for call in last_calls.values()
    )

    usage = [m.usage_metadata for m in new_messages if isinstance(m, AIMessage) and m.usage_metadata]
    debug = {
        "model": settings.llm_model,
        "tool_calls": tool_calls,
        # "length" means the answer was cut by LLM_MAX_TOKENS, which reasoning models spend quickly.
        "finish_reason": final.response_metadata.get("finish_reason") if final else None,
        "empty_answer": answer == EMPTY_ANSWER,
        "marker_removed": CONSULTED_PREFIX in raw_answer,
        "unverified_numbers": unverified_numbers(
            answer, [call["output"] for call in tool_calls] + [query, SYSTEM_PROMPT]
        ),
        "part_numbers_consulted": consulted,
        "input_tokens": sum(u.get("input_tokens", 0) for u in usage),
        "output_tokens": sum(u.get("output_tokens", 0) for u in usage),
        "latency_ms": round((time.monotonic() - started) * 1000),
    }
    return TurnResult(
        answer=answer,
        products=products,
        needs_clarification=needs_clarification,
        focus=focus_from(tool_calls),
        debug=debug,
    )
