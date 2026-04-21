CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_labs_joined` 
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
WITH edw AS (
    SELECT
        asdb_member_key
        , index_date
        , baby_dob

        , lab_papp_a
        , lab_hCG

        , lab_hba1c_pre
        , lab_hba1c_current
        , lab_glucose_pre
        , lab_glucose_current
        , glucose_challenge_pre    
        , glucose_challenge_current

        , lab_bmi_pre
        , lab_waist_circ

        , lab_chol
        , lab_hdl
        , lab_ldl
        , lab_triglyc_pre
        , lab_triglyc_current

        , lab_crp_pre
        , lab_crp_current
        , lab_creat
        , lab_altsgpt
        , lab_bilirub
        , lab_sodium
        , lab_ferritin
    FROM
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_edw_lab3yr` 
)
, asdb AS (
    SELECT
        asdb_member_key
        , index_date
        , baby_dob

        , lab_papp_a
        , lab_hCG

        , lab_hba1c_pre
        , lab_hba1c_current
        , lab_glucose_pre
        , lab_glucose_current
        , glucose_challenge_pre    
        , glucose_challenge_current

        , lab_bmi_pre
        , lab_waist_circ

        , lab_chol
        , lab_hdl
        , lab_ldl
        , lab_triglyc_pre
        , lab_triglyc_current

        , lab_crp_pre
        , lab_crp_current
        , lab_creat
        , lab_altsgpt
        , lab_bilirub
        , lab_sodium
        , lab_ferritin
    FROM
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_asdb_labvals` 
)
, joint AS (
    SELECT 
        * 
    FROM 
        asdb
    UNION ALL
        SELECT * FROM edw
)
SELECT
    asdb_member_key
    , index_date
    , baby_dob

    , MAX(lab_papp_a) AS lab_pappa_a
    , MAX(lab_hCG) AS lab_hCG

    , MAX(lab_hba1c_pre) AS lab_hba1c_pre
    , MAX(lab_hba1c_current) AS lab_hba1c_current
    , MAX(lab_glucose_pre) AS lab_glucose_pre
    , MAX(lab_glucose_current) AS lab_glucose_current
    , MAX(glucose_challenge_pre) AS glucose_challenge_pre    
    , MAX(glucose_challenge_current) AS glucose_challenge_current

    , MAX(lab_bmi_pre) AS lab_bmi_pre
    , MAX(lab_waist_circ) AS lab_waist_circ

    , MAX(lab_chol) AS lab_chol
    , MAX(lab_hdl) AS lab_hdl
    , MAX(lab_ldl) AS lab_ldl
    , MAX(lab_triglyc_pre) AS lab_triglyc_pre
    , MAX(lab_triglyc_current) AS lab_triglyc_current
    
    , MAX(lab_crp_pre) AS lab_crp_pre
    , MAX(lab_crp_current) AS lab_crp_current
    , MAX(lab_creat) AS lab_creat
    , MAX(lab_altsgpt) AS lab_altsgpt
    , MAX(lab_bilirub) AS lab_bilirub
    , MAX(lab_sodium) AS lab_sodium
    , MAX(lab_ferritin) AS lab_ferritin
FROM
    joint
GROUP BY
    asdb_member_key
    , index_date
    , baby_dob
;    
    
SELECT COUNT(DISTINCT asdb_member_key) FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_labs_joined` WHERE lab_glucose_current IS NOT NULL AND lab_glucose_current > 0;
--26,615 have glucose challenge for current pregnancy
--7,431 (27.9% any glucose challenge, 17.8% of any moms with labs; 13.1% of all moms in cohort) are high
--41,691 moms have some entry in the lab table
--56,824 distinct mom asdb_member_keys

SELECT COUNT(DISTINCT asdb_member_key) FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_labs_joined` WHERE lab_glucose_pre IS NOT NULL AND lab_glucose_pre > 0;
--13,986 have glucose challenge from prior pregnancy
--2,140 were high in prior pregnancy (> 135)