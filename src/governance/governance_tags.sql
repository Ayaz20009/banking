-- =============================================================================
-- Post-pipeline governance: tags on pipeline-owned tables (run after the pipeline update,
-- because the tables must exist). Idempotent. Column comments for pipeline tables live in
-- the pipeline definitions (ALTER COLUMN COMMENT is not allowed on pipeline materialized views).
-- Tag keys are namespaced (nm_*) because generic keys are governed by other teams' tag policies.
-- =============================================================================
USE CATALOG classic_stable_zjnu75_catalog;
USE SCHEMA network_migration;

-- Consumption tables (people, Genie, App): row filter by persona.
ALTER TABLE gold_auth_daily   SET TAGS ('nm_layer' = 'gold',   'nm_data_class' = 'commercially_sensitive', 'nm_policy' = 'row_filter_persona');
ALTER TABLE gold_auth_hourly  SET TAGS ('nm_layer' = 'gold',   'nm_data_class' = 'commercially_sensitive', 'nm_policy' = 'row_filter_persona');
ALTER TABLE gold_baseline_gap SET TAGS ('nm_layer' = 'gold',   'nm_data_class' = 'commercially_sensitive', 'nm_policy' = 'row_filter_persona');
ALTER TABLE auth_detail       SET TAGS ('nm_layer' = 'gold',   'nm_data_class' = 'cardholder_restricted',  'nm_policy' = 'row_filter_persona_and_card_mask');
ALTER TABLE auth_detail ALTER COLUMN card_ref SET TAGS ('nm_sensitivity' = 'restricted');
ALTER TABLE auth_detail ALTER COLUMN issuer_segment SET TAGS ('nm_sensitivity' = 'commercially_sensitive');

-- Pipeline-internal tables: no grants to personas (admin only), so policies never change what the pipeline computes.
ALTER TABLE silver_auth             SET TAGS ('nm_layer' = 'silver', 'nm_data_class' = 'cardholder_restricted', 'nm_policy' = 'admin_only');
ALTER TABLE silver_issuer_auth      SET TAGS ('nm_layer' = 'silver', 'nm_data_class' = 'cardholder_restricted', 'nm_policy' = 'admin_only');
ALTER TABLE silver_network_response SET TAGS ('nm_layer' = 'silver', 'nm_data_class' = 'commercially_sensitive', 'nm_policy' = 'admin_only');
ALTER TABLE silver_cards            SET TAGS ('nm_layer' = 'silver', 'nm_data_class' = 'cardholder_restricted', 'nm_policy' = 'admin_only');
ALTER TABLE quarantine_auth         SET TAGS ('nm_layer' = 'silver', 'nm_data_class' = 'cardholder_restricted', 'nm_policy' = 'admin_only');
ALTER TABLE bronze_issuer_auth      SET TAGS ('nm_layer' = 'bronze', 'nm_data_class' = 'cardholder_restricted', 'nm_policy' = 'admin_only');
ALTER TABLE bronze_card_portfolio   SET TAGS ('nm_layer' = 'bronze', 'nm_data_class' = 'cardholder_restricted', 'nm_policy' = 'admin_only');
