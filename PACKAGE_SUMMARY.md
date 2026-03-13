# Jira Progress Reporter - Package Summary

**Extracted from:** Coxswain chief-of-staff AI agent
**Created:** 2026-03-11
**Status:** ✅ Ready for testing

---

## What This Package Does

Generates comprehensive progress reports for Jira Outcomes and Features with:
- ✅ Dependency graph traversal (parent-child + issuelinks)
- ✅ Health status analysis (GREEN/YELLOW/RED based on Jira signals)
- ✅ Markdown + JSON exports
- ✅ Branded PowerPoint slides (Red Hat theme)
- ✅ Optional LLM synthesis for executive summaries

---

## Package Structure

```
jira-progress-skill/
├── README.md                    # User documentation
├── INSTALL.md                   # Installation guide
├── LICENSE                      # MIT license
├── pyproject.toml               # Package metadata + dependencies
├── .env.example                 # Configuration template
├── .gitignore                   # Git ignore rules
│
├── claude-skill.md              # Claude Desktop skill (copy to ~/.claude/skills/)
├── cursorrules.md               # Cursor integration (add to .cursorrules)
│
└── src/jira_progress/
    ├── __init__.py              # Package exports
    ├── __main__.py              # CLI entry point (jira-progress command)
    ├── client.py                # Jira REST API client (httpx-based)
    ├── pipeline.py              # Core pipeline: fetch → analyze → report
    ├── slides.py                # PowerPoint export (python-pptx)
    ├── prompts.py               # LLM prompt templates
    └── config/
        └── brand.json           # Red Hat brand colors/fonts
```

---

## Dependencies

**Core:**
- `httpx>=0.28.1` - Jira API client
- `pydantic>=2.0` - Data models
- `pydantic-ai>=1.67.0` - LLM synthesis (optional, can skip with `--no-llm`)
- `python-pptx>=0.6.0` - PowerPoint export

**Why Pydantic?**
- Already required by pydantic-ai
- Provides clean data models with validation
- Easy JSON serialization (`.model_dump()`)
- Date parsing (ISO string → Python `date`)

**Total size:** ~2MB installed

---

## Installation & Usage

### Install
```bash
cd jira-progress-skill
pip install -e .
```

### Configure
```bash
cp .env.example .env
# Edit .env with your Jira credentials
```

### Run
```bash
jira-progress RHAISTRAT-26              # Basic report
jira-progress RHAISTRAT-26 --slides     # With PowerPoint
jira-progress RHAISTRAT-26 --no-llm     # Skip LLM synthesis
```

### Output
Reports saved to `progress/`:
- `2026-03-11_rhaistrat_26.md` - Markdown report
- `2026-03-11_rhaistrat_26.json` - Structured JSON
- `2026-03-11_rhaistrat_26.pptx` - PowerPoint slides (if `--slides`)

---

## Claude Desktop Integration

```bash
# Copy skill file
cp claude-skill.md ~/.claude/skills/jira-progress.md

# Use in Claude:
> "Generate a progress report for RHAISTRAT-26 with slides"

# Claude will:
# 1. Run: jira-progress RHAISTRAT-26 --slides
# 2. Read: progress/2026-03-11_rhaistrat_26.md
# 3. Present formatted report with insights
```

---

## Cursor Integration

```bash
# Add to project's .cursorrules
cat cursorrules.md >> .cursorrules

# Use in Cursor Composer:
> "Generate progress report for RHAISTRAT-26"
```

---

## What Was Removed from Coxswain

**Removed** (not needed for progress reports):
- ❌ MCP servers (Slack, Google, GitHub)
- ❌ Briefing pipeline
- ❌ Triage pipeline
- ❌ Typer CLI (replaced with argparse)
- ❌ Rich console output
- ❌ APScheduler
- ❌ Settings class (using os.getenv instead)

**Kept** (essential for progress reports):
- ✅ JiraClient (REST API client)
- ✅ Outcome pipeline (fetch, analyze, report)
- ✅ Slides exporter (PowerPoint generation)
- ✅ LLM synthesis (PydanticAI)
- ✅ Brand config (Red Hat theme)

---

## Customization Points

Users can customize for their Jira instance:

