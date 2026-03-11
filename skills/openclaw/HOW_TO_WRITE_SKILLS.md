# How to Write OpenClaw Skills

> Based on `lerobot-env-setup` — a production skill used on Jetson/SO-ARM.
> Intended as a reference for agents writing new skills.

---

## 1. What is a Skill?

A skill is a directory installed at `~/.agents/skills/<skill-name>/` containing:
- **`SKILL.md`** — the agent's instruction file (loaded when the skill is invoked)
- **`scripts/`** — executable helper scripts (bash, python)
- **`references/`** — static data files (JSON, markdown) the scripts read

OpenClaw discovers skills from this path and surfaces them with
`openclaw skills list` / `openclaw skills info <name>`.

---

## 2. Directory Layout

```
~/.agents/skills/<skill-name>/
├── SKILL.md                   # required
├── scripts/
│   ├── main_script.sh         # entry-point script
│   └── helper.py              # supporting scripts
└── references/
    ├── data.json
    └── notes.md
```

Minimal skill: just `SKILL.md`. Add `scripts/` and `references/` only when needed.

---

## 3. SKILL.md Format

### 3.1 YAML Frontmatter (required)

```markdown
---
name: skill-name-hyphenated
description: One-sentence description shown in `openclaw skills list`.
---
```

Rules:
- `name` must match the directory name exactly (hyphenated, lowercase)
- `description` is what other agents and users see when browsing skills — make it
  specific enough to answer "when should I use this?"

**Good description:**
```
Set up the LeRobot environment on NVIDIA Jetson (SO-ARM / JetPack 6.0+). Installs
Seeed-fork LeRobot with GPU-enabled torch 2.8, pinned numpy 1.26, OpenCV 4.10,
and resolves the torch-overwrite trap from editable install. Use when the user
asks to install, rebuild, or fix LeRobot on Jetson.
```

**Bad description:**
```
Installs stuff for robots.
```

### 3.2 Content Structure

The body of `SKILL.md` is the agent's operating manual. Structure it as:

```
# <Skill Title>

## Execution model        ← HOW the agent should run this skill
## Phase commands         ← WHAT commands to run (copy-paste ready)
## Failure decision tree  ← WHAT to do when things go wrong
## Reference files        ← WHERE to find more detail
```

---

## 4. The Phase Pattern (key insight)

**Do not write a single monolithic command.** Break long operations into phases.

### Why

| Problem | Solution |
|---------|----------|
| Agent bash calls have implicit timeouts | Short phases finish within the window |
| Silent failure mid-install is unrecoverable | Each phase has a clear success/failure signal |
| User has no visibility into progress | Agent reports output after each phase |
| Retry is expensive if everything re-runs | Idempotent phases skip already-done steps |

### How to design phases

1. Identify natural checkpoints (env created / files downloaded / pkg installed)
2. Make each phase independently re-runnable (idempotent)
3. Name phases descriptively: `env`, `download`, `build`, `validate`
4. Expose via a single `--phase` flag, with `all` as the default

```bash
# Agent runs one phase at a time:
bash script.sh --env myenv --phase env
bash script.sh --env myenv --phase download
bash script.sh --env myenv --phase install
```

### Idempotency checklist

Each phase should check before acting:

```bash
# Pattern: check → skip or do
if already_done; then
  log "Step N: already done — skip"
else
  log "Step N: doing work..."
  do_work
fi
```

---

## 5. Script Conventions

### Log format

Use a consistent prefix so the agent can parse output:

```bash
log()  { echo "[install] $*"; }      # normal progress
die()  { echo "[STOP]    $*" >&2; exit 1; }  # hard stop, agent must not continue
```

The agent instruction in `SKILL.md` should say:
> If script printed `[STOP]` → stop and follow failure decision tree.
> If script ended with `[OK]` → proceed to next phase.

### Hard stops vs soft warnings

| Use `die` ([STOP]) when | Use a warning when |
|-------------------------|--------------------|
| Precondition is unmet (missing file, wrong Python version) | A step was skipped (already installed) |
| Continuing would produce silent wrong state | A non-critical component failed |
| The agent cannot self-recover without user input | The agent can retry automatically |

