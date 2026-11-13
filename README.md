# gftv-hellobot
Global Furry Television Communities' HelloBot

---

[Buy Augy a Coffee](https://donate.stripe.com/28o2akeAr3hv0DK6oo) or [Support Augy Monthly](https://donate.stripe.com/6oEbKUdwn9FTgCI7st)!

Is the bot not responding? Check its status [here](https://pages.statusbot.us/id/873989298507120690)!

> **Note:** Music and voice channel commands have been removed. The bot no longer supports audio playback or joining/leaving voice channels.

## Checks

Run these before merging any change to either bot. They need Python 3.13 or newer (`audioop-lts`), and
never log in to Discord or Telegram.

```bash
python3 -m venv .venv
.venv/bin/pip install ruff
.venv/bin/pip install -r telegram-bot/requirements.txt   # the import check loads the Telegram cogs too
.venv/bin/pip install -r discord-bot/requirements.txt    # last: the Telegram file pins an older discord.py
tools/check_all.sh
```

- `tools/check_all.sh` runs, in order: a compile check, ruff, an import check of every cog with
  the network blocked, the protected-names check, and the unit tests. It stops at the first
  failure.
- **Protected names** (`tests/protected-names.json`) are the names and text users and Discord
  see: slash commands and their descriptions, options with their help text, choices (name and
  value) and which options autocomplete, button ids, Telegram commands, and hooks, recorded as
  `file::Class.method`. After a change that's meant to alter one, regenerate it with
  `python3 tools/check_protected_names.py` and review the diff.
- The check reads env keys only from literal `os.getenv("KEY")` calls, so keep them literal.
- **The ruff baseline** is in `tests/ruff-baseline.txt` (15 today). Lower it as findings are
  fixed; the check fails if the count goes up.

## Code style

- Names are whole words in snake_case (`user_message`, `letter_index`), not short forms (`w`,
  `cnt`, `i`, `e`). A bare `_` is fine for a throwaway value.
- Every function and method has a docstring. Big functions (about 40 lines or more) also have a
  comment above each main step.
- Slash command callbacks keep a one-line docstring, because discord.py reads it.
- No one-line `a if b else c`: write a full `if` / `else`. No `lambda`: use a named function.
  Simple comprehensions are fine, with a comment saying what they build.
- Never change a command name, option name, `custom_id` or the Telegram session name
  `HelloBotSession` while tidying. `tools/check_protected_names.py --check` catches this.
- Run `tools/check_all.sh` before merging.
