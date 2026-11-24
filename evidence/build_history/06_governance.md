# Evidence 06: Unity Catalog governance

Namespace `classic_stable_zjnu75_catalog.network_migration`. Captured 2026-11-21 (UTC).
- **Source:** `src/governance/governance.sql` (job task `setup_governance`), `src/governance/governance_tags.sql` (job task `apply_tags`), and the policy clauses in `src/pipeline/04_gold.sql`.
- **Test scripts:** `tools/persona_check.py`, `tools/access_test.py`.

## Model

- **Entitlements are data.** `personas` defines what each persona may see; `entitlements` records who holds which persona (user, service principal or account group). Changing access means changing a row, and no identity appears in any function. The job owner's own row is created with `current_user()` at run time.
- **Policies sit only on the tables people, Genie and the App query:** `gold_auth_daily`, `gold_auth_hourly`, `gold_baseline_gap` and `auth_detail`.
  - They are never on bronze or silver, which the pipeline reads, so policies cannot change what the pipeline computes.
  - Pipeline-owned tables take them through `WITH ROW FILTER` / `MASK` in the table definition.
- **Policy functions run with the table owner's authority,** so readers need no access to `personas` or `entitlements`. The service principal test confirms this: it was denied a direct read of `entitlements`.

### Personas (`personas` table)

| Persona | Role | Issuer scope | Region scope | Sensitive (card_ref) |
|---|---|---|---|---|
| ADMIN | Platform owner (pipelines, jobs) | ALL | ALL | yes |
| P1_DIRECTOR | Director of Payment Network Operations | OWN | ALL | no |
| P2_REGIONAL | Regional ops analyst (Southeast) | OWN | SE | no |
| P3_CARD_INV | Card investigations specialist (cleared) | OWN | ALL | yes |
| P4_PARTNER | Network partner operations | THIRD_PARTY | ALL | no |

### Policy definitions

```sql
CREATE OR REPLACE FUNCTION f_row_filter(p_issuer_segment STRING, p_region STRING)
RETURNS BOOLEAN
COMMENT 'Row filter: TRUE when the caller (user, or a member of an entitled account group) holds a persona whose issuer and region scope cover this row. No entitlement = no rows.'
RETURN EXISTS (
  SELECT 1
  FROM classic_stable_zjnu75_catalog.network_migration.entitlements e
  JOIN classic_stable_zjnu75_catalog.network_migration.personas p ON p.persona = e.persona
  WHERE (e.principal = current_user() OR (e.principal_type = 'GROUP' AND is_account_group_member(e.principal)))
    AND (p.issuer_scope = 'ALL' OR p.issuer_scope = p_issuer_segment)
    AND (p.region_scope = 'ALL' OR p.region_scope = p_region)
);

CREATE OR REPLACE FUNCTION f_mask_card(card_ref STRING)
RETURNS STRING
COMMENT 'Column mask for card_ref: clear value only for personas with can_see_sensitive = TRUE; otherwise RESTRICTED.'
RETURN CASE
  WHEN EXISTS (
    SELECT 1
    FROM classic_stable_zjnu75_catalog.network_migration.entitlements e
    JOIN classic_stable_zjnu75_catalog.network_migration.personas p ON p.persona = e.persona
    WHERE (e.principal = current_user() OR (e.principal_type = 'GROUP' AND is_account_group_member(e.principal)))
      AND p.can_see_sensitive
  ) THEN card_ref
  ELSE 'RESTRICTED'
END;
```

### Where the policies are attached (`information_schema`)

| table_name | filter_name | target_columns |
|---|---|---|
| auth_detail | classic_stable_zjnu75_catalog.network_migration.f_row_filter | issuer_segment, region |
| gold_auth_daily | classic_stable_zjnu75_catalog.network_migration.f_row_filter | issuer_segment, region |
| gold_auth_hourly | classic_stable_zjnu75_catalog.network_migration.f_row_filter | issuer_segment, region |
| gold_baseline_gap | classic_stable_zjnu75_catalog.network_migration.f_row_filter | issuer_segment, region |

