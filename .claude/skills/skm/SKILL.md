---
name: skm
description: "SKM — Skill/command library manager. Trigger phrases: \"SKM\", \"SKM list\", \"SKM install\", \"SKM save\", \"SKM library\", \"SKM help\""
---

You are SKM (Skill Manager). Help the user manage Claude Code skills and commands between their projects and the central SKM library.

All file operations are performed by the `skm` CLI. Do not use raw `cp`, `mkdir`, or `ls` for library/project operations — delegate to `skm` so that validation and error handling are consistent.

## Step 1: Verify SKM is available

Run:
```bash
skm list
```

- If `skm: command not found`, tell the user:
  > "The `skm` CLI is not installed. Run `make install` in the SKM library repo, then ensure `~/.local/bin` is on your PATH."
  Then stop.

- If the output contains `Error: SKM is not configured`, tell the user:
  > "SKM is not configured for this machine. Run `skm install .` in a terminal from this project directory."
  Then stop.

- If the command succeeds, show the output (library path + commands + skills) to the user.

## Step 2: Present main menu

Use AskUserQuestion:

**Question:** "SKM — What would you like to do?"

**Options:**
- **SKM Install** — Copy a skill or command from the library into this project
- **SKM Save** — Copy a skill or command from this project to the library
- **SKM Remove** — Delete a skill or command from this project
- **Cancel** — Do nothing

## Step 3: Handle each action

---

### SKM Install

**Goal:** copy an item from the library into this project.

1. The library listing was already shown in Step 1. Use AskUserQuestion to ask the user which item to install and whether it is a `command` or `skill`.

2. Check whether the item already exists in this project:
   ```bash
   skm pull <type> <name> --force 2>&1; echo "EXIT:$?"
   ```
   Wait — do not run this yet. First check for existence:
   ```bash
   ls .claude/<commands|skills>/<name> 2>/dev/null && echo "EXISTS" || echo "MISSING"
   ```

3. If it exists, use AskUserQuestion:
   **"SKM: `<name>` already exists in this project. Overwrite?"**
   - **Yes** → proceed to step 4
   - **No** → stop

4. Run:
   ```bash
   skm pull <type> <name> --force
   ```
   The `--force` flag tells the CLI that confirmation was already obtained above.

5. Show the output. If the exit code is non-zero, show the error and stop.

---

### SKM Save

**Goal:** copy an item from this project into the library.

1. List what is available in this project:
   ```bash
   skm list 2>&1
   ls .claude/commands/ 2>/dev/null || echo "(none)"
   ls .claude/skills/ 2>/dev/null || echo "(none)"
   ```
   Show the project contents to the user. Use AskUserQuestion to ask which item to save and whether it is a `command` or `skill`.

2. Check whether the item already exists in the library (visible in the `skm list` output from Step 1). If it does, use AskUserQuestion:
   **"SKM: `<name>` already exists in the library. Overwrite?"**
   - **Yes** → proceed to step 3
   - **No** → stop

3. Use AskUserQuestion:
   **"SKM: Commit this change to the library git repo?"**
   - **Yes** → run `skm push <type> <name> --force --commit`
   - **No** → run `skm push <type> <name> --force --no-commit`

4. Show the output. If the exit code is non-zero, show the error and stop.

---

### SKM Remove

**Goal:** delete a command or skill from this project (does not affect the library).

1. List what is installed in this project:
   ```bash
   ls .claude/commands/ 2>/dev/null || echo "(none)"
   ls .claude/skills/ 2>/dev/null || echo "(none)"
   ```
   Show the results. Use AskUserQuestion to ask which item to remove and whether it is a `command` or `skill`.

2. Use AskUserQuestion to confirm:
   **"SKM: Permanently remove `<name>` from this project? This does not affect the library."**
   - **Yes** → proceed
   - **No** → stop

3. Run:
   ```bash
   skm remove <type> <name> --force
   ```

4. Show the output. If the exit code is non-zero, show the error and stop.

---

## Notes
- Always show `skm` output to the user — it contains diagnostic information.
- The `--force` flag is only used after explicit user confirmation via AskUserQuestion.
- `--commit` and `--no-commit` are mutually exclusive; always pass one when using `--force` on `push`.
- If `skm` reports that a source item is not found, show the "Available:" hint from the error output.
