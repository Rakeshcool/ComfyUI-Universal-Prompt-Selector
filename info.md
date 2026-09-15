# Node reference — ComfyUI-Universal-Prompt-Selector

## Prompt Selector

**Category:** `utils` · **Output node** (can terminate a graph) · **Outputs:** `SYSTEM_PROMPT` (STRING)

Renders an inline text preview of the selected prompt's text.

| Input | Type | Default | Notes |
|---|---|---|---|
| `prompt_name` | COMBO | first saved prompt | Choices come live from your library plus `(manual entry)`. |
| `manual_text` | STRING (multiline) | `""` | Only used when `prompt_name` is `(manual entry)`. |

Buttons added by the JS extension:

- **✏ Edit** — open a dialog with the selected prompt's name/description/text; save writes to the library and refreshes every selector's dropdown.
- **➕ New** — create a new prompt; the dropdown refreshes and selects it.
- **🗑 Delete** — remove the selected prompt after confirmation.

Caching: the node re-executes when the underlying prompt's text/`updated_at` changes (V3 `fingerprint_inputs`), so edits propagate without workflow changes.

## Prompt Combiner

**Category:** `utils` · **Output node** · **Outputs:** `FINAL_PROMPT` (STRING)

Renders an inline text preview of the combined result.

| Input | Type | Default | Notes |
|---|---|---|---|
| `system_prompt` | STRING (multiline, widget-converted input) | — | Connect the Prompt Selector output here. |
| `user_prompt` | STRING (multiline, widget-converted input) | — | The user's request text. |
| `format` | COMBO | `plain_merge` | `plain_merge` / `labeled` / `instruct` / `xml` / `custom`. |
| `custom_template` | STRING (multiline) | `""` | Used only when `format = custom`; must contain `{system_prompt}` and/or `{user_prompt}`. |
| `strip_whitespace` | BOOLEAN | `true` | Trims both inputs before merging. |

Errors raised at run time: `custom` selected with an empty template or a template missing both placeholders.

## Library storage

- File: `<ComfyUI>/user/ComfyUI-Universal-Prompt-Selector/prompts.json`
- Schema: `{"version": 1, "prompts": [{id, name, description, prompt, created_at, updated_at}]}`
- Writes are atomic (temp file + replace) and serialized behind a lock; a corrupt file is backed up as `prompts.json.corrupt-<ts>` and a fresh library is created rather than losing data silently.
- Overridable location for tests/portable setups via the `UPSEL_STORE_PATH` environment variable.
