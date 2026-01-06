"""
Advanced Website Scraper Collector
Handles JavaScript-rendered sites using Playwright
Falls back to BeautifulSoup for static sites
"""

import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Optional, Set
import time
import re


class AdvancedWebsiteCollector:
    """Advanced scraper that handles both static and JavaScript-rendered sites"""

    # Data protection limits
    MAX_BYTES = 120 * 1024 * 1024  # 120MB max per source
    MAX_WORDS = 10_000_000  # 10 million words max per source

    def __init__(self, user_agent: str = "NeighborhoodAI/1.0", use_browser: bool = True):
        self.user_agent = user_agent
        self.use_browser = use_browser
        self.visited_urls: Set[str] = set()
        self.total_bytes = 0
        self.total_words = 0

    def is_valid_url(self, url: str) -> bool:
        """Check if URL is valid"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False

    def normalize_domain(self, domain: str) -> str:
        """Normalize domain by removing www. prefix"""
        return domain.replace('www.', '')

    def is_same_domain(self, url1: str, url2: str) -> bool:
        """Check if two URLs are from the same domain (ignoring www.)"""
        domain1 = self.normalize_domain(urlparse(url1).netloc)
        domain2 = self.normalize_domain(urlparse(url2).netloc)
        return domain1 == domain2

    def check_limits(self) -> tuple[bool, str]:
        """Check if data protection limits have been reached"""
        if self.total_bytes >= self.MAX_BYTES:
            return True, f"Byte limit reached ({self.total_bytes / (1024*1024):.1f}MB / {self.MAX_BYTES / (1024*1024):.0f}MB)"
        if self.total_words >= self.MAX_WORDS:
            return True, f"Word limit reached ({self.total_words:,} / {self.MAX_WORDS:,} words)"
        return False, ""

    def reset_limits(self):
        """Reset tracking counters for a new source"""
        self.total_bytes = 0
        self.total_words = 0
        self.visited_urls = set()

    async def scrape_page_with_browser(self, url: str) -> Optional[Dict]:
        """Scrape page using Playwright browser (handles JavaScript)"""
        if url in self.visited_urls:
            return None

        # Check limits before scraping
        limit_reached, limit_msg = self.check_limits()
        if limit_reached:
            print(f"Data protection limit reached: {limit_msg}")
            return None

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(user_agent=self.user_agent)
                page = await context.new_page()

                # Navigate and wait for content
                await page.goto(url, wait_until='networkidle', timeout=30000)

                # Wait a bit for dynamic content
                await page.wait_for_timeout(2000)

                # Get page content
                content = await page.content()
                title = await page.title()

                # Track bytes
                self.total_bytes += len(content.encode('utf-8'))
                self.visited_urls.add(url)

                # Parse with BeautifulSoup
                soup = BeautifulSoup(content, 'html.parser')

                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()

                # Get meta description
                meta_desc = soup.find("meta", {"name": "description"})
                description = meta_desc.get("content", "") if meta_desc else ""

                # Get main content
                main_content = soup.find('main') or soup.find('article') or soup.find('div', class_=re.compile('content|main'))

                if main_content:
                    text = main_content.get_text()
                else:
                    text = soup.get_text()

                # Clean up text
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = ' '.join(chunk for chunk in chunks if chunk)

                # Track word count
                word_count = len(text.split())
                self.total_words += word_count

                # Get links
                links = []
                for link in soup.find_all('a', href=True):
                    href = urljoin(url, link['href'])
                    if self.is_valid_url(href):
                        links.append({
                            'url': href,
                            'text': link.get_text().strip()
                        })

                await browser.close()

                return {
                    'url': url,
                    'title': title,
                    'description': description,
                    'content': text,
                    'word_count': word_count,
                    'links': links,
                    'scraped_at': time.time(),
                    'method': 'playwright'
                }

        except PlaywrightTimeout:
            print(f"Timeout loading {url}")
            return None
        except Exception as e:
            print(f"Error scraping {url} with Playwright: {e}")
            return None

    def scrape_page_static(self, url: str) -> Optional[Dict]:
        """Scrape page using requests + BeautifulSoup (static HTML only)"""
        import requests

        if url in self.visited_urls:
            return None

        # Check limits before scraping
        limit_reached, limit_msg = self.check_limits()
        if limit_reached:
            print(f"Data protection limit reached: {limit_msg}")
            return None

        try:
            response = requests.get(url, timeout=15, headers={'User-Agent': self.user_agent})
            response.raise_for_status()
            self.visited_urls.add(url)

            # Track bytes
            content_length = len(response.content)
            self.total_bytes += content_length

            # Try to decode content properly
            content_type = response.headers.get('content-type', '').lower()

            if 'html' not in content_type and 'text' not in content_type:
                print(f"Skipping non-HTML content: {url}")
                return None

            content = response.content.decode(response.encoding or 'utf-8', errors='replace')
            soup = BeautifulSoup(content, 'html.parser')

            # Remove script and style elements
            for script in soup(["script", "style", "nav", "footer", "header"]):
                script.decompose()

            # Get title
            title = soup.title.string if soup.title else ""

            # Get meta description
            meta_desc = soup.find("meta", {"name": "description"})
            description = meta_desc.get("content", "") if meta_desc else ""

            # Get main content
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_=re.compile('content|main'))

            if main_content:
                text = main_content.get_text()
            else:
                text = soup.get_text()

            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)

            # Track word count
            word_count = len(text.split())
            self.total_words += word_count

            # Get links
            links = []
            for link in soup.find_all('a', href=True):
                href = urljoin(url, link['href'])
                if self.is_valid_url(href):
                    links.append({
                        'url': href,
                        'text': link.get_text().strip()
                    })

            return {
                'url': url,
                'title': title.strip(),
                'description': description.strip(),
                'content': text,
                'word_count': word_count,
                'links': links,
                'scraped_at': time.time(),
                'method': 'beautifulsoup'
            }

        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None

    async def crawl_website_async(self,
                                   start_url: str,
                                   max_pages: int = 50,
                                   same_domain_only: bool = True,
                                   progress_callback=None) -> List[Dict]:
        """Crawl a website using Playwright for JavaScript sites"""
        self.reset_limits()

        base_domain = urlparse(start_url).netloc
        to_visit = [start_url]
        results = []
        limit_message = None
        skipped_external = 0

        print(f"Starting crawl of {start_url} (max {max_pages} pages) with Playwright")
        print(f"Base domain: {base_domain}")

        while to_visit and len(results) < max_pages:
            # Check data protection limits
            limit_reached, limit_msg = self.check_limits()
            if limit_reached:
                limit_message = limit_msg
                print(f"Stopping crawl: {limit_msg}")
                break

            url = to_visit.pop(0)

            # Skip if already visited
            if url in self.visited_urls:
                continue

            # Check domain if restricting
            if same_domain_only and not self.is_same_domain(url, start_url):
                skipped_external += 1
                continue

            # Scrape page with browser
            page_data = await self.scrape_page_with_browser(url)

            if page_data:
                results.append(page_data)

                if progress_callback:
                    mb_used = self.total_bytes / (1024 * 1024)
                    progress_callback(len(results), max_pages, page_data['title'],
                                      f"{mb_used:.1f}MB / {self.total_words:,} words")

                # Add new links to visit
                for link in page_data['links']:
                    if link['url'] not in self.visited_urls and link['url'] not in to_visit:
                        if not same_domain_only or self.is_same_domain(link['url'], start_url):
                            to_visit.append(link['url'])

            # Be polite - rate limiting
            await asyncio.sleep(2)

        # Log final stats
        mb_used = self.total_bytes / (1024 * 1024)
        print(f"Crawl complete: {len(results)} pages, {mb_used:.1f}MB, {self.total_words:,} words")
        print(f"Skipped {skipped_external} external links")
        if limit_message:
            print(f"Note: {limit_message}")

        return results

    def crawl_website(self,
                      start_url: str,
                      max_pages: int = 50,
                      same_domain_only: bool = True,
                      progress_callback=None) -> List[Dict]:
        """Synchronous wrapper for async crawling"""
        # Use a thread with its own event loop to avoid conflicts with FastAPI's loop
        import threading

        result_container = []
        error_container = []

        def run_in_thread():
            try:
                # Create a fresh event loop in this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(
                        self.crawl_website_async(start_url, max_pages, same_domain_only, progress_callback)
                    )
                    result_container.append(result)
                finally:
                    loop.close()
            except Exception as e:
                error_container.append(e)

        thread = threading.Thread(target=run_in_thread)
        thread.start()
        thread.join()

        if error_container:
            raise error_container[0]

        return result_container[0] if result_container else []


# Example usage
if __name__ == "__main__":
    collector = AdvancedWebsiteCollector()

    # Test with a JavaScript-heavy site
    result = asyncio.run(collector.scrape_page_with_browser("https://www.brooklinema.gov"))
    if result:
        print(f"Title: {result['title']}")
        print(f"Words: {result['word_count']}")
        print(f"Method: {result['method']}")
        print(f"Content preview: {result['content'][:200]}...")
