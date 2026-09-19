"""Read the environment names a brain package's settings classes read, without importing them."""

import ast
from pathlib import Path
from typing import NamedTuple

from moduleconstants import constants, parse, text
from treewalk import walk_files

PACKAGES = Path("brain/packages")
SOURCE = "src"

CONFIG_ATTRIBUTE = "model_config"
CONFIG_CALL = "SettingsConfigDict"
SETTINGS_BASE = "BaseSettings"
PREFIX_KEYWORD = "env_prefix"
DELIMITER_KEYWORD = "env_nested_delimiter"
ALIAS_KEYWORD = "validation_alias"
MAP_ANNOTATION = "dict"
UNREAD_ANNOTATION = "ClassVar"


class SettingsReadError(Exception):
    """A settings class has a form this reader cannot reduce to environment names."""


class Field(NamedTuple):
    """One settings field: the variable it reads, and the delimiter its entries take if a map."""

    file: str
    owner: str
    name: str
    delimiter: str | None

    def named_by(self, keys: frozenset[str]) -> bool:
        """Whether ``keys`` names this field whole, or names one entry of it when it is a map."""
        if self.name in keys:
            return True
        entry = None if self.delimiter is None else self.name + self.delimiter
        return entry is not None and any(key.startswith(entry) for key in keys)


class Settings(NamedTuple):
    """Every settings class one module package declares, and the fields they read."""

    classes: tuple[str, ...]
    fields: tuple[Field, ...]


def module_directory(root: Path, module: str) -> Path | None:
    """The source directory of the workspace package that provides ``module``, if one does."""
    packages = root / PACKAGES
    if not packages.is_dir():
        return None
    found = [path for package in packages.iterdir() if (path := package / SOURCE / module).is_dir()]
    return found[0] if len(found) == 1 else None


def _call_name(node: ast.expr) -> str | None:
    """The bare name a call expression calls, or None for anything else."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return node.func.id
    return None


def _keyword(call: ast.Call, name: str, strings: dict[str, str], where: str) -> str | None:
    """The string one keyword of ``call`` is given, None when absent, raising when unreadable."""
    for keyword in call.keywords:
        if keyword.arg != name:
            continue
        value = text(keyword.value, strings)
        if value is None:
            msg = f"{where}: {name} is not a string this reader can reduce"
            raise SettingsReadError(msg)
        return value
    return None


def _config(node: ast.ClassDef) -> ast.Call | None:
    """The `SettingsConfigDict(...)` call a class binds its `model_config` to, if it binds one."""
    for statement in node.body:
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target, value = statement.targets[0], statement.value
        elif isinstance(statement, ast.AnnAssign):
            target, value = statement.target, statement.value
        if (
            isinstance(target, ast.Name)
            and target.id == CONFIG_ATTRIBUTE
            and isinstance(value, ast.Call)
            and _call_name(value) == CONFIG_CALL
        ):
            return value
    return None


def _subclasses_settings(node: ast.ClassDef) -> bool:
    """Whether a class names `BaseSettings` among its bases."""
    return any(isinstance(base, ast.Name) and base.id == SETTINGS_BASE for base in node.bases)


def _outer(annotation: ast.expr) -> str | None:
    """The outermost name an annotation is written with: `dict` for `dict[str, int]`."""
    if isinstance(annotation, ast.Subscript):
        annotation = annotation.value
    return annotation.id if isinstance(annotation, ast.Name) else None


def _fields(
    node: ast.ClassDef, config: ast.Call, strings: dict[str, str], shown: str
) -> list[Field]:
    """Every field one settings class reads, in the order the class declares them."""
    where = f"{shown}: {node.name}"
    prefix = _keyword(config, PREFIX_KEYWORD, strings, where) or ""
    delimiter = _keyword(config, DELIMITER_KEYWORD, strings, where)
    read: list[Field] = []
    for statement in node.body:
        if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.target, ast.Name):
            continue
        name = statement.target.id
        outer = _outer(statement.annotation)
        if name == CONFIG_ATTRIBUTE or name.startswith("_") or outer == UNREAD_ANNOTATION:
            continue
        alias = None
        if isinstance(statement.value, ast.Call):
            alias = _keyword(statement.value, ALIAS_KEYWORD, strings, f"{where}.{name}")
        env = alias if alias is not None else prefix + name.upper()
        mapped = delimiter if outer == MAP_ANNOTATION else None
        read.append(Field(shown, node.name, env, mapped))
    return read


def read_module(tree: ast.Module, shown: str) -> tuple[list[str], list[Field]]:
    """The settings classes one parsed module declares at its top level, and their fields."""
    strings, _ = constants(tree)
    classes: list[str] = []
    fields: list[Field] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        config = _config(node)
        if config is None:
            if _subclasses_settings(node):
                msg = f"{shown}: {node.name} subclasses {SETTINGS_BASE} with no {CONFIG_CALL} call"
                raise SettingsReadError(msg)
            continue
        classes.append(node.name)
        fields.extend(_fields(node, config, strings, shown))
    return classes, fields


def read_settings(root: Path, directory: Path) -> Settings:
    """Every settings class under one module directory, read in path order."""
    classes: list[str] = []
    fields: list[Field] = []
    for path in sorted(walk_files(directory)):
        if path.suffix != ".py":
            continue
        shown = path.relative_to(root).as_posix()
        declared, read = read_module(parse(path, shown), shown)
        classes.extend(declared)
        fields.extend(read)
    return Settings(tuple(classes), tuple(fields))
