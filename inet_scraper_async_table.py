#!/usr/bin/env python3
"""
Async INET scraper with cookie persistence
This version uses aiohttp for asynchronous HTTP requests
"""

import aiohttp
from bs4 import BeautifulSoup
import asyncio
import os
import pickle
from urllib.parse import urljoin
from typing import Optional
import sys
import ssl


class WebScraperAsync:
    """An async web scraper using aiohttp and BeautifulSoup."""
    
    def __init__(self, cookie_file: str = "cookies.pkl"):
        """Initialize the scraper with cookie persistence."""
        self.session: Optional[aiohttp.ClientSession] = None
        self.current_url: Optional[str] = None
        self.current_response: Optional[str] = None
        self.cookie_file = cookie_file
        self.cookies = {}
        
        # Load existing cookies if they exist
        self.load_cookies()
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.create_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def create_session(self):
        """Create the aiohttp session with proper configuration."""
        if self.session is None or self.session.closed:
            # Create SSL context that doesn't verify certificates
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # Create connector with SSL context
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            
            # Set up headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            # Create cookie jar from loaded cookies
            cookie_jar = aiohttp.CookieJar()
            if self.cookies:
                # Convert our simple dict to cookies
                for name, value in self.cookies.items():
                    cookie_jar.update_cookies({name: value})
            
            self.session = aiohttp.ClientSession(
                headers=headers,
                connector=connector,
                cookie_jar=cookie_jar
            )
            
            # Add AWS load balancer cookies for inet.indsci.com
            self.add_cookie(
                "AWSALB", 
                "lO9Hx450KJM1R9A3hpoGvXvEKzx2H90bLYmykxwR1OoQhSG97IrvBUjeBHMyy9Ab48bP3Ko1sBbEkt1LO3ZnALGvuOYskuAXtTjUSCSzqpZO4G50nsU5iazAXeOM"
            )
            self.add_cookie(
                "AWSALBCORS", 
                "lO9Hx450KJM1R9A3hpoGvXvEKzx2H90bLYmykxwR1OoQhSG97IrvBUjeBHMyy9Ab48bP3Ko1sBbEkt1LO3ZnALGvuOYskuAXtTjUSCSzqpZO4G50nsU5iazAXeOM"
            )
    
    def load_cookies(self):
        """Load cookies from file if it exists."""
        try:
            if os.path.exists(self.cookie_file):
                with open(self.cookie_file, 'rb') as f:
                    self.cookies = pickle.load(f)
                print(f"Loaded cookies from {self.cookie_file}")
            else:
                print(f"No existing cookie file found at {self.cookie_file}")
        except Exception as e:
            print(f"Error loading cookies: {e}")
    
    def save_cookies(self):
        """Save current cookies to file."""
        try:
            if self.session:
                # Convert cookies to a simple dict
                cookie_dict = {}
                for cookie in self.session.cookie_jar:
                    cookie_dict[cookie.key] = cookie.value
                with open(self.cookie_file, 'wb') as f:
                    pickle.dump(cookie_dict, f)
                print(f"Saved cookies to {self.cookie_file}")
        except Exception as e:
            print(f"Error saving cookies: {e}")
    
    def clear_cookies(self):
        """Clear all cookies and delete the cookie file."""
        self.cookies = {}
        if self.session:
            self.session.cookie_jar.clear()
        try:
            if os.path.exists(self.cookie_file):
                os.remove(self.cookie_file)
                print(f"Cleared cookies and deleted {self.cookie_file}")
        except Exception as e:
            print(f"Error clearing cookies: {e}")
    
    def add_cookie(self, name: str, value: str, domain: str = None, path: str = "/"):
        """
        Add a cookie to the session.
        
        Args:
            name: Cookie name
            value: Cookie value
            domain: Cookie domain (optional)
            path: Cookie path (default: "/")
        """
        # Add to internal cookies dict
        self.cookies[name] = value
        
        # Add to session if it exists
        if self.session and not self.session.closed:
            from http.cookies import SimpleCookie
            cookie = SimpleCookie()
            cookie[name] = value
            if domain:
                cookie[name]['domain'] = domain
            cookie[name]['path'] = path
            self.session.cookie_jar.update_cookies({name: value})
            print(f"Added cookie: {name}")
    
    def add_cookies(self, cookies: dict):
        """
        Add multiple cookies to the session.
        
        Args:
            cookies: Dictionary of cookie name-value pairs
        """
        for name, value in cookies.items():
            self.add_cookie(name, value)
    
    def get_cookies(self) -> dict:
        """
        Get all current cookies as a dictionary.
        
        Returns:
            Dictionary of cookie name-value pairs
        """
        if self.session and not self.session.closed:
            cookie_dict = {}
            for cookie in self.session.cookie_jar:
                cookie_dict[cookie.key] = cookie.value
            return cookie_dict
        return self.cookies.copy()
    
    async def login(self, 
                   login_url: str, 
                   username_field: str, 
                   username_value: str, 
                   password_field: str, 
                   password_value: str, 
                   submit_button: Optional[str] = None) -> bool:
        """
        Log into a website using the provided credentials.
        
        Args:
            login_url: URL of the login page
            username_field: Name or id of the username field
            username_value: Username to use for login
            password_field: Name or id of the password field
            password_value: Password to use for login
            submit_button: Name or id of the submit button (optional)
            
        Returns:
            bool: True if login was successful, False otherwise
        """
        try:
            await self.create_session()
            
            # First, get the login page to extract form data
            print(f"Opening login page: {login_url}")
            async with self.session.get(login_url, timeout=30) as response:
                response.raise_for_status()
                html_content = await response.text()
            
            # Parse the HTML to find the form
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find the login form
            form = soup.find('form')
            if not form:
                print("Error: No form found on the login page")
                return False
            
            # Extract form action and method
            form_action = form.get('action', '')
            form_method = form.get('method', 'post').lower()
            
            # Build the full URL for form submission
            if form_action.startswith('http'):
                submit_url = form_action
            else:
                submit_url = urljoin(login_url, form_action)
            
            # Prepare form data
            form_data = {}
            
            # Add all hidden fields from the form
            for hidden_input in form.find_all('input', type='hidden'):
                name = hidden_input.get('name')
                value = hidden_input.get('value', '')
                if name:
                    form_data[name] = value
            
            # Add username and password
            form_data[username_field] = username_value
            form_data[password_field] = password_value
            
            # Add submit button if specified
            if submit_button:
                form_data[submit_button] = submit_button
            
            print(f"Filling username field '{username_field}' with '{username_value}'")
            print(f"Filling password field '{password_field}'")
            print(f"Submitting form to: {submit_url}")
            
            # Submit the form
            if form_method == 'get':
                async with self.session.get(submit_url, params=form_data, timeout=30) as response:
                    response.raise_for_status()
                    self.current_response = await response.text()
                    self.current_url = str(response.url)
            else:
                async with self.session.post(submit_url, data=form_data, timeout=30) as response:
                    response.raise_for_status()
                    self.current_response = await response.text()
                    self.current_url = str(response.url)
            
            print(f"Login response URL: {self.current_url}")
            
            # Basic check: if we're still on the login page, login probably failed
            if login_url in self.current_url or 'login' in self.current_url.lower():
                print("Warning: Still on login page - login may have failed")
                return False
            
            print("Login appears successful!")
            # Save cookies after successful login
            self.save_cookies()
            return True
            
        except aiohttp.ClientError as e:
            print(f"Network error during login: {str(e)}")
            return False
        except Exception as e:
            print(f"Error during login: {str(e)}")
            return False
    
    async def save_page(self, 
                       filename: str, 
                       url: Optional[str] = None, 
                       encoding: str = 'utf-8') -> bool:
        """
        Save the current page or a specific URL to a file.
        
        Args:
            filename: Name of the file to save to
            url: URL to save (if None, saves current page)
            encoding: Text encoding to use
            
        Returns:
            bool: True if save was successful, False otherwise
        """
        try:
            await self.create_session()
            
            # If URL is provided, navigate to it first
            if url:
                print(f"Navigating to: {url}")
                async with self.session.get(url, timeout=30) as response:
                    response.raise_for_status()
                    page_content = await response.text()
                    self.current_response = page_content
                    self.current_url = url
            elif not self.current_response:
                print("Error: No current page to save")
                return False
            else:
                page_content = self.current_response
            
            # Save to file
            with open(filename, 'w', encoding=encoding) as f:
                f.write(page_content)
            
            print(f"Page saved successfully to: {filename}")
            return True
            
        except Exception as e:
            print(f"Error saving page: {str(e)}")
            return False
    
    def get_current_url(self) -> str:
        """Get the current URL."""
        return self.current_url or "No URL available"
    
    def get_page_title(self) -> str:
        """Get the title of the current page."""
        try:
            if self.current_response:
                soup = BeautifulSoup(self.current_response, 'html.parser')
                title_tag = soup.find('title')
                return title_tag.get_text().strip() if title_tag else "No title available"
            return "No page loaded"
        except:
            return "No title available"
    
    def get_page_content(self) -> str:
        """Get the raw HTML content of the current page."""
        if self.current_response:
            return self.current_response
        return ""
    
    async def close(self):
        """Close the session and save cookies."""
        self.save_cookies()
        if self.session and not self.session.closed:
            await self.session.close()


