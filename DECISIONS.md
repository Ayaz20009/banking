# Decisions

> [YOUR WORDS] Drafted by AI from your choices. Rewrite each entry in your own words.

## 2026-11-20 — Unity Catalog naming
- **Decision:** use `febar.network_migration` instead of the originally proposed schema, which named the customer and the network.
- **Options considered:** (A) keep the customer-named schema; (B) neutral `febar.network_migration`; (C) existing sandbox catalog with a neutral schema.
- **Why:** [YOUR WORDS] The original names contain the customer's name and the acquired network's name, which breaks the FE Bar no-names rule.

## 2026-11-20 — Workspace and CLI profile
- **Decision:** workspace `fevm-classic-stable-zjnu75`, CLI profile `febar`.
- **Why:** [YOUR WORDS]

## 2026-11-20 — Catalog location (supersedes the `febar` catalog)
- **Decision:** use `classic_stable_zjnu75_catalog.network_migration`.
- **Options considered:** (A) the workspace default catalog; (B) request CREATE_CATALOG for `febar`; (C) default now, migrate later.
- **Why:** [YOUR WORDS] No CREATE_CATALOG on the metastore. You already have ALL_PRIVILEGES and MANAGE on the default catalog, so nothing blocks the build. The catalog stays a bundle variable.
