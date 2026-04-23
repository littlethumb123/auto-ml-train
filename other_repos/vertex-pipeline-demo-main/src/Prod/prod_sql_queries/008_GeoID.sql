-- GeoID Query
-- Creates geographic identifier table for ACS data
-- Variables: GCP_PROJECT, GCP_DB, PREFIX, OWNER, COST_CENTER, DEFAULT_EXP

DROP TABLE IF EXISTS `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_geoid`;

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_geoid`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
WITH maxdt AS (
    SELECT iodb_member_key
           , MAX(source_pstd_dts) AS source_pstd_dts
    FROM `anbc-hcb-prod.insights_share_hcb_prod.v_enriched_address_medicaid`
    GROUP BY iodb_member_key
)

SELECT DISTINCT 
    st.asdb_member_key
    , mb.iodb_member_key
    , id.ctfips
    , id.bgfips
FROM
    (SELECT DISTINCT asdb_member_key, asdb_plan_key FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st`) AS st
INNER JOIN 
    (SELECT
        iodb_member_key
        , asdb_member_key
        , asdb_plan_key
     FROM `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_MEMBER`) AS mb
        ON st.asdb_member_key=mb.asdb_member_key
        AND st.asdb_plan_key=mb.asdb_plan_key
INNER JOIN 
    (SELECT
         block_code AS bgfips
         , CONCAT(fips_state_county_code, census_tract) AS ctfips
         , iodb_member_key
         , source_pstd_dts
         , geo_accuracy_code
    FROM `anbc-hcb-prod.insights_share_hcb_prod.v_enriched_address_medicaid`) AS id
        ON mb.iodb_member_key=id.iodb_member_key
INNER JOIN maxdt 
    ON id.iodb_member_key=maxdt.iodb_member_key
       AND id.source_pstd_dts=maxdt.source_pstd_dts
WHERE TRIM(id.geo_accuracy_code) IN ("1", "2", "5", "6");
