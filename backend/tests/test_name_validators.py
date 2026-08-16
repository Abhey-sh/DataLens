import pandas as pd
import pytest

from app.core.exceptions import BusinessRuleException
from app.validation.members.validators import (
    CombinedNameValidator,
    FirstNameDefaultValidator,
    LastNameDefaultValidator,
)
from app.validation.members.service import MembersValidationService


def test_name_validation_allows_unicode_digits_marks_and_approved_punctuation():
    values = [
        "John",
        "j0hn",
        "00932",
        "Élodie",
        "Иван",
        "山田",
        "अनिल",
        "Jose\u0301",
        "O’Neil-(Jr.):#1,",
    ]
    frame = pd.DataFrame(
        {"firstName": values, "lastName": ["Valid"] * len(values)}
    )

    assert FirstNameDefaultValidator().validate(frame) == []


@pytest.mark.parametrize(
    "value",
    [
        "J@hn",
        "A_B",
        "A/B",
        "A&B",
        "A!",
        "A?",
        "A*",
        "A+",
        "A=B",
        'A"B',
        "😀",
    ],
)
def test_name_validation_rejects_unapproved_characters(value):
    frame = pd.DataFrame({"firstName": [value], "lastName": ["Valid"]})

    issue = FirstNameDefaultValidator().validate(frame)[0]

    assert issue.suggested_value is None
    assert issue.auto_fix_available is False
    assert issue.issue_type == "validation"


def test_name_validation_enforces_individual_length_limits():
    first_frame = pd.DataFrame(
        {
            "firstName": ["A" * 30, "A" * 31],
            "lastName": ["Valid", "Valid"],
        }
    )
    last_frame = pd.DataFrame(
        {
            "firstName": ["Valid", "Valid"],
            "lastName": ["A" * 60, "A" * 61],
        }
    )

    first_issues = FirstNameDefaultValidator().validate(first_frame)
    last_issues = LastNameDefaultValidator().validate(last_frame)

    assert [issue.row_number for issue in first_issues] == [2]
    assert [issue.row_number for issue in last_issues] == [2]


def test_name_validation_rejects_individual_and_combined_url_shapes():
    individual = pd.DataFrame(
        {"firstName": ["Acme.com"], "lastName": ["Valid"]}
    )
    combined = pd.DataFrame({"firstName": ["Acme."], "lastName": ["com"]})

    assert FirstNameDefaultValidator().validate(individual)
    assert FirstNameDefaultValidator().validate(combined) == []
    assert LastNameDefaultValidator().validate(combined) == []
    combined_issues = CombinedNameValidator().validate(combined)
    assert len(combined_issues) == 1
    assert combined_issues[0].field_name == "combinedName"


def test_name_validation_does_not_treat_s_dot_lucy_as_a_url():
    frame = pd.DataFrame({"firstName": ["Lucy"], "lastName": ["S."]})

    assert FirstNameDefaultValidator().validate(frame) == []
    assert LastNameDefaultValidator().validate(frame) == []
    assert CombinedNameValidator().validate(frame) == []


def test_members_service_returns_one_combined_name_issue():
    service = MembersValidationService()

    result = service.validate_dataframe(
        pd.DataFrame({"firstName": ["Acme."], "lastName": ["com"]})
    )

    name_issues = [
        issue
        for issue in result.affected_rows
        if issue.rule_id
        in {
            "first_name_default",
            "last_name_default",
            "combined_name_validation",
        }
    ]
    assert len(name_issues) == 1
    assert name_issues[0].rule_id == "combined_name_validation"
    assert name_issues[0].row_data["firstName"] == "Acme."
    assert name_issues[0].row_data["lastName"] == "com"


def test_members_service_strips_controls_and_trims_names_before_validation():
    service = MembersValidationService()

    result = service.validate_dataframe(
        pd.DataFrame(
            {
                "firstName": [" \u202eJose\u0301\u0000 "],
                "lastName": [" Doe  Smith "],
            }
        )
    )

    assert service.pipeline.working_df.at[0, "firstName"] == "José"
    assert service.pipeline.working_df.at[0, "lastName"] == "Doe  Smith"
    assert not any(
        issue.field_name in {"firstName", "lastName"}
        for issue in result.affected_rows
    )


def test_name_auto_fix_only_applies_configured_blank_defaults():
    service = MembersValidationService()
    service.validate_dataframe(
        pd.DataFrame(
            {
                "firstName": [None, "J@hn"],
                "lastName": ["Doe", "Smith"],
            }
        )
    )

    result = service.apply_auto_fix("first_name_default", "blank")

    assert service.pipeline.working_df["firstName"].tolist() == [
        "Change Me",
        "J@hn",
    ]
    invalid_issue = next(
        issue
        for issue in result.affected_rows
        if issue.field_name == "firstName"
    )
    assert invalid_issue.row_number == 2
    assert invalid_issue.auto_fix_available is False


def test_bulk_fill_updates_only_physical_name_blanks():
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

    assert updated_rows == 1
    assert service.pipeline.working_df["firstName"].tolist() == [
        "Unknown",
        "00932",
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
    assert [entry["old_value"] for entry in audit_entries] == [None]
    assert all(entry["new_value"] == "Unknown" for entry in audit_entries)


def test_bulk_fill_rolls_back_an_invalid_name_replacement():
    service = MembersValidationService()
    service.validate_dataframe(
        pd.DataFrame(
            {
                "firstName": [None, "John"],
                "lastName": ["Doe", "Jones"],
            }
        )
    )

    with pytest.raises(BusinessRuleException, match="not valid"):
        service.bulk_fill_blank_cells("firstName", "Bad@Name")

    assert pd.isna(service.pipeline.working_df.at[0, "firstName"])
    assert service.pipeline.working_df.at[1, "firstName"] == "John"
    assert not any(
        entry["rule_id"] == "bulk_fill_blank"
        for entry in service.get_audit_log()
    )
