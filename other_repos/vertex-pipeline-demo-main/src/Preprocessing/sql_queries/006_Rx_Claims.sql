-- Rx Claims Query - OPTIMIZED
-- Single scan of ASDB_RX_DATA_STAGE for full 24-month window
-- Creates _rx_claims_all with year_flag, then _rx_summary_all with yr1/yr2 columns pivoted
-- Variables: GCP_PROJECT, GCP_DB, PREFIX, OWNER, COST_CENTER, DEFAULT_EXP

-- Step 1: Single scan - create claims table with year_flag

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_rx_claims_all`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT DISTINCT
    st.asdb_member_key
    , st.asdb_plan_key
    , st.index_dt
    , rx.asdb_pharmacy_key
    , rx.prescriptionnum
    , CAST(rx.asdb_incurred_dt AS DATE) AS disp_dt
    , rx.days_supply
    , rx.script_ct
    , ROUND(CASE WHEN rx.days_supply >= 0.1 AND rx.days_supply < 30 THEN 30
               ELSE rx.days_supply END/30) AS scripts
    , rx.ndcnum AS ndc_cd
    , rx.gpi AS adjudicated_gpi_cd
    , SUBSTR(rx.gpi,1,4) AS gpi4
    , SUBSTR(rx.gpi,1,2) AS gpi2
    , rx.billed_amt
    , rx.claim_adj_amt
    , rx.copay_amt
    , CASE WHEN rx.pharmacytype="R" THEN 1 ELSE 0 END AS retail_flag
    , CASE WHEN rx.pharmacytype="M" THEN 1 ELSE 0 END AS mail_order_flag
    , CASE WHEN rx.drugtype = 3 THEN 1 ELSE 0 END AS generic_fill_flag
    , CASE WHEN rx.drugtype = 2 THEN 1 ELSE 0 END AS branded_generic_fill_flag
    , CASE WHEN rx.drugtype = 4 THEN 1 ELSE 0 END AS otc_fill_flag
    , CASE WHEN rx.drugtype = 1 THEN 1 ELSE 0 END AS ss_brand_fill_flag
    , CASE WHEN rx.drugtype = 5 THEN 1 ELSE 0 END AS ms_brand_fill_flag
    , CASE WHEN rx.formularyflag="F" or rx.drugtype = 3 THEN 1 ELSE 0 END AS formulary_fill_flag
    , CASE WHEN c.maint_drug_cd="X" THEN 1 ELSE 0 END AS maint_drug_flag
    , CASE WHEN d.ndc IS NOT NULL THEN 1 ELSE 0 END AS specialty_rx_flag
    -- Year flag: 1 = most recent 12 months, 2 = prior 12 months
    , CASE 
        WHEN CAST(rx.asdb_incurred_dt AS DATE) >= DATE_SUB(st.index_dt, INTERVAL 12 MONTH) THEN 1
        ELSE 2
      END AS year_flag
FROM 
    (SELECT DISTINCT asdb_member_key, asdb_plan_key, index_dt FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st`) AS st
INNER JOIN 
    `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_RX_DATA_STAGE` AS rx
        ON st.asdb_member_key = rx.asdb_member_key
        AND st.asdb_plan_key = rx.asdb_plan_key
LEFT JOIN 
    `edp-prod-hcbstorage.edp_hcb_core_cnsv.BASE_DRUG` AS c
        ON TRIM(rx.ndcnum) = TRIM(c.ndc_cd)
LEFT JOIN 
    `edp-prod-hcbstorage.edp_hcb_core_srcv.specdrug_pww_universal_spec_list` AS d
        ON TRIM(rx.ndcnum) = TRIM(d.ndc)
WHERE 
    rx.ClaimType = "P"
    AND CAST(rx.asdb_incurred_dt AS DATE) BETWEEN DATE_SUB(st.index_dt, INTERVAL 24 MONTH) AND DATE_SUB(st.index_dt, INTERVAL 1 DAY);