| table_name | column_name | mask_name |
|---|---|---|
| auth_detail | card_ref | classic_stable_zjnu75_catalog.network_migration.f_mask_card |

### Tags

| lvl | obj | tag_name | tag_value |
|---|---|---|---|
| table | personas | nm_data_class | access_control |
| table | entitlements | nm_data_class | access_control |
| column | auth_detail.card_ref | nm_sensitivity | restricted |
| schema | network_migration | nm_domain | payment_network_migration |
| schema | network_migration | nm_origin | synthetic |

The tables in `governance_tags.sql` carry `nm_layer`, `nm_data_class` and `nm_policy` tags; the `information_schema` listing above was taken before that task ran.

Tag keys are namespaced (`nm_*`). This shared metastore enforces governed tag policies on generic keys such as `data_domain` and `data_class`, whose allowed values belong to other teams. The first attempt failed with `UC_TAG_POLICY_VALUE_NOT_ALLOWED` (see BUILD_LOG).

**Not tested:** the `principal_type = 'GROUP'` branch. This workspace login cannot create account groups (that needs account admin), so every entitlement is held by a user or service principal and grants go to principals directly. With account groups, access becomes one `entitlements` row per group.

## Persona results: the same query, my entitlement row switched to each persona

The query sums `gold_auth_daily.attempts` by issuer segment, lists the regions visible, counts `auth_detail` rows, and samples one `card_ref`:

| persona | attempts_visible | own_attempts | third_party_attempts | regions_visible | detail_rows | card_ref_sample |
|---|---|---|---|---|---|---|
| P1_DIRECTOR | 9845175 | 9845175 |  | INTL,MW,NE,SE,SW,W | 1549375 | RESTRICTED |
| P2_REGIONAL | 2420664 | 2420664 |  | SE | 381355 | RESTRICTED |
| P3_CARD_INV | 9845175 | 9845175 |  | INTL,MW,NE,SE,SW,W | 1549375 | CR60779996 |
| P4_PARTNER | 1088686 |  | 1088686 | INTL,MW,NE,SE,SW,W | 172554 | RESTRICTED |
| (no entitlement) |  |  |  |  | 0 |  |
| ADMIN | 10933861 | 9845175 | 1088686 | INTL,MW,NE,SE,SW,W | 1721929 | CR60779996 |

- P1 + P4 = ADMIN (9,845,175 + 1,088,686 = 10,933,861). The two issuer scopes partition the data with no overlap and no gaps.
- With no entitlement the caller sees **0 rows**.
- After the test the row was restored to ADMIN (verified).

## Non-admin test: service principal `febar-access-test`

- **Identity:** application ID `bbcf4a20-bd3b-4db3-8938-1c93a8232c52`, OAuth M2M; the secret is stored only in a local CLI profile and was never printed or committed.
- **Persona:** entitled as **P2_REGIONAL** for the test.
- **Recording rule:** each step shows the identity, status, error class and response size. Protected reads record **status and size only**.

