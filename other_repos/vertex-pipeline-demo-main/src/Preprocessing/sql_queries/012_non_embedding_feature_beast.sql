-- Non-Embedding Features Query
-- Creates comprehensive feature table combining all previous tables
-- Variables: GCP_PROJECT, GCP_DB, PREFIX, OWNER, COST_CENTER, DEFAULT_EXP
-- All joins are on asdb_member_key AND index_dt (each member+index_dt is one row)

DROP TABLE IF EXISTS `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_non_embedding_features`;

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_non_embedding_features`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT DISTINCT
    st.asdb_member_key
    , st.index_dt
    -- ED features (from pivoted _ed_all)
    , COALESCE(ed.sum_ed_visits_yr1, 0) AS sum_ed_visits_yr1
    , COALESCE(ed.ed_flag_yr1, 0) AS ed_flag_yr1
    , COALESCE(ed.sum_avoidable_yr1, 0) AS sum_avoidable_yr1
    , COALESCE(ed.sum_unnecessary_yr1, 0) AS sum_unnecessary_yr1
    , COALESCE(ed.sum_preventable_yr1, 0) AS sum_preventable_yr1
    , COALESCE(ed.low_sev_ed_visits_yr1, 0) AS low_sev_ed_visits_yr1
    , COALESCE(ed.low_med_sev_ed_visits_yr1, 0) AS low_med_sev_ed_visits_yr1
    , COALESCE(ed.med_sev_ed_visits_yr1, 0) AS med_sev_ed_visits_yr1
    , COALESCE(ed.med_high_sev_ed_visits_yr1, 0) AS med_high_sev_ed_visits_yr1
    , COALESCE(ed.high_sev_ed_visits_yr1, 0) AS high_sev_ed_visits_yr1
    , COALESCE(ed.low_sev_ed_flag_yr1, 0) AS low_sev_ed_flag_yr1
    , COALESCE(ed.low_med_sev_ed_flag_yr1, 0) AS low_med_sev_ed_flag_yr1
    , COALESCE(ed.med_sev_ed_flag_yr1, 0) AS med_sev_ed_flag_yr1
    , COALESCE(ed.med_high_sev_ed_flag_yr1, 0) AS med_high_sev_ed_flag_yr1
    , COALESCE(ed.high_sev_ed_flag_yr1, 0) AS high_sev_ed_flag_yr1
    , COALESCE(ed.ed_flag_yr2, 0) AS ed_flag_yr2   
    , COALESCE(ed.sum_ed_visits_yr2, 0) AS sum_ed_visits_yr2
    , COALESCE(ed.sum_avoidable_yr2, 0) AS sum_avoidable_yr2
    , COALESCE(ed.sum_unnecessary_yr2, 0) AS sum_unnecessary_yr2
    , COALESCE(ed.sum_preventable_yr2, 0) AS sum_preventable_yr2
    , COALESCE(ed.low_sev_ed_visits_yr2, 0) AS low_sev_ed_visits_yr2
    , COALESCE(ed.low_med_sev_ed_visits_yr2, 0) AS low_med_sev_ed_visits_yr2
    , COALESCE(ed.med_sev_ed_visits_yr2, 0) AS med_sev_ed_visits_yr2
    , COALESCE(ed.med_high_sev_ed_visits_yr2, 0) AS med_high_sev_ed_visits_yr2
    , COALESCE(ed.high_sev_ed_visits_yr2, 0) AS high_sev_ed_visits_yr2
    , COALESCE(ed.low_sev_ed_flag_yr2, 0) AS low_sev_ed_flag_yr2
    , COALESCE(ed.low_med_sev_ed_flag_yr2, 0) AS low_med_sev_ed_flag_yr2
    , COALESCE(ed.med_sev_ed_flag_yr2, 0) AS med_sev_ed_flag_yr2
    , COALESCE(ed.med_high_sev_ed_flag_yr2, 0) AS med_high_sev_ed_flag_yr2
    , COALESCE(ed.high_sev_ed_flag_yr2, 0) AS high_sev_ed_flag_yr2
    -- IP features (from pivoted _ip_all)
    , COALESCE(ip.acute_ip_flag_yr1, 0) AS acute_ip_flag_yr1
    , COALESCE(ip.sum_acute_ip_admits_yr1, 0) AS sum_acute_ip_admits_yr1
    , COALESCE(ip.sum_acute_calc_los_yr1, 0) AS sum_acute_calc_los_yr1
    , COALESCE(ip.acute_ip_flag_yr2, 0) AS acute_ip_flag_yr2
    , COALESCE(ip.sum_acute_ip_admits_yr2, 0) AS sum_acute_ip_admits_yr2
    , COALESCE(ip.sum_acute_calc_los_yr2, 0) AS sum_acute_calc_los_yr2
    -- OP features (from pivoted _op_all)
    , COALESCE(op.sum_op_visits_yr1, 0) AS sum_op_visits_yr1
    , COALESCE(op.sum_op_visits_yr2, 0) AS sum_op_visits_yr2
    -- Utilization features (from pivoted _other_cost_utilization_all)
    , COALESCE(ut.emis_community_clm_yr1, 0) AS emis_community_clm_yr1
    , COALESCE(ut.emis_ed_clm_yr1, 0) AS emis_ed_clm_yr1
    , COALESCE(ut.emis_hh_clm_yr1, 0) AS emis_hh_clm_yr1
    , COALESCE(ut.emis_home_clm_yr1, 0) AS emis_home_clm_yr1
    , COALESCE(ut.emis_ip_clm_yr1, 0) AS emis_ip_clm_yr1
    , COALESCE(ut.emis_ins_clm_yr1, 0) AS emis_ins_clm_yr1
    , COALESCE(ut.emis_lab_clm_yr1, 0) AS emis_lab_clm_yr1
    , COALESCE(ut.emis_mrx_clm_yr1, 0) AS emis_mrx_clm_yr1
    , COALESCE(ut.emis_mh_clm_yr1, 0) AS emis_mh_clm_yr1
    , COALESCE(ut.emis_misc_clm_yr1, 0) AS emis_misc_clm_yr1
    , COALESCE(ut.emis_pcp_clm_yr1, 0) AS emis_pcp_clm_yr1
    , COALESCE(ut.emis_radio_clm_yr1, 0) AS emis_radio_clm_yr1
    , COALESCE(ut.emis_ambul_clm_yr1, 0) AS emis_ambul_clm_yr1
    , COALESCE(ut.emis_spec_clm_yr1, 0) AS emis_spec_clm_yr1
    , COALESCE(ut.ltc_clm_yr1, 0) AS ltc_clm_yr1
    , COALESCE(ut.coe_ip_hos_clm_yr1, 0) AS coe_ip_hos_clm_yr1
    , COALESCE(ut.coe_ip_non_hos_clm_yr1, 0) AS coe_ip_non_hos_clm_yr1
    , COALESCE(ut.coe_lab_clm_yr1, 0) AS coe_lab_clm_yr1
    , COALESCE(ut.coe_ltc_community_clm_yr1, 0) AS coe_ltc_community_clm_yr1
    , COALESCE(ut.coe_ltc_home_clm_yr1, 0) AS coe_ltc_home_clm_yr1
    , COALESCE(ut.coe_ltc_ins_clm_yr1, 0) AS coe_ltc_ins_clm_yr1
    , COALESCE(ut.coe_other_clm_yr1, 0) AS coe_other_clm_yr1
    , COALESCE(ut.coe_op_hos_clm_yr1, 0) AS coe_op_hos_clm_yr1
    , COALESCE(ut.coe_op_non_hos_clm_yr1, 0) AS coe_op_non_hos_clm_yr1
    , COALESCE(ut.coe_anesth_clm_yr1, 0) AS coe_anesth_clm_yr1
    , COALESCE(ut.coe_eval_clm_yr1, 0) AS coe_eval_clm_yr1
    , COALESCE(ut.coe_maternity_clm_yr1, 0) AS coe_maternity_clm_yr1
    , COALESCE(ut.coe_mrx_clm_yr1, 0) AS coe_mrx_clm_yr1
    , COALESCE(ut.coe_mh_clm_yr1, 0) AS coe_mh_clm_yr1
    , COALESCE(ut.coe_phy_clm_yr1, 0) AS coe_phy_clm_yr1
    , COALESCE(ut.coe_surg_clm_yr1, 0) AS coe_surg_clm_yr1
    , COALESCE(ut.coe_radio_clm_yr1, 0) AS coe_radio_clm_yr1
    , COALESCE(ut.uc_clm_yr1, 0) AS uc_clm_yr1
    , COALESCE(ut.obs_clm_yr1, 0) AS obs_clm_yr1   
    , COALESCE(ut.emis_community_clm_yr2, 0) AS emis_community_clm_yr2
    , COALESCE(ut.emis_ed_clm_yr2, 0) AS emis_ed_clm_yr2
    , COALESCE(ut.emis_hh_clm_yr2, 0) AS emis_hh_clm_yr2
    , COALESCE(ut.emis_home_clm_yr2, 0) AS emis_home_clm_yr2
    , COALESCE(ut.emis_ip_clm_yr2, 0) AS emis_ip_clm_yr2
    , COALESCE(ut.emis_ins_clm_yr2, 0) AS emis_ins_clm_yr2
    , COALESCE(ut.emis_lab_clm_yr2, 0) AS emis_lab_clm_yr2
    , COALESCE(ut.emis_mrx_clm_yr2, 0) AS emis_mrx_clm_yr2
    , COALESCE(ut.emis_mh_clm_yr2, 0) AS emis_mh_clm_yr2
    , COALESCE(ut.emis_misc_clm_yr2, 0) AS emis_misc_clm_yr2
    , COALESCE(ut.emis_pcp_clm_yr2, 0) AS emis_pcp_clm_yr2
    , COALESCE(ut.emis_radio_clm_yr2, 0) AS emis_radio_clm_yr2
    , COALESCE(ut.emis_ambul_clm_yr2, 0) AS emis_ambul_clm_yr2
    , COALESCE(ut.emis_spec_clm_yr2, 0) AS emis_spec_clm_yr2
    , COALESCE(ut.ltc_clm_yr2, 0) AS ltc_clm_yr2
    , COALESCE(ut.coe_ip_hos_clm_yr2, 0) AS coe_ip_hos_clm_yr2
    , COALESCE(ut.coe_ip_non_hos_clm_yr2, 0) AS coe_ip_non_hos_clm_yr2
    , COALESCE(ut.coe_lab_clm_yr2, 0) AS coe_lab_clm_yr2
    , COALESCE(ut.coe_ltc_community_clm_yr2, 0) AS coe_ltc_community_clm_yr2
    , COALESCE(ut.coe_ltc_home_clm_yr2, 0) AS coe_ltc_home_clm_yr2
    , COALESCE(ut.coe_ltc_ins_clm_yr2, 0) AS coe_ltc_ins_clm_yr2
    , COALESCE(ut.coe_other_clm_yr2, 0) AS coe_other_clm_yr2
    , COALESCE(ut.coe_op_hos_clm_yr2, 0) AS coe_op_hos_clm_yr2
    , COALESCE(ut.coe_op_non_hos_clm_yr2, 0) AS coe_op_non_hos_clm_yr2
    , COALESCE(ut.coe_anesth_clm_yr2, 0) AS coe_anesth_clm_yr2
    , COALESCE(ut.coe_eval_clm_yr2, 0) AS coe_eval_clm_yr2
    , COALESCE(ut.coe_maternity_clm_yr2, 0) AS coe_maternity_clm_yr2
    , COALESCE(ut.coe_mrx_clm_yr2, 0) AS coe_mrx_clm_yr2
    , COALESCE(ut.coe_mh_clm_yr2, 0) AS coe_mh_clm_yr2
    , COALESCE(ut.coe_phy_clm_yr2, 0) AS coe_phy_clm_yr2
    , COALESCE(ut.coe_surg_clm_yr2, 0) AS coe_surg_clm_yr2
    , COALESCE(ut.coe_radio_clm_yr2, 0) AS coe_radio_clm_yr2
    , COALESCE(ut.uc_clm_yr2, 0) AS uc_clm_yr2
    , COALESCE(ut.obs_clm_yr2, 0) AS obs_clm_yr2
    -- Conditions features
    , COALESCE(cond.abdominal_pain, 0) AS abdominal_pain
    , COALESCE(cond.AID, 0) AS AID
    , COALESCE(cond.IDA, 0) AS IDA
    , COALESCE(cond.ANX, 0) AS ANX
    , COALESCE(cond.OST, 0) AS OST
    , COALESCE(cond.AST, 0) AS AST
    , COALESCE(cond.AUT, 0) AS AUT
    , COALESCE(cond.CHO, 0) AS CHO
    , COALESCE(cond.burns, 0) AS burns
    , COALESCE(cond.cad, 0) AS cad
    , COALESCE(cond.Cancer, 0) AS Cancer
    , COALESCE(cond.narc, 0) AS narc
    , COALESCE(cond.CBD, 0) AS CBD
    , COALESCE(cond.CHF, 0) AS CHF
    , COALESCE(cond.CRF, 0) AS CRF
    , COALESCE(cond.VNA, 0) AS VNA
    , COALESCE(cond.CHD, 0) AS CHD
    , COALESCE(cond.COP, 0) AS COP
    , COALESCE(cond.CYS, 0) AS CYS
    , COALESCE(cond.DEP, 0) AS DEP
    , COALESCE(cond.DIA, 0) AS DIA
    , COALESCE(cond.EDO, 0) AS EDO
    , COALESCE(cond.esrd, 0) AS esrd
    , COALESCE(cond.EPL, 0) AS EPL
    , COALESCE(cond.CRO, 0) AS CRO
    , COALESCE(cond.MOH, 0) AS MOH
    , COALESCE(cond.HEM, 0) AS HEM
    , COALESCE(cond.HepC, 0) AS HepC
    , COALESCE(cond.HYP, 0) AS HYP
    , COALESCE(cond.HYC, 0) AS HYC
    , COALESCE(cond.immune, 0) AS immune
    , COALESCE(cond.intel_dsblty, 0) AS intel_dsblty
    , COALESCE(cond.meta_cancer, 0) AS meta_cancer
    , COALESCE(cond.liver_dis, 0) AS liver_dis
    , COALESCE(cond.MSS, 0) AS MSS
    , COALESCE(cond.OBE, 0) AS OBE
    , COALESCE(cond.oud, 0) AS oud
    , COALESCE(cond.liver_other, 0) AS liver_other
    , COALESCE(cond.paralysis, 0) AS paralysis
    , COALESCE(cond.PAR, 0) AS PAR
    , COALESCE(cond.PUD, 0) AS PUD
    , COALESCE(cond.hmd, 0) AS hmd
    , COALESCE(cond.PVD, 0) AS PVD
    , COALESCE(cond.autoimmune, 0) AS autoimmune
    , COALESCE(cond.DEM, 0) AS DEM
    , COALESCE(cond.SCA, 0) AS SCA
    , COALESCE(cond.sleep_apnea, 0) AS sleep_apnea
    , COALESCE(cond.spinal_inj, 0) AS spinal_inj
    , COALESCE(cond.back, 0) AS back
    , COALESCE(cond.substance, 0) AS substance
    , COALESCE(cond.ALC, 0) AS ALC
    , COALESCE(cond.bipolar, 0) AS bipolar 
    , COALESCE(cond.psychoses, 0) AS psychoses
    , COALESCE(cond.major_chronic_cnt, 0) AS major_chronic_cnt 
    -- Rx Year 1 features (from pivoted _rx_summary_all)
    , COALESCE(rx.rx_claim_cnt_yr1, 0) AS rx_claim_cnt_yr1
    , COALESCE(rx.days_supply_sum_yr1, 0) AS days_supply_sum_yr1
    , COALESCE(rx.ndc_cnt_yr1, 0) AS ndc_cnt_yr1
    , COALESCE(rx.gpi_cnt_yr1, 0) AS gpi_cnt_yr1
    , COALESCE(rx.gpi4_cnt_yr1, 0) AS gpi4_cnt_yr1
    , COALESCE(rx.gpi2_cnt_yr1, 0) AS gpi2_cnt_yr1
    , COALESCE(rx.retail_fills_yr1, 0) AS retail_fills_yr1
    , COALESCE(rx.mail_order_fills_yr1, 0) AS mail_order_fills_yr1
    , COALESCE(rx.generic_fills_yr1, 0) AS generic_fills_yr1
    , COALESCE(rx.branded_generic_fills_yr1, 0) AS branded_generic_fills_yr1
    , COALESCE(rx.otc_fills_yr1, 0) AS otc_fills_yr1
    , COALESCE(rx.ss_brand_fills_yr1, 0) AS ss_brand_fills_yr1
    , COALESCE(rx.ms_brand_fills_yr1, 0) AS ms_brand_fills_yr1
    , COALESCE(rx.formulary_fills_yr1, 0) AS formulary_fills_yr1
    , COALESCE(rx.maint_drug_fills_yr1, 0) AS maint_drug_fills_yr1
    , COALESCE(rx.antidiabetic_scripts_yr1, 0) AS antidiabetic_scripts_yr1
    , COALESCE(rx.antidiabetic_days_supply_yr1, 0) AS antidiabetic_days_supply_yr1
    , COALESCE(rx.beta_blocker_scripts_yr1, 0) AS beta_blocker_scripts_yr1
    , COALESCE(rx.beta_blocker_days_supply_yr1, 0) AS beta_blocker_days_supply_yr1
    , COALESCE(rx.antihypertensive_scripts_yr1, 0) AS antihypertensive_scripts_yr1
    , COALESCE(rx.antihypertensive_days_supply_yr1, 0) AS antihypertensive_days_supply_yr1
    , COALESCE(rx.lipid_lowering_scripts_yr1, 0) AS lipid_lowering_scripts_yr1
    , COALESCE(rx.lipid_lowering_days_supply_yr1, 0) AS lipid_lowering_days_supply_yr1
    , COALESCE(rx.calcium_channel_blk_scripts_yr1, 0) AS calcium_channel_blk_scripts_yr1
    , COALESCE(rx.calcium_channel_blk_days_supply_yr1, 0) AS calcium_channel_blk_days_supply_yr1
    , COALESCE(rx.diuretic_scripts_yr1, 0) AS diuretic_scripts_yr1
    , COALESCE(rx.diuretic_days_supply_yr1, 0) AS diuretic_days_supply_yr1
    , COALESCE(rx.antianginal_agent_scripts_yr1, 0) AS antianginal_agent_scripts_yr1
    , COALESCE(rx.antianginal_agent_days_supply_yr1, 0) AS antianginal_agent_days_supply_yr1
    , COALESCE(rx.antidepressant_scripts_yr1, 0) AS antidepressant_scripts_yr1
    , COALESCE(rx.antidepressant_days_supply_yr1, 0) AS antidepressant_days_supply_yr1
    , COALESCE(rx.antipsychotic_scripts_yr1, 0) AS antipsychotic_scripts_yr1
    , COALESCE(rx.antipsychotic_days_supply_yr1, 0) AS antipsychotic_days_supply_yr1
    , COALESCE(rx.antianxiety_scripts_yr1, 0) AS antianxiety_scripts_yr1
    , COALESCE(rx.antianxiety_days_supply_yr1, 0) AS antianxiety_days_supply_yr1
    , COALESCE(rx.anticonvulsant_scripts_yr1, 0) AS anticonvulsant_scripts_yr1
    , COALESCE(rx.anticonvulsant_days_supply_yr1, 0) AS anticonvulsant_days_supply_yr1
    , COALESCE(rx.inhaled_steroid_scripts_yr1, 0) AS inhaled_steroid_scripts_yr1
    , COALESCE(rx.inhaled_steroid_days_supply_yr1, 0) AS inhaled_steroid_days_supply_yr1
    -- Rx Year 2 features (from pivoted _rx_summary_all)
    , COALESCE(rx.rx_claim_cnt_yr2, 0) AS rx_claim_cnt_yr2
    , COALESCE(rx.days_supply_sum_yr2, 0) AS days_supply_sum_yr2
    , COALESCE(rx.ndc_cnt_yr2, 0) AS ndc_cnt_yr2
    , COALESCE(rx.gpi_cnt_yr2, 0) AS gpi_cnt_yr2
    , COALESCE(rx.gpi4_cnt_yr2, 0) AS gpi4_cnt_yr2
    , COALESCE(rx.gpi2_cnt_yr2, 0) AS gpi2_cnt_yr2
    , COALESCE(rx.retail_fills_yr2, 0) AS retail_fills_yr2
    , COALESCE(rx.mail_order_fills_yr2, 0) AS mail_order_fills_yr2
    , COALESCE(rx.generic_fills_yr2, 0) AS generic_fills_yr2
    , COALESCE(rx.branded_generic_fills_yr2, 0) AS branded_generic_fills_yr2
    , COALESCE(rx.otc_fills_yr2, 0) AS otc_fills_yr2
    , COALESCE(rx.ss_brand_fills_yr2, 0) AS ss_brand_fills_yr2
    , COALESCE(rx.ms_brand_fills_yr2, 0) AS ms_brand_fills_yr2
    , COALESCE(rx.formulary_fills_yr2, 0) AS formulary_fills_yr2
    , COALESCE(rx.maint_drug_fills_yr2, 0) AS maint_drug_fills_yr2
    , COALESCE(rx.antidiabetic_scripts_yr2, 0) AS antidiabetic_scripts_yr2
    , COALESCE(rx.antidiabetic_days_supply_yr2, 0) AS antidiabetic_days_supply_yr2
    , COALESCE(rx.beta_blocker_scripts_yr2, 0) AS beta_blocker_scripts_yr2
    , COALESCE(rx.beta_blocker_days_supply_yr2, 0) AS beta_blocker_days_supply_yr2
    , COALESCE(rx.antihypertensive_scripts_yr2, 0) AS antihypertensive_scripts_yr2
    , COALESCE(rx.antihypertensive_days_supply_yr2, 0) AS antihypertensive_days_supply_yr2
    , COALESCE(rx.lipid_lowering_scripts_yr2, 0) AS lipid_lowering_scripts_yr2
    , COALESCE(rx.lipid_lowering_days_supply_yr2, 0) AS lipid_lowering_days_supply_yr2
    , COALESCE(rx.calcium_channel_blk_scripts_yr2, 0) AS calcium_channel_blk_scripts_yr2
    , COALESCE(rx.calcium_channel_blk_days_supply_yr2, 0) AS calcium_channel_blk_days_supply_yr2
    , COALESCE(rx.diuretic_scripts_yr2, 0) AS diuretic_scripts_yr2
    , COALESCE(rx.diuretic_days_supply_yr2, 0) AS diuretic_days_supply_yr2
    , COALESCE(rx.antianginal_agent_scripts_yr2, 0) AS antianginal_agent_scripts_yr2
    , COALESCE(rx.antianginal_agent_days_supply_yr2, 0) AS antianginal_agent_days_supply_yr2
    , COALESCE(rx.antidepressant_scripts_yr2, 0) AS antidepressant_scripts_yr2
    , COALESCE(rx.antidepressant_days_supply_yr2, 0) AS antidepressant_days_supply_yr2
    , COALESCE(rx.antipsychotic_scripts_yr2, 0) AS antipsychotic_scripts_yr2
    , COALESCE(rx.antipsychotic_days_supply_yr2, 0) AS antipsychotic_days_supply_yr2
    , COALESCE(rx.antianxiety_scripts_yr2, 0) AS antianxiety_scripts_yr2
    , COALESCE(rx.antianxiety_days_supply_yr2, 0) AS antianxiety_days_supply_yr2
    , COALESCE(rx.anticonvulsant_scripts_yr2, 0) AS anticonvulsant_scripts_yr2
    , COALESCE(rx.anticonvulsant_days_supply_yr2, 0) AS anticonvulsant_days_supply_yr2
    , COALESCE(rx.inhaled_steroid_scripts_yr2, 0) AS inhaled_steroid_scripts_yr2
    , COALESCE(rx.inhaled_steroid_days_supply_yr2, 0) AS inhaled_steroid_days_supply_yr2
    -- Demographics features
    , COALESCE(demo.agenbr, 0) AS agenbr
    , COALESCE(demo.gender, 'U') AS gender
    , COALESCE(demo.ethnicity_code, 'U') AS ethnicity_code
    , COALESCE(demo.primarylanguage_desc, 'Unknown') AS primarylanguage_desc
    , COALESCE(demo.tenure_yr1, 0) AS tenure_yr1
    , COALESCE(demo.tenure_yr2, 0) AS tenure_yr2
    , COALESCE(demo.urbsubr, 'U') AS urbsubr
    , COALESCE(demo.zip_weight_avg_medinc, 0) AS zip_weight_avg_medinc
    -- ACS features
    , COALESCE(acs.social_risk_score, 0) AS acs_social_risk_score
    , COALESCE(acs.sdi_score, 0) AS sdi_score
    , COALESCE(acs.svi_score, 0) AS svi_score
    , COALESCE(acs.adi_score, 0) AS adi_score
    -- CSDI features
    , COALESCE(csdi.citizenship_index, 0) AS citizenship_index
    , COALESCE(csdi.education_index, 0) AS education_index
    , COALESCE(csdi.food_access, 0) AS food_access
    , COALESCE(csdi.health_access, 0) AS health_access
    , COALESCE(csdi.health_habits, 0) AS health_habits
    , COALESCE(csdi.housing_desert, 0) AS housing_desert
    , COALESCE(csdi.housing_ownership, 0) AS housing_ownership     
    , COALESCE(csdi.housing_quality, 0) AS housing_quality     
    , COALESCE(csdi.income_index, 0) AS income_index    
    , COALESCE(csdi.income_inequality, 0) AS income_inequality    
    , COALESCE(csdi.language_score, 0) AS language_score    
    , COALESCE(csdi.natural_disaster, 0) AS natural_disaster 
    , COALESCE(csdi.poverty_score, 0) AS poverty_score 
    , COALESCE(csdi.proactive_health, 0) AS proactive_health
    , COALESCE(csdi.racial_diversity, 0) AS racial_diversity
    , COALESCE(csdi.social_isolation, 0) AS social_isolation    
    , COALESCE(csdi.technology_access, 0) AS technology_access    
    , COALESCE(csdi.transport_access, 0) AS transport_access     
    , COALESCE(csdi.unemployment_index, 0) AS unemployment_index    
    , COALESCE(csdi.water_quality, 0) AS water_quality     
    , COALESCE(csdi.disability_score, 0) AS disability_score    
    , COALESCE(csdi.health_infra, 0) AS health_infra    
    , COALESCE(csdi.social_risk_score, 0) AS csdi_social_risk_score   
    -- Preventative care features
    , prev.first_prv_dt
    , prev.last_prv_dt
    , COALESCE(prev.sum_pcp, 0) AS sum_pcp
    , COALESCE(prev.sum_spec, 0) AS sum_spec
    , COALESCE(prev.sum_ob, 0) AS sum_ob
    , COALESCE(prev.sum_dme, 0) AS sum_dme
    , COALESCE(prev.sum_chol_lab, 0) AS sum_chol_lab
    , COALESCE(prev.sum_a1c_lab, 0) AS sum_a1c_lab
    , COALESCE(prev.sum_chemo, 0) AS sum_chemo
    , COALESCE(prev.cms_alc_scrn, 0) AS cms_alc_scrn
    , COALESCE(prev.cms_bone_scrn, 0) AS cms_bone_scrn
    , COALESCE(prev.cms_cvd_scrn, 0) AS cms_cvd_scrn
    , COALESCE(prev.cms_col_scrn, 0) AS cms_col_scrn
    , COALESCE(prev.cms_tobacco, 0) AS cms_tobacco
    , COALESCE(prev.cms_dep_scrn, 0) AS cms_dep_scrn
    , COALESCE(prev.cms_t2d_scrn, 0) AS cms_t2d_scrn
    , COALESCE(prev.cms_hepb_scrn, 0) AS cms_hepb_scrn
    , COALESCE(prev.cms_hepb_vax, 0) AS cms_hepb_vax
    , COALESCE(prev.cms_ibt_cvd, 0) AS cms_ibt_cvd
    , COALESCE(prev.cms_ibt_obese, 0) AS cms_ibt_obese
    , COALESCE(prev.cms_flu_vax, 0) AS cms_flu_vax
    , COALESCE(prev.cms_lung_cancer_scrn, 0) AS cms_lung_cancer_scrn
    , COALESCE(prev.cms_nutrition, 0) AS cms_nutrition
    , COALESCE(prev.cms_pneum_vax, 0) AS cms_pneum_vax
    , COALESCE(prev.cms_hpv_scrn, 0) AS cms_hpv_scrn
    , COALESCE(prev.cms_sti_scrn, 0) AS cms_sti_scrn
    , COALESCE(prev.cms_mam_scrn, 0) AS cms_mam_scrn
    , COALESCE(prev.cms_pap, 0) AS cms_pap
    , COALESCE(prev.cms_pelvic, 0) AS cms_pelvic
    , COALESCE(prev.cms_t2d_train, 0) AS cms_t2d_train
    , COALESCE(prev.cms_prost_cancer_scrn, 0) AS cms_prost_cancer_scrn
FROM (SELECT DISTINCT asdb_member_key, index_dt FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st`) AS st
LEFT JOIN `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_ed_all` AS ed
    ON st.asdb_member_key = ed.asdb_member_key
    AND st.index_dt = ed.index_dt
