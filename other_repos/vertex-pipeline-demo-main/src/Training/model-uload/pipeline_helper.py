import os
import re

def process_sql_file(sql_file_path, constants, base_path="../sql_queries/"):
    
    # Construct full path
    full_path = os.path.join(base_path, sql_file_path)
    
    # Read the SQL file content
    with open(full_path, 'r') as file:
        sql_content = file.read()
    
    # Find all variables in the SQL file
    variables_in_sql = re.findall(r'\{([^}]+)\}', sql_content)
    
    # Create a clean substitution dictionary from constants
    substitution_dict = {}
    
    for key, value in constants.items():
        # Skip nested dictionaries and non-string values that aren't useful for SQL
        if isinstance(value, dict):
            continue  # Skip LABELS and other nested objects
        elif isinstance(value, bool):
            substitution_dict[key] = str(value).upper()  # Convert True/False to TRUE/FALSE
        else:
            substitution_dict[key] = str(value)  # Convert everything to string
    
    # Add additional mappings for common SQL variable patterns
    additional_mappings = {
        'COST_CENTER': constants.get('COSTCENTER', ''),  # Map COSTCENTER to COST_CENTER
    }
    
    # Merge additional mappings
    substitution_dict.update(additional_mappings)
    
    # Check which variables can be substituted
    missing_variables = []
    available_substitutions = {}
    
    for var_name in variables_in_sql:
        if var_name in substitution_dict:
            available_substitutions[var_name] = substitution_dict[var_name]
        else:
            missing_variables.append(var_name)
    
    # Warn about missing variables but don't fail
    if missing_variables:
        print(f"Warning: Variables not found in constants: {missing_variables}")
        print(f"Available substitutions: {list(substitution_dict.keys())}")
        print(f"Variables in SQL: {variables_in_sql}")
    
    # Substitute variables using **kwargs
    try:
        sql_query = sql_content.format(**available_substitutions)
    except KeyError as e:
        print(f"Error: Missing variable {e} in SQL file {sql_file_path}")
        print(f"Available substitutions: {list(available_substitutions.keys())}")
        raise
    
    return sql_query