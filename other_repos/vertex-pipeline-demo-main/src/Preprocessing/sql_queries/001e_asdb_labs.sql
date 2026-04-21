--TODO: seperate out current pregnancy from prior to pregnancy...
/*
        , CASE WHEN asdb_incurred_dt < DATE_SUB(index_date, INTERVAL gest_age WEEK) AND
                    (S.icd_code LIKE "O24%" OR T.icd_code LIKE "O24%" OR 
                S.icd_group = 22 OR T.icd_group = 22) THEN 1 ELSE 0                           END AS prior_dm
        , CASE WHEN asdb_incurred_dt > DATE_SUB(index_date, INTERVAL gest_age WEEK) AND
                    (S.icd_code LIKE "O24%" OR T.icd_code LIKE "O24%" OR 
                S.icd_group = 22 OR T.icd_group = 22) THEN 1 ELSE 0                           END AS current_dm
*/
--TODO: seperate out index date and service date into second table not labeled tmp


CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_asdb_labvals` 
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
WITH labresults_daily AS (
    SELECT DISTINCT 
        a.mom_key AS asdb_member_key
        , a.baby_dob
        , a.index_date
        , xref.asdb_plan_key
        , d.loinc_class_cd
        , CAST(b.service_start_dts AS DATE) AS service_start_dts
        , CAST(b.create_dts AS DATE) AS known_dt
        , SAFE_CAST(TRIM(c.result_value_txt) AS FLOAT64) AS result_value
        , CASE WHEN TRIM(d.loinc_class_cd)= "CHOLEST" THEN 1 ELSE 0 END AS lab_cholesterol
        , CASE WHEN TRIM(d.loinc_class_cd)= "HDL" AND TRIM(c.loinc_cd) NOT IN ("9832-7" , "98327" , "9833-5", "98335") THEN 1 ELSE 0 END AS lab_hdl
        , CASE WHEN TRIM(d.loinc_class_cd)= "LDL" THEN 1 ELSE 0 END AS lab_ldl
        , CASE WHEN TRIM(d.loinc_class_cd)= "TRIGLYC" 
            AND CAST(b.service_start_dts AS DATE) < DATE_SUB(index_date, INTERVAL gest_age WEEK)
            THEN 1 ELSE 0 END AS lab_triglyc_pre
        , CASE WHEN TRIM(d.loinc_class_cd)= "TRIGLYC" 
            AND CAST(b.service_start_dts AS DATE) >= DATE_SUB(index_date, INTERVAL gest_age WEEK)
            THEN 1 ELSE 0 END AS lab_triglyc_current
        , CASE WHEN TRIM(d.loinc_class_cd)= "GLUCOSE" 
            AND CAST(b.service_start_dts AS DATE) < DATE_SUB(index_date, INTERVAL gest_age WEEK)
            THEN 1 ELSE 0 END AS lab_glucose_pre
        , CASE WHEN TRIM(d.loinc_class_cd)= "GLUCOSE" 
            AND CAST(b.service_start_dts AS DATE) >= DATE_SUB(index_date, INTERVAL gest_age WEEK)
            THEN 1 ELSE 0 END AS lab_glucose_current
        , CASE WHEN TRIM(d.loinc_class_cd)= "HBA1C" 
            AND CAST(b.service_start_dts AS DATE) < DATE_SUB(index_date, INTERVAL gest_age WEEK)
            THEN 1 ELSE 0 END AS lab_hba1c_pre
        , CASE WHEN TRIM(d.loinc_class_cd)= "HBA1C" 
            AND CAST(b.service_start_dts AS DATE) >= DATE_SUB(index_date, INTERVAL gest_age WEEK)
            THEN 1 ELSE 0 END AS lab_hba1c_current
        , CASE WHEN TRIM(d.loinc_class_cd) IN ("BP_DIA","BP_SYS") THEN 1 ELSE 0 END AS lab_bp
        , CASE WHEN TRIM(d.loinc_class_cd)= "CREAT" THEN 1 ELSE 0 END AS lab_creat
        , CASE WHEN TRIM(d.loinc_class_cd)="HEMOGLOB" THEN 1 ELSE 0 END AS lab_hemoglob
        , CASE WHEN TRIM(d.loinc_class_cd)="PROTEIN" THEN 1 ELSE 0 END AS lab_protein
        , CASE WHEN TRIM(d.loinc_class_cd)="WBC" THEN 1 ELSE 0 END AS lab_WBC
        , CASE WHEN TRIM(d.loinc_class_cd)="GFR" THEN 1 ELSE 0 END AS lab_GFR   
        , CASE WHEN TRIM(d.loinc_class_cd)="ALT/SGPT" THEN 1 ELSE 0 END AS lab_alt_sgpt
        , CASE WHEN TRIM(d.loinc_class_cd)="BILIRUB" THEN 1 ELSE 0 END AS lab_bilirub
        , CASE WHEN TRIM(d.loinc_class_cd)="CRP" 
            AND CAST(b.service_start_dts AS DATE) < DATE_SUB(index_date, INTERVAL gest_age WEEK)
            THEN 1 ELSE 0 END AS lab_CRP_pre
        , CASE WHEN TRIM(d.loinc_class_cd)="CRP" 
            AND CAST(b.service_start_dts AS DATE) >= DATE_SUB(index_date, INTERVAL gest_age WEEK)    
            THEN 1 ELSE 0 END AS lab_CRP_current
        , CASE WHEN TRIM(d.loinc_class_cd)="SODIUM" THEN 1 ELSE 0 END AS lab_sodium
        , CASE WHEN TRIM(d.loinc_class_cd)="FERRITIN" THEN 1 ELSE 0 END AS ferritin
        , CASE WHEN TRIM(d.loinc_cd) IN ("48407-1", "32123-2", "76348-2") 
            AND CAST(b.service_start_dts AS DATE) >= DATE_SUB(index_date, INTERVAL gest_age WEEK)    
            THEN 1 ELSE 0 END AS papp_a
        , CASE WHEN TRIM(d.loinc_class_cd) = "Preg Tes" 
            AND CAST(b.service_start_dts AS DATE) >= DATE_SUB(index_date, INTERVAL gest_age WEEK)    
            THEN 1 ELSE 0 END hCG
        , CASE WHEN TRIM(d.loinc_cd) IN ("1504-0") 
            AND CAST(b.service_start_dts AS DATE) < DATE_SUB(index_date, INTERVAL gest_age WEEK)
            THEN 1 ELSE 0 END AS glucose_challenge_pre
        , CASE WHEN TRIM(d.loinc_cd) IN ("1504-0") 
            AND CAST(b.service_start_dts AS DATE) >= DATE_SUB(index_date, INTERVAL gest_age WEEK)
            THEN 1 ELSE 0 END AS glucose_challenge_current    
        , CASE WHEN TRIM(d.loinc_class_cd)="BMI" 
            AND CAST(b.service_start_dts AS DATE) < DATE_SUB(index_date, INTERVAL gest_age WEEK)
            THEN 1 ELSE 0 END AS lab_bmi_pre
        , CASE WHEN TRIM(d.loinc_class_cd)= "WAIST" THEN 1 ELSE 0 END AS lab_waist_circ
    FROM 
    --TODO repoint to cohort file...
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_longitudinal` AS a
    INNER JOIN 
        `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_MEMBER` AS xref
            ON a.mom_key = xref.asdb_member_key
    INNER JOIN 
        `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.IODB_LAB_CLAIM` AS b 
            ON xref.iodb_member_key = b.iodb_member_key
    INNER JOIN 
        `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.IODB_LAB_CLAIM_TEST_RESULT` AS c 
            ON b.iodb_lab_claim_key = c.iodb_lab_claim_key
    INNER JOIN
        `edp-prod-hcbstorage.edp_hcb_core_cnsv.BASE_LAB_RESULTS_REF` AS d
            ON TRIM(c.loinc_cd) = TRIM(d.lab_loinc_cd)
    WHERE 1 = 1 
        AND CAST(b.service_start_dts AS DATE) < a.index_date  -- Labs must be known before index_date
        AND a.index_date >= DATE_SUB(CAST(b.service_start_dts AS DATE), INTERVAL 36 MONTH)
        AND SAFE_CAST(TRIM(c.result_value_txt) AS FLOAT64) > 0
    ORDER BY
        a.mom_key
        , a.index_date
        , a.baby_dob
    )
