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
    , clm.srv_start_dt AS incurred_dt
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
    , base.incurred_dt
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

---------------------------------
--- Visit-level risk presence (one row per claim line; reduces 001i join size)
---------------------------------
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_edw_visit_risk_presence`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
WITH visit_keys AS (
    SELECT DISTINCT asdb_member_key, member_id, index_dt, claim_line_id, incurred_dt
    FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_edw_cpt_and_revcode`
),
icd_presence AS (
    SELECT
        asdb_member_key
        , index_dt
        , claim_line_id
        , incurred_dt
        , MAX(CASE WHEN icd9_dx_cd LIKE "O60.0%" OR icd9_dx_cd LIKE "O60.2%" THEN 1 ELSE 0 END) AS has_pre_term_labor_codes
        , MAX(CASE WHEN icd9_dx_cd LIKE "O42.01%" OR icd9_dx_cd LIKE "O42.11%" OR icd9_dx_cd LIKE "O42.91%" OR icd9_dx_cd LIKE "O60.1%" OR icd9_dx_cd LIKE "P07.2%" OR icd9_dx_cd LIKE "P07.3%" THEN 1 ELSE 0 END) AS has_pre_term_delivery_codes
        , MAX(CASE WHEN icd9_dx_cd LIKE "O24%" OR icd_group = 22 THEN 1 ELSE 0 END) AS has_dm_codes
        , MAX(CASE WHEN icd_group IN (10, 109) THEN 1 ELSE 0 END) AS has_ht_codes
        , MAX(CASE WHEN icd_group = 110 THEN 1 ELSE 0 END) AS has_pre_e_codes
        , MAX(CASE WHEN icd_group = 97 THEN 1 ELSE 0 END) AS has_97
        , MAX(CASE WHEN icd_group = 92 THEN 1 ELSE 0 END) AS has_92
        , MAX(CASE WHEN icd9_dx_cd = "R73.03" THEN 1 ELSE 0 END) AS pre_dm
        , MAX(CASE WHEN icd9_dx_cd = "Z83.3" THEN 1 ELSE 0 END) AS f_hist_dm
        , MAX(CASE WHEN icd9_dx_cd = "D68.61" THEN 1 ELSE 0 END) AS aps
        , MAX(CASE WHEN icd9_dx_cd IN ("Z31.83", "N98.1") THEN 1 ELSE 0 END) AS art_icd
        , MAX(CASE WHEN icd_group IN (181, 182) THEN 1 ELSE 0 END) AS autoimmune
        , MAX(CASE WHEN icd9_dx_cd = "Z87.59" OR icd9_dx_cd LIKE "O01%" THEN 1 ELSE 0 END) AS hist_ob_comp
        , MAX(CASE WHEN icd9_dx_cd LIKE "E66%" THEN 1 ELSE 0 END) AS obesity
        , MAX(CASE WHEN icd9_dx_cd = "E28.2" THEN 1 ELSE 0 END) AS pcos
        , MAX(CASE WHEN icd_group IN (66, 67, 68, 234) THEN 1 ELSE 0 END) AS renal
        , MAX(CASE WHEN icd_group = 257 THEN 1 ELSE 0 END) AS sle
        , MAX(CASE WHEN icd9_dx_cd LIKE "C58%" THEN 1 ELSE 0 END) AS trophoblastic
        , MAX(CASE WHEN icd9_dx_cd LIKE "F10%" OR icd9_dx_cd = "R78.0" THEN 1 ELSE 0 END) AS Alcohol
        , MAX(CASE WHEN icd9_dx_cd LIKE "F11%" OR icd9_dx_cd = "R78.1" THEN 1 ELSE 0 END) AS OUD
        , MAX(CASE WHEN icd9_dx_cd LIKE "F12%" THEN 1 ELSE 0 END) AS Cannabis
        , MAX(CASE WHEN icd9_dx_cd LIKE "F14%" OR icd9_dx_cd = "R78.2" THEN 1 ELSE 0 END) AS Cocaine
        , MAX(CASE WHEN icd9_dx_cd LIKE "F17%" OR icd9_dx_cd LIKE "O99.33%" THEN 1 ELSE 0 END) AS Nicotine
        , MAX(CASE WHEN icd9_dx_cd LIKE "F13%" OR icd9_dx_cd LIKE "F15%" OR icd9_dx_cd LIKE "F16%" OR icd9_dx_cd LIKE "F18%" OR icd9_dx_cd LIKE "F19%" OR icd9_dx_cd LIKE "F55%" OR icd9_dx_cd LIKE "O99.32%" OR icd9_dx_cd IN ("R78.3", "R78.4", "R78.5", "R78.6") THEN 1 ELSE 0 END) AS Other_drug
    FROM
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_edw_icd_codes`
    GROUP BY asdb_member_key, index_dt, claim_line_id, incurred_dt
),
art_cpt AS (
    SELECT
        asdb_member_key
        , index_dt
        , claim_line_id
        , incurred_dt
        , 1 AS art_cpt
    FROM
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_edw_cpt_and_revcode`
    WHERE prcdr_cd = 'S4042'
)
SELECT
    v.asdb_member_key
    , v.index_dt
    , v.claim_line_id
    , v.incurred_dt
    , COALESCE(i.has_pre_term_labor_codes, 0) AS has_pre_term_labor_codes
    , COALESCE(i.has_pre_term_delivery_codes, 0) AS has_pre_term_delivery_codes
    , COALESCE(i.has_dm_codes, 0) AS has_dm_codes
    , COALESCE(i.has_ht_codes, 0) AS has_ht_codes
    , COALESCE(i.has_pre_e_codes, 0) AS has_pre_e_codes
    , COALESCE(i.has_97, 0) AS has_97
    , COALESCE(i.has_92, 0) AS has_92
    , COALESCE(i.pre_dm, 0) AS pre_dm
    , COALESCE(i.f_hist_dm, 0) AS f_hist_dm
    , COALESCE(i.aps, 0) AS aps
    , COALESCE(i.art_icd, 0) AS art_icd
    , CASE WHEN c.art_cpt = 1 THEN 1 ELSE 0 END AS art_cpt
    , COALESCE(i.autoimmune, 0) AS autoimmune
    , COALESCE(i.hist_ob_comp, 0) AS hist_ob_comp
    , COALESCE(i.obesity, 0) AS obesity
    , COALESCE(i.pcos, 0) AS pcos
    , COALESCE(i.renal, 0) AS renal
    , COALESCE(i.sle, 0) AS sle
    , COALESCE(i.trophoblastic, 0) AS trophoblastic
    , COALESCE(i.Alcohol, 0) AS Alcohol
    , COALESCE(i.OUD, 0) AS OUD
    , COALESCE(i.Cannabis, 0) AS Cannabis
    , COALESCE(i.Cocaine, 0) AS Cocaine
    , COALESCE(i.Nicotine, 0) AS Nicotine
    , COALESCE(i.Other_drug, 0) AS Other_drug
FROM visit_keys AS v
LEFT JOIN icd_presence AS i
    ON v.asdb_member_key = i.asdb_member_key
    AND v.index_dt = i.index_dt
    AND v.claim_line_id = i.claim_line_id
    AND v.incurred_dt = i.incurred_dt
LEFT JOIN art_cpt AS c
    ON v.asdb_member_key = c.asdb_member_key
    AND v.index_dt = c.index_dt
    AND v.claim_line_id = c.claim_line_id
    AND v.incurred_dt = c.incurred_dt
;