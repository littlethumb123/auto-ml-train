

--TODO: do a check of 12 month history pulling with and without icd array. Do a basic condition prevalence check too.

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_risk_flags`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
WITH pre AS (
SELECT
    asdb_member_key
    , delivery_dt
    , CASE WHEN DATE_DIFF(delivery_dt, asdb_incurred_dt, MONTH) >= 9 
        AND S.icd_code LIKE "O24%" OR S.icd_group = 22 THEN 1 ELSE 0                      END AS prior_dm
    , CASE WHEN DATE_DIFF(delivery_dt, asdb_incurred_dt, MONTH) < 9 
        AND S.icd_code LIKE "O24%" OR S.icd_group = 22 THEN 1 ELSE 0                      END AS current_dm
    , CASE WHEN S.icd_code = "R73.03" THEN 1 ELSE 0                                       END AS pre_dm
    , CASE WHEN S.icd_code = "Z83.3" THEN 1 ELSE 0                                        END AS f_hist_dm
    , CASE WHEN S.icd_code = "D68.61" THEN 1 ELSE 0                                       END AS aps
    , CASE WHEN S.icd_code IN ("Z31.83", "N98.1") OR 
        EXISTS(SELECT * FROM UNNEST(cpt_vals) AS x WHERE x IN ("S4042")) THEN 1 ELSE 0    END AS art
    , CASE WHEN S.icd_group IN (181, 182) THEN 1 ELSE 0                                   END AS autoimmune
    , CASE WHEN S.icd_code = "Z87.59" OR S.icd_code LIKE "O01%" THEN 1 ELSE 0             END AS hist_ob_comp
    , CASE WHEN DATE_DIFF(delivery_dt, asdb_incurred_dt, MONTH) >= 9 
        AND  S.icd_group IN (10, 109) THEN 1 ELSE 0                                       END AS prior_ht
    , CASE WHEN DATE_DIFF(delivery_dt, asdb_incurred_dt, MONTH) < 9 
        AND  S.icd_group IN (10, 109) THEN 1 ELSE 0                                       END AS current_preg_ht
    , CASE WHEN DATE_DIFF(delivery_dt, asdb_incurred_dt, MONTH) >= 9 
        AND S.icd_group = 110 THEN 1 ELSE 0                                               END AS prior_pre_e
    , CASE WHEN DATE_DIFF(delivery_dt, asdb_incurred_dt, MONTH) < 9 
        AND S.icd_group = 110 THEN 1 ELSE 0                                               END AS current_pre_e
    , CASE WHEN S.icd_code LIKE "E66%" THEN 1 ELSE 0                                          END AS obesity
    , CASE WHEN S.icd_code = "E28.2" THEN 1 ELSE 0                                        END AS pcos
    , CASE WHEN S.icd_group IN (66, 67, 68, 234) THEN 1 ELSE 0                            END AS renal
    , CASE WHEN S.icd_group = 257 THEN 1 ELSE 0                                           END AS sle
    , CASE WHEN DATE_DIFF(delivery_dt, asdb_incurred_dt, MONTH) <= 9
        AND S.icd_group = 97 THEN 1 ELSE 0                                                END AS multi
FROM
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_prior_diagnoses`
    , UNNEST(icd_vals) AS S
)
SELECT
    asdb_member_key
    , delivery_dt
    , MAX(prior_dm) AS prior_dm
    , MAX(current_dm) AS current_dm
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
FROM
    pre
GROUP BY
    asdb_member_key
    , delivery_dt
;

SELECT SUM(prior_dm) FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_risk_flags`; --2454
SELECT SUM(current_dm) FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_risk_flags`; --5556
SELECT SUM(current_dm) FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_risk_flags` WHERE prior_dm = 1; --1984

SELECT SUM(prior_ht) FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_risk_flags`; --4170
SELECT SUM(current_preg_ht) FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_risk_flags`; --6829
SELECT SUM(current_preg_ht) FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_risk_flags` WHERE prior_ht = 1; --2162

