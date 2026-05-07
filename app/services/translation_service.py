import copy
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.core.llm import call_llm

logger = logging.getLogger(__name__)

# Strings matching these patterns are never sent to LLM
_DATE_RE = re.compile(r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$')
_CASE_NUM_RE = re.compile(
    # Short abbreviation prefixes that always indicate a case reference
    r'\b(S\.B\.|W\.P\.|WP|CWP|O\.A\.|M\.A\.)\b'
    # Full terms only when followed by "No." and a digit — i.e. an actual case number
    r'|\b(Civil Writ Petition|Criminal Appeal|SLP|Civil Suit)\s+No\.?\s*\d',
    re.IGNORECASE,
)
# Strings that are purely alphanumeric codes / short IDs
_CODE_RE = re.compile(r'^[A-Z0-9\s./(),-]{1,40}$')

# Mostly-ASCII heuristic: if >60% of non-space chars are ASCII letters, flag as untranslated
_ASCII_LETTER_RE = re.compile(r'[a-zA-Z]')
_NON_SPACE_RE = re.compile(r'\S')

BATCH_TRANSLATE_PROMPT = """\
You are a legal translation API for Indian court documents.
Translate every value in the JSON object below to {target_lang}.

RULES (mandatory):
1. Return ONLY valid JSON — same keys, translated values.
2. Translate institution names, court names, government department names, role titles, legal terms, and descriptive text.
3. Keep personal human names unchanged (names of people).
4. Keep values that are purely numeric codes, reference numbers, or dates unchanged.
5. Every value MUST appear in the output — never omit a key.
6. Do not add, remove, or rename any key.
7. Each value must be entirely in {target_lang} — never mix languages within a single value.
8. If a value was already fully in {target_lang}, return it unchanged.

JSON to translate:
{batch_json}

Return translated JSON now:"""

MAX_BATCH_CHARS = 2000


def _is_non_translatable(value: str) -> bool:
    """Return True if value should be passed through without translation."""
    v = value.strip()
    if not v:
        return True
    if _DATE_RE.match(v):
        return True
    # Only exclude case references if the string IS mostly a case number (short)
    # Longer strings may contain a case number embedded in translatable prose
    if _CASE_NUM_RE.search(v) and len(v) <= 60:
        return True
    # Very short pure-code strings (e.g. "IPC 420", "2015")
    if _CODE_RE.match(v) and len(v) <= 25:
        return True
    return False


def _is_likely_untranslated(original: str, translated: str) -> bool:
    """Heuristic: translated value still looks like English."""
    if not translated or not original:
        return False
    non_space = _NON_SPACE_RE.findall(translated)
    if not non_space:
        return False
    ascii_letters = _ASCII_LETTER_RE.findall(translated)
    ratio = len(ascii_letters) / len(non_space)
    # If >55% ASCII letters and string is non-trivial, likely untranslated
    return ratio > 0.55 and len(translated) > 15


# ── JSON walker ──────────────────────────────────────────────────────────────

def _collect_strings(obj: Any, path: str = "") -> List[Tuple[str, str]]:
    """
    Recursively walk obj and return [(path, value)] for every non-empty
    string that is translatable.
    """
    results = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
            results.extend(_collect_strings(v, p))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            results.extend(_collect_strings(item, f"{path}[{i}]"))
    elif isinstance(obj, str) and obj.strip() and not _is_non_translatable(obj):
        results.append((path, obj))
    return results


def _parse_path(path: str) -> List[Any]:
    """Convert 'a.b[0].c' → ['a', 'b', 0, 'c']"""
    tokens: List[Any] = []
    for segment in path.split("."):
        # Handle trailing [n] index, e.g. "citations[0]"
        match = re.match(r'^(\w+)\[(\d+)\]$', segment)
        if match:
            tokens.append(match.group(1))
            tokens.append(int(match.group(2)))
        elif segment.startswith("[") and segment.endswith("]"):
            tokens.append(int(segment[1:-1]))
        elif segment:
            tokens.append(segment)
    return tokens


def _set_at_path(obj: Any, tokens: List[Any], value: str) -> None:
    """Mutate obj in-place, setting value at location described by tokens."""
    for token in tokens[:-1]:
        obj = obj[token]
    obj[tokens[-1]] = value


# ── Translation batching ─────────────────────────────────────────────────────

def _translate_batch(id_to_value: Dict[str, str], target_lang: str) -> Dict[str, str]:
    """
    Send {id: value} flat dict to LLM for translation.
    Returns {id: translated_value}. Falls back to original per-key on failure.
    """
    batch_json = json.dumps(id_to_value, ensure_ascii=False)
    token_budget = min(max(4096, len(batch_json) * 3), 16384)
    prompt = BATCH_TRANSLATE_PROMPT.format(target_lang=target_lang, batch_json=batch_json)

    for attempt in range(2):
        result = call_llm(prompt, max_tokens=token_budget)

        if result.get("error") == "invalid_response":
            logger.warning(f"[translate] batch LLM error attempt {attempt + 1}")
            continue

        # Verify all keys returned
        missing = set(id_to_value) - set(result)
        if missing:
            logger.warning(f"[translate] batch attempt {attempt + 1}: missing ids {missing}")
            continue

        # Detect untranslated values and warn
        untranslated = [
            k for k, v in result.items()
            if _is_likely_untranslated(id_to_value[k], str(v))
        ]
        if untranslated:
            logger.warning(f"[translate] likely untranslated values: {[id_to_value[k] for k in untranslated]}")

        return {k: str(result[k]) for k in id_to_value}

    # Both attempts failed — return originals
    logger.error("[translate] batch failed after 2 attempts, returning originals")
    return id_to_value


def _chunk_strings(strings: List[Tuple[str, str]]) -> List[List[Tuple[str, str]]]:
    """Split string list into batches that fit within MAX_BATCH_CHARS."""
    batches, current, current_len = [], [], 0
    for path, value in strings:
        entry_len = len(json.dumps({path: value}))
        if current and current_len + entry_len > MAX_BATCH_CHARS:
            batches.append(current)
            current, current_len = [], 0
        current.append((path, value))
        current_len += entry_len
    if current:
        batches.append(current)
    return batches


# ── Public API ────────────────────────────────────────────────────────────────

def translate_output(output: Dict[str, Any], target_lang: str) -> Tuple[Dict[str, Any], List[str]]:
    """
    Translate all string values in output to target_lang.

    Returns (translated_dict, warnings) where warnings is a list of field paths
    that appeared to remain untranslated after LLM processing.

    Strategy:
    1. Walk JSON, collect translatable string leaves.
    2. Batch-send flat {id: value} dicts to LLM.
    3. Reassemble translated values back into cloned structure.
    """
    strings = _collect_strings(output)
    if not strings:
        return output, []

    result = copy.deepcopy(output)
    batches = _chunk_strings(strings)
    all_warnings: List[str] = []

    for batch in batches:
        id_to_value = {f"t{i}": value for i, (_, value) in enumerate(batch)}
        translated = _translate_batch(id_to_value, target_lang)

        for i, (path, original) in enumerate(batch):
            translated_value = translated.get(f"t{i}", original)
            if _is_likely_untranslated(original, translated_value):
                all_warnings.append(path)
            try:
                tokens = _parse_path(path)
                _set_at_path(result, tokens, translated_value)
            except (KeyError, IndexError, TypeError) as e:
                logger.error(f"[translate] failed to set path {path}: {e}")

    return result, all_warnings