async def check_if_logged_in(scraper: WebScraperAsync) -> bool:
    """Check if we're already logged in by trying to access a protected page."""
    try:
        await scraper.create_session()
        
        # Try to access the dashboard - if we're logged in, this should work
        test_url = "https://inet.indsci.com/Dashboard/LandingPage.aspx"
        async with scraper.session.get(test_url, timeout=30) as response:
            # Check if we're redirected to login page or if we get the dashboard
            if 'login' in str(response.url).lower() or 'Login.aspx' in str(response.url):
                print("Not logged in - cookies expired or invalid")
                return False
            else:
                print("Already logged in via saved cookies!")
                return True
            
    except Exception as e:
        print(f"Error checking login status: {e}")
        return False


async def inet_login_and_save():
    """Login to INET and save pages using cookie persistence."""
    
    # Initialize the scraper with cookie persistence
    async with WebScraperAsync(cookie_file="inet_cookies.pkl") as scraper:
        try:
            print("INET Login Scraper with Cookie Persistence (Async Version)")
            print("=" * 50)
            
            # Check if we're already logged in
            if await check_if_logged_in(scraper):
                print("Using existing session - skipping login")
                # Set the current response by fetching the dashboard page
                dashboard_url = "https://inet.indsci.com/Dashboard/LandingPage.aspx"
                async with scraper.session.get(dashboard_url, timeout=30) as response:
                    scraper.current_response = await response.text()
                    scraper.current_url = dashboard_url
            else:
                # Need to login
                print("Performing fresh login...")
                
                # INET login details with CORRECTED field names
                login_url = "https://inet.indsci.com/Login.aspx"
                username_field = "ctl00$cph1$main$Login1$UserName"  # Corrected: uses $ not _
                username_value = "jporcelli"
                password_field = "ctl00$cph1$main$Login1$Password"  # Corrected: uses $ not _
                password_value = "qR2gKQ!Ub!qbRaOhMizuBzAfE1ZebPrgbGCL^C#SRiV*5hVky%&frcozcUqI!yn0Iay3F$iAI!WUNku06rb#U7KA%IPEN^XtFXW"
                submit_button = "ctl00$cph1$main$Login1$LoginButton"  # Corrected: uses $ not _
                
                print(f"Attempting to login to: {login_url}")
                print(f"Username: {username_value}")
                
                # Attempt login
                if not await scraper.login(login_url, username_field, username_value, 
                                          password_field, password_value, submit_button):
                    print("Login failed! Let's save the login page for debugging...")
                    await scraper.save_page("inet_login_debug.html", login_url)
                    print("Login page saved to inet_login_debug.html for inspection")
                    return
            
            print(f"\nSession established!")
            print(f"Current URL: {scraper.get_current_url()}")
            print(f"Page title: {scraper.get_page_title()}")
            
            # Save the current page (dashboard landing page)
            filename = "inet_logged_in_page.html"
            if await scraper.save_page(filename):
                print(f"Dashboard landing page saved to {filename}")
            
            # Navigate to and save the Equipment List page
            equipment_list_url = "https://inet.indsci.com/Dashboard/EquipmentList.aspx"
            print(f"\nNavigating to Equipment List: {equipment_list_url}")
            
            if await scraper.save_page("inet_equipment_list.html", equipment_list_url):
                print("Equipment List page saved to inet_equipment_list.html")
            else:
                print("Failed to save Equipment List page")
            
            # Try to save some other common pages
            common_pages = [
                "https://inet.indsci.com/Default.aspx",
                "https://inet.indsci.com/Home.aspx", 
                "https://inet.indsci.com/Dashboard.aspx"
            ]
            
            for page_url in common_pages:
                try:
                    page_name = page_url.split('/')[-1].replace('.aspx', '')
                    filename = f"inet_{page_name}.html"
                    if await scraper.save_page(filename, page_url):
                        print(f"Saved {page_name} to {filename}")
                except Exception as e:
                    print(f"Could not save {page_url}: {e}")
        
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
        except Exception as e:
            print(f"An error occurred: {str(e)}")