SELECT SUM(prior_pre_e) FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_risk_flags`; --1216
SELECT SUM(current_pre_e) FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_risk_flags`; --1338
SELECT SUM(current_pre_e) FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_risk_flags` WHERE prior_pre_e = 1; --171

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_risk_w_nicu_flags`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT
  risk.*
  , birth.nicu_max
  , CASE WHEN birth.nicu_max >= 2 THEN 1 WHEN birth.nicu_max IS NULL THEN NULL ELSE 0 END AS nicu_flag
FROM
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_deliveries_w_dob` AS birth
LEFT JOIN
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_risk_flags` AS risk
        ON birth.asdb_member_key = risk.asdb_member_key
        AND birth.baby_dob = risk.delivery_dt
WHERE
  risk.asdb_member_key IS NOT NULL
;




CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_gest_ages`
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
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_prior_diagnoses`
        , UNNEST(icd_vals) AS S
    WHERE 1 = 1
        AND S.icd_code LIKE "Z3A%"
        AND NOT S.icd_code IN ("Z3A.00", "Z3A.39", "Z3A.40")
),
pre2 AS (
  SELECT
      asdb_member_key
      , delivery_dt
      , asdb_incurred_dt
      , icd_code
      , CASE WHEN icd_code =  "Z3A.08" THEN 8
          WHEN icd_code = "Z3A.09" THEN 9
          WHEN icd_code = "Z3A.10" THEN 10
          WHEN icd_code = "Z3A.11" THEN 11
          WHEN icd_code = "Z3A.12" THEN 12
          WHEN icd_code = "Z3A.13" THEN 13
          WHEN icd_code = "Z3A.14" THEN 14
          WHEN icd_code = "Z3A.15" THEN 15
          WHEN icd_code = "Z3A.16" THEN 16
          WHEN icd_code = "Z3A.17" THEN 17
          WHEN icd_code = "Z3A.18" THEN 18
          WHEN icd_code = "Z3A.19" THEN 19
          WHEN icd_code = "Z3A.20" THEN 20
          WHEN icd_code = "Z3A.21" THEN 21
          WHEN icd_code = "Z3A.22" THEN 22
          WHEN icd_code = "Z3A.23" THEN 23
          WHEN icd_code = "Z3A.24" THEN 24
          WHEN icd_code = "Z3A.25" THEN 25
          WHEN icd_code = "Z3A.26" THEN 26
          WHEN icd_code = "Z3A.27" THEN 27
          WHEN icd_code = "Z3A.28" THEN 28
          WHEN icd_code = "Z3A.29" THEN 29
          WHEN icd_code = "Z3A.30" THEN 30
          WHEN icd_code = "Z3A.31" THEN 31
          WHEN icd_code = "Z3A.32" THEN 32
          WHEN icd_code = "Z3A.33" THEN 33
          WHEN icd_code = "Z3A.34" THEN 34
          WHEN icd_code = "Z3A.35" THEN 35
          WHEN icd_code = "Z3A.36" THEN 36
          WHEN icd_code = "Z3A.37" THEN 37
          WHEN icd_code = "Z3A.38" THEN 38
          WHEN icd_code = "Z3A.39" THEN 39     
          WHEN icd_code = "Z3A.40" THEN 40
          WHEN icd_code = "Z3A.41" THEN 41
          WHEN icd_code = "Z3A.42" THEN 42
          WHEN icd_code = "Z3A.49" THEN 43
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
      , DATE_SUB(asdb_incurred_dt, INTERVAL (wks_gestation - 8) WEEK) AS est_edc_plus_8
      , DATE_ADD(asdb_incurred_dt, INTERVAL (40 - wks_gestation) WEEK) AS est_eop
      , DATE_DIFF(delivery_dt, DATE_ADD(asdb_incurred_dt, INTERVAL (40 - wks_gestation) WEEK), DAY) AS eop_del_dif
      , ROW_NUMBER() 
          OVER(PARTITION BY asdb_member_key, delivery_dt 
              ORDER BY ABS(DATE_DIFF(delivery_dt, DATE_ADD(asdb_incurred_dt, INTERVAL (40 - wks_gestation) WEEK), DAY))) 
          AS rn
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
ORDER BY
    eop_del_dif DESC;


CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_last_date_before_delivery`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
WITH pre AS (
SELECT DISTINCT
    asdb_member_key
    , delivery_dt
    , asdb_incurred_dt
    , icd_code
    , wks_gestation
    , est_edc_plus_8
    , est_eop
    , eop_del_dif
    , COUNT(*) OVER (PARTITION BY asdb_member_key) AS z_codes
    , ROW_NUMBER() OVER (PARTITION BY asdb_member_key ORDER BY ABS(eop_del_dif) ASC) AS rn
FROM
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_gest_ages`
)
SELECT
    * EXCEPT(rn)
