"""
Field value normalizer: validates and normalizes extracted values by type.
"""
import re
from typing import Optional

def normalize_value(value: str, field_type: str, field_name: str) -> tuple[str, str, list]:
    """
    Normalize and validate an extracted field value.
    Returns (normalized_value, validation_status, warnings).
    """
    if not value:
        return "", "uncertain", ["Empty value"]

    warnings = []
    status = "valid"

    if field_type == "handwritten_sin":
        # SIN format: 9 digits, optionally formatted as XXX XXX XXX
        cleaned = re.sub(r'[\s\-]', '', value)
        if re.match(r'^\d{9}$', cleaned):
            formatted = f"{cleaned[:3]} {cleaned[3:6]} {cleaned[6:]}"
            return formatted, "valid", []
        else:
            warnings.append(f"SIN format unexpected: {value}")
            status = "uncertain"
            return value, status, warnings

    elif field_type == "handwritten_date":
        # Try to parse various date formats
        patterns = [
            (r'^\d{4}-\d{2}-\d{2}$', "YYYY-MM-DD"),
            (r'^\d{2}/\d{2}/\d{4}$', "MM/DD/YYYY"),
            (r'^\d{2}-\d{2}-\d{4}$', "MM-DD-YYYY"),
        ]
        for pat, fmt in patterns:
            if re.match(pat, value):
                return value, "valid", []
        warnings.append(f"Date format unexpected: {value}")
        status = "uncertain"
        return value, status, warnings

    elif field_type == "handwritten_phone":
        cleaned = re.sub(r'[\s\-\(\)]', '', value)
        if re.match(r'^\d{10}$', cleaned):
            formatted = f"({cleaned[:3]}) {cleaned[3:6]}-{cleaned[6:]}"
            return formatted, "valid", []
        warnings.append(f"Phone format unexpected: {value}")
        status = "uncertain"
        return value, status, warnings

    elif field_type == "handwritten_currency":
        # Extract numeric value
        numeric = re.sub(r'[^0-9.]', '', value)
        try:
            float(numeric)
            return numeric, "valid", []
        except:
            warnings.append(f"Currency format unexpected: {value}")
            status = "uncertain"
            return value, status, warnings

    # Default: pass through
    return value, status, warnings