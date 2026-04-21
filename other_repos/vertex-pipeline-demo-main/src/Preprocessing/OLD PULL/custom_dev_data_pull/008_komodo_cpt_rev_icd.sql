--TODO: Map to ICD group

/*
As of Oct 2024, the files are surfaced in the following views in anbc-hcb-prod.eds_srcapp_komodombr_share_hcb_prod as partitioned history tables containing various Aetna identifiers (individual_id, individual_analytics_identifier, medicaid_id, car_mbr_id, alternate_id_cumb_hmo) 

aetna_mdcd_beneficiary_komodo_final_history

aetna_mdcd_beneficiary_komodo_trace_history

aetna_mdcd_beneficiary_komodo_traceindv_history

To use these tables, please deploy the following code, where for each subsequent month, you use increment the ‘month’ value up by +01:

SELECT * FROM `anbc-hcb-prod.eds_srcapp_komodombr_share_hcb_prod.aetna_mdcd_beneficiary_komodo_trace_history` where cast(dt_field as date) = cast('2024-08-01' as date)

To reidentify Medicaid members:
The TRACE table will have patient_id, upk_token_2, individual_id, and medicaid_id, and car_mbr_id.
Query the appropriate month's TRACE table (e.g., V_AETNA_MDCD_BENEFICARY_KOMODO_FINAL_TRACE_YYYY_MM) as described above.
Join the upk_token_2 in the TRACE table with the patient_token_2 field in the Medical and Pharmacy tables to pull medicaid_id, and car_mbr_id.
Note, it is an analytic decision whether you want to use token 1, 2, or a concatenation of both based on a given use case's appetite for splits vs. collisions. If using individual_ID as a starting point (i.e., as source of truth for a single individual), users can consider combining data rows across claims tables for a given individual_ID, even if data are coming from different token 1s / token 2s. 

Medicaid (MDCD):

Table Name	Row_Count
Enc_Medical_Headers	181,649,849
Medical_Service_Lines	511,678,427
Patient_Enrollments	5,413,967
Patient_Summaries	1,824,567
Pharmacy	307,355,375
Visit_Summaries	138,620,547
*/

--anbc-hcb-prod.eds_srcapp_komodombr_share_hcb_prod.aetna_mdcd_beneficiary_komodo_trace_history

--`anbc-hcb-prod.eds_srcapp_komodombr_share_hcb_prod.medical_headers` -> lob_cd = mdcd
--icd_type = "10"
--need to insert the decimal...
--ICD
--d1	d2	d3	d4	d5	d6	d7	d8	d9	d10	d11	d12	d13	d14	d15	d16	d17	d18	d19	d20	d21	d22	d23	d24	d25	d26

--`anbc-hcb-prod.eds_srcapp_komodombr_share_hcb_prod.medical_service_lines`
--service_from
--procedure
--revenue_code
/*
            n	lob_cd
1,618,627,202	non_mdcd
  181,649,849	mdcd

f0_	revenue_code
12459     0170
40717     0171
 4436     0172
 3651     0173
 2536     0174

mdcd only
 97    0170
449    0171
 28    0173
 14    0174
 39    0172
*/

---------------------------------
--- CPT and rev codes 
---------------------------------

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_kmdo_cpt_and_revcode`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT
    base.asdb_member_key
    , base.baby_dob AS index_dt
    , base.upk_token_2
    , clm.visit_id --, clm.claimid
    , clm.service_from --, clm.asdb_incurred_dt
    , clm.revenue_code --STRING FORMAT!; ASDB is string format too--, clm.revcode
    , clm.procedure --, clm.servcode
FROM 
    `anbc-hcb-prod.eds_srcapp_komodombr_share_hcb_prod.medical_service_lines` AS clm
    LEFT JOIN
        `anbc-hcb-prod.eds_srcapp_komodombr_share_hcb_prod.medical_headers` AS hdr
            ON clm.encounter_key = hdr.encounter_key
LEFT JOIN
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_id_crosswalk` AS base 
        ON clm.patient_token_2 = base.upk_token_2