SELECT 
    asdb_member_key
    , index_date
    , baby_dob
    , asdb_plan_key

    , MAX(CASE WHEN papp_a = 1 THEN result_value ELSE NULL END) AS lab_papp_a
    , MAX(CASE WHEN hCG = 1 THEN result_value ELSE NULL END) AS lab_hCG

    , MAX(CASE WHEN lab_hba1c_pre = 1 THEN result_value ELSE NULL END) AS lab_hba1c_pre
    , MAX(CASE WHEN lab_hba1c_current = 1 THEN result_value ELSE NULL END) AS lab_hba1c_current
    , MAX(CASE WHEN lab_glucose_pre = 1 THEN result_value ELSE NULL END) AS lab_glucose_pre
    , MAX(CASE WHEN lab_glucose_current = 1 THEN result_value ELSE NULL END) AS lab_glucose_current
    , MAX(CASE WHEN glucose_challenge_pre = 1 THEN result_value ELSE NULL END) AS glucose_challenge_pre    
    , MAX(CASE WHEN glucose_challenge_current = 1 THEN result_value ELSE NULL END) AS glucose_challenge_current

    , MAX(CASE WHEN lab_bmi_pre = 1 THEN result_value ELSE NULL END) AS lab_bmi_pre
    , MAX(CASE WHEN lab_waist_circ = 1 THEN result_value ELSE NULL END) AS lab_waist_circ

    , MAX(CASE WHEN lab_cholesterol = 1 THEN result_value ELSE NULL END) AS lab_chol
    , MAX(CASE WHEN lab_hdl = 1 THEN result_value END) AS lab_hdl
    , MAX(CASE WHEN lab_ldl = 1 THEN result_value ELSE NULL END) AS lab_ldl
    , MAX(CASE WHEN lab_triglyc_pre = 1 THEN result_value ELSE NULL END) AS lab_triglyc_pre
    , MAX(CASE WHEN lab_triglyc_current = 1 THEN result_value ELSE NULL END) AS lab_triglyc_current
    
    , MAX(CASE WHEN lab_CRP_pre = 1 THEN result_value ELSE NULL END) AS lab_crp_pre
    , MAX(CASE WHEN lab_CRP_current = 1 THEN result_value ELSE NULL END) AS lab_crp_current
    , MAX(CASE WHEN lab_creat = 1 THEN result_value ELSE NULL END) AS lab_creat
    , MAX(CASE WHEN lab_alt_sgpt = 1 THEN result_value ELSE NULL END) AS lab_altsgpt
    , MAX(CASE WHEN lab_bilirub = 1 THEN result_value ELSE NULL END) AS lab_bilirub
    , MAX(CASE WHEN lab_sodium = 1 THEN result_value ELSE NULL END) AS lab_sodium
    , MAX(CASE WHEN ferritin = 1 THEN result_value ELSE NULL END) AS lab_ferritin
FROM 
    labresults_daily
GROUP BY 
    asdb_member_key
    , index_date
    , baby_dob
    , asdb_plan_key
;


SELECT COUNT(DISTINCT asdb_member_key) FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_asdb_labvals` WHERE lab_glucose_current IS NOT NULL AND lab_glucose_current > 0;
--26,366 have glucose challenge for current pregnancy

SELECT COUNT(DISTINCT asdb_member_key) FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_asdb_labvals` WHERE lab_glucose_pre IS NOT NULL AND lab_glucose_pre > 0;
--13,420 have glucose challenge from prior pregnancy
--2,116 were high in prior pregnancy (> 135)

/*
creat    16,834
HBA1c    12,309
glucose  30,822
tot_chol  8,335
hdl       7,898
ldl       8,241
tri       8,110   
altsgpt  16,314
billi    13,944
cea          64
crp         840
ggt         554
magnesium   579
psa          59
sedrate     688
sodium   15,609
bp_syst       1
bp_dia        1
ferritin  4,890
papp-a      923
hcg      10,462
*/