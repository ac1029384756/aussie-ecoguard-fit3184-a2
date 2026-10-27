Image2 was published to the existing private Artifact Registry repository and verified, as observed by the operator in official CloudShell at **2026-10-24 00:02:48 UTC**. This is a manually selected record of that observation; it is not the raw helper output or a separate live check.

- Project: `ecoguard-fit3184-a2-2026` (`995070689587`), region `us-central1`.
- Source: `9b16f12872c067163f41de5c3d29d01e78cebbdd`.
- Tag: `c-20261024-2`; immutable image digest: `sha256:0e274acc0dff67b2f233ebd5914235ea328147b8505044de23cfc135217e5c91`.
- One explicit push; remote manifest/config bytes and all ten compressed layer blobs verified. The old image/tag remained available. Client-internal HTTP retries are not counted as separate explicit pushes.
- Terraform state stayed at 13 resources, serial 17, SHA256 `f3b6113be12f34b05701da2e095d0df5763a97d8efdcd6a38a7fdbfc0d1d8fad`; IAM was unchanged.

The retained private publication summary is `image-publication-20261024-4/summary.json`, SHA256 `56d2a11852a53ef5953711d01e976ab384ff4e0c23020c011a5c11ca486e69da`. The repository-after observation has SHA256 `ced1d3f3ff43b75c50dee9f5d00a12d064464f0e5478e6419baa8617358d839a`, with `updateTime` `2026-10-23T23:58:59.146652Z`. Paths are relative to the private CloudShell task directory `~/ecoguard-c-personal-20261023`.

The earlier preflight failure (`Existing private repository differs`) occurred before a push. Its raw-label diagnostic and the original helper remain preserved; the correction accepts only the exact provider attribution label in the live API response while retaining `state.labels = {}`.

This publication changed no runtime configuration and establishes no HTTP, model warmup or cross-cloud acceptance result. The subsequent image-only plan review and apply need their own actual records. No cloud action was performed to create this selection. The companion JSON contains the selected fields, provenance and verification limits.
