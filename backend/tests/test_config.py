import pytest
from pydantic import ValidationError

from core.config import Settings


@pytest.mark.parametrize(
    ("raw_origins", "expected"),
    [
        ("", []),
        ("https://app.example.com", ["https://app.example.com"]),
        (
            " https://app.example.com,https://admin.example.com, ,",
            ["https://app.example.com", "https://admin.example.com"],
        ),
        (
            ["https://app.example.com", "https://admin.example.com"],
            ["https://app.example.com", "https://admin.example.com"],
        ),
    ],
)
def test_allowed_origins_accepts_environment_and_list_formats(raw_origins, expected):
    settings = Settings(_env_file=None, ALLOWED_ORIGINS=raw_origins)

    assert settings.ALLOWED_ORIGINS == expected


def test_allowed_origins_reads_comma_separated_environment_value(monkeypatch):
    monkeypatch.setenv(
        "ALLOWED_ORIGINS",
        "https://first.example.com, https://second.example.com",
    )

    settings = Settings(_env_file=None)

    assert settings.ALLOWED_ORIGINS == [
        "https://first.example.com",
        "https://second.example.com",
    ]


def test_allowed_origins_default_is_not_shared_between_settings_instances(monkeypatch):
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    first = Settings(_env_file=None)
    second = Settings(_env_file=None)

    first.ALLOWED_ORIGINS.append("https://first.example.com")

    assert second.ALLOWED_ORIGINS == []


def test_allowed_origins_rejects_non_string_list_members():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ALLOWED_ORIGINS=["https://valid.example.com", 1])
