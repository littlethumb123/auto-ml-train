-- Cost and Utilization Query - OPTIMIZED
-- Single scan of source tables for full 24-month window
-- Creates pivoted summary tables with yr1/yr2 columns (one row per member)
-- Variables: GCP_PROJECT, GCP_DB, PREFIX, OWNER, COST_CENTER, DEFAULT_EXP

---------------------------------
-- STEP 1: ED Cases (single scan of ASDB_ASDB_ICE_OP for 24 months)
---------------------------------
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_ed_cases_all`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT 
    st.asdb_member_key
    , st.asdb_plan_key
    , st.index_dt
    , mc.asdb_incurred_dt AS ed_vis_dt
    , mc.event_ct
    , mc.prindiag
    , mc.cost
    , mc.op_severitylvl
    , CASE WHEN TRIM(nyu.avoidable_ind) = "Y" THEN 1 ELSE 0 END AS avoidable_er_visits
    , CASE WHEN TRIM(nyu.er_type) = "UNNECESSARY" THEN 1 ELSE 0 END AS unnecessary_er_visits
    , CASE WHEN TRIM(nyu.er_type) = "PREVENTABLE" THEN 1 ELSE 0 END AS preventable_er_visits
    , CASE WHEN CAST(mc.asdb_incurred_dt AS DATE) >= DATE_SUB(st.index_dt, INTERVAL 12 MONTH) THEN 1 ELSE 2 END AS year_flag
FROM 
    (SELECT DISTINCT asdb_member_key, asdb_plan_key, index_dt FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st`) AS st
INNER JOIN 
    `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_ASDB_ICE_OP` AS mc
        ON st.asdb_member_key=mc.asdb_member_key
        AND st.asdb_plan_key=mc.asdb_plan_key
LEFT JOIN 
    `anbc-hcb-prod.cm_medicaid_hcb_prod.ICD10_X_ER_TYPE` AS nyu
        ON TRIM(mc.prindiag) = TRIM(nyu.dx_cd)
WHERE 
    CAST(mc.asdb_incurred_dt AS DATE) BETWEEN DATE_SUB(st.index_dt, INTERVAL 24 MONTH) AND DATE_SUB(st.index_dt, INTERVAL 1 DAY)
    AND CAST(mc.asdb_coe_id AS INT64) = 20100
    AND event_ct=1;

---------------------------------
-- STEP 2: IP Cases (single scan of ASDB_ICE_IP for 24 months)
---------------------------------
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_ip_cases_all`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT 
    mc.asdb_member_key
    , mc.asdb_plan_key
    , st.index_dt
    , mc.asdb_event_start_dt
    , mc.asdb_event_end_dt
    , mc.final_discharge_dt
    , mc.prindiag
    , CASE WHEN mc.asdb_coe_id IN (10200,10700,10800) THEN "Acute"
        WHEN mc.asdb_coe_id IN (10000,10100,10300) THEN "Maternity/Infant"
        ELSE "Non-Acute" END AS ip_type
    , DATE_DIFF(mc.final_discharge_dt, mc.asdb_event_start_dt, DAY) AS calc_los
    , mc.event_ct
    , mc.admit_los
    , mc.paid_los
    , mc.cost AS ip_paid_amt
    , CASE WHEN CAST(mc.asdb_event_start_dt AS DATE) >= DATE_SUB(st.index_dt, INTERVAL 12 MONTH) THEN 1 ELSE 2 END AS year_flag
FROM
    (SELECT DISTINCT asdb_member_key, asdb_plan_key, index_dt FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st`) AS st
INNER JOIN 
    `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_ICE_IP` AS mc
        ON st.asdb_member_key=mc.asdb_member_key
        AND st.asdb_plan_key=mc.asdb_plan_key
WHERE 
    CAST(mc.asdb_event_start_dt AS DATE) BETWEEN DATE_SUB(st.index_dt, INTERVAL 24 MONTH) AND DATE_SUB(st.index_dt, INTERVAL 1 DAY)
    AND mc.event_ct=1;