async def scrape_table(url: str, table_id: str = "ctl00_ctl00_ctl00_cph1_main_dr_Grid_DXMainTable") -> list:
    """
    Scrape a table from a URL after ensuring login.
    
    Args:
        url: The URL to scrape
        table_id: The HTML id of the table to scrape
        
    Returns:
        List of dictionaries, where each dict represents a row with header names as keys
    """
    async with WebScraperAsync(cookie_file="inet_cookies.pkl") as scraper:
        try:
            # Check if we're already logged in
            if not await check_if_logged_in(scraper):
                print("Not logged in, performing login...")
                
                # INET login details
                login_url = "https://inet.indsci.com/Login.aspx"
                username_field = "ctl00$cph1$main$Login1$UserName"
                username_value = "jporcelli"
                password_field = "ctl00$cph1$main$Login1$Password"
                password_value = "qR2gKQ!Ub!qbRaOhMizuBzAfE1ZebPrgbGCL^C#SRiV*5hVky%&frcozcUqI!yn0Iay3F$iAI!WUNku06rb#U7KA%IPEN^XtFXW"
                submit_button = "ctl00$cph1$main$Login1$LoginButton"
                
                if not await scraper.login(login_url, username_field, username_value, 
                                          password_field, password_value, submit_button):
                    print("Login failed!")
                    return []
            
            # Fetch the page
            print(f"Fetching page: {url}")
            await scraper.create_session()
            async with scraper.session.get(url, timeout=30) as response:
                response.raise_for_status()
                html_content = await response.text()
            
            # Parse the HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find the table
            table = soup.find('table', id=table_id)
            if not table:
                print(f"Table with id '{table_id}' not found")
                return []
            
            # Find the header row (DevExpress uses DXHeadersRow0 pattern)
            header_row = table.find('tr', id=lambda x: x and 'DXHeadersRow0' in x)
            if not header_row:
                print("Header row not found")
                return []
            
            # Extract header names
            # In DevExpress, header cells are direct children TDs with class dxgvHeader_Moderno
            headers = []
            header_cells = header_row.find_all('td', class_='dxgvHeader_Moderno', recursive=False)
            for header_cell in header_cells:
                # Each header cell contains a nested table
                # We need to get the text from the first cell of the first row of that table
                nested_table = header_cell.find('table')
                if nested_table:
                    first_row = nested_table.find('tr')
                    if first_row:
                        first_cell = first_row.find('td')
                        if first_cell:
                            header_text = first_cell.get_text(strip=True)
                            # Only add non-empty headers
                            if header_text:
                                headers.append(header_text)
                            else:
                                headers.append("")  # Keep position for empty headers
                        else:
                            headers.append("")
                    else:
                        headers.append("")
                else:
                    # Fallback if no nested table - get direct text
                    header_text = header_cell.get_text(strip=True)
                    if header_text:
                        headers.append(header_text)
                    else:
                        headers.append("")
            
            print(f"Found {len(headers)} columns: {headers}")
            
            # Find all data rows
            data_rows = table.find_all('tr', id=lambda x: x and 'DXDataRow' in x)
            print(f"Found {len(data_rows)} data rows")
            
            # Extract data
            results = []
            for row in data_rows:
                cells = row.find_all('td')
                if len(cells) == len(headers):
                    row_data = {}
                    for i, cell in enumerate(cells):
                        # Get text content, handling nested elements
                        cell_text = cell.get_text(strip=True)
                        row_data[headers[i]] = cell_text
                    results.append(row_data)
            
            print(f"Successfully extracted {len(results)} rows")
            return results
            
        except Exception as e:
            print(f"Error scraping table: {str(e)}")
            return []


