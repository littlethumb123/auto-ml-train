-----------------------------------------------------------------------------------------
--- Get all ICD and CPT codes so we can find relevant conditions and gestational ages ---
-----------------------------------------------------------------------------------------
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_qc_all_icd`
AS
WITH icd AS (
    SELECT
        clm.asdb_plan_key
        , clm.claimid
        , CASE WHEN LENGTH(TRIM(codeid)) = 3 THEN TRIM(UPPER(codeid))
            WHEN SUBSTR(TRIM(UPPER(codeid)), 4, 1) = "." THEN TRIM(UPPER(codeid))
            ELSE CONCAT(SUBSTR(TRIM(UPPER(codeid)), 1, 3), ".", SUBSTR(TRIM(codeid), 5, 9)) END AS codeid
        , grp.ICD9_DX_GROUP_NBR AS icd_group
    FROM
        `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_ASDB_CLAIMDIAG` AS clm
    LEFT JOIN
        (SELECT ICD9_DX_GROUP_NBR, ICD9_DX_CD FROM `edp-prod-hcbstorage.edp_hcb_anbor_enrsrcv.EDW_ICD9_DIAGNOSIS`) AS grp
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

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_qc_all_procedure`
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
    
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_qc_all_diagnoses`
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
            (SELECT ICD9_DX_GROUP_NBR, ICD9_DX_CD FROM `edp-prod-hcbstorage.edp_hcb_anbor_enrsrcv.EDW_ICD9_DIAGNOSIS`) AS grp
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
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_qc_all_icd` AS icd
        ON clm.claimid = icd.claimid
        AND clm.asdb_plan_key = icd.asdb_plan_key
