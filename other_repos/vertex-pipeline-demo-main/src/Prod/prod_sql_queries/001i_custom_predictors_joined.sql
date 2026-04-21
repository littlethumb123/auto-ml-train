-------------------------------
--- predictors data pulling ---
--- ASDB risk flags: visit-level join (one row per visit). Filter: asdb_incurred_dt < {INDEX_DT}.
-------------------------------
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_asdb_risk_flags`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
WITH cohort AS (
    SELECT
        mem.asdb_member_key
        , mem.index_dt
        , mem.mom_age
        , mem.gest_age
        , mem2.ethnicity_desc
    FROM
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st` AS mem
    LEFT JOIN
        `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_MEMBER` AS mem2
        ON mem.asdb_member_key = mem2.asdb_member_key
),
visit_with_flags AS (
    SELECT
        v.asdb_member_key
        , mem.index_dt
        , mem.mom_age
        , mem2.ethnicity_desc
        , mem.gest_age
        , CASE WHEN v.asdb_incurred_dt < DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_pre_term_labor_codes = 1 THEN 1 ELSE 0 END AS pre_term_labor_clm
        , CASE WHEN v.asdb_incurred_dt < DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_pre_term_delivery_codes = 1 THEN 1 ELSE 0 END AS pre_term_delivery_clm
        , CASE WHEN v.asdb_incurred_dt < DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_dm_codes = 1 THEN 1 ELSE 0 END AS prior_dm
        , CASE WHEN v.asdb_incurred_dt > DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_dm_codes = 1 THEN 1 ELSE 0 END AS current_dm
        , v.pre_dm
        , v.f_hist_dm
        , v.aps
        , CASE WHEN v.art_icd = 1 OR v.art_cpt = 1 THEN 1 ELSE 0 END AS art
        , v.autoimmune
        , v.hist_ob_comp
        , CASE WHEN v.asdb_incurred_dt < DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_ht_codes = 1 THEN 1 ELSE 0 END AS prior_ht
        , CASE WHEN v.asdb_incurred_dt > DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_ht_codes = 1 THEN 1 ELSE 0 END AS current_preg_ht
        , CASE WHEN v.asdb_incurred_dt < DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_pre_e_codes = 1 THEN 1 ELSE 0 END AS prior_pre_e
        , CASE WHEN v.asdb_incurred_dt > DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_pre_e_codes = 1 THEN 1 ELSE 0 END AS current_pre_e
        , v.obesity
        , v.pcos
        , v.renal
        , v.sle
        , CASE WHEN v.asdb_incurred_dt > DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_97 = 1 THEN 1 ELSE 0 END AS multi
        , CASE WHEN v.asdb_incurred_dt > DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_92 = 1 THEN 1 ELSE 0 END AS bleeding_in_current_preg
        , v.trophoblastic
        , v.Alcohol
        , v.OUD
        , v.Cannabis
        , v.Cocaine
        , v.Nicotine
        , v.Other_drug
    FROM
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_asdb_visit_risk_presence` AS v
    INNER JOIN
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st` AS mem
        ON v.asdb_member_key = mem.asdb_member_key
    LEFT JOIN
        `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_MEMBER` AS mem2
        ON mem.asdb_member_key = mem2.asdb_member_key
    WHERE v.asdb_incurred_dt < {INDEX_DT}
),
icd_agg AS (
    SELECT
        asdb_member_key
        , index_dt
        , mom_age
        , ethnicity_desc
        , gest_age
        , MAX(pre_term_labor_clm) AS pre_term_labor_clm
        , MAX(pre_term_delivery_clm) AS pre_term_delivery_clm
        , MAX(prior_dm) AS prior_dm
        , MAX(current_dm) AS current_dm
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
    FROM visit_with_flags
    GROUP BY asdb_member_key, index_dt, mom_age, ethnicity_desc, gest_age
)
SELECT
    co.asdb_member_key
    , co.mom_age
    , co.ethnicity_desc
    , co.gest_age
    , COALESCE(ia.pre_term_labor_clm, 0) AS pre_term_labor_clm
    , COALESCE(ia.pre_term_delivery_clm, 0) AS pre_term_delivery_clm
    , COALESCE(ia.prior_dm, 0) AS prior_dm
    , COALESCE(ia.current_dm, 0) AS current_dm
    , COALESCE(ia.pre_dm, 0) AS pre_dm
    , COALESCE(ia.f_hist_dm, 0) AS f_hist_dm
    , COALESCE(ia.aps, 0) AS aps
    , COALESCE(ia.art, 0) AS art
    , COALESCE(ia.autoimmune, 0) AS autoimmune
    , COALESCE(ia.hist_ob_comp, 0) AS hist_ob_comp
    , COALESCE(ia.prior_ht, 0) AS prior_ht
    , COALESCE(ia.current_preg_ht, 0) AS current_preg_ht
    , COALESCE(ia.prior_pre_e, 0) AS prior_pre_e
    , COALESCE(ia.current_pre_e, 0) AS current_pre_e
    , COALESCE(ia.obesity, 0) AS obesity
    , COALESCE(ia.pcos, 0) AS pcos
    , COALESCE(ia.renal, 0) AS renal
    , COALESCE(ia.sle, 0) AS sle
    , COALESCE(ia.multi, 0) AS multi
    , COALESCE(ia.bleeding_in_current_preg, 0) AS bleeding_in_current_preg
    , COALESCE(ia.trophoblastic, 0) AS trophoblastic
    , COALESCE(ia.Alcohol, 0) AS Alcohol
    , COALESCE(ia.OUD, 0) AS OUD
    , COALESCE(ia.Cannabis, 0) AS Cannabis
    , COALESCE(ia.Cocaine, 0) AS Cocaine
    , COALESCE(ia.Nicotine, 0) AS Nicotine
    , COALESCE(ia.Other_drug, 0) AS Other_drug
