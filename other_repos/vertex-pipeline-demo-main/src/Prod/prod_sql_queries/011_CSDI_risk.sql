------------
--- SDoH ---
------------

CREATE OR REPLACE TABLE `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_csdi` 
OPTIONS (labels = [("owner", "{OWNER}"),("cost_center", "{COST_CENTER}")]
         , expiration_timestamp = TIMESTAMP_ADD(CURRENT_TIMESTAMP(), {DEFAULT_EXP}))
AS
WITH maxdt AS (
    SELECT 
        iodb_member_key
        , MAX(source_pstd_dts) AS source_pstd_dts
    FROM 
        `anbc-hcb-prod.insights_share_hcb_prod.v_enriched_address_medicaid`
    GROUP BY 
        iodb_member_key
)
, geo AS (
    SELECT 
        st.asdb_member_key
        , mb.iodb_member_key
        , id.ctfips
        , id.bgfips
    FROM
        (SELECT DISTINCT asdb_member_key FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st`) AS st
    LEFT JOIN 
        (SELECT
            asdb_member_key
            , iodb_member_key
         FROM `edp-prod-hcbstorage.edp_hcb_mdcd_core_srcv.ASDB_MEMBER`) AS mb
            ON st.asdb_member_key=mb.asdb_member_key
    LEFT JOIN 
        (SELECT
             block_code AS bgfips
             , CONCAT(fips_state_county_code, census_tract) AS ctfips
             , iodb_member_key
             , source_pstd_dts
             , geo_accuracy_code
        FROM 
            `anbc-hcb-prod.insights_share_hcb_prod.v_enriched_address_medicaid`
        WHERE 1 = 1
            AND TRIM(geo_accuracy_code) IN ("1", "2", "5", "6")
    ) AS id
            ON mb.iodb_member_key=id.iodb_member_key
    LEFT JOIN maxdt 
        ON id.iodb_member_key=maxdt.iodb_member_key
           AND id.source_pstd_dts=maxdt.source_pstd_dts
)
, csdi AS (
    SELECT
        st.asdb_member_key
        , COALESCE(MAX(c.citizenship_index), 0) AS citizenship_index
        , COALESCE(MAX(c.disability_score), 0) AS disability_score
        , COALESCE(MAX(c.education_index), 0) AS education_index
        , COALESCE(MAX(c.food_access), 0) AS food_access
        , COALESCE(MAX(c.health_access), 0) AS health_access              
        , COALESCE(MAX(c.health_habits), 0) AS health_habits
        , COALESCE(MAX(c.health_infra), 0) AS health_infra
        , COALESCE(MAX(c.housing_desert), 0) AS housing_desert
        , COALESCE(MAX(c.housing_ownership), 0) AS housing_ownership               
        , COALESCE(MAX(c.housing_quality), 0) AS housing_quality              
        , COALESCE(MAX(c.income_index), 0) AS income_index          
        , COALESCE(MAX(c.income_inequality), 0) AS income_inequality             
        , COALESCE(MAX(c.language_score), 0) AS language_score              
        , COALESCE(MAX(c.natural_disaster), 0) AS natural_disaster              
        , COALESCE(MAX(c.poverty_score), 0) AS poverty_score
        , COALESCE(MAX(c.proactive_health), 0) AS proactive_health
        , COALESCE(MAX(c.racial_diversity), 0) AS racial_diversity
        , COALESCE(MAX(c.social_isolation), 0) AS social_isolation              
        , COALESCE(MAX(c.technology_access), 0) AS technology_access
        , COALESCE(MAX(c.transport_access), 0) AS transport_access
        , COALESCE(MAX(c.unemployment_index), 0) AS unemployment_index
        , COALESCE(MAX(c.water_quality), 0) AS water_quality                       
        , COALESCE(MAX(c.social_risk_score), 0) AS social_risk_score 
    FROM 
        (SELECT DISTINCT asdb_member_key, bgfips FROM geo) AS st
    LEFT JOIN 
        (SELECT * FROM `edp-prod-storage.edp_ent_sdoheir_srcv.risk_index_block_group_historical_data` WHERE effective_year = CAST({SDOH_YR} AS INT)) AS c
            ON TRIM(st.bgfips)=TRIM(c.bgfips)
    GROUP BY 
        st.asdb_member_key
)
, acs AS ( 
    SELECT
        st.asdb_member_key
        , COALESCE(MAX(b.social_risk_score), 0) AS acs_social_risk_score
        , COALESCE(MAX(b.sdi_score), 0) AS sdi_score
        , COALESCE(MAX(b.svi_score), 0) AS svi_score
        , COALESCE(MAX(b.adi_score), 0) AS adi_score
    FROM (SELECT DISTINCT asdb_member_key FROM `{GCP_PROJECT}.{GCP_DB}.{PREFIX}_st`) AS st
    LEFT JOIN 
        geo AS id
            ON st.asdb_member_key = id.asdb_member_key
    LEFT JOIN 
        (SELECT
             *
         FROM `edp-prod-storage.edp_ent_sdoheir_srcv.srs_acs_block_group_allscores_historical_data` AS a
         WHERE effective_year = {SDOH_YR}) AS b
        ON id.ctfips = b.ctfips
    GROUP BY
        st.asdb_member_key
)
SELECT
    csdi.asdb_member_key
    , csdi.citizenship_index
    , csdi.disability_score
    , csdi.education_index
    , csdi.food_access
    , csdi.health_access
    , csdi.health_habits
    , csdi.health_infra
    , csdi.housing_desert
    , csdi.housing_ownership
    , csdi.housing_quality
    , csdi.income_index
    , csdi.income_inequality
    , csdi.language_score
    , csdi.natural_disaster
    , csdi.poverty_score
    , csdi.proactive_health
    , csdi.racial_diversity
    , csdi.social_isolation
    , csdi.technology_access
    , csdi.transport_access
    , csdi.unemployment_index
    , csdi.water_quality
    , csdi.social_risk_score
    , acs.acs_social_risk_score
    , acs.sdi_score
    , acs.svi_score
    , acs.adi_score
FROM
    csdi
LEFT JOIN
    acs
        ON csdi.asdb_member_key = acs.asdb_member_key
;