LEFT JOIN 
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_qc_all_procedure` AS cpt
        ON clm.claimid = cpt.claimid
        AND clm.asdb_plan_key = cpt.asdb_plan_key
WHERE 1 = 1
    AND clm.asdb_incurred_dt IS NOT NULL 
    AND NOT clm.asdb_member_key = 0
;

---------------------------------------------------------------------------------------------------------------------------------------
--- pull all relevant information into a single table with the DM and pre-e outcomes (and first date within pregnancy of diagnosis) ---
---------------------------------------------------------------------------------------------------------------------------------------
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_qc_final_timepoint`
AS
WITH baby AS (
    SELECT
        mem.asdb_plan_key
        , mem.asdb_member_key
        , mem.guardian
        , mem.baby_dob
        , MAX(nicu_lvl) AS nicu_lvl
    FROM 
        (
            SELECT 
                asdb_member_key
                , asdb_plan_key
                , guardian
                , CAST(dob AS DATE) AS baby_dob 
            FROM 
                `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_MEMBER` 
            WHERE 1 = 1
                AND CAST(dob AS DATE) BETWEEN "2022-06-01" AND "2024-10-14"
        ) AS mem
    LEFT JOIN
        (
            SELECT
                 asdb_member_key
                , CASE WHEN revcode = "0174" THEN 4
                    WHEN revcode = "0173" THEN 3
                    WHEN revcode = "0172" THEN 2
                    WHEN revcode = "0171" THEN 1
                    ELSE 0 END AS nicu_lvl
            FROM
                `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_qc_all_diagnoses`
            WHERE 1 = 1
                AND revcode IN ("0170", "0171", "0172", "0173", "0174", "0179")
        ) AS clm
            ON mem.asdb_member_key = clm.asdb_member_key
    GROUP BY
        asdb_plan_key
        , asdb_member_key
        , guardian
        , baby_dob
) --As of 9/25/2024 we have 100,285 babies with NICU recorded, so born with claims to us.
, mom AS (
    SELECT DISTINCT
        mem.asdb_plan_key
        , mem.asdb_member_key AS mom_key
        , mem.guardian
        , mem.mom_dob
        , CAST(FLOOR(DATE_DIFF(baby.baby_dob, mem.mom_dob, MONTH)/12) AS INT64) AS mom_age
        , baby.asdb_member_key AS baby_key
        , baby.baby_dob
        , baby.nicu_lvl
    FROM 
        (
            SELECT DISTINCT
                asdb_member_key 
                , CAST(asdb_incurred_dt AS DATE) AS asdb_incurred_dt
            FROM 
                `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_qc_all_diagnoses`
            WHERE
                1 = 1
                AND (asdb_coe_id = 10000
                    AND (revcode IN ("0112", "0122", "0132", "0142", "0152", "112", "122", "132", "142", "152")
                    OR prindiag_vals[SAFE_OFFSET(0)].icd_code IN (
                        "O10.02", "O10.12", "O10.22", "O10.32", "O10.42", "O10.92", "O11.4", "O13.4", "O16.4",--HT
                        "O12.04", "O12.14", "O12.24", --proteinuria w/o hypertension
                        "O14.04", "O14.14", "O14.24", "O14.94", --preeclampsia
                        "O24.02", "O24.12", "O24.32", "O24.42", "O24.420", "O24.424", "O24.425", "O24.429", "O24.82", "O24.92", --diabetes
                        "O25.2", --malnutrition
                        "O26.62", "O26.72", --other condition
                        "O42.10", "O42.111", "O42.112", "O42.113", "O42.119", "O4.212", --PROM
                        "O60.12X0", "O60.12X1", "O60.12X2",
                        "O60.12X3", "O60.12X4", "O60.12X5", "O60.12X9", "O60.13X0", "O60.13X1", "O60.13X2",
                        "O60.13X3", "O60.13X4", "O60.13X5", "O60.13X9", "O60.14X0", "O60.14X1", "O60.14X2",
                        "O60.14X3", "O60.14X4", "O60.14X5", "O60.14X9", "O60.22X0", "O60.22X1", "O60.22X2",
                        "O60.22X3", "O60.22X4", "O60.22X5", "O60.22X9", "O60.23X0", "O60.23X1", "O60.23X2",
                        "O60.23X3", "O60.23X4", "O60.23X5", "O60.23X9", "O62.3", "O62.8", "O62.9", "O63.2",
                        "O65.0", "O651", "O652", "O653", "O654", "O655", "O658", "O659", "O669", "O68",
                        "O69.0XX0", "O69.0XX1", "O69.0XX2", "O69.0XX3", "O69.0XX4", "O69.0XX5", "O69.0XX9",
                        "O69.1XX0", "O69.1XX1", "O69.1XX2", "O69.1XX3", "O69.1XX4", "O69.1XX5", "O69.1XX9",
                        "O69.2XX0", "O69.2XX1", "O69.2XX2", "O69.2XX3", "O69.2XX4", "O69.2XX5", "O69.2XX9",
                        "O69.3XX0", "O69.3XX1", "O69.3XX2", "O69.3XX3", "O69.3XX4", "O69.3XX5", "O69.3XX9",
                        "O69.4XX0", "O69.4XX1", "O69.4XX2", "O69.4XX3", "O69.4XX4", "O69.4XX5", "O69.4XX9",
                        "O69.5XX0", "O69.5XX1", "O69.5XX2", "O69.5XX3", "O69.5XX4", "O69.5XX5", "O69.5XX9",
                        "O69.81X0", "O69.81X1", "O69.81X2", "O69.81X3", "O69.81X4", "O69.81X5", "O69.81X9",
                        "O69.82X0", "O69.82X1", "O69.82X2", "O69.82X3", "O69.82X4", "O69.82X5", "O69.82X9",
                        "O69.89X0", "O69.89X1", "O69.89X2", "O69.89X3", "O69.89X4", "O69.89X5", "O69.89X9",
                        "O69.9XX0", "O69.9XX1", "O69.9XX2", "O69.9XX3", "O69.9XX4", "O69.9XX5", "O69.9XX9",
                        "O70.0", "O70.1", "O70.2", "O70.20", "O70.21", "O70.22", "O70.23", "O70.3", "O70.4",
                        "O70.9", "O71.02", "O71.03", "O71.1", "O74.0", "O74.1", "O74.2", "O74.3", "O74.4",
                        "O74.5", "O74.6", "O74.7", "O74.8", "O74.9", "O75.0", "O75.1", "O75.5", "O75.81",
                        "O75.89", "O75.9", "O77.0", "O77.1", "O77.8", "O77.9", --labor related
                        "O80", "O82", "O88.02",
                        "O88.12", "O88.22", "O88.32", "O88.82", "O90.0", "O98.02", "O98.12", "O98.22", "O98.32",
                        "O98.42", "O98.52", "O98.62", "O98.72", "O98.82", "O98.92", "O99.02", "O99.284",
                        "O99.314", "O99.324", "O99.344", "O99.354", "O99.42", "O99.52", "O99.62", "O99.72",
                        "O99.814", "O99.824", "O99.834", "O9A.12", "O9A.22", "O9A.32", "O9A.42", "O9A.52",
                        "Z37.0",
                        "Z37.1", "Z37.2", "Z37.3", "Z37.4", "Z37.50", "Z37.51", "Z3752", "Z3753", "Z3754",
                        "Z37.59", "Z37.60", "Z37.61", "Z37.62", "Z37.63", "Z37.64", "Z37.69", "Z37.7", "Z37.9",
                        "Z38.00", "Z38.01", "Z38.2", "Z38.30", "Z38.31", "Z38.5", "Z38.61", "Z38.62", "Z38.63",
                        "Z38.64", "Z38.65", "Z38.66", "Z38.68", "Z38.69", "Z38.8")
                    OR cpt_clm_ln[SAFE_OFFSET(0)] IN ("01960", "01961", "01967", "01968", "59409",
                        "59410", "59514", "59515", "59612", "59614", "59620", "59622")))
        ) AS clm
    LEFT JOIN
        (
            SELECT 
                asdb_member_key
                , asdb_plan_key
                , CASE WHEN guardian = "" THEN NULL ELSE guardian END AS guardian 
                , CAST(dob AS DATE) AS mom_dob
            FROM 
                `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_MEMBER`
        ) AS mem
            ON clm.asdb_member_key = mem.asdb_member_key
    LEFT JOIN
        baby
            ON mem.guardian = baby.guardian
            AND mem.asdb_plan_key = baby.asdb_plan_key
    WHERE 1 = 1
        AND ABS(DATE_DIFF(clm.asdb_incurred_dt, baby.baby_dob, DAY)) < 30
        AND baby.nicu_lvl IS NOT NULL
        AND CAST(FLOOR(DATE_DIFF(baby.baby_dob, mem.mom_dob, MONTH)/12) AS INT64) > 9
) --As of 9/25/2024 we have 73,121 moms with linked babies
, gest_age1 AS (
    SELECT
        mom.asdb_plan_key
        , mom.mom_key
        , mom.guardian
        , mom.mom_dob
        , mom.mom_age
        , mom.baby_key
        , mom.baby_dob
        , mom.nicu_lvl
        , clm.asdb_incurred_dt
        , CASE WHEN S.icd_code =  "Z3A.08" THEN 8
            WHEN S.icd_code = "Z3A.09" THEN 9
            WHEN S.icd_code = "Z3A.10" THEN 10
            WHEN S.icd_code = "Z3A.11" THEN 11
            WHEN S.icd_code = "Z3A.12" THEN 12
            WHEN S.icd_code = "Z3A.13" THEN 13
            WHEN S.icd_code = "Z3A.14" THEN 14
            WHEN S.icd_code = "Z3A.15" THEN 15
            WHEN S.icd_code = "Z3A.16" THEN 16
            WHEN S.icd_code = "Z3A.17" THEN 17
            WHEN S.icd_code = "Z3A.18" THEN 18
            WHEN S.icd_code = "Z3A.19" THEN 19
            WHEN S.icd_code = "Z3A.20" THEN 20
            WHEN S.icd_code = "Z3A.21" THEN 21
            WHEN S.icd_code = "Z3A.22" THEN 22
            WHEN S.icd_code = "Z3A.23" THEN 23
            WHEN S.icd_code = "Z3A.24" THEN 24
            WHEN S.icd_code = "Z3A.25" THEN 25
            WHEN S.icd_code = "Z3A.26" THEN 26
            WHEN S.icd_code = "Z3A.27" THEN 27
            WHEN S.icd_code = "Z3A.28" THEN 28
            WHEN S.icd_code = "Z3A.29" THEN 29
            WHEN S.icd_code = "Z3A.30" THEN 30
            WHEN S.icd_code = "Z3A.31" THEN 31
            WHEN S.icd_code = "Z3A.32" THEN 32
            WHEN S.icd_code = "Z3A.33" THEN 33
            WHEN S.icd_code = "Z3A.34" THEN 34
            WHEN S.icd_code = "Z3A.35" THEN 35
            WHEN S.icd_code = "Z3A.36" THEN 36
            WHEN S.icd_code = "Z3A.37" THEN 37
            WHEN S.icd_code = "Z3A.38" THEN 38
            WHEN S.icd_code = "Z3A.39" THEN 39     
            WHEN S.icd_code = "Z3A.40" THEN 40
            WHEN S.icd_code = "Z3A.41" THEN 41
            WHEN S.icd_code = "Z3A.42" THEN 42
            WHEN S.icd_code = "Z3A.49" THEN 43
            ELSE NULL END AS wks_gestation
    FROM
        mom
    LEFT JOIN
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_qc_all_diagnoses` AS clm
            ON mom.mom_key = clm.asdb_member_key
        , UNNEST(icd_vals) AS S
    WHERE 1 = 1
        AND S.icd_code LIKE "Z3A%"
        AND NOT S.icd_code IN ("Z3A.00", "Z3A.39", "Z3A.40")
)
, gest_age2 AS (
    SELECT    
        gest_age1.asdb_plan_key
        , gest_age1.mom_key
        , gest_age1.guardian
        , gest_age1.mom_dob
        , gest_age1.mom_age
        , gest_age1.baby_key
        , gest_age1.baby_dob
        , gest_age1.nicu_lvl    
        , DATE_ADD(gest_age1.asdb_incurred_dt, INTERVAL (40 - gest_age1.wks_gestation) WEEK) AS est_eop
        , DATE_DIFF(gest_age1.baby_dob, DATE_ADD(asdb_incurred_dt, INTERVAL (40 - wks_gestation) WEEK), DAY) AS eop_del_dif
        , ROW_NUMBER() 
            OVER(PARTITION BY gest_age1.baby_key, gest_age1.baby_dob 
                ORDER BY ABS(DATE_DIFF(gest_age1.baby_dob, DATE_ADD(baby_dob, INTERVAL (40 - gest_age1.wks_gestation) WEEK), DAY))) 
            AS rn
  FROM
      gest_age1
  WHERE 1 = 1
      AND NOT gest_age1.mom_key = 0
      AND gest_age1.wks_gestation IS NOT NULL
) -- 58,579 mom/baby pairs
, outcomes AS (
    SELECT
        gest_age2.asdb_plan_key
        , gest_age2.mom_key
        , gest_age2.guardian
        , gest_age2.mom_dob
        , gest_age2.mom_age
        , gest_age2.baby_key
        , gest_age2.baby_dob
        , gest_age2.nicu_lvl    
        , CAST(FLOOR((280 + gest_age2.eop_del_dif)/7) AS INT64) AS gest_age_at_birth
        , CASE WHEN DATE_DIFF(gest_age2.baby_dob, clm.asdb_incurred_dt, WEEK) < CAST(FLOOR((280 - gest_age2.eop_del_dif)/7) AS INT64)
                AND (S.icd_group = 110 OR T.icd_group = 110) THEN 1 ELSE 0                                               
            END AS current_pre_e
        , CASE WHEN DATE_DIFF(gest_age2.baby_dob, clm.asdb_incurred_dt, WEEK) < CAST(FLOOR((280 - gest_age2.eop_del_dif)/7) AS INT64)
                AND (S.icd_group = 110 OR T.icd_group = 110) THEN asdb_incurred_dt ELSE NULL                                            
            END AS current_pre_e_dt
        , CASE WHEN DATE_DIFF(gest_age2.baby_dob, clm.asdb_incurred_dt, MONTH) < CAST(FLOOR((280 - gest_age2.eop_del_dif)/7) AS INT64) 
                AND (S.icd_code LIKE "O24%" OR S.icd_group = 22 OR T.icd_code LIKE "O24%" OR T.icd_group = 22) THEN 1 ELSE 0                      
            END AS current_dm 
        , CASE WHEN DATE_DIFF(gest_age2.baby_dob, clm.asdb_incurred_dt, MONTH) < CAST(FLOOR((280 - gest_age2.eop_del_dif)/7) AS INT64) 
                AND (S.icd_code LIKE "O24%" OR S.icd_group = 22 OR T.icd_code LIKE "O24%" OR T.icd_group = 22) THEN asdb_incurred_dt ELSE NULL                       
            END AS current_dm_dt  
FROM 
    gest_age2
LEFT JOIN
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_qc_all_diagnoses` AS clm
        ON gest_age2.mom_key = clm.asdb_member_key
        AND gest_age2.baby_dob >= clm.asdb_incurred_dt
        , UNNEST(icd_vals) AS S
        , UNNEST(prindiag_vals) AS T
WHERE 1 = 1
    AND gest_age2.rn = 1
    AND gest_age2.eop_del_dif BETWEEN -123 AND 21
)
SELECT 
    outcomes.asdb_plan_key
    , outcomes.mom_key
    , outcomes.guardian
    , outcomes.mom_dob
    , outcomes.mom_age
    , outcomes.baby_key
    , outcomes.baby_dob
    , outcomes.nicu_lvl    
    , outcomes.gest_age_at_birth
    , GENERATE_DATE_ARRAY(DATE_SUB(baby_dob, INTERVAL (gest_age_at_birth - 8) WEEK), baby_dob, INTERVAL 1 WEEK) AS dates
    , MAX(outcomes.current_pre_e) AS preeclampsia
    , MIN(outcomes.current_pre_e_dt) AS preeclampsia_first_dt
    , MAX(outcomes.current_dm) AS diabetes
    , MIN(outcomes.current_dm_dt) AS diabetes_first_dt
