"""Universal Prompt Selector nodes for ComfyUI (V3 node API).

Nodes:
    - Prompt Selector: pick a saved system prompt; output it as a STRING.
    - Prompt Combiner: merge system + user prompts through a named template.

Both nodes render an inline text preview (the same widget ComfyUI's built-in
PreviewText uses) and are output nodes, so they can terminate a graph.

The prompt library itself lives in storage.py (persistent JSON in the ComfyUI
user directory) and is managed over HTTP routes (api.py) with buttons injected
by the JavaScript extension (web/upsel.js).
"""

import logging

from typing_extensions import override

from comfy_api.latest import ComfyExtension, IO, UI

from .formatting import (
    TEMPLATE_CHOICES,
    TEMPLATE_NL2,
    combine,
)
from .storage import StorageError, get_store

logger = logging.getLogger("upsel")

NODE_ID_SELECTOR = "UniversalPromptSelector"
NODE_ID_COMBINER = "UniversalPromptCombiner"

#: Combo choice that types the selector value in manually instead of
#: choosing a saved prompt from the library.
MANUAL_CHOICE = "(manual entry)"


class PromptSelectorNode(IO.ComfyNode):
    """Select one of the saved system prompts and expose it as a STRING."""

    @classmethod
    def define_schema(cls):
        try:
            names = [p["name"] for p in get_store().list_prompts()]
        except StorageError as e:
            logger.warning("Prompt library unreadable, selector falls back to manual: %s", e)
            names = []
        if names:
            options = names + [MANUAL_CHOICE]
        else:
            options = ["(library empty - add prompts)", MANUAL_CHOICE]
        return IO.Schema(
            node_id=NODE_ID_SELECTOR,
            display_name="Prompt Selector",
            description=(
                "Pick a saved system prompt from your persistent library and "
                "output it as a STRING. Use the Edit / New / Delete buttons on "
                "the node to manage the library."
            ),
            category="utils",
            is_output_node=True,
            inputs=[
                IO.Combo.Input(
                    "prompt_name",
                    options=options,
                    default=options[0],
                    tooltip="Saved system prompt to output. '(manual entry)' types text directly instead.",
                ),
                IO.String.Input(
                    "manual_text",
                    multiline=True,
                    default="",
                    placeholder="Type a system prompt here when '(manual entry)' is selected...",
                    tooltip="Only used when prompt_name is '(manual entry)'.",
                ),
            ],
            outputs=[
                IO.String.Output(display_name="SYSTEM_PROMPT"),
            ],
        )

    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        """Re-run when the saved prompt's text changed on disk.

        The combo input only carries the prompt *name*, so a plain input
        fingerprint would skip execution after an edit. Including the store's
        current file mtime makes edited prompts propagate to new runs.
        """
        import os

        name = kwargs.get("prompt_name") or ""
        try:
            store = get_store()
            p = store.get_by_name(name) if name and name != MANUAL_CHOICE else None
            path = store.path
        except StorageError:
            path = ""
            p = None
        try:
            mtime = os.path.getmtime(path) if path and os.path.exists(path) else 0
        except OSError:
            mtime = 0
        return f"{name}|{mtime}|{'M' if p is None else p.get('updated_at', '')}"

    @classmethod
    def execute(cls, prompt_name: str, manual_text: str) -> IO.NodeOutput:
        if prompt_name == MANUAL_CHOICE:
            text = manual_text or ""
            return IO.NodeOutput(text, ui=UI.PreviewText(text))
        try:
            store = get_store()
            p = store.get_by_name(prompt_name)
        except StorageError as e:
            raise RuntimeError(str(e)) from e
        if p is None:
            available = ", ".join(x["name"] for x in store.list_prompts()) or "(none)"
            raise RuntimeError(
                f"Saved prompt {prompt_name!r} no longer exists. Available: {available}. "
                "Pick another from the dropdown."
            )
        text = p["prompt"]
        return IO.NodeOutput(text, ui=UI.PreviewText(text))


class PromptCombinerNode(IO.ComfyNode):
    """Combine a SYSTEM_PROMPT and a USER_PROMPT through a named template."""

    @classmethod
    def define_schema(cls):
        return IO.Schema(
            node_id=NODE_ID_COMBINER,
            display_name="Prompt Combiner",
            description=(
                "Merge a system prompt with a user prompt using a configurable "
                "template (plain merge, labeled System/User, instruct style, XML "
                "tags, or a fully custom template)."
            ),
            category="utils",
            is_output_node=True,
            inputs=[
                IO.String.Input(
                    "system_prompt",
                    force_input=True,
                    multiline=True,
                    tooltip="System prompt - connect the Prompt Selector output here.",
                ),
                IO.String.Input(
                    "user_prompt",
                    force_input=True,
                    multiline=True,
                    tooltip="The user request/prompt text.",
                ),
                IO.Combo.Input(
                    "format",
                    options=TEMPLATE_CHOICES,
                    default=TEMPLATE_NL2,
                    tooltip="How to merge the two texts.",
                ),
                IO.String.Input(
                    "custom_template",
                    multiline=True,
                    default="",
                    placeholder="System:\n{system_prompt}\n\nUser:\n{user_prompt}",
                    tooltip=(
                        "Used when format is 'custom'. Must contain "
                        "{system_prompt} and/or {user_prompt} placeholders."
                    ),
                ),
                IO.Boolean.Input(
                    "strip_whitespace",
                    default=True,
                    tooltip="Trim surrounding whitespace from both inputs before merging.",
                ),
            ],
            outputs=[
                IO.String.Output(display_name="FINAL_PROMPT"),
            ],
        )

    @classmethod
    def execute(
        cls,
        system_prompt: str,
        user_prompt: str,
        format: str,
        custom_template: str,
        strip_whitespace: bool,
    ) -> IO.NodeOutput:
        from .formatting import FormatError

        try:
            final = combine(
                system_prompt,
                user_prompt,
                format_name=format,
                custom_template=custom_template,
                strip_whitespace=strip_whitespace,
            )
        except FormatError as e:
            raise RuntimeError(str(e)) from e
        return IO.NodeOutput(final, ui=UI.PreviewText(final))


async def comfy_entrypoint() -> ComfyExtension:
    class UniversalPromptSelectorExtension(ComfyExtension):
        @override
        async def get_node_list(self) -> list:
            return [PromptSelectorNode, PromptCombinerNode]

    return UniversalPromptSelectorExtension()