-- Step 2: Create pivoted summary table with yr1/yr2 columns (one row per member+index_dt)
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_rx_summary_all`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT 
    asdb_member_key
    , index_dt
    -- Year 1 features
    , COALESCE(SUM(CASE WHEN year_flag = 1 THEN 1 ELSE 0 END), 0) AS rx_claim_cnt_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 THEN days_supply ELSE 0 END), 0) AS days_supply_sum_yr1
    , COUNT(DISTINCT CASE WHEN year_flag = 1 THEN ndc_cd END) AS ndc_cnt_yr1
    , COUNT(DISTINCT CASE WHEN year_flag = 1 THEN adjudicated_gpi_cd END) AS gpi_cnt_yr1
    , COUNT(DISTINCT CASE WHEN year_flag = 1 THEN gpi4 END) AS gpi4_cnt_yr1
    , COUNT(DISTINCT CASE WHEN year_flag = 1 THEN gpi2 END) AS gpi2_cnt_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 THEN retail_flag ELSE 0 END), 0) AS retail_fills_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 THEN mail_order_flag ELSE 0 END), 0) AS mail_order_fills_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 THEN generic_fill_flag ELSE 0 END), 0) AS generic_fills_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 THEN branded_generic_fill_flag ELSE 0 END), 0) AS branded_generic_fills_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 THEN otc_fill_flag ELSE 0 END), 0) AS otc_fills_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 THEN ss_brand_fill_flag ELSE 0 END), 0) AS ss_brand_fills_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 THEN ms_brand_fill_flag ELSE 0 END), 0) AS ms_brand_fills_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 THEN formulary_fill_flag ELSE 0 END), 0) AS formulary_fills_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 THEN maint_drug_flag ELSE 0 END), 0) AS maint_drug_fills_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 AND gpi2="27" THEN scripts ELSE 0 END), 0) AS antidiabetic_scripts_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 AND gpi2="27" THEN days_supply ELSE 0 END), 0) AS antidiabetic_days_supply_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 AND gpi2="33" THEN scripts ELSE 0 END), 0) AS beta_blocker_scripts_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 AND gpi2="33" THEN days_supply ELSE 0 END), 0) AS beta_blocker_days_supply_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 AND gpi2="36" THEN scripts ELSE 0 END), 0) AS antihypertensive_scripts_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 AND gpi2="36" THEN days_supply ELSE 0 END), 0) AS antihypertensive_days_supply_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 AND gpi2="39" THEN scripts ELSE 0 END), 0) AS lipid_lowering_scripts_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 AND gpi2="39" THEN days_supply ELSE 0 END), 0) AS lipid_lowering_days_supply_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 AND gpi2="34" THEN scripts ELSE 0 END), 0) AS calcium_channel_blk_scripts_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 AND gpi2="34" THEN days_supply ELSE 0 END), 0) AS calcium_channel_blk_days_supply_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 AND gpi2="37" THEN scripts ELSE 0 END), 0) AS diuretic_scripts_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 AND gpi2="37" THEN days_supply ELSE 0 END), 0) AS diuretic_days_supply_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 AND gpi2="32" THEN scripts ELSE 0 END), 0) AS antianginal_agent_scripts_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 AND gpi2="32" THEN days_supply ELSE 0 END), 0) AS antianginal_agent_days_supply_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 AND gpi2="58" THEN scripts ELSE 0 END), 0) AS antidepressant_scripts_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 AND gpi2="58" THEN days_supply ELSE 0 END), 0) AS antidepressant_days_supply_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 AND gpi2="59" THEN scripts ELSE 0 END), 0) AS antipsychotic_scripts_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 AND gpi2="59" THEN days_supply ELSE 0 END), 0) AS antipsychotic_days_supply_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 AND gpi2="57" THEN scripts ELSE 0 END), 0) AS antianxiety_scripts_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 AND gpi2="57" THEN days_supply ELSE 0 END), 0) AS antianxiety_days_supply_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 AND gpi2="72" THEN scripts ELSE 0 END), 0) AS anticonvulsant_scripts_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 AND gpi2="72" THEN days_supply ELSE 0 END), 0) AS anticonvulsant_days_supply_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 AND gpi4="4440" THEN scripts ELSE 0 END), 0) AS inhaled_steroid_scripts_yr1
    , COALESCE(SUM(CASE WHEN year_flag = 1 AND gpi4="4440" THEN days_supply ELSE 0 END), 0) AS inhaled_steroid_days_supply_yr1
    -- Year 2 features
    , COALESCE(SUM(CASE WHEN year_flag = 2 THEN 1 ELSE 0 END), 0) AS rx_claim_cnt_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 THEN days_supply ELSE 0 END), 0) AS days_supply_sum_yr2
    , COUNT(DISTINCT CASE WHEN year_flag = 2 THEN ndc_cd END) AS ndc_cnt_yr2
    , COUNT(DISTINCT CASE WHEN year_flag = 2 THEN adjudicated_gpi_cd END) AS gpi_cnt_yr2
    , COUNT(DISTINCT CASE WHEN year_flag = 2 THEN gpi4 END) AS gpi4_cnt_yr2
    , COUNT(DISTINCT CASE WHEN year_flag = 2 THEN gpi2 END) AS gpi2_cnt_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 THEN retail_flag ELSE 0 END), 0) AS retail_fills_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 THEN mail_order_flag ELSE 0 END), 0) AS mail_order_fills_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 THEN generic_fill_flag ELSE 0 END), 0) AS generic_fills_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 THEN branded_generic_fill_flag ELSE 0 END), 0) AS branded_generic_fills_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 THEN otc_fill_flag ELSE 0 END), 0) AS otc_fills_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 THEN ss_brand_fill_flag ELSE 0 END), 0) AS ss_brand_fills_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 THEN ms_brand_fill_flag ELSE 0 END), 0) AS ms_brand_fills_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 THEN formulary_fill_flag ELSE 0 END), 0) AS formulary_fills_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 THEN maint_drug_flag ELSE 0 END), 0) AS maint_drug_fills_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 AND gpi2="27" THEN scripts ELSE 0 END), 0) AS antidiabetic_scripts_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 AND gpi2="27" THEN days_supply ELSE 0 END), 0) AS antidiabetic_days_supply_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 AND gpi2="33" THEN scripts ELSE 0 END), 0) AS beta_blocker_scripts_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 AND gpi2="33" THEN days_supply ELSE 0 END), 0) AS beta_blocker_days_supply_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 AND gpi2="36" THEN scripts ELSE 0 END), 0) AS antihypertensive_scripts_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 AND gpi2="36" THEN days_supply ELSE 0 END), 0) AS antihypertensive_days_supply_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 AND gpi2="39" THEN scripts ELSE 0 END), 0) AS lipid_lowering_scripts_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 AND gpi2="39" THEN days_supply ELSE 0 END), 0) AS lipid_lowering_days_supply_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 AND gpi2="34" THEN scripts ELSE 0 END), 0) AS calcium_channel_blk_scripts_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 AND gpi2="34" THEN days_supply ELSE 0 END), 0) AS calcium_channel_blk_days_supply_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 AND gpi2="37" THEN scripts ELSE 0 END), 0) AS diuretic_scripts_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 AND gpi2="37" THEN days_supply ELSE 0 END), 0) AS diuretic_days_supply_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 AND gpi2="32" THEN scripts ELSE 0 END), 0) AS antianginal_agent_scripts_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 AND gpi2="32" THEN days_supply ELSE 0 END), 0) AS antianginal_agent_days_supply_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 AND gpi2="58" THEN scripts ELSE 0 END), 0) AS antidepressant_scripts_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 AND gpi2="58" THEN days_supply ELSE 0 END), 0) AS antidepressant_days_supply_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 AND gpi2="59" THEN scripts ELSE 0 END), 0) AS antipsychotic_scripts_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 AND gpi2="59" THEN days_supply ELSE 0 END), 0) AS antipsychotic_days_supply_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 AND gpi2="57" THEN scripts ELSE 0 END), 0) AS antianxiety_scripts_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 AND gpi2="57" THEN days_supply ELSE 0 END), 0) AS antianxiety_days_supply_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 AND gpi2="72" THEN scripts ELSE 0 END), 0) AS anticonvulsant_scripts_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 AND gpi2="72" THEN days_supply ELSE 0 END), 0) AS anticonvulsant_days_supply_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 AND gpi4="4440" THEN scripts ELSE 0 END), 0) AS inhaled_steroid_scripts_yr2
    , COALESCE(SUM(CASE WHEN year_flag = 2 AND gpi4="4440" THEN days_supply ELSE 0 END), 0) AS inhaled_steroid_days_supply_yr2
FROM 
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_rx_claims_all`
GROUP BY 
    asdb_member_key, index_dt;
