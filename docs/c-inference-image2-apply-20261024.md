The image-only Cloud Run apply and configuration verification passed at **2026-10-24 00:23:15.752203 UTC**, according to actual official CloudShell terminal output. This is a manually selected evidence record, not the raw helper output or an independent live check.

- One saved-plan apply exited `0`: **1 update, 12 no-ops, 0 creates/deletes**, leaving 13 managed resources.
- Source: `9b16f12872c067163f41de5c3d29d01e78cebbdd`; image digest: `sha256:0e274acc0dff67b2f233ebd5914235ea328147b8505044de23cfc135217e5c91`.
- Ready revision: `ecoguard-inference-00002-vmh`; service URL remained `https://ecoguard-inference-adlnb7yumq-uc.a.run.app`.
- State serial advanced `17 → 19`, with the same lineage (selected prefix `b35a`). Post-state SHA256: `dbe309c8b3813639f920e82d01354220d5c555a5d4b39c34da888a61ee0cd61e`.
- Full IAM, enabled APIs and capacity were unchanged. The apply helper made no HTTP/model/AWS calls.

The retained apply summary has SHA256 `cfe213b3c0e4ecbaaea30e9c992eb4b23b0fca1fc5f190cd6bd8b2c433ed6e47`; its post-verification detail has SHA256 `e69505968925265a0835c3c952a6d1589d1ae3881859c5a82bd7ca184db3dedf`. Both remain in the original plan's private `apply-20261024-1` directory. The companion JSON pins the saved binary, frozen apply/review helpers and publication record.

The original blocked plan review remains preserved. A separate read-only review accepted only the eight observed null-to-empty defaults on deep copies, retaining the full image-only gate and its computed-value restrictions. A separate truthful standing-task record bound this apply to the user's existing finish-C/default-consent direction and A$0 additional-spend limit; it claimed no new human approval and reused no historical four-create-plan approval.

The later [HTTP repair batch](c-private-http-repair-20261024.md) returned403 for anonymous health,200 for authenticated health and401 for warmup. This apply record verifies configuration/Ready status only; model and cross-cloud acceptance remain unfinished.
