"""Admin-panel LLM provider/model settings -- SPEC.md §14.

Deliberately separate from `llm.py`'s `get_llm()`, which stays env-var-only so its existing
test/hermeticity contract (see that module's own docstring) is unaffected by this feature.
`resolve_active_choice()` is the one function `server.py`'s lifespan and admin endpoint call to
find the settings-store's answer; `get_llm()` is then called with that answer passed explicitly
via its `provider`/`model` kwargs, never by having `get_llm()` reach into this module itself.

`ALLOWED_CHOICES` is a curated allow-list, not a free-text field: `OLLAMA_EVALUATION.md`'s
30-case battery only validated two provider/model combos for this graph's tool-calling path, and
two other tried Ollama models are confirmed *broken* for it (`qwen2.5-coder:7b`'s `tool_calls`
never populate; `llama3.1:8b` -- this repo's own `DEFAULT_OLLAMA_MODEL` -- serializes list-typed
tool args as Python-repr strings). An open text field would let the admin panel silently break
tool-calling with no diagnostic visible in the UI.
"""

from __future__ import annotations

import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class AllowedChoice(BaseModel):
    id: str
    provider: str
    model: str
    label: str


ALLOWED_CHOICES: list[AllowedChoice] = [
    AllowedChoice(
        id="anthropic-sonnet",
        provider="anthropic",
        model="claude-sonnet-5",
        label="Claude Sonnet 5 (Anthropic)",
    ),
    AllowedChoice(
        id="ollama-qwen14b-ctx8k",
        provider="ollama",
        model="qwen2.5:14b-ctx8k",
        label="Qwen 2.5 14B (local, 8k ctx)",
    ),
]

_CHOICES_BY_ID = {choice.id: choice for choice in ALLOWED_CHOICES}
DEFAULT_CHOICE = ALLOWED_CHOICES[0]


def choice_by_id(choice_id: str) -> AllowedChoice | None:
    return _CHOICES_BY_ID.get(choice_id)


class LlmChoice(BaseModel):
    provider: str
    model: str
    updated_at: str


def _default_store_path() -> Path:
    # Outside the repo checkout on purpose -- a config file that shows up in `git status` on
    # the Mac Mini deploy is exactly the kind of drift this store must avoid, mirroring the
    # plist's own out-of-repo posture for machine-local config.
    return Path("~/Library/Application Support/ghg-emissions-agent/llm_choice.json").expanduser()


def _store_path() -> Path:
    override = os.environ.get("AGENT_ADMIN_STORE_PATH")
    return Path(override).expanduser() if override else _default_store_path()


def _find_allowed(provider: str, model: str) -> AllowedChoice | None:
    for choice in ALLOWED_CHOICES:
        if choice.provider == provider and choice.model == model:
            return choice
    return None


def read_stored_choice() -> LlmChoice | None:
    """Returns `None` if the file is missing, unreadable, malformed, or names a
    `(provider, model)` pair no longer on the allow-list -- a hand-edited or stale file must
    never crash startup, just fall through to the next precedence level."""
    path = _store_path()
    try:
        raw = path.read_text()
    except FileNotFoundError:
        return None
    except OSError:
        logger.warning("could not read LLM settings store at %s", path, exc_info=True)
        return None

    try:
        choice = LlmChoice.model_validate_json(raw)
    except ValueError:
        logger.warning("LLM settings store at %s is malformed, ignoring", path)
        return None

    if _find_allowed(choice.provider, choice.model) is None:
        logger.warning(
            "LLM settings store at %s names %s/%s, which is no longer on the allow-list -- ignoring",
            path,
            choice.provider,
            choice.model,
        )
        return None

    return choice


def write_stored_choice(choice: LlmChoice) -> None:
    """Atomic write (tempfile + os.replace) so a crash mid-write never corrupts the file for
    the next boot."""
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # NamedTemporaryFile (not mkstemp + os.fdopen) so the file object -- and its underlying fd
    # -- is always closed via the `with` block, even if writing itself raises.
    with tempfile.NamedTemporaryFile(
        mode="w", dir=path.parent, prefix=".llm_choice-", suffix=".tmp", delete=False
    ) as f:
        tmp_name = f.name
        f.write(choice.model_dump_json())
    try:
        os.replace(tmp_name, path)
    finally:
        Path(tmp_name).unlink(missing_ok=True)


def _from_env() -> AllowedChoice | None:
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    if provider == "ollama":
        model = os.environ.get("LOCAL_LLM_MODEL", "llama3.1:8b")
    else:
        model = os.environ.get("AGENT_LLM_MODEL", "claude-sonnet-5")
    return _find_allowed(provider, model)


def resolve_active_choice() -> AllowedChoice:
    """Precedence: stored file (if present and still allow-listed) -> env vars (llm.py's
    pre-admin-panel behavior) -> code default (Sonnet)."""
    stored = read_stored_choice()
    if stored is not None:
        allowed = _find_allowed(stored.provider, stored.model)
        if allowed is not None:
            return allowed

    from_env = _from_env()
    if from_env is not None:
        return from_env

    return DEFAULT_CHOICE


def now_iso() -> str:
    return datetime.now(UTC).isoformat()
