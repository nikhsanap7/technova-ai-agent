"""Gemini-powered agent. Gemini only DECIDES; our code EXECUTES.

Flow: user text -> Gemini -> (tool request -> MCP client -> MCP server ->
backend -> result -> Gemini)* -> final answer.
Write tools are intercepted and need confirm_pending() before they run.
"""
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

from agent.confirmation import (ALLOWED_ORDER_STATUSES, PendingAction,
                                is_write_tool, normalize_order_status)
from retrieval.metadata_search import search_operations
from tools.mcp_client import call_tool_sync, list_tools_sync

load_dotenv()

MAX_STEPS = 5  # max Gemini <-> tool round trips per user message

# ---------- logging ----------
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
log = logging.getLogger("technova.agent")
if not log.handlers:
    log.setLevel(logging.INFO)
    handler = logging.FileHandler(LOG_DIR / "agent.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)

SYSTEM_PROMPT = """You are the TechNova GmbH enterprise assistant. You help \
employees query and update the company's business system (customers, orders, \
products, invoices) using the provided tools.

Rules:
1. Use the tools for every question about business data. Never answer from \
memory and never invent data, IDs, tools or parameters.
2. Extract parameters exactly as the user states them. Do not guess missing \
information.
3. If the request is ambiguous or lacks required information (for example \
"update the customer" without saying which customer or what to change), do \
not call any tool. Ask one short clarification question instead.
4. If the user asks for something no tool supports, say so plainly.
5. To change an order, call update_order_status. The system itself asks the \
user for confirmation before anything is changed, so do NOT ask for \
confirmation in text, and never claim a change was made until the tool \
result confirms it.
6. If a tool returns an error, explain it in plain words. Never present a \
failed operation as successful.
7. Present results clearly and concisely. Amounts are in euros."""


# ---------- schema conversion: MCP -> Gemini ----------
def clean_schema(schema: dict) -> dict:
    """Reduce a JSON Schema to the simple subset Gemini accepts.
    Python's Optional[int] becomes anyOf[integer, null]; we keep 'integer'."""
    out = {}
    if "anyOf" in schema:
        non_null = [s for s in schema["anyOf"] if s.get("type") != "null"]
        if non_null:
            out.update(clean_schema(non_null[0]))
    for key in ("type", "description", "enum"):
        if key in schema:
            out[key] = schema[key]
    if "properties" in schema:
        out["properties"] = {k: clean_schema(v)
                             for k, v in schema["properties"].items()}
    if "required" in schema:
        out["required"] = schema["required"]
    return out


def build_declarations(tools: list[dict]) -> dict:
    decls = {}
    for t in tools:
        kwargs = {"name": t["name"],
                  "description": " ".join((t["description"] or "").split())}
        schema = clean_schema(t["input_schema"])
        if schema.get("properties"):          # tools without parameters: omit
            kwargs["parameters_json_schema"] = schema
        decls[t["name"]] = types.FunctionDeclaration(**kwargs)
    return decls


def coerce_args(args: dict, schema: dict) -> dict:
    """Gemini sometimes returns 1025.0 for an integer; fix that."""
    props = schema.get("properties", {})
    fixed = {}
    for key, value in args.items():
        if (props.get(key, {}).get("type") == "integer"
                and isinstance(value, float) and value.is_integer()):
            value = int(value)
        fixed[key] = value
    return fixed


@dataclass
class AgentReply:
    text: str = ""
    tool_calls: list = field(default_factory=list)  # what was executed (for UI/eval)
    pending: Optional[PendingAction] = None         # set when confirmation is needed
    error: Optional[str] = None
    seconds: float = 0.0


class EnterpriseAgent:
    def __init__(self, tool_mode: str = "all"):
        """tool_mode: 'all' = give Gemini every MCP tool;
        'retrieval' = give only the top-3 tools from metadata retrieval."""
        key = os.getenv("GEMINI_API_KEY")
        self.model = os.getenv("GEMINI_MODEL")
        if not key or not self.model:
            raise RuntimeError("GEMINI_API_KEY or GEMINI_MODEL missing in .env")
        self.client = genai.Client(api_key=key)
        self.tool_mode = tool_mode

        tools = list_tools_sync()                      # MCP tool discovery
        self.declarations = build_declarations(tools)
        self.schemas = {t["name"]: clean_schema(t["input_schema"]) for t in tools}

        self.history: list[types.Content] = []
        self.pending: Optional[PendingAction] = None
        self._trace: list[dict] = []

    # ---------- public API ----------
    def send(self, user_text: str) -> AgentReply:
        start = time.time()
        if self.pending:                       # a new message cancels an open request
            self._resolve_pending(approved=False, silent=True)
        self._trace = []
        log.info("USER: %s", user_text)
        self.history.append(types.Content(
            role="user", parts=[types.Part.from_text(text=user_text)]))
        return self._loop(self._select_tools(user_text), start)

    def confirm_pending(self) -> AgentReply:
        return self._resolve_pending(approved=True)

    def cancel_pending(self) -> AgentReply:
        return self._resolve_pending(approved=False)

    # ---------- internals ----------
    def _select_tools(self, user_text: str) -> list[str]:
        if self.tool_mode == "retrieval":
            names = [h["tool_name"] for h in search_operations(user_text, top_k=3)]
            if names:
                return names
        return list(self.declarations)

    def _generate(self, tool_names: list[str]):
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[types.Tool(function_declarations=[
                self.declarations[n] for n in tool_names])],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True),
        )
        for attempt in range(4):
            try:
                return self.client.models.generate_content(
                    model=self.model, contents=self.history, config=config)
            except errors.APIError as e:
                code = getattr(e, "code", None)
                if code in (429, 500, 503) and attempt < 3:
                    wait = 10 * (attempt + 1)
                    log.warning("Gemini error %s, retrying in %ss", code, wait)
                    time.sleep(wait)
                    continue
                raise

    def _run_tool(self, name: str, args: dict, purpose: str = "agent",
                  confirmed: bool = False) -> dict:
        """The ONLY place tools are executed. Write tools need confirmed=True,
        which only _resolve_pending(approved=True) ever passes."""
        if name not in self.declarations:
            return {"ok": False, "error": f"Tool '{name}' is not available."}
        if is_write_tool(name) and not confirmed:
            raise PermissionError(f"Write tool '{name}' requires confirmation")
        args = coerce_args(args, self.schemas[name])
        t0 = time.time()
        try:
            result = call_tool_sync(name, args)
        except Exception as e:
            result = {"ok": False, "error": f"Tool call failed: {e}"}
        ms = round((time.time() - t0) * 1000)
        log.info("TOOL %s args=%s purpose=%s ok=%s (%d ms)",
                 name, args, purpose, result.get("ok"), ms)
        self._trace.append({"name": name, "args": args, "result": result,
                            "ms": ms, "purpose": purpose})
        return result

    @staticmethod
    def _response_part(name: str, result: dict) -> types.Part:
        return types.Part.from_function_response(
            name=name, response={"result": result})

    def _preview(self, name: str, args: dict) -> tuple[bool, str]:
        """Check a write request BEFORE asking the user to confirm it.
        Returns (ok, description_for_user) or (False, error_message)."""
        if name == "update_order_status":
            status = normalize_order_status(args.get("status"))
            if status is None:
                return False, ("Invalid status. Allowed: "
                               + ", ".join(ALLOWED_ORDER_STATUSES))
            if args.get("order_id") is None:
                return False, "order_id is missing."
            res = self._run_tool("get_order", {"order_id": args["order_id"]},
                                 purpose="preview")
            if not res.get("ok"):
                return False, f"{res.get('error')} (nothing was changed)"
            order = res["data"]
            if order["status"] == status:
                return False, (f"Order {order['order_id']} already has status "
                               f"'{status}'. Nothing to change.")
            args["status"] = status
            return True, (f"Order {order['order_id']} ({order['company']}, "
                          f"{order['product']}, EUR {order['amount']}): "
                          f"status '{order['status']}' -> '{status}'")
        return True, f"Execute {name} with {args}"

    def _loop(self, tool_names: list[str], start: float) -> AgentReply:
        try:
            for _ in range(MAX_STEPS):
                resp = self._generate(tool_names)
                calls = resp.function_calls or []
                if not calls:
                    text = resp.text or "(The model returned no answer.)"
                    self.history.append(types.Content(
                        role="model", parts=[types.Part.from_text(text=text)]))
                    log.info("AGENT: %s", text)
                    return AgentReply(text=text, tool_calls=self._trace,
                                      seconds=round(time.time() - start, 2))

                self.history.append(resp.candidates[0].content)
                parts, pending = [], None
                for call in calls:
                    args = dict(call.args or {})
                    if is_write_tool(call.name):
                        if pending is not None:
                            parts.append(self._response_part(call.name, {
                                "ok": False,
                                "error": "Only one change per request. Not executed."}))
                            continue
                        ok, info = self._preview(call.name, args)
                        if ok:
                            pending = PendingAction(call.name, args, info)
                            parts.append(None)               # filled after confirm
                            pending.slot = len(parts) - 1
                        else:
                            parts.append(self._response_part(
                                call.name, {"ok": False, "error": info}))
                    else:
                        result = self._run_tool(call.name, args)
                        parts.append(self._response_part(call.name, result))

                if pending:
                    pending.parts = parts
                    self.pending = pending
                    log.info("PENDING CONFIRMATION: %s", pending.description)
                    return AgentReply(tool_calls=self._trace, pending=pending,
                                      seconds=round(time.time() - start, 2))
                self.history.append(types.Content(role="user", parts=parts))

            return AgentReply(error="Stopped: too many tool steps for one request.",
                              tool_calls=self._trace,
                              seconds=round(time.time() - start, 2))
        except Exception as e:
            log.exception("Agent error")
            return AgentReply(error=f"{type(e).__name__}: {e}",
                              tool_calls=self._trace,
                              seconds=round(time.time() - start, 2))

    def _resolve_pending(self, approved: bool, silent: bool = False) -> AgentReply:
        start = time.time()
        p = self.pending
        if p is None:
            return AgentReply(error="There is nothing waiting for confirmation.")
        self.pending = None
        self._trace = []

        if not approved:
            log.info("USER DECLINED: %s", p.description)
            p.parts[p.slot] = self._response_part(p.tool_name, {
                "ok": False, "error": "The user declined. Nothing was changed."})
            self.history.append(types.Content(role="user", parts=p.parts))
            self.history.append(types.Content(role="model", parts=[
                types.Part.from_text(text="Understood. No changes were made.")]))
            return AgentReply(text="Cancelled. No changes were made.",
                              seconds=round(time.time() - start, 2))

        log.info("USER CONFIRMED: %s", p.description)
        write = self._run_tool(p.tool_name, p.args,
                               purpose="confirmed_write", confirmed=True)
        outcome = {"ok": write.get("ok", False), "update_result": write}
        if write.get("ok") and p.tool_name == "update_order_status":
            check = self._run_tool("get_order", {"order_id": p.args["order_id"]},
                                   purpose="verify")
            verified = (check.get("ok")
                        and check["data"]["status"] == p.args["status"])
            outcome["verified_in_database"] = bool(verified)
            outcome["record_after_update"] = check.get("data")
        p.parts[p.slot] = self._response_part(p.tool_name, outcome)
        self.history.append(types.Content(role="user", parts=p.parts))
        return self._loop(list(self.declarations), start)