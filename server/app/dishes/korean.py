# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Korean particles chosen from the word they follow. Pure functions, no dependencies.

A Hangul syllable has a final consonant (batchim) when (code - 0xAC00) % 28 != 0; ㄹ is final 8,
which matters for 으로/로 (밥으로, 물로). A word that does not end in a Hangul syllable (egg, B12)
is treated as having no final consonant for 이/가, 을/를, 은/는, 와/과 and as ending in a vowel
for 으로/로: the reader then sees 가/를/는/와/로, the common choice for Latin names read aloud.
"""

_FIRST, _LAST, _FINALS = 0xAC00, 0xD7A3, 28
_RIEUL = 8
_PAIRS = {"이": ("이", "가"), "을": ("을", "를"), "은": ("은", "는"), "과": ("과", "와")}


def _final(word: str) -> int | None:
    """Index of the final consonant of the last character (0 = none), None if not Hangul."""
    text = word.rstrip()
    if not text:
        return None
    code = ord(text[-1])
    if not _FIRST <= code <= _LAST:
        return None
    return (code - _FIRST) % _FINALS


def particle(word: str, kind: str) -> str:
    """The particle of ``kind`` ('이', '을', '은', '과' or '으로') that follows ``word``."""
    final = _final(word)
    if kind == "으로":
        return "으로" if final not in (None, 0, _RIEUL) else "로"
    with_final, without = _PAIRS[kind]
    return with_final if final else without


def attach(word: str, kind: str) -> str:
    """``word`` followed by its particle, e.g. attach('김치', '이') -> '김치가'."""
    return word + particle(word, kind)