### PATH and environment portability

Agent sessions do not source `~/.bashrc`, so tools like `conda` may not be in PATH.
Always probe standard locations explicitly:

```bash
for _p in "$(command -v conda 2>/dev/null)" \
          "$HOME/miniconda3/bin/conda" \
          "$HOME/anaconda3/bin/conda"; do
  [[ -n "$_p" && -x "$_p" ]] && { CONDA_BIN="$_p"; break; }
done
[[ -z "$CONDA_BIN" ]] && die "conda not found — install Miniconda first"
```

### Self-referencing scripts

Use `SKILL_DIR` to reference sibling files inside the skill:

```bash
SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
# Now reference: "$SKILL_DIR/references/data.json"
#                "$SKILL_DIR/scripts/helper.py"
```

---

## 6. Failure Decision Table

Every `SKILL.md` should include a table mapping `[STOP]` outputs to agent actions:

```markdown
## Failure decision tree

| Output | Action |
|--------|--------|
| `[STOP] conda not found` | Ask user to confirm Miniconda path |
| `[STOP] wheel not found after download` | URL may be expired — ask user to re-share |
| `[STOP] CUDA = False` | Wheel corrupt — `rm ~/wheels/*.whl` then re-run download + install |
| `[FAIL] Some checks failed` | Check which line shows ✗, see `references/playbook.md` |
| No output for >5 min | Report to user, ask whether to cancel |
```

The table is the agent's substitute for judgment. When something fails, the agent
should not guess — it looks up the `[STOP]` message in this table.

---

## 7. Reference Files

Use `references/` for data the script reads or the agent consults:

| File type | Purpose |
|-----------|---------|
| `*_matrix.json` | Version compatibility gates (read by scripts) |
| `*_playbook.md` | Step-by-step recovery for known failure modes |
| `*_rules.md` | Decision rules (install order, priority logic) |
| `*_setup.md` | Detailed human-readable install notes |

Keep scripts lean — push lookup tables and config into `references/` files.

---

## 8. SKILL.md Agent Instructions Style

Write for a language model, not a human. Be explicit about:

- **When to stop vs. continue** — don't leave it ambiguous
- **What to relay to the user** — "show `[install]` lines" is more useful than "report progress"
- **Decision points with tables** — tables are easier for agents to parse than prose
- **Copy-paste ready commands** — put `--env <ENV>` substitution in the command block,
  not in a separate sentence

**Prefer:**
```markdown
If output contains `[STOP]` → stop. Look up the message in the failure table.
If output ends with `[OK]` → tell the user "Phase N done" and run the next phase command.
```

**Avoid:**
```markdown
Monitor the output and handle errors appropriately.
```

---

## 9. Install / Source Sync Pattern

Keep source and installed copies in sync with a deploy script or rsync:

```bash
# Source (version-controlled):
~/Dayu_ws/jetson-develop/skills/openclaw/my_skill/

# Export dir (used by install script):
~/openclaw_skills/my-skill/

# Installed location (OpenClaw reads from here):
~/.agents/skills/my-skill/

# Sync command:
rsync -a --exclude='__pycache__' \
  ~/Dayu_ws/jetson-develop/skills/openclaw/my_skill/ \
  ~/openclaw_skills/my-skill/

# Install:
bash ~/Dayu_ws/jetson-develop/scripts/install_skills.sh
```

After install, verify with:
```bash
openclaw skills list
openclaw skills info my-skill
```

---

## 10. Quick Checklist

Before shipping a skill:

- [ ] `SKILL.md` has valid YAML frontmatter (`name`, `description`)
- [ ] `name` in frontmatter matches directory name
- [ ] `description` answers "when should I use this?"
- [ ] Long operations are split into phases with `--phase` flag
- [ ] Each phase is idempotent (re-runnable without side effects)
- [ ] Scripts use `[install]` / `[STOP]` / `[OK]` log format
- [ ] `SKILL.md` has a failure decision table covering all `[STOP]` cases
- [ ] Scripts use `SKILL_DIR` to reference sibling files
- [ ] Scripts probe for tools (conda, python, etc.) without assuming PATH
- [ ] Verified: `openclaw skills info <name>` shows correct description