FROM 
    outcomes
GROUP BY
    outcomes.asdb_plan_key
    , outcomes.mom_key
    , outcomes.guardian
    , outcomes.mom_dob
    , outcomes.mom_age
    , outcomes.baby_key
    , outcomes.baby_dob
    , outcomes.nicu_lvl 
    , outcomes.gest_age_at_birth
;--58,888 mom/baby pairs
--SELECT COUNT(nicu_lvl), nicu_lvl, EXTRACT(MONTH FROM baby_dob) AS mnth,EXTRACT(YEAR FROM baby_dob) AS yr  FROM `{GCP_PROJECT}.{GCP_DB}.a534354_final_timepoint` GROUP BY nicu_lvl, EXTRACT(MONTH FROM baby_dob), EXTRACT(YEAR FROM baby_dob) ORDER BY yr, mnth, nicu_lvl

-------------------------------------------------------
--- create longitudinal set for 8 weeks to delivery ---
-------------------------------------------------------
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_qc_longitudinal`
AS
WITH pre AS (
    SELECT
        index_date
        , DATE_DIFF(index_date, baby_dob, WEEK) + gest_age_at_birth  AS gest_age
        , asdb_plan_key
        , mom_key
        , guardian
        , mom_dob
        , mom_age
        , baby_key
        , baby_dob
        , nicu_lvl    
        , gest_age_at_birth
        , preeclampsia
        , preeclampsia_first_dt
        , diabetes
        , diabetes_first_dt
FROM
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_qc_final_timepoint`
    , UNNEST (dates) AS index_date
)
SELECT
    index_date
    , gest_age
    , asdb_plan_key
    , mom_key
    , guardian
    , mom_dob
    , mom_age
    , baby_key
    , baby_dob
    , nicu_lvl    
    , gest_age_at_birth
    , preeclampsia
    , CASE WHEN preeclampsia_first_dt < index_date OR preeclampsia_first_dt IS NULL THEN preeclampsia ELSE 0 END AS pre_e_at_index
    , preeclampsia_first_dt
    , CASE WHEN diabetes_first_dt < index_date OR diabetes_first_dt IS NULL THEN diabetes ELSE 0 END AS diabetes_at_index
    , diabetes
    , diabetes_first_dt
