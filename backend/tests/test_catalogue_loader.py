import pytest
from app.ingestion.catalogue_loader import catalogue_loader
from app.ingestion.data_validator import DataValidator
from app.core.config import settings

def test_json_catalogue_ingestion():
    fixture_json = settings.get_dev_fixtures_path() / "sample_catalogue.json"
    status = catalogue_loader.load_file(fixture_json, is_official=False, is_synthetic=True)
    assert status["is_ready"] is True
    assert status["records_loaded"] >= 5
    assert catalogue_loader.get_product("TC-DEV-101") is not None
    assert catalogue_loader.get_product("TC-DEV-101")["price"] == 1499.0

def test_csv_catalogue_ingestion():
    fixture_csv = settings.get_dev_fixtures_path() / "sample_catalogue.csv"
    status = catalogue_loader.load_file(fixture_csv, is_official=False, is_synthetic=True)
    assert status["is_ready"] is True
    assert status["records_loaded"] >= 5
    assert catalogue_loader.get_product("TC-DEV-105") is not None

def test_invalid_records_handling():
    test_records = [
        {"product_id": "", "title": "No ID Item", "price": 100}, # Missing ID
        {"product_id": "TC-INV-1", "title": "", "price": 100}, # Missing title
        {"product_id": "TC-INV-2", "title": "Bad Price", "price": "invalid_price"}, # Bad price
        {"product_id": "TC-VALID", "title": "Good Item", "price": 299.0} # Valid item
    ]
    status = catalogue_loader.load_from_records(
        records=test_records,
        is_official=False,
        is_synthetic=True,
        source_name="unit_test"
    )
    assert status["records_loaded"] == 1
    assert status["records_rejected"] == 3
    assert catalogue_loader.get_product("TC-VALID") is not None

def test_duplicate_records_protection():
    test_records = [
        {"product_id": "TC-DUP-1", "title": "Original Item", "price": 100},
        {"product_id": "TC-DUP-1", "title": "Duplicate Item", "price": 200}
    ]
    status = catalogue_loader.load_from_records(
        records=test_records,
        is_official=False,
        is_synthetic=True,
        source_name="unit_test"
    )
    assert status["records_loaded"] == 1
    assert status["duplicate_records"] == 1
    # Preserves first valid record
    assert catalogue_loader.get_product("TC-DUP-1")["title"] == "Original Item"
