-----------------------------------------------------------------------------------------
--- Get all ICD and CPT codes so we can find relevant conditions and gestational ages ---
-----------------------------------------------------------------------------------------
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_asdb_icd`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
WITH icd AS (
    SELECT
        clm.asdb_plan_key
        , clm.claimid
        , CASE WHEN LENGTH(TRIM(codeid)) = 3 THEN TRIM(UPPER(codeid))
            WHEN SUBSTR(TRIM(UPPER(codeid)), 4, 1) = "." THEN TRIM(UPPER(codeid))
            ELSE CONCAT(SUBSTR(TRIM(UPPER(codeid)), 1, 3), ".", SUBSTR(TRIM(codeid), 5, 8)) END AS codeid
        , grp.ICD9_DX_GROUP_NBR AS icd_group
    FROM
        `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_ASDB_CLAIMDIAG` AS clm
    LEFT JOIN
        (SELECT ICD9_DX_GROUP_NBR, ICD9_DX_CD FROM `edp-prod-hcbstorage.edp_hcb_core_cnsv.ICD9_DIAGNOSIS`) AS grp
          ON TRIM(UPPER(clm.codeid)) = TRIM(UPPER(grp.ICD9_DX_CD))
)
SELECT 
 asdb_plan_key
 , claimid
 , ARRAY_AGG(STRUCT(icd.codeid AS icd_code, icd.icd_group AS icd_group)) icd_vals
FROM 
    icd
GROUP BY 
    claimid
    , asdb_plan_key
;

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_asdb_procedure`
AS
SELECT 
 asdb_plan_key
 , claimid
 , ARRAY_AGG(DISTINCT cols IGNORE NULLS) AS cpt_vals
FROM 
    `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_CLAIMICDPROCSUMMARY`
    , UNNEST ([icdpx1, icdpx1, icdpx2, icdpx3, icdpx4, icdpx5, icdpx6, icdpx7, icdpx8, icdpx9, icdpx10
               , icdpx11, icdpx12, icdpx13, icdpx14, icdpx15, icdpx16, icdpx17, icdpx18, icdpx19, icdpx20]) AS cols
GROUP BY 
    claimid
    , asdb_plan_key
; 
    
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_asdb_diagnoses`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT DISTINCT
    clm.asdb_member_key
    , clm.asdb_incurred_dt
    , icd.icd_vals
    , cpt.cpt_vals
    , clm.prindiag_vals
    , clm.cpt_clm_ln
    , clm.revcode
    , clm.asdb_coe_id
FROM 
    (
        SELECT
             clm.asdb_member_key
            , CAST( clm.asdb_incurred_dt AS DATE) AS asdb_incurred_dt
            , clm.claimid
            , clm.asdb_plan_key 
            , clm.revcode
            , clm.asdb_coe_id
            , ARRAY_AGG(DISTINCT clm.servcode IGNORE NULLS) AS cpt_clm_ln
            , ARRAY_AGG(STRUCT(CASE WHEN TRIM(clm.prindiag) IS NULL THEN NULL ELSE clm.prindiag END AS icd_code, 
                                CASE WHEN TRIM(clm.prindiag) IS NULL THEN NULL ELSE grp.ICD9_DX_GROUP_NBR END AS icd_group
                    ) IGNORE NULLS) prindiag_vals
        FROM 
            `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_CLM_DATA_STAGE` AS clm
        LEFT JOIN
            (SELECT ICD9_DX_GROUP_NBR, ICD9_DX_CD FROM `edp-prod-hcbstorage.edp_hcb_core_cnsv.ICD9_DIAGNOSIS`) AS grp
                ON TRIM(UPPER(prindiag)) = TRIM(UPPER(grp.ICD9_DX_CD))
        GROUP BY
             clm.asdb_member_key
            , clm.asdb_incurred_dt
            , clm.claimid
            , clm.asdb_plan_key
            , clm.revcode
            , clm.asdb_coe_id
    ) AS clm
LEFT JOIN 
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_asdb_icd` AS icd
        ON clm.claimid = icd.claimid
        AND clm.asdb_plan_key = icd.asdb_plan_key
LEFT JOIN 
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_asdb_procedure` AS cpt
        ON clm.claimid = cpt.claimid
        AND clm.asdb_plan_key = cpt.asdb_plan_key
WHERE 1 = 1
    AND clm.asdb_incurred_dt IS NOT NULL 
    AND NOT clm.asdb_member_key = 0
;