FROM 
    pre
ORDER BY
    mom_key
    , index_date
;
-------------------------------
--- predictors data pulling ---
-------------------------------
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_qc_risk_flags`
AS
WITH pre AS (
    SELECT
        mem.mom_key AS asdb_member_key
        , mem.index_date
        , mem.baby_dob 
        , CAST(FLOOR(DATE_DIFF(mem.index_date, mem.mom_dob, MONTH)/12) AS INT64) AS mom_age
        , mem2.ethnicity_desc
        , CASE WHEN asdb_incurred_dt < DATE_SUB(index_date, INTERVAL gest_age WEEK) AND
                    (S.icd_code LIKE "O24%" OR T.icd_code LIKE "O24%" OR 
                S.icd_group = 22 OR T.icd_group = 22) THEN 1 ELSE 0                           END AS prior_dm
        , CASE WHEN asdb_incurred_dt > DATE_SUB(index_date, INTERVAL gest_age WEEK) AND
                    (S.icd_code LIKE "O24%" OR T.icd_code LIKE "O24%" OR 
                S.icd_group = 22 OR T.icd_group = 22) THEN 1 ELSE 0                           END AS current_dm
        , CASE WHEN S.icd_code = "R73.03" OR T.icd_code = "R73.03" THEN 1 ELSE 0              END AS pre_dm
        , CASE WHEN S.icd_code = "Z83.3" OR T.icd_code = "Z83.3" THEN 1 ELSE 0                END AS f_hist_dm
        , CASE WHEN S.icd_code = "D68.61" OR T.icd_code = "D68.61" THEN 1 ELSE 0              END AS aps
        , CASE WHEN S.icd_code IN ("Z31.83", "N98.1") OR
                     T.icd_code IN ("Z31.83", "N98.1") OR 
                     EXISTS(SELECT * FROM UNNEST(cpt_vals) AS x WHERE x IN ("S4042")) OR 
                     EXISTS(SELECT * FROM UNNEST(cpt_clm_ln) AS x WHERE x IN ("S4042")) 
                     THEN 1 ELSE 0                                                            END AS art
        , CASE WHEN S.icd_group IN (181, 182) OR T.icd_group IN (181, 182) THEN 1 ELSE 0      END AS autoimmune
        , CASE WHEN S.icd_code = "Z87.59" OR T.icd_code = "Z87.59" OR
                    S.icd_code LIKE "O01%" OR T.icd_code LIKE "O01%" THEN 1 ELSE 0            END AS hist_ob_comp 
        , CASE WHEN asdb_incurred_dt < DATE_SUB(index_date, INTERVAL gest_age WEEK) AND 
                    (S.icd_group IN (10, 109) OR T.icd_group IN (10, 109)) THEN 1 ELSE 0      END AS prior_ht
    
        , CASE WHEN asdb_incurred_dt > DATE_SUB(index_date, INTERVAL gest_age WEEK) AND 
                    (S.icd_group IN (10, 109) OR T.icd_group IN (10, 109)) THEN 1 ELSE 0     END AS current_preg_ht
        , CASE WHEN asdb_incurred_dt < DATE_SUB(index_date, INTERVAL gest_age WEEK) AND 
                    (S.icd_group = 110 OR T.icd_group = 110) THEN 1 ELSE 0                   END AS prior_pre_e
        , CASE WHEN asdb_incurred_dt > DATE_SUB(index_date, INTERVAL gest_age WEEK) AND 
                    (S.icd_group = 110 OR T.icd_group = 110) THEN 1 ELSE 0                   END AS current_pre_e 
        , CASE WHEN S.icd_code LIKE "E66%" OR T.icd_code LIKE "E66%" THEN 1 ELSE 0           END AS obesity
        , CASE WHEN S.icd_code = "E28.2" OR T.icd_code = "E28.2" THEN 1 ELSE 0               END AS pcos
        , CASE WHEN S.icd_group IN (66, 67, 68, 234) OR
                    T.icd_group IN (66, 67, 68, 234) THEN 1 ELSE 0                           END AS renal
        , CASE WHEN S.icd_group = 257 OR T.icd_group = 257 THEN 1 ELSE 0                     END AS sle
        , CASE WHEN asdb_incurred_dt > DATE_SUB(index_date, INTERVAL gest_age WEEK)
                    AND (S.icd_group = 97 OR T.icd_group = 97)THEN 1 ELSE 0                  END AS multi
        , CASE WHEN asdb_incurred_dt > DATE_SUB(index_date, INTERVAL gest_age WEEK) AND 
                    (S.icd_group = 92 OR T.icd_group = 92) THEN 1 ELSE 0                     END AS bleeding_in_current_preg 
        , CASE WHEN S.icd_code LIKE "C58%" OR S.icd_code LIKE "O01%" OR
                    T.icd_code LIKE "C58%" OR T.icd_code LIKE "O01%" THEN 1 ELSE 0           END AS trophoblastic  
        , CASE WHEN S.icd_code LIKE "F10%" OR T.icd_code LIKE "F10%" OR
                    S.icd_code = "R78.0" OR T.icd_code = "R78.0"     THEN 1 ELSE 0           END AS Alcohol
        , CASE WHEN S.icd_code LIKE "F11%" OR T.icd_code LIKE "F11%" OR
                    S.icd_code = "R78.1" OR T.icd_code = "R78.1"     THEN 1 ELSE 0           END AS OUD
        , CASE WHEN S.icd_code LIKE "F12%" OR T.icd_code LIKE "F12%" THEN 1 ELSE 0           END AS Cannabis
        , CASE WHEN S.icd_code LIKE "F14%" OR T.icd_code LIKE "F14%" OR
                    S.icd_code = "R78.2" OR T.icd_code = "R78.2"     THEN 1 ELSE 0           END AS Cocaine
        , CASE WHEN S.icd_code LIKE "F17%" OR T.icd_code LIKE "F17%" OR
                    S.icd_code LIKE "O99.33%" OR T.icd_code LIKE "O99.33%"  THEN 1 ELSE 0    END AS Nicotine    
        , CASE WHEN S.icd_code LIKE "F13%" OR S.icd_code LIKE "F15%" OR 
                    S.icd_code LIKE "F16%" OR S.icd_code LIKE "F18%" OR 
                    S.icd_code LIKE "F19%" OR S.icd_code LIKE "F55%" OR 
                    S.icd_code LIKE "O99.32%" OR T.icd_code LIKE "F13%" OR 
                    T.icd_code LIKE "F15%" OR T.icd_code LIKE "F16%" OR 
                    T.icd_code LIKE "F18%" OR T.icd_code LIKE "F19%" OR 
                    T.icd_code LIKE "F55%" OR T.icd_code LIKE "O99.32%" OR
                    S.icd_code IN ("R78.3", "R78.4", "R78.5", "R78.6") OR 
                    T.icd_code IN ("R78.3", "R78.4", "R78.5", "R78.6") THEN 1 ELSE 0         END AS Other_drug  
    FROM
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_qc_longitudinal` AS mem
    LEFT JOIN
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_qc_all_diagnoses` AS clm
            ON mem.mom_key = clm.asdb_member_key
        , UNNEST (icd_vals) AS S
        , UNNEST(prindiag_vals) AS T
    LEFT JOIN
        `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_MEMBER` AS mem2
            ON mem.mom_key = mem2.asdb_member_key
    WHERE 1 = 1
        AND clm.asdb_incurred_dt < mem.index_date
)
SELECT
    asdb_member_key
    , index_date
    , baby_dob
    , mom_age
    , ethnicity_desc
    , MAX(prior_dm) AS prior_dm
    , MAX(current_dm) As current_dm
    , MAX(pre_dm) AS pre_dm
    , MAX(f_hist_dm) AS f_hist_dm
    , MAX(aps) AS aps
    , MAX(art) AS art
    , MAX(autoimmune) AS autoimmune
    , MAX(hist_ob_comp) AS hist_ob_comp
    , MAX(prior_ht) AS prior_ht
    , MAX(current_preg_ht) AS current_preg_ht
    , MAX(prior_pre_e) AS prior_pre_e
    , MAX(current_pre_e) AS current_pre_e
    , MAX(obesity) AS obesity
    , MAX(pcos) AS pcos
    , MAX(renal) AS renal
    , MAX(sle) AS sle
    , MAX(multi) AS multi
    , MAX(bleeding_in_current_preg) AS bleeding_in_current_preg
    , MAX(trophoblastic) AS trophoblastic
    , MAX(Alcohol) AS Alcohol
    , MAX(OUD) AS OUD
    , MAX(Cannabis) AS Cannabis
    , MAX(Cocaine) AS Cocaine
    , MAX(Nicotine) AS Nicotine
    , MAX(Other_drug) AS Other_drug
FROM
    pre
GROUP BY
    asdb_member_key
    , index_date
    , baby_dob
    , mom_age
    , ethnicity_desc
;

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_qc_risk_w_nicu_flags`
AS
SELECT
  risk.*
  , birth.nicu_lvl
  , CASE WHEN birth.nicu_lvl >= 2 THEN 1 ELSE 0 END AS nicu_flag
FROM
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_qc_final_timepoint` AS birth
LEFT JOIN
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_qc_risk_flags` AS risk
        ON birth.mom_key = risk.asdb_member_key
        AND birth.baby_dob = risk.baby_dob
WHERE
  risk.asdb_member_key IS NOT NULL
;


CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_v2_risk_w_nicu_flags_final_timepoint`
AS
SELECT
  *
FROM
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_qc_risk_w_nicu_flags` 
WHERE
  index_date = baby_dob
;