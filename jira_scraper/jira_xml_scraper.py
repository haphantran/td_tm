"""
JIRA XML Scraper - Much simpler than HTML scraping!
Uses JIRA's XML view for clean, structured data extraction
"""

import os
import asyncio
import pandas as pd
import xml.etree.ElementTree as ET
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv('config/.env')


class JIRAXMLScraper:
    def __init__(self):
        self.jira_url = os.getenv('JIRA_URL')
        self.project_key = os.getenv('JIRA_PROJECT_KEY', 'TMHUB')

        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.tickets_data = []

    async def initialize_browser(self, headless=False):
        """Initialize browser"""
        self.playwright = await async_playwright().start()

        # Use system Chrome/Edge
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
            self.browser = await self.playwright.chromium.launch(headless=headless)

        # Create context to maintain session
        self.context = await self.browser.new_context()
        self.page = await self.context.new_page()

    async def login(self):
        """Navigate and wait for SSO authentication"""
        print(f"Navigating to JIRA: {self.jira_url}")
        await self.page.goto(self.jira_url)

        try:
            print("Waiting for SSO authentication...")
            await self.page.wait_for_selector(
                'nav[aria-label="Primary"], #quickSearchInput, [data-testid="navigation-apps-sidebar"]',
                timeout=60000
            )
            print("✓ SSO authentication successful!")
        except Exception as e:
            print(f"SSO timeout: {str(e)}")
            print("Please manually complete authentication...")
            input("Press Enter after login...")

    async def fetch_ticket_xml(self, ticket_key):
        """Fetch XML data for a single ticket"""
        # XML URL format: /si/jira.issueviews:issue-xml/{TICKET-KEY}/{TICKET-KEY}.xml
        xml_url = f"{self.jira_url}/si/jira.issueviews:issue-xml/{ticket_key}/{ticket_key}.xml"

        print(f"Fetching XML: {ticket_key}...")

        try:
            await self.page.goto(xml_url, timeout=15000)
            await self.page.wait_for_load_state("networkidle")

            # Get the XML content
            xml_content = await self.page.content()

            # Parse XML
            root = ET.fromstring(xml_content)

            # Extract data from XML
            ticket_data = self.parse_xml(root, ticket_key)

            if ticket_data:
                self.tickets_data.append(ticket_data)
                print(f"  ✓ Extracted {ticket_key}")
                return ticket_data
            else:
                print(f"  ✗ No data found in XML for {ticket_key}")
                return None

        except Exception as e:
            print(f"  ✗ Error fetching {ticket_key}: {str(e)}")
            return None

    def parse_xml(self, root, ticket_key):
        """Parse JIRA XML and extract all fields"""
        try:
            # Find the item element
            item = root.find('.//item')
            if item is None:
                return None

            # Helper function to get text safely
            def get_text(element, tag, default=''):
                elem = element.find(tag)
                return elem.text if elem is not None and elem.text else default

            # Extract standard fields
            ticket_data = {
                'ticket_key': ticket_key,
                'title': get_text(item, 'title'),
                'summary': get_text(item, 'summary'),
                'description': get_text(item, 'description'),
                'status': get_text(item, 'status'),
                'priority': get_text(item, 'priority'),
                'type': get_text(item, 'type'),
                'assignee': get_text(item, 'assignee'),
                'reporter': get_text(item, 'reporter'),
                'created': get_text(item, 'created'),
                'updated': get_text(item, 'updated'),
                'resolved': get_text(item, 'resolved'),
                'resolution': get_text(item, 'resolution'),
            }

            # Extract custom fields (look for customfields section)
            customfields = item.find('customfields')
            if customfields is not None:
                for customfield in customfields.findall('customfield'):
                    field_name = customfield.find('customfieldname')
                    field_values = customfield.find('customfieldvalues')

                    if field_name is not None and field_values is not None:
                        # Get field name
                        name = field_name.text

                        # Get field value(s)
                        values = []
                        for value in field_values.findall('customfieldvalue'):
                            if value.text:
                                values.append(value.text)

                        # Store in ticket_data (sanitize field name for CSV)
                        if name:
                            field_key = name.lower().replace(' ', '_').replace('-', '_')
                            ticket_data[field_key] = ', '.join(values) if values else ''

            # Extract labels
            labels = item.find('labels')
            if labels is not None:
                label_list = [label.text for label in labels.findall('label') if label.text]
                ticket_data['labels'] = ', '.join(label_list)
            else:
                ticket_data['labels'] = ''

            # Extract components
            components = item.find('components')
            if components is not None:
                component_list = [comp.text for comp in components.findall('component') if comp.text]
                ticket_data['components'] = ', '.join(component_list)
            else:
                ticket_data['components'] = ''

            return ticket_data

        except Exception as e:
            print(f"Error parsing XML: {str(e)}")
            return None

    async def scrape_tickets(self, ticket_keys, headless=False):
        """Scrape multiple tickets by their keys"""
        try:
            # Initialize browser
            await self.initialize_browser(headless=headless)

            # Login
            await self.login()

            # Fetch each ticket
            for i, ticket_key in enumerate(ticket_keys, 1):
                print(f"\nProcessing {i}/{len(ticket_keys)}: {ticket_key}")
                await self.fetch_ticket_xml(ticket_key)
                await asyncio.sleep(0.3)  # Be nice to the server

            print(f"\n✓ Scraping completed! Extracted {len(self.tickets_data)} tickets")

        except Exception as e:
            print(f"Error during scraping: {str(e)}")
            raise

    async def scrape_from_jql(self, jql_query=None, max_tickets=None, headless=False):
        """Scrape tickets using JQL query to get ticket list, then fetch XML for each"""
        try:
            # Initialize browser
            await self.initialize_browser(headless=headless)

            # Login
            await self.login()

            # Get ticket keys from JQL search
            if jql_query is None:
                jql_query = f'project = {self.project_key} ORDER BY created DESC'

            ticket_keys = await self.get_ticket_keys_from_jql(jql_query)

            if max_tickets:
                ticket_keys = ticket_keys[:max_tickets]

            # Fetch XML for each ticket
            for i, ticket_key in enumerate(ticket_keys, 1):
                print(f"\nProcessing {i}/{len(ticket_keys)}: {ticket_key}")
                await self.fetch_ticket_xml(ticket_key)
                await asyncio.sleep(0.3)

            print(f"\n✓ Scraping completed! Extracted {len(self.tickets_data)} tickets")

        except Exception as e:
            print(f"Error during scraping: {str(e)}")
            raise

    async def get_ticket_keys_from_jql(self, jql_query):
        """Get ticket keys from JQL search"""
        from urllib.parse import quote
        encoded_jql = quote(jql_query)

        search_urls = [
            f"{self.jira_url}/issues/?jql={encoded_jql}",
            f"{self.jira_url}/browse/{self.project_key}?jql={encoded_jql}",
            f"{self.jira_url}/secure/IssueNavigator.jspa?jqlQuery={encoded_jql}",
        ]

        print(f"Searching with JQL: {jql_query}")

        ticket_keys = []
        for i, search_url in enumerate(search_urls):
            try:
                print(f"Trying URL format {i+1}...")
                await self.page.goto(search_url, timeout=15000)
                await self.page.wait_for_load_state("networkidle")

                # Extract ticket keys
                ticket_elements = await self.page.query_selector_all(
                    'a[data-testid*="issue-key"], .issue-link-key, [data-issue-key]'
                )

                for element in ticket_elements:
                    ticket_key = await element.text_content()
                    if not ticket_key:
                        ticket_key = await element.get_attribute('data-issue-key')

                    if ticket_key:
                        ticket_key = ticket_key.strip()
                        if '-' in ticket_key and ticket_key not in ticket_keys:
                            ticket_keys.append(ticket_key)

                if ticket_keys:
                    print(f"✓ Found {len(ticket_keys)} tickets")
                    break

            except Exception as e:
                print(f"  URL format {i+1} failed: {str(e)[:50]}")
                continue

        return ticket_keys

    def save_to_csv(self, output_path='data/jira_tickets_xml.csv'):
        """Save extracted data to CSV"""
        if not self.tickets_data:
            print("No data to save!")
            return

        df = pd.DataFrame(self.tickets_data)

        # Create output directory
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Save to CSV
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"\n✓ Data saved to {output_path}")
        print(f"  Columns: {len(df.columns)}")
        print(f"  Rows: {len(df)}")

        return df

    async def close(self):
        """Close browser"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        print("Browser closed")


async def main():
    """Main execution"""
    scraper = JIRAXMLScraper()

    try:
        # Option 1: Scrape specific ticket keys
        ticket_keys = [
            'TMHUB-998',
            # Add more ticket keys...
        ]

        print("=" * 80)
        print("JIRA XML SCRAPER")
        print("=" * 80)

        choice = input("\nChoose method:\n1. Scrape specific ticket keys\n2. Use JQL query\nChoice (1 or 2): ").strip()

        if choice == '1':
            # Manual ticket list
            keys_input = input("\nEnter ticket keys (comma-separated, e.g., TMHUB-998,TMHUB-999): ").strip()
            if keys_input:
                ticket_keys = [k.strip() for k in keys_input.split(',')]

            await scraper.scrape_tickets(ticket_keys, headless=False)

        else:
            # JQL query
            jql = input("\nEnter JQL query (or press Enter for default): ").strip()
            if not jql:
                jql = f'project = TMHUB AND created >= -12M ORDER BY created DESC'

            max_tickets = input("Max tickets to scrape (or press Enter for all): ").strip()
            max_tickets = int(max_tickets) if max_tickets else None

            await scraper.scrape_from_jql(jql_query=jql, max_tickets=max_tickets, headless=False)

        # Save to CSV
        scraper.save_to_csv('data/jira_tickets_xml.csv')

    except Exception as e:
        print(f"Scraping failed: {str(e)}")

    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(main())
