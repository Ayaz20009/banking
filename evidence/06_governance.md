# Evidence 06: Unity Catalog governance per persona

Generated 2026-11-24T20:08:56Z by tools/generate_evidence.py from the live workspace.

Proves that access is enforced by Unity Catalog, not by the app: which tables carry the row filter and the column mask, the tags, the grants, and, for each persona, what the same query returns when run by a caller holding that persona (rows, segments, regions, masked card references). It also shows a non-admin service principal's result and the lineage Unity Catalog recorded.

## Policies attached (information_schema)

Row filters:

| table_name | filter_name | target_columns |
|---|---|---|
| auth_detail | classic_stable_zjnu75_catalog.network_migration.f_row_filter | issuer_segment, region |
| gold_anomalies | classic_stable_zjnu75_catalog.network_migration.f_row_filter | issuer_segment, region |
| gold_anomaly_scores | classic_stable_zjnu75_catalog.network_migration.f_row_filter | issuer_segment, region |
| gold_auth_daily | classic_stable_zjnu75_catalog.network_migration.f_row_filter | issuer_segment, region |
| gold_auth_hourly | classic_stable_zjnu75_catalog.network_migration.f_row_filter | issuer_segment, region |
| gold_baseline_gap | classic_stable_zjnu75_catalog.network_migration.f_row_filter | issuer_segment, region |
| gold_case_status | classic_stable_zjnu75_catalog.network_migration.f_row_filter | issuer_segment, region_scope |
| gold_wave_readiness | classic_stable_zjnu75_catalog.network_migration.f_row_filter | issuer_segment, region |


Column masks:

| table_name | column_name | mask_name |
|---|---|---|
| auth_detail | card_ref | classic_stable_zjnu75_catalog.network_migration.f_mask_card |


## Policy functions (definition as stored)

`f_mask_card`:

```sql
CASE
  WHEN EXISTS (
    SELECT 1
    FROM classic_stable_zjnu75_catalog.network_migration.entitlements e
    JOIN classic_stable_zjnu75_catalog.network_migration.personas p ON p.persona = e.persona
    WHERE (e.principal = current_user() OR (e.principal_type = 'GROUP' AND is_account_group_member(e.principal)))
      AND p.can_see_sensitive
  ) THEN card_ref
  ELSE 'RESTRICTED'
END
```

`f_row_filter`:

```sql
EXISTS (
  SELECT 1
  FROM classic_stable_zjnu75_catalog.network_migration.entitlements e
  JOIN classic_stable_zjnu75_catalog.network_migration.personas p ON p.persona = e.persona
  WHERE (e.principal = current_user() OR (e.principal_type = 'GROUP' AND is_account_group_member(e.principal)))
    AND (p.issuer_scope = 'ALL' OR p.issuer_scope = p_issuer_segment)
    AND (p.region_scope = 'ALL' OR p.region_scope = p_region)
)
```


## Personas and entitlements (data, not code)

| persona | title | issuer_scope | region_scope | can_see_sensitive | purpose |
|---|---|---|---|---|---|
| ADMIN | Platform owner (pipelines, jobs) | ALL | ALL | true | Owns and runs the pipeline and jobs; needs every row to compute results |
| P1_DIRECTOR | Director of Payment Network Operations | OWN | ALL | false | Network-wide view of the bank's own portfolio; no cardholder identifiers |
| P2_REGIONAL | Regional ops analyst (Southeast) | OWN | SE | false | Investigates incidents in one region |
| P3_CARD_INV | Card investigations specialist (cleared) | OWN | ALL | true | Needs card identifiers to fix card-on-file and token issues |
| P4_PARTNER | Network partner operations | THIRD_PARTY | ALL | false | Serves third-party issuers on the network; never sees the bank's own portfolio |


Entitlement rows (principals counted, not named):

| principal_type | persona | principals |
|---|---|---|
| USER | ADMIN | 1 |


## Same query, one persona at a time

The caller's own entitlement row is switched to each persona, the query below runs, and the row is restored to ADMIN at the end (in `finally`). Policies are evaluated by Unity Catalog at query time.

```sql
SELECT
  (SELECT persona FROM entitlements WHERE principal = current_user()) AS persona,
  sum(attempts) AS attempts_visible,
  sum(CASE WHEN issuer_segment = 'OWN' THEN attempts END) AS own_attempts,
  sum(CASE WHEN issuer_segment = 'THIRD_PARTY' THEN attempts END) AS third_party_attempts,
  concat_ws(',', sort_array(collect_set(region))) AS regions_visible,
  (SELECT count(*) FROM gold_case_status) AS cases_visible,
  (SELECT count(*) FROM gold_wave_readiness) AS readiness_rows_visible,
  (SELECT count(*) FROM auth_detail) AS detail_rows,
  (SELECT max_by(card_ref, auth_id) FROM auth_detail) AS card_ref_sample
FROM gold_auth_daily
```

| persona | attempts_visible | own_attempts | third_party_attempts | regions_visible | cases_visible | readiness_rows_visible | detail_rows | card_ref_sample |
|---|---|---|---|---|---|---|---|---|
| P1_DIRECTOR | 9898016 | 9898016 |  | INTL,MW,NE,SE,SW,W | 5 | 16 | 1552193 | RESTRICTED |
| P2_REGIONAL | 2433518 | 2433518 |  | SE | 1 | 0 | 381680 | RESTRICTED |
| P3_CARD_INV | 9898016 | 9898016 |  | INTL,MW,NE,SE,SW,W | 5 | 16 | 1552193 | CR12267792 |
| P4_PARTNER | 1094534 |  | 1094534 | INTL,MW,NE,SE,SW,W | 2 | 16 | 172748 | RESTRICTED |
| (no entitlement) |  |  |  |  | 0 | 0 | 0 |  |
| ADMIN | 10992550 | 9898016 | 1094534 | INTL,MW,NE,SE,SW,W | 7 | 32 | 1724941 | CR12267792 |


