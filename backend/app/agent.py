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

from app import catalog, language
from app.config import settings
from app.numbers import part_numbers_in, unverified_numbers, unverified_part_numbers
from app.products import complete, focus_from, roles_from
from app.tools import TOOLS

SYSTEM_PROMPT = """You are the technical assistant for Series 76 electric actuators, used by plant engineers to look up
data and choose models. Answer in the language the user writes in.

Numbers
- State a technical value only if a tool returned it in this turn. Never answer from memory or from earlier
  messages. For a follow-up question, call the tool again.
- Earlier answers end with "[Part numbers consulted: ...]". When the user refers to a model from earlier,
  call get_actuator_specs with that exact part number.
- If the user says it, its, that one or similar and your previous answer listed several models without the user
  picking one: when the answer is the same for all of them, give it for all of them; otherwise ask which one they
  mean and list the part numbers. Never assume the first one.
- Pass torque to the tools in the unit the user stated. Never convert units yourself.
- If the user wants a model's torque in ft-lbs or kgf-m, call get_actuator_specs with convert_torque true, give
  torque_ft_lbs_converted or torque_kgf_m_converted and say it is converted from the table. In search results, give
  torque in the table's units without commenting on it.
- Never do arithmetic: no sums, differences, ratios or percentages, not even simple ones. Give the values the
  tools returned side by side and let the user compare them. If asked to calculate something, give those values
  and say you cannot calculate it.
- If the user gives a torque without a unit, ask for the unit before searching.

How to answer
- Be brief. The app shows every value of each model in its own table, so mention only what was asked and what
  matters to decide.
- Never write tables. Use short sentences or a short bullet list instead.
- Always write full part numbers, such as 762A00-11300000/A.
- Asked for the largest or most powerful model: call recommend_actuators with sort_by highest_torque. The first
  result is the largest.
- A torque the user needs, such as "I need 500 Nm", is a minimum: min_torque only. Use max_torque only if the user
  says between, at most, no more than or exactly; "exactly" gives the same value in both. "More than" a value also
  sets min_torque_exclusive. Models without a certification use exclude_certification, and a size uses size.
- Asked how many models there are: give total_models, models_with_data and models_without_data from
  list_available_options, models_by_enclosure for an enclosure, or the models field of a group. Code counted them;
  do not add anything up.
- A total from a search counts only models with data. If without_data_not_checked is above zero and you say how
  many models exist, say they are the ones with data and add "in addition, N other models are listed without
  values". Those N are not among the models you did not show.
- Search results come smallest first, so the first one is the smallest that qualifies even if more exist. With
  shown lower than total, say how many you show out of the total.
- Every model under matches already meets every requirement, in the unit the user stated: code checked it. Say so,
  and never say you cannot tell whether it meets them.
- In a result with closest_condition, that condition is only the one that came closest. It does not mean the model
  is limited to that service or frequency.
- Each model lookup gives operating_limits, the voltage and frequency ranges the datasheet allows, and
  datasheet_notes. Mention them only if the user asks about tolerances or the notes: then say the range and whether
  the value is inside it.
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
- If you cannot do something, say what you can do and what information you need. Never explain it by talking about
  your tools or your technical limitations. If the user asks about them directly, say you cannot share internal
  details.

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
# Two or more lines like "| 763B00-11300000/A | 500 Nm |": a Markdown table, which the app shows as raw text
# and which repeats the app's own table. Measured, not removed: removing it could drop the only copy of a value.
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$", re.MULTILINE)
# Measured, not removed: a user can ask about these on purpose, and then refusing is the right answer.
INTERNAL_WORDS = re.compile(
    r"\b(?:tools?|functions?|json|schema|herramientas?|system prompt|" + "|".join(tool.name for tool in TOOLS) + r")\b",
    re.IGNORECASE,
)
EMPTY_ANSWER = "I could not finish the answer. Please ask again."
MAX_CONSULTED = 8
CLARIFICATION_STATUSES = {"ambiguous", "not_found", "needs_requirements", "invalid"}
OMITTED_TURNS_NOTE = (
    "\n\nThis conversation has older turns that you cannot see. If the user refers to something you cannot see, "
    "such as the first model they asked about, say so and ask for the part number. Never guess it from the turns "
    "you can see."
)
LANGUAGE_NOTE = "\n\nThe user's latest message is in {language}. Write your whole answer in {language}."


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


def has_markdown_table(text: str) -> bool:
    return len(TABLE_ROW.findall(text)) >= 2


def instructions(query: str, omitted_turns: int = 0) -> str:
    """The fixed instructions, plus what only this turn can say."""
    text = SYSTEM_PROMPT
    if omitted_turns:
        text += OMITTED_TURNS_NOTE
    detected = language.detect(query)
    if detected:
        text += LANGUAGE_NOTE.format(language=detected)
    return text


def run_turn(query: str, history: list[dict], model: BaseChatModel | None = None, omitted_turns: int = 0) -> TurnResult:
    started = time.monotonic()
    agent = create_agent(model or build_chat_model(), TOOLS, system_prompt=instructions(query, omitted_turns))
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
    ) or (not tool_calls and "?" in answer)  # With no tool result, the text is the only signal there is.

    usage = [m.usage_metadata for m in new_messages if isinstance(m, AIMessage) and m.usage_metadata]
    debug = {
        "model": settings.llm_model,
        "tool_calls": tool_calls,
        # "length" means the answer was cut by LLM_MAX_TOKENS, which reasoning models spend quickly.
        "finish_reason": final.response_metadata.get("finish_reason") if final else None,
        "empty_answer": answer == EMPTY_ANSWER,
        "marker_removed": CONSULTED_PREFIX in raw_answer,
        "markdown_table": has_markdown_table(answer),
        "mentions_internals": bool(INTERNAL_WORDS.search(answer)),
        # Only when the answer has one, to skip the query otherwise.
        "unverified_part_numbers": unverified_part_numbers(
            answer, catalog.part_numbers(), " ".join([query, *(t["content"] for t in history if t["role"] == "user")])
        ) if part_numbers_in(answer) else [],
        "unverified_numbers": unverified_numbers(
            # The arguments hold requirements stated in earlier turns, such as the 60 of "at least 60 Nm".
            answer, [call["output"] for call in tool_calls] + [call["args"] for call in tool_calls] + [query, SYSTEM_PROMPT]
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
