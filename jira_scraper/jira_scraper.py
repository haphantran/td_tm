"""
JIRA Threat Modeling Ticket Scraper
Extracts threat modeling metrics from JIRA tickets for PowerBI dashboard
"""

import os
import time
import asyncio
import pandas as pd
from datetime import datetime
from playwright.async_api import async_playwright
from dotenv import load_dotenv
from bs4 import BeautifulSoup

# Load environment variables
load_dotenv('config/.env')

class JIRAScraper:
    def __init__(self):
        self.jira_url = os.getenv('JIRA_URL')
        self.username = os.getenv('JIRA_USERNAME')
        self.password = os.getenv('JIRA_PASSWORD')
        self.project_key = os.getenv('JIRA_PROJECT_KEY', 'TM')

        self.playwright = None
        self.browser = None
        self.page = None
        self.tickets_data = []

    async def initialize_browser(self, headless=False, use_system_browser=True):
        """Initialize Playwright browser"""
        self.playwright = await async_playwright().start()

        if use_system_browser:
            # Use Chrome/Edge installed on system (no download needed)
            # Try Chrome first, then Edge
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            ]

            browser_path = None
            for path in chrome_paths:
                if os.path.exists(path):
                    browser_path = path
                    print(f"Using browser: {path}")
                    break

            if browser_path:
                self.browser = await self.playwright.chromium.launch(
                    headless=headless,
                    executable_path=browser_path
                )
            else:
                print("No system browser found. Falling back to Playwright Chromium.")
                self.browser = await self.playwright.chromium.launch(headless=headless)
        else:
            self.browser = await self.playwright.chromium.launch(headless=headless)

        self.page = await self.browser.new_page()
        # Set viewport size
        await self.page.set_viewport_size({"width": 1920, "height": 1080})

    async def login(self):
        """Navigate to JIRA and wait for SSO authentication"""
        print(f"Navigating to JIRA: {self.jira_url}")
        await self.page.goto(self.jira_url)

        try:
            # Wait for SSO authentication to complete
            # The page will automatically handle SSO with current user
            print("Waiting for SSO authentication...")

            # Wait for JIRA homepage to load (adjust selector based on your JIRA version)
            # This waits for either the project dropdown or search bar to appear
            await self.page.wait_for_selector(
                'nav[aria-label="Primary"], #quickSearchInput, [data-testid="navigation-apps-sidebar"]',
                timeout=60000  # 60 seconds for SSO
            )

            print("✓ SSO authentication successful!")

        except Exception as e:
            print(f"SSO authentication failed or timed out: {str(e)}")
            print("Please manually complete authentication in the browser window")
            # Wait for user to manually authenticate
            input("Press Enter after you've logged in manually...")
            await self.page.wait_for_load_state("networkidle")

    async def get_ticket_list(self, jql_query=None):
        """Get list of tickets using JQL query"""
        if jql_query is None:
            # Default query for threat modeling tickets
            jql_query = f'project = {self.project_key} ORDER BY created DESC'

        # URL encode the JQL query
        from urllib.parse import quote
        encoded_jql = quote(jql_query)

        # Try multiple URL formats for different JIRA versions
        search_urls = [
            f"{self.jira_url}/projects/{self.project_key}/issues/?jql={encoded_jql}",  # JIRA Cloud
            f"{self.jira_url}/browse/{self.project_key}?jql={encoded_jql}",  # Alternative
            f"{self.jira_url}/secure/IssueNavigator.jspa?jqlQuery={encoded_jql}",  # JIRA Server/Classic
        ]

        print(f"Searching tickets with JQL: {jql_query}")

        # Try each URL format until one works
        ticket_keys = []
        for i, search_url in enumerate(search_urls):
            try:
                print(f"Trying URL format {i+1}: {search_url[:80]}...")
                await self.page.goto(search_url, timeout=15000)
                await self.page.wait_for_load_state("networkidle")

                # Check if we got to a valid page (not 404 or error)
                page_title = await self.page.title()
                if "404" not in page_title and "error" not in page_title.lower():
                    print(f"✓ URL format {i+1} worked!")
                    break
            except Exception as e:
                print(f"  URL format {i+1} failed: {str(e)[:50]}")
                continue

        # Get ticket keys from search results
        ticket_keys = []
        try:
            # Wait for results to load - try multiple selectors for different JIRA versions
            await self.page.wait_for_selector(
                'a[data-testid*="issue-key"], .issue-link-key, [data-issue-key]',
                timeout=10000
            )

            # Extract ticket keys using different selectors
            ticket_elements = await self.page.query_selector_all(
                'a[data-testid*="issue-key"], .issue-link-key, [data-issue-key]'
            )

            for element in ticket_elements:
                # Try to get text content or data attribute
                ticket_key = await element.text_content()
                if not ticket_key:
                    ticket_key = await element.get_attribute('data-issue-key')

                if ticket_key:
                    ticket_key = ticket_key.strip()
                    # Validate format (PROJECT-NUMBER)
                    if '-' in ticket_key and ticket_key not in ticket_keys:
                        ticket_keys.append(ticket_key)

            print(f"Found {len(ticket_keys)} tickets")

        except Exception as e:
            print(f"Error getting ticket list: {str(e)}")

        return ticket_keys

    async def extract_ticket_data(self, ticket_key):
        """Extract data from a single ticket"""
        ticket_url = f"{self.jira_url}/browse/{ticket_key}"
        print(f"Extracting data from {ticket_key}...")

        await self.page.goto(ticket_url)
        await self.page.wait_for_load_state("networkidle")

        try:
            # Wait for ticket to load
            await self.page.wait_for_selector(
                '#summary-val, [data-testid="issue.views.field.rich-text.summary"], h1',
                timeout=10000
            )

            # Get page content
            content = await self.page.content()
            soup = BeautifulSoup(content, 'html.parser')

            # Extract ticket data using multiple strategies
            ticket_data = {
                'ticket_key': ticket_key,
                'summary': await self._extract_field_with_xpath('summary'),
                'status': await self._extract_field_with_xpath('status'),
                'priority': await self._extract_field_with_xpath('priority'),
                'assignee': await self._extract_field_with_xpath('assignee'),
                'reporter': await self._extract_field_with_xpath('reporter'),
                'created': await self._extract_field_with_xpath('created'),
                'updated': await self._extract_field_with_xpath('updated'),
                'resolved': await self._extract_field_with_xpath('resolved'),
                'description': await self._extract_field_with_xpath('description'),
            }

            # Extract custom fields (adjust field names based on your JIRA setup)
            ticket_data.update({
                'application_name': await self._extract_custom_field('Application Name'),
                'application_rating': await self._extract_custom_field('Application Rating'),
                'threat_modeler': await self._extract_custom_field('Threat Modeler'),
                'tm_completion_date': await self._extract_custom_field('TM Completion Date'),
                'num_threats_identified': await self._extract_custom_field('Threats Identified'),
                'num_threats_mitigated': await self._extract_custom_field('Threats Mitigated'),
                'num_open_items': await self._extract_custom_field('Open Items'),
                'pentest_findings': await self._extract_custom_field('Pentest Findings Not Identified'),
            })

            self.tickets_data.append(ticket_data)
            print(f"  ✓ Extracted data from {ticket_key}")

        except Exception as e:
            print(f"  ✗ Error extracting {ticket_key}: {str(e)}")

    async def _extract_field(self, soup, field_name):
        """Helper to extract standard field value using context-aware CSS selectors"""
        try:
            # Context-aware selectors (parent > child) for uniqueness
            # UPDATE THESE with selectors from Chrome DevTools "Copy JS path"
            selectors = {
                'summary': [
                    '#summary-val',
                    '[data-testid*="summary"]',
                    'h1',
                ],
                'status': [
                    '#opsbar-transitions_more > span',  # Your exact selector from Chrome
                    '#opsbar-transitions_more .dropdown-text',  # Alternative
                    '#status-val .dropdown-text',
                    '#status-val',
                    '[data-testid*="status"]',
                ],
                'priority': [
                    '#priority-val .dropdown-text',  # More specific: priority field dropdown only
                    '#priority-val > span > span.dropdown-text',  # Even more specific
                    '#priority-val',
                    '[data-testid*="priority"]',
                ],
                'assignee': [
                    '#assignee-val',
                    '[data-testid*="assignee"]',
                ],
                'reporter': [
                    '#reporter-val',
                    '[data-testid*="reporter"]',
                ],
                'created': [
                    '#created-val',
                    '[data-testid*="created"]',
                ],
                'updated': [
                    '#updated-val',
                    '[data-testid*="updated"]',
                ],
                'resolved': [
                    '#resolved-val',
                    '[data-testid*="resolved"]',
                ],
                'description': [
                    '#description-val',
                    '[data-testid*="description"]',
                ],
            }

            # Try each selector
            for selector in selectors.get(field_name, []):
                element = soup.select_one(selector)
                if element:
                    return element.text.strip()

            return ''
        except:
            return ''

    async def _extract_field_with_xpath(self, field_name):
        """Helper to extract field value using XPath (more reliable)"""
        try:
            # XPath selectors for each field - UPDATE THESE WITH YOUR COPIED XPATHS
            xpaths = {
                'summary': [
                    '//*[@id="summary-val"]',
                    '//h1',
                ],
                'status': [
                    '//*[@id="status-val"]//span[@class="dropdown-text"]',  # UPDATE THIS XPATH
                    '//*[@id="status-val"]',
                ],
                'priority': [
                    '//*[@id="priority-val"]//span[@class="dropdown-text"]',  # UPDATE THIS XPATH
                    '//*[@id="priority-val"]',
                ],
                'assignee': ['//*[@id="assignee-val"]'],
                'reporter': ['//*[@id="reporter-val"]'],
                'created': ['//*[@id="created-val"]'],
                'updated': ['//*[@id="updated-val"]'],
                'resolved': ['//*[@id="resolved-val"]'],
                'description': ['//*[@id="description-val"]'],
            }

            # Try each XPath for this field
            for xpath in xpaths.get(field_name, []):
                try:
                    element = await self.page.query_selector(f'xpath={xpath}')
                    if element:
                        value = await element.text_content()
                        return value.strip() if value else ''
                except:
                    continue

            return ''
        except:
            return ''

    async def _extract_custom_field(self, field_label):
        """Helper to extract custom field value by label using Playwright"""
        try:
            # Try to find the field by label text
            # Different JIRA versions use different structures
            selectors = [
                f'//dt[contains(text(), "{field_label}")]/following-sibling::dd',
                f'//label[contains(text(), "{field_label}")]/following-sibling::*',
                f'//*[contains(text(), "{field_label}")]/ancestor::div[contains(@class, "field")]//div[contains(@class, "value")]',
            ]

            for selector in selectors:
                try:
                    element = await self.page.query_selector(f'xpath={selector}')
                    if element:
                        value = await element.text_content()
                        return value.strip() if value else ''
                except:
                    continue

            return ''
        except:
            return ''

    async def scrape_all_tickets(self, jql_query=None, max_tickets=None, headless=False):
        """Main method to scrape all tickets"""
        try:
            # Initialize browser
            await self.initialize_browser(headless=headless)

            # Login (SSO)
            await self.login()

            # Get ticket list
            ticket_keys = await self.get_ticket_list(jql_query)

            # Limit number of tickets if specified
            if max_tickets:
                ticket_keys = ticket_keys[:max_tickets]

            # Extract data from each ticket
            for i, ticket_key in enumerate(ticket_keys, 1):
                print(f"\nProcessing {i}/{len(ticket_keys)}: {ticket_key}")
                await self.extract_ticket_data(ticket_key)
                await asyncio.sleep(0.5)  # Be respectful to the server

            print(f"\n✓ Scraping completed! Extracted {len(self.tickets_data)} tickets")

        except Exception as e:
            print(f"Error during scraping: {str(e)}")
            raise

    def save_to_csv(self, output_path='data/jira_tickets.csv'):
        """Save extracted data to CSV"""
        if not self.tickets_data:
            print("No data to save!")
            return

        df = pd.DataFrame(self.tickets_data)

        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Save to CSV
        df.to_csv(output_path, index=False)
        print(f"\n✓ Data saved to {output_path}")
        print(f"  Columns: {list(df.columns)}")
        print(f"  Rows: {len(df)}")

        return df

    async def close(self):
        """Close the browser"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        print("Browser closed")


async def main():
    """Main execution function"""
    scraper = JIRAScraper()

    try:
        # Define your JQL query
        # Example: Get all threat modeling tickets from the last 12 months
        jql_query = f"project = TM AND created >= -12w ORDER BY created DESC"

        # Scrape tickets (set max_tickets for testing, None for all)
        # headless=False will show the browser (useful for SSO authentication)
        await scraper.scrape_all_tickets(jql_query=jql_query, max_tickets=3, headless=False)

        # Save to CSV
        scraper.save_to_csv('data/jira_tickets.csv')

    except Exception as e:
        print(f"Scraping failed: {str(e)}")

    finally:
        # Always close the browser
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(main())
