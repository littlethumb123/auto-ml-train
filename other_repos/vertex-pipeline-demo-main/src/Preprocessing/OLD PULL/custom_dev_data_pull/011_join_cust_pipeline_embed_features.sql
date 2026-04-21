CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_predictors` 
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT
    a.*
    , b.* EXCEPT(asdb_member_key, index_date, baby_dob)
    , c.* EXCEPT(asdb_member_key, asdb_plan_key, index_dt, oud, autoimmune)
    , d.* EXCEPT(individual_id)
FROM
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_risk_w_nicu_flags` AS a
LEFT JOIN
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_labs_joined` AS b
        ON a.asdb_member_key = b.asdb_member_key
        AND a.index_date = b.index_date
LEFT JOIN
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_non_embedding_features` AS c
        ON a.asdb_member_key = c.asdb_member_key
        AND a.index_date = c.index_dt
LEFT JOIN
    `anbc-hcb-prod.cm_medicaid_hcb_prod.medicaid_transformer_embed_scores_hist` AS d
        ON a.asdb_member_key = d.individual_id
        AND DATE_TRUNC(a.index_date, MONTH) = DATE_TRUNC(d.index_dt, MONTH)
;


-----------------------
-- get training IDS ---
-----------------------
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_training_ids` 
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT DISTINCT
    mom_key 
FROM 
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_final_timepoint` 
WHERE
    ABS(MOD(FARM_FINGERPRINT(CAST(mom_key AS STRING)), 10)) < 8
;
--45,544


CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_testing_ids` 
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT DISTINCT
    mom_key 
FROM 
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_final_timepoint` 
WHERE
    ABS(MOD(FARM_FINGERPRINT(CAST(mom_key AS STRING)), 10)) >= 8
;
--11,280

SELECT COUNT(DISTINCT mom_key) FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_final_timepoint`
--56824 = 45544 + 11280 confirmed!