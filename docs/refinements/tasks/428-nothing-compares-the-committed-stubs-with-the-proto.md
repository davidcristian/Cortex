# Nothing compares the committed seam stubs with the proto they were generated from

**Status:** open, actionable
**Area:** seam-transport
**Origin:** [ADR-0003](../../adr/ADR-0003-seam-codegen.md)

Opened 2026-08-25 by the close of
[R-399](399-the-body-edge-is-two-sites-and-no-prose.md), which tied a value spelled in the proto's
own comments and could not reach the generated copy of it.

Both stacks commit their stubs and regenerate them by hand: the Python ones by `just proto`, the
Rust ones by `CORTEX_REGEN_PROTO=1 cargo build -p body-rpc`, which `body/crates/rpc/build.rs`
otherwise does nothing on. A normal build, and every CI run, reads the committed files and never
asks whether they are what `proto/body.proto` produces today. So an edit to the proto that is not
followed by a regeneration leaves two files disagreeing with the source of truth, with every gate
green.

`tonic` copies the proto's comments into the Rust stub verbatim, which makes this visible rather
than theoretical: `body/crates/rpc/src/_generated/cortex.seam.v1.rs` carries `0 means "the body's
default" (1600)` word for word from the comment on `max_edge`. That comment is now a registered far
side of the body's own default edge and the generated copy is not, generated code being outside
every scan here. Retune the edge and the gate names the proto; regenerate and the stub follows;
forget to, and the stub goes on stating the old number in the file a Rust reader actually opens.

**Why it was left.** It is a question about the codegen contract rather than about any value, and
the answer is a CI job rather than a registry row. It also has a real cost the committed-stub
decision was made to avoid: checking would mean running `protoc` and `tonic` in CI, which is the
toolchain the committed stubs exist so nobody needs, and pinning their versions closely enough that
a codegen release does not redden the gate on a diff nobody wrote.

**What would close it.** Decide whether the check is worth its toolchain. The narrow version is a
job that regenerates into a temporary directory and diffs, pinned to the exact `protoc`,
`grpcio-tools` and `tonic-prost-build` the last regeneration used, run on changes to
`proto/body.proto` alone rather than on every commit. The narrower one is to hold only what a
reader reads, the comments, which is a text comparison needing no codegen at all: every comment
line in the proto should appear in the Rust stub. Decide also whether a stale stub is worth
catching at all given that a wrong stub usually fails to compile against the code that uses it,
which is the argument that the only silent case is exactly this one, a comment.

## Trail

- 2026-08-25: opened by the close of
  [R-399](399-the-body-edge-is-two-sites-and-no-prose.md), which registered the proto comment
  stating the body's default edge and left the generated copy of that comment unreachable.
