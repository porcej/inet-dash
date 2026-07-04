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
import re
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode
from typing import Optional, Tuple, Dict
import sys
import ssl


INET_LOGIN_URL = "https://inet.indsci.com/Login.aspx"
SECUREAUTH_HOST = "secureauth.com"


def _decode_js_uri_path(encoded_path: str) -> str:
    """Decode SecureAuth fingerprint redirect paths embedded in JavaScript."""
    return encoded_path.replace("\\/", "/").replace("\\u0026", "&")


def _is_dbfp_page(html: str) -> bool:
    return "SecureAuth.getFingerprint" in html and "redirectURL = new URL" in html


def _build_dbfp_redirect_url(html: str, base_url: str) -> Optional[str]:
    """Build the dbfp=success redirect URL from a fingerprint loader page."""
    match = re.search(r'redirectURL = new URL\(decodeURI\("([^"]+)"', html)
    if not match:
        return None

    base = urlparse(base_url)
    path = _decode_js_uri_path(match.group(1))
    redirect_url = urlunparse((base.scheme, base.netloc, path, "", "", ""))
    parts = urlparse(redirect_url)
    query = dict(parse_qsl(parts.query))
    query["dbfp"] = "success"
    query["duration"] = "100"
    return urlunparse((parts.scheme, parts.netloc, parts.path, parts.params, urlencode(query), parts.fragment))


def _parse_auto_submit_form(html: str) -> Optional[Tuple[str, Dict[str, str]]]:
    """Parse OAuth callback pages that auto-post hidden fields to INET."""
    soup = BeautifulSoup(html, "html.parser")
    form = soup.find("form", method=re.compile("^post$", re.I))
    if not form:
        return None

    action = form.get("action", "")
    if not action:
        return None

    fields = {}
    for hidden_input in form.find_all("input", type="hidden"):
        name = hidden_input.get("name")
        if name:
            fields[name] = hidden_input.get("value", "")

    if "code" not in fields:
        return None

    return action, fields


def _is_login_page(html: str, url: str) -> bool:
    """Return True when the response is still an authentication page."""
    if SECUREAUTH_HOST in url.lower():
        return True

    soup = BeautifulSoup(html, "html.parser")
    title = soup.find("title")
    title_text = title.get_text(strip=True).lower() if title else ""
    if title_text in {"log in", "login"}:
        return True

    return "Login.aspx" in url or "/login" in url.lower()


