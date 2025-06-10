from typing import Any


def dynamodb_attribute_to_python_type(attribute_value)->Any:
    """
    Converts a DynamoDB AttributeValue to its appropriate Python type.

    Args:
        attribute_value (dict): A DynamoDB AttributeValue dictionary.
                                Example: {'S': 'string'}, {'N': '123.45'}, {'BOOL': True}

    Returns:
        The Python equivalent of the DynamoDB attribute value.
        Returns None if the attribute_value is None or not a dictionary.
    """
    if not isinstance(attribute_value, dict):
        return None

    if 'S' in attribute_value:
        return str(attribute_value['S'])
    elif 'N' in attribute_value:
        # Numbers can be int or float
        num_str = attribute_value['N']
        if '.' in num_str:
            return float(num_str)
        else:
            return int(num_str)
    elif 'B' in attribute_value:
        return attribute_value['B']  # boto3 already returns bytes
    elif 'BOOL' in attribute_value:
        return bool(attribute_value['BOOL'])
    elif 'NULL' in attribute_value and attribute_value['NULL']:
        return None
    elif 'M' in attribute_value:
        return {k: dynamodb_attribute_to_python_type(v) for k, v in attribute_value['M'].items()}
    elif 'L' in attribute_value:
        return [dynamodb_attribute_to_python_type(item) for item in attribute_value['L']]
    elif 'SS' in attribute_value:
        return set(attribute_value['SS'])
    elif 'NS' in attribute_value:
        # Convert number strings in the set to int or float
        return set(float(n_str) if '.' in n_str else int(n_str) for n_str in attribute_value['NS'])
    elif 'BS' in attribute_value:
        return set(attribute_value['BS']) # boto3 already returns set of bytes
    else:
        # Should not happen for valid DynamoDB AttributeValue
        return None