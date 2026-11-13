# Merging `dev` into `main`: HelloBot

Context for whoever merges this repo's `dev` branch into `main`. Augy, give this file to Claude: "Read `.claude/merge-dev-into-main.md` and help me merge `dev` into `main`."

- **What's on `dev`:** the readable-refactor chain for help desk #19, one squash commit per job. 8 of 8 jobs have landed so far.
- **What merging does:** Merging into `main` changes nothing live by itself: the bots run on a server. After the merge, pull `main` there and restart both bots.
- **Kept up to date:** the coordinator (Thomas's workspace) updates this file each time a job lands, and once more just before opening the pull request. Last updated 13 Nov, 16:46 SGT.

## Claude: how to run the merge

Work through these in order, and stop to ask Augy wherever a step says so.

1. **Read first:** this file, then `README.md`. Never read, print or copy a `.env` or `token.env` file; use the `.example` files.
2. **Check `dev` matches this file:** `git fetch origin`, then `git log --oneline origin/main..origin/dev`. Every commit in the Jobs table below should be there. Commits titled "Merge context" only update this file. Read the message of any other commit the table doesn't list (`git show <sha>`) and tell Augy what it is.
3. **Run the tests** on a checkout of `dev` (commands below). All must pass. If one fails, stop and tell Augy; don't fix it on `main`.
4. **Go through "Before merging"** with Augy. Steps marked as his (Vercel settings, the database) are his to do by hand; ask him to confirm each one.
5. **The pull request:** `gh pr list --base main --head dev`. Thomas's side opens it once the last job lands. If Augy wants to ship before that, open it yourself: `gh pr create --base main --head dev`, titled "Help desk #19: readable refactor", with the Jobs table as its body.
6. **Merge with a merge commit, never squash or rebase**: `gh pr merge <number> --merge`. Squashing would drop the one-commit-per-job history, and each commit's `Archived-As` line points to the job's full branch. Ask Augy before running it: **merging is deploying.**
7. **Go through "After merging"**, then the smoke test with Augy (unless this file says to run it before merging).
8. **If something breaks:** in Vercel, promote the previous production deployment to roll back at once. Then revert the merge on `main` through a pull request (`git revert -m 1 <merge sha>`), and tell Thomas. Never force-push.

## Jobs

| Job | What it does | On `dev` |
|---|---|---|
| 01 | Safety net | `9c733c2` |
| 02 | Shared and small files | `bada18b` |
| 03 | Telegram bot cogs | `68e9a14` |
| 04 | Discord: small cogs | `425677a` |
| 05 | Discord: generative and profile | `109a9f8` |
| 06 | Discord: games and utility | `75c8d02` |
| 07 | Final sweep | `0cbe30f` |
| 08 | Security: `/math` and moderation permissions | `9749ea5` |

Each job's commit message lists what changed and how it was reviewed. The full branch is kept at `refs/archive/<job-id>`: `git fetch origin 'refs/archive/*:refs/archive/*'` to see them.

## Tests

```bash
python3 -m venv .venv
.venv/bin/pip install ruff
.venv/bin/pip install -r discord-bot/requirements.txt
.venv/bin/pip install -r telegram-bot/requirements.txt   # separately: the two pin different discord.py
tools/check_all.sh   # compile, ruff, imports, protected names, unit tests; never logs in
```

They need no `.env`, network or real database.

## Before merging

- **Protected names:** `python3 tools/check_protected_names.py --check` must pass on `dev`. It proves no slash command, option, choice, button id or Telegram command changed.

## After merging

- Pull `main` on the bot server, reinstall requirements if they changed, and restart both bots.

## Smoke test before merging

Augy's call (decision 4): run these on a test server with the real tokens before merging, since the checks never log in:

- **Start and sync:** `discord-bot/main.py` starts with every cog loaded; `/dev sync` succeeds; typing `/` shows the commands, `/dev` included.
- **One command per cog**, each replying: `/ping`, `/help` (category choice and buttons), `/botinfo`, `/serverinfo`, `/userinfo`, `/8ball`, `/coin guess:HEADS`, `/roll dice:2d6`, `/math expression:2+3*4` (14), `/randnum` (options still `min_num`/`max_num`), and on a test user `/nickname`, `/mute`, `/unmute`; as owner `/dev stats`, `/dev sessions`, `/dev reload`.
- **Buttons:** `/tictactoe`, `/connect4`, `/chess`, `/battle`, `/trivia`, `/uno`, `/flagmatch` (only the right player's presses count); the `/botinfo` and `/serverinfo` pagers; `/countrychecklist`; `/translate text:hello to_lang:es` (autocomplete, both listen buttons).
- **Image commands** return an attachment: `/profile`, `/enhance`, `/dots` (overlap true and false), `/waves`, `/3dify`, `/predict`.
- **Word list and animals:** `/wordle length:5`, `/hangman length:6`, `/cat`, `/dog`, `/fox`.
- **Telegram bot:** starts with `HelloBotSession` still logged in; `/start`, `/help`, `/ping`, `/roll`, `/coin` and its button, `/cat`; owner-only `/broadcast`, `/dm` in a test chat.
- **Job 08:** a member without the permission gets a private refusal from `/kick` or `/mute`; `/math expression:9**9**9` is refused at once; `/math expression:0/0` still sends the cookie reply.
- The log channel still gets entries.

## What users may notice

- None meant: this chain only renames and rewrites for readability. Users should see no difference.

Open questions and anything left for later are on help desk #19's review page, not here.
