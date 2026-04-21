----------------------------------------
--- births June 1 2022- July 31 2024 ---
----------------------------------------
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_babies`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
WITH pre AS (   
    SELECT
        clm.asdb_plan_key
        , clm.asdb_member_key
        , mem.guardian
        , MIN(CAST(clm.asdb_incurred_dt AS date)) AS asdb_incurred_dt
        , mem.dob
        , clm.revcode
        , CASE WHEN clm.revcode = "0174" THEN 4
            WHEN clm.revcode = "0173" THEN 3
            WHEN clm.revcode = "0172" THEN 2
            WHEN clm.revcode = "0171" THEN 1
            ELSE 0 END AS nicu_lvl
    FROM 
        `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_CLM_DATA_STAGE` AS clm
    LEFT JOIN
        (SELECT asdb_member_key, guardian, dob FROM `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_MEMBER`) AS mem
            ON clm.asdb_member_key = mem.asdb_member_key
    WHERE CAST(asdb_incurred_dt AS DATE) BETWEEN "2022-06-01" AND "2024-07-31"
        AND final_claim = 1
        AND TRIM(UPPER(status_header)) = "PAID"
        AND status_detail NOT IN ("DENY", "DENIED")
        AND revcode IN ("0170", "0171", "0172", "0173", "0174", "0179")
    GROUP BY
        asdb_plan_key
        , asdb_member_key
        , revcode
        , guardian
        , dob
)
SELECT
    asdb_plan_key
    , asdb_member_key
    , guardian
    , asdb_incurred_dt
    , dob AS baby_dob
    , MAX( nicu_lvl) AS nicu_max
FROM
    pre
GROUP BY
    asdb_plan_key
    , asdb_member_key
    , guardian
    , asdb_incurred_dt
    , dob
;
--120,474 babies

--------------------------------------------
--- deliveries June 1 2022- July 31 2024 ---
--------------------------------------------
--extra dates (want cohort delivered by end of May 2024 to account for bundle billing that includes the 6-week postpartum visit...
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_deliveries_w_dob`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT DISTINCT
    clm.asdb_plan_key
    , clm.asdb_member_key
    --, CAST(clm.asdb_incurred_dt AS DATE) AS asdb_incurred_dt
    , mem.guardian
    , CAST(baby.baby_dob AS DATE) AS baby_dob
    , MAX(baby.nicu_max) AS nicu_max
    , baby.asdb_member_key AS baby_key
    , 
FROM `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_CLM_DATA_STAGE` AS clm
LEFT JOIN
    (SELECT asdb_member_key, asdb_plan_key, CASE WHEN guardian = "" THEN NULL ELSE guardian END AS guardian FROM `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_MEMBER`) AS mem
        ON clm.asdb_member_key = mem.asdb_member_key
LEFT JOIN
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_babies` AS baby
        ON mem.guardian = baby.guardian
        AND mem.asdb_plan_key = baby.asdb_plan_key
WHERE 1 = 1
    AND (ABS(DATE_DIFF(CAST(clm.asdb_incurred_dt AS DATE), CAST(baby.baby_dob AS DATE), DAY)) < 30
        OR baby.baby_dob IS NULL)
    AND NOT clm.asdb_member_key = 0
    AND CAST(clm.asdb_incurred_dt AS DATE) BETWEEN "2022-06-01" AND "2024-07-31"
    AND clm.final_claim = 1
    AND TRIM(UPPER(clm.status_header)) = "PAID"
    AND clm.status_detail NOT IN ("DENY", "DENIED")
    AND (clm.asdb_coe_id = 10000
        AND (clm.revcode IN ("0112", "0122", "0132", "0142", "0152", "112", "122", "132", "142", "152")
            OR clm.prindiag IN (
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
            OR clm.servcode IN ("01960", "01961", "01967", "01968", "59409",
                "59410", "59514", "59515", "59612", "59614", "59620", "59622")
                ))
GROUP BY
    clm.asdb_plan_key
    , clm.asdb_member_key
    --, asdb_incurred_dt
    , mem.guardian
    , baby.baby_dob
    , baby.asdb_member_key
ORDER BY
    clm.asdb_member_key
    , baby_dob
;
--97,631


CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_delivery_dates`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT
    clm.asdb_plan_key
    , clm.asdb_member_key
    , clm.carriermemid
    , CAST(clm.asdb_incurred_dt AS date) AS asdb_incurred_dt
    , clm.prindiag
    , clm.servcode
    , mem.guardian
