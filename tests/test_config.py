from seeed_jetson_develop.core import config


def test_save_replaces_existing_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text('{"language": "en"}', encoding="utf-8")
    monkeypatch.setattr(config, "_CONFIG_PATH", config_path)

    config.save({"language": "zh-CN"})

    assert config.load() == {"language": "zh-CN"}
    assert not config_path.with_suffix(".tmp").exists()
