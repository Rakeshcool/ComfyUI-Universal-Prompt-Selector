/**
 * ComfyUI-Universal-Prompt-Selector — frontend extension.
 *
 * Adds to every Prompt Selector node:
 *   - [Edit] [New] [Delete] buttons bound to the /upsel/prompts HTTP API
 *   - a create/edit dialog (name, description, prompt text)
 *   - live refresh of the prompt combo on all selector nodes after CRUD
 *   - automatic combo sync whenever a node is created or a workflow is
 *     loaded (works around frontend node-definition caching, which would
 *     otherwise show a stale dropdown until the next full reload)
 *   - restore-after-load: a selection saved in the workflow is re-applied
 *     after the sync, even if the freshly-loaded node definition was stale
 *   - a Refresh button to re-pull the library on demand
 *
 * No build step, no dependencies — plain ES module loaded by ComfyUI from
 * /extensions/ComfyUI-Universal-Prompt-Selector/upsel.js
 */
import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const NODE_TYPE = "UniversalPromptSelector";
const WIDGET_NAME = "prompt_name";
const MANUAL_CHOICE = "(manual entry)";
const EMPTY_CHOICE = "(library empty - add prompts)";

/* ------------------------------------------------------------------ api */

async function fetchPrompts() {
  const res = await api.fetchApi("/upsel/prompts");
  const body = await res.json();
  if (!body.ok) throw new Error(body.error || `HTTP ${res.status}`);
  return body.prompts || [];
}