## Non-admin service principal (separate identity, profile `febar-sp`)

| query | state | result or error class |
|---|---|---|
| current persona | FAILED | INSUFFICIENT_PERMISSIONS: does not have USE CATALOG on Catalog 'classic_stable_zjnu75_catalog' |
| rows visible in gold_auth_daily | FAILED | INSUFFICIENT_PERMISSIONS: does not have USE CATALOG on Catalog 'classic_stable_zjnu75_catalog' |
| cases visible in gold_case_status | FAILED | INSUFFICIENT_PERMISSIONS: does not have USE CATALOG on Catalog 'classic_stable_zjnu75_catalog' |
| direct read of silver_auth | FAILED | INSUFFICIENT_PERMISSIONS: does not have USE CATALOG on Catalog 'classic_stable_zjnu75_catalog' |


This is the service principal's state now. The full non-admin test (temporary grants, persona P2_REGIONAL, then clean-up) is recorded in `build_history/06_governance.md`; its grants were removed at the end of that test.


## Tags

| table_name | tag_name | tag_value |
|---|---|---|
| auth_detail | nm_data_class | cardholder_restricted |
| auth_detail | nm_layer | gold |
| auth_detail | nm_policy | row_filter_persona_and_card_mask |
| bronze_card_portfolio | nm_data_class | cardholder_restricted |
| bronze_card_portfolio | nm_layer | bronze |
| bronze_card_portfolio | nm_policy | admin_only |
| bronze_issuer_auth | nm_data_class | cardholder_restricted |
| bronze_issuer_auth | nm_layer | bronze |
| bronze_issuer_auth | nm_policy | admin_only |
| entitlements | nm_data_class | access_control |
| gold_auth_daily | nm_data_class | commercially_sensitive |
| gold_auth_daily | nm_layer | gold |
| gold_auth_daily | nm_policy | row_filter_persona |
| gold_auth_hourly | nm_data_class | commercially_sensitive |
| gold_auth_hourly | nm_layer | gold |
| gold_auth_hourly | nm_policy | row_filter_persona |
| gold_baseline_gap | nm_data_class | commercially_sensitive |
| gold_baseline_gap | nm_layer | gold |
| gold_baseline_gap | nm_policy | row_filter_persona |
| gold_wave_readiness | nm_data_class | commercially_sensitive |
| gold_wave_readiness | nm_layer | gold |
| gold_wave_readiness | nm_policy | row_filter_persona |
| personas | nm_data_class | access_control |
| quarantine_auth | nm_data_class | cardholder_restricted |
| quarantine_auth | nm_layer | silver |
| quarantine_auth | nm_policy | admin_only |
| silver_auth | nm_data_class | cardholder_restricted |
| silver_auth | nm_layer | silver |
| silver_auth | nm_policy | admin_only |
| silver_cards | nm_data_class | cardholder_restricted |
| silver_cards | nm_layer | silver |
| silver_cards | nm_policy | admin_only |
| silver_issuer_auth | nm_data_class | cardholder_restricted |
| silver_issuer_auth | nm_layer | silver |
| silver_issuer_auth | nm_policy | admin_only |
| silver_network_response | nm_data_class | commercially_sensitive |
| silver_network_response | nm_layer | silver |
| silver_network_response | nm_policy | admin_only |


Column tags:

| table_name | column_name | tag_name | tag_value |
|---|---|---|---|
| auth_detail | card_ref | nm_sensitivity | restricted |
| auth_detail | issuer_segment | nm_sensitivity | commercially_sensitive |


## Grants on the schema

| Principal | ActionType | ObjectType | ObjectKey |
|---|---|---|---|
| 852bd824-1020-495c-a7bd-a8a936f2d21b | READ METADATA | METASTORE | metastore_aws_us_east_1 |
| 29d3b98e-b968-4882-b54b-ae42cafd9cb6 | READ METADATA | METASTORE | metastore_aws_us_east_1 |
| 22204953-12c2-4c38-b92b-f1ae7655e921 | READ METADATA | METASTORE | metastore_aws_us_east_1 |
| account users | READ METADATA | METASTORE | metastore_aws_us_east_1 |
| <user> | ALL PRIVILEGES | CATALOG | classic_stable_zjnu75_catalog |
| <user> | MANAGE | CATALOG | classic_stable_zjnu75_catalog |
| <user> | READ METADATA | METASTORE | metastore_aws_us_east_1 |


## Lineage recorded by Unity Catalog (system.access.table_lineage, distinct edges into gold)

| source | target |
|---|---|
| anomaly_explanations | gold_anomalies |
| gold_anomaly_scores | gold_anomalies |
| silver_acquirers | gold_anomalies |
| silver_auth | gold_anomaly_scores |
| silver_auth | gold_auth_daily |
| silver_auth | gold_auth_hourly |
| ref_recovery_assumptions | gold_baseline_gap |
| silver_auth | gold_baseline_gap |
| gold_anomalies | gold_case_flags |
| gold_baseline_gap | gold_wave_readiness |
| gold_case_status | gold_wave_readiness |
| ref_recovery_assumptions | gold_wave_readiness |
| silver_auth | gold_wave_readiness |
| silver_cards | gold_wave_readiness |
