-----------------------------
--- All IDs cross-linking ---
-----------------------------
--take asdb IDs from target population (table a)
--cross-link to insights for iodb, QNXT, and edw individual_id (table b)
--cross-link to edw individual_id -> member_id so we can find all claims for a given member in the edw (table c)
--cross-link to komodo mdcd reidentification file (table d)
--cross-link to komodo non-mdcd reidentificaiton file (table e)
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_id_crosswalk`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
WITH d AS (
    SELECT DISTINCT 
        medicaid_id
        , upk_token_2
        , individual_id 
    FROM 
        `anbc-hcb-prod.eds_srcapp_komodombr_share_hcb_prod.enriched_active_aetna_beneficiary` 
    WHERE 1 = 1
        AND CAST(dt_field AS DATE) >= "2022-05-01"
)
SELECT DISTINCT
    a.mom_key AS asdb_member_key
    , b.iodb_mbr_key AS iodb_member_key
    , TRIM(b.src_mbr_id) AS medicaid_id
    , TRIM(b.indiv_id) individual_id
    --, ARRAY_AGG(DISTINCT c.member_id IGNORE NULLS) AS member_id
    , c.member_id
    , TRIM(d.upk_token_2) AS upk_token_2
    , a.baby_dob
FROM
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_final_timepoint` AS a
LEFT JOIN 
    `anbc-hcb-prod.insights_share_hcb_prod.v_insights_medicaid_member_xwalk` AS b
        ON a.mom_key = b.asdb_mbr_key
LEFT JOIN 
    `edp-prod-hcbstorage.edp_hcb_core_cnsv.INDVDL_CUST_DIST` AS c
        ON SAFE_CAST(b.indiv_id AS INT64) = c.individual_id
LEFT JOIN 
    d
        ON TRIM(b.src_mbr_id) = TRIM(d.medicaid_id)
            OR TRIM(b.indiv_id) = d.individual_id
/*
GROUP BY
    asdb_member_key
    , iodb_member_key
    , medicaid_id
    , individual_id
    , upk_token_2
    , baby_dob  
*/
;
--