---------------------------------
-- STEP 3: Med claims flag table (uses _med_claims_all)
---------------------------------
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_med_claims_flag_all`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
WITH clm AS (
    SELECT *
        , CASE WHEN TRIM(asdb_coe_general_type)="Inpatient" OR TRIM(emis_cat)="Institutional Services" THEN "Inpatient"
            WHEN TRIM(emis_cat)="Emergency" THEN "Emergency"
            ELSE "Outpatient" END AS plc_svc_ctg
    FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_med_claims_all`
)
SELECT 
    clm.*, fac.prov_specialty
    -- Cost Metrics
    , CASE WHEN plc_svc_ctg="Inpatient" THEN paid_amt ELSE 0 END AS inpatient_cost
    , CASE WHEN plc_svc_ctg="Emergency" THEN paid_amt ELSE 0 END AS emergency_cost
    , CASE WHEN plc_svc_ctg="Outpatient" THEN paid_amt ELSE 0 END AS outpatient_cost
    , CASE WHEN TRIM(emis_cat)="Community-Based Services" THEN paid_amt ELSE 0 END AS emis_community_cost
    , CASE WHEN TRIM(emis_cat)="Emergency" THEN paid_amt ELSE 0 END AS emis_ed_cost
    , CASE WHEN TRIM(emis_cat)="Home Health" THEN paid_amt ELSE 0 END AS emis_hh_cost
    , CASE WHEN TRIM(emis_cat)="Home-Based Services" THEN paid_amt ELSE 0 END AS emis_home_cost
    , CASE WHEN TRIM(emis_cat)="Inpatient Facility" THEN paid_amt ELSE 0 END AS emis_ip_cost
    , CASE WHEN TRIM(emis_cat)="Institutional Services" THEN paid_amt ELSE 0 END AS emis_ins_cost
    , CASE WHEN TRIM(emis_cat)="Laboratory" THEN paid_amt ELSE 0 END AS emis_lab_cost
    , CASE WHEN TRIM(emis_cat)="Medical Pharmacy" THEN paid_amt ELSE 0 END AS emis_mrx_cost
    , CASE WHEN TRIM(emis_cat)="Mental Health" THEN paid_amt ELSE 0 END AS emis_mh_cost
    , CASE WHEN TRIM(emis_cat)="Misc. Medical" THEN paid_amt ELSE 0 END AS emis_misc_cost
    , CASE WHEN TRIM(emis_cat)="Primary Physician" THEN paid_amt ELSE 0 END AS emis_pcp_cost
    , CASE WHEN TRIM(emis_cat)="Radiology" THEN paid_amt ELSE 0 END AS emis_radio_cost
    , CASE WHEN TRIM(emis_cat)="Selected Ambulatory Facility" THEN paid_amt ELSE 0 END AS emis_ambul_cost
    , CASE WHEN TRIM(emis_cat)="Specialist Physician" THEN paid_amt ELSE 0 END AS emis_spec_cost
    , CASE WHEN TRIM(asdb_coe_general_type)="Long Term Care" THEN paid_amt ELSE 0 END AS coe_ltc_cost
    , CASE WHEN TRIM(asdb_coe_general_type)="Inpatient" AND TRIM(asdb_coe_sub_cat)="Hospital" THEN paid_amt ELSE 0 END AS coe_ip_hos_cost
    , CASE WHEN TRIM(asdb_coe_general_type)="Inpatient" AND TRIM(asdb_coe_sub_cat)="Non Hospital" THEN paid_amt ELSE 0 END AS coe_ip_non_hos_cost
    , CASE WHEN TRIM(asdb_coe_general_type)="Laboratory" AND TRIM(asdb_coe_sub_cat)="Professional" THEN paid_amt ELSE 0 END AS coe_lab_cost
    , CASE WHEN TRIM(asdb_coe_general_type)="Long Term Care" AND TRIM(asdb_coe_sub_cat)="Community Based Services" THEN paid_amt ELSE 0 END AS coe_ltc_community_cost
    , CASE WHEN TRIM(asdb_coe_general_type)="Long Term Care" AND TRIM(asdb_coe_sub_cat)="Home Based Services" THEN paid_amt ELSE 0 END AS coe_ltc_home_cost
    , CASE WHEN TRIM(asdb_coe_general_type)="Long Term Care" AND TRIM(asdb_coe_sub_cat)="Institution" THEN paid_amt ELSE 0 END AS coe_ltc_ins_cost
    , CASE WHEN TRIM(asdb_coe_general_type)="Other" AND TRIM(asdb_coe_sub_cat)="Professional" THEN paid_amt ELSE 0 END AS coe_other_cost
    , CASE WHEN TRIM(asdb_coe_general_type)="Outpatient" AND TRIM(asdb_coe_sub_cat)="Hospital" THEN paid_amt ELSE 0 END AS coe_op_hos_cost
    , CASE WHEN TRIM(asdb_coe_general_type)="Outpatient" AND TRIM(asdb_coe_sub_cat)="Non Hospital" THEN paid_amt ELSE 0 END AS coe_op_non_hos_cost
    , CASE WHEN TRIM(asdb_coe_general_type)="Physician" AND TRIM(asdb_coe_sub_cat)="Anesthesia" THEN paid_amt ELSE 0 END AS coe_anesth_cost
    , CASE WHEN TRIM(asdb_coe_general_type)="Physician" AND TRIM(asdb_coe_sub_cat)="Evaluation & Management" THEN paid_amt ELSE 0 END AS coe_eval_cost
    , CASE WHEN TRIM(asdb_coe_general_type)="Physician" AND TRIM(asdb_coe_sub_cat)="Maternity" THEN paid_amt ELSE 0 END AS coe_maternity_cost
    , CASE WHEN TRIM(asdb_coe_general_type)="Physician" AND TRIM(asdb_coe_sub_cat)="Medicine" THEN paid_amt ELSE 0 END AS coe_mrx_cost
    , CASE WHEN TRIM(asdb_coe_general_type)="Physician" AND TRIM(asdb_coe_sub_cat)="Mental Health" THEN paid_amt ELSE 0 END AS coe_mh_cost
    , CASE WHEN TRIM(asdb_coe_general_type)="Physician" AND TRIM(asdb_coe_sub_cat)="Physician" THEN paid_amt ELSE 0 END AS coe_phy_cost
    , CASE WHEN TRIM(asdb_coe_general_type)="Physician" AND TRIM(asdb_coe_sub_cat)="Surgery" THEN paid_amt ELSE 0 END AS coe_surg_cost
    , CASE WHEN TRIM(asdb_coe_general_type)="Radiology" AND TRIM(asdb_coe_sub_cat)="Professional" THEN paid_amt ELSE 0 END AS coe_radio_cost
    , CASE WHEN TRIM(fac.prov_specialty)="Urgent Care" OR TRIM(location)="20" OR TRIM(servcode)="S9083" THEN paid_amt ELSE 0 END AS uc_cost
    -- Utilization Metrics
    , CASE WHEN TRIM(emis_cat)="Community-Based Services" THEN 1 ELSE 0 END AS emis_community_clm
    , CASE WHEN TRIM(emis_cat)="Emergency" THEN 1 ELSE 0 END AS emis_ed_clm
    , CASE WHEN TRIM(emis_cat)="Home Health" THEN 1 ELSE 0 END AS emis_hh_clm
    , CASE WHEN TRIM(emis_cat)="Home-Based Services" THEN 1 ELSE 0 END AS emis_home_clm
    , CASE WHEN TRIM(emis_cat)="Inpatient Facility" THEN 1 ELSE 0 END AS emis_ip_clm
    , CASE WHEN TRIM(emis_cat)="Institutional Services" THEN 1 ELSE 0 END AS emis_ins_clm
    , CASE WHEN TRIM(emis_cat)="Laboratory" THEN 1 ELSE 0 END AS emis_lab_clm
    , CASE WHEN TRIM(emis_cat)="Medical Pharmacy" THEN 1 ELSE 0 END AS emis_mrx_clm
    , CASE WHEN TRIM(emis_cat)="Mental Health" THEN 1 ELSE 0 END AS emis_mh_clm
    , CASE WHEN TRIM(emis_cat)="Misc. Medical" THEN 1 ELSE 0 END AS emis_misc_clm
    , CASE WHEN TRIM(emis_cat)="Primary Physician" THEN 1 ELSE 0 END AS emis_pcp_clm
    , CASE WHEN TRIM(emis_cat)="Radiology" THEN 1 ELSE 0 END AS emis_radio_clm
    , CASE WHEN TRIM(emis_cat)="Selected Ambulatory Facility" THEN 1 ELSE 0 END AS emis_ambul_clm
    , CASE WHEN TRIM(emis_cat)="Specialist Physician" THEN 1 ELSE 0 END AS emis_spec_clm
    , CASE WHEN TRIM(asdb_coe_general_type)="Long Term Care" THEN 1 ELSE 0 END as ltc_clm
    , CASE WHEN TRIM(asdb_coe_general_type)="Inpatient" AND TRIM(asdb_coe_sub_cat)="Hospital" THEN 1 ELSE 0 END AS coe_ip_hos_clm
    , CASE WHEN TRIM(asdb_coe_general_type)="Inpatient" AND TRIM(asdb_coe_sub_cat)="Non Hospital" THEN 1 ELSE 0 END AS coe_ip_non_hos_clm
    , CASE WHEN TRIM(asdb_coe_general_type)="Laboratory" AND TRIM(asdb_coe_sub_cat)="Professional" THEN 1 ELSE 0 END AS coe_lab_clm
    , CASE WHEN TRIM(asdb_coe_general_type)="Long Term Care" AND TRIM(asdb_coe_sub_cat)="Community Based Services" THEN 1 ELSE 0 END AS coe_ltc_community_clm
    , CASE WHEN TRIM(asdb_coe_general_type)="Long Term Care" AND TRIM(asdb_coe_sub_cat)="Home Based Services" THEN 1 ELSE 0 END AS coe_ltc_home_clm
    , CASE WHEN TRIM(asdb_coe_general_type)="Long Term Care" AND TRIM(asdb_coe_sub_cat)="Institution" THEN 1 ELSE 0 END AS coe_ltc_ins_clm
    , CASE WHEN TRIM(asdb_coe_general_type)="Other" AND TRIM(asdb_coe_sub_cat)="Professional" THEN 1 ELSE 0 END AS coe_other_clm
    , CASE WHEN TRIM(asdb_coe_general_type)="Outpatient" AND TRIM(asdb_coe_sub_cat)="Hospital" THEN 1 ELSE 0 END AS coe_op_hos_clm
    , CASE WHEN TRIM(asdb_coe_general_type)="Outpatient" AND TRIM(asdb_coe_sub_cat)="Non Hospital" THEN 1 ELSE 0 END AS coe_op_non_hos_clm
    , CASE WHEN TRIM(asdb_coe_general_type)="Physician" AND TRIM(asdb_coe_sub_cat)="Anesthesia" THEN 1 ELSE 0 END AS coe_anesth_clm
    , CASE WHEN TRIM(asdb_coe_general_type)="Physician" AND TRIM(asdb_coe_sub_cat)="Evaluation & Management" THEN 1 ELSE 0 END AS coe_eval_clm
    , CASE WHEN TRIM(asdb_coe_general_type)="Physician" AND TRIM(asdb_coe_sub_cat)="Maternity" THEN 1 ELSE 0 END AS coe_maternity_clm
    , CASE WHEN TRIM(asdb_coe_general_type)="Physician" AND TRIM(asdb_coe_sub_cat)="Medicine" THEN 1 ELSE 0 END AS coe_mrx_clm
    , CASE WHEN TRIM(asdb_coe_general_type)="Physician" AND TRIM(asdb_coe_sub_cat)="Mental Health" THEN 1 ELSE 0 END AS coe_mh_clm
    , CASE WHEN TRIM(asdb_coe_general_type)="Physician" AND TRIM(asdb_coe_sub_cat)="Physician" THEN 1 ELSE 0 END AS coe_phy_clm
    , CASE WHEN TRIM(asdb_coe_general_type)="Physician" AND TRIM(asdb_coe_sub_cat)="Surgery" THEN 1 ELSE 0 END AS coe_surg_clm
    , CASE WHEN TRIM(asdb_coe_general_type)="Radiology" AND TRIM(asdb_coe_sub_cat)="Professional" THEN 1 ELSE 0 END AS coe_radio_clm
    , CASE WHEN TRIM(fac.prov_specialty)="Urgent Care" OR TRIM(location)="20" OR TRIM(servcode)="S9083" THEN 1 ELSE 0 END AS uc_clm
    , CASE WHEN (TRIM(clm.revcode) in ("0760","0761","0762","0769") AND (TRIM(clm.billtype) like "13%" or TRIM(clm.billtype) like "85%") 
            AND (TRIM(clm.servcode)) in ("99217","99218","99219","99202","G0378","G0379","")) THEN 1 ELSE 0 END AS obs_clm
