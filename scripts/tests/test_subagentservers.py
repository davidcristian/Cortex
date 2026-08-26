"""Behaviour of the reader that derives which servers a composed stack starts as subagents.

The set is the deliverable here, so the tests below are mostly about membership: what makes a
service one of these servers, what keeps a service that looks like one out, and which of the two
readings catches which. The last tests run it over the committed compose tree, because a reader
that agreed with its own fixtures and found nothing real would leave the gate above it green over
an empty set.
"""

from pathlib import Path

import pytest

from composestarts import ComposeStartError, Started, read_starts
from subagentservers import dialed, names_a_subagent_model, servers

REPO_ROOT = Path(__file__).resolve().parents[2]

WIRED = """\
services:
  brain:
    environment:
      CORTEX_SUBAGENTS_ENDPOINT: "http://llama-subagent:8082"
      CORTEX_SUBAGENTS_GPU_ENDPOINT: "${CORTEX_SUBAGENTS_GPU_ENDPOINT:-http://llama-subagent:8082}"

  llama-subagent:
    image: "ghcr.io/ggml-org/llama.cpp:server"
    command:
      - "--model"
      - "/models/written-out.gguf"
      - "--jinja"
"""

ROSTERED = """\
services:
  brain:
    environment:
      CORTEX_SUBAGENTS_ROSTER__qwen: >-
        {"endpoint": "http://llama-subagent-qwen:8083",
        "gpu_endpoint": "http://llama-subagent-gpu:9083"}

  llama-subagent-qwen:
    command:
      - "--model"
      - "/models/alternate.gguf"
"""

BY_ARGV = """\
services:
  llama-subagent-third:
    image: "ghcr.io/ggml-org/llama.cpp:server"
    command:
      - "--model"
      - "/models/${CORTEX_MODEL_FILE_SUBAGENT_THIRD:-vendor/third.gguf}"
"""

EMBEDDER = """\
services:
  llama-embed:
    image: "ghcr.io/ggml-org/llama.cpp:server"
    command:
      - "--model"
      - "/models/${CORTEX_EMBED_MODEL_FILE:-nomic/nomic-embed.gguf}"
      - "--embeddings"
"""


def _tree(root: Path, files: dict[str, str]) -> Path:
    """A compose tree written under ``root``, which is how a stack arrives here."""
    (root / "docker").mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (root / "docker" / name).write_text(text, encoding="utf-8")
    return root


def _one(text: str) -> Started:
    """The one service of ``text`` that starts with a command, which is the server under test."""
    found = [started for started in read_starts(text) if started.command is not None]
    assert len(found) == 1, found
    return found[0]


# ── what makes a service one of these servers ──────────────────────────────────


def test_a_server_the_flat_wiring_dials_is_one(tmp_path: Path) -> None:
    """Its own argv writes its model path out, so the wiring is the only thing that finds it."""
    found = servers(_tree(tmp_path, {"docker-compose.subagents.yml": WIRED}))
    assert [server.service for server in found] == ["llama-subagent"]
    assert found[0].file == "docker/docker-compose.subagents.yml"


def test_a_server_a_roster_entry_dials_is_one(tmp_path: Path) -> None:
    """The address sits inside a JSON object folded over two lines, which is the only way to
    write one, and both of that object's endpoints name a server the tier may run on."""
    found = servers(_tree(tmp_path, {"docker-compose.subagents-roster.yml": ROSTERED}))
    assert [server.service for server in found] == ["llama-subagent-qwen"]


def test_a_server_whose_argv_names_a_subagent_model_is_one_with_nobody_dialling_it(
    tmp_path: Path,
) -> None:
    """The reading the wiring cannot make: an override that starts a server and leaves its
    address to the host environment is exactly the fourth server this scan was written for."""
    found = servers(_tree(tmp_path, {"docker-compose.subagents-third.yml": BY_ARGV}))
    assert [server.service for server in found] == ["llama-subagent-third"]


