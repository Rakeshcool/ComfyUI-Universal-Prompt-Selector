"""Template-based formatting for the Prompt Combiner node.

Instead of blindly concatenating strings, the combiner renders a named
template with two placeholders:

    {system_prompt}  -> the system prompt text
    {user_prompt}    -> the user prompt text

Built-in templates cover the common shapes; users may also supply a fully
custom template (selected via the ``custom`` option). ``str.format`` is NOT
used on purpose - it chokes on literal braces in prompt text (e.g. JSON
examples inside prompts). Placeholders are replaced with plain ``str.replace``
so arbitrary content is always safe.
"""

from __future__ import annotations

from typing import Dict

SYSTEM_PLACEHOLDER = "{system_prompt}"
USER_PLACEHOLDER = "{user_prompt}"

TEMPLATE_NL2 = "plain_merge"  # system + "\n\n" + user
TEMPLATE_LABELED = "labeled"  # "System:\n...\n\nUser:\n..."
TEMPLATE_INSTRUCT = "instruct"  # "System prompt:\n...\n\nUser request:\n..."
TEMPLATE_XML = "xml"  # <system_prompt>...</system_prompt> style
TEMPLATE_CUSTOM = "custom"

TEMPLATES: Dict[str, str] = {
    TEMPLATE_NL2: "{system_prompt}\n\n{user_prompt}",
    TEMPLATE_LABELED: "System:\n{system_prompt}\n\nUser:\n{user_prompt}",
    TEMPLATE_INSTRUCT: (
        "System prompt:\n{system_prompt}\n\nUser request:\n{user_prompt}"
    ),
    TEMPLATE_XML: (
        "<system_prompt>\n{system_prompt}\n</system_prompt>\n\n"
        "<user_prompt>\n{user_prompt}\n</user_prompt>"
    ),
}

#: Shown in the combo; picking it makes the ``custom_template`` widget active.
TEMPLATE_CHOICES = [TEMPLATE_NL2, TEMPLATE_LABELED, TEMPLATE_INSTRUCT, TEMPLATE_XML, TEMPLATE_CUSTOM]


class FormatError(Exception):
    """Raised when a custom template cannot be rendered."""


def resolve_template(format_name: str, custom_template: str = "") -> str:
    """Return the template body for a named format.

    Raises FormatError if ``custom`` is selected with an empty template or
    the template is missing one of the placeholders.
    """
    name = (format_name or TEMPLATE_NL2).strip()
    if name == TEMPLATE_CUSTOM:
        body = (custom_template or "").strip()
        if not body:
            raise FormatError(
                "Template 'custom' selected but the custom_template input is empty."
            )
        if SYSTEM_PLACEHOLDER not in body and USER_PLACEHOLDER not in body:
            raise FormatError(
                "custom_template must contain at least one of "
                f"{SYSTEM_PLACEHOLDER} or {USER_PLACEHOLDER}."
            )
        return body
    return TEMPLATES.get(name, TEMPLATES[TEMPLATE_NL2])


def combine(
    system_prompt: str,
    user_prompt: str,
    format_name: str = TEMPLATE_NL2,
    custom_template: str = "",
    strip_whitespace: bool = True,
) -> str:
    """Render system+user prompts through the selected template.

    Args:
        system_prompt: The system prompt text (may come from the selector).
        user_prompt: The user prompt text.
        format_name: One of ``TEMPLATE_CHOICES`` (bad values fall back to
            ``plain_merge`` so old workflows never break).
        custom_template: Template body used when ``format_name == 'custom'``.
        strip_whitespace: Trim surrounding whitespace from both inputs before
            merging (recommended; keeps output tidy).
    Returns:
        The final combined prompt.
    """
    sys_text = system_prompt or ""
    usr_text = user_prompt or ""
    if strip_whitespace:
        sys_text = sys_text.strip()
        usr_text = usr_text.strip()

    body = resolve_template(format_name, custom_template)
    return body.replace(SYSTEM_PLACEHOLDER, sys_text).replace(USER_PLACEHOLDER, usr_text)
