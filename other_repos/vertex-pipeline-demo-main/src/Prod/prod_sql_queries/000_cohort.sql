------------------------------------------------------------------------------------------
------- Project: Vertex Pipeline Demo - Production Scoring                     ---------
------- Based on: Medicaid maternity models feature pull pattern               ---------
------- Population: All Medicaid pregnant members from PREGNANCY_TABLE_W       ---------
------------------------------------------------------------------------------------------

--------------------------------
-- Source table dependencies ---
--------------------------------
--`edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.PREGNANCY_TABLE_W`
--`anbc-hcb-prod.insights_share_hcb_prod.v_insights_medicaid_member_xwalk`
--`edp-prod-hcbstorage.edp_hcb_core_cnsv.INDVDL_CUST_DIST`
--`anbc-hcb-prod.eds_srcapp_komodombr_share_hcb_prod.aetna_mdcd_beneficiary_komodo_trace_history`
--`edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_MEMBER`

-------------------
--- system vars ---
-------------------
--GCP_PROJECT  = ex. anbc-hcb-dev
--GCP_DB       = ex. cm_medicaid_hcb_dev
--PREFIX       = ex. a534354_nicu_prod
--OWNER        = ex. palmere1_aetna_com
--COST_CENTER  = ex. 13070
--DEFAULT_EXP  = ex. INTERVAL 180 DAY
--INDEX_DT     = job run date (ex. "2024-12-04")
--KMDO_DT      = komodo data date (ex. "2024-11-01")
--SDOH_YR      = max year available (ex. 2023)

----------------------------------------
--- Get membership for current month ---
----------------------------------------
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st` 
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
WITH kmdo AS (
    SELECT DISTINCT 
        medicaid_id
        , upk_token_2
        , individual_id 
    FROM 
        `anbc-hcb-prod.eds_srcapp_komodombr_share_hcb_prod.enriched_active_aetna_beneficiary`
    WHERE 1 = 1
        AND CAST(dt_field AS DATE) = {KMDO_DT}
)
SELECT DISTINCT
    w.asdb_member_key
    , w.asdb_plan_key
    , xwlk.iodb_mbr_key AS iodb_member_key
    , TRIM(xwlk.src_mbr_id) AS medicaid_id
    , TRIM(xwlk.indiv_id) AS individual_id
    , edw.member_id
    , TRIM(kmdo.upk_token_2) AS upk_token_2
    , FLOOR(DATE_DIFF(DATE({INDEX_DT}), DATE(mb.dob), YEAR)) AS mom_age 
    -- Robust gestational age calculation handling missing dates
    , CASE 
        WHEN w.min_preg_dt IS NULL AND w.est_eop_dt IS NULL THEN CAST(6 AS INT64) 
        WHEN DATE_ADD(CAST(w.min_preg_dt AS DATE), INTERVAL 238 DAY) < w.rpt_end_dt THEN CAST(42 AS INT64)
        WHEN w.est_eop_dt IS NULL THEN CAST(FLOOR(DATE_DIFF(DATE_ADD(CAST(w.min_preg_dt AS DATE), INTERVAL 238 DAY), w.rpt_end_dt, DAY) / 7) AS INT64)
        WHEN {INDEX_DT} > DATE_ADD(CAST(w.est_eop_dt AS DATE), INTERVAL 14 DAY) THEN CAST(42 AS INT64)
        ELSE CAST(FLOOR(DATE_DIFF(CAST(w.rpt_end_dt AS DATE), DATE_SUB(CAST(w.est_eop_dt AS DATE), INTERVAL 280 DAY), DAY)/7) AS INT64)
      END AS gest_age
    , CAST(w.min_preg_dt AS DATE) AS min_preg_dt
    , CAST(w.est_eop_dt AS DATE) AS est_eop_dt
    , CAST(w.rpt_end_dt AS DATE) AS rpt_end_dt
    , DATE({INDEX_DT}) AS index_dt
FROM
    `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.PREGNANCY_TABLE_W` AS w
LEFT JOIN 
    `anbc-hcb-prod.insights_share_hcb_prod.v_insights_medicaid_member_xwalk` AS xwlk
        ON w.asdb_member_key = xwlk.asdb_mbr_key
LEFT JOIN 
    `edp-prod-hcbstorage.edp_hcb_core_cnsv.INDVDL_CUST_DIST` AS edw
        ON SAFE_CAST(xwlk.indiv_id AS INT64) = edw.individual_id
LEFT JOIN 
    kmdo
        ON TRIM(xwlk.src_mbr_id) = TRIM(kmdo.medicaid_id)
            OR TRIM(xwlk.indiv_id) = kmdo.individual_id
LEFT JOIN
    `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_MEMBER` AS mb
        ON w.asdb_member_key = mb.asdb_member_key
WHERE 1 = 1
    AND w.asdb_member_key IS NOT NULL
    AND w.asdb_member_key != 0
;