def test_a_server_dialled_from_one_file_and_started_in_another_is_still_one(tmp_path: Path) -> None:
    """A stack is layered, so the file that dials and the file that starts need not be one file."""
    dials = (
        'services:\n  brain:\n    environment:\n      CORTEX_SUBAGENTS_ENDPOINT: "http://far:1"\n'
    )
    starts = 'services:\n  far:\n    command:\n      - "--model"\n      - "/models/far.gguf"\n'
    found = servers(
        _tree(tmp_path, {"docker-compose.a.yml": dials, "docker-compose.b.yml": starts})
    )
    assert [server.service for server in found] == ["far"]


# ── and what keeps a service that looks like one out ───────────────────────────


def test_the_embedder_is_not_a_subagent_server_though_it_runs_the_same_image(
    tmp_path: Path,
) -> None:
    """The image is deliberately not part of the answer: the CPU embedder is started from the
    very same llama.cpp server image and would be asked for a chat template it never uses."""
    stack = {"docker-compose.memory.yml": EMBEDDER, "docker-compose.subagents.yml": WIRED}
    found = servers(_tree(tmp_path, stack))
    assert [server.service for server in found] == ["llama-subagent"]


def test_a_dialled_service_that_declares_no_command_is_not_one(tmp_path: Path) -> None:
    """The supervisor case: the model host starts its subagent tier as a child process, and that
    argv is pinned by the model_manager suite rather than readable from any compose file."""
    supervised = """\
services:
  brain:
    environment:
      CORTEX_SUBAGENTS_GPU_ENDPOINT: "http://model-host:8083"

  model-host:
    image: "cortex-model-host"
"""
    found = servers(_tree(tmp_path, {"docker-compose.gpu.yml": supervised}))
    assert found == ()


PASSTHROUGH = """\
services:
  brain:
    environment:
      CORTEX_SUBAGENTS_ENDPOINT: "${CORTEX_SUBAGENTS_ENDPOINT}"
  s:
    command:
      - "x"
"""


def test_an_endpoint_that_writes_no_address_dials_nothing() -> None:
    """A pure passthrough names the server only in the host environment, which no reader of this
    tree can resolve; it is a legitimate shape rather than one to guess at."""
    assert dialed(read_starts(PASSTHROUGH)[0]) == frozenset()


def test_a_variable_that_only_starts_like_the_subagent_prefix_is_not_a_subagent_model() -> None:
    """`CORTEX_EMBED_MODEL_FILE` and `CORTEX_MODEL_FILE_CORTEX` are the two neighbours, and
    neither begins with the prefix that says a server is serving this tier."""
    cortex = (
        'services:\n  c:\n    command:\n      - "/models/${CORTEX_MODEL_FILE_CORTEX:-x.gguf}"\n'
    )
    assert not names_a_subagent_model(_one(cortex))
    assert not names_a_subagent_model(_one(EMBEDDER))


# ── and what it refuses rather than guesses at ─────────────────────────────────


def test_a_command_spending_a_dollar_form_no_reader_can_name_is_raised() -> None:
    """The substitution reader owns that refusal and this one re-raises it with the service on
    it, since a fault naming only a line number would send a reader to the wrong file."""
    broken = 'services:\n  s:\n    command:\n      - "${"\n'
    with pytest.raises(ComposeStartError, match="the command of 's' cannot be read"):
        names_a_subagent_model(_one(broken))


def test_a_compose_file_that_cannot_be_read_is_named(tmp_path: Path) -> None:
    _tree(tmp_path, {"docker-compose.yml": WIRED})
    (tmp_path / "docker" / "docker-compose.yml").write_bytes(b"\xff\xfe not text")
    with pytest.raises(ComposeStartError, match="cannot read"):
        servers(tmp_path)


# ── the same reader, against the tree it is written for ────────────────────────


def test_the_committed_tree_starts_the_two_subagent_servers_it_ships(tmp_path: Path) -> None:
    """A fixture-only reader could be right about nothing real. The count is asserted loosely,
    since a new override adding a third server should extend this set rather than fail here."""
    found = servers(REPO_ROOT)
    assert {server.service for server in found} >= {"llama-subagent", "llama-subagent-qwen"}
    assert all(server.command for server in found)
    assert not [server for server in found if server.service == "llama-embed"], tmp_path
