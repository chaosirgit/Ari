# -*- coding: utf-8 -*-
# pylint: skip-file
"""Get the signatures of functions and classes in the textual library."""
from typing import Literal, Callable
import inspect
import importlib
from pydantic import BaseModel

import textual

# Import key submodules to make them available
TEXTUAL_SUBMODULES = [
    "actions", "app", "binding", "box_model", "cache", "canvas", "case", "clock",
    "color", "command", "compose", "constants", "containers", "content", "coordinate",
    "css", "design", "dom", "driver", "drivers", "errors", "eta", "events",
    "expand_tabs", "features", "file_monitor", "filter", "fuzzy", "geometry",
    "getters", "highlight", "keys", "layout", "lazy", "logging", "map_geometry",
    "markup", "message", "message_pump", "messages", "notifications", "pad",
    "pilot", "reactive", "render", "rlock", "screen", "scroll_view", "scrollbar",
    "selection", "signal", "strip", "style", "suggester", "suggestions",
    "system_commands", "theme", "timer", "types", "validation", "visual", "walk",
    "widget", "widgets", "worker", "worker_manager"
]

for submodule in TEXTUAL_SUBMODULES:
    try:
        importlib.import_module(f"textual.{submodule}")
    except ImportError:
        pass


def get_class_signature(cls: type) -> str:
    """Get the signature of a class."""
    class_name = cls.__name__
    class_docstring = cls.__doc__ or ""

    class_str = f"class {class_name}:\n"
    if class_docstring:
        class_str += f'    """{class_docstring}"""\n'

    methods = []
    for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
        if method.__qualname__.split(".")[0] != class_name:
            continue

        if name.startswith("_") and name not in ["__init__", "__call__"]:
            continue

        try:
            sig = inspect.signature(method)
        except ValueError:
            sig = "(...)"

        method_str = f"    def {name}{sig}:\n"
        method_docstring = method.__doc__ or ""
        if method_docstring:
            method_str += f'        """{method_docstring}"""\n'

        methods.append(method_str)

    class_str += "\n".join(methods)
    return class_str


def get_function_signature(func: Callable) -> str:
    """Get the signature of a function."""
    try:
        sig = inspect.signature(func)
    except ValueError:
        sig = "(...)"
    method_str = f"def {func.__name__}{sig}:\n"

    method_docstring = func.__doc__ or ""
    if method_docstring:
        method_str += f'   """{method_docstring}"""\n'

    return method_str


class FuncOrCls(BaseModel):
    """The class records the module, signature, docstring, reference, and type"""
    module: str
    signature: str
    docstring: str
    reference: str
    type: Literal["function", "class"]

    def __init__(
        self,
        module: str,
        signature: str,
        docstring: str,
        reference: str,
        type: Literal["function", "class"],
    ) -> None:
        super().__init__(
            module=module,
            signature=signature.strip(),
            docstring=docstring.strip(),
            reference=reference,
            type=type,
        )


def _truncate_docstring(docstring: str, max_length: int = 200) -> str:
    if len(docstring) > max_length:
        return docstring[:max_length] + "..."
    return docstring


