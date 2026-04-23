-----------------------------
--- EDW Lab Results       ---
--- Uses {INDEX_DT} as reference date for production scoring
-----------------------------

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_edw_labvals` 
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
WITH pre AS (
    SELECT 
        st.individual_id
        , st.asdb_member_key
        , st.gest_age
        , elr.lab_create_dt
        , elr.srv_start_dt
        , CAST(elr.lab_result_nbr AS FLOAT64) AS lab_result_nbr
        , elrr.loinc_class_cd
        , elrr.loinc_cd
        , elrr.prcdr_cd
    FROM 
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st` AS st
    INNER JOIN 
        `edp-prod-hcbstorage.edp_hcb_core_cnsv.INDVDL_CUST_DIST` AS eicd 
            ON CAST(st.individual_id AS INT64) = eicd.individual_id
    INNER JOIN 
        `edp-prod-hcbstorage.edp_hcb_core_cnsv.LAB_RESULTS` AS elr  
            ON eicd.member_id = elr.member_id
    INNER JOIN 
        `edp-prod-hcbstorage.edp_hcb_core_cnsv.LAB_RESULTS_REF` AS elrr 
            ON elr.lab_loinc_cd = elrr.lab_loinc_cd
    WHERE 1 = 1
        AND DATE_SUB({INDEX_DT}, INTERVAL 36 MONTH) <= elr.srv_start_dt
        AND CAST(elr.lab_result_nbr AS FLOAT64) > 0
)
SELECT 
    l.individual_id
    , l.asdb_member_key
    , MAX(CASE WHEN TRIM(l.loinc_cd) IN ("48407-1", "32123-2", "76348-2") 
          AND CAST(l.srv_start_dt AS DATE) >= DATE_SUB({INDEX_DT}, INTERVAL gest_age WEEK)  
          THEN lab_result_nbr ELSE NULL END) AS lab_papp_a
    , MAX(CASE WHEN TRIM(l.loinc_cd) IN ("48407-1", "32123-2", "76348-2") 
            AND CAST(l.srv_start_dt AS DATE) >= DATE_SUB({INDEX_DT}, INTERVAL gest_age WEEK)
          THEN lab_result_nbr ELSE NULL END) AS lab_hCG

    , MAX(CASE WHEN TRIM(l.loinc_class_cd)= "HBA1C" 
          AND CAST(l.srv_start_dt AS DATE) < DATE_SUB({INDEX_DT}, INTERVAL gest_age WEEK)  
          THEN lab_result_nbr ELSE NULL END) AS lab_hba1c_pre
    , MAX(CASE WHEN TRIM(l.loinc_class_cd)= "HBA1C" 
          AND CAST(l.srv_start_dt AS DATE) >= DATE_SUB({INDEX_DT}, INTERVAL gest_age WEEK)  
          THEN lab_result_nbr ELSE NULL END) AS lab_hba1c_current
    , MAX(CASE WHEN TRIM(l.loinc_class_cd)= "GLUCOSE" 
          AND CAST(l.srv_start_dt AS DATE) < DATE_SUB({INDEX_DT}, INTERVAL gest_age WEEK)  
          THEN lab_result_nbr ELSE NULL END) AS lab_glucose_pre
    , MAX(CASE WHEN TRIM(l.loinc_class_cd)= "GLUCOSE" 
          AND CAST(l.srv_start_dt AS DATE) >= DATE_SUB({INDEX_DT}, INTERVAL gest_age WEEK)  
          THEN lab_result_nbr ELSE NULL END) AS lab_glucose_current
    , MAX(CASE WHEN TRIM(l.loinc_cd) IN ("1504-0") 
            AND CAST(l.srv_start_dt AS DATE) < DATE_SUB({INDEX_DT}, INTERVAL gest_age WEEK)
          THEN lab_result_nbr ELSE NULL END) AS glucose_challenge_pre
    , MAX(CASE WHEN TRIM(l.loinc_cd) IN ("1504-0") 
            AND CAST(l.srv_start_dt AS DATE) >= DATE_SUB({INDEX_DT}, INTERVAL gest_age WEEK)
          THEN lab_result_nbr ELSE NULL END) AS glucose_challenge_current

    , MAX(CASE WHEN TRIM(l.loinc_class_cd)= "BMI" 
          AND CAST(l.srv_start_dt AS DATE) < DATE_SUB({INDEX_DT}, INTERVAL gest_age WEEK)  
          THEN lab_result_nbr ELSE NULL END) AS lab_bmi_pre
    , MAX(CASE WHEN TRIM(l.loinc_class_cd)= "WAIST" THEN lab_result_nbr ELSE NULL END) AS lab_waist_circ

    , MAX(CASE WHEN TRIM(l.loinc_class_cd)= "CHOLEST" THEN lab_result_nbr ELSE NULL END) AS lab_chol
    , MAX(CASE WHEN TRIM(l.loinc_class_cd)= "HDL" THEN lab_result_nbr ELSE NULL END) AS lab_hdl
    , MAX(CASE WHEN TRIM(l.loinc_class_cd)= "LDL" THEN lab_result_nbr ELSE NULL END) AS lab_ldl
    , MAX(CASE WHEN TRIM(l.loinc_class_cd)= "TRIGLYC" 
          AND CAST(l.srv_start_dt AS DATE) < DATE_SUB({INDEX_DT}, INTERVAL gest_age WEEK)  
          THEN lab_result_nbr ELSE NULL END) AS lab_triglyc_pre
    , MAX(CASE WHEN TRIM(l.loinc_class_cd)= "TRIGLYC" 
          AND CAST(l.srv_start_dt AS DATE) >= DATE_SUB({INDEX_DT}, INTERVAL gest_age WEEK)  
          THEN lab_result_nbr ELSE NULL END) AS lab_triglyc_current

    , MAX(CASE WHEN TRIM(l.loinc_class_cd)= "CRP" 
          AND CAST(l.srv_start_dt AS DATE) < DATE_SUB({INDEX_DT}, INTERVAL gest_age WEEK)  
          THEN lab_result_nbr ELSE NULL END) AS lab_crp_pre
    , MAX(CASE WHEN TRIM(l.loinc_class_cd)= "CRP" 
          AND CAST(l.srv_start_dt AS DATE) >= DATE_SUB({INDEX_DT}, INTERVAL gest_age WEEK)  
          THEN lab_result_nbr ELSE NULL END) AS lab_crp_current
    , MAX(CASE WHEN TRIM(l.loinc_class_cd)= "CREAT" THEN lab_result_nbr ELSE NULL END) AS lab_creat
    , MAX(CASE WHEN TRIM(l.loinc_class_cd)= "ALT/SGPT" THEN lab_result_nbr ELSE NULL END) AS lab_altsgpt
    , MAX(CASE WHEN TRIM(l.loinc_class_cd)= "BILIRUB" THEN lab_result_nbr ELSE NULL END) AS lab_bilirub
    , MAX(CASE WHEN TRIM(l.loinc_class_cd)= "SODIUM" THEN lab_result_nbr ELSE NULL END) AS lab_sodium
    , MAX(CASE WHEN TRIM(l.loinc_class_cd)= "FERRITIN" THEN lab_result_nbr ELSE NULL END) AS lab_ferritin
    -- Additional lab columns (matching ASDB)
    , MAX(CASE WHEN TRIM(l.loinc_class_cd) IN ("BP_DIA","BP_SYS") THEN lab_result_nbr ELSE NULL END) AS lab_bp
    , MAX(CASE WHEN TRIM(l.loinc_class_cd)= "HEMOGLOB" THEN lab_result_nbr ELSE NULL END) AS lab_hemoglob
    , MAX(CASE WHEN TRIM(l.loinc_class_cd)= "PROTEIN" THEN lab_result_nbr ELSE NULL END) AS lab_protein
    , MAX(CASE WHEN TRIM(l.loinc_class_cd)= "WBC" THEN lab_result_nbr ELSE NULL END) AS lab_WBC
    , MAX(CASE WHEN TRIM(l.loinc_class_cd)= "GFR" THEN lab_result_nbr ELSE NULL END) AS lab_GFR
   
FROM 
    pre AS l  
WHERE 1 = 1
    AND l.asdb_member_key IS NOT NULL
GROUP BY
    l.individual_id
    , l.asdb_member_key
;
