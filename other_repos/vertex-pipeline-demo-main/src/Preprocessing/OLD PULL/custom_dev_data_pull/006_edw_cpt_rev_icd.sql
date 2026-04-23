--TODO: Map to ICD group

---------------------------------
--- CPT and rev codes 
---------------------------------

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_edw_cpt_and_revcode`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT
    base.asdb_member_key
    , base.member_id
    , base.index_dt
    , clm.claim_line_id
    , clm.srv_start_dt AS dt
    , CASE WHEN TRIM(clm.revenue_cd) = '' THEN NULL 
        ELSE TRIM(clm.revenue_cd) END AS revenue_cd
    , CASE WHEN TRIM(clm.prcdr_cd) = '' THEN NULL 
        ELSE TRIM(clm.prcdr_cd) END AS prcdr_cd
FROM 
    (SELECT asdb_member_key, member_id, baby_dob AS index_dt FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_id_crosswalk`) AS base 
LEFT JOIN
    `edp-prod-hcbstorage.edp_hcb_core_cnsv.EMIS_CLAIM_LINE` AS clm 
        ON base.member_id = clm.member_id
WHERE 1=1
    AND clm.duplicate_ind = 'N' 
    AND clm.summarized_srv_ind = 'Y'
    AND CAST(base.index_dt AS DATE) > CAST(clm.adjn_dt AS DATE)
    AND CAST(base.index_dt AS DATE) > CAST(clm.received_dt AS DATE)
    AND CAST(base.index_dt AS DATE) > clm.srv_start_dt
    AND DATE_ADD(clm.srv_start_dt, INTERVAL 36 MONTH) > CAST(base.index_dt AS DATE)
;
--166,800

--QC check
SELECT 
    'da' AS step
    , COUNT(1) AS cnt
    , COUNT(DISTINCT asdb_member_key) AS cnt_ind
FROM 
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_edw_cpt_and_revcode`
;
/*
step     cnt   cnt_ind
 d1a 166,800     2,906
*/


---------------------------------
--- ICD codes 
---------------------------------

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_edw_icd_codes`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS

SELECT 
    base.asdb_member_key
    , base.member_id
    , base.index_dt
    , base.claim_line_id
    , b.icd9_dx_cd
    , grp.ICD9_DX_GROUP_NBR AS icd_group
FROM
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_edw_cpt_and_revcode` AS base 
INNER JOIN
    `edp-prod-hcbstorage.edp_hcb_core_cnsv.CLM_LN_X_ICD9_DX` AS b 
        ON base.claim_line_id = b.claim_line_id
        AND base.member_id = b.member_id
LEFT JOIN
    `edp-prod-hcbstorage.edp_hcb_core_cnsv.ICD9_DIAGNOSIS` AS grp
          ON TRIM(UPPER(b.icd9_dx_cd)) = TRIM(UPPER(grp.ICD9_DX_CD))
WHERE 1 = 1
    AND CAST(b.sequence_id AS INT) < 4
;
--356,996 rows

SELECT 
    'd1b' AS step
    , COUNT(1) AS cnt
    , COUNT(DISTINCT asdb_member_key) AS cnt_ind
FROM 
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_edw_icd_codes`
;
/*
step     cnt   cnt_ind
 d1b 356,996     2,906
*/
