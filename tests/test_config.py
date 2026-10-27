from app import config


def test_default_settings_values():
    s = config.default_settings()
    assert s["unit"] == "mm"
    assert s["theme"] == "dark"
    assert s["startup_page"] == "home"
    assert isinstance(s["export_dir"], str) and s["export_dir"]


def test_default_settings_returns_independent_copies():
    a = config.default_settings()
    a["unit"] = "x"
    assert config.default_settings()["unit"] == "mm"


def test_default_values_are_valid():
    s = config.default_settings()
    assert s["unit"] in config.VALID_UNITS
    assert s["theme"] in config.VALID_THEMES
    assert s["startup_page"] in config.STARTUP_PAGES


def test_sanitize_discards_invalid_values():
    s = config.sanitize_settings({"unit": "furlong", "theme": "neon",
                                  "export_dir": 42, "startup_page": "nope"})
    assert s == config.default_settings()


def test_sanitize_non_dict_returns_defaults():
    for bad in (None, [], "texto", 3):
        assert config.sanitize_settings(bad) == config.default_settings()


def test_sanitize_keeps_valid_values():
    s = config.sanitize_settings({"export_dir": "  /tmp/saida ", "startup_page": "last"})
    assert s["export_dir"] == "/tmp/saida"
    assert s["startup_page"] == "last"


