# Evidence 00: Bundle skeleton, schema and raw volume

Captured: 2026-11-20T21:23:14Z · profile `febar` · bundle target `dev`

## databricks bundle validate --strict
```
Name: febar
Target: dev
Workspace:
  Host: https://fevm-classic-stable-zjnu75.cloud.databricks.com
  Path: /Workspace/Users/<user>/.bundle/febar/dev

Validation OK!
```

## databricks bundle deploy (rerun: idempotent)
```
Files: 1 uploaded, 1 deleted
Resources: 0 created, 0 changed, 0 deleted, 2 unchanged
```

## Unity Catalog objects
```
schema classic_stable_zjnu75_catalog.network_migration | comment: FE Bar prototype: acceptance risk control for card migration onto an acquired payment network. Synthetic data only.
volume classic_stable_zjnu75_catalog.network_migration.raw MANAGED | s3://<redacted>
```
