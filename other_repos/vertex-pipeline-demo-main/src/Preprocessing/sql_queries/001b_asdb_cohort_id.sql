---------------------------------------------------------------------------------------------------------------------------------------
--- pull all relevant information into a single table with the DM and pre-e outcomes (and first date within pregnancy of diagnosis) ---
---------------------------------------------------------------------------------------------------------------------------------------
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_final_timepoint`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
WITH baby AS (
    SELECT DISTINCT 
        c.asdb_member_key
        , c.asdb_plan_key
        , a.member_id
        , c.guardian
        , a.med_case_start_dt AS baby_dob
        , CASE WHEN revenue_cd = "174" THEN 4
            WHEN revenue_cd = "173" THEN 3
            WHEN revenue_cd = "172" THEN 2
            WHEN revenue_cd = "171" THEN 1
            ELSE 0 END AS nicu_lvl
    FROM
        `anbc-hcb-prod.cm_medicaid_hcb_prod.MEDICAL_CASE_MEDICAID` AS a
    LEFT JOIN
        `edp-prod-hcbstorage.edp_hcb_mdcd_core_cnsv.ALT_ID_XWALK` AS b
            ON a.member_id = b.member_id
    LEFT JOIN
        `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_MEMBER` AS c
            ON CAST(b.src_indvdl_id AS INT) = c.iodb_member_key
    WHERE 1 = 1
        AND a.med_case_start_dt BETWEEN {DOB_ST} AND {DOB_END}
        AND revenue_cd IN ('170', '171', '172', '173', '174', '179')
        AND guardian IS NOT NULL
)
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
                `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_diagnoses`
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
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_diagnoses` AS clm
            ON mom.mom_key = clm.asdb_member_key
        , UNNEST(icd_vals) AS S
    WHERE 1 = 1
        AND S.icd_code LIKE "Z3A%"
        AND NOT S.icd_code IN ("Z3A.0", "Z3A.00", "Z3A.1", "Z3A.2", "Z3A.3", "Z3A.4")
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
                    AND (S.icd_code LIKE "O60.0%" OR T.icd_code LIKE "O60.0%" OR
                     S.icd_code LIKE "O60.2%" OR T.icd_code LIKE "O60.2%"
                    ) THEN 1 ELSE 0                                                           END AS pre_term_labor_clm
        , CASE WHEN DATE_DIFF(gest_age2.baby_dob, clm.asdb_incurred_dt, WEEK) < CAST(FLOOR((280 - gest_age2.eop_del_dif)/7) AS INT64)
                    AND (S.icd_code LIKE "O60.0%" OR T.icd_code LIKE "O60.0%" OR
                     S.icd_code LIKE "O60.2%" OR T.icd_code LIKE "O60.2%"
                    ) THEN asdb_incurred_dt ELSE NULL                                         END AS pre_term_labor_clm_dt
        , CASE WHEN DATE_DIFF(gest_age2.baby_dob, clm.asdb_incurred_dt, WEEK) < CAST(FLOOR((280 - gest_age2.eop_del_dif)/7) AS INT64)
                    AND (S.icd_code LIKE "O42.01%" OR T.icd_code LIKE "O42.01%" OR
                     S.icd_code LIKE "O42.11%" OR T.icd_code LIKE "O42.11%" OR
                     S.icd_code LIKE "O42.91%" OR T.icd_code LIKE "O42.91%" OR
                     S.icd_code LIKE "O60.1%" OR T.icd_code LIKE "O60.1%" OR
                     S.icd_code LIKE "P07.2%" OR T.icd_code LIKE "P07.2%" OR
                     S.icd_code LIKE "P07.3%" OR T.icd_code LIKE "P07.3%"
                    ) THEN 1 ELSE 0                                                           END AS pre_term_delivery_clm
        , CASE WHEN DATE_DIFF(gest_age2.baby_dob, clm.asdb_incurred_dt, WEEK) < CAST(FLOOR((280 - gest_age2.eop_del_dif)/7) AS INT64)
                    AND (S.icd_code LIKE "O42.01%" OR T.icd_code LIKE "O42.01%" OR
                     S.icd_code LIKE "O42.11%" OR T.icd_code LIKE "O42.11%" OR
                     S.icd_code LIKE "O42.91%" OR T.icd_code LIKE "O42.91%" OR
                     S.icd_code LIKE "O60.1%" OR T.icd_code LIKE "O60.1%" OR
                     S.icd_code LIKE "P07.2%" OR T.icd_code LIKE "P07.2%" OR
                     S.icd_code LIKE "P07.3%" OR T.icd_code LIKE "P07.3%"
                    ) THEN asdb_incurred_dt ELSE NULL                                         END AS pre_term_delivery_clm_dt
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
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_diagnoses` AS clm
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
    , MAX(outcomes.pre_term_labor_clm) AS pre_term_labor_clm
    , MIN(outcomes.pre_term_labor_clm_dt) AS pre_term_labor_clm_dt
    , MAX(outcomes.pre_term_delivery_clm) AS pre_term_delivery_clm
    , MIN(outcomes.pre_term_delivery_clm_dt) AS pre_term_delivery_clm_dt
    , CASE WHEN MAX(pre_term_labor_clm) = 1 OR MAX(pre_term_delivery_clm) = 1 THEN 1 ELSE 0 END AS pre_term
    , CASE 
        WHEN MIN(outcomes.pre_term_labor_clm_dt) IS NULL THEN MIN(outcomes.pre_term_delivery_clm_dt)
        WHEN MIN(outcomes.pre_term_delivery_clm_dt) IS NULL THEN MIN(outcomes.pre_term_labor_clm_dt)
        ELSE LEAST(MIN(outcomes.pre_term_labor_clm_dt), MIN(outcomes.pre_term_delivery_clm_dt))
      END AS pre_term_dt
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
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_longitudinal`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
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
        , pre_term
        , pre_term_dt
FROM
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_final_timepoint`
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
    , pre_term
    , CASE WHEN pre_term_dt < index_date OR pre_term_dt IS NULL THEN pre_term ELSE 0 END AS pre_term_at_index    
    , pre_term_dt    
FROM 
    pre
ORDER BY
    mom_key
    , index_date
;
--1,815,426 rows; keep in mind this includes multi-gestational infants...

--------------------------------------
-- simple table for standard pulls ---
--------------------------------------
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT DISTINCT
    mom_key AS asdb_member_key
    , asdb_plan_key
    , index_date AS index_dt
FROM
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_longitudinal`
;
--1,763,026 rows