-- Final Feature Assembly
-- Joins all feature tables on asdb_member_key only (one row per member)
-- Variables: GCP_PROJECT, GCP_DB, PREFIX, OWNER, COST_CENTER, DEFAULT_EXP

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_predictors` 
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT
    a.*
    , b.* EXCEPT(asdb_member_key)
    , c.* EXCEPT(asdb_member_key, oud, autoimmune)
    , d.* EXCEPT(individual_id)
FROM 
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_risk_flags` AS a
LEFT JOIN
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_all_labs_joined` AS b
        ON a.asdb_member_key = b.asdb_member_key
LEFT JOIN
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_non_embedding_features` AS c
        ON a.asdb_member_key = c.asdb_member_key
LEFT JOIN
    `anbc-hcb-prod.cm_medicaid_hcb_prod.medicaid_transformer_embed_scores_hist` AS d
        ON a.asdb_member_key = d.individual_id
        AND DATE_TRUNC(CURRENT_DATE(), MONTH) = DATE_TRUNC(d.index_dt, MONTH)
;