FROM cohort AS co
LEFT JOIN icd_agg AS ia
    ON co.asdb_member_key = ia.asdb_member_key AND co.index_dt = ia.index_dt
;

-- Komodo risk flags: visit-level join (one row per visit). Filter: incurred_dt < {INDEX_DT}.
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_kmdo_risk_flags`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
WITH cohort AS (
    SELECT
        mem.asdb_member_key
        , mem.index_dt
        , mem.mom_age
        , mem.gest_age
        , mem2.ethnicity_desc
    FROM
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st` AS mem
    LEFT JOIN
        `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_MEMBER` AS mem2
        ON mem.asdb_member_key = mem2.asdb_member_key
),
visit_with_flags AS (
    SELECT
        v.asdb_member_key
        , v.index_dt
        , mem.mom_age
        , mem2.ethnicity_desc
        , mem.gest_age
        , CASE WHEN v.incurred_dt < DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_pre_term_labor_codes = 1 THEN 1 ELSE 0 END AS pre_term_labor_clm
        , CASE WHEN v.incurred_dt < DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_pre_term_delivery_codes = 1 THEN 1 ELSE 0 END AS pre_term_delivery_clm
        , CASE WHEN v.incurred_dt < DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_dm_codes = 1 THEN 1 ELSE 0 END AS prior_dm
        , CASE WHEN v.incurred_dt > DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_dm_codes = 1 THEN 1 ELSE 0 END AS current_dm
        , v.pre_dm
        , v.f_hist_dm
        , v.aps
        , v.art_icd AS art
        , v.autoimmune
        , v.hist_ob_comp
        , CASE WHEN v.incurred_dt < DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_ht_codes = 1 THEN 1 ELSE 0 END AS prior_ht
        , CASE WHEN v.incurred_dt > DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_ht_codes = 1 THEN 1 ELSE 0 END AS current_preg_ht
        , CASE WHEN v.incurred_dt < DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_pre_e_codes = 1 THEN 1 ELSE 0 END AS prior_pre_e
        , CASE WHEN v.incurred_dt > DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_pre_e_codes = 1 THEN 1 ELSE 0 END AS current_pre_e
        , v.obesity
        , v.pcos
        , v.renal
        , v.sle
        , CASE WHEN v.incurred_dt > DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_97 = 1 THEN 1 ELSE 0 END AS multi
        , CASE WHEN v.incurred_dt > DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_92 = 1 THEN 1 ELSE 0 END AS bleeding_in_current_preg
        , v.trophoblastic
        , v.Alcohol
        , v.OUD
        , v.Cannabis
        , v.Cocaine
        , v.Nicotine
        , v.Other_drug
    FROM
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_kmdo_visit_risk_presence` AS v
    INNER JOIN
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st` AS mem
        ON v.asdb_member_key = mem.asdb_member_key AND v.index_dt = mem.index_dt
    LEFT JOIN
        `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_MEMBER` AS mem2
        ON mem.asdb_member_key = mem2.asdb_member_key
    WHERE v.incurred_dt < {INDEX_DT}
),
icd_agg AS (
    SELECT
        asdb_member_key
        , index_dt
        , mom_age
        , ethnicity_desc
        , gest_age
        , MAX(pre_term_labor_clm) AS pre_term_labor_clm
        , MAX(pre_term_delivery_clm) AS pre_term_delivery_clm
        , MAX(prior_dm) AS prior_dm
        , MAX(current_dm) AS current_dm
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
    FROM visit_with_flags
    GROUP BY asdb_member_key, index_dt, mom_age, ethnicity_desc, gest_age
),
art_from_cpt AS (
    SELECT
        c.asdb_member_key
        , c.index_dt
        , 1 AS art_cpt
    FROM
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_kmdo_cpt_and_revcode` AS c
    INNER JOIN
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st` AS m
        ON c.asdb_member_key = m.asdb_member_key AND c.index_dt = m.index_dt
    WHERE c.procedure = 'S4042' AND c.incurred_dt < {INDEX_DT}
    GROUP BY c.asdb_member_key, c.index_dt
)
SELECT
    co.asdb_member_key
    , co.mom_age
    , co.ethnicity_desc
    , co.gest_age
    , COALESCE(ia.pre_term_labor_clm, 0) AS pre_term_labor_clm
    , COALESCE(ia.pre_term_delivery_clm, 0) AS pre_term_delivery_clm
    , COALESCE(ia.prior_dm, 0) AS prior_dm
    , COALESCE(ia.current_dm, 0) AS current_dm
    , COALESCE(ia.pre_dm, 0) AS pre_dm
    , COALESCE(ia.f_hist_dm, 0) AS f_hist_dm
    , COALESCE(ia.aps, 0) AS aps
    , CASE WHEN COALESCE(ia.art, 0) = 1 OR ac.art_cpt = 1 THEN 1 ELSE 0 END AS art
    , COALESCE(ia.autoimmune, 0) AS autoimmune
    , COALESCE(ia.hist_ob_comp, 0) AS hist_ob_comp
    , COALESCE(ia.prior_ht, 0) AS prior_ht
    , COALESCE(ia.current_preg_ht, 0) AS current_preg_ht
    , COALESCE(ia.prior_pre_e, 0) AS prior_pre_e
    , COALESCE(ia.current_pre_e, 0) AS current_pre_e
    , COALESCE(ia.obesity, 0) AS obesity
    , COALESCE(ia.pcos, 0) AS pcos
    , COALESCE(ia.renal, 0) AS renal
    , COALESCE(ia.sle, 0) AS sle
    , COALESCE(ia.multi, 0) AS multi
    , COALESCE(ia.bleeding_in_current_preg, 0) AS bleeding_in_current_preg
    , COALESCE(ia.trophoblastic, 0) AS trophoblastic
    , COALESCE(ia.Alcohol, 0) AS Alcohol
    , COALESCE(ia.OUD, 0) AS OUD
    , COALESCE(ia.Cannabis, 0) AS Cannabis
    , COALESCE(ia.Cocaine, 0) AS Cocaine
    , COALESCE(ia.Nicotine, 0) AS Nicotine
    , COALESCE(ia.Other_drug, 0) AS Other_drug
