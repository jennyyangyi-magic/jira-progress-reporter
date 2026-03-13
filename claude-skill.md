# Jira Progress Report

Generate comprehensive progress reports for Jira Outcomes and Features with dependency analysis, health status, and PowerPoint slides.

## Installation

The user has installed `jira-progress-reporter`:

```bash
pip install jira-progress-reporter
```

Configuration is in `.env`:
```bash
JIRA_URL=https://issues.redhat.com
JIRA_PERSONAL_TOKEN=xxx
```

Or for Jira Cloud:
```bash
JIRA_URL=https://yourcompany.atlassian.net
JIRA_USERNAME=your@email.com
JIRA_API_TOKEN=xxx
```

## When the User Asks for a Progress Report

### Step 1: Run the Command

Use the Bash tool to execute:

```bash
jira-progress ISSUE-KEY [--slides] [--no-llm]
```

Examples:
- `jira-progress RHAISTRAT-26` - Basic report
- `jira-progress RHAISTRAT-26 --slides` - With PowerPoint
- `jira-progress RHAISTRAT-26 --no-llm` - Skip LLM synthesis (faster, structured only)

### Step 2: Check Output

The tool creates files in the `progress/` directory:
- `{date}_{issue_key}.md` - Markdown report
- `{date}_{issue_key}.json` - Structured data (JSON)
- `{date}_{issue_key}.pptx` - PowerPoint slides (if `--slides` flag used)

### Step 3: Present Results

Use the Read tool to load the markdown file and show it to the user.

For example:
```
Read: progress/2026-03-11_rhaistrat_26.md
```

Then present the report, highlighting:
- Overall health (GREEN/YELLOW/RED counts)
- Blocked or at-risk STRATs
- Release readiness
- Coverage gaps (approved RFEs without STRATs)

### Step 4: Answer Follow-up Questions

The user may ask:
- "Show me the blocked tickets" → Extract from the "Blocked STRATs" section
- "What's targeted for 3.4?" → Parse the "STRATs by Target Release" section
- "Which RFEs are approved but not planned?" → Check "Coverage Gaps" section
- "Export to slides" → Re-run with `--slides` flag

You can also read the JSON file for programmatic analysis:
```
Read: progress/2026-03-11_rhaistrat_26.json
```

## What the Tool Does

1. **Fetch** - Traverses Jira hierarchy from the Outcome/Feature
   - Uses `childIssuesOf()` JQL for parent-child relationships
   - Follows `issuelinks` for dependencies (Blocks, Depends, Related, etc.)
   - Collects STRATs (Features), RFEs (Feature Requests), and implementation tickets

2. **Analyze** - Computes health status from Jira fields
   - **GREEN** = Closed/Done, or In Progress with target release
   - **YELLOW** = No target release, or New but targeted
   - **RED** = Blocked, or Color Status = Red, or committed but not started

3. **Report** - Generates structured markdown
   - Outcome summary with all STRATs
   - Inter-STRAT dependencies
   - Health signals (Color Status, Status Summary, blocked flags)
   - STRATs grouped by target release
   - Implementation ticket rollups by project
   - Coverage gaps (approved RFEs without STRATs)

4. **Synthesize** (if `--no-llm` not used) - LLM generates executive summary
   - Overall health assessment
   - Release readiness (ON TRACK / AT RISK / BLOCKED)
   - Key findings
   - Risks and blockers
   - Recommended actions

5. **Export** - Creates branded PowerPoint slides (if `--slides`)
   - Overview slide with release-grouped STRATs
   - Detail slide per STRAT (health signals, relationships, implementation)
   - Red Hat brand colors and fonts
   - Hyperlinked Jira keys

## Troubleshooting

### If the command fails:

1. **Check credentials**
   ```bash
   # Verify .env exists and has the right values
   cat .env
   ```

2. **Verify the issue exists**
   - The issue key must be a valid Jira Outcome or Feature
   - The user must have read access to the issue

3. **Check for missing dependencies**
   ```bash
   pip list | grep -E "httpx|pydantic|python-pptx"
   ```

4. **Look at the error message**
   - `OutcomeError` = The issue is not an Outcome or Feature
   - `401/403` = Authentication failed
   - `404` = Issue not found

## Customization

The user can customize for their Jira instance by editing the Python package source.

Key configuration constants in `src/jira_progress/pipeline.py`:

```python
# Implementation project keys to track
IMPLEMENTATION_PROJECTS = frozenset({"RHOAIENG", "RHAIENG", "AIPCC", "PSAP"})

# Link types to traverse
TRAVERSAL_LINK_TYPES = frozenset({"Blocks", "Cloners", "Depend", "Related"})

# Custom field IDs (varies by Jira instance)
CF_COLOR_STATUS = "customfield_12320845"
CF_BLOCKED = "customfield_12316543"
CF_TARGET_VERSION = "customfield_12319940"
# ... etc
```

To find custom field IDs for their instance, they can use:
```bash
# This feature is not yet implemented - suggest they check Jira admin
```

## Examples

**User:** "Generate a progress report for RHAISTRAT-26"

**You:**
1. Run: `jira-progress RHAISTRAT-26`
2. Read: `progress/2026-03-11_rhaistrat_26.md`
3. Present the report with summary:
   - "RHAISTRAT-26 has 13 STRATs: 5 GREEN, 6 YELLOW, 2 RED"
   - "2 STRATs are blocked: RHAISTRAT-979 and RHAISTRAT-1045"
   - "Target release 3.4 has 8 STRATs, 3.5 has 2 STRATs, 3 are unplanned"

---

**User:** "Also generate slides for this"

**You:**
1. Run: `jira-progress RHAISTRAT-26 --slides`
2. Confirm: "✓ Slides generated at progress/2026-03-11_rhaistrat_26.pptx"

---

**User:** "Show me which tickets are blocked"

**You:**
1. Parse the markdown you already read
2. Extract the "Blocked STRATs" section
3. Present: "2 blocked STRATs: RHAISTRAT-979 (dependency on upstream), RHAISTRAT-1045 (waiting for API approval)"

---

**User:** "What's the status of the 3.4 release?"

**You:**
1. Parse the "STRATs by Target Release → 3.4" section
2. Summarize: "3.4 has 8 STRATs: 4 In Progress (GREEN), 2 New but targeted (YELLOW), 1 blocked (RED), 1 Closed (GREEN)"