async function createPrompt(data) {
  const res = await api.fetchApi("/upsel/prompts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  const body = await res.json();
  if (!body.ok) throw new Error(body.error || `HTTP ${res.status}`);
  return body.prompt;
}

async function updatePrompt(id, data) {
  const res = await api.fetchApi(`/upsel/prompts/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  const body = await res.json();
  if (!body.ok) throw new Error(body.error || `HTTP ${res.status}`);
  return body.prompt;
}

async function deletePrompt(id) {
  const res = await api.fetchApi(`/upsel/prompts/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
  const body = await res.json();
  if (!body.ok) throw new Error(body.error || `HTTP ${res.status}`);
  return body.deleted;
}

/* --------------------------------------------------------------- widget */

function comboWidget(node) {
  return (node.widgets || []).find((w) => w.name === WIDGET_NAME) || null;
}

function currentName(node) {
  const w = comboWidget(node);
  return w ? w.value : null;
}

/**
 * Build the option list for the current library state.
 * @returns {string[]} combo values
 */
function optionsFor(prompts) {
  const names = prompts.map((p) => p.name);
  if (names.length) return names.concat([MANUAL_CHOICE]);
  return [EMPTY_CHOICE, MANUAL_CHOICE];
}

/**
 * Apply new options to one node's combo, preserving the current selection
 * whenever it still exists. Only these cases change the value:
 *   - `preferred` (a value restored from a saved workflow) exists -> select it
 *   - the current value is the empty-library placeholder and real prompts
 *     now exist -> select the first real prompt
 *   - the current value is empty/null -> select the first option
 * A value that no longer exists in the library is KEPT (not silently
 * reset) so the node's execute() can report exactly which prompt went
 * missing instead of the workflow quietly running with a different one.
 */
function applyOptions(node, options, preferred) {
  const w = comboWidget(node);
  if (!w) return;
  const prev = w.value;
  w.options = Object.assign({}, w.options, { values: options });
  if (preferred && options.indexOf(preferred) !== -1) {
    w.value = preferred;
  } else if (prev == null || prev === "" || prev === EMPTY_CHOICE) {
    w.value = options[0];
  } else {
    w.value = prev; // kept even if missing -> surfaced at queue time
  }
}

/** Re-pull the library and refresh every selector node on the canvas. */
async function refreshCombos(selectName) {
  const prompts = await fetchPrompts(); // caller toasts on failure
  const options = optionsFor(prompts);
  const nodes = (app.graph && app.graph._nodes) || [];
  for (const node of nodes) {
    if (node.type !== NODE_TYPE) continue;
    applyOptions(node, options, selectName);
  }
  app.graph.setDirtyCanvas(true, true);
  return { options };
}

/** Fetch the library and sync one node's combo (used on node creation). */
async function syncNode(node, preferred) {
  try {
    const prompts = await fetchPrompts();
    applyOptions(node, optionsFor(prompts), preferred);
    app.graph.setDirtyCanvas(true, true);
  } catch (e) {
    // Silent on load paths: the server may briefly be unavailable; the
    // Refresh button gives an explicit, reported retry.
    console.warn("[upsel] could not sync prompt dropdown:", e);
  }
}

/* ----------------------------------------------------------------- ui */

function toast(message, isError) {
  const el = document.createElement("div");
  el.textContent = message;
  el.style.cssText = [
    "position:fixed", "bottom:18px", "left:50%", "transform:translateX(-50%)",
    "z-index:10001", "padding:10px 16px", "border-radius:8px",
    "font:13px/1.4 sans-serif", "max-width:70vw", "box-shadow:0 4px 14px rgba(0,0,0,.4)",
    isError ? "background:#b3372f;color:#fff" : "background:#2f7d4f;color:#fff",
  ].join(";");
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

let dialogOpen = false;

/** Modal form dialog. Returns via onSubmit(data) or closes on cancel. */
function showDialog({ title, initial, submitLabel, onSubmit }) {
  if (dialogOpen) return;
  dialogOpen = true;

  const backdrop = document.createElement("div");
  backdrop.style.cssText =
    "position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:10000;display:flex;" +
    "align-items:center;justify-content:center;";
  backdrop.addEventListener("mousedown", (ev) => {
    if (ev.target === backdrop) close();
  });

  const box = document.createElement("div");
  box.style.cssText =
    "background:#1e1e1e;color:#ddd;border:1px solid #444;border-radius:10px;" +
    "padding:16px;width:540px;max-width:92vw;max-height:86vh;display:flex;" +
    "flex-direction:column;gap:10px;font:13px/1.45 sans-serif;box-shadow:0 8px 30px rgba(0,0,0,.6);";

  const h = document.createElement("div");
  h.textContent = title;
  h.style.cssText = "font-size:15px;font-weight:600;color:#fff;";
  box.appendChild(h);

  const mkLabel = (t) => {
    const l = document.createElement("div");
    l.textContent = t;
    l.style.cssText = "color:#999;font-size:11px;text-transform:uppercase;letter-spacing:.05em;";
    return l;
  };

  const nameIn = document.createElement("input");
  nameIn.value = initial.name || "";
  nameIn.placeholder = "Prompt name (e.g. Video Prompt Writer)";
  nameIn.style.cssText =
    "width:100%;box-sizing:border-box;background:#111;color:#eee;border:1px solid #444;" +
    "border-radius:6px;padding:8px;";

  const descIn = document.createElement("input");
  descIn.value = initial.description || "";
  descIn.placeholder = "Short description (optional)";
  descIn.style.cssText = nameIn.style.cssText;

  const promptTa = document.createElement("textarea");
  promptTa.value = initial.prompt || "";
  promptTa.placeholder = "The system prompt text...";
  promptTa.rows = 12;
  promptTa.style.cssText =
    "width:100%;box-sizing:border-box;background:#111;color:#eee;border:1px solid #444;" +
    "border-radius:6px;padding:8px;resize:vertical;font:12px/1.5 monospace;min-height:180px;";

  const row = document.createElement("div");
  row.style.cssText = "display:flex;gap:8px;justify-content:flex-end;";
  const err = document.createElement("div");
  err.style.cssText = "color:#ff8f8f;font-size:12px;min-height:1em;white-space:pre-wrap;";

  const mkBtn = (label, primary) => {
    const b = document.createElement("button");
    b.textContent = label;
    b.style.cssText =
      "padding:7px 14px;border-radius:6px;border:1px solid #555;cursor:pointer;font:13px sans-serif;" +
      (primary ? "background:#3a7bd5;color:#fff;border-color:#3a7bd5;" : "background:#2a2a2a;color:#ccc;");
    return b;
  };
  const cancelBtn = mkBtn("Cancel");
  const saveBtn = mkBtn(submitLabel, true);
  row.appendChild(cancelBtn);
  row.appendChild(saveBtn);

  box.appendChild(mkLabel("Name"));
  box.appendChild(nameIn);
  box.appendChild(mkLabel("Description"));
  box.appendChild(descIn);
  box.appendChild(mkLabel("Prompt"));
  box.appendChild(promptTa);
  box.appendChild(err);
  box.appendChild(row);
  backdrop.appendChild(box);
  document.body.appendChild(backdrop);

  function close() {
    dialogOpen = false;
    backdrop.remove();
  }

  cancelBtn.addEventListener("click", close);
  const onKey = (ev) => {
    if (ev.key === "Escape") {
      ev.stopPropagation();
      close();
    }
  };
  document.addEventListener("keydown", onKey, true);

  async function submit() {
    const data = {
      name: nameIn.value.trim(),
      description: descIn.value.trim(),
      prompt: promptTa.value,
    };
    if (!data.name) {
      err.textContent = "Name cannot be empty.";
      return;
    }
    if (!data.prompt.trim()) {
      err.textContent = "Prompt text cannot be empty.";
      return;
    }
    saveBtn.disabled = true;
    try {
      await onSubmit(data);
      close();
    } catch (e) {
      err.textContent = e.message || String(e);
      saveBtn.disabled = false;
    }
  }
  saveBtn.addEventListener("click", submit);
  promptTa.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) {
      ev.preventDefault();
      submit();
    }
  });

  nameIn.focus();
}

