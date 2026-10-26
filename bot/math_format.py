"""Convert common LaTeX into readable Telegram text."""

import re

_SUPERSCRIPT = str.maketrans("0123456789+-=()n", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ")
_SUBSCRIPT = str.maketrans("0123456789+-=()", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎")

_MATH_WORDS = {
    "times": "×",
    "cdot": "·",
    "div": "÷",
    "pm": "±",
    "mp": "∓",
    "approx": "≈",
    "leq": "≤",
    "le": "≤",
    "geq": "≥",
    "ge": "≥",
    "neq": "≠",
    "ne": "≠",
    "infty": "∞",
    "to": "→",
    "rightarrow": "→",
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "delta": "δ",
    "theta": "θ",
    "lambda": "λ",
    "mu": "μ",
    "pi": "π",
    "sigma": "σ",
    "omega": "ω",
    "sum": "Σ",
    "prod": "Π",
    "int": "∫",
    "partial": "∂",
}


def _script(value: str, table, marker: str) -> str:
    if value and all(ch in "0123456789+-=()n" for ch in value):
        return value.translate(table)
    return f"{marker}({value})"


def clean_math(text: str) -> str:
    """Replace common LaTeX commands with Unicode / plain readable text."""
    text = text.replace("$$", "").replace("$", "")
    text = re.sub(r"\\\[|\\\]|\\\(|\\\)", "", text)

    # Normalise wrappers before fractions so nested braces can collapse.
    text = re.sub(
        r"\\(?:text|mathrm|operatorname|mathbf|mathit)\{([^{}]*)\}",
        r"\1",
        text,
    )
    text = re.sub(
        r"\^\{([^{}]+)\}",
        lambda match: _script(match.group(1), _SUPERSCRIPT, "^"),
        text,
    )
    text = re.sub(
        r"_\{([^{}]+)\}",
        lambda match: _script(match.group(1), _SUBSCRIPT, "_"),
        text,
    )
    text = re.sub(r"\\sqrt\{([^{}]+)\}", r"√(\1)", text)

    for _ in range(6):
        new = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r"(\1)/(\2)", text)
        if new == text:
            break
        text = new

    for word, symbol in _MATH_WORDS.items():
        text = re.sub(rf"\\{word}\b", symbol, text)

    text = text.replace("\\,", "").replace("\\;", "").replace("\\!", "")
    text = re.sub(r"\\[a-zA-Z]+\*?", "", text)
    return text