class WebScraperAsync:
    """An async web scraper using aiohttp and BeautifulSoup."""
    
    def __init__(self, 
                 cookie_file: str = "cookies.pkl",
                 username: Optional[str] = None,
                 password: Optional[str] = None,
                 login_url: Optional[str] = None,
                 username_field: Optional[str] = None,
                 password_field: Optional[str] = None,
                 submit_button: Optional[str] = None):
        """
        Initialize the scraper with cookie persistence.
        
        Args:
            cookie_file: Path to file for storing cookies
            username: Username for login (optional)
            password: Password for login (optional)
            login_url: URL of the login page (optional)
            username_field: Name or id of the username field (optional)
            password_field: Name or id of the password field (optional)
            submit_button: Name or id of the submit button (optional)
        """
        self.session: Optional[aiohttp.ClientSession] = None
        self.current_url: Optional[str] = None
        self.current_response: Optional[str] = None
        self.cookie_file = cookie_file
        self.cookies = {}
        
        # Store login credentials
        self.username = username
        self.password = password
        self.login_url = login_url
        self.username_field = username_field
        self.password_field = password_field
        self.submit_button = submit_button
        
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
    
    async def _fetch_through_dbfp(self, url: str) -> Tuple[str, str]:
        """Follow SecureAuth browser-fingerprint redirects until a real page loads."""
        current_url = url
        html = ""

        for _ in range(5):
            async with self.session.get(current_url, allow_redirects=True, timeout=30) as response:
                response.raise_for_status()
                html = await response.text()
                current_url = str(response.url)

            if not _is_dbfp_page(html):
                break

            next_url = _build_dbfp_redirect_url(html, current_url)
            if not next_url:
                break
            current_url = next_url

        return html, current_url

    async def _submit_oauth_callback(self, html: str) -> Tuple[str, str]:
        """Submit the OAuth authorization code back to INET."""
        parsed_form = _parse_auto_submit_form(html)
        if not parsed_form:
            return html, self.current_url or ""

        action, fields = parsed_form
        if action.startswith("./") or action.startswith("../"):
            return html, self.current_url or ""

        if not action.startswith("http"):
            action = urljoin(self.current_url or INET_LOGIN_URL, action)

        print(f"Completing OAuth callback to: {action}")
        async with self.session.post(action, data=fields, allow_redirects=True, timeout=30) as response:
            response.raise_for_status()
            html = await response.text()
            current_url = str(response.url)

        if _is_dbfp_page(html):
            html, current_url = await self._fetch_through_dbfp(_build_dbfp_redirect_url(html, current_url) or current_url)

        callback_form = _parse_auto_submit_form(html)
        if callback_form:
            html, current_url = await self._submit_oauth_callback(html)

        return html, current_url

    async def _select_authentication_id(self, discovery_url: str, login_id: str,
                                        login_state: str, username: str) -> Optional[str]:
        """Discover the SecureAuth identity provider for the given username."""
        payload = {
            "identifier": username,
            "login_id": login_id,
            "login_state": login_state,
        }
        async with self.session.post(discovery_url, json=payload, timeout=30) as response:
            response.raise_for_status()
            data = await response.json()

        idps = data.get("idps") or []
        if not idps:
            print("Error: No identity providers found for this username")
            return None

        for idp in idps:
            if idp.get("instant_redirect"):
                return idp.get("id")

        return idps[0].get("id")

    async def login(self,
                   login_url: str,
                   username_value: str,
                   password_value: str,
                   username_field: Optional[str] = None,
                   password_field: Optional[str] = None,
                   submit_button: Optional[str] = None) -> bool:
        """
        Log into INET via SecureAuth OAuth.

        INET now redirects Login.aspx to SecureAuth. This method follows that flow:
        fingerprint check -> username discovery -> password entry -> OAuth callback.
        """
        del username_field, password_field, submit_button  # legacy args kept for compatibility

        try:
            await self.create_session()

            print(f"Opening login page: {login_url}")
            html, current_url = await self._fetch_through_dbfp(login_url)

            if not SECUREAUTH_HOST in current_url:
                print(f"Unexpected login redirect: {current_url}")
                return False

            login_page_url = current_url
            login_parts = urlparse(login_page_url)
            login_query = dict(parse_qsl(login_parts.query))
            login_id = login_query.get("login_id")
            login_state = login_query.get("login_state")
            if not login_id or not login_state:
                print("Error: Missing SecureAuth login session parameters")
                return False

            discovery_url = f"{login_page_url.split('?')[0]}/discovery"
            print(f"Discovering identity provider for: {username_value}")
            authentication_id = await self._select_authentication_id(
                discovery_url, login_id, login_state, username_value
            )
            if not authentication_id:
                return False

            print(f"Using identity provider: {authentication_id}")
            async with self.session.post(
                login_page_url,
                data={
                    "version": "2",
                    "source": "main_login_page",
                    "username": username_value,
                    "authentication_id": authentication_id,
                },
                allow_redirects=True,
                timeout=30,
            ) as response:
                response.raise_for_status()
                html = await response.text()
                current_url = str(response.url)

            if _is_dbfp_page(html):
                next_url = _build_dbfp_redirect_url(html, current_url)
                if not next_url:
                    print("Error: Could not parse federation fingerprint redirect")
                    return False
                html, current_url = await self._fetch_through_dbfp(next_url)

            if "text-field-password-input" not in html:
                print("Error: Password form not reached during login")
                return False

            print("Submitting credentials to SecureAuth")
            async with self.session.post(
                current_url,
                data={
                    "identifier": username_value,
                    "password": password_value,
                    "authn_mode": "password_view",
                },
                allow_redirects=True,
                timeout=30,
            ) as response:
                response.raise_for_status()
                html = await response.text()
                current_url = str(response.url)

            if _is_dbfp_page(html):
                next_url = _build_dbfp_redirect_url(html, current_url)
                if next_url:
                    html, current_url = await self._fetch_through_dbfp(next_url)

            callback_form = _parse_auto_submit_form(html)
            if callback_form:
                html, current_url = await self._submit_oauth_callback(html)

            self.current_response = html
            self.current_url = current_url

            if _is_login_page(html, current_url):
                print("Warning: Still on a login page - authentication may have failed")
                return False

            print(f"Login successful! Current URL: {current_url}")
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
    
    async def login_with_stored_credentials(self) -> bool:
        """
        Login using stored credentials.
        
        Returns:
            bool: True if login was successful, False otherwise
        """
        if not all([self.login_url, self.username, self.password]):
            print("Error: Missing login credentials. Please provide username, password, and login URL.")
            return False
        
        return await self.login(
            self.login_url,
            self.username,
            self.password,
        )
    
    async def close(self):
        """Close the session and save cookies."""
        self.save_cookies()
        if self.session and not self.session.closed:
            await self.session.close()


