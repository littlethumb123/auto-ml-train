# Pipeline Parameter Validation Pattern

## Problem

When defining KFP (Kubeflow Pipelines) pipelines, parameters are `PipelineParameterChannel` objects at compile time, not actual values. You cannot directly call string methods on them.

## Solution Pattern

Use this pattern to safely check if a pipeline parameter is valid (not None/Null/Empty):

```python
should_use_param = False

try:
    # Step 1: Get the actual value from PipelineParameterChannel
    if hasattr(param, 'value'):
        param_value = param.value  # Extract value from channel
    else:
        param_value = param  # Already a value (not a channel)
    
    # Step 2: Check if value is valid
    if param_value is not None:
        if isinstance(param_value, str):
            # Clean and validate string
            param_clean = param_value.strip().lower()
            # Check against all invalid string representations
            if param_clean and param_clean not in ("null", "none", "", "nan", "n/a"):
                should_use_param = True
        else:
            # Non-string, non-None value is valid
            should_use_param = True
            
except (AttributeError, TypeError):
    # If we can't access .value (truly a channel at compile time),
    # just check if the channel itself is not None
    if param is not None:
        should_use_param = True

# Step 3: Use the parameter if valid
if should_use_param:
    # Use param (not param_value - use the original parameter/channel)
    my_config["key"] = param
```

## Key Points

### 1. Why Use `.value`?

`PipelineParameterChannel` objects have a `.value` attribute that holds the default value:
- **At compile time**: `.value` gives you the default value to check
- **At runtime**: The parameter resolves to the actual passed value

### 2. Always Use Original Parameter, Not `.value`

```python
# ✅ CORRECT
if should_use_param:
    machine_type["acceleratorType"] = accelerator_type  # Use original parameter

# ❌ WRONG
if should_use_param:
    machine_type["acceleratorType"] = accel_value  # Don't use extracted value
```

**Why?** The original parameter (channel) will be resolved to the actual runtime value by KFP. The `.value` is just for validation.

### 3. Handle All Invalid String Representations

Check against multiple representations of "nothing":
```python
if param_clean and param_clean not in ("null", "none", "", "nan", "n/a"):
```

Common invalid values from YAML:
- `None` (Python None)
- `"None"` (string "None")
- `"null"` (string "null")
- `"Null"` (case variations)
- `""` (empty string)
- `"nan"` (not a number)
- `"n/a"` (not applicable)

### 4. Use Try-Except for Safety

The try-except handles edge cases:
- Parameter has no `.value` attribute
- `.value` access raises AttributeError
- Type checking fails
- Unexpected parameter types

## Complete Example: Accelerator Type Validation

```python
# Machine type configuration
machine_type = {"machineType": machine_type_param}

# Validate and add accelerator if provided
should_add_accelerator = False

try:
    # Extract value from channel
    if hasattr(accelerator_type, 'value'):
        accel_value = accelerator_type.value
    else:
        accel_value = accelerator_type
    
    # Check if valid
    if accel_value is not None:
        if isinstance(accel_value, str):
            accel_clean = accel_value.strip().lower()
            if accel_clean and accel_clean not in ("null", "none", "", "nan"):
                should_add_accelerator = True
        else:
            should_add_accelerator = True
            
except (AttributeError, TypeError):
    if accelerator_type is not None:
        should_add_accelerator = True

# Use original parameter (not accel_value)
if should_add_accelerator:
    machine_type["acceleratorType"] = accelerator_type  # ✅ Original parameter
    machine_type["acceleratorCount"] = accelerator_count
```

## When to Use This Pattern

Use this validation pattern when:

1. **Optional parameters** that might be None, empty, or "null" string
2. **GPU/accelerator configs** where None/empty means "no accelerator"
3. **Table names** where empty string means "use default"
4. **Any string parameter** that comes from YAML config (can be None/null/empty)

## When NOT to Use

Don't use this pattern for:

1. **Required parameters** - Let KFP validate they're provided
2. **Boolean flags** - Use the parameter directly
3. **Numeric parameters** - Use the parameter directly
4. **Inside component functions** - There you have actual values, not channels

## Testing

Test with different config.yaml values:

```yaml
# Test 1: Valid accelerator
accelerator_type: "NVIDIA_TESLA_T4"  # ✅ Should add

# Test 2: None
accelerator_type: None  # ❌ Should NOT add

# Test 3: Empty string
accelerator_type: ""  # ❌ Should NOT add

# Test 4: String "null"
accelerator_type: "null"  # ❌ Should NOT add

# Test 5: String "None"
accelerator_type: "None"  # ❌ Should NOT add
```

All invalid values should be filtered out, and the accelerator config should not be added to the machine spec.

## Summary

✅ **DO**: Use `.value` to check, but use original parameter in config
✅ **DO**: Check against multiple invalid string representations
✅ **DO**: Use try-except for safety
✅ **DO**: Wrap validation logic before using parameter

❌ **DON'T**: Call string methods directly on pipeline parameters
❌ **DON'T**: Use `.value` in the actual config (use original parameter)
❌ **DON'T**: Assume parameters are always strings at compile time
