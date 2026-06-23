from __future__ import annotations

import re

from app.profiles.regex_rules import RegexRule


def transform_text(text: str, rules: list[RegexRule], target: str) -> str:
    result = text or ""
    for rule in rules:
        if not rule.enabled or not applies_to_target(rule.target, target):
            continue
        try:
            result = re.sub(rule.pattern, rule.replacement, result)
        except re.error:
            continue
    return result


def applies_to_target(rule_target: str, requested_target: str) -> bool:
    normalized_rule = (rule_target or "").strip().lower()
    normalized_requested = (requested_target or "").strip().lower()
    return normalized_rule in {"both", normalized_requested}
