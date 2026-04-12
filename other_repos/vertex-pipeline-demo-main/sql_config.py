# Configuration for SQL Pipeline Variables
SQL_CONFIG = {
    # BigQuery Configuration
    "GCP_PROJECT": "anbc-hcb-dev",
    "GCP_DB": "cm_medicaid_hcb_dev",
    "PREFIX": "a534354_mat_v2",
    "OWNER": "palmere1_aetna_com",
    "COST_CENTER": "13070",
    "DEFAULT_EXP": "INTERVAL 180 DAY",
    "SDOH_YEAR": "2023",
    
    # Query execution order - these will be executed sequentially
    "EXECUTION_ORDER": [
        "002_Med_Claims_yr1",
        "002_Med_Claims_yr2",
        "003_Cost_and_Utilization_yr1",
        "003_Cost_and_Utilization_yr2",
        "004_Conditions",
        "006_Rx_Claims_yr1",
        "006_Rx_Claims_yr2",
        "007_Demographics",
        "008_GeoID",
        "009_ACS",
        "010_preventative",
        "011_CSDI_risk",
        "013_non_embedding_feature_beast"
    ]
}

# Derived variables
SQL_CONFIG["ST"] = f"{SQL_CONFIG['GCP_PROJECT']}.{SQL_CONFIG['GCP_DB']}.{SQL_CONFIG['PREFIX']}_st"
