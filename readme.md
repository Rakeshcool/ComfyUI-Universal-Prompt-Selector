# ComfyUI-Universal-Prompt-Selector

Reusable **system prompts as first-class ComfyUI assets** — create, store, manage, select, and apply system prompts inside ComfyUI, and compose them with user prompts through configurable templates.

```text
System Prompt                    ┌──────────────────┐
     ↓                           │ Saved Prompt DB  │
Prompt Selector ───────────────► │ • Video Writer   │
     ↓ SYSTEM_PROMPT             │ • OCR Expert     │
User Prompt ──► Prompt Combiner  │ • Image Prompt   │
     ↓ FINAL_PROMPT              │ • Coding Expert  │
LLM / API / Text Encoder         └──────────────────┘
```

## Nodes

| Node | Purpose |
|---|---|
| **Prompt Selector** | Dropdown of saved system prompts → outputs the text as a `STRING`. Includes **Edit / New / Delete / Refresh** buttons to manage the library without leaving the canvas. Also offers `(manual entry)` for one-off text. |
| **Prompt Combiner** | Merges `SYSTEM_PROMPT` + `USER_PROMPT` → `FINAL_PROMPT` through a selectable template. Both nodes show an inline text preview and are output nodes. |

### Combiner formats

| Format | Output shape |
|---|---|
| `plain_merge` | system + blank line + user |
| `labeled` | `System:\n…\n\nUser:\n…` |
| `instruct` | `System prompt:\n…\n\nUser request:\n…` |
| `xml` | `<system_prompt>…</system_prompt>\n\n<user_prompt>…</user_prompt>` |
| `custom` | your own template using `{system_prompt}` / `{user_prompt}` |

Templates are rendered with plain placeholder substitution (not `str.format`), so prompt text containing literal braces (JSON examples, code) is always safe.

## Install

**A) ComfyUI Manager / Registry:** search for *ComfyUI-Universal-Prompt-Selector* and install.

**B) git clone:**
```bash
cd <ComfyUI>/custom_nodes
git clone https://github.com/Rakeshcool/ComfyUI-Universal-Prompt-Selector.git
```

**C) Manual:** copy the `ComfyUI-Universal-Prompt-Selector` folder into `<ComfyUI>/custom_nodes/`.

No Python dependencies — everything uses the ComfyUI-shipped stack (aiohttp, stdlib). Restart ComfyUI after installing.

## Usage

1. Add **Prompt Selector** → click **➕ New** → fill in name + prompt text → *Create*. The dropdown refreshes immediately and selects the new prompt.
2. Add **Prompt Combiner**, connect the selector's `SYSTEM_PROMPT` into it and type (or wire) your `user_prompt`.
3. Choose a format (or write a `custom` template) and queue — the combined text previews on the node and flows onward as a `STRING`.

Your library lives at `<ComfyUI>/user/ComfyUI-Universal-Prompt-Selector/prompts.json` (human-editable JSON), so prompts survive restarts and are shared by every workflow. A few starter prompts are seeded on first run.

## Example workflow

A ready-made example ships with the pack: [`examples/sample_prompt_selector.json`](examples/sample_prompt_selector.json).

```text
[Primitive String] "hello there" ──USER_PROMPT──┐
                                                v
[Prompt Selector] "Coding Expert" ─SYSTEM_PROMPT→ [Prompt Combiner] (instruct) ─FINAL_PROMPT→ [Preview as Text]
```

**Load it:** drag the JSON file onto the ComfyUI canvas (or *Workflow → Open*). It selects the *Coding Expert* starter prompt, merges it with the Primitive String text using the `instruct` format, and shows the final prompt in a *Preview as Text* node — queue it and the combined text appears on both the Combiner and the preview.

The graph is plain core nodes plus this pack, so it loads anywhere ComfyUI runs (no pysssss or extra dependencies). The selector's dropdown re-syncs with your own library on load, so pick any saved prompt you like.

## HTTP API (used by the UI, handy for scripting)

| Method | Route | Body |
|---|---|---|
| GET | `/upsel/prompts` | — |
| POST | `/upsel/prompts` | `{name, prompt, description?}` |
| PUT | `/upsel/prompts/{id}` | `{name?, prompt?, description?}` |
| DELETE | `/upsel/prompts/{id}` | — |

Also mirrored under `/api/upsel/prompts`.

## Tips

- Selector caches per prompt content: editing a prompt in the library and re-queueing the same workflow picks up the new text automatically (no cache staleness).
- Deleting a prompt that a workflow references fails that queue with a clear message naming the missing prompt; the dropdown refreshes on next interaction.
- Use `(manual entry)` in the selector to type a one-off system prompt without saving it.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Buttons missing on the node | Extension JS not loaded — confirm `/extensions/ComfyUI-Universal-Prompt-Selector/upsel.js` returns 200 and hard-refresh the browser (Ctrl+F5). |
| "Could not refresh prompt list" | The ComfyUI server wasn't reachable or the routes didn't register; check the ComfyUI console for `Prompt library API registered under /upsel/prompts`. |
| Corrupt prompts.json warning | The store backed up the bad file as `prompts.json.corrupt-…` and created a fresh library; recover your texts from the backup file. |
| Edited prompt not picked up on queue | Older ComfyUI without the V3 `fingerprint_inputs` hook — press Queue twice or change any input. |
| New prompt missing from the dropdown after reload | Should not happen since v1.0.1: the dropdown re-syncs from the library on node creation and workflow load, and the workflow's saved selection is restored afterwards. If it ever does, click **🔄 Refresh** on the node and hard-refresh the browser (Ctrl+F5). |
| Workflow's prompt selection resets on load | The saved selection is restored even when the cached node definition is stale. A selection whose prompt was deleted from the library is kept intentionally and reported at queue time. |