async def check_if_logged_in(scraper: WebScraperAsync) -> bool:
    """Check if we're already logged in by trying to access a protected page."""
    try:
        await scraper.create_session()

        test_url = "https://inet.indsci.com/Dashboard/LandingPage.aspx"
        async with scraper.session.get(test_url, allow_redirects=True, timeout=30) as response:
            html = await response.text()
            final_url = str(response.url)

            if _is_login_page(html, final_url):
                print("Not logged in - cookies expired or invalid")
                return False

            if "DXMainTable" in html or "EquipmentList" in html or "LandingPage" in final_url:
                print("Already logged in via saved cookies!")
                return True

            # Fallback: treat non-login INET dashboard URLs as authenticated
            if "inet.indsci.com/Dashboard" in final_url:
                print("Already logged in via saved cookies!")
                return True

            print("Not logged in - redirected to authentication")
            return False

    except Exception as e:
        print(f"Error checking login status: {e}")
        return False


async def inet_login_and_save(username: str = None, password: str = None):
    """
    Login to INET and save pages using cookie persistence.
    
    Args:
        username: Username for INET login (if None, uses default)
        password: Password for INET login (if None, uses default)
    """
    # Default credentials if not provided
    username = username or "dashboard_user"
    password = password or "900_Second!"
    
    # INET login configuration (SecureAuth OAuth via Login.aspx redirect)
    login_url = INET_LOGIN_URL
    
    # Initialize the scraper with cookie persistence and credentials
    async with WebScraperAsync(
        cookie_file="inet_cookies.pkl",
        username=username,
        password=password,
        login_url=login_url,
    ) as scraper:
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
                print(f"Attempting to login to: {login_url}")
                print(f"Username: {username}")
                
                # Attempt login using stored credentials
                if not await scraper.login_with_stored_credentials():
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


async def scrape_table(url: str, 
                       table_id: str = "ctl00_ctl00_ctl00_cph1_main_dr_Grid_DXMainTable",
                       username: str = None,
                       password: str = None) -> list:
    """
    Scrape a table from a URL after ensuring login.
    
    Args:
        url: The URL to scrape
        table_id: The HTML id of the table to scrape
        username: Username for INET login (if None, uses default)
        password: Password for INET login (if None, uses default)
        
    Returns:
        List of dictionaries, where each dict represents a row with header names as keys
    """
    # Default credentials if not provided
    username = username or "dashboard_user"
    password = password or "900_Second!"
    
    # INET login configuration (SecureAuth OAuth via Login.aspx redirect)
    login_url = INET_LOGIN_URL
    
    async with WebScraperAsync(
        cookie_file="inet_cookies.pkl",
        username=username,
        password=password,
        login_url=login_url,
    ) as scraper:
        try:
            # Check if we're already logged in
            if not await check_if_logged_in(scraper):
                print("Not logged in, performing login...")
                
                if not await scraper.login_with_stored_credentials():
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


async def scrape_equipment_list(username: str = None, password: str = None):
    """
    Scrape the equipment list table and display results.
    
    Args:
        username: Username for INET login (if None, uses default)
        password: Password for INET login (if None, uses default)
    """
    equipment_list_url = "https://inet.indsci.com/Dashboard/EquipmentList.aspx"
    
    print("INET Equipment List Scraper (Async Version)")
    print("=" * 50)
    
    results = await scrape_table(equipment_list_url, username=username, password=password)
    
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

