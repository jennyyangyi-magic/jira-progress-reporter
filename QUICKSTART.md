# Quick Start Guide

Get up and running with `jira-progress-reporter` in 5 minutes.

## 1. Install

```bash
cd jira-progress-skill
pip install -e .
```

Verify:
```bash
jira-progress --help
```

## 2. Configure

Create `.env` file:

```bash
# For Red Hat Jira (Data Center with Personal Access Token)
cat > .env <<EOF
JIRA_URL=https://issues.redhat.com
JIRA_PERSONAL_TOKEN=your-token-here
EOF
```

Or for Jira Cloud:
```bash
cat > .env <<EOF
JIRA_URL=https://yourcompany.atlassian.net
JIRA_USERNAME=your@email.com
JIRA_API_TOKEN=your-api-token-here
EOF
```

## 3. Run

```bash
# Basic report (markdown + JSON)
jira-progress RHAISTRAT-26

# With PowerPoint slides
jira-progress RHAISTRAT-26 --slides

# Without LLM synthesis (faster, no API key needed)
jira-progress RHAISTRAT-26 --no-llm
```

## 4. View Output

```bash
# Check the progress/ directory
ls -lh progress/

# View markdown report
cat progress/2026-03-11_rhaistrat_26.md

# Or open PowerPoint
open progress/2026-03-11_rhaistrat_26.pptx
```

## 5. Use with Claude Desktop

```bash
# Copy the skill
cp claude-skill.md ~/.claude/skills/jira-progress.md

# Restart Claude Desktop

# Ask Claude:
# "Generate a progress report for RHAISTRAT-26 with slides"
```

## 6. Use with Cursor

```bash
# In your project directory
cat cursorrules.md >> .cursorrules

# In Cursor Composer:
# "Generate progress report for RHAISTRAT-26"
```

---

## What You Get

### Markdown Report (`*.md`)
- Outcome summary with all STRATs
- Health status (GREEN/YELLOW/RED) per STRAT
- Inter-STRAT dependencies
- STRATs grouped by target release
- Implementation ticket rollups
- Coverage gaps (approved RFEs without STRATs)
- Executive summary (if LLM enabled)

### JSON Export (`*.json`)
- Structured data for programmatic access
- All STRAT health signals
- Dependency graph
- Implementation ticket mappings

### PowerPoint Slides (`*.pptx`)
- Overview slide with release-grouped STRATs
- Detail slide per STRAT
- Health signals, relationships, implementation
- Red Hat brand colors
- Hyperlinked Jira keys

---

## Example Output

```bash
$ jira-progress RHAISTRAT-26 --slides

2026-03-11 21:15:00 [INFO] Fetching outcome tree for RHAISTRAT-26
2026-03-11 21:15:02 [INFO] Extracting progress data
2026-03-11 21:15:02 [INFO] Formatting structured report
2026-03-11 21:15:02 [INFO] Synthesizing with LLM (anthropic:claude-sonnet-4-6)
2026-03-11 21:15:05 [INFO] Exporting to progress/
2026-03-11 21:15:05 [INFO] Saved: progress/2026-03-11_rhaistrat_26.md
2026-03-11 21:15:05 [INFO] Saved: progress/2026-03-11_rhaistrat_26.json
2026-03-11 21:15:05 [INFO] Generating PowerPoint slides
2026-03-11 21:15:06 [INFO] Saved: progress/2026-03-11_rhaistrat_26.pptx

✓ Report generated: progress/2026-03-11_rhaistrat_26.md
✓ Slides generated: progress/2026-03-11_rhaistrat_26.pptx
```

---

## Troubleshooting

### "Missing required environment variable: JIRA_URL"
→ Create `.env` file (see step 2)

### "401 Unauthorized"
→ Check your token/credentials are correct

### "OutcomeError: ... is not an Outcome or Feature"
→ The issue key must be a Jira Outcome or Feature type

### "ModuleNotFoundError: No module named 'jira_progress'"
→ Run `pip install -e .` from the package directory

---

## Next Steps

- **Customize**: Edit `src/jira_progress/pipeline.py` for your Jira instance
- **Share**: Copy `claude-skill.md` or `cursorrules.md` to your team
- **Automate**: Run on a schedule with cron/GitHub Actions
- **Extend**: Add new health logic or export formats

See `README.md` and `INSTALL.md` for full documentation.
