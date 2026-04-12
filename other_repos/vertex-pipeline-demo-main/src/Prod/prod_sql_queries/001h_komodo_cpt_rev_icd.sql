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
--- CPT and rev codes (cohort-first: join from _st to reduce Komodo scan)
---------------------------------

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_kmdo_cpt_and_revcode`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT
    base.asdb_member_key
    , base.index_dt
    , base.upk_token_2
    , clm.visit_id
    , clm.service_from AS incurred_dt
    , clm.revenue_code
    , clm.procedure
FROM
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st` AS base
INNER JOIN
    `anbc-hcb-prod.eds_srcapp_komodombr_share_hcb_prod.medical_service_lines` AS clm
    ON clm.patient_token_2 = base.upk_token_2
LEFT JOIN
    `anbc-hcb-prod.eds_srcapp_komodombr_share_hcb_prod.medical_headers` AS hdr
    ON clm.encounter_key = hdr.encounter_key
WHERE 1 = 1
;

----------------
--- ICD codes (single-pass unpivot: one join to medical_service_lines instead of 4)
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
        , base.incurred_dt
    FROM
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_kmdo_cpt_and_revcode` AS base
)
, unpivoted AS (
    SELECT
        base.asdb_member_key
        , base.upk_token_2
        , base.visit_id
        , base.index_dt
        , base.incurred_dt
        , TRIM(dx) AS raw_dx
    FROM
        base
    INNER JOIN
        `anbc-hcb-prod.eds_srcapp_komodombr_share_hcb_prod.medical_service_lines` AS b
        ON base.visit_id = b.visit_id
    , UNNEST([b.diagnosis_code_1, b.diagnosis_code_2, b.diagnosis_code_3, b.diagnosis_code_4]) AS dx
    WHERE dx IS NOT NULL AND TRIM(dx) != ''
)
, normalized AS (
    SELECT
        asdb_member_key
        , upk_token_2
        , visit_id
        , index_dt
        , incurred_dt
        , CASE
            WHEN LENGTH(TRIM(raw_dx)) = 3 THEN TRIM(UPPER(raw_dx))
            WHEN LENGTH(TRIM(raw_dx)) > 3 AND SUBSTR(TRIM(raw_dx), 4, 1) = '.' THEN TRIM(UPPER(raw_dx))
            ELSE CONCAT(SUBSTR(TRIM(UPPER(raw_dx)), 1, 3), '.', SUBSTR(TRIM(raw_dx), 5, 8))
          END AS icd9_dx_cd
    FROM
        unpivoted
)
SELECT
    n.*
    , grp.ICD9_DX_GROUP_NBR AS icd_group
FROM
    normalized AS n
LEFT JOIN
    `edp-prod-hcbstorage.edp_hcb_core_cnsv.ICD9_DIAGNOSIS` AS grp
    ON TRIM(UPPER(n.icd9_dx_cd)) = TRIM(UPPER(grp.ICD9_DX_CD))
;

----------------
--- Visit-level risk presence (one row per visit; reduces 001i join size)
----------------
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_kmdo_visit_risk_presence`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT
    asdb_member_key
    , index_dt
    , visit_id
    , incurred_dt
    , MAX(CASE WHEN icd9_dx_cd LIKE "O60.0%" OR icd9_dx_cd LIKE "O60.2%" THEN 1 ELSE 0 END) AS has_pre_term_labor_codes
    , MAX(CASE WHEN icd9_dx_cd LIKE "O42.01%" OR icd9_dx_cd LIKE "O42.11%" OR icd9_dx_cd LIKE "O42.91%" OR icd9_dx_cd LIKE "O60.1%" OR icd9_dx_cd LIKE "P07.2%" OR icd9_dx_cd LIKE "P07.3%" THEN 1 ELSE 0 END) AS has_pre_term_delivery_codes
    , MAX(CASE WHEN icd9_dx_cd LIKE "O24%" OR icd_group = 22 THEN 1 ELSE 0 END) AS has_dm_codes
    , MAX(CASE WHEN icd_group IN (10, 109) THEN 1 ELSE 0 END) AS has_ht_codes
    , MAX(CASE WHEN icd_group = 110 THEN 1 ELSE 0 END) AS has_pre_e_codes
    , MAX(CASE WHEN icd_group = 97 THEN 1 ELSE 0 END) AS has_97
    , MAX(CASE WHEN icd_group = 92 THEN 1 ELSE 0 END) AS has_92
    , MAX(CASE WHEN icd9_dx_cd = "R73.03" THEN 1 ELSE 0 END) AS pre_dm
    , MAX(CASE WHEN icd9_dx_cd = "Z83.3" THEN 1 ELSE 0 END) AS f_hist_dm
    , MAX(CASE WHEN icd9_dx_cd = "D68.61" THEN 1 ELSE 0 END) AS aps
    , MAX(CASE WHEN icd9_dx_cd IN ("Z31.83", "N98.1") THEN 1 ELSE 0 END) AS art_icd
    , MAX(CASE WHEN icd_group IN (181, 182) THEN 1 ELSE 0 END) AS autoimmune
    , MAX(CASE WHEN icd9_dx_cd = "Z87.59" OR icd9_dx_cd LIKE "O01%" THEN 1 ELSE 0 END) AS hist_ob_comp
    , MAX(CASE WHEN icd9_dx_cd LIKE "E66%" THEN 1 ELSE 0 END) AS obesity
    , MAX(CASE WHEN icd9_dx_cd = "E28.2" THEN 1 ELSE 0 END) AS pcos
    , MAX(CASE WHEN icd_group IN (66, 67, 68, 234) THEN 1 ELSE 0 END) AS renal
    , MAX(CASE WHEN icd_group = 257 THEN 1 ELSE 0 END) AS sle
    , MAX(CASE WHEN icd9_dx_cd LIKE "C58%" THEN 1 ELSE 0 END) AS trophoblastic
    , MAX(CASE WHEN icd9_dx_cd LIKE "F10%" OR icd9_dx_cd = "R78.0" THEN 1 ELSE 0 END) AS Alcohol
    , MAX(CASE WHEN icd9_dx_cd LIKE "F11%" OR icd9_dx_cd = "R78.1" THEN 1 ELSE 0 END) AS OUD
    , MAX(CASE WHEN icd9_dx_cd LIKE "F12%" THEN 1 ELSE 0 END) AS Cannabis
    , MAX(CASE WHEN icd9_dx_cd LIKE "F14%" OR icd9_dx_cd = "R78.2" THEN 1 ELSE 0 END) AS Cocaine
    , MAX(CASE WHEN icd9_dx_cd LIKE "F17%" OR icd9_dx_cd LIKE "O99.33%" THEN 1 ELSE 0 END) AS Nicotine
    , MAX(CASE WHEN icd9_dx_cd LIKE "F13%" OR icd9_dx_cd LIKE "F15%" OR icd9_dx_cd LIKE "F16%" OR icd9_dx_cd LIKE "F18%" OR icd9_dx_cd LIKE "F19%" OR icd9_dx_cd LIKE "F55%" OR icd9_dx_cd LIKE "O99.32%" OR icd9_dx_cd IN ("R78.3", "R78.4", "R78.5", "R78.6") THEN 1 ELSE 0 END) AS Other_drug
FROM
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_kmdo_icd_codes`
GROUP BY
    asdb_member_key
    , index_dt
    , visit_id
    , incurred_dt
;