FROM clm
LEFT JOIN `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_SVC_PROV` AS fac
    ON clm.asdb_svc_prov_key = fac.asdb_svc_prov_key AND clm.asdb_plan_key = fac.asdb_plan_key;

---------------------------------
-- STEP 4: ED Summary - PIVOTED with yr1/yr2 columns
---------------------------------
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_ed_all`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT 
    st.asdb_member_key
    , st.index_dt
    -- Year 1 ED features
    , COALESCE(SUM(CASE WHEN mc.year_flag = 1 THEN mc.event_ct ELSE 0 END), 0) AS sum_ed_visits_yr1
    , CASE WHEN SUM(CASE WHEN mc.year_flag = 1 THEN mc.event_ct ELSE 0 END) > 0 THEN 1 ELSE 0 END AS ed_flag_yr1
    , COALESCE(SUM(CASE WHEN mc.year_flag = 1 THEN mc.avoidable_er_visits ELSE 0 END), 0) AS sum_avoidable_yr1
    , COALESCE(SUM(CASE WHEN mc.year_flag = 1 THEN mc.unnecessary_er_visits ELSE 0 END), 0) AS sum_unnecessary_yr1
    , COALESCE(SUM(CASE WHEN mc.year_flag = 1 THEN mc.preventable_er_visits ELSE 0 END), 0) AS sum_preventable_yr1
    , SUM(CASE WHEN mc.year_flag = 1 AND TRIM(mc.op_severitylvl) = "1-Low" THEN mc.event_ct ELSE 0 END) AS low_sev_ed_visits_yr1
    , SUM(CASE WHEN mc.year_flag = 1 AND TRIM(mc.op_severitylvl) = "2-Low/Med" THEN mc.event_ct ELSE 0 END) AS low_med_sev_ed_visits_yr1
    , SUM(CASE WHEN mc.year_flag = 1 AND TRIM(mc.op_severitylvl) = "3-Med" THEN mc.event_ct ELSE 0 END) AS med_sev_ed_visits_yr1
    , SUM(CASE WHEN mc.year_flag = 1 AND TRIM(mc.op_severitylvl) = "4-Med/High" THEN mc.event_ct ELSE 0 END) AS med_high_sev_ed_visits_yr1
    , SUM(CASE WHEN mc.year_flag = 1 AND TRIM(mc.op_severitylvl) = "5-High" THEN mc.event_ct ELSE 0 END) AS high_sev_ed_visits_yr1
    , CASE WHEN SUM(CASE WHEN mc.year_flag = 1 AND TRIM(mc.op_severitylvl) = "1-Low" THEN mc.event_ct ELSE 0 END) > 0 THEN 1 ELSE 0 END AS low_sev_ed_flag_yr1
    , CASE WHEN SUM(CASE WHEN mc.year_flag = 1 AND TRIM(mc.op_severitylvl) = "2-Low/Med" THEN mc.event_ct ELSE 0 END) > 0 THEN 1 ELSE 0 END AS low_med_sev_ed_flag_yr1
    , CASE WHEN SUM(CASE WHEN mc.year_flag = 1 AND TRIM(mc.op_severitylvl) = "3-Med" THEN mc.event_ct ELSE 0 END) > 0 THEN 1 ELSE 0 END AS med_sev_ed_flag_yr1
    , CASE WHEN SUM(CASE WHEN mc.year_flag = 1 AND TRIM(mc.op_severitylvl) = "4-Med/High" THEN mc.event_ct ELSE 0 END) > 0 THEN 1 ELSE 0 END AS med_high_sev_ed_flag_yr1
    , CASE WHEN SUM(CASE WHEN mc.year_flag = 1 AND TRIM(mc.op_severitylvl) = "5-High" THEN mc.event_ct ELSE 0 END) > 0 THEN 1 ELSE 0 END AS high_sev_ed_flag_yr1
    -- Year 2 ED features
    , COALESCE(SUM(CASE WHEN mc.year_flag = 2 THEN mc.event_ct ELSE 0 END), 0) AS sum_ed_visits_yr2
    , CASE WHEN SUM(CASE WHEN mc.year_flag = 2 THEN mc.event_ct ELSE 0 END) > 0 THEN 1 ELSE 0 END AS ed_flag_yr2
    , COALESCE(SUM(CASE WHEN mc.year_flag = 2 THEN mc.avoidable_er_visits ELSE 0 END), 0) AS sum_avoidable_yr2
    , COALESCE(SUM(CASE WHEN mc.year_flag = 2 THEN mc.unnecessary_er_visits ELSE 0 END), 0) AS sum_unnecessary_yr2
    , COALESCE(SUM(CASE WHEN mc.year_flag = 2 THEN mc.preventable_er_visits ELSE 0 END), 0) AS sum_preventable_yr2
    , SUM(CASE WHEN mc.year_flag = 2 AND TRIM(mc.op_severitylvl) = "1-Low" THEN mc.event_ct ELSE 0 END) AS low_sev_ed_visits_yr2
    , SUM(CASE WHEN mc.year_flag = 2 AND TRIM(mc.op_severitylvl) = "2-Low/Med" THEN mc.event_ct ELSE 0 END) AS low_med_sev_ed_visits_yr2
    , SUM(CASE WHEN mc.year_flag = 2 AND TRIM(mc.op_severitylvl) = "3-Med" THEN mc.event_ct ELSE 0 END) AS med_sev_ed_visits_yr2
    , SUM(CASE WHEN mc.year_flag = 2 AND TRIM(mc.op_severitylvl) = "4-Med/High" THEN mc.event_ct ELSE 0 END) AS med_high_sev_ed_visits_yr2
    , SUM(CASE WHEN mc.year_flag = 2 AND TRIM(mc.op_severitylvl) = "5-High" THEN mc.event_ct ELSE 0 END) AS high_sev_ed_visits_yr2
    , CASE WHEN SUM(CASE WHEN mc.year_flag = 2 AND TRIM(mc.op_severitylvl) = "1-Low" THEN mc.event_ct ELSE 0 END) > 0 THEN 1 ELSE 0 END AS low_sev_ed_flag_yr2
    , CASE WHEN SUM(CASE WHEN mc.year_flag = 2 AND TRIM(mc.op_severitylvl) = "2-Low/Med" THEN mc.event_ct ELSE 0 END) > 0 THEN 1 ELSE 0 END AS low_med_sev_ed_flag_yr2
    , CASE WHEN SUM(CASE WHEN mc.year_flag = 2 AND TRIM(mc.op_severitylvl) = "3-Med" THEN mc.event_ct ELSE 0 END) > 0 THEN 1 ELSE 0 END AS med_sev_ed_flag_yr2
    , CASE WHEN SUM(CASE WHEN mc.year_flag = 2 AND TRIM(mc.op_severitylvl) = "4-Med/High" THEN mc.event_ct ELSE 0 END) > 0 THEN 1 ELSE 0 END AS med_high_sev_ed_flag_yr2
    , CASE WHEN SUM(CASE WHEN mc.year_flag = 2 AND TRIM(mc.op_severitylvl) = "5-High" THEN mc.event_ct ELSE 0 END) > 0 THEN 1 ELSE 0 END AS high_sev_ed_flag_yr2
FROM 
    (SELECT DISTINCT asdb_member_key, index_dt FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st`) AS st
