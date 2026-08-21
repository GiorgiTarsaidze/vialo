# Kiro evidence

Machine-verifiable artifacts for the claims in [`KIRO.md`](../../KIRO.md), `README.md`, and
`DEVLOG.md`. Everything here was produced by running a command in this repository and can be
regenerated. Nothing is reconstructed after the fact, and nothing is a mock-up.

**What this folder is, precisely.** One file, `hook-runs.txt`, is evidence of the Kiro workflow
itself. Everything else is verification of the product those workflows produced: security,
reproducibility, performance, and live deployment. Both belong next to the Kiro story, because a
workflow claim is only worth as much as the thing it built, but they are different kinds of evidence
and the folder name flattens them. The Kiro workflow itself is evidenced by the committed
[`.kiro/`](../../.kiro/) tree and the commit ordering described in [`KIRO.md`](../../KIRO.md).

`docs/kiro-evidence/raw/` is gitignored so that any oversized capture can be kept locally without
reaching the repository. It is currently empty; nothing here needed it.

| File | What it proves | How to regenerate |
|---|---|---|
| `hook-runs.txt` | The three Kiro hooks wired into `.kiro/agents/*.json` execute and pass, and both agent configs validate. | `.kiro/hooks/validate-repository.sh`, `.kiro/hooks/validate-frontend.sh`, `.kiro/hooks/validate-backend.sh`, `kiro-cli agent validate --path .kiro/agents/<name>.json` |
| `secret-scan.txt` | No credential anywhere in the commit history, across all 19 commits. Three matches are reported and every one is a deliberate test vector, decoded in full in the transcript rather than suppressed with an ignore file. A second working-tree run is the positive control: it finds far more, all in gitignored paths, proving the scanner does detect real keys. | `docker run --rm -v "$PWD:/repo" zricethezav/gitleaks:latest detect --source=/repo --redact` |
| `fresh-clone.txt` | The Phase 4 clean-machine gate: a fresh clone of the public remote passes every README command, including contract-drift and ARM64 layer checks. | `git clone https://github.com/GiorgiTarsaidze/vialo.git` then follow `README.md` → Local validation |
| `scope-guard-battery.txt` / `.json` | 33 adversarial and legitimate prompts against the deployed scope guard, with zero provider spend, plus the prompt length cap. | `uv run --project backend python scripts/scope_guard_battery.py` |
| `scope-guard-deployed.txt` | The same guard behaviour on the live API, returning typed `OFF_TOPIC` / `INVALID_INPUT` before any paid call. | `curl -X POST https://vialo.place/api/itineraries -d '{"prompt":"..."}'` |
| `solver-benchmark/*.json` | The exact solver's 8!/9! latency on a real 512 MB, 1024 MB, and 1769 MB ARM64 Lambda, plus a local host baseline. This closed spec task 13 and drove the memory decision. | `uv run --project backend python scripts/solver_benchmark.py --stops 8 9 --repeats 5`, and `scripts/solver_benchmark.py` deployed as a throwaway Lambda handler |
| `live-production-run.txt` | A genuinely computed 7-stop Naples itinerary on the deployed stack, with real metrics, unverified-hours disclosure, a dropped-stop reason, and no horizontal overflow at 390 px. | Playwright MCP against `https://vialo.place` |
| `live-result-*.png` | The deployed application returning a genuinely computed itinerary at the reviewed viewports, captured 2026-08-20. **The interface was revised on 2026-08-20 and 2026-08-21**, so these show the itinerary surfaces as they were, not as they are: the dropped-stop section has since become a neutral "Also worth seeing" list and the header was rebuilt. The computed result they show is real and unchanged in substance. For current appearance, open the live site. | Playwright MCP against `https://vialo.place` |
| `journal-verification.txt` | The deployed Journal: anonymous reads work, every write path refuses unauthenticated and forged callers (including an `alg=none` JWT with a real audience), the media bucket is unreachable except through CloudFront, SPA routes resolve, the CSP was widened by exactly the Cognito entries the flow needs, and the corrected Privacy and Terms copy is in the shipped bundle. Also pins the hidden-story comment-leak regression. | `bash docs/kiro-evidence/regenerate-journal-verification.sh` |

## What is deliberately not here

No screen recordings of Kiro generating steering files or executing spec waves. Those were not
captured while they happened, and staging them afterwards would be a reconstruction pretending to
be a capture. The Kiro workflow is instead evidenced by artifacts a reviewer can inspect and
re-run: the committed `.kiro/` tree, the spec whose tasks map one-to-one onto the shipped modules,
the hook transcripts above, and the corrections recorded in `DEVLOG.md` with the commit that
resolved each one.
