"""Deterministic sentence-level aspect polarity and review-level consensus."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
import unicodedata

import yaml

LEXICON_PATH = Path(__file__).resolve().parents[1] / "lexicons" / "aspects.yaml"
TOKEN = re.compile(r"[\w]+(?:'[\w]+)?|[^\w\s]", re.UNICODE)
NEGATORS = {"not", "no", "never", "without", "zero", "doesn't", "don't", "isn't",
            "wasn't", "didn't", "isnt", "doesnt", "didnt", "dont", "aren't", "cant", "can't"}
BOUNDARY = {",", ";", ":", ".", "!", "?", "but", "yet", "however", "although", "and", "or"}


def _tokens(s):
    text = unicodedata.normalize("NFKC", s).casefold().replace("’", "'").replace("‘", "'")
    return TOKEN.findall(re.sub(r"[-‐‑–—]", " ", text))


@lru_cache(maxsize=1)
def _nlp():
    from spacy.lang.en import English
    nlp = English()
    nlp.add_pipe("sentencizer")
    return nlp


def sentences(body):
    nlp = _nlp()
    for line in body.splitlines():
        if line.strip():
            yield from (s.text.strip() for s in nlp(line).sents if s.text.strip())


@lru_cache(maxsize=1)
def lexicon():
    return yaml.safe_load(LEXICON_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _rules():
    by_first = {}
    for aspect, groups in lexicon().items():
        for polarity in ("pos", "neg", "neutral"):
            for phrase in groups.get(polarity, []):
                words = tuple(_tokens(phrase))
                by_first.setdefault(words[0], []).append((aspect, words, polarity))
    return by_first


def merge_polarities(labels):
    directional = set(labels) - {"neutral"}
    if "mixed" in directional or len(directional) > 1:
        return "mixed"
    return next(iter(directional), "neutral")


def _negated(words, start):
    for i in range(start - 1, max(-1, start - 4), -1):
        word = words[i]
        if word in BOUNDARY:
            break
        if word in NEGATORS:
            # “not only hydrating” is an intensifier, not a negation.
            if words[i:i+2] != ["not", "only"]:
                return True
    return False


def tag_sentence(sentence, rating=None):
    words = _tokens(sentence)
    matches = {}
    for i, token in enumerate(words):
        for aspect, phrase, polarity in _rules().get(token, []):
            if tuple(words[i:i + len(phrase)]) == phrase:
                matches.setdefault(aspect, []).append((i, i + len(phrase), polarity))
    result = {}
    for aspect, spans in matches.items():
        # A multiword exception occupies its whole span. Disjoint phrases still
        # contribute, so opposing experiences in a sentence remain mixed.
        occupied = set()
        labels = []
        for start, end, polarity in sorted(spans, key=lambda x: (x[2] == "neutral", x[0]-x[1], x[2] != "pos", x[0])):
            positions = set(range(start, end))
            if positions & occupied:
                continue
            occupied.update(positions)
            if polarity != "neutral" and _negated(words, start):
                polarity = "neg" if polarity == "pos" else "pos"
            labels.append(polarity)
        polarity = merge_polarities(labels)
        if polarity == "neutral" and isinstance(rating, (int, float)):
            polarity = "pos" if rating >= 4 else "neg" if rating <= 2 else "neutral"
        result[aspect] = polarity
    return result
