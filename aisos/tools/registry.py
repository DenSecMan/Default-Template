"""Auto-discovery scanner for the tools/ directory."""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import pkgutil
from pathlib import Path

from aisos.tools.base import BaseTool

DEFAULT_TOOLS_PACKAGE = "tools"


class ToolRegistry:
    """Holds discovered BaseTool instances keyed by name."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered.")
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        try:
            return self._tools[name]
        except KeyError as e:
            raise KeyError(f"No tool registered with name '{name}'.") from e

    def all(self) -> list[BaseTool]:
        return list(self._tools.values())

    def names(self) -> list[str]:
        return sorted(self._tools)

    def discover(self, package: str = DEFAULT_TOOLS_PACKAGE) -> list[BaseTool]:
        """Import every module under `package` and instantiate each BaseTool subclass."""
        try:
            pkg = importlib.import_module(package)
        except ModuleNotFoundError:
            return []
        if not hasattr(pkg, "__path__"):
            return []
        found: list[BaseTool] = []
        for mod_info in pkgutil.iter_modules(pkg.__path__, prefix=f"{package}."):
            module = importlib.import_module(mod_info.name)
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if obj is BaseTool or not issubclass(obj, BaseTool):
                    continue
                if obj.__module__ != module.__name__:
                    continue
                if inspect.isabstract(obj):
                    continue
                instance = obj()
                if instance.name in self._tools:
                    continue
                self._tools[instance.name] = instance
                found.append(instance)
        return found

    def discover_path(self, path: Path) -> list[BaseTool]:
        """Discover tools under an arbitrary filesystem path (for tests)."""
        path = Path(path)
        if not path.is_dir():
            return []
        found: list[BaseTool] = []
        for py_file in sorted(path.glob("*.py")):
            if py_file.name == "__init__.py":
                continue
            spec = importlib.util.spec_from_file_location(
                f"_aisos_tool_{py_file.stem}", py_file
            )
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if obj is BaseTool or not issubclass(obj, BaseTool):
                    continue
                if obj.__module__ != module.__name__:
                    continue
                if inspect.isabstract(obj):
                    continue
                instance = obj()
                if instance.name in self._tools:
                    continue
                self._tools[instance.name] = instance
                found.append(instance)
        return found


__all__ = ["DEFAULT_TOOLS_PACKAGE", "ToolRegistry"]
