------------------------------------------------------------------
--- pull data needed to create claims and utilization features ---
--- OPTIMIZED: Single scan of ASDB_CLM_DATA_STAGE for both years --
--- Creates _med_claims_all with year_flag column               ---
--- Downstream queries filter: WHERE year_flag = 1 (yr1) or 2   ---
------------------------------------------------------------------

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_med_claims_all`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT
    st.asdb_member_key
    , st.asdb_plan_key
    , clm.claimid
    , clm.asdb_coe_id
    , coe.asdb_coe_general_type
    , coe.asdb_coe_sub_cat
    , clm.asdb_svc_prov_key
    , clm.asdb_pcp_prov_key
    , CAST(clm.asdb_incurred_dt AS DATE) AS asdb_incurred_dt
    , CAST(clm.asdb_paid_dt AS DATE) AS asdb_paid_dt
    , clm.location
    , clm.revcode
    , clm.servcode
    , clm.billtype
    , clm.prindiag
    , clm.paid_amt
    , clm.emis_cat
    -- Year flag: 1 = most recent 12 months, 2 = prior 12 months
    , CASE 
        WHEN CAST(clm.asdb_incurred_dt AS DATE) >= DATE_SUB({INDEX_DT}, INTERVAL 12 MONTH) THEN 1
        ELSE 2
      END AS year_flag
FROM 
    `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st` AS st
INNER JOIN 
    `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_CLM_DATA_STAGE` AS clm
        ON st.asdb_member_key = clm.asdb_member_key
LEFT JOIN 
    `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_TYPE_OF_SERVICE` AS coe
        ON clm.asdb_coe_id = coe.asdb_coe_id
WHERE 1 = 1
    AND clm.final_claim = 1
    AND TRIM(UPPER(clm.status_header)) = "PAID"
    AND TRIM(UPPER(clm.status_detail)) NOT IN ("DENY", "DENIED")
    AND CAST(clm.asdb_incurred_dt AS DATE) BETWEEN DATE_SUB({INDEX_DT}, INTERVAL 24 MONTH) AND DATE_SUB({INDEX_DT}, INTERVAL 1 DAY)
;