LEFT JOIN `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_ip_all` AS ip
    ON st.asdb_member_key = ip.asdb_member_key
    AND st.index_dt = ip.index_dt
LEFT JOIN `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_op_all` AS op
    ON st.asdb_member_key = op.asdb_member_key
    AND st.index_dt = op.index_dt
LEFT JOIN `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_other_cost_utilization_all` AS ut
    ON st.asdb_member_key = ut.asdb_member_key
    AND st.index_dt = ut.index_dt
LEFT JOIN `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_conditions` AS cond
    ON st.asdb_member_key = cond.asdb_member_key
    AND st.index_dt = cond.index_dt
LEFT JOIN `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_rx_summary_all` AS rx
    ON st.asdb_member_key = rx.asdb_member_key
    AND st.index_dt = rx.index_dt
LEFT JOIN `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_demographics` AS demo
    ON st.asdb_member_key = demo.asdb_member_key
    AND st.index_dt = demo.index_dt
LEFT JOIN `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_acs` AS acs
    ON st.asdb_member_key = acs.asdb_member_key
    AND st.index_dt = acs.index_dt
LEFT JOIN `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_csdi` AS csdi
    ON st.asdb_member_key = csdi.asdb_member_key
    AND st.index_dt = csdi.index_dt
LEFT JOIN `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_preventative_summary` AS prev
    ON st.asdb_member_key = prev.asdb_member_key
    AND st.index_dt = prev.index_dt;
