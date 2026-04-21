-- Demographics Query
-- Creates demographics table with member information and tenure calculations
-- Variables: GCP_PROJECT, GCP_DB, PREFIX, OWNER, COST_CENTER, DEFAULT_EXP

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
    , CAST(mnth.asdb_elig_dt AS DATE) AS asdb_elig_dt
FROM
    (SELECT asdb_member_key, asdb_elig_dt FROM `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_ELIG_DATA_MBR_PER_MTH`) AS mnth
LEFT JOIN
    (SELECT asdb_member_key, rpt_end_dt FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st`) AS st
        ON st.asdb_member_key = mnth.asdb_member_key
WHERE CAST(mnth.asdb_elig_dt AS DATE) BETWEEN DATE_SUB(st.rpt_end_dt, INTERVAL 24 MONTH) AND DATE_ADD(st.rpt_end_dt, INTERVAL 6 MONTH);

-- Create demographics table
CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_demographics`
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
-- Single pass: filter elig once to [rpt_end_dt - 24 mo, rpt_end_dt - 1 mo], dedupe, then count months in yr1/yr2 windows.
-- yr1 = months in [rpt_end_dt - 12, rpt_end_dt - 1]; yr2 = [rpt_end_dt - 24, rpt_end_dt - 13]. Caps ensure tenure <= 12.
WITH elig_filtered AS (
    SELECT DISTINCT
        mnth.asdb_member_key,
        st.rpt_end_dt,
        CAST(mnth.asdb_elig_dt AS DATE) AS asdb_elig_dt
    FROM `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_ELIG_DATA_MBR_PER_MTH` AS mnth
    INNER JOIN (SELECT asdb_member_key, rpt_end_dt FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st`) AS st
        ON st.asdb_member_key = mnth.asdb_member_key
        AND st.rpt_end_dt > CAST(mnth.asdb_elig_dt AS DATE)
    WHERE CAST(mnth.asdb_elig_dt AS DATE) BETWEEN DATE_SUB(st.rpt_end_dt, INTERVAL 24 MONTH) AND DATE_SUB(st.rpt_end_dt, INTERVAL 1 MONTH)
),
tenure AS (
    SELECT
        asdb_member_key,
        rpt_end_dt,
        COUNTIF(asdb_elig_dt BETWEEN DATE_SUB(rpt_end_dt, INTERVAL 12 MONTH) AND DATE_SUB(rpt_end_dt, INTERVAL 1 MONTH)) AS tenure_yr1,
        COUNTIF(asdb_elig_dt BETWEEN DATE_SUB(rpt_end_dt, INTERVAL 24 MONTH) AND DATE_SUB(rpt_end_dt, INTERVAL 13 MONTH)) AS tenure_yr2
    FROM elig_filtered
    GROUP BY asdb_member_key, rpt_end_dt
)
SELECT
    st.asdb_member_key
    , FLOOR(DATE_DIFF(DATE(st.rpt_end_dt), DATE(mb.dob), YEAR)) AS agenbr
    , mb.gender
    , mb.ethnicity_code
    , mb.primarylanguage_desc
    , COALESCE(t.tenure_yr1, 0) AS tenure_yr1
    , COALESCE(t.tenure_yr2, 0) AS tenure_yr2
    , zcuu.urbsubr
    , zcuu.zip_weight_avg_medinc
FROM
    (SELECT DISTINCT asdb_member_key, rpt_end_dt FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st`) AS st
LEFT JOIN
    `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_MEMBER` AS mb
        ON st.asdb_member_key = mb.asdb_member_key
LEFT JOIN tenure AS t
        ON st.asdb_member_key = t.asdb_member_key AND st.rpt_end_dt = t.rpt_end_dt
LEFT JOIN
    `edp-prod-hcbstorage.edp_hcb_tra_ckd_phm_srcv.ZIP_CENSUS_USPS_URBRUR` AS zcuu
        ON TRIM(mb.member_zip) = TRIM(zcuu.zip_cd);