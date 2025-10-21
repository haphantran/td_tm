# JIRA Threat Modeling Ticket Scraper

Automated web scraper to extract threat modeling metrics from JIRA tickets using Playwright for PowerBI dashboard.

## Features

- **SSO Authentication**: Automatically handles SSO login with your current user session
- **Playwright-based**: Modern, reliable browser automation
- **JQL Support**: Flexible ticket filtering using JIRA Query Language
- **CSV Export**: Exports data in CSV format for PowerBI integration
- **Custom Fields**: Extracts both standard and custom JIRA fields
- **Progress Tracking**: Real-time progress updates during scraping

## Project Structure

```
jira_scraper/
├── jira_scraper.py          # Main scraper script
├── requirements.txt          # Python dependencies
├── config/
│   └── .env.example         # Configuration template
└── data/
    └── jira_tickets.csv     # Output file (generated)
```

## Setup

### 1. Install Python Dependencies

```bash
cd jira_scraper
pip install -r requirements.txt
```

### 2. Install Playwright Browsers

```bash
playwright install chromium
```

### 3. Configure JIRA Settings

Copy the example configuration:
```bash
cp config/.env.example config/.env
```

Edit `config/.env` with your JIRA details:
```env
JIRA_URL=https://your-company.atlassian.net
JIRA_USERNAME=your.email@company.com
JIRA_PASSWORD=your-password-or-api-token
JIRA_PROJECT_KEY=TM
```

**Note**: For SSO authentication, the username/password may not be needed. The scraper will open a browser window and use your existing session.

## Usage

### Basic Usage

Run the scraper with default settings:
```bash
python jira_scraper.py
```

### Customize in Code

Edit the `main()` function in [jira_scraper.py](jira_scraper.py) to customize:

```python
async def main():
    scraper = JIRAScraper()

    try:
        # Customize your JQL query
        jql_query = 'project = TM AND created >= -12M ORDER BY created DESC'

        # Scrape tickets
        # max_tickets: Limit number of tickets (None for all)
        # headless: Run browser in background (False to see browser)
        await scraper.scrape_all_tickets(
            jql_query=jql_query,
            max_tickets=50,  # Set to None for all tickets
            headless=False   # Set to True to hide browser
        )

        # Save to CSV
        scraper.save_to_csv('data/jira_tickets.csv')

    finally:
        await scraper.close()
```

### JQL Query Examples

```python
# All threat modeling tickets from last 12 months
jql_query = 'project = TM AND created >= -12M ORDER BY created DESC'

# High priority tickets only
jql_query = 'project = TM AND priority = High ORDER BY created DESC'

# Completed tickets
jql_query = 'project = TM AND status = Completed ORDER BY created DESC'

# Specific assignee
jql_query = 'project = TM AND assignee = "john.doe@company.com"'

# Multiple conditions
jql_query = 'project = TM AND status != Completed AND created >= -6M'
```

## Extracted Fields

### Standard Fields
- Ticket Key
- Summary
- Status
- Priority
- Assignee
- Reporter
- Created Date
- Updated Date
- Resolved Date
- Description

### Custom Fields (Threat Modeling)
- Application Name
- Application Rating (VH/H/M/L)
- Threat Modeler
- TM Completion Date
- Number of Threats Identified
- Number of Threats Mitigated
- Number of Open Items
- Penetration Testing Findings Not Identified

## Output

The scraper generates `data/jira_tickets.csv` with all extracted data:

```csv
ticket_key,summary,status,priority,assignee,...
TM-1001,Threat Model for App X,Completed,High,john.doe@company.com,...
TM-1002,Threat Model for App Y,In Progress,Very High,jane.smith@company.com,...
```

## Troubleshooting

### SSO Authentication Issues

If SSO authentication fails:
1. The script will prompt you to manually log in
2. Complete authentication in the browser window
3. Press Enter when logged in successfully

### Missing Fields

If custom fields are not extracted:
1. Inspect the JIRA ticket page in your browser
2. Identify the correct field labels
3. Update the field names in [jira_scraper.py:143-151](jira_scraper.py#L143-L151)

### Selectors Not Working

Different JIRA versions use different HTML structures. If data extraction fails:
1. Set `headless=False` to see the browser
2. Inspect the page elements using browser DevTools
3. Update selectors in `_extract_field()` method

## Performance Tips

- Use `max_tickets` parameter for testing
- Set `headless=True` for faster scraping
- Adjust `await asyncio.sleep(0.5)` to control scraping speed
- Use specific JQL queries to limit results

## Security Notes

- **Never commit** your `.env` file with real credentials
- The `.env` file is git-ignored by default
- For API token instead of password, generate one in JIRA settings
- SSO is the recommended authentication method

## Next Steps

After scraping data:
1. Review the CSV output in `data/jira_tickets.csv`
2. Import into PowerBI for dashboard creation
3. Set up scheduled runs using cron/Task Scheduler
4. Validate data quality and field mappings

## Support

For issues with:
- **Playwright**: https://playwright.dev/python/docs/intro
- **JIRA REST API**: https://developer.atlassian.com/cloud/jira/platform/rest/v3/
- **JQL**: https://www.atlassian.com/software/jira/guides/expand-jira/jql
