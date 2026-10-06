# A subagent server named under another family word is checked only when compose dials it

**Status:** open, waiting for its trigger
**Area:** repo-checks
**Trigger:** a compose service names its model under a `CORTEX_MODEL_FILE_` variable that neither
begins `CORTEX_MODEL_FILE_SUBAGENT` nor is the embedder's `CORTEX_MODEL_FILE_EMBED`. Countable by
listing `artifactnames.composed` over the tree, which today returns those three: `EMBED`,
`SUBAGENT` and `SUBAGENT_QWEN`
**Origin:** [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md)
**Verified:** 2026-10-07

`subagentservers.py` counts a compose service as a subagent server when a compose file writes an
address that dials it (`CORTEX_SUBAGENTS_ENDPOINT`, `CORTEX_SUBAGENTS_GPU_ENDPOINT` or a
`CORTEX_SUBAGENTS_ROSTER__<name>` entry), or when its argv names its model under
`CORTEX_MODEL_FILE_SUBAGENT` (`MODEL_PREFIX`). The naming rule asks only that the variable begin
`CORTEX_MODEL_FILE_` (`FAMILY_PREFIX`). So a server that serves subagents, names its model
`CORTEX_MODEL_FILE_HELPER`, and is dialed by an address no compose file writes, such as a bare
`CORTEX_SUBAGENTS_ENDPOINT:` key passed through from the host or a roster entry set in a `.env`,
passes the naming rule and is outside the flag rule. It can then start without `--jinja` or the
reasoning-off pair, and nothing reports it.

Today both compose subagent servers pass both tests: `docker-compose.subagents.yml` writes
`http://llama-subagent:8082` and the roster file writes `http://llama-subagent-qwen:8083`, and both
servers name their model under `CORTEX_MODEL_FILE_SUBAGENT`. Two fixes, cheapest first: keep the
words a family variable may use after the prefix in one list that says which of them are
subagents, so a new word is a diff to that list; or count as a subagent server every compose
service naming a family artifact whose argv does not declare `--embeddings`.

## History

- 2026-10-02: opened because [ADR-0043](../../adr/ADR-0043-subagent-server-flags.md) listed this
  case as recorded in the backlog when no task file named it. Found while declining
  [R-521](521-a-settings-method-reading-the-mount-for-anything-but-a-path-is-refused.md).