LEFT JOIN 
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_ed_cases_all` AS mc
        ON st.asdb_member_key = mc.asdb_member_key
        AND st.index_dt = mc.index_dt
GROUP BY 
    st.asdb_member_key, st.index_dt;

---------------------------------
-- STEP 5: IP Summary - PIVOTED with yr1/yr2 columns
---------------------------------
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_ip_all`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT 
    st.asdb_member_key
    , st.index_dt
    -- Year 1 Acute IP
    , CASE WHEN SUM(CASE WHEN mc.year_flag = 1 AND mc.ip_type = "Acute" THEN mc.event_ct ELSE 0 END) > 0 THEN 1 ELSE 0 END AS acute_ip_flag_yr1
    , COALESCE(SUM(CASE WHEN mc.year_flag = 1 AND mc.ip_type = "Acute" THEN mc.event_ct ELSE 0 END), 0) AS sum_acute_ip_admits_yr1
    , COALESCE(SUM(CASE WHEN mc.year_flag = 1 AND mc.ip_type = "Acute" THEN mc.calc_los ELSE 0 END), 0) AS sum_acute_calc_los_yr1
    -- Year 2 Acute IP
    , CASE WHEN SUM(CASE WHEN mc.year_flag = 2 AND mc.ip_type = "Acute" THEN mc.event_ct ELSE 0 END) > 0 THEN 1 ELSE 0 END AS acute_ip_flag_yr2
    , COALESCE(SUM(CASE WHEN mc.year_flag = 2 AND mc.ip_type = "Acute" THEN mc.event_ct ELSE 0 END), 0) AS sum_acute_ip_admits_yr2
    , COALESCE(SUM(CASE WHEN mc.year_flag = 2 AND mc.ip_type = "Acute" THEN mc.calc_los ELSE 0 END), 0) AS sum_acute_calc_los_yr2
