#!/usr/bin/env python3
"""Snapshot of the names that must not change (help desk #19).

Walks both bots with `ast` (nothing is imported or run) and records, in
`tests/protected-names.json`:
  - slash command names (with their group) and option names, after any
    `@app_commands.rename`, plus each command's description, each option's
    `@app_commands.describe` text, every `app_commands.Choice` name and value
    (from `@app_commands.choices`), and which options have an autocomplete
    (`@app_commands.autocomplete(...)` or `@command.autocomplete("option")`)
  - button and select `custom_id` values
  - discord.py hooks and listeners, and the `setup` functions, keyed by file
    and class (`file::Class.method`; module-level ones are `file::name`)
  - the cog module paths `discord-bot/main.py` loads
  - Telegram commands, menu commands, callback data and event handlers
  - the Telethon session name, env keys and data file names

Usage:
  python3 tools/check_protected_names.py           write tests/protected-names.json
  python3 tools/check_protected_names.py --check   compare with the saved file; exit 1 on any difference

The output is sorted, so it is identical from run to run. No line numbers are
recorded, so moving code around doesn't change it.
"""
import ast
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = REPO_ROOT / "tests" / "protected-names.json"
DISCORD_FOLDER = REPO_ROOT / "discord-bot"
TELEGRAM_FOLDER = REPO_ROOT / "telegram-bot"

# Function names that discord.py calls by name.
HOOK_NAMES = {
    "setup", "teardown", "callback", "interaction_check", "on_timeout", "on_error",
    "on_submit", "on_ready", "on_interaction", "autocomplete",
}
HOOK_PREFIXES = ("on_", "cog_", "bot_check")
DATA_FILE_SUFFIXES = (".csv", ".txt", ".json")


def relative(path):
    """Path of a file relative to the repo root, with forward slashes."""
    return path.relative_to(REPO_ROOT).as_posix()


def python_files(folder):
    """Every .py file under a folder, in sorted order, skipping caches, tests and virtualenvs."""
    found = []
    for path in sorted(folder.rglob("*.py")):
        parts = set(path.relative_to(folder).parts)
        if parts & {"__pycache__", ".venv", "tests"}:
            continue
        found.append(path)
    return found


