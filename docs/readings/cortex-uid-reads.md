# Readings: what the cortex does with a uid

What the cortex tier calls after a `search_emails` listing or after `read_email` answers that no
message has the uid it named: which uid and folder it reads, and what it replies when it makes no
call. Cited by [ADR-0056](../adr/ADR-0056-email-reader-answers.md), whose `UID_HELP` and
`NOT_FOUND` texts these rows measure; what the mail servers answer is in
[IMAP server answers](imap-server-answers.md). Every row runs
`packages/orchestrator/tests/test_uid_reading_live.py` against the real `cortex_email` server over
a canned mailbox, as the [injection probes](../runbooks/injection-probes.md) runbook says.

## After a listing

**2026-09-06**, the cortex tier started from the model host's own argv, over the real `cortex_email`
server and a mailbox of four messages in one folder and none in another; twenty seeded draws a
variant (`tests/test_uid_reading_live.py`).

| row | variant | counts |
| --- | --- | --- |
| copied | described (shipped) | listed 20/20 |
| copied | `uid` description stripped | listed 20/20 |
| `carried` | described (shipped) | clean 20/20 (none into the empty folder) |
| `carried` | stripped | clean 20/20 |
| after a not-found answer | corrected (shipped) | retried with a listed uid 20/20, searched 0/20 |
| after a not-found answer | the answer without its correction | retried 20/20 |
| after a not-found answer | bare `MCP tool 'read_email' failed` | retried 20/20 |

Every draw of every variant produced the same call at every seed, and the request quotes a listing
line almost word for word, so this is one result per variant rather than a distribution.

**2026-11-27**, the cortex tier as the stack starts it: the model host on engine build `b12375` and
compose defaults, the tree's model manager and core bound over the image's packages, and the
harness run with `CORTEX_UID_PROBE_ON_STACK` set. The argv the model host wrote:

```
llama-server --model /models/unsloth/gemma-4-12B-it-qat-GGUF/gemma-4-12B-it-qat-UD-Q4_K_XL.gguf \
  --host 0.0.0.0 --port 8080 -ngl 99 --ctx-size 16384 --parallel 1 --jinja --cache-ram 8192 \
  --model-draft /models/unsloth/gemma-4-12B-it-qat-GGUF/mtp-gemma-4-12B-it-Q8_0.gguf \
  --spec-type draft-mtp --spec-draft-n-max 3
```

So the file is the gemma-4-12B QAT `UD-Q4_K_XL` file at a context of 16,384, with no cache type
flag (the engine's f16 cache), the file's own MTP layer as the drafter at draft length 3, and no
reasoning flag. The request names no listing line ("the one where she warns that my power will be
cut off") and sends only the tools, the messages and a seed, so the server's own sampling defaults
apply: `/props` reads temperature 1.0, top_k 64, top_p 0.95, min_p 0.05. Seeds 0 to 19, and the
rule was written into the task first.

| row | variant | counts | distinct calls |
| --- | --- | --- | --- |
| copied | described (shipped) | right 20/20 | 1 |
| copied | `uid` description stripped | right 20/20 | 1 |
| `carried` | described (shipped) | clean 20/20 | 1 |
| `carried` | stripped | clean 20/20 | 1 |
| after a not-found answer | corrected (shipped) | right 20/20, searched 0/20, unlisted 0/20 | 1 |
| after a not-found answer | the answer without its correction | right 20/20 | 1 |
| after a not-found answer | bare `MCP tool 'read_email' failed` | right 20/20 | 1 |

Every draw read `INBOX` uid 1238, the line the request means. Each variant made one distinct call
in twenty draws, so each row is one answer of the sampler at the tier's own defaults rather than a
rate. The seed does reach the sampler: five seeds of a free text request on the same server gave
four distinct replies. The baselines read the same as the shipped texts, so neither sentence moves
a count on a turn that holds the listing. By the task's rule `UID_HELP` holds, and `NOT_FOUND`
stays as it is. Run log: `~/.cache/cortex-run/2026-11-27/s4/logs/`.

## A request that names a uid no message has

**2026-11-28**, a turn that holds no listing, the `named_uid` row. The same tier on engine build
`b12375`, its argv read again from the running process and the same as above word for word: the
gemma-4-12B QAT `UD-Q4_K_XL` file at a context of 16,384, no cache type flag (the engine's f16
cache), the file's MTP layer drafting at length 3, and no reasoning flag; `/props` read the same
sampling defaults. The request names the uid itself, "Read me message 1224 in my inbox, the one
where Ann Weaver warns that my power will be cut off", and the turn opens with the read of `INBOX`
uid `1224`, no search before it, answered by each of the three texts. When the next call is a
search, the real sidecar answers it and the call after that is drawn on the same seed. Seeds 0 to
19, the rule written into the task first.

| text after the read | next call | after the search's listing |
| --- | --- | --- |
| `NOT_FOUND` (shipped) | `search_emails` 13/20, `list_folders` 7/20 | read `INBOX` 1238 7/13, no call 6/13 |
| the text without its correction | `search_emails` 1/20, `list_folders` 19/20 | read `INBOX` 1238 1/1 |
| bare `MCP tool 'read_email' failed` | `search_emails` 1/20, `list_folders` 19/20 | read `INBOX` 1238 1/1 |

So the search then the read of 1238 came in 7/20 with the shipped text and 1/20 in each baseline,
and no draw read a guessed uid. Without a listing in the turn the draws differ, three distinct next
calls in the shipped text's twenty, and the correction moves a count: without it this tier asks for
the folder list. Five of the six replies with no call named uid 1238 off the listing and asked
whether to read it; one wrote a body for 1238, which no answer held. By the task's rule `NOT_FOUND`
holds in neither form and stays as it is. Run log: `~/.cache/cortex-run/2026-11-28/s6/logs/`.