| # | Step | Identity | Result | Error class | Response bytes | Matches expectation |
|---|---|---|---|---|---|---|
| 1 | (admin) CREATE TABLE IF NOT EXISTS classic_stable_zjnu75_catalog.network_migration.zz_ac | admin | SUCCEEDED |  | 617 | ✓ |
| 2 | (admin) DELETE | admin | SUCCEEDED |  | 702 | ✓ |
| 3 | (admin) INSERT INTO classic_stable_zjnu75_catalog.network_migration.entitlements VALUES  | admin | SUCCEEDED |  | 863 | ✓ |
| 4 | 0. identity seen by UC | service principal | SUCCEEDED |  | 1052 |  |
| 5 | 1a. BEFORE grant: read approved table gold_auth_daily | service principal | FAILED | INSUFFICIENT_PERMISSIONS | 373 | ✓ |
| 6 | 1b. BEFORE grant: read harmless probe zz_access_probe | service principal | FAILED | INSUFFICIENT_PERMISSIONS | 373 | ✓ |
| 7 | (admin) GRANT USE CATALOG ON CATALOG classic_stable_zjnu75_catalog | admin | SUCCEEDED |  | 294 | ✓ |
| 8 | (admin) GRANT USE SCHEMA ON SCHEMA classic_stable_zjnu75_catalog.network_migration | admin | SUCCEEDED |  | 294 | ✓ |
| 9 | (admin) GRANT SELECT ON TABLE classic_stable_zjnu75_catalog.network_migration.gold_auth_ | admin | SUCCEEDED |  | 294 | ✓ |
| 10 | (admin) GRANT SELECT ON TABLE classic_stable_zjnu75_catalog.network_migration.auth_detai | admin | SUCCEEDED |  | 294 | ✓ |
| 11 | (admin) GRANT SELECT ON TABLE classic_stable_zjnu75_catalog.network_migration.zz_access_ | admin | SUCCEEDED |  | 294 | ✓ |
| 12 | 3a. AFTER grant: probe readable (so 1b failed only for lack of permission) | service principal | SUCCEEDED |  | 849 | ✓ |
| 13 | 3b. governed read: attempts by issuer segment x region (expect OWN + SE only) | service principal | SUCCEEDED |  | 1014 | ✓ |
| 14 | 3c. masked column: card_ref in auth_detail (expect RESTRICTED) | service principal | SUCCEEDED |  | 857 | ✓ |
| 15 | 3d. join on the masked column (all values collapse to RESTRICTED, so cards cannot be linked) | service principal | SUCCEEDED |  | 871 | ✓ |
| 16 | 3e. column statistics for the masked column (DESCRIBE ... card_ref): is min/max exposed? | service principal | SUCCEEDED |  | 1450 | ✓ |
| 17 | 4. PROTECTED read silver_auth (not granted) | service principal | FAILED | INSUFFICIENT_PERMISSIONS | 396 | ✓ |
| 18 | 4. PROTECTED read bronze_issuer_auth (not granted) | service principal | FAILED | INSUFFICIENT_PERMISSIONS | 403 | ✓ |
| 19 | 4. PROTECTED read quarantine_auth (not granted) | service principal | FAILED | INSUFFICIENT_PERMISSIONS | 400 | ✓ |
| 20 | 4. PROTECTED read entitlements (not granted) | service principal | FAILED | INSUFFICIENT_PERMISSIONS | 397 | ✓ |
| 21 | 4. PROTECTED read gold_baseline_gap (not granted) | service principal | FAILED | INSUFFICIENT_PERMISSIONS | 402 | ✓ |
| 22 | 4f. metadata: table names visible via inherited READ_METADATA (account users) | service principal | SUCCEEDED |  | 699 |  |
| 23 | (admin) REVOKE SELECT ON TABLE classic_stable_zjnu75_catalog.network_migration.zz_access | admin | SUCCEEDED |  | 294 | ✓ |
| 24 | (admin) REVOKE SELECT ON TABLE classic_stable_zjnu75_catalog.network_migration.auth_deta | admin | SUCCEEDED |  | 294 | ✓ |
| 25 | (admin) REVOKE SELECT ON TABLE classic_stable_zjnu75_catalog.network_migration.gold_auth | admin | SUCCEEDED |  | 294 | ✓ |
| 26 | (admin) REVOKE USE SCHEMA ON SCHEMA classic_stable_zjnu75_catalog.network_migration | admin | SUCCEEDED |  | 294 | ✓ |
| 27 | (admin) REVOKE USE CATALOG ON CATALOG classic_stable_zjnu75_catalog | admin | SUCCEEDED |  | 294 | ✓ |
| 28 | (admin) DELETE | admin | SUCCEEDED |  | 702 | ✓ |
| 29 | 6a. AFTER revoke: read gold_auth_daily again | service principal | FAILED | INSUFFICIENT_PERMISSIONS | 373 | ✓ |
| 30 | 6b. AFTER revoke: read probe again | service principal | FAILED | INSUFFICIENT_PERMISSIONS | 373 | ✓ |

**Read results (governed, allowed):**

**0. identity seen by UC**

