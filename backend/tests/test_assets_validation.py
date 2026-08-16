from io import BytesIO

import pandas as pd
import pytest

from app.core.exceptions import BusinessRuleException
from app.main import app
from app.validation.assets.service import AssetsValidationService
from app.validation.assets.validators import asset_url_extension


def sample_assets(**overrides) -> pd.DataFrame:
    data = {
        "resourceForeignId": ["101", "102", "103", "104", "105"],
        "studioForeignId": ["Bangsar", "Bangsar", "KLCC", "Bangsar", "Bangsar"],
        "studioId": ["id-bangsar", "id-bangsar", "id-klcc", "id-bangsar", "id-bangsar"],
        "resourceType": ["MEMBER", "STAFF", "MEMBER", "GUEST", "MEMBER"],
        "assetURL": [
            "s3://bucket/101_appImage.jpeg",
            "s3://bucket/102_appImage.png",
            "s3://bucket/103_appImage.jpeg",
            "s3://bucket/104_appImage.jpeg",
            "s3://bucket/105_appImage.gif",
        ],
    }
    data.update(overrides)
    return pd.DataFrame(data)


def test_asset_url_extension_from_s3_path():
    assert asset_url_extension("s3://bucket/Photos/101_appImage.jpeg") == ".jpeg"
    assert asset_url_extension("https://cdn.example/a.PNG") == ".png"
    assert asset_url_extension("no-extension") is None


def test_missing_required_headers_blocks_file():
    service = AssetsValidationService()
    result = service.validate_dataframe(
        pd.DataFrame({"resourceForeignId": ["1"], "studioForeignId": ["A"]})
    )

    assert result.summary.valid == 0
    assert result.summary.validation_score == 0
    assert any(row.rule_id == "required_headers" for row in result.affected_rows)
    assert "studioId" in result.affected_rows[0].reason
    assert "resourceType" in result.affected_rows[0].reason
    assert "assetURL" in result.affected_rows[0].reason


def test_assets_does_not_auto_add_missing_headers():
    service = AssetsValidationService()
    service.validate_dataframe(
        pd.DataFrame({"resourceForeignId": ["1"], "studioForeignId": ["A"]})
    )
    with pytest.raises(BusinessRuleException, match="cannot be added automatically"):
        service.add_missing_mandatory_columns()


def test_assets_keeps_majority_studio_and_removes_other_full_rows():
    service = AssetsValidationService()
    # Only Bangsar-valid rows that also pass type/url/dup checks.
    result = service.validate_dataframe(
        sample_assets(
            resourceType=["MEMBER", "STAFF", "MEMBER", "MEMBER", "MEMBER"],
            assetURL=[
                "s3://bucket/101.jpeg",
                "s3://bucket/102.png",
                "s3://bucket/103.jpeg",
                "s3://bucket/104.jpeg",
                "s3://bucket/105.jpeg",
            ],
        )
    )

    kept_ids = service.pipeline.working_df["resourceForeignId"].tolist()
    assert "103" not in kept_ids  # KLCC minority studio removed
    assert result.summary.total_records == 5
    assert any(row.rule_id == "primary_studio" for row in result.affected_rows)


def test_assets_removes_invalid_resource_type_and_url_and_duplicates():
    service = AssetsValidationService()
    result = service.validate_dataframe(
        sample_assets(
            resourceForeignId=["101", "102", "103", "104", "101"],
            studioForeignId=["Bangsar"] * 5,
            studioId=["id-bangsar"] * 5,
            resourceType=["MEMBER", "STAFF", "MEMBER", "GUEST", "MEMBER"],
            assetURL=[
                "s3://bucket/101.jpeg",
                "s3://bucket/102.png",
                "s3://bucket/103.gif",
                "s3://bucket/104.jpeg",
                "s3://bucket/101b.jpeg",
            ],
        )
    )

    kept = service.pipeline.working_df["resourceForeignId"].tolist()
    assert kept == ["101", "102"]
    rule_ids = {row.rule_id for row in result.affected_rows}
    assert "resource_type" in rule_ids
    assert "asset_url" in rule_ids
    assert "duplicate_resource_foreign_id" in rule_ids


def test_assets_corrected_report_contains_only_kept_rows():
    service = AssetsValidationService()
    service.validate_dataframe(
        sample_assets(
            resourceForeignId=["101", "102"],
            studioForeignId=["Bangsar", "Bangsar"],
            studioId=["id-bangsar", "id-bangsar"],
            resourceType=["MEMBER", "STAFF"],
            assetURL=["s3://bucket/101.jpeg", "s3://bucket/102.bmp"],
        )
    )

    generated = service.create_report_generator().generate("corrected")
    content = generated.content.decode()
    assert generated.filename == "assets.csv"
    assert "101" in content and "102" in content
    assert "countryCode" not in content


def test_assets_removed_report_lists_dropped_rows_with_reasons():
    service = AssetsValidationService()
    result = service.validate_dataframe(
        sample_assets(
            resourceForeignId=["101", "102", "103"],
            studioForeignId=["Bangsar", "Bangsar", "Bangsar"],
            studioId=["id-bangsar", "id-bangsar", "id-bangsar"],
            resourceType=["MEMBER", "GUEST", "MEMBER"],
            assetURL=[
                "s3://bucket/101.jpeg",
                "s3://bucket/102.jpeg",
                "s3://bucket/103.gif",
            ],
        )
    )

    assert any(row.status == "Removed" for row in result.affected_rows)
    assert result.reports["removed"].url == "/api/assets/report/removed"

    generated = service.create_report_generator().generate("removed")
    content = generated.content.decode()
    removed = pd.read_csv(BytesIO(generated.content))
    assert generated.filename == "assets_validation_removed.csv"
    assert set(removed["Row Number"]) == {3, 4}
    assert "Removal Rule" in content
    assert "GUEST" in content
    assert "resource_type" in content or "Resource Type" in content
    assert ".gif" in content or "asset_url" in content or "Asset URL" in content


def test_assets_and_members_routes_are_both_registered():
    paths = set(app.openapi()["paths"])

    for domain in ("assets", "members"):
        assert {
            f"/api/{domain}/validate",
            f"/api/{domain}/validate/start",
            f"/api/{domain}/validate/{{validation_id}}/progress",
            f"/api/{domain}/rows",
            f"/api/{domain}/auto-fix",
            f"/api/{domain}/auto-fix/issue",
            f"/api/{domain}/edit",
            f"/api/{domain}/bulk-fill",
            f"/api/{domain}/file-review/add-missing-columns",
        } <= paths

    assert "/api/assets/report/{report_name}" in paths
