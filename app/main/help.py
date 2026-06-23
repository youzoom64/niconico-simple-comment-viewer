from __future__ import annotations

from app.main.entrypoints import Entrypoint


def format_entrypoint_report(
    default_entrypoint: str,
    active_entrypoints: dict[str, Entrypoint],
    future_entrypoints: dict[str, str],
) -> str:
    lines = [
        f"default: {default_entrypoint}",
        "active:",
    ]
    for name, entrypoint in active_entrypoints.items():
        lines.append(f"  - {name}: {entrypoint.description} ({entrypoint.runtime_layer})")
    lines.append("future:")
    for name, location in future_entrypoints.items():
        lines.append(f"  - {name}: {location}")
    return "\n".join(lines)
