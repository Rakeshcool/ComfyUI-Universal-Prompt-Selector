"""ComfyUI-Universal-Prompt-Selector — reusable system prompts as first-class ComfyUI assets.

Nodes:
    - Prompt Selector: pick a saved system prompt; output it as a STRING,
      with Edit / New / Delete buttons to manage the library from the node.
    - Prompt Combiner: merge SYSTEM_PROMPT + USER_PROMPT into FINAL_PROMPT
      through a configurable template (plain, labeled, instruct, XML, custom).

The prompt library is persistent JSON in ComfyUI's user directory
(`<ComfyUI>/user/ComfyUI-Universal-Prompt-Selector/prompts.json`) and is
managed over `/upsel/prompts` HTTP routes by the bundled JS extension.
"""

from . import api  # attaches the /upsel/prompts routes on import
from .nodes import (
    PromptCombinerNode,
    PromptSelectorNode,
    comfy_entrypoint,
)

__all__ = [
    "api",
    "PromptSelectorNode",
    "PromptCombinerNode",
    "comfy_entrypoint",
]

WEB_DIRECTORY = "web"  # served at /extensions/ComfyUI-Universal-Prompt-Selector/

__version__ = "1.0.2"