def parse(path):
    """Parse a source file into an ast tree."""
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def dotted_name(node):
    """`a.b.c` for a Name/Attribute chain, else an empty string."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return ""


def constant(node):
    """The value of a str/bytes constant node, or the source text for anything else."""
    if isinstance(node, ast.Constant):
        value = node.value
        if isinstance(value, bytes):
            return value.decode("utf-8", "replace")
        return value
    return ast.unparse(node)


def keyword_value(call, name):
    """The node of keyword argument `name` in a call, or None."""
    for keyword in call.keywords:
        if keyword.arg == name:
            return keyword.value
    return None


def is_hook(name):
    """True when discord.py calls a function with this name."""
    return name in HOOK_NAMES or name.startswith(HOOK_PREFIXES)


def string_value(node):
    """The text of a constant node as a str (source text for non-constants)."""
    return str(constant(node))


def choice_list(node):
    """The `app_commands.Choice(name=..., value=...)` entries of a list node, as dicts."""
    choices = []
    if not isinstance(node, (ast.List, ast.Tuple)):
        return choices
    for item in node.elts:
        if isinstance(item, ast.Call) and dotted_name(item.func).endswith("Choice"):
            name_node = keyword_value(item, "name")
            value_node = keyword_value(item, "value")
            # Positional form: Choice("name", "value")
            if name_node is None and len(item.args) > 0:
                name_node = item.args[0]
            if value_node is None and len(item.args) > 1:
                value_node = item.args[1]
            choices.append({
                "name": string_value(name_node) if name_node is not None else "",
                "value": string_value(value_node) if value_node is not None else "",
            })
    return choices


def collect_discord_commands(tree, file_label, commands, hooks):
    """Record slash commands, options, descriptions, choices and autocompletes found in one cog file."""
    for class_node in [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]:
        # Group variables: `dev = app_commands.Group(name="dev", ...)`
        groups = {}
        for statement in class_node.body:
            if (isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Call)
                    and dotted_name(statement.value.func).endswith("Group")):
                name_node = keyword_value(statement.value, "name")
                for target in statement.targets:
                    if isinstance(target, ast.Name) and name_node is not None:
                        groups[target.id] = string_value(name_node)
        # Names of the command functions in this class, for `@help_command.autocomplete("category")`.
        command_functions = {}
        for function in class_node.body:
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            command_name = None
            group_name = None
            description = ""
            renames = {}
            describes = {}
            choices = {}
            autocompletes = set()
            for decorator in function.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                target = dotted_name(decorator.func)
                if target == "app_commands.command" or (
                        target.endswith(".command") and target.split(".")[0] in groups):
                    name_node = keyword_value(decorator, "name")
                    command_name = string_value(name_node) if name_node is not None else function.name
                    description_node = keyword_value(decorator, "description")
                    if description_node is not None:
                        description = string_value(description_node)
                    if target != "app_commands.command":
                        group_name = groups[target.split(".")[0]]
                elif target == "app_commands.rename":
                    for keyword in decorator.keywords:
                        renames[keyword.arg] = string_value(keyword.value)
                elif target == "app_commands.describe":
                    for keyword in decorator.keywords:
                        describes[keyword.arg] = string_value(keyword.value)
                elif target == "app_commands.choices":
                    for keyword in decorator.keywords:
                        choices[keyword.arg] = choice_list(keyword.value)
                elif target == "app_commands.autocomplete":
                    for keyword in decorator.keywords:
                        autocompletes.add(keyword.arg)
            if command_name is None:
                continue
            command_functions[function.name] = (function, renames, describes, choices, autocompletes,
                                                command_name, group_name, description)
        # `@some_command.autocomplete("option")` sits on a different function from the command.
        for function in class_node.body:
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in function.decorator_list:
                if (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)
                        and decorator.func.attr == "autocomplete"
                        and isinstance(decorator.func.value, ast.Name)
                        and decorator.func.value.id in command_functions):
                    for argument in decorator.args:
                        command_functions[decorator.func.value.id][4].add(string_value(argument))
        for (function, renames, describes, choices, autocompletes, command_name, group_name,
             description) in command_functions.values():
            parameters = [argument.arg for argument in function.args.posonlyargs + function.args.args
                          + function.args.kwonlyargs]
            options = [renames.get(parameter, parameter) for parameter in parameters[2:]]  # skip self, interaction
            entry = {
                "name": f"{group_name} {command_name}" if group_name else command_name,
                "file": file_label,
                "options": options,
                "description": description,
            }
            # Option details are keyed by the visible option name (after any rename).
            if describes:
                entry["option_descriptions"] = {renames.get(key, key): text for key, text in sorted(describes.items())}
            if choices:
                entry["option_choices"] = {renames.get(key, key): value for key, value in sorted(choices.items())}
            if autocompletes:
                entry["option_autocomplete"] = sorted(renames.get(key, key) for key in autocompletes)
            commands.append(entry)
    # Group commands themselves are protected names too.
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and dotted_name(node.func).endswith("Group"):
            name_node = keyword_value(node, "name")
            if name_node is not None:
                description_node = keyword_value(node, "description")
                commands.append({
                    "name": string_value(name_node),
                    "file": file_label,
                    "options": ["<group>"],
                    "description": string_value(description_node) if description_node is not None else "",
                })


def collect_hooks(tree, file_label, hooks):
    """Record discord.py hooks, listeners, events and setup functions in one file.

    Each is keyed `file::Class.method` (nested classes joined with dots), or
    `file::name` for a function outside any class.
    """

    def visit(node, class_names):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, class_names + [child.name])
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualified = ".".join(class_names + [child.name])
                decorators = [ast.unparse(decorator) for decorator in child.decorator_list]
                is_event = any(text.endswith(".event") or ".listen" in text or text.endswith("Cog.listener()")
                               for text in decorators)
                if is_hook(child.name) or is_event:
                    hooks.append(f"{file_label}::{qualified}")
                for decorator in child.decorator_list:
                    # @bot.listen("on_socket_response") names the event as a string.
                    if (isinstance(decorator, ast.Call) and dotted_name(decorator.func).endswith(".listen")
                            and decorator.args):
                        hooks.append(f"{file_label}::listen({constant(decorator.args[0])})")
                visit(child, class_names)
            else:
                visit(child, class_names)

    visit(tree, [])


def collect_custom_ids(tree, file_label, custom_ids):
    """Record every `custom_id=` keyword in one file."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            value = keyword_value(node, "custom_id")
            if value is not None:
                custom_ids.append(f"{file_label}::{constant(value)}")


def collect_env_keys(tree, env_keys):
    """Record the names read with os.getenv / os.environ."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and dotted_name(node.func) in ("os.getenv", "os.environ.get") and node.args:
            env_keys.add(str(constant(node.args[0])))


def collect_data_files(tree, data_files):
    """Record string constants that look like data file names (no slashes or colons)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            text = node.value
            if text.endswith(DATA_FILE_SUFFIXES) and "/" not in text and ":" not in text and " " not in text:
                data_files.add(text)


def discord_section():
    """Everything protected in discord-bot."""
    commands, hooks, custom_ids, env_keys, data_files = [], [], [], set(), set()
    for path in python_files(DISCORD_FOLDER):
        tree = parse(path)
        label = relative(path)
        if path.parent.name == "commands":
            collect_discord_commands(tree, label, commands, hooks)
        collect_hooks(tree, label, hooks)
        collect_custom_ids(tree, label, custom_ids)
        collect_env_keys(tree, env_keys)
        collect_data_files(tree, data_files)
    # The cog module paths main.py loads by string.
    cog_modules = []
    main_tree = parse(DISCORD_FOLDER / "main.py")
    for node in ast.walk(main_tree):
        if (isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "extensions"
                                                  for target in node.targets)):
            cog_modules = [str(constant(item)) for item in node.value.elts]
    commands.sort(key=lambda entry: (entry["name"], entry["file"]))
    return {
        "slash_commands": commands,
        "custom_ids": sorted(set(custom_ids)),
        "hooks": sorted(set(hooks)),
        "cog_modules": sorted(cog_modules),
        "env_keys": sorted(env_keys),
        "data_files": sorted(data_files),
    }


