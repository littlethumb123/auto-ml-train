-- Demographics Query
-- Creates demographics table with member information and tenure calculations
-- Variables: GCP_PROJECT, GCP_DB, PREFIX, OWNER, COST_CENTER, DEFAULT_EXP, ST

-- Drop existing tables
DROP TABLE IF EXISTS `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_demographics_months`;
DROP TABLE IF EXISTS `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_demographics`;

-- Create demographics months table
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_demographics_months`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
SELECT
    mnth.asdb_member_key
    , st.index_dt
    , CAST(mnth.asdb_elig_dt AS DATE) AS asdb_elig_dt
FROM
    (SELECT asdb_member_key, asdb_elig_dt FROM `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_ELIG_DATA_MBR_PER_MTH`) AS mnth
LEFT JOIN
    (SELECT asdb_member_key, index_dt FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st`) AS st
        ON st.asdb_member_key = mnth.asdb_member_key
WHERE CAST(mnth.asdb_elig_dt AS DATE) BETWEEN DATE_SUB(st.index_dt, INTERVAL 24 MONTH) AND DATE_ADD(st.index_dt, INTERVAL 6 MONTH);

-- Create demographics table
-- Single pass: filter elig once to [index_dt - 24 mo, index_dt + 6 mo] (expanded for post_mnths), then COUNTIF for tenure_yr1, tenure_yr2, post_mnths (prod-style logic; post_mnths kept for training only).
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_demographics`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
WITH elig_filtered AS (
    SELECT DISTINCT
        mnth.asdb_member_key,
        st.index_dt,
        CAST(mnth.asdb_elig_dt AS DATE) AS asdb_elig_dt
    FROM `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_ELIG_DATA_MBR_PER_MTH` AS mnth
    INNER JOIN (SELECT asdb_member_key, index_dt FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st`) AS st
        ON st.asdb_member_key = mnth.asdb_member_key
    WHERE CAST(mnth.asdb_elig_dt AS DATE) BETWEEN DATE_SUB(st.index_dt, INTERVAL 24 MONTH) AND DATE_ADD(st.index_dt, INTERVAL 6 MONTH)
),
tenure AS (
    SELECT
        asdb_member_key,
        index_dt,
        COUNTIF(asdb_elig_dt BETWEEN DATE_SUB(index_dt, INTERVAL 12 MONTH) AND DATE_SUB(index_dt, INTERVAL 1 MONTH)) AS tenure_yr1,
        COUNTIF(asdb_elig_dt BETWEEN DATE_SUB(index_dt, INTERVAL 24 MONTH) AND DATE_SUB(index_dt, INTERVAL 13 MONTH)) AS tenure_yr2,
        COUNTIF(asdb_elig_dt BETWEEN DATE_ADD(index_dt, INTERVAL 1 MONTH) AND DATE_ADD(index_dt, INTERVAL 6 MONTH)) AS post_mnths
    FROM elig_filtered
    GROUP BY asdb_member_key, index_dt
)
SELECT
    st.asdb_member_key
    , st.asdb_plan_key
    , st.index_dt
    , FLOOR(DATE_DIFF(DATE(st.index_dt), DATE(mb.dob), YEAR)) AS agenbr
    , mb.gender
    , mb.ethnicity_code
    , mb.primarylanguage_desc
    , COALESCE(t.tenure_yr1, 0) AS tenure_yr1
    , COALESCE(t.tenure_yr2, 0) AS tenure_yr2
    , COALESCE(t.post_mnths, 0) AS post_mnths
    , zcuu.urbsubr
    , zcuu.zip_weight_avg_medinc
FROM
    (SELECT DISTINCT asdb_member_key, asdb_plan_key, index_dt FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st`) AS st
LEFT JOIN
    `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_MEMBER` AS mb
        ON st.asdb_member_key = mb.asdb_member_key
LEFT JOIN tenure AS t
        ON st.asdb_member_key = t.asdb_member_key AND st.index_dt = t.index_dt
LEFT JOIN
    `edp-prod-hcbstorage.edp_hcb_tra_ckd_phm_srcv.ZIP_CENSUS_USPS_URBRUR` AS zcuu
        ON TRIM(mb.member_zip) = TRIM(zcuu.zip_cd);