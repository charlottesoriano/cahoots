from core.config import Settings


def test_allowed_origins_parses_comma_separated_environment_value(monkeypatch):
    monkeypatch.setenv(
        "ALLOWED_ORIGINS",
        " https://one.example.com,https://two.example.com, , https://three.example.com ",
    )

    configured = Settings(_env_file=None)

    assert configured.ALLOWED_ORIGINS == [
        "https://one.example.com",
        "https://two.example.com",
        "https://three.example.com",
    ]


def test_allowed_origins_accepts_a_list_without_modification():
    origins = ["https://one.example.com", "https://two.example.com"]

    configured = Settings(ALLOWED_ORIGINS=origins, _env_file=None)

    assert configured.ALLOWED_ORIGINS == origins


def test_allowed_origins_defaults_are_empty_and_not_shared(monkeypatch):
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    first = Settings(_env_file=None)
    second = Settings(_env_file=None)

    first.ALLOWED_ORIGINS.append("https://mutated.example.com")

    assert second.ALLOWED_ORIGINS == []