def telegram_section():
    """Everything protected in telegram-bot."""
    commands, menu_commands, callback_data = {}, set(), set()
    handlers, hooks, session_names, env_keys, data_files = set(), set(), set(), set(), set()
    for path in python_files(TELEGRAM_FOLDER):
        tree = parse(path)
        label = relative(path)
        collect_env_keys(tree, env_keys)
        collect_data_files(tree, data_files)
        for node in ast.walk(tree):
            # Telethon session name: TelegramClient("HelloBotSession", ...)
            if isinstance(node, ast.Call):
                target = dotted_name(node.func)
                if target == "TelegramClient" and node.args:
                    session_names.add(str(constant(node.args[0])))
                if target == "Button.inline" and len(node.args) > 1:
                    callback_data.add(str(constant(node.args[1])))
                if target.endswith("events.NewMessage") or target.endswith("events.CallbackQuery"):
                    for keyword in node.keywords:
                        if keyword.arg in ("pattern", "data"):
                            commands[f"pattern:{constant(keyword.value)}"] = ""
            # @self.client.on(events.X): the event handler registrations
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for decorator in node.decorator_list:
                    text = ast.unparse(decorator)
                    if ".on(" in text:
                        handlers.add(f"{label}::{node.name}({text.split('.on(', 1)[1][:-1]})")
                if node.name.startswith(("command_", "handle_")):
                    hooks.add(f"{label}::{node.name}")
            # commands = {"start": command_start, ...} and the setMyCommands list
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "commands"
                                                     for target in node.targets):
                if isinstance(node.value, ast.Dict):
                    for key, value in zip(node.value.keys, node.value.values):
                        commands[str(constant(key))] = ast.unparse(value)
                elif isinstance(node.value, ast.List):
                    for item in node.value.elts:
                        if isinstance(item, ast.Dict):
                            for key, value in zip(item.keys, item.values):
                                if constant(key) == "command":
                                    menu_commands.add(str(constant(value)))
            # action in ["list_users", ...] / action.startswith("guess_") in the callback handler
            if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id == "action":
                for comparator in node.comparators:
                    if isinstance(comparator, (ast.List, ast.Tuple, ast.Set)):
                        callback_data.update(str(constant(item)) for item in comparator.elts)
                    else:
                        callback_data.add(str(constant(comparator)))
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "startswith" and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "action" and node.args):
                callback_data.add(f"startswith:{constant(node.args[0])}")
    command_entries = [{"command": name, "handler": handler} for name, handler in sorted(commands.items())]
    return {
        "commands": command_entries,
        "menu_commands": sorted(menu_commands),
        "callback_data": sorted(callback_data),
        "event_handlers": sorted(handlers),
        "handler_functions": sorted(hooks),
        "session_names": sorted(session_names),
        "env_keys": sorted(env_keys),
        "data_files": sorted(data_files),
    }


def build_snapshot():
    """The full snapshot as a plain dict."""
    snapshot = {"discord": discord_section(), "telegram": telegram_section()}
    if "HelloBotSession" not in snapshot["telegram"]["session_names"]:
        raise SystemExit("check_protected_names: session name HelloBotSession not found in telegram-bot")
    return snapshot


def to_text(snapshot):
    """Stable JSON text: sorted keys, two-space indent, trailing newline."""
    return json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def flatten(value, prefix=""):
    """Flatten a snapshot into a set of 'path = item' lines, to show differences."""
    lines = set()
    if isinstance(value, dict):
        for key, item in value.items():
            lines |= flatten(item, f"{prefix}/{key}")
    elif isinstance(value, list):
        for item in value:
            lines.add(f"{prefix}: {json.dumps(item, sort_keys=True, ensure_ascii=False)}")
    else:
        lines.add(f"{prefix}: {value}")
    return lines


def main():
    """Write the snapshot, or with --check compare against the saved one."""
    text = to_text(build_snapshot())
    if "--check" in sys.argv[1:]:
        if not SNAPSHOT.exists():
            print(f"check_protected_names: {relative(SNAPSHOT)} is missing; run without --check to create it")
            return 1
        saved = SNAPSHOT.read_text(encoding="utf-8")
        if saved == text:
            print("check_protected_names: protected names unchanged")
            return 0
        saved_lines, new_lines = flatten(json.loads(saved)), flatten(json.loads(text))
        print("check_protected_names: DIFFERENCES from tests/protected-names.json")
        for line in sorted(saved_lines - new_lines):
            print(f"  removed: {line}")
        for line in sorted(new_lines - saved_lines):
            print(f"  added:   {line}")
        return 1
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(text, encoding="utf-8")
    print(f"check_protected_names: wrote {relative(SNAPSHOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
