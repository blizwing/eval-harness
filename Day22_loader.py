"""
Day 22 — Dataset loader: YAML -> typed Pydantic objects.
Malformed file handled cleanly (readable error, not a stack trace).

Pattern follows day5_validate.py: return (status, payload) tuples instead
of raising, so callers (and later, the CLI's `run` subcommand) can branch
on status without a try/except at every call site.
"""

import yaml
from pydantic import BaseModel, Field, ValidationError, model_validator


class Requirement(BaseModel):
    id: str
    text: str = Field(min_length=1)


class RequirementSet(BaseModel):
    requirements: list[Requirement]

    @model_validator(mode="after")
    def check_unique_ids(self):
        ids = [r.id for r in self.requirements]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"Duplicate requirement id(s): {sorted(dupes)}")
        return self


def load_requirements(path: str) -> tuple[str, object]:
    """
    Returns (status, payload):
      ("not_found", str)          - file doesn't exist
      ("invalid_yaml", str)       - file exists but isn't valid YAML
      ("invalid_schema", list)    - valid YAML but doesn't match RequirementSet
      ("valid", RequirementSet)   - success
    """
    try:
        with open(path, "r") as f:
            raw_text = f.read()
    except FileNotFoundError:
        return ("not_found", f"No such file: {path}")

    try:
        parsed = yaml.safe_load(raw_text)
    except yaml.YAMLError as e:
        return ("invalid_yaml", str(e))

    try:
        result = RequirementSet.model_validate(parsed)
    except ValidationError as e:
        return ("invalid_schema", e.errors())

    return ("valid", result)


if __name__ == "__main__":
    test_paths = {
        "real_file": "Day8_Project_Requirements/fsm_requirements.yaml",
        "valid_fixture": "Day22_fixtures/valid.yaml",
        "missing_file": "does_not_exist.yaml",
        "broken_yaml": "Day22_fixtures/broken_yaml.yaml",
        "missing_key": "Day22_fixtures/missing_key.yaml",
        "missing_field": "Day22_fixtures/missing_field.yaml",
        "empty_text": "Day22_fixtures/empty_text.yaml",
        "duplicate_ids": "Day22_fixtures/duplicate_ids.yaml",
    }

    for name, path in test_paths.items():
        status, payload = load_requirements(path)
        print(f"{name} -> {status}")
        if status != "valid":
            print(f"  {payload}")