WHERE 1=1
    AND CAST(base.baby_dob AS DATE) > DATE_ADD(CAST(hdr.received_date AS DATE), INTERVAL 2 MONTH)
;

--records that match this criteria 273,869,343
--QC check
SELECT 
    'da' AS step
    , COUNT(1) AS cnt
    , COUNT(DISTINCT asdb_member_key) AS cnt_ind
FROM 
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_kmdo_cpt_and_revcode`
;
/*
step        cnt     cnt_ind
  da 1,0748,955     27,354
*/

----------------
---ICD codes ---
----------------
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_kmdo_icd_codes`
OPTIONS (
  labels = [("owner", "palmere1_aetna_com"),("cost_center", "13070")]
  , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), INTERVAL 180 DAY))
AS
WITH base AS (
    SELECT 
        base.asdb_member_key
        , base.upk_token_2
        , base.visit_id
        , base.index_dt
    FROM
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_kmdo_cpt_and_revcode` AS base 
)
, p AS (
    SELECT 
        base.asdb_member_key
        , base.upk_token_2
        , base.visit_id
        , base.index_dt
        , SUBSTR(b.diagnosis_code_1, 1, 3) AS x_0
        , SUBSTR(b.diagnosis_code_1, 4, 7) AS x_1
    FROM
        base 
    INNER JOIN
        `anbc-hcb-prod.eds_srcapp_komodombr_share_hcb_prod.medical_service_lines` AS b 
            ON base.visit_id = b.visit_id
)
, s1 AS (
    SELECT 
        base.asdb_member_key
        , base.upk_token_2
        , base.visit_id
        , base.index_dt
        , SUBSTR(b.diagnosis_code_2, 1, 3) AS x_0
        , SUBSTR(b.diagnosis_code_2, 4, 7) AS x_1
    FROM
        base 
    INNER JOIN
        `anbc-hcb-prod.eds_srcapp_komodombr_share_hcb_prod.medical_service_lines` AS b 
            ON base.visit_id = b.visit_id
)
, s2 AS (
    SELECT 
        base.asdb_member_key
        , base.upk_token_2
        , base.visit_id
        , base.index_dt
        , SUBSTR(b.diagnosis_code_3, 1, 3) AS x_0
        , SUBSTR(b.diagnosis_code_3, 4, 7) AS x_1
    FROM
        base 
    INNER JOIN
        `anbc-hcb-prod.eds_srcapp_komodombr_share_hcb_prod.medical_service_lines` AS b 
            ON base.visit_id = b.visit_id
)
, s3 AS (
    SELECT 
        base.asdb_member_key
        , base.upk_token_2
        , base.visit_id
        , base.index_dt
        , SUBSTR(b.diagnosis_code_4, 1, 3) AS x_0
        , SUBSTR(b.diagnosis_code_4, 4, 7) AS x_1
    FROM
        base 
    INNER JOIN
        `anbc-hcb-prod.eds_srcapp_komodombr_share_hcb_prod.medical_service_lines` AS b 
            ON base.visit_id = b.visit_id
)
, x1 AS (
    SELECT 
        * 
    FROM 
        p 
    UNION DISTINCT
        SELECT * FROM s1 
    UNION DISTINCT
        SELECT * FROM s2 
    UNION DISTINCT
        SELECT * FROM s3 
),
x2 AS (
    SELECT 
        asdb_member_key
        , upk_token_2
        , visit_id
        , index_dt
        , CASE WHEN x_1 IS NULL THEN x_0
            ELSE CONCAT(x_0, '.', x_1) END AS icd9_dx_cd
    FROM 
        x1
)
SELECT
    x2.*
    , grp.ICD9_DX_GROUP_NBR AS icd_group
FROM
    x2
LEFT JOIN
    `edp-prod-hcbstorage.edp_hcb_core_cnsv.ICD9_DIAGNOSIS` AS grp
          ON TRIM(UPPER(x2.icd9_dx_cd)) = TRIM(UPPER(grp.ICD9_DX_CD))    
;
/*
step     cnt       cnt_ind
 d1b     4,457,822  27,354
*/