import pandas as pd

from app.validation.members.validators import GenderValidator


def test_gender_validator_normalizes_known_values_and_defaults_unknown_values():
    validator = GenderValidator()
    frame = pd.DataFrame(
        {"gender": ["M", "Female", "male", "Alpha", "123", None]}
    )

    issues = {issue.row_number: issue for issue in validator.validate(frame)}

    assert set(issues) == {2, 3, 4, 5, 6}
    assert issues[2].suggested_value == "F"
    assert issues[3].suggested_value == "M"
    assert issues[4].suggested_value == "P"
    assert issues[5].suggested_value == "P"
    assert issues[6].suggested_value == "P"
    assert issues[6].issue_type == "blank"
    assert all(issue.auto_fix_available for issue in issues.values())


def test_gender_validator_applies_default_for_unknown_values():
    validator = GenderValidator()
    frame = pd.DataFrame({"gender": ["Female", "Alpha", "123", None]})

    for row_index in frame.index:
        validator.apply_fix(frame, row_index)

    assert frame["gender"].tolist() == ["F", "P", "P", "P"]