FROM cohort AS co
LEFT JOIN icd_agg AS ia
    ON co.asdb_member_key = ia.asdb_member_key AND co.index_dt = ia.index_dt
LEFT JOIN art_from_cpt AS ac
    ON co.asdb_member_key = ac.asdb_member_key AND co.index_dt = ac.index_dt
;

-- EDW risk flags: visit-level join (one row per claim line). Filter: incurred_dt < {INDEX_DT}.
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_edw_risk_flags`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
WITH cohort AS (
    SELECT
        mem.asdb_member_key
        , mem.index_dt
        , mem.mom_age
        , mem.gest_age
        , mem2.ethnicity_desc
    FROM
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st` AS mem
    LEFT JOIN
        `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_MEMBER` AS mem2
        ON mem.asdb_member_key = mem2.asdb_member_key
),
visit_with_flags AS (
    SELECT
        v.asdb_member_key
        , v.index_dt
        , mem.mom_age
        , mem2.ethnicity_desc
        , mem.gest_age
        , CASE WHEN v.incurred_dt < DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_pre_term_labor_codes = 1 THEN 1 ELSE 0 END AS pre_term_labor_clm
        , CASE WHEN v.incurred_dt < DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_pre_term_delivery_codes = 1 THEN 1 ELSE 0 END AS pre_term_delivery_clm
        , CASE WHEN v.incurred_dt < DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_dm_codes = 1 THEN 1 ELSE 0 END AS prior_dm
        , CASE WHEN v.incurred_dt > DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_dm_codes = 1 THEN 1 ELSE 0 END AS current_dm
        , v.pre_dm
        , v.f_hist_dm
        , v.aps
        , CASE WHEN v.art_icd = 1 OR v.art_cpt = 1 THEN 1 ELSE 0 END AS art
        , v.autoimmune
        , v.hist_ob_comp
        , CASE WHEN v.incurred_dt < DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_ht_codes = 1 THEN 1 ELSE 0 END AS prior_ht
        , CASE WHEN v.incurred_dt > DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_ht_codes = 1 THEN 1 ELSE 0 END AS current_preg_ht
        , CASE WHEN v.incurred_dt < DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_pre_e_codes = 1 THEN 1 ELSE 0 END AS prior_pre_e
        , CASE WHEN v.incurred_dt > DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_pre_e_codes = 1 THEN 1 ELSE 0 END AS current_pre_e
        , v.obesity
        , v.pcos
        , v.renal
        , v.sle
        , CASE WHEN v.incurred_dt > DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_97 = 1 THEN 1 ELSE 0 END AS multi
        , CASE WHEN v.incurred_dt > DATE_SUB({INDEX_DT}, INTERVAL mem.gest_age WEEK) AND v.has_92 = 1 THEN 1 ELSE 0 END AS bleeding_in_current_preg
        , v.trophoblastic
        , v.Alcohol
        , v.OUD
        , v.Cannabis
        , v.Cocaine
        , v.Nicotine
        , v.Other_drug
    FROM
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_edw_visit_risk_presence` AS v
    INNER JOIN
        `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st` AS mem
        ON v.asdb_member_key = mem.asdb_member_key AND v.index_dt = mem.index_dt
    LEFT JOIN
        `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_MEMBER` AS mem2
        ON mem.asdb_member_key = mem2.asdb_member_key
    WHERE v.incurred_dt < {INDEX_DT}
),
icd_agg AS (
    SELECT
        asdb_member_key
        , index_dt
        , mom_age
        , ethnicity_desc
        , gest_age
        , MAX(pre_term_labor_clm) AS pre_term_labor_clm
        , MAX(pre_term_delivery_clm) AS pre_term_delivery_clm
        , MAX(prior_dm) AS prior_dm
        , MAX(current_dm) AS current_dm
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
    FROM visit_with_flags
    GROUP BY asdb_member_key, index_dt, mom_age, ethnicity_desc, gest_age
)
SELECT
    co.asdb_member_key
    , co.mom_age
    , co.ethnicity_desc
    , co.gest_age
    , COALESCE(ia.pre_term_labor_clm, 0) AS pre_term_labor_clm
    , COALESCE(ia.pre_term_delivery_clm, 0) AS pre_term_delivery_clm
    , COALESCE(ia.prior_dm, 0) AS prior_dm
    , COALESCE(ia.current_dm, 0) AS current_dm
    , COALESCE(ia.pre_dm, 0) AS pre_dm
    , COALESCE(ia.f_hist_dm, 0) AS f_hist_dm
    , COALESCE(ia.aps, 0) AS aps
    , COALESCE(ia.art, 0) AS art
    , COALESCE(ia.autoimmune, 0) AS autoimmune
    , COALESCE(ia.hist_ob_comp, 0) AS hist_ob_comp
    , COALESCE(ia.prior_ht, 0) AS prior_ht
    , COALESCE(ia.current_preg_ht, 0) AS current_preg_ht
    , COALESCE(ia.prior_pre_e, 0) AS prior_pre_e
    , COALESCE(ia.current_pre_e, 0) AS current_pre_e
    , COALESCE(ia.obesity, 0) AS obesity
    , COALESCE(ia.pcos, 0) AS pcos
    , COALESCE(ia.renal, 0) AS renal
    , COALESCE(ia.sle, 0) AS sle
    , COALESCE(ia.multi, 0) AS multi
    , COALESCE(ia.bleeding_in_current_preg, 0) AS bleeding_in_current_preg
    , COALESCE(ia.trophoblastic, 0) AS trophoblastic
    , COALESCE(ia.Alcohol, 0) AS Alcohol
    , COALESCE(ia.OUD, 0) AS OUD
    , COALESCE(ia.Cannabis, 0) AS Cannabis
    , COALESCE(ia.Cocaine, 0) AS Cocaine
    , COALESCE(ia.Nicotine, 0) AS Nicotine
    , COALESCE(ia.Other_drug, 0) AS Other_drug
FROM cohort AS co
LEFT JOIN icd_agg AS ia
    ON co.asdb_member_key = ia.asdb_member_key AND co.index_dt = ia.index_dt
;

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
    joint.asdb_member_key
    , joint.mom_age
    , joint.ethnicity_desc
    , MAX(joint.pre_term_labor_clm) AS pre_term_labor_clm
    , MAX(joint.pre_term_delivery_clm) AS pre_term_delivery_clm
    , CASE WHEN MAX(joint.pre_term_labor_clm) = 1 OR MAX(joint.pre_term_delivery_clm) = 1 THEN 1 ELSE 0 END AS pre_term_max
    , MAX(joint.prior_dm) AS prior_dm
    , MAX(joint.current_dm) As current_dm
    , MAX(joint.pre_dm) AS pre_dm
    , MAX(joint.f_hist_dm) AS f_hist_dm
    , MAX(joint.aps) AS aps
    , MAX(joint.art) AS art
    , MAX(joint.autoimmune) AS autoimmune
    , MAX(joint.hist_ob_comp) AS hist_ob_comp
    , MAX(joint.prior_ht) AS prior_ht
    , MAX(joint.current_preg_ht) AS current_preg_ht
    , MAX(joint.prior_pre_e) AS prior_pre_e
    , MAX(joint.current_pre_e) AS current_pre_e
    , MAX(joint.obesity) AS obesity
    , MAX(joint.pcos) AS pcos
    , MAX(joint.renal) AS renal
    , MAX(joint.sle) AS sle
    , MAX(joint.multi) AS multi
    , MAX(joint.bleeding_in_current_preg) AS bleeding_in_current_preg
    , MAX(joint.trophoblastic) AS trophoblastic
    , MAX(joint.Alcohol) AS Alcohol
    , MAX(joint.OUD) AS OUD
    , MAX(joint.Cannabis) AS Cannabis
    , MAX(joint.Cocaine) AS Cocaine
    , MAX(joint.Nicotine) AS Nicotine
    , MAX(joint.Other_drug) AS Other_drug
    , MAX(joint.gest_age) AS gest_age
FROM
    joint
GROUP BY
    joint.asdb_member_key
    , joint.mom_age
    , joint.ethnicity_desc
ORDER BY
    joint.asdb_member_key
;