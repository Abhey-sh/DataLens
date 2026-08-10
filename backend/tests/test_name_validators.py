import pandas as pd
import pytest

from app.core.exceptions import BusinessRuleException
from app.validation.members.validators import (
    FirstNameDefaultValidator,
    LastNameDefaultValidator,
)
from app.validation.members.service import MembersValidationService


def test_first_name_cleanup_suggestions_and_blank_classification():
    validator = FirstNameDefaultValidator()
    frame = pd.DataFrame(
        {
            "firstName": [
                "John",
                "j0hn",
                "J@hn123",
                "00932",
                None,
                "Élodie",
            ]
        }
    )

    issues = {issue.row_number: issue for issue in validator.validate(frame)}

    assert set(issues) == {2, 3, 4, 5}
    assert issues[2].suggested_value == "john"
    assert issues[2].issue_type == "validation"
    assert issues[3].suggested_value == "Jhn"
    assert issues[3].issue_type == "validation"
    assert issues[4].current_value == "00932"
    assert issues[4].suggested_value == "Change Me"
    assert issues[4].issue_type == "blank"
    assert issues[5].suggested_value == "Change Me"
    assert issues[5].issue_type == "blank"


def test_first_name_cleanup_applies_the_reported_values():
    validator = FirstNameDefaultValidator()
    frame = pd.DataFrame({"firstName": ["j0hn", "00932"]})

    validator.apply_fix(frame, 0)
    validator.apply_fix(frame, 1)

    assert frame["firstName"].tolist() == ["john", "Change Me"]


def test_last_name_cleanup_uses_last_name_default():
    validator = LastNameDefaultValidator()
    frame = pd.DataFrame({"lastName": ["Sm1th!", "1234"]})

    issues = validator.validate(frame)
    validator.apply_fix(frame, 0)
    validator.apply_fix(frame, 1)

    assert issues[0].suggested_value == "Smth"
    assert issues[0].issue_type == "validation"
    assert issues[1].suggested_value == "Me"
    assert issues[1].issue_type == "blank"
    assert frame["lastName"].tolist() == ["Smth", "Me"]


def test_bulk_fill_updates_physical_and_effective_name_blanks():
    service = MembersValidationService()
    service.validate_dataframe(
        pd.DataFrame(
            {
                "firstName": [None, "00932", "John"],
                "lastName": ["Doe", "Smith", "Jones"],
            }
        )
    )

    updated_rows, result = service.bulk_fill_blank_cells(
        "firstName", "Unknown"
    )

    assert updated_rows == 2
    assert service.pipeline.working_df["firstName"].tolist() == [
        "Unknown",
        "Unknown",
        "John",
    ]
    assert not any(
        issue.field_name == "firstName" for issue in result.affected_rows
    )
    audit_entries = [
        entry
        for entry in service.get_audit_log()
        if entry["rule_id"] == "bulk_fill_blank"
    ]
    assert [entry["old_value"] for entry in audit_entries] == [None, "00932"]
    assert all(entry["new_value"] == "Unknown" for entry in audit_entries)


def test_bulk_fill_rolls_back_an_invalid_name_replacement():
    service = MembersValidationService()
    service.validate_dataframe(
        pd.DataFrame(
            {
                "firstName": ["00932", "John"],
                "lastName": ["Doe", "Jones"],
            }
        )
    )

    with pytest.raises(BusinessRuleException, match="not valid"):
        service.bulk_fill_blank_cells("firstName", "1234")

    assert service.pipeline.working_df["firstName"].tolist() == [
        "00932",
        "John",
    ]
    assert not any(
        entry["rule_id"] == "bulk_fill_blank"
        for entry in service.get_audit_log()
    )
