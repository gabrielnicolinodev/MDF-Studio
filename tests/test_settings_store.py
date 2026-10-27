import json

from app import config
from app.storage.settings_store import SettingsStore


def test_missing_file_returns_defaults(tmp_path):
    store = SettingsStore(tmp_path / "nao_existe" / "settings.json")
    assert store.load() == config.default_settings()


def test_empty_file_returns_defaults(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("", encoding="utf-8")
    assert SettingsStore(p).load() == config.default_settings()


def test_invalid_json_returns_defaults(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("{ isto nao e json", encoding="utf-8")
    assert SettingsStore(p).load() == config.default_settings()


def test_json_with_wrong_type_returns_defaults(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    assert SettingsStore(p).load() == config.default_settings()


def test_save_and_load_roundtrip(tmp_path):
    store = SettingsStore(tmp_path / "sub" / "settings.json")
    data = config.default_settings()
    data["export_dir"] = str(tmp_path / "saida")
    data["startup_page"] = "generators"
    assert store.save(data) is True
    assert store.load() == data
    assert json.loads(store.path.read_text(encoding="utf-8"))["startup_page"] == "generators"


def test_save_creates_parent_directory(tmp_path):
    path = tmp_path / "a" / "b" / "settings.json"
    assert SettingsStore(path).save(config.default_settings())
    assert path.is_file()


def test_save_failure_returns_false(tmp_path):
    blocker = tmp_path / "arquivo"
    blocker.write_text("x")
    store = SettingsStore(blocker / "settings.json")  # pai e um arquivo
    assert store.save(config.default_settings()) is False


def test_partial_json_is_merged_with_defaults(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"startup_page": "projects"}), encoding="utf-8")
    s = SettingsStore(p).load()
    assert s["startup_page"] == "projects"
    assert s["unit"] == "mm"


def test_saved_values_are_valid(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.save({"unit": "invalido", "theme": "dark"})
    s = store.load()
    assert s["unit"] in config.VALID_UNITS
    assert s["theme"] in config.VALID_THEMES
