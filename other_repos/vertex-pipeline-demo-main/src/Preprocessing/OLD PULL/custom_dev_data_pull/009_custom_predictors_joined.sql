-------------------------------
--- predictors data pulling ---
-------------------------------
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_asdb_risk_flags`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
    SELECT
        mem.mom_key AS asdb_member_key
        , mem.index_date
        , mem.baby_dob 
        , CAST(FLOOR(DATE_DIFF(mem.index_date, mem.mom_dob, MONTH)/12) AS INT64) AS mom_age
        , mem2.ethnicity_desc
        , CASE WHEN asdb_incurred_dt < DATE_SUB(index_date, INTERVAL gest_age WEEK) AND
                    (S.icd_code LIKE "O60.0%" OR T.icd_code LIKE "O60.0%" OR
                     S.icd_code LIKE "O60.2%" OR T.icd_code LIKE "O60.2%"
                    ) THEN 1 ELSE 0                                                           END AS pre_term_labor_clm
        , CASE WHEN asdb_incurred_dt < DATE_SUB(index_date, INTERVAL gest_age WEEK) AND
                    (S.icd_code LIKE "O42.01%" OR T.icd_code LIKE "O42.01%" OR
                     S.icd_code LIKE "O42.11%" OR T.icd_code LIKE "O42.11%" OR
                     S.icd_code LIKE "O42.91%" OR T.icd_code LIKE "O42.91%" OR
                     S.icd_code LIKE "O60.1%" OR T.icd_code LIKE "O60.1%" OR
                     S.icd_code LIKE "P07.2%" OR T.icd_code LIKE "P07.2%" OR
                     S.icd_code LIKE "P07.3%" OR T.icd_code LIKE "P07.3%"
                    ) THEN 1 ELSE 0                                                           END AS pre_term_delivery_clm
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
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_longitudinal` AS mem
    LEFT JOIN
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_diagnoses` AS clm --change to _asdb_diagnoses once created
            ON mem.mom_key = clm.asdb_member_key
        , UNNEST (icd_vals) AS S
        , UNNEST(prindiag_vals) AS T
    LEFT JOIN
        `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_MEMBER` AS mem2
            ON mem.mom_key = mem2.asdb_member_key
    WHERE 1 = 1
        AND clm.asdb_incurred_dt < mem.index_date
;
--1,085,489,432 rows

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_kmdo_risk_flags`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
    SELECT
        mem.mom_key AS asdb_member_key
        , mem.index_date
        , mem.baby_dob 
        , CAST(FLOOR(DATE_DIFF(mem.index_date, mem.mom_dob, MONTH)/12) AS INT64) AS mom_age
        , mem2.ethnicity_desc
        , CASE WHEN clm.service_from < DATE_SUB(index_date, INTERVAL gest_age WEEK) AND
                    (icd.icd9_dx_cd LIKE "O60.0%" OR icd.icd9_dx_cd LIKE "O60.2%") 
                    THEN 1 ELSE 0                                                             END AS pre_term_labor_clm
        , CASE WHEN clm.service_from < DATE_SUB(index_date, INTERVAL gest_age WEEK) AND
                    (icd.icd9_dx_cd LIKE "O42.01%" OR icd.icd9_dx_cd LIKE "O42.11%" OR
                     icd.icd9_dx_cd LIKE "O42.91%" OR icd.icd9_dx_cd LIKE "O60.1%" OR
                     icd.icd9_dx_cd LIKE "P07.2%" OR icd.icd9_dx_cd LIKE "P07.3%"
                    ) THEN 1 ELSE 0                                                           END AS pre_term_delivery_clm
        , CASE WHEN clm.service_from < DATE_SUB(index_date, INTERVAL gest_age WEEK) AND
                    (icd.icd9_dx_cd LIKE "O24%" OR icd.icd_group = 22) THEN 1 ELSE 0          END AS prior_dm
        , CASE WHEN clm.service_from > DATE_SUB(index_date, INTERVAL gest_age WEEK) AND
                    (icd.icd9_dx_cd LIKE "O24%" OR icd.icd_group = 22) THEN 1 ELSE 0          END AS current_dm
        , CASE WHEN icd.icd9_dx_cd = "R73.03" THEN 1 ELSE 0                                   END AS pre_dm
        , CASE WHEN icd.icd9_dx_cd = "Z83.3" THEN 1 ELSE 0                                    END AS f_hist_dm
        , CASE WHEN icd.icd9_dx_cd = "D68.61" THEN 1 ELSE 0                                   END AS aps
        , CASE WHEN icd.icd9_dx_cd IN ("Z31.83", "N98.1") OR clm.procedure = "S4042"
                     THEN 1 ELSE 0                                                            END AS art
        , CASE WHEN icd.icd_group IN (181, 182) THEN 1 ELSE 0                                 END AS autoimmune
        , CASE WHEN icd.icd9_dx_cd = "Z87.59" OR
                    icd.icd9_dx_cd LIKE "O01%" THEN 1 ELSE 0                                  END AS hist_ob_comp 
        , CASE WHEN clm.service_from < DATE_SUB(index_date, INTERVAL gest_age WEEK) AND 
                    (icd.icd_group IN (10, 109)) THEN 1 ELSE 0                                END AS prior_ht
    
        , CASE WHEN clm.service_from > DATE_SUB(index_date, INTERVAL gest_age WEEK) AND 
                    (icd.icd_group IN (10, 109)) THEN 1 ELSE 0                                END AS current_preg_ht
        , CASE WHEN clm.service_from < DATE_SUB(index_date, INTERVAL gest_age WEEK) AND 
                    (icd.icd_group = 110) THEN 1 ELSE 0                                       END AS prior_pre_e
        , CASE WHEN clm.service_from > DATE_SUB(index_date, INTERVAL gest_age WEEK) AND 
                    (icd.icd_group = 110) THEN 1 ELSE 0                                       END AS current_pre_e 
        , CASE WHEN icd.icd9_dx_cd LIKE "E66%" THEN 1 ELSE 0                                  END AS obesity
        , CASE WHEN icd.icd9_dx_cd = "E28.2" THEN 1 ELSE 0                                    END AS pcos
        , CASE WHEN icd.icd_group IN (66, 67, 68, 234) THEN 1 ELSE 0                          END AS renal
        , CASE WHEN icd.icd_group = 257 THEN 1 ELSE 0                                         END AS sle
        , CASE WHEN clm.service_from > DATE_SUB(index_date, INTERVAL gest_age WEEK)
                    AND (icd.icd_group = 97)THEN 1 ELSE 0                                     END AS multi
        , CASE WHEN clm.service_from > DATE_SUB(index_date, INTERVAL gest_age WEEK) AND 
                    (icd.icd_group = 92) THEN 1 ELSE 0                                        END AS bleeding_in_current_preg 
        , CASE WHEN icd.icd9_dx_cd LIKE "C58%" OR
                    icd.icd9_dx_cd LIKE "C58%" THEN 1 ELSE 0                                  END AS trophoblastic  
        , CASE WHEN icd.icd9_dx_cd LIKE "F10%" OR
                    icd.icd9_dx_cd = "R78.0"     THEN 1 ELSE 0                                END AS Alcohol
        , CASE WHEN icd.icd9_dx_cd LIKE "F11%" OR
                    icd.icd9_dx_cd = "R78.1" THEN 1 ELSE 0                                    END AS OUD
        , CASE WHEN icd.icd9_dx_cd LIKE "F12%" THEN 1 ELSE 0                                  END AS Cannabis
        , CASE WHEN icd.icd9_dx_cd LIKE "F14%" OR
                    icd.icd9_dx_cd = "R78.2" THEN 1 ELSE 0                                    END AS Cocaine
        , CASE WHEN icd.icd9_dx_cd LIKE "F17%" OR
                    icd.icd9_dx_cd LIKE "O99.33%" THEN 1 ELSE 0                               END AS Nicotine    
        , CASE WHEN icd.icd9_dx_cd LIKE "F13%" OR icd.icd9_dx_cd LIKE "F15%" OR 
                    icd.icd9_dx_cd LIKE "F16%" OR icd.icd9_dx_cd LIKE "F18%" OR 
                    icd.icd9_dx_cd LIKE "F19%" OR icd.icd9_dx_cd LIKE "F55%" OR 
                    icd.icd9_dx_cd LIKE "O99.32%" OR
                    icd.icd9_dx_cd IN ("R78.3", "R78.4", "R78.5", "R78.6") THEN 1 ELSE 0      END AS Other_drug  
    FROM
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_longitudinal` AS mem
    LEFT JOIN
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_kmdo_cpt_and_revcode` AS clm
            ON mem.mom_key = clm.asdb_member_key
    LEFT JOIN
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_kmdo_icd_codes` AS icd
            ON mem.mom_key = icd.asdb_member_key
            AND clm.visit_id = icd.visit_id
    LEFT JOIN
        `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_MEMBER` AS mem2
            ON mem.mom_key = mem2.asdb_member_key
    WHERE 1 = 1
        AND clm.service_from < mem.index_date
;
--1,001,661,105 rows

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_edw_risk_flags`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
    SELECT
        mem.mom_key AS asdb_member_key
        , mem.index_date
        , mem.baby_dob 
        , CAST(FLOOR(DATE_DIFF(mem.index_date, mem.mom_dob, MONTH)/12) AS INT64) AS mom_age
        , mem2.ethnicity_desc
        , CASE WHEN clm.dt < DATE_SUB(index_date, INTERVAL gest_age WEEK) AND
                    (icd.icd9_dx_cd LIKE "O60.0%" OR icd.icd9_dx_cd LIKE "O60.2%") 
                    THEN 1 ELSE 0                                                             END AS pre_term_labor_clm
        , CASE WHEN clm.dt < DATE_SUB(index_date, INTERVAL gest_age WEEK) AND
                    (icd.icd9_dx_cd LIKE "O42.01%" OR icd.icd9_dx_cd LIKE "O42.11%" OR
                     icd.icd9_dx_cd LIKE "O42.91%" OR icd.icd9_dx_cd LIKE "O60.1%" OR
                     icd.icd9_dx_cd LIKE "P07.2%" OR icd.icd9_dx_cd LIKE "P07.3%"
                    ) THEN 1 ELSE 0                                                           END AS pre_term_delivery_clm
        , CASE WHEN clm.dt < DATE_SUB(index_date, INTERVAL gest_age WEEK) AND
                    (icd.icd9_dx_cd LIKE "O24%" OR icd.icd_group = 22) THEN 1 ELSE 0          END AS prior_dm
        , CASE WHEN clm.dt > DATE_SUB(index_date, INTERVAL gest_age WEEK) AND
                    (icd.icd9_dx_cd LIKE "O24%" OR icd.icd_group = 22) THEN 1 ELSE 0          END AS current_dm
        , CASE WHEN icd.icd9_dx_cd = "R73.03" THEN 1 ELSE 0                                   END AS pre_dm
        , CASE WHEN icd.icd9_dx_cd = "Z83.3" THEN 1 ELSE 0                                    END AS f_hist_dm
        , CASE WHEN icd.icd9_dx_cd = "D68.61" THEN 1 ELSE 0                                   END AS aps
        , CASE WHEN icd.icd9_dx_cd IN ("Z31.83", "N98.1") OR clm.prcdr_cd = "S4042"
                     THEN 1 ELSE 0                                                            END AS art
        , CASE WHEN icd.icd_group IN (181, 182) THEN 1 ELSE 0                                 END AS autoimmune
        , CASE WHEN icd.icd9_dx_cd = "Z87.59" OR
                    icd.icd9_dx_cd LIKE "O01%" THEN 1 ELSE 0                                  END AS hist_ob_comp 
        , CASE WHEN clm.dt < DATE_SUB(index_date, INTERVAL gest_age WEEK) AND 
                    (icd.icd_group IN (10, 109)) THEN 1 ELSE 0                                END AS prior_ht
    
        , CASE WHEN clm.dt > DATE_SUB(index_date, INTERVAL gest_age WEEK) AND 
                    (icd.icd_group IN (10, 109)) THEN 1 ELSE 0                                END AS current_preg_ht
        , CASE WHEN clm.dt < DATE_SUB(index_date, INTERVAL gest_age WEEK) AND 
                    (icd.icd_group = 110) THEN 1 ELSE 0                                       END AS prior_pre_e
        , CASE WHEN clm.dt > DATE_SUB(index_date, INTERVAL gest_age WEEK) AND 
                    (icd.icd_group = 110) THEN 1 ELSE 0                                       END AS current_pre_e 
        , CASE WHEN icd.icd9_dx_cd LIKE "E66%" THEN 1 ELSE 0                                  END AS obesity
        , CASE WHEN icd.icd9_dx_cd = "E28.2" THEN 1 ELSE 0                                    END AS pcos
        , CASE WHEN icd.icd_group IN (66, 67, 68, 234) THEN 1 ELSE 0                          END AS renal
        , CASE WHEN icd.icd_group = 257 THEN 1 ELSE 0                                         END AS sle
        , CASE WHEN clm.dt > DATE_SUB(index_date, INTERVAL gest_age WEEK)
                    AND (icd.icd_group = 97)THEN 1 ELSE 0                                     END AS multi
        , CASE WHEN clm.dt > DATE_SUB(index_date, INTERVAL gest_age WEEK) AND 
                    (icd.icd_group = 92) THEN 1 ELSE 0                                        END AS bleeding_in_current_preg 
        , CASE WHEN icd.icd9_dx_cd LIKE "C58%" OR
                    icd.icd9_dx_cd LIKE "C58%" THEN 1 ELSE 0                                  END AS trophoblastic  
        , CASE WHEN icd.icd9_dx_cd LIKE "F10%" OR
                    icd.icd9_dx_cd = "R78.0"     THEN 1 ELSE 0                                END AS Alcohol
        , CASE WHEN icd.icd9_dx_cd LIKE "F11%" OR
                    icd.icd9_dx_cd = "R78.1" THEN 1 ELSE 0                                    END AS OUD
        , CASE WHEN icd.icd9_dx_cd LIKE "F12%" THEN 1 ELSE 0                                  END AS Cannabis
        , CASE WHEN icd.icd9_dx_cd LIKE "F14%" OR
                    icd.icd9_dx_cd = "R78.2" THEN 1 ELSE 0                                    END AS Cocaine
        , CASE WHEN icd.icd9_dx_cd LIKE "F17%" OR
                    icd.icd9_dx_cd LIKE "O99.33%" THEN 1 ELSE 0                               END AS Nicotine    
        , CASE WHEN icd.icd9_dx_cd LIKE "F13%" OR icd.icd9_dx_cd LIKE "F15%" OR 
                    icd.icd9_dx_cd LIKE "F16%" OR icd.icd9_dx_cd LIKE "F18%" OR 
                    icd.icd9_dx_cd LIKE "F19%" OR icd.icd9_dx_cd LIKE "F55%" OR 
                    icd.icd9_dx_cd LIKE "O99.32%" OR
                    icd.icd9_dx_cd IN ("R78.3", "R78.4", "R78.5", "R78.6") THEN 1 ELSE 0      END AS Other_drug  
    FROM
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_longitudinal` AS mem
    LEFT JOIN
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_edw_cpt_and_revcode` AS clm
            ON mem.mom_key = clm.asdb_member_key
    LEFT JOIN
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_edw_icd_codes` AS icd
            ON mem.mom_key = icd.asdb_member_key
            AND clm.claim_line_id = icd.claim_line_id
    LEFT JOIN
        `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_MEMBER` AS mem2
            ON mem.mom_key = mem2.asdb_member_key
    WHERE 1 = 1
        AND clm.dt < mem.index_date
;
--10,072,741 rows

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_risk_flags`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
WITH joint AS (
    SELECT 
        * 
    FROM 
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_asdb_risk_flags`
    UNION ALL
        SELECT * FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_kmdo_risk_flags`
    UNION ALL
        SELECT * FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_edw_risk_flags`
)
SELECT
    asdb_member_key
    , index_date
    , baby_dob
    , mom_age
    , ethnicity_desc
    , MAX(pre_term_labor_clm) AS pre_term_labor_clm
    , MAX(pre_term_delivery_clm) AS pre_term_delivery_clm
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
    joint
GROUP BY
    asdb_member_key
    , index_date
    , baby_dob
    , mom_age
    , ethnicity_desc
ORDER BY
    asdb_member_key
    , index_date
;
--1,521,623 rows out of 1,815,426 in longitudinal with edw and asdb only; so rows missing do not have any claims?
--1,553,872 with komodo

--------------------------------------------
--- add in NICU flags for outcome checks ---
--------------------------------------------
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_risk_w_nicu_flags`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT
  risk.*
  , birth.nicu_lvl
  , CASE WHEN birth.nicu_lvl >= 2 THEN 1 ELSE 0 END AS nicu_flag
FROM
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_final_timepoint` AS birth
LEFT JOIN
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_risk_flags` AS risk
        ON birth.mom_key = risk.asdb_member_key
        AND birth.baby_dob = risk.baby_dob
WHERE
  risk.asdb_member_key IS NOT NULL
;
--1,599,065

-------------------------------------------
--- get only final timepoint with NICUs ---
-------------------------------------------

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_risk_w_nicu_flags_final_timepoint` 
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT
  *
FROM
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_risk_w_nicu_flags` 
WHERE
  index_date = baby_dob
;
--58,379


---------------------
--- sanity checks ---
---------------------
--done at the gest_age2 stage
-- SELECT
--     eop_del_dif[OFFSET(0)] AS p0,  
--     eop_del_dif[OFFSET(1)] AS p1,
--     eop_del_dif[OFFSET(10)] AS p10,
--     eop_del_dif[OFFSET(25)] AS p25,
--     eop_del_dif[OFFSET(50)] AS p50,
--     eop_del_dif[OFFSET(75)] AS p75,
--     eop_del_dif[OFFSET(90)] AS p90,
--     eop_del_dif[OFFSET(99)] AS p99,
--     eop_del_dif[OFFSET(100)] AS p100,
-- FROM 
-- (
--     SELECT 
--         APPROX_QUANTILES(eop_del_dif, 100) AS eop_del_dif
--     FROM 
--         `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_final_timepoint`
-- )
-- ;
--done after finishing final timepoint
SELECT COUNT(*) AS n, SUM(diabetes) AS GDM,  SUM(diabetes)/COUNT(*) AS percent FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_final_timepoint`;
--done on longitudinal data
SELECT COUNT(*) AS n, SUM(diabetes_at_index) AS GDM,  SUM(diabetes_at_index)/COUNT(*) AS percent, gest_age FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_longitudinal` GROUP BY gest_age ORDER BY gest_age;

--done after finishing final timepoint
SELECT COUNT(*) AS n, SUM(preeclampsia) AS pre_e,  SUM(preeclampsia)/COUNT(*) AS percent FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_final_timepoint`;
--done on longitudinal data

SELECT COUNT(*) AS n, SUM(pre_e_at_index) AS pre_e,  SUM(pre_e_at_index)/COUNT(*) AS percent, gest_age FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_longitudinal` GROUP BY gest_age ORDER BY gest_age;
