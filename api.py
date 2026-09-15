"""HTTP routes for managing the prompt library from the ComfyUI frontend.

Registered on ComfyUI's shared aiohttp ``RouteTableDef`` at import time (the
same pattern ComfyUI-Manager uses). ComfyUI materializes the table after all
custom nodes have imported, and mirrors every route under ``/api``, so the
frontend can call ``/upsel/prompts`` via ``api.fetchApi``.

Routes:
    GET    /upsel/prompts            -> list all prompts (sorted by name)
    POST   /upsel/prompts            -> create  {name, prompt, description}
    PUT    /upsel/prompts/{id}       -> update  {name?, prompt?, description?}
    DELETE /upsel/prompts/{id}       -> delete

All responses are JSON: ``{"ok": true, ...}`` or ``{"ok": false, "error": str}``.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from aiohttp import web

from .storage import StorageError, get_store

logger = logging.getLogger("upsel.api")

_routes_attached = False


def _err(message: str, status: int = 400) -> web.Response:
    return web.json_response({"ok": False, "error": message}, status=status)


async def _json_body(request: web.Request) -> Dict[str, Any]:
    try:
        data = await request.json()
    except Exception as e:
        raise ValueError(f"Request body is not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise ValueError("Request body must be a JSON object.")
    return data


async def handle_list(request: web.Request) -> web.Response:
    store = get_store()
    try:
        prompts = store.list_prompts()
    except StorageError as e:
        return _err(str(e), 500)
    return web.json_response(
        {"ok": True, "prompts": prompts, "store_path": store.path}
    )


async def handle_create(request: web.Request) -> web.Response:
    try:
        data = await _json_body(request)
    except ValueError as e:
        return _err(str(e), 400)
    try:
        item = get_store().create_prompt(
            name=str(data.get("name", "")),
            prompt=str(data.get("prompt", "")),
            description=str(data.get("description", "")),
        )
    except StorageError as e:
        return _err(str(e), 400)
    logger.info("Created prompt %r (%s)", item["name"], item["id"])
    return web.json_response({"ok": True, "prompt": item}, status=201)


def _is_missing(exc: StorageError) -> bool:
    return "No prompt with id" in str(exc)


async def handle_update(request: web.Request) -> web.Response:
    prompt_id = request.match_info.get("prompt_id", "")
    try:
        data = await _json_body(request)
    except ValueError as e:
        return _err(str(e), 400)
    try:
        item = get_store().update_prompt(
            prompt_id,
            name=str(data["name"]) if "name" in data else None,
            prompt=str(data["prompt"]) if "prompt" in data else None,
            description=str(data["description"]) if "description" in data else None,
        )
    except StorageError as e:
        return _err(str(e), 404 if _is_missing(e) else 400)
    logger.info("Updated prompt %r (%s)", item["name"], item["id"])
    return web.json_response({"ok": True, "prompt": item})


async def handle_delete(request: web.Request) -> web.Response:
    prompt_id = request.match_info.get("prompt_id", "")
    try:
        removed = get_store().delete_prompt(prompt_id)
    except StorageError as e:
        return _err(str(e), 404 if _is_missing(e) else 400)
    logger.info("Deleted prompt %r (%s)", removed["name"], removed["id"])
    return web.json_response({"ok": True, "deleted": removed})


def attach_routes() -> bool:
    """Register the routes on ComfyUI's shared route table. Safe to re-call."""
    global _routes_attached
    if _routes_attached:
        return True
    try:
        from server import PromptServer  # noqa: PLC0415 - only importable inside ComfyUI
    except Exception:
        logger.info("ComfyUI server module unavailable; prompt API routes not registered.")
        return False
    server = getattr(PromptServer, "instance", None)
    if server is None or getattr(server, "routes", None) is None:
        logger.warning("PromptServer not ready; prompt API routes not registered.")
        return False

    routes = server.routes
    routes.get("/upsel/prompts")(handle_list)
    routes.post("/upsel/prompts")(handle_create)
    routes.put("/upsel/prompts/{prompt_id}")(handle_update)
    routes.delete("/upsel/prompts/{prompt_id}")(handle_delete)

    _routes_attached = True
    logger.info("Prompt library API registered under /upsel/prompts")
    return True


attach_routes()