def get_textual_module_signatures() -> list[FuncOrCls]:
    signatures = []
    
    all_modules = list(textual.__all__) + TEXTUAL_SUBMODULES
    
    for module in all_modules:
        if not hasattr(textual, module):
            continue
            
        as_module = getattr(textual, module)
        path_module = ".".join(["textual", module])

        if inspect.isfunction(as_module):
            file = inspect.getfile(as_module)
            try:
                source_lines, start_line = inspect.getsourcelines(as_module)
                ref = f"{file}: {start_line}-{start_line + len(source_lines)}"
            except Exception:
                ref = f"{file}"
                
            signatures.append(
                FuncOrCls(
                    module=path_module,
                    signature=get_function_signature(as_module),
                    docstring=_truncate_docstring(as_module.__doc__ or ""),
                    reference=ref,
                    type="function",
                ),
            )

        else:
            members = []
            if inspect.ismodule(as_module):
                 members = getattr(as_module, "__all__", None)
                 if members is None:
                     members = [m for m in dir(as_module) if not m.startswith("_")]
            else:
                 if inspect.isclass(as_module):
                    file = inspect.getfile(as_module)
                    try:
                        source_lines, start_line = inspect.getsourcelines(as_module)
                        ref = f"{file}: {start_line}-{start_line + len(source_lines)}"
                    except Exception:
                        ref = f"{file}"
                        
                    signatures.append(
                        FuncOrCls(
                            module=path_module,
                            signature=get_class_signature(as_module),
                            docstring=_truncate_docstring(as_module.__doc__ or ""),
                            reference=ref,
                            type="class",
                        ),
                    )
                    continue
                 else:
                     continue

            for name in members:
                if not hasattr(as_module, name):
                    continue
                func_or_cls = getattr(as_module, name)
                path_func_or_cls = ".".join([path_module, name])

                if inspect.isclass(func_or_cls):
                    try:
                        file = inspect.getfile(func_or_cls)
                        source_lines, start_line = inspect.getsourcelines(func_or_cls)
                        ref = f"{file}: {start_line}-{start_line + len(source_lines)}"
                    except Exception:
                        ref = "Unknown"
                        
                    signatures.append(
                        FuncOrCls(
                            module=path_func_or_cls,
                            signature=get_class_signature(func_or_cls),
                            docstring=_truncate_docstring(func_or_cls.__doc__ or ""),
                            reference=ref,
                            type="class",
                        ),
                    )

                elif inspect.isfunction(func_or_cls):
                    try:
                        file = inspect.getfile(func_or_cls)
                        source_lines, start_line = inspect.getsourcelines(func_or_cls)
                        ref = f"{file}: {start_line}-{start_line + len(source_lines)}"
                    except Exception:
                        ref = "Unknown"

                    signatures.append(
                        FuncOrCls(
                            module=path_func_or_cls,
                            signature=get_function_signature(func_or_cls),
                            docstring=_truncate_docstring(func_or_cls.__doc__ or ""),
                            reference=ref,
                            type="function",
                        ),
                    )

    return signatures


def view_textual_library(
    module: str,
) -> str:
    """View Textual's Python library by given a module name."""
    if not module.startswith("textual"):
        return (
            f"Module '{module}' is invalid. The input module should be "
            f"'textual' or submodule of 'textual.xxx.xxx' "
            f"(separated by dots)."
        )

    if module == "textual":
        top_modules_description = [
            "The top-level modules in Textual library (partial list):",
        ]
        
        all_modules = list(textual.__all__) + TEXTUAL_SUBMODULES
        all_modules = sorted(list(set(all_modules)))
        
        for name in all_modules:
            if hasattr(textual, name):
                obj = getattr(textual, name)
                doc = _truncate_docstring(obj.__doc__ or "", 100).strip().replace('\n', ' ')
                top_modules_description.append(f"- textual.{name}: {doc}")
        
        top_modules_description.append(
                "You can further view the classes/function within above "
                "modules by calling this function with the above module name.",
        )
        return "\n".join(top_modules_description)

    modules = get_textual_module_signatures()
    for as_module in modules:
        if as_module.module == module:
            return f"- The signature of '{module}':\n```python\n{as_module.signature}\n```\n\n- Source code reference: {as_module.reference}"

    collected_modules = []
    for as_module in modules:
        if as_module.module.startswith(module):
            collected_modules.append(as_module)

    if len(collected_modules) > 0:
        collected_modules_content = (
            [
                f"The classes/functions and their truncated docstring in "
                f"'{module}' module:",
            ]
            + [f"- {_.module}: {repr(_.docstring)}" for _ in collected_modules]
            + [
                "The docstring is truncated for limited context. For detailed "
                "signature and methods, call this function with the above "
                "module name",
            ]
        )

        return "\n".join(collected_modules_content)

    return (
        f"Module '{module}' not found. Use 'textual' to view the "
        f"top-level modules to ensure the given module is valid."
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--module",
        type=str,
        default="textual",
        help="The module name to view, e.g. 'textual'",
    )
    args = parser.parse_args()

    res = view_textual_library(module=args.module)
    print(res)
