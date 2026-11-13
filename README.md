# gftv-hellobot
Global Furry Television Communities' HelloBot

---

[Buy Augy a Coffee](https://donate.stripe.com/28o2akeAr3hv0DK6oo) or [Support Augy Monthly](https://donate.stripe.com/6oEbKUdwn9FTgCI7st)!

Is the bot not responding? Check its status [here](https://pages.statusbot.us/id/873989298507120690)!

> **Note:** Music and voice channel commands have been removed. The bot no longer supports audio playback or joining/leaving voice channels.

## Checks

Run these before merging any change to either bot. They need Python 3.10 or newer, and never log
in to Discord or Telegram.

```bash
python3 -m venv .venv
.venv/bin/pip install ruff
iconv -f UTF-16 -t UTF-8 discord-bot/requirements.txt > /tmp/discord-req.txt
.venv/bin/pip install -r /tmp/discord-req.txt
tools/check_all.sh
```

- `tools/check_all.sh` runs, in order: a compile check, ruff, an import check of every cog with
  the network blocked, the protected-names check, and the unit tests. It stops at the first
  failure.
- The `requirements.txt` files are UTF-16 for now, hence `iconv`; help desk #19's final job
  converts them to UTF-8.
- **Protected names** (`tests/protected-names.json`) are the names and text users and Discord
  see: slash commands and their descriptions, options with their help text, choices (name and
  value) and which options autocomplete, button ids, Telegram commands, and hooks, recorded as
  `file::Class.method`. After a change that's meant to alter one, regenerate it with
  `python3 tools/check_protected_names.py` and review the diff.
- The check reads env keys only from literal `os.getenv("KEY")` calls, so keep them literal.
- **The ruff baseline** is in `tests/ruff-baseline.txt` (20 today). Lower it as findings are
  fixed; the check fails if the count goes up.
