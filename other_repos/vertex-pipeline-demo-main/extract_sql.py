#!/usr/bin/env python3
"""
SQL Extractor - Extracts SQL queries from bash scripts and converts them to pure SQL files
"""

import os
import re
import glob
from typing import Dict, List, Tuple

class SQLExtractor:
    """Extracts SQL queries from bash scripts and creates pure SQL files."""
    
    def __init__(self, 
                 bash_scripts_dir: str = "src/sql",
                 output_dir: str = "sql_queries"):
        self.bash_scripts_dir = bash_scripts_dir
        self.output_dir = output_dir
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
    
    def extract_sql_from_bash(self, bash_file_path: str) -> List[Tuple[str, str]]:
        """Extract SQL queries from a bash script file."""
        
        with open(bash_file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Find all SQL queries between single quotes in bq query commands
        sql_queries = []
        
        # Pattern to match SQL queries in bq query commands
        # This matches: bq query ... ' ... SQL ... '
        pattern = r"bq query[^']*'([^']*(?:'[^']*'[^']*)*?)'"
        
        matches = re.findall(pattern, content, re.DOTALL | re.MULTILINE)
        
        for i, match in enumerate(matches):
            # Clean up the SQL
            sql = match.strip()
            
            # Skip simple DROP TABLE statements
            if sql.strip().upper().startswith('DROP TABLE') and len(sql.split('\n')) <= 1:
                continue
                
            # Add table drop if this is a CREATE statement
            if 'CREATE OR REPLACE TABLE' in sql.upper():
                # Extract table name from CREATE statement
                table_match = re.search(r'CREATE OR REPLACE TABLE\s+`([^`]+)`', sql, re.IGNORECASE)
                if table_match:
                    table_name = table_match.group(1)
                    drop_statement = f"DROP TABLE IF EXISTS `{table_name}`;\n\n"
                    sql = drop_statement + sql
            
            # Add semicolon if not present
            if not sql.strip().endswith(';'):
                sql += ';'
                
            sql_queries.append((f"query_{i+1}", sql))
        
        return sql_queries
    
    def process_all_bash_scripts(self) -> Dict[str, str]:
        """Process all bash scripts in the directory."""
        
        bash_files = glob.glob(os.path.join(self.bash_scripts_dir, "*.sh"))
        bash_files.sort()  # Process in order
        
        extracted_queries = {}
        
        for bash_file in bash_files:
            filename = os.path.basename(bash_file)
            script_name = filename.replace('.sh', '')
            
            # Skip the main run script
            if script_name.startswith('000_run'):
                continue
                
            print(f"Processing {filename}...")
            
            try:
                sql_queries = self.extract_sql_from_bash(bash_file)
                
                if sql_queries:
                    # Combine all queries for this script
                    combined_sql = f"-- {filename} - Extracted SQL Queries\n"
                    combined_sql += f"-- Original script: {bash_file}\n\n"
                    
                    for query_name, sql in sql_queries:
                        combined_sql += f"-- {query_name}\n"
                        combined_sql += sql + "\n\n"
                    
                    # Convert variable references to placeholder format
                    combined_sql = self.convert_variables(combined_sql)
                    
                    # Save to SQL file
                    output_file = os.path.join(self.output_dir, f"{script_name}.sql")
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(combined_sql)
                    
                    extracted_queries[script_name] = output_file
                    print(f"  -> Created {output_file}")
                else:
                    print(f"  -> No SQL queries found in {filename}")
                    
            except Exception as e:
                print(f"  -> Error processing {filename}: {e}")
        
        return extracted_queries
    
    def convert_variables(self, sql: str) -> str:
        """Convert bash variable references to Python string format placeholders."""
        
        # Map of bash variables to Python format strings
        variable_mapping = {
            r'\$GCP_PROJECT': '{GCP_PROJECT}',
            r'\$GCP_DB': '{GCP_DB}',
            r'\$PREFIX': '{PREFIX}',
            r'\$OWNER': '{OWNER}',
            r'\$COST_CENTER': '{COST_CENTER}',
            r'\$DEFAULT_EXP': '{DEFAULT_EXP}',
            r'\$ST': '{ST}',
            r'\$SDOH_YEAR': '{SDOH_YEAR}',
            r"'\$GCP_PROJECT'": "'{GCP_PROJECT}'",
            r"'\$GCP_DB'": "'{GCP_DB}'",
            r"'\$PREFIX'": "'{PREFIX}'",
            r"'\$OWNER'": "'{OWNER}'",
            r"'\$COST_CENTER'": "'{COST_CENTER}'",
            r"'\$DEFAULT_EXP'": "'{DEFAULT_EXP}'",
            r"'\$ST'": "'{ST}'",
            r"'\$SDOH_YEAR'": "'{SDOH_YEAR}'"
        }
        
        # Apply replacements
        for bash_var, python_var in variable_mapping.items():
            sql = re.sub(bash_var, python_var, sql)
        
        return sql
    
    def create_query_manifest(self, extracted_queries: Dict[str, str]) -> str:
        """Create a manifest file listing all extracted queries in execution order."""
        
        # Define execution order based on the original script
        execution_order = [
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
        
        manifest = {
            "name": "Sequential SQL Pipeline",
            "description": "Extracted SQL queries from bash scripts for sequential execution",
            "queries": []
        }
        
        for script_name in execution_order:
            if script_name in extracted_queries:
                manifest["queries"].append({
                    "name": script_name,
                    "file": extracted_queries[script_name],
                    "description": f"SQL queries from {script_name}.sh"
                })
        
        # Save manifest
        manifest_file = os.path.join(self.output_dir, "query_manifest.json")
        import json
        with open(manifest_file, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)
        
        print(f"Created query manifest: {manifest_file}")
        return manifest_file


def main():
    """Main function to extract SQL queries."""
    
    print("SQL Extractor - Converting bash scripts to SQL files")
    print("=" * 60)
    
    # Get the absolute path to the workspace
    workspace_root = "/home/sahil_gadge_aetna_com/Repo2/vertex-pipeline-demo"
    bash_scripts_dir = os.path.join(workspace_root, "src", "sql")
    output_dir = os.path.join(workspace_root, "sql_queries")
    
    # Create extractor
    extractor = SQLExtractor(bash_scripts_dir, output_dir)
    
    # Process all bash scripts
    extracted_queries = extractor.process_all_bash_scripts()
    
    # Create manifest
    extractor.create_query_manifest(extracted_queries)
    
    print("\n" + "=" * 60)
    print(f"SQL extraction completed!")
    print(f"Extracted {len(extracted_queries)} SQL files:")
    for script_name, file_path in extracted_queries.items():
        print(f"  - {script_name}: {file_path}")
    
    print(f"\nNext steps:")
    print(f"1. Review the extracted SQL files in: {output_dir}")
    print(f"2. Update sql_config.py with your specific configuration values")
    print(f"3. Run the pipeline using: python sql_pipeline_runner.py")


if __name__ == "__main__":
    main()
