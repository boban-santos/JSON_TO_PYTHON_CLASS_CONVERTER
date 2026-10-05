"""Tests for name sanitization, keyword collisions, and class naming."""

from json2py.core.namer import (
    sanitize_field_name,
    singularize,
    suggest_class_name,
    to_pascal_case,
    to_snake_case,
)


def test_snake_case_conversion():
    assert to_snake_case("firstName") == "first_name"
    assert to_snake_case("first-name") == "first_name"
    assert to_snake_case("First_Name") == "first_name"
    assert to_snake_case("User ID") == "user_id"
    assert to_snake_case("XMLHttpRequest") == "xml_http_request"


def test_sanitize_keywords():
    clean, alias = sanitize_field_name("class")
    assert clean == "class_"
    assert alias == "class"

    clean, alias = sanitize_field_name("from")
    assert clean == "from_"
    assert alias == "from"

    clean, alias = sanitize_field_name("dict")
    assert clean == "dict_"
    assert alias == "dict"


def test_sanitize_leading_digits():
    clean, alias = sanitize_field_name("2fa")
    assert clean == "val_2fa"
    assert alias == "2fa"

    clean, alias = sanitize_field_name("100_percent")
    assert clean == "val_100_percent"


def test_singularization():
    assert singularize("users") == "user"
    assert singularize("addresses") == "address"
    assert singularize("categories") == "category"
    assert singularize("data") == "data"


def test_pascal_case_and_class_name():
    assert to_pascal_case("user_profile") == "UserProfile"
    assert to_pascal_case("billing-info") == "BillingInfo"
    assert suggest_class_name("users", is_list_item=True) == "User"
    assert suggest_class_name("items", is_list_item=True, parent_class="Order") == "OrderItem"