```sql
SELECT current_user() AS me, is_account_group_member('account users') AS in_account_users, is_account_group_member('admins') AS in_admins
```

| me | in_account_users | in_admins |
|---|---|---|
| bbcf4a20-bd3b-4db3-8938-1c93a8232c52 | true | false |

**3a. AFTER grant: probe readable (so 1b failed only for lack of permission)**

```sql
SELECT * FROM classic_stable_zjnu75_catalog.network_migration.zz_access_probe
```

| probe_value | note |
|---|---|
| 1 | harmless |

**3b. governed read: attempts by issuer segment x region (expect OWN + SE only)**

```sql
SELECT issuer_segment, region, sum(attempts) AS attempts FROM classic_stable_zjnu75_catalog.network_migration.gold_auth_daily GROUP BY ALL ORDER BY 1, 2
```

| issuer_segment | region | attempts |
|---|---|---|
| OWN | SE | 2420664 |

**3c. masked column: card_ref in auth_detail (expect RESTRICTED)**

```sql
SELECT card_ref, count(*) AS rows FROM classic_stable_zjnu75_catalog.network_migration.auth_detail GROUP BY 1 ORDER BY 2 DESC LIMIT 3
```

| card_ref | rows |
|---|---|
| RESTRICTED | 381355 |

**3d. join on the masked column (all values collapse to RESTRICTED, so cards cannot be linked)**

```sql
SELECT count(*) AS joined_pairs, count(DISTINCT a.card_ref) AS distinct_card_ref_values FROM classic_stable_zjnu75_catalog.network_migration.auth_detail a JOIN classic_stable_zjnu75_catalog.network_migration.auth_detail b ON a.card_ref = b.card_ref WHERE a.business_date = '2026-11-14' AND b.business_date = '2026-11-14' AND a.acquirer_id = 'ACQ-001' AND b.acquirer_id = 'ACQ-001'
```

| joined_pairs | distinct_card_ref_values |
|---|---|
| 1183744 | 1 |

**3e. column statistics for the masked column (DESCRIBE ... card_ref): is min/max exposed?**: statistics rows returned = ['distinct_count', 'max', 'min', 'num_nulls']; min/max values present = False

**4f. metadata: table names visible via inherited READ_METADATA (account users)**

```sql
SELECT count(*) AS tables_listed FROM classic_stable_zjnu75_catalog.information_schema.tables WHERE table_schema = 'network_migration'
```

| tables_listed |
|---|
| 53 |

### Reading the denials

Before any grant, the approved table and the harmless probe table `zz_access_probe` failed identically (`INSUFFICIENT_PERMISSIONS`, 373 bytes). Once SELECT was granted on the probe, it became readable (step 12). So the earlier failure was a **permission denial, not a missing object**. The protected tables (`silver_auth`, `bronze_issuer_auth`, `quarantine_auth`, `entitlements`, `gold_baseline_gap`) returned the same error class and were never granted.

### Effective permissions after clean-up (including inheritance and groups)

| Securable | Effective privileges for the SP (incl. inherited / via groups) |
|---|---|
| catalog `classic_stable_zjnu75_catalog` | READ_METADATA (from metastore_aws_us_east_1) |
| schema `network_migration` | READ_METADATA (from metastore_aws_us_east_1) |
| table `network_migration.gold_auth_daily` | READ_METADATA (from metastore_aws_us_east_1) |
| table `network_migration.auth_detail` | READ_METADATA (from metastore_aws_us_east_1) |
| table `network_migration.silver_auth` | READ_METADATA (from metastore_aws_us_east_1) |
| table `network_migration.entitlements` | READ_METADATA (from metastore_aws_us_east_1) |

Groups the SP belongs to (workspace view):
no direct groups (implicit: account users)

The only remaining privilege is metastore-wide `READ_METADATA`, inherited by every account user. No grant reaches the data, directly or through a group.

## What the platform reveals anyway (checked)