async def scrape_equipment_list():
    """Scrape the equipment list table and display results."""
    equipment_list_url = "https://inet.indsci.com/Dashboard/EquipmentList.aspx"
    
    print("INET Equipment List Scraper (Async Version)")
    print("=" * 50)
    
    results = await scrape_table(equipment_list_url)
    
    if results:
        print(f"\nExtracted {len(results)} equipment records:")
        print("-" * 50)
        
        # Display first few rows as example
        for i, row in enumerate(results[:3], 1):
            print(f"\nRow {i}:")
            for key, value in row.items():
                if value:  # Only show non-empty values
                    print(f"  {key}: {value}")
        
        if len(results) > 3:
            print(f"\n... and {len(results) - 3} more rows")
    else:
        print("No data extracted")
    
    return results


async def clear_cookies_async():
    """Clear saved cookies and force fresh login."""
    async with WebScraperAsync(cookie_file="inet_cookies.pkl") as scraper:
        scraper.clear_cookies()
        print("Cookies cleared. Next run will require fresh login.")


def main():
    """Main entry point that runs the async code."""
    if len(sys.argv) > 1 and sys.argv[1] == "clear-cookies":
        asyncio.run(clear_cookies_async())
    elif len(sys.argv) > 1 and sys.argv[1] == "scrape-table":
        asyncio.run(scrape_equipment_list())
    else:
        asyncio.run(inet_login_and_save())


if __name__ == "__main__":
    main()

