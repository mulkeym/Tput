from __future__ import annotations

from app.generators import generate_all


def render_prompt(template: str, generators: list[str]) -> str:
    """Replace {placeholder} tags in template with generated values.

    Only placeholders matching names in `generators` are replaced.
    Unknown placeholders are left as-is.
    """
    if not generators:
        return template

    values = generate_all(generators)
    result = template
    for key, val in values.items():
        result = result.replace("{" + key + "}", val)
    return result


def build_request_body(
    text: str,
    image_base64: str | None = None,
) -> dict:
    """Build a RAMPART-compatible evaluate request body."""
    if image_base64:
        content = [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": image_base64}},
        ]
    else:
        content = text

    return {
        "request": {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": content}
            ],
        }
    }
