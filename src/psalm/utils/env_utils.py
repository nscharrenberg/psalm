import ast
import os
from typing import TypeVar, Optional, Callable

from dotenv import load_dotenv

load_dotenv()

T = TypeVar("T")
def get_env_by_name_or_default(env_name: str, default_value: T, parse: Optional[Callable[[str], T]] = None) -> T:
    found_value: Optional[str] = os.getenv(env_name, None)

    if found_value is None:
        return default_value

    if parse is not None:
        if parse == bool:
            return bool_check(found_value)

        return parse(found_value)

    # Fallback: try to coerce using the default's type but guard edge cases
    t = type(default_value)

    if default_value is None:
        # Can't infer target type from None; return the raw string or default
        return default_value

    if t is bool:
        return bool_check(found_value)  # type: ignore[return-value]

    try:
        return t(found_value)  # type: ignore[call-arg, return-value]
    except Exception:
        # If coercion fails, return default
        return default_value

def bool_check(s: str) -> bool:
    return s.strip().lower() in ("1", "true", "t", "yes", "y", "on")

def get_dict_env_by_name_or_default(env_name: str, default_value: Optional[dict]) -> dict:
    return get_env_by_name_or_default(env_name, default_value, ast.literal_eval)

def get_list_env_by_name_or_default(env_name: str, default_value: Optional[list]) -> list:
    return get_env_by_name_or_default(env_name, default_value, split_to_list)

def split_to_list(s: str) -> list:
    return s.split(",")

