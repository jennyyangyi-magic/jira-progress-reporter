# Jira Progress Reporter

Generate comprehensive progress reports from Jira Outcomes and Features with:
- ✅ Dependency graph traversal
- ✅ Health status analysis (GREEN/YELLOW/RED)
- ✅ Markdown + JSON exports
- ✅ Branded PowerPoint slides

Originally extracted from the [Coxswain](https://github.com/yangyi/coxswain) chief-of-staff AI agent.

## Installation

```bash
pip install jira-progress-reporter
```

## Quick Start

```bash
# Set up credentials
export JIRA_URL="https://issues.redhat.com"
export JIRA_PERSONAL_TOKEN="your-pat-token"

# Or for Jira Cloud:
export JIRA_URL="https://yourcompany.atlassian.net"
export JIRA_USERNAME="your@email.com"
export JIRA_API_TOKEN="your-api-token"

# Generate a report
jira-progress RHAISTRAT-26

# With PowerPoint slides
jira-progress RHAISTRAT-26 --slides
```

## Output

Reports are saved to `progress/` directory:
- `{date}_{issue_key}.md` - Markdown report
- `{date}_{issue_key}.json` - Structured data
- `{date}_{issue_key}.pptx` - PowerPoint slides (if `--slides` flag used)

## Use with Claude Desktop

Copy the skill file to enable Claude to generate reports for you:

```bash
cp claude-skill.md ~/.claude/skills/jira-progress.md
```

Then in Claude:
```
> Generate a progress report for RHAISTRAT-26 with slides
```

## Use with Cursor

Add to your project's `.cursorrules`:

```bash
cat cursorrules.md >> .cursorrules
```

Then in Cursor Composer:
```
> Generate progress report for RHAISTRAT-26
```

## Configuration

### Customizing for Your Jira Instance

Edit these constants in `src/jira_progress/pipeline.py`:

```python
# Your implementation project keys
IMPLEMENTATION_PROJECTS = frozenset({"RHOAIENG", "RHAIENG", "AIPCC", "PSAP"})

# Which link types to traverse
TRAVERSAL_LINK_TYPES = frozenset({"Blocks", "Cloners", "Depend", "Related"})

# Your custom field IDs (find with: jira-progress --list-fields)
CF_COLOR_STATUS = "customfield_12320845"
CF_BLOCKED = "customfield_12316543"
# ... etc
```

### Health Status Logic

**GREEN** = Closed/Done, or In Progress with target release
**YELLOW** = No target release, or New but targeted
**RED** = Blocked, Color Status=Red, or committed but not started

## Architecture

1. **Fetch** - Traverse Jira hierarchy via REST API (no LLM cost)
   - Uses `childIssuesOf()` JQL for parent-child links
   - Follows `issuelinks` for dependencies

2. **Analyze** - Compute health signals from Jira fields
   - Color Status, blocked flags, target releases
   - Status Summary custom field

3. **Report** - Generate structured markdown + JSON
   - Release-grouped STRAT lists
   - Dependency graphs
   - Implementation ticket rollups

4. **Synthesize** - Optional LLM summary (PydanticAI)
   - Executive summary with health assessment
   - Risk identification
   - Recommended actions

5. **Export** - Create branded PowerPoint slides
   - Red Hat brand colors and fonts
   - Overview + per-STRAT detail slides
   - Hyperlinked Jira keys

## License

MIT
