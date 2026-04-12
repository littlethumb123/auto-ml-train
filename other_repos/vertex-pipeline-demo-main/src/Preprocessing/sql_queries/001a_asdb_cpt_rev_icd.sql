-----------------------------------------------------------------------------------------
--- Get all ICD and CPT codes so we can find relevant conditions and gestational ages ---
-----------------------------------------------------------------------------------------
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_icd`
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

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_procedure`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
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
    
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_diagnoses`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT DISTINCT
    clm.asdb_member_key
    , clm.asdb_incurred_dt
    , clm.claimid
    , clm.asdb_plan_key
    , clm.asdb_coe_id
    , icd.icd_vals
    , cpt.cpt_vals
    , clm.prindiag_vals
    , clm.cpt_clm_ln
    , clm.revcode
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
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_icd` AS icd
        ON clm.claimid = icd.claimid
        AND clm.asdb_plan_key = icd.asdb_plan_key
LEFT JOIN 
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_procedure` AS cpt
        ON clm.claimid = cpt.claimid
        AND clm.asdb_plan_key = cpt.asdb_plan_key
WHERE 1 = 1
    AND clm.asdb_incurred_dt IS NOT NULL 
    AND NOT clm.asdb_member_key = 0
;

-----------------------------------------------------------------------------------------
--- Visit-level risk presence (one row per claim/visit; reduces 001i join size)
-----------------------------------------------------------------------------------------
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_asdb_visit_risk_presence`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
WITH visit_keys AS (
    SELECT DISTINCT asdb_member_key, asdb_incurred_dt, claimid, asdb_plan_key, asdb_coe_id
    FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_diagnoses`
),
icd_flat AS (
    SELECT
        d.asdb_member_key
        , d.asdb_incurred_dt
        , d.claimid
        , d.asdb_plan_key
        , d.asdb_coe_id
        , S.icd_code
        , S.icd_group
    FROM
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_diagnoses` AS d
        , UNNEST(ARRAY_CONCAT(COALESCE(d.icd_vals, []), COALESCE(d.prindiag_vals, []))) AS S
    WHERE S.icd_code IS NOT NULL
),
cpt_flat AS (
    SELECT
        d.asdb_member_key
        , d.asdb_incurred_dt
        , d.claimid
        , d.asdb_plan_key
        , d.asdb_coe_id
        , cpt_val
    FROM
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_diagnoses` AS d
        , UNNEST(ARRAY_CONCAT(COALESCE(d.cpt_vals, []), COALESCE(d.cpt_clm_ln, []))) AS cpt_val
    WHERE cpt_val IS NOT NULL
),
icd_presence AS (
    SELECT
        asdb_member_key
        , asdb_incurred_dt
        , claimid
        , asdb_plan_key
        , asdb_coe_id
        , MAX(CASE WHEN icd_code LIKE "O60.0%" OR icd_code LIKE "O60.2%" THEN 1 ELSE 0 END) AS has_pre_term_labor_codes
        , MAX(CASE WHEN icd_code LIKE "O42.01%" OR icd_code LIKE "O42.11%" OR icd_code LIKE "O42.91%" OR icd_code LIKE "O60.1%" OR icd_code LIKE "P07.2%" OR icd_code LIKE "P07.3%" THEN 1 ELSE 0 END) AS has_pre_term_delivery_codes
        , MAX(CASE WHEN icd_code LIKE "O24%" OR icd_group = 22 THEN 1 ELSE 0 END) AS has_dm_codes
        , MAX(CASE WHEN icd_group IN (10, 109) THEN 1 ELSE 0 END) AS has_ht_codes
        , MAX(CASE WHEN icd_group = 110 THEN 1 ELSE 0 END) AS has_pre_e_codes
        , MAX(CASE WHEN icd_group = 97 THEN 1 ELSE 0 END) AS has_97
        , MAX(CASE WHEN icd_group = 92 THEN 1 ELSE 0 END) AS has_92
        , MAX(CASE WHEN icd_code = "R73.03" THEN 1 ELSE 0 END) AS pre_dm
        , MAX(CASE WHEN icd_code = "Z83.3" THEN 1 ELSE 0 END) AS f_hist_dm
        , MAX(CASE WHEN icd_code = "D68.61" THEN 1 ELSE 0 END) AS aps
        , MAX(CASE WHEN icd_code IN ("Z31.83", "N98.1") THEN 1 ELSE 0 END) AS art_icd
        , MAX(CASE WHEN icd_group IN (181, 182) THEN 1 ELSE 0 END) AS autoimmune
        , MAX(CASE WHEN icd_code = "Z87.59" OR icd_code LIKE "O01%" THEN 1 ELSE 0 END) AS hist_ob_comp
        , MAX(CASE WHEN icd_code LIKE "E66%" THEN 1 ELSE 0 END) AS obesity
        , MAX(CASE WHEN icd_code = "E28.2" THEN 1 ELSE 0 END) AS pcos
        , MAX(CASE WHEN icd_group IN (66, 67, 68, 234) THEN 1 ELSE 0 END) AS renal
        , MAX(CASE WHEN icd_group = 257 THEN 1 ELSE 0 END) AS sle
        , MAX(CASE WHEN icd_code LIKE "C58%" THEN 1 ELSE 0 END) AS trophoblastic
        , MAX(CASE WHEN icd_code LIKE "F10%" OR icd_code = "R78.0" THEN 1 ELSE 0 END) AS Alcohol
        , MAX(CASE WHEN icd_code LIKE "F11%" OR icd_code = "R78.1" THEN 1 ELSE 0 END) AS OUD
        , MAX(CASE WHEN icd_code LIKE "F12%" THEN 1 ELSE 0 END) AS Cannabis
        , MAX(CASE WHEN icd_code LIKE "F14%" OR icd_code = "R78.2" THEN 1 ELSE 0 END) AS Cocaine
        , MAX(CASE WHEN icd_code LIKE "F17%" OR icd_code LIKE "O99.33%" THEN 1 ELSE 0 END) AS Nicotine
        , MAX(CASE WHEN icd_code LIKE "F13%" OR icd_code LIKE "F15%" OR icd_code LIKE "F16%" OR icd_code LIKE "F18%" OR icd_code LIKE "F19%" OR icd_code LIKE "F55%" OR icd_code LIKE "O99.32%" OR icd_code IN ("R78.3", "R78.4", "R78.5", "R78.6") THEN 1 ELSE 0 END) AS Other_drug
    FROM icd_flat
    GROUP BY asdb_member_key, asdb_incurred_dt, claimid, asdb_plan_key, asdb_coe_id
),
cpt_art AS (
    SELECT
        asdb_member_key
        , asdb_incurred_dt
        , claimid
        , asdb_plan_key
        , asdb_coe_id
        , MAX(CASE WHEN cpt_val = "S4042" THEN 1 ELSE 0 END) AS art_cpt
    FROM cpt_flat
    GROUP BY asdb_member_key, asdb_incurred_dt, claimid, asdb_plan_key, asdb_coe_id
)
SELECT
    v.asdb_member_key
    , v.asdb_incurred_dt
    , v.claimid
    , v.asdb_plan_key
    , v.asdb_coe_id
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
    , COALESCE(c.art_cpt, 0) AS art_cpt
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
    AND v.asdb_incurred_dt = i.asdb_incurred_dt
    AND v.claimid = i.claimid
    AND v.asdb_plan_key = i.asdb_plan_key
    AND v.asdb_coe_id = i.asdb_coe_id
LEFT JOIN cpt_art AS c
    ON v.asdb_member_key = c.asdb_member_key
    AND v.asdb_incurred_dt = c.asdb_incurred_dt
    AND v.claimid = c.claimid
    AND v.asdb_plan_key = c.asdb_plan_key
    AND v.asdb_coe_id = c.asdb_coe_id
;