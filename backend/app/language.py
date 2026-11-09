"""Tells the model which language to answer in, because instructions alone did not hold.

With a question carrying an injection attempt, half of the answers came back in another language.
A rule in the instructions fixed that but sent ordinary English questions to Spanish. Naming the
language of this particular message, from code, gave the right language in every run we measured.

Only English and Spanish are recognised. Anything else, or a message too short to tell ("In-lbs.",
a bare part number), gets no hint and the model follows the conversation.
"""

import re

SPANISH_SIGNS = re.compile(r"[¿¡ñ]")
SPANISH_WORDS = re.compile(
    r"\b(el|los|del|qué|cuál|cuáles|cuánto|cuántos|cuánta|necesito|busco|dame|muéstrame|quiero|tengo|hola|tiene|modelo|actuador|servicio)\b",
    re.IGNORECASE,
)
ENGLISH_WORDS = re.compile(
    r"\b(the|what|which|is|are|of|for|with|need|at|how|and|can|you|give|show|tell|find|does|my)\b",
    re.IGNORECASE,
)
MIN_WORDS = 2


def detect(text: str) -> str | None:
    """"English", "Spanish", or None when the message does not clearly say."""
    if SPANISH_SIGNS.search(text):
        return "Spanish"
    spanish, english = len(SPANISH_WORDS.findall(text)), len(ENGLISH_WORDS.findall(text))
    if spanish >= MIN_WORDS and english == 0:
        return "Spanish"
    if english >= MIN_WORDS and spanish == 0:
        return "English"
    return None