### 1. Implementation Projects
```python
# src/jira_progress/pipeline.py, line 26
IMPLEMENTATION_PROJECTS = frozenset({"RHOAIENG", "RHAIENG", "AIPCC", "PSAP"})
```

### 2. Link Types to Traverse
```python
# src/jira_progress/pipeline.py, line 28
TRAVERSAL_LINK_TYPES = frozenset({"Blocks", "Cloners", "Depend", "Related"})
```

### 3. Custom Field IDs
```python
# src/jira_progress/pipeline.py, lines 39-44
CF_COLOR_STATUS = "customfield_12320845"
CF_BLOCKED = "customfield_12316543"
# ... etc (varies by Jira instance)
```

### 4. Health Status Logic
```python
# src/jira_progress/pipeline.py, _compute_strat_health() function
# Currently: GREEN/YELLOW/RED based on status, blocked flag, target release
```

### 5. Brand Colors
```python
# src/jira_progress/config/brand.json
# Currently: Red Hat red (#EE0000) + black (#292929)
```

---

## Testing Checklist

Before distribution, test:

- [ ] Install: `pip install -e .`
- [ ] CLI help: `jira-progress --help`
- [ ] Basic report: `jira-progress RHAISTRAT-26`
- [ ] With slides: `jira-progress RHAISTRAT-26 --slides`
- [ ] No LLM: `jira-progress RHAISTRAT-26 --no-llm`
- [ ] Claude skill: Copy to `~/.claude/skills/`, test in Claude
- [ ] Cursor: Add to `.cursorrules`, test in Cursor
- [ ] Invalid issue: `jira-progress INVALID-123` (should fail gracefully)
- [ ] Missing auth: Remove `.env`, verify error message

---

## Distribution Options

### Option 1: PyPI Package
```bash
# Build
python -m build

# Upload to PyPI
twine upload dist/*

# Users install:
pip install jira-progress-reporter
```

### Option 2: GitHub Template Repo
```bash
# Create repo: github.com/you/jira-progress-reporter
# Users clone and install:
git clone https://github.com/you/jira-progress-reporter
cd jira-progress-reporter
pip install -e .
```

### Option 3: Direct Share
```bash
# Zip the directory
zip -r jira-progress-reporter.zip jira-progress-skill/

# Share the zip file
# Users unzip and install:
pip install -e jira-progress-skill/
```

---

## Next Steps

1. **Test with real data**
   - Run against RHAISTRAT-26 or similar Outcome
   - Verify all sections populate correctly
   - Check PowerPoint slides render properly

2. **Test Claude integration**
   - Copy `claude-skill.md` to `~/.claude/skills/`
   - Ask Claude to generate a report
   - Verify Claude runs the command and reads output

3. **Test Cursor integration**
   - Add `cursorrules.md` to a project
   - Use Cursor Composer to generate a report
   - Verify it works in IDE context

4. **Customize for others**
   - Document how to find custom field IDs
   - Add `--list-fields` command to help users
   - Make project keys configurable via env vars

5. **Publish**
   - Choose distribution method (PyPI, GitHub, zip)
   - Add contributing guidelines
   - Create issue templates

---

## Known Limitations

1. **Jira Cloud vs Data Center**
   - Custom field IDs differ between instances
   - Users must update `CF_*` constants for their instance

2. **Red Hat Specific**
   - IMPLEMENTATION_PROJECTS hardcoded to Red Hat projects
   - Health logic assumes Red Hat Color Status field
   - Slides use Red Hat brand colors

3. **LLM Dependency**
   - Requires Anthropic API key (or other model) for synthesis
   - Can skip with `--no-llm` flag, but loses executive summary

4. **No Custom Field Discovery**
   - User must manually find their custom field IDs
   - TODO: Add `jira-progress --list-fields` command

---

## Success Criteria

✅ Package installs without errors
✅ CLI command works (`jira-progress --help`)
✅ Generates reports matching original Coxswain output
✅ Claude skill enables Claude to run reports
✅ Cursor integration works in IDE
✅ Documentation is clear and complete
✅ Customization points are well-documented

---

## Contact

Package extracted from Coxswain by Jenny Yang Yi (yyi@redhat.com)
Original repo: https://github.com/yangyi/coxswain
