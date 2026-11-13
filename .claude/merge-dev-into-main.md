# Merging `dev` into `main`: HelloBot

Context for whoever merges this repo's `dev` branch into `main`. Augy, give this file to Claude: "Read `.claude/merge-dev-into-main.md` and help me merge `dev` into `main`."

- **What's on `dev`:** the readable-refactor chain for help desk #19, one squash commit per job. 2 of 7 jobs have landed so far.
- **What merging does:** Merging into `main` changes nothing live by itself: the bots run on a server. After the merge, pull `main` there and restart both bots.
- **Kept up to date:** the coordinator (Thomas's workspace) updates this file each time a job lands, and once more just before opening the pull request. Last updated 13 Nov, 15:37 SGT.

## Claude: how to run the merge

Work through these in order, and stop to ask Augy wherever a step says so.

1. **Read first:** this file, then `README.md`. Never read, print or copy a `.env` or `token.env` file; use the `.example` files.
2. **Check `dev` matches this file:** `git fetch origin`, then `git log --oneline origin/main..origin/dev`. Every commit in the Jobs table below should be there. Read the message of any commit the table doesn't list (`git show <sha>`) and tell Augy what it is.
3. **Run the tests** on a checkout of `dev` (commands below). All must pass. If one fails, stop and tell Augy; don't fix it on `main`.
4. **Go through "Before merging"** with Augy. Steps marked as his (Vercel settings, the database) are his to do by hand; ask him to confirm each one.
5. **The pull request:** `gh pr list --base main --head dev`. Thomas's side opens it once the last job lands. If Augy wants to ship before that, open it yourself: `gh pr create --base main --head dev`, titled "Help desk #19: readable refactor", with the Jobs table as its body.
6. **Merge with a merge commit, never squash or rebase**: `gh pr merge <number> --merge`. Squashing would drop the one-commit-per-job history, and each commit's `Archived-As` line points to the job's full branch. Ask Augy before running it: **merging is deploying.**
7. **Go through "After merging"**, then the smoke test with Augy on the live site.
8. **If something breaks:** in Vercel, promote the previous production deployment to roll back at once. Then revert the merge on `main` through a pull request (`git revert -m 1 <merge sha>`), and tell Thomas. Never force-push.

## Jobs

| Job | What it does | On `dev` |
|---|---|---|
| 01 | Safety net | `9c733c2` |
| 02 | Shared and small files | `bada18b` |
| 03 | Telegram bot cogs | to come |
| 04 | Discord: small cogs | to come |
| 05 | Discord: generative and profile | to come |
| 06 | Discord: games and utility | to come |
| 07 | Final sweep | to come |

Each job's commit message lists what changed and how it was reviewed. The full branch is kept at `refs/archive/<job-id>`: `git fetch origin 'refs/archive/*:refs/archive/*'` to see them.

## Tests

```bash
python3 -m venv .venv
.venv/bin/pip install ruff
iconv -f UTF-16 -t UTF-8 discord-bot/requirements.txt > /tmp/discord-req.txt   # until job 07 converts it
.venv/bin/pip install -r /tmp/discord-req.txt
tools/check_all.sh   # compile, ruff, imports, protected names, unit tests; never logs in
```

They need no `.env`, network or real database.

## Before merging

- **Protected names:** `python3 tools/check_protected_names.py --check` must pass on `dev`. It proves no slash command, option, choice, button id or Telegram command changed.

## After merging

- Pull `main` on the bot server, reinstall requirements if they changed, and restart both bots.

## Smoke test on the live site

The tests can't reach the real database, logins or messaging, so check these by hand after the deploy:

- Slash commands sync in the test server and appear in Discord.
- Run one command from each cog, a button flow, and an image command.
- The Telegram bot answers its commands.
- The log channel still gets entries.

## What users may notice

- None meant: this chain only renames and rewrites for readability. Users should see no difference.

Open questions and anything left for later are on help desk #19's review page, not here.
