-----------------------------
--- Join ASDB and EDW lab results
--- Production version: joins lab tables with _st
-----------------------------

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_labs_joined` 
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT
    st.asdb_member_key
    -- Lab values: take MAX from either ASDB or EDW source
    , GREATEST(COALESCE(asdb.lab_papp_a, 0), COALESCE(edw.lab_papp_a, 0)) AS lab_pappa_a
    , GREATEST(COALESCE(asdb.lab_hCG, 0), COALESCE(edw.lab_hCG, 0)) AS lab_hCG
    , GREATEST(COALESCE(asdb.lab_hba1c_pre, 0), COALESCE(edw.lab_hba1c_pre, 0)) AS lab_hba1c_pre
    , GREATEST(COALESCE(asdb.lab_hba1c_current, 0), COALESCE(edw.lab_hba1c_current, 0)) AS lab_hba1c_current
    , GREATEST(COALESCE(asdb.lab_glucose_pre, 0), COALESCE(edw.lab_glucose_pre, 0)) AS lab_glucose_pre
    , GREATEST(COALESCE(asdb.lab_glucose_current, 0), COALESCE(edw.lab_glucose_current, 0)) AS lab_glucose_current
    , GREATEST(COALESCE(asdb.glucose_challenge_pre, 0), COALESCE(edw.glucose_challenge_pre, 0)) AS glucose_challenge_pre    
    , GREATEST(COALESCE(asdb.glucose_challenge_current, 0), COALESCE(edw.glucose_challenge_current, 0)) AS glucose_challenge_current
    , GREATEST(COALESCE(asdb.lab_bmi_pre, 0), COALESCE(edw.lab_bmi_pre, 0)) AS lab_bmi_pre
    , GREATEST(COALESCE(asdb.lab_waist_circ, 0), COALESCE(edw.lab_waist_circ, 0)) AS lab_waist_circ
    , GREATEST(COALESCE(asdb.lab_chol, 0), COALESCE(edw.lab_chol, 0)) AS lab_chol
    , GREATEST(COALESCE(asdb.lab_hdl, 0), COALESCE(edw.lab_hdl, 0)) AS lab_hdl
    , GREATEST(COALESCE(asdb.lab_ldl, 0), COALESCE(edw.lab_ldl, 0)) AS lab_ldl
    , GREATEST(COALESCE(asdb.lab_triglyc_pre, 0), COALESCE(edw.lab_triglyc_pre, 0)) AS lab_triglyc_pre
    , GREATEST(COALESCE(asdb.lab_triglyc_current, 0), COALESCE(edw.lab_triglyc_current, 0)) AS lab_triglyc_current
    , GREATEST(COALESCE(asdb.lab_crp_pre, 0), COALESCE(edw.lab_crp_pre, 0)) AS lab_crp_pre
    , GREATEST(COALESCE(asdb.lab_crp_current, 0), COALESCE(edw.lab_crp_current, 0)) AS lab_crp_current
    , GREATEST(COALESCE(asdb.lab_creat, 0), COALESCE(edw.lab_creat, 0)) AS lab_creat
    , GREATEST(COALESCE(asdb.lab_altsgpt, 0), COALESCE(edw.lab_altsgpt, 0)) AS lab_altsgpt
    , GREATEST(COALESCE(asdb.lab_bilirub, 0), COALESCE(edw.lab_bilirub, 0)) AS lab_bilirub
    , GREATEST(COALESCE(asdb.lab_sodium, 0), COALESCE(edw.lab_sodium, 0)) AS lab_sodium
    , GREATEST(COALESCE(asdb.lab_ferritin, 0), COALESCE(edw.lab_ferritin, 0)) AS lab_ferritin
    -- Additional lab columns (available in both ASDB and EDW)
    , GREATEST(COALESCE(asdb.lab_bp, 0), COALESCE(edw.lab_bp, 0)) AS lab_bp
    , GREATEST(COALESCE(asdb.lab_hemoglob, 0), COALESCE(edw.lab_hemoglob, 0)) AS lab_hemoglob
    , GREATEST(COALESCE(asdb.lab_protein, 0), COALESCE(edw.lab_protein, 0)) AS lab_protein
    , GREATEST(COALESCE(asdb.lab_WBC, 0), COALESCE(edw.lab_WBC, 0)) AS lab_WBC
    , GREATEST(COALESCE(asdb.lab_GFR, 0), COALESCE(edw.lab_GFR, 0)) AS lab_GFR
FROM
    (SELECT DISTINCT asdb_member_key FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st`) AS st
LEFT JOIN
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_asdb_labvals` AS asdb
        ON st.asdb_member_key = asdb.asdb_member_key
LEFT JOIN
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_edw_labvals` AS edw
        ON st.asdb_member_key = edw.asdb_member_key
;
