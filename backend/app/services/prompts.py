"""Shared defaults and limits for the AI system prompt."""

DEFAULT_SYSTEM_PROMPT = (
    "You are Vidhya Bot, a highly intelligent educational AI assistant, "
    "developed independently by Vidhya Platform.\n"
    "Under no circumstances should you identify as DeepSeek, OpenAI, Qwen, "
    "or any other foundational LLM model.\n"
    "Answer the user's questions as accurately and concisely as possible.\n"
    "CRITICAL: Do NOT output any internal monologue, reasoning, "
    "'let me think' thoughts, or meta-commentary.\n"
    "CRITICAL: Do NOT cite sources, mention document names, or use phrases "
    "like 'According to the context'. Seamlessly incorporate the information "
    "as your own knowledge.\n"
    "Respond with the final concise answer directly. Never think out loud."
)

SYSTEM_PROMPT_MAX_CHARS = 8000
SYSTEM_PROMPT_MAX_WORDS = 1200


class SystemPromptError(ValueError):
    pass


def clean_system_prompt(value: str) -> str:
    """Validate an admin-supplied prompt and fall back to the default."""
    text = (value or "").strip()
    if not text:
        return DEFAULT_SYSTEM_PROMPT
    if len(text) > SYSTEM_PROMPT_MAX_CHARS:
        raise SystemPromptError(
            f"The system prompt is {len(text)} characters; the limit is "
            f"{SYSTEM_PROMPT_MAX_CHARS}."
        )
    words = len(text.split())
    if words > SYSTEM_PROMPT_MAX_WORDS:
        raise SystemPromptError(
            f"The system prompt has {words} words; the limit is "
            f"{SYSTEM_PROMPT_MAX_WORDS}."
        )
    return text


FORMATTING_RULES = (
    "\n\nFORMATTING: Do not use LaTeX or TeX commands "
    "(no $...$, \\(...\\), \\frac, or \\text). Write formulas in plain "
    "readable text with Unicode symbols such as × ÷ √ ² ³ ₀ ₁ ≤ ≥ ≈ ∞. "
    "Use Markdown bold for labels and avoid tables."
)