FROM 
    (SELECT DISTINCT asdb_member_key, index_dt FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st`) AS st
LEFT JOIN 
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_ip_cases_all` AS mc
        ON st.asdb_member_key = mc.asdb_member_key
        AND st.index_dt = mc.index_dt
GROUP BY 
    st.asdb_member_key, st.index_dt;

---------------------------------
-- STEP 6: OP Visits - PIVOTED with yr1/yr2 columns
---------------------------------
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_op_all`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
WITH clm AS(
    SELECT 
        *
        , CASE WHEN ROW_NUMBER() OVER(PARTITION BY asdb_member_key, index_dt, asdb_plan_key, asdb_svc_prov_key, asdb_incurred_dt, year_flag) = 1 THEN 1 ELSE 0 END AS op_ct
    FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_med_claims_all`
    WHERE TRIM(asdb_coe_general_type) != "Inpatient"
        AND TRIM(emis_cat) != "Institutional Services"
        AND TRIM(emis_cat) != "Emergency"
)
SELECT 
    st.asdb_member_key
    , st.index_dt
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.op_ct ELSE 0 END), 0) AS sum_op_visits_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.op_ct ELSE 0 END), 0) AS sum_op_visits_yr2
FROM 
    (SELECT DISTINCT asdb_member_key, index_dt FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st`) AS st
LEFT JOIN clm
    ON st.asdb_member_key = clm.asdb_member_key
    AND st.index_dt = clm.index_dt
GROUP BY 
    st.asdb_member_key, st.index_dt;

---------------------------------
-- STEP 7: Other Cost Utilization Summary - PIVOTED with yr1/yr2 columns
---------------------------------
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_other_cost_utilization_all`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT
    st.asdb_member_key
    , st.index_dt
    -- Year 1 Utilization
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.emis_community_clm ELSE 0 END), 0) AS emis_community_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.emis_ed_clm ELSE 0 END), 0) AS emis_ed_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.emis_hh_clm ELSE 0 END), 0) AS emis_hh_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.emis_home_clm ELSE 0 END), 0) AS emis_home_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.emis_ip_clm ELSE 0 END), 0) AS emis_ip_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.emis_ins_clm ELSE 0 END), 0) AS emis_ins_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.emis_lab_clm ELSE 0 END), 0) AS emis_lab_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.emis_mrx_clm ELSE 0 END), 0) AS emis_mrx_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.emis_mh_clm ELSE 0 END), 0) AS emis_mh_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.emis_misc_clm ELSE 0 END), 0) AS emis_misc_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.emis_pcp_clm ELSE 0 END), 0) AS emis_pcp_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.emis_radio_clm ELSE 0 END), 0) AS emis_radio_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.emis_ambul_clm ELSE 0 END), 0) AS emis_ambul_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.emis_spec_clm ELSE 0 END), 0) AS emis_spec_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.ltc_clm ELSE 0 END), 0) AS ltc_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.coe_ip_hos_clm ELSE 0 END), 0) AS coe_ip_hos_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.coe_ip_non_hos_clm ELSE 0 END), 0) AS coe_ip_non_hos_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.coe_lab_clm ELSE 0 END), 0) AS coe_lab_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.coe_ltc_community_clm ELSE 0 END), 0) AS coe_ltc_community_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.coe_ltc_home_clm ELSE 0 END), 0) AS coe_ltc_home_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.coe_ltc_ins_clm ELSE 0 END), 0) AS coe_ltc_ins_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.coe_other_clm ELSE 0 END), 0) AS coe_other_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.coe_op_hos_clm ELSE 0 END), 0) AS coe_op_hos_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.coe_op_non_hos_clm ELSE 0 END), 0) AS coe_op_non_hos_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.coe_anesth_clm ELSE 0 END), 0) AS coe_anesth_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.coe_eval_clm ELSE 0 END), 0) AS coe_eval_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.coe_maternity_clm ELSE 0 END), 0) AS coe_maternity_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.coe_mrx_clm ELSE 0 END), 0) AS coe_mrx_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.coe_mh_clm ELSE 0 END), 0) AS coe_mh_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.coe_phy_clm ELSE 0 END), 0) AS coe_phy_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.coe_surg_clm ELSE 0 END), 0) AS coe_surg_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.coe_radio_clm ELSE 0 END), 0) AS coe_radio_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.uc_clm ELSE 0 END), 0) AS uc_clm_yr1
    , COALESCE(SUM(CASE WHEN clm.year_flag = 1 THEN clm.obs_clm ELSE 0 END), 0) AS obs_clm_yr1
    -- Year 2 Utilization
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.emis_community_clm ELSE 0 END), 0) AS emis_community_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.emis_ed_clm ELSE 0 END), 0) AS emis_ed_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.emis_hh_clm ELSE 0 END), 0) AS emis_hh_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.emis_home_clm ELSE 0 END), 0) AS emis_home_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.emis_ip_clm ELSE 0 END), 0) AS emis_ip_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.emis_ins_clm ELSE 0 END), 0) AS emis_ins_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.emis_lab_clm ELSE 0 END), 0) AS emis_lab_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.emis_mrx_clm ELSE 0 END), 0) AS emis_mrx_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.emis_mh_clm ELSE 0 END), 0) AS emis_mh_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.emis_misc_clm ELSE 0 END), 0) AS emis_misc_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.emis_pcp_clm ELSE 0 END), 0) AS emis_pcp_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.emis_radio_clm ELSE 0 END), 0) AS emis_radio_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.emis_ambul_clm ELSE 0 END), 0) AS emis_ambul_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.emis_spec_clm ELSE 0 END), 0) AS emis_spec_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.ltc_clm ELSE 0 END), 0) AS ltc_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.coe_ip_hos_clm ELSE 0 END), 0) AS coe_ip_hos_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.coe_ip_non_hos_clm ELSE 0 END), 0) AS coe_ip_non_hos_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.coe_lab_clm ELSE 0 END), 0) AS coe_lab_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.coe_ltc_community_clm ELSE 0 END), 0) AS coe_ltc_community_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.coe_ltc_home_clm ELSE 0 END), 0) AS coe_ltc_home_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.coe_ltc_ins_clm ELSE 0 END), 0) AS coe_ltc_ins_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.coe_other_clm ELSE 0 END), 0) AS coe_other_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.coe_op_hos_clm ELSE 0 END), 0) AS coe_op_hos_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.coe_op_non_hos_clm ELSE 0 END), 0) AS coe_op_non_hos_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.coe_anesth_clm ELSE 0 END), 0) AS coe_anesth_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.coe_eval_clm ELSE 0 END), 0) AS coe_eval_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.coe_maternity_clm ELSE 0 END), 0) AS coe_maternity_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.coe_mrx_clm ELSE 0 END), 0) AS coe_mrx_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.coe_mh_clm ELSE 0 END), 0) AS coe_mh_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.coe_phy_clm ELSE 0 END), 0) AS coe_phy_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.coe_surg_clm ELSE 0 END), 0) AS coe_surg_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.coe_radio_clm ELSE 0 END), 0) AS coe_radio_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.uc_clm ELSE 0 END), 0) AS uc_clm_yr2
    , COALESCE(SUM(CASE WHEN clm.year_flag = 2 THEN clm.obs_clm ELSE 0 END), 0) AS obs_clm_yr2
FROM 
    (SELECT DISTINCT asdb_member_key, index_dt FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st`) AS st
LEFT JOIN `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_med_claims_flag_all` AS clm
    ON st.asdb_member_key=clm.asdb_member_key
    AND st.index_dt = clm.index_dt
GROUP BY 
    st.asdb_member_key, st.index_dt;