FROM
    pre
WHERE 
    rn = 1
ORDER BY
  eop_del_dif DESC
;

SELECT COUNT(DISTINCT asdb_member_key) FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_last_date_before_delivery` WHERE eop_del_dif >= -126;
--38,693 (66.6%)

SELECT AVG(eop_del_dif) FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_last_date_before_delivery` WHERE eop_del_dif >= -126;
--15.36373504251398


SELECT
  eop_del_dif[OFFSET(1)] AS p1,
  eop_del_dif[OFFSET(10)] AS p10,
  eop_del_dif[OFFSET(25)] AS p25,
  eop_del_dif[OFFSET(50)] AS p50,
  eop_del_dif[OFFSET(75)] AS p75,
  eop_del_dif[OFFSET(90)] AS p90,
  eop_del_dif[OFFSET(99)] AS p99
FROM 
(
  SELECT 
        APPROX_QUANTILES(eop_del_dif, 100) AS eop_del_dif
  FROM 
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_last_date_before_delivery`
)
;










-----------------
--- keep for useful code
----------


CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_icd_20240913`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
WITH pre AS (
    SELECT
        asdb_plan_key
        , claimid
        , CASE WHEN SUBSTR(TRIM(UPPER(codeid)), 4, 1) = "." THEN TRIM(UPPER(codeid))
            WHEN SUBSTR(TRIM(codeid), 4, 9) IS NULL THEN TRIM(UPPER(codeid))
            ELSE CONCAT(SUBSTR(TRIM(UPPER(codeid)), 1, 3), ".", SUBSTR(TRIM(codeid), 5, 9)) END AS codeid
    FROM
        `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_ASDB_CLAIMDIAG`
        --`edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_ASDB_CLAIMDIAGSUMMARY`
)
SELECT 
 asdb_plan_key
 , claimid
 , ARRAY_AGG(DISTINCT codeid IGNORE NULLS) icd_vals
FROM 
    pre

/*UNNEST ([icddxpri
        , icddxsec1
        , icddxsec2
        , icddxsec3
        , icddxsec4
        , icddxsec5
        , icddxsec6
        , icddxsec7
        , icddxsec8
        , icddxsec9
        , icddxsec10
        , icddxsec11
        , icddxsec12
        , icddxsec13
        , icddxsec14
        , icddxsec15
        , icddxsec16
        , icddxsec17
        , icddxsec18
        , icddxsec19
        , icddxsec20
        , icddxsec21
        , icddxsec22
        , icddxsec23
        , icddxsec24
        , icddxsec25
        , icddxsec26
        , icddxsec27
        , icddxsec28
        , icddxsec29
        , icddxsec30]) cols

***USE THIS SYNTAX IF YOU NEED TO ARRAY OVER A SET OF COLUMNS ***
*/
GROUP BY 
    claimid
    , asdb_plan_key
;
