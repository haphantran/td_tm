"""
JIRA XML Scraper - Much simpler than HTML scraping!
Uses JIRA's XML view for clean, structured data extraction
"""

import os
import asyncio
import pandas as pd
import xml.etree.ElementTree as ET
import re
from html import unescape
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

    def parse_html_description(self, html_description):
        """Parse HTML description to extract plain text and specific fields"""
        if not html_description:
            return '', {}

        # First, extract href from <a> tags before removing them (for additional_information)
        additional_info_link = ''
        additional_info_match = re.search(r'Additional\s+Information\s*:\s*<a[^>]+href=["\']([^"\']+)["\']', html_description, re.IGNORECASE)
        if additional_info_match:
            additional_info_link = additional_info_match.group(1)

        # Replace ALL variations of <br> tags with newlines (including those with class, id, etc.)
        cleaned_html = re.sub(r'<br[^>]*>', '\n', html_description, flags=re.IGNORECASE)
        cleaned_html = re.sub(r'<p[^>]*>', '\n', cleaned_html)
        cleaned_html = re.sub(r'</p>', '\n', cleaned_html)
        cleaned_html = re.sub(r'<li[^>]*>', '\n- ', cleaned_html)

        # Remove all other HTML tags
        cleaned_html = re.sub(r'<[^>]+>', '', cleaned_html)

        # Unescape HTML entities
        cleaned_html = unescape(cleaned_html)

        # Now extract fields from the cleaned text (no HTML tags to worry about!)
        extracted_fields = {}

        # Split by newlines to process line by line
        lines = cleaned_html.split('\n')

        # Define field patterns - match field name and capture value on same line
        # Stop at newline or when we see another field name pattern
        field_patterns = {
            'project_manager': r'Project\s+Manager\s*:\s*(.*)',
            'solution_architect': r'Solution\s+Architect\s*:\s*(.*)',
            'biso': r'BISO\s*:\s*(.*)',
            'dcj': r'DCJ\s*:\s*(.*)',
            'internet_facing': r'Internet\s+Facing\s*:\s*(.*)',
            'nda': r'NDA\s*:\s*(.*)',
            'additional_information': r'Additional\s+Information\s*:\s*(.*)',
        }

        # Process each line
        for line in lines:
            line = line.strip()
            if not line:
                continue

            for field_name, pattern in field_patterns.items():
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()

                    # Special handling for additional_information - use extracted link if available
                    if field_name == 'additional_information' and additional_info_link:
                        value = additional_info_link

                    extracted_fields[field_name] = value
                    break  # Move to next line once we've matched a field

        # Ensure all fields exist (even if empty)
        for field_name in field_patterns.keys():
            if field_name not in extracted_fields:
                extracted_fields[field_name] = ''

        # Create plain text version for the description field
        plain_text = cleaned_html.strip()
        # Clean up multiple newlines
        plain_text = re.sub(r'\n\s*\n\s*\n+', '\n\n', plain_text)

        return plain_text, extracted_fields

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

            # Get raw description (may contain HTML)
            raw_description = get_text(item, 'description')

            # Parse description HTML to get plain text and extract specific fields
            description_plain, description_fields = self.parse_html_description(raw_description)

            # Extract standard fields
            ticket_data = {
                'ticket_key': ticket_key,
                'title': get_text(item, 'title'),
                'summary': get_text(item, 'summary'),
                'description': description_plain,
                'description_raw': raw_description,  # Keep original HTML version if needed
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

            # Add extracted fields from description
            ticket_data.update(description_fields)

            # Initialize important custom fields with blank values (ensures they exist in CSV)
            ticket_data['mal_code'] = ''

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

    async def scrape_all_tickets(self, jql_query=None, max_tickets=None, headless=False):
        """Main method to scrape all tickets - same interface as original scraper"""
        try:
            # Initialize browser
            await self.initialize_browser(headless=headless)

            # Login (SSO)
            await self.login()

            # Get ticket list from JQL
            ticket_keys = await self.get_ticket_list(jql_query)

            # Limit number of tickets if specified
            if max_tickets:
                ticket_keys = ticket_keys[:max_tickets]

            # Extract XML data from each ticket
            for i, ticket_key in enumerate(ticket_keys, 1):
                print(f"\nProcessing {i}/{len(ticket_keys)}: {ticket_key}")
                await self.fetch_ticket_xml(ticket_key)
                await asyncio.sleep(0.3)  # Be respectful to the server

            print(f"\n✓ Scraping completed! Extracted {len(self.tickets_data)} tickets")

        except Exception as e:
            print(f"Error during scraping: {str(e)}")
            raise

    async def get_ticket_list(self, jql_query=None):
        """Get list of tickets using JQL query - same as original scraper"""
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
    """Main execution - same interface as original scraper"""
    scraper = JIRAXMLScraper()

    try:
        # Define your JQL query
        # Example: Get all threat modeling tickets from the last 12 months
        jql_query = 'project = TMHUB AND created >= -12M ORDER BY created DESC'

        # Scrape tickets (set max_tickets for testing, None for all)
        # headless=False will show the browser (useful for SSO authentication)
        await scraper.scrape_all_tickets(jql_query=jql_query, max_tickets=3, headless=False)

        # Save to CSV
        scraper.save_to_csv('data/jira_tickets_xml.csv')

    except Exception as e:
        print(f"Scraping failed: {str(e)}")

    finally:
        # Always close the browser
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(main())