FROM 
    `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_CLM_DATA_STAGE` AS clm
LEFT JOIN
    (SELECT asdb_member_key, guardian FROM `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_MEMBER`) AS mem
        ON clm.asdb_member_key = mem.asdb_member_key
WHERE CAST(asdb_incurred_dt AS DATE) BETWEEN "2022-06-01" AND "2024-05-31"
    AND final_claim = 1
    AND TRIM(UPPER(status_header)) = "PAID"
    AND status_detail NOT IN ("DENY", "DENIED")
    AND (asdb_coe_id = 10000
        AND (revcode IN ("0112", "0122", "0132", "0142", "0152", "112", "122", "132", "142", "152")
            OR prindiag IN (
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
            OR servcode IN ("01960", "01961", "01967", "01968", "59409",
                "59410", "59514", "59515", "59612", "59614", "59620", "59622")))
;

SELECT COUNT(DISTINCT asdb_member_key) FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_delivery_dates` WHERE 
    --servcode IN ("01960", "01961", "01967", "01968", "59409", "59410", "59514", "59515", "59612", "59614", "59620", "59622")
    --prindiag IN ("O10.02", "O10.12", "O10.22", "O10.32", "O10.42", "O10.92", "O11.4", "O13.4", "O16.4") 
    --prindiag IN ("O14.04", "O14.14", "O14.24", "O14.94")
    asdb_incurred_dt > "2023-06-01";
--88,557 deliveries in 2 years
-- 7,504 (8.5%) members with HT
-- 4,218 (4.8%) with diabetes

--44,099 deliveries in 1 year
-- 3,723 (8.4%) with HT
-- 2,099 (4.8%) with diabetes

--Getting a sense of history
--SELECT * FROM `edp-prod-hcbstorage.edp_hcb_anbor_enrsrc.T_EDW_BASE_ICD9_DIAGNOSIS` WHERE icd9_dx_group_nbr = 110;



CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_mom_baby_link` 
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
WITH tmp AS (
  SELECT 
    a.asdb_member_key AS baby_asdb_member_key
    , a.memid AS baby_memid
    , a.guardian
    , a.dob AS baby_dob
  FROM 
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_babies` AS b
  LEFT JOIN
    `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_MEMBER` AS a
      ON b.asdb_member_key = a.asdb_member_key
)
SELECT DISTINCT
    a.asdb_member_key AS mom_asdb_member_key
    , a.memid AS mom_memid
    , a.guardian
    , a.dob AS mom_dob
    , a.age_in_mths_no AS mom_age_in_mths
    , tmp.baby_asdb_member_key
    , tmp.baby_memid
    , tmp.baby_dob
FROM 
  `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_MEMBER` AS a 
LEFT JOIN
  tmp
    ON a.guardian = tmp.guardian
WHERE 
  a.guardian IN (SELECT DISTINCT tmp.guardian FROM tmp)
  --AND a.age_in_mths_no >= 168
  AND a.guardian IS NOT NULL
  AND NOT TRIM(a.guardian) = ""
  AND TRIM(a.gender) = "F"
  AND a.asdb_member_key IN(SELECT asdb_member_key FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_deliveries_w_dob`)
ORDER BY
 a.asdb_member_key
 , tmp.baby_dob
;
-- 98,548 in mom table (high due to including June for accidental claim misdating) for 1 extra month
--102,283 in mom table for 2 extra months
--120,474 babies in baby table
--70,591 in link table (approx 75% of deliveries?)






CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_pre_ICD_CPT`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT DISTINCT 
  d.asdb_member_key
  , CAST(clm.asdb_incurred_dt AS DATE) AS asdb_incurred_dt
  , d.asdb_incurred_dt AS delivery_dt
  , clm.prindiag
  , clm.servcode 
FROM 
  `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_delivery_dates` AS d
LEFT JOIN 
  `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_CLM_DATA_STAGE` AS clm
    ON d.asdb_member_key = clm.asdb_member_key
    AND d.asdb_incurred_dt > CAST(clm.asdb_incurred_dt AS DATE)
WHERE 1 = 1 
  AND final_claim = 1
  AND TRIM(UPPER(status_header)) = "PAID"
  AND TRIM(UPPER(status_detail)) NOT IN ("DENY", "DENIED");


--- NOTE: 2-year cohort ---
--total     n = 86,530
--APS       n =     47
--ART       n =     27
--PCOS      n =  1,287
--pre-DM    n =    781
--f-hist DM n =    151
--Z87.59    n =  2,009

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_icd_20240913`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
WITH pre AS (
    SELECT
        asdb_plan_key
        , claimid
        , CASE WHEN LENGTH(TRIM(codeid)) = 3 THEN TRIM(UPPER(codeid))
            WHEN SUBSTR(TRIM(UPPER(codeid)), 4, 1) = "." THEN TRIM(UPPER(codeid))
            ELSE CONCAT(SUBSTR(TRIM(UPPER(codeid)), 1, 3), ".", SUBSTR(TRIM(codeid), 5, 9)) END AS codeid
    FROM
        `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_ASDB_CLAIMDIAG`
)
, pre2 AS (
    SELECT DISTINCT
        pre.*
        , grp.ICD9_DX_GROUP_NBR AS icd_group
    FROM
        pre
    LEFT JOIN
        (SELECT ICD9_DX_GROUP_NBR, ICD9_DX_CD FROM `edp-prod-hcbstorage.edp_hcb_anbor_enrsrcv.EDW_ICD9_DIAGNOSIS`) AS grp
          ON TRIM(UPPER(pre.codeid)) = TRIM(UPPER(grp.ICD9_DX_CD))
)
SELECT 
 asdb_plan_key
 , claimid
 , ARRAY_AGG(STRUCT(pre2.codeid AS icd_code, pre2.icd_group AS icd_group)) icd_vals
FROM 
    pre2
GROUP BY 
    claimid
    , asdb_plan_key
;

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_prior_diagnoses`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT
    mem.asdb_member_key
    , mem.baby_dob AS delivery_dt
    , clm.asdb_incurred_dt
    , COALESCE(icd.claimid, clm.claimid) AS claimid
    , COALESCE(icd.asdb_plan_key, clm.asdb_plan_key) AS asdb_plan_key
    , icd.icd_vals
    , clm.prindiag
    , clm.cpt_vals
FROM 
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_deliveries_w_dob` AS mem
LEFT JOIN 
    (
        SELECT 
            asdb_member_key
            , CAST(asdb_incurred_dt AS DATE) AS asdb_incurred_dt
            , claimid
            , asdb_plan_key 
            , ARRAY_AGG(DISTINCT servcode IGNORE NULLS) AS cpt_vals
            , prindiag
        FROM 
            `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_CLM_DATA_STAGE` 
        WHERE 1 = 1 
            AND final_claim = 1
            AND TRIM(UPPER(status_header)) = "PAID"
            AND TRIM(UPPER(status_detail)) NOT IN ("DENY", "DENIED")
        GROUP BY
            asdb_member_key
            , asdb_incurred_dt
            , claimid
            , asdb_plan_key
            , prindiag
    ) AS clm
        ON mem.asdb_member_key = clm.asdb_member_key
        AND mem.baby_dob> clm.asdb_incurred_dt
LEFT JOIN 
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_icd_20240913` AS icd
        ON clm.claimid = icd.claimid
        AND clm.asdb_plan_key = icd.asdb_plan_key
WHERE clm.asdb_incurred_dt IS NOT NULL
;

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_baby_ICDs`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT
    mem.baby_key AS asdb_member_key
    , mem.baby_dob AS delivery_dt
    , clm.asdb_incurred_dt
    , COALESCE(icd.claimid, clm.claimid) AS claimid
    , COALESCE(icd.asdb_plan_key, clm.asdb_plan_key) AS asdb_plan_key
    , icd.icd_vals
    , clm.prindiag
    , clm.cpt_vals
FROM 
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_deliveries_w_dob` AS mem
LEFT JOIN 
    (
        SELECT 
            asdb_member_key
            , CAST(asdb_incurred_dt AS DATE) AS asdb_incurred_dt
            , claimid
            , asdb_plan_key 
            , ARRAY_AGG(DISTINCT servcode IGNORE NULLS) AS cpt_vals
            , prindiag
        FROM 
            `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_CLM_DATA_STAGE` 
        WHERE 1 = 1 
            AND final_claim = 1
            AND TRIM(UPPER(status_header)) = "PAID"
            AND TRIM(UPPER(status_detail)) NOT IN ("DENY", "DENIED")
        GROUP BY
            asdb_member_key
            , asdb_incurred_dt
            , claimid
            , asdb_plan_key
            , prindiag
    ) AS clm
        ON mem.asdb_member_key = clm.asdb_member_key
LEFT JOIN 
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_icd_20240913` AS icd
        ON clm.claimid = icd.claimid
        AND clm.asdb_plan_key = icd.asdb_plan_key
WHERE clm.asdb_incurred_dt IS NOT NULL
;


CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_gest_age_baby`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
WITH pre AS (
    SELECT
        asdb_member_key
        , delivery_dt
        , asdb_incurred_dt
        , S.icd_code AS icd_code
    FROM 
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_baby_ICDs`
        , UNNEST(icd_vals) AS S
    WHERE 1 = 1
        AND S.icd_code LIKE "P07%" OR S.icd_code LIKE "P08%"
        --AND NOT S.icd_code IN ("Z3A.00", "Z3A.39", "Z3A.40")
),
pre2 AS (
  SELECT
      asdb_member_key
      , delivery_dt
      , asdb_incurred_dt
      , icd_code
      , CASE WHEN icd_code = "P07.21" THEN 22
          WHEN icd_code = "P07.22" THEN 23
          WHEN icd_code = "P07.23" THEN 24
          WHEN icd_code = "P07.24" THEN 25
          WHEN icd_code = "P07.25" THEN 26
          WHEN icd_code = "P07.26" THEN 27
          WHEN icd_code = "P07.31" THEN 28
          WHEN icd_code = "P07.32" THEN 29
          WHEN icd_code = "P07.33" THEN 30
          WHEN icd_code = "P07.34" THEN 31
          WHEN icd_code = "P07.35" THEN 32
          WHEN icd_code = "P07.36" THEN 33
          WHEN icd_code = "P07.37" THEN 34
          WHEN icd_code = "P07.38" THEN 35
          WHEN icd_code = "P07.39" THEN 36
          WHEN icd_code = "P08.2" THEN 42
          WHEN icd_code = "P08.21" THEN 42
          WHEN icd_code = "P08.22" THEN 42
          ELSE NULL END AS wks_gestation
  FROM
    pre
)
, pre3 AS (
  SELECT
      asdb_member_key
      , delivery_dt
      , asdb_incurred_dt
      , icd_code
      , wks_gestation
      , CASE WHEN wks_gestation <= 36 THEN "preterm"
          WHEN wks_gestation = 42 THEN "late term"
          ELSE "not specified" END AS gestation_cat
      , ROW_NUMBER() 
          OVER(PARTITION BY asdb_member_key, delivery_dt) AS rn
  FROM
      pre2
  WHERE 1 = 1
      AND NOT asdb_member_key = 0
      AND wks_gestation IS NOT NULL
      AND DATE_DIFF(delivery_dt, asdb_incurred_dt, MONTH) <= 10
)
SELECT
    * EXCEPT(rn)
FROM 
    pre3
WHERE rn = 1
;





--SELECT COUNT(DISTINCT asdb_member_key) FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_prior_diagnoses`;
--44099
--SELECT COUNT(DISTINCT asdb_member_key) FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_prior_diagnoses` WHERE asdb_plan_key IS NOT NULL;
--42891
-- SELECT COUNT(DISTINCT asdb_member_key) FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_prior_diagnoses` 
-- WHERE EXISTS(SELECT * FROM UNNEST(icd_vals) AS x WHERE x = "Z87.59");

--total     n = 43,094
--APS       n =     70   /    23
--PCOS      n =  1,301   /   713
--pre-DM    n =    994   /   485
--f-hist DM n =  1,670   /    84
--Z87.59    n =  4,711   / 1,044
--E10/11    n =  1,588   /   911
--auto      n =    674
--ht        n =  8,923 (20.7%)

