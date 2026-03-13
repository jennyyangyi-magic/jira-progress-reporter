# Installation Guide

## Quick Install

```bash
cd jira-progress-skill
pip install -e .
```

## Setup

1. **Copy environment template:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with your credentials:**
   ```bash
   # For Red Hat Jira Data Center:
   JIRA_URL=https://issues.redhat.com
   JIRA_PERSONAL_TOKEN=your-token-here

   # Or for Jira Cloud:
   JIRA_URL=https://yourcompany.atlassian.net
   JIRA_USERNAME=your@email.com
   JIRA_API_TOKEN=your-api-token
   ```

3. **Test the installation:**
   ```bash
   jira-progress --help
   ```

## Use with Claude Desktop

```bash
# Copy the skill file
cp claude-skill.md ~/.claude/skills/jira-progress.md

# Restart Claude Desktop (if running)

# Use it:
# Open Claude and ask: "Generate a progress report for RHAISTRAT-26"
```

## Use with Cursor

```bash
# Add to your project's .cursorrules
cat cursorrules.md >> /path/to/your/project/.cursorrules

# Or copy as a template:
cp cursorrules.md /path/to/your/project/.cursorrules

# Use it:
# In Cursor Composer: "Generate progress report for RHAISTRAT-26"
```

## Verify Installation

```bash
# Check the package is installed
pip show jira-progress-reporter

# Run a test (requires valid Jira credentials)
jira-progress RHAISTRAT-26
```

## Customization

To customize for your Jira instance, edit:

**Implementation projects** (which tickets to track):
```python
# src/jira_progress/pipeline.py, line 26
IMPLEMENTATION_PROJECTS = frozenset({"RHOAIENG", "RHAIENG", "AIPCC", "PSAP"})
```

**Link types** (which relationships to follow):
```python
# src/jira_progress/pipeline.py, line 28
TRAVERSAL_LINK_TYPES = frozenset({"Blocks", "Cloners", "Depend", "Related"})
```

**Custom field IDs** (varies by Jira instance):
```python
# src/jira_progress/pipeline.py, lines 39-44
CF_COLOR_STATUS = "customfield_12320845"
CF_BLOCKED = "customfield_12316543"
CF_BLOCKED_REASON = "customfield_12316544"
CF_PARENT_LINK = "customfield_12313140"
CF_TARGET_VERSION = "customfield_12319940"
CF_STATUS_SUMMARY = "customfield_12320841"
```

After editing, reinstall:
```bash
pip install -e .
```

## Troubleshooting

### Import Errors

If you see import errors after installation:
```bash
# Make sure you're in the package directory
cd jira-progress-skill

# Reinstall in editable mode
pip install -e .
```

### Authentication Errors

If you get 401/403 errors:
```bash
# Check your .env file exists
cat .env

# Verify the credentials are correct
# For Data Center: test your Personal Access Token in Jira UI
# For Cloud: verify API token is not expired
```

### Missing Dependencies

If you see "ModuleNotFoundError":
```bash
# Install dependencies manually
pip install httpx pydantic pydantic-ai python-pptx
```

## Uninstall

```bash
pip uninstall jira-progress-reporter

# Remove Claude skill
rm ~/.claude/skills/jira-progress.md

# Remove Cursor rules (manual - edit .cursorrules)
```
