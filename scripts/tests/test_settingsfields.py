import ast
from pathlib import Path

import pytest

from settingsfields import (
    Field,
    SettingsReadError,
    module_directory,
    read_module,
    read_settings,
)

SETTINGS = """
from typing import ClassVar
from pydantic_settings import BaseSettings, SettingsConfigDict

PREFIX = "CORTEX_DEMO_"
ALIAS = "CORTEX_OTHER_NAME"

class Demo(BaseSettings):
    model_config = SettingsConfigDict(env_prefix=PREFIX, env_nested_delimiter="__")

    plain: int = 1
    called: float = Field(default=2.0, gt=0)
    literal: str = Field(default="", validation_alias="CORTEX_LITERAL")
    constant: str = Field(default="", validation_alias=ALIAS)
    costs: dict[str, int] = {}
    listed: tuple[str, ...] = ()
    bare: int
    _private: int = 0
    shared: ClassVar[int] = 3
    other.attribute: int = 4
    unannotated = 5
"""


def fields(source: str) -> tuple[list[str], list[Field]]:
    """Read one module written as ``source``."""
    return read_module(ast.parse(source), "demo.py")


def test_each_field_reads_its_alias_or_its_prefixed_name() -> None:
    classes, read = fields(SETTINGS)
    assert classes == ["Demo"]
    assert [field.name for field in read] == [
        "CORTEX_DEMO_PLAIN",
        "CORTEX_DEMO_CALLED",
        "CORTEX_LITERAL",
        "CORTEX_OTHER_NAME",
        "CORTEX_DEMO_COSTS",
        "CORTEX_DEMO_LISTED",
        "CORTEX_DEMO_BARE",
    ]
    assert {field.owner for field in read} == {"Demo"}
    assert [field.name for field in read if field.delimiter == "__"] == ["CORTEX_DEMO_COSTS"]


def test_a_map_is_named_whole_or_by_one_entry_and_nothing_else_is() -> None:
    costs = Field("demo.py", "Demo", "CORTEX_DEMO_COSTS", "__")
    plain = Field("demo.py", "Demo", "CORTEX_DEMO_PLAIN", None)
    assert costs.named_by(frozenset({"CORTEX_DEMO_COSTS"}))
    assert costs.named_by(frozenset({"CORTEX_DEMO_COSTS__SPAWN"}))
    assert not costs.named_by(frozenset({"CORTEX_DEMO_COSTSX"}))
    assert plain.named_by(frozenset({"CORTEX_DEMO_PLAIN"}))
    assert not plain.named_by(frozenset({"CORTEX_DEMO_PLAIN__X"}))


def test_a_class_without_a_prefix_reads_bare_upper_case_names() -> None:
    _, read = fields(
        "class Bare(BaseSettings):\n"
        "    model_config: ClassVar[object] = SettingsConfigDict()\n"
        "    level: str = 'info'\n"
    )
    assert [(field.name, field.delimiter) for field in read] == [("LEVEL", None)]


@pytest.mark.parametrize(
    "source",
    [
        "class Model(BaseModel):\n    name: str = ''\n",
        "class Odd(pydantic.BaseSettings):\n    model_config = pydantic.SettingsConfigDict()\n"
        "    name: str = ''\n    x = y = SettingsConfigDict()\n",
        "class Declared:\n    model_config = {}\n    model_config: dict[str, str]\n",
        "def helper() -> None:\n    pass\n",
    ],
    ids=["plain-model", "qualified-call", "not-a-call", "no-class"],
)
def test_a_class_that_is_not_a_settings_class_is_stepped_over(source: str) -> None:
    assert fields(source) == ([], [])


@pytest.mark.parametrize(
    ("source", "detail"),
    [
        (
            "class Loose(BaseSettings):\n    name: str = ''\n",
            "demo.py: Loose subclasses BaseSettings with no SettingsConfigDict call",
        ),
        (
            "class Built(BaseSettings):\n"
            "    model_config = SettingsConfigDict(env_prefix='A_' + 'B_')\n",
            "demo.py: Built: env_prefix is not a string this reader can reduce",
        ),
        (
            "class Aliased(BaseSettings):\n"
            "    model_config = SettingsConfigDict(env_prefix='A_')\n"
            "    name: str = Field(default='', validation_alias=AliasChoices('A', 'B'))\n",
            "demo.py: Aliased.name: validation_alias is not a string this reader can reduce",
        ),
    ],
    ids=["no-config", "computed-prefix", "alias-choices"],
)
def test_a_shape_the_reader_was_not_taught_raises(source: str, detail: str) -> None:
    with pytest.raises(SettingsReadError) as raised:
        fields(source)
    assert str(raised.value) == detail


def test_a_module_directory_is_found_only_when_exactly_one_package_provides_it(
    tmp_path: Path,
) -> None:
    assert module_directory(tmp_path, "cortex_demo") is None
    (tmp_path / "brain/packages/demo/src/cortex_demo").mkdir(parents=True)
    assert module_directory(tmp_path, "cortex_demo") == (
        tmp_path / "brain/packages/demo/src/cortex_demo"
    )
    (tmp_path / "brain/packages/again/src/cortex_demo").mkdir(parents=True)
    assert module_directory(tmp_path, "cortex_demo") is None
    (tmp_path / "brain/packages/file/src").mkdir(parents=True)
    (tmp_path / "brain/packages/file/src/cortex_file").write_text("", encoding="utf-8")
    assert module_directory(tmp_path, "cortex_file") is None


def test_every_python_file_under_a_module_is_read_in_path_order(tmp_path: Path) -> None:
    directory = tmp_path / "pkg"
    (directory / "sub").mkdir(parents=True)
    (directory / "b.py").write_text(SETTINGS, encoding="utf-8")
    (directory / "sub" / "a.py").write_text(
        "class Other(BaseSettings):\n"
        "    model_config = SettingsConfigDict(env_prefix='X_')\n"
        "    one: int = 1\n",
        encoding="utf-8",
    )
    (directory / "notes.txt").write_text("class Nope(BaseSettings): pass\n", encoding="utf-8")
    read = read_settings(tmp_path, directory)
    assert read.classes == ("Demo", "Other")
    assert read.fields[-1] == Field("pkg/sub/a.py", "Other", "X_ONE", None)
    assert read.fields[0].file == "pkg/b.py"