| Channel | What a non-entitled identity can see | Mitigation |
|---|---|---|
| **Metadata** (inherited `READ_METADATA` via `account users`) | Table and column names, comments and tags of all 53 objects in the schema (step 22) | Comments and tags never contain data values. Comments describe meaning only. |
| **Column statistics** on the masked `card_ref` | `DESCRIBE … card_ref` returns min/max/distinct-count rows with **no values** (step 16) | None needed. Re-check if `ANALYZE TABLE … COMPUTE STATISTICS FOR COLUMNS` is ever run. |
| **Joins on a masked column** | Masked values collapse to one constant `RESTRICTED`, so joining on them links nothing (1,183,744 pairs, 1 distinct value, step 15) | By design. Investigators who need linkage hold P3. |
| **Lineage** (`system.access.table_lineage`) | Table-to-table edges only, no values; system tables are not granted to personas | Admin-only |
| **Error messages** | Denials name the missing privilege and the object, not data | Logged as status + size only |

## Lineage for the main tables (`system.access.table_lineage`)

| source | target | lineage_events | last_seen |
|---|---|---|---|
| silver_auth | gold_auth_daily | 1 | 2026-11-21T04:09:31.564Z |
| ref_recovery_assumptions | gold_baseline_gap | 4 | 2026-11-21T04:09:32.288Z |
| silver_auth | gold_baseline_gap | 4 | 2026-11-21T04:09:32.288Z |
| bronze_acquirer_ref | recon_file_control | 4 | 2026-11-21T04:08:49.606Z |
| bronze_atl_daily | recon_file_control | 4 | 2026-11-21T04:08:49.606Z |
| bronze_card_portfolio | recon_file_control | 4 | 2026-11-21T04:08:49.606Z |
| bronze_file_manifests | recon_file_control | 3 | 2026-11-21T04:08:49.606Z |
| bronze_issuer_auth | recon_file_control | 4 | 2026-11-21T04:08:49.606Z |
| bronze_manifests | recon_file_control | 1 | 2026-11-21T03:46:55.269Z |
| bronze_merchant_master | recon_file_control | 4 | 2026-11-21T04:08:49.606Z |
| bronze_mrd_events | recon_file_control | 4 | 2026-11-21T04:08:49.606Z |
| quarantine_auth | recon_file_control | 4 | 2026-11-21T04:08:49.606Z |
| silver_issuer_auth | recon_file_control | 4 | 2026-11-21T04:08:49.606Z |
| silver_network_response | recon_file_control | 4 | 2026-11-21T04:08:49.606Z |
| stg_cards | recon_file_control | 4 | 2026-11-21T04:08:49.606Z |
| stg_issuer_auth | recon_file_control | 4 | 2026-11-21T04:08:49.606Z |
| ref_response_code_map | silver_auth | 4 | 2026-11-21T04:09:17.035Z |
| silver_acquirers | silver_auth | 4 | 2026-11-21T04:09:17.035Z |
| silver_cards | silver_auth | 4 | 2026-11-21T04:09:17.035Z |
| silver_issuer_auth | silver_auth | 4 | 2026-11-21T04:09:17.035Z |
| silver_merchants | silver_auth | 4 | 2026-11-21T04:09:17.035Z |
| silver_network_response | silver_auth | 4 | 2026-11-21T04:09:17.035Z |
| stg_issuer_auth | silver_issuer_auth | 4 | 2026-11-21T04:08:30.128Z |
| bronze_atl_daily | silver_network_response | 5 | 2026-11-21T04:08:26.189Z |
| bronze_mrd_events | silver_network_response | 5 | 2026-11-21T04:08:25.548Z |
| ref_response_code_map | silver_network_response | 10 | 2026-11-21T04:08:26.189Z |

`bronze_manifests` is the empty table dropped in step 2; its edge is history. `auth_detail` (created this step) had not appeared in lineage yet when this was captured.

## Job run (governance inside the end-to-end job)

`febar_main` run 630235442628047: TERMINATED / SUCCESS.

| task | state | seconds |
|---|---|---|
| setup_governance | SUCCESS | 12 |
| refresh_pipeline | SUCCESS | 213 |
| apply_tags | SUCCESS | 9 |
