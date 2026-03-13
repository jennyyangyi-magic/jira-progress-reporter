# Jira Progress Reporter

The user has `jira-progress-reporter` installed for generating Jira progress reports.

## Configuration

Reads from `.env`:
```
JIRA_URL=https://issues.redhat.com
JIRA_PERSONAL_TOKEN=xxx
```

Or for Jira Cloud:
```
JIRA_URL=https://yourcompany.atlassian.net
JIRA_USERNAME=your@email.com
JIRA_API_TOKEN=xxx
```

## Usage

When the user asks for a Jira progress report, run in terminal:

```bash
jira-progress ISSUE-KEY [--slides] [--no-llm]
```

Examples:
- `jira-progress RHAISTRAT-26` - Generate report with LLM synthesis
- `jira-progress RHAISTRAT-26 --slides` - Also create PowerPoint slides
- `jira-progress RHAISTRAT-26 --no-llm` - Skip LLM synthesis (faster)

## Output

Reports are saved to `progress/` directory:
- `{date}_{issue_key}.md` - Markdown report
- `{date}_{issue_key}.json` - Structured JSON data
- `{date}_{issue_key}.pptx` - PowerPoint slides (if `--slides` used)

## What It Does

1. Traverses Jira hierarchy from Outcome/Feature to collect:
   - Child Features (STRATs)
   - RFE precursors
   - Implementation tickets (RHOAIENG, etc.)

2. Analyzes health status:
   - GREEN = On track
   - YELLOW = At risk or missing target
   - RED = Blocked or critical issues

3. Generates:
   - Structured markdown report
   - Dependency graph
   - Release-grouped STRAT lists
   - Executive summary (via LLM, unless `--no-llm`)
   - Branded PowerPoint slides (if `--slides`)

## Examples

User: "Generate progress report for RHAISTRAT-26"
→ Run: `jira-progress RHAISTRAT-26`
→ Read and present: `progress/2026-03-11_rhaistrat_26.md`

User: "Show me blocked tickets"
→ Parse the markdown, extract "Blocked STRATs" section

User: "Export to PowerPoint"
→ Run: `jira-progress RHAISTRAT-26 --slides`
