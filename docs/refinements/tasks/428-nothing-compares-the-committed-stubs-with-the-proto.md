# Nothing compares the committed stubs with the proto they were generated from

**Status:** done 2026-08-25
**Area:** rpc-transport
**Origin:** [ADR-0003](../../adr/ADR-0003-generated-stubs.md)

Both stacks commit their generated stubs and regenerate them by hand: the Python ones by
`just proto`, the Rust ones by `CORTEX_REGEN_PROTO=1 cargo build -p body-rpc`, which
`body/crates/rpc/build.rs` otherwise does nothing on. A normal build, and every CI run, reads the
committed files and never asks whether they are what `proto/body.proto` produces today. So an edit
to the proto that is not followed by a regeneration leaves two files disagreeing with the source of
truth, with every check passing.

`tonic` copies the proto's comments into the Rust stub word for word, which makes this visible
rather than theoretical: `body/crates/rpc/src/_generated/cortex.seam.v1.rs` contains
`0 means "the body's default" (1600)` exactly as the comment on `max_edge` writes it. That comment
is now a registered place for the body's own default edge and the generated copy is not, generated
code being outside every scan here. Retune the edge and the check names the proto; regenerate and
the stub follows; forget to, and the stub goes on stating the old number in the file a Rust reader
opens.

Two candidate checks. Regenerate into a temporary directory and diff, which means running `protoc`
and `tonic` in CI, the toolchain the committed stubs exist so nobody needs. Or compare only what a
reader reads, the comments, which is a text comparison needing no codegen at all.

## History

- 2026-08-25: opened by the close of
  [R-399](399-the-body-edge-is-two-sites-and-no-prose.md), which registered the proto comment
  stating the body's default edge and could not reach the generated copy of it.
- 2026-08-25: closed, and the two options came out ranked the opposite way round once measured. The
  comment comparison is the one that ships, and regenerate-and-diff is declined on evidence rather
  than on cost. Regenerating the Python stubs is free (`grpcio-tools` is already a brain dev
  dependency and bundles its own `protoc`) and reproduces byte for byte, so the toolchain worry
  this entry recorded does not apply to that half. It was declined because editing the proto
  comment that states the body's default capture edge by one digit and regenerating left all three
  Python files byte identical: the `.pyi` has no comments and the descriptor is stripped of its
  source info, so the check would have seen only structural differences, which pyright and the Rust
  compile already report. The entry's other claim held exactly: the Rust stub does contain that
  sentence word for word, among 338 doc comment lines. So `scripts/stubcheck.py` plus
  `scripts/protocomments.py` require every comment in the proto body to still appear in that stub,
  as a text comparison running no codegen, allowing for the three rewritings prost applies on the
  way into `///`. It passed over 208 proto comments, 177 leading and 31 trailing. Fourteen
  mutations over the check against the real proto and the real stub, all as designed, and fourteen
  mutants over the check's own 54 tests, all killed. The rule is ADR-0003 decision 7. Where a check
  like this may live, and why the Rust regenerate-and-diff does not become a second recipe outside
  `just check`, is answered once in ADR-0067 decision 1. One residue filed, covering the three
  things this check deliberately does not compare, including a doubled service banner the mutation
  table found ([R-434](434-the-stub-check-reads-one-direction-and-one-stub.md)).
