import pandas as pd

from app.validation.members.format_validators import EmailValidator


def test_email_validator_suggests_safe_dot_corrections():
    validator = EmailValidator()
    frame = pd.DataFrame(
        {
            "email": [
                "valid@example.com",
                "test.scott.@neonhive.co.nz",
                "john..doe@example..com",
            ]
        }
    )

    issues = {issue.row_number: issue for issue in validator.validate(frame)}

    assert set(issues) == {2, 3}
    assert issues[2].suggested_value == "test.scott@neonhive.co.nz"
    assert issues[3].suggested_value == "john.doe@example.com"
    assert all(issue.auto_fix_available for issue in issues.values())
    assert all(issue.severity.value == "error" for issue in issues.values())


def test_email_validator_keeps_ambiguous_errors_manual():
    validator = EmailValidator()
    issue = validator.validate(pd.DataFrame({"email": ["not-an-email"]}))[0]

    assert issue.suggested_value is None
    assert issue.auto_fix_available is False


def test_email_validator_applies_the_reported_suggestion():
    validator = EmailValidator()
    frame = pd.DataFrame({"email": ["test.scott.@neonhive.co.nz"]})

    validator.apply_fix(frame, 0)

    assert frame.at[0, "email"] == "test.scott@neonhive.co.nz"