/* ------------------------------------------------------------ extension */

app.registerExtension({
  name: "upsel.prompt.library",

  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== NODE_TYPE) return;

    const onNodeCreated = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = onNodeCreated ? onNodeCreated.apply(this, arguments) : undefined;

      // Sync the dropdown with the live library on every node creation,
      // including when a saved workflow is loaded. Fire-and-forget: never
      // block canvas construction; the Refresh button is the manual path.
      void syncNode(this);

      this.addWidget("button", "🔄 Refresh", null, () => {
        refreshCombos()
          .then(() => toast("Prompt list refreshed."))
          .catch((e) => toast(`Could not refresh prompt list: ${e.message}`, true));
      });

      this.addWidget("button", "✏ Edit", null, () => {
        const name = currentName(this);
        if (!name || name === MANUAL_CHOICE || name === EMPTY_CHOICE) {
          toast("Select a saved prompt first (or use New).", true);
          return;
        }
        (async () => {
          let list;
          try {
            list = await fetchPrompts();
          } catch (e) {
            toast(e.message, true);
            return;
          }
          const item = list.find((p) => p.name === name);
          if (!item) {
            toast("That prompt is no longer in the library.", true);
            refreshCombos().catch(() => {});
            return;
          }
          showDialog({
            title: `Edit prompt: ${item.name}`,
            initial: item,
            submitLabel: "Save changes",
            onSubmit: async (data) => {
              await updatePrompt(item.id, data);
              await refreshCombos(data.name);
              toast(`Updated "${data.name}".`);
            },
          });
        })();
      });

      this.addWidget("button", "➕ New", null, () => {
        showDialog({
          title: "New system prompt",
          initial: { name: "", description: "", prompt: "" },
          submitLabel: "Create prompt",
          onSubmit: async (data) => {
            const created = await createPrompt(data);
            await refreshCombos(created.name);
            toast(`Created "${created.name}".`);
          },
        });
      });

      this.addWidget("button", "🗑 Delete", null, () => {
        const name = currentName(this);
        if (!name || name === MANUAL_CHOICE || name === EMPTY_CHOICE) {
          toast("Select a saved prompt first.", true);
          return;
        }
        (async () => {
          let list;
          try {
            list = await fetchPrompts();
          } catch (e) {
            toast(e.message, true);
            return;
          }
          const item = list.find((p) => p.name === name);
          if (!item) {
            toast("That prompt is no longer in the library.", true);
            refreshCombos().catch(() => {});
            return;
          }
          if (!window.confirm(`Delete prompt "${item.name}"? This cannot be undone.`)) return;
          try {
            await deletePrompt(item.id);
            await refreshCombos();
            toast(`Deleted "${item.name}".`);
          } catch (e) {
            toast(e.message, true);
          }
        })();
      });

      return r;
    };

    // Restore-after-load: onConfigure runs when a saved workflow's widget
    // values are applied. Remember the serialized selection and re-apply it
    // after the async sync, so a stale node definition (cached options that
    // predate the saved prompt) can't drop the selection on load.
    const onConfigure = nodeType.prototype.onConfigure;
    nodeType.prototype.onConfigure = function () {
      const r = onConfigure ? onConfigure.apply(this, arguments) : undefined;
      const saved = currentName(this);
      if (saved) void syncNode(this, saved);
      return r;
    };
  },
});
