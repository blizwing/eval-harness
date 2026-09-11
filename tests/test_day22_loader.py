import Day22_loader as loader

FIXTURES = "Day22_fixtures"


def test_valid_requirements_file():
    status, payload = loader.load_requirements(f"{FIXTURES}/valid.yaml")
    assert status == "valid"
    assert len(payload.requirements) > 0


def test_missing_file():
    status, _ = loader.load_requirements(f"{FIXTURES}/does_not_exist.yaml")
    assert status == "not_found"


def test_broken_yaml():
    status, _ = loader.load_requirements(f"{FIXTURES}/broken_yaml.yaml")
    assert status == "invalid_yaml"


def test_missing_key():
    status, _ = loader.load_requirements(f"{FIXTURES}/missing_key.yaml")
    assert status == "invalid_schema"


def test_missing_field():
    status, _ = loader.load_requirements(f"{FIXTURES}/missing_field.yaml")
    assert status == "invalid_schema"


def test_empty_text():
    status, _ = loader.load_requirements(f"{FIXTURES}/empty_text.yaml")
    assert status == "invalid_schema"


def test_duplicate_ids():
    status, errors = loader.load_requirements(f"{FIXTURES}/duplicate_ids.yaml")
    assert status == "invalid_schema"
    assert any("Duplicate requirement id" in str(err) for err in errors)
