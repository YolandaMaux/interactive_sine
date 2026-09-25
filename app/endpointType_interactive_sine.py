#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
endpointType_interactive_sine.py – LLM endpoint routing for the INTERACTIVE SINE framework.

Derived from endpointType_template.py (endpointType_stock_chat.py lineage).
App-agnostic: every environment variable uses ENV_PREFIX, so a forked app
only changes that one constant (and the file name).

Two wire formats are supported:
- OpenAI-compatible chat completions (llama.cpp / vLLM / any local OpenAI-style server)
- Perplexity Agent API (successor to Sonar Chat Completions; Sonar is sunset 2026-09-27)

INTEGRATION NOTE
================
This module is used by main_interactive_sine.py (stream_completion) and needs no
edits for a standard app. Only touch it if your app talks to a different
wire protocol.
"""

from __future__ import annotations

import json
import os

# Renamed from TEMPLATE_ when forking the template; keep in sync with
# app_interactive_sine.py + main_interactive_sine.py.
ENV_PREFIX = "INTERACTIVE_SINE_"

ROUTES = {
    "chat": "v1/chat/completions",
    "agent": "v1/agent",
    "embed": "v1/embeddings",
    "embeddings": "v1/embeddings",
    "models": "v1/models",
}

_BASE_URL_ENV_BY_KIND = {
    "llm": ENV_PREFIX + "LLM_ENGINE_URL",
    "embedding": ENV_PREFIX + "EMBEDDING_LLM_ENGINE_URL",
    "reranker": ENV_PREFIX + "RERANKER_LLM_BASE_URL",
}

PERPLEXITY_HOST = "api.perplexity.ai"

# Sonar -> preset mappings. Presets configure web search and reasoning
# effort and CANNOT have their tools disabled ("tools": [] does not clear
# preset tools), so for pure-chunk RAG these must stay unused (default off).
SONAR_PRESET_MAP = {
    "sonar": "fast",
    "sonar-pro": "low",
    "sonar-reasoning-pro": "medium",
    "sonar-deep-research": "high",
}

def get_base_url(kind: str = "llm") -> str:
    env_var = _BASE_URL_ENV_BY_KIND.get(kind, ENV_PREFIX + "LLM_ENGINE_URL")
    return os.getenv(
        env_var,
        os.getenv(ENV_PREFIX + "LLM_ENGINE_URL", "http://localhost:8080"),
    )

def is_perplexity(base: str) -> bool:
    return PERPLEXITY_HOST in base

def endpoint(route: str, kind: str = "llm") -> str:
    base = get_base_url(kind).rstrip("/")
    if is_perplexity(base):
        if base.endswith("/v1"):
            base = base[: -len("/v1")]
        if route == "chat":
            route = "agent"
        return f"{base}/{ROUTES[route]}"
    return f"{base}/{ROUTES[route]}"

# ------------------------------------------------- llama.cpp / vLLM (RAG-safe)
# Payload contains ONLY model, messages, stream, temperature, max_tokens.
# No tools are ever attached, and a local llama.cpp/vLLM server has no
# web-search capability to invoke. Reasoning is never triggered by the
# request; it only occurs if you deliberately load a reasoning model.

def build_chat_payload(conv: dict) -> dict:
    msgs = []
    if (conv.get("system_prompt") or "").strip():
        msgs.append({"role": "system", "content": conv["system_prompt"].strip()})
    msgs += [
        {"role": m["role"], "content": m["content"]}
        for m in conv.get("messages", [])
        if m.get("content")
    ]
    return {
        "model": conv["model"],
        "messages": msgs,
        "stream": True,
        "temperature": float(conv.get("temperature", 0.7)),
        "max_tokens": int(conv.get("max_tokens", 4096)),
    }

def parse_stream_chunk(raw_line: str) -> tuple[str, bool]:
    line = raw_line.strip()
    if not line:
        return "", False
    if line.startswith("data:"):
        line = line[5:].strip()
    if line == "[DONE]":
        return "", True
    try:
        data = json.loads(line)
        choice = (data.get("choices") or [{}])[0]
        delta = choice.get("delta", {}).get("content", "")
        done = choice.get("finish_reason") is not None
        return delta or "", done
    except (json.JSONDecodeError, IndexError):
        return "", False

# ------------------------------- Perplexity Agent API (RAG-safe by default)
# Pure-chunk RAG rules, per the migration guide:
# 1. Do NOT include any tools. Web search is opt-in on the Agent API;
#    omitting the web_search tool means the model does not search
#    (the Sonar "disable_search" equivalent).
# 2. Do NOT use a preset. Preset tools stay enabled and cannot be cleared
#    ("tools": [] does not remove them), and presets set reasoning effort.
# 3. Use model="perplexity/sonar" directly — a non-reasoning model, so no
#    reasoning trace is produced.
# 4. To constrain the model to the retrieved chunks, instruct it in the
#    system prompt to answer ONLY from the provided context.

def build_agent_payload(
    conv: dict,
    use_preset: bool = False,
    web_search: bool = False,
) -> dict:
    payload = {
        "input": [
            {"type": "message", "role": m["role"], "content": m["content"]}
            for m in conv.get("messages", [])
            if m.get("content")
        ],
        "stream": True,
        "temperature": float(conv.get("temperature", 0.7)),
        "max_output_tokens": int(conv.get("max_tokens", 4096)),
    }
    instructions = (conv.get("system_prompt") or "").strip()
    if instructions:
        payload["instructions"] = instructions

    # RAG-safe default: no tools key at all -> no web search, no tool loop.
    if web_search:
        payload["tools"] = [{"type": "web_search"}]

    model = conv.get("model", "sonar")
    if use_preset and model in SONAR_PRESET_MAP:
        # Research presets: enable search + reasoning. NOT for pure RAG.
        payload["preset"] = SONAR_PRESET_MAP[model]
    else:
        payload["model"] = model if "/" in model else f"perplexity/{model}"
    return payload

def parse_agent_stream_chunk(raw_line: str) -> tuple[str, bool]:
    line = raw_line.strip()
    if not line:
        return "", False
    if line.startswith("data:"):
        line = line[5:].strip()
    if line == "[DONE]":
        return "", True
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return "", False
    etype = event.get("type", "")
    if etype == "response.output_text.delta":
        return event.get("delta") or "", False
    if etype in (
        "response.completed",
        "response.failed",
        "response.incomplete",
        "error",
    ):
        return "", True
    return "", False

def parse_agent_response(data: dict) -> dict:
    """Extract answer text and search results from a non-streaming response."""
    text_parts, results = [], []
    for item in data.get("output", []):
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    text_parts.append(part.get("text", ""))
        elif item.get("type") == "search_results":
            results = item.get("results", [])
    return {"text": "".join(text_parts), "search_results": results}

# ------------------------------------------------------------------ shared

def build_chat_payload_for(
    conv: dict,
    base: str,
    use_preset: bool = False,
    web_search: bool = False,
) -> dict:
    """Route-aware payload builder. RAG-safe defaults on both paths."""
    if is_perplexity(base):
        return build_agent_payload(
            conv, use_preset=use_preset, web_search=web_search
        )
    return build_chat_payload(conv)

def parse_stream_chunk_for(raw_line: str, base: str) -> tuple[str, bool]:
    """Route-aware stream parser."""
    if is_perplexity(base):
        return parse_agent_stream_chunk(raw_line)
    return parse_stream_chunk(raw_line)

# ------------------------------------------------------------------- misc

def parse_models_response(data: dict) -> list[str]:
    names = [m.get("id") for m in data.get("data", []) if m.get("id")]
    return sorted(filter(None, names), key=str.lower)

def build_embed_payload(text: str, model: str) -> dict:
    return {"model": model, "input": text}

def parse_embed_response(data: dict):
    items = data.get("data") or []
    return items[0].get("embedding") if items else None
