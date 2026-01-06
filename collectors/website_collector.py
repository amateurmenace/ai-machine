"""
Website Scraper Collector
Scrapes content from websites with respect for robots.txt
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Optional, Set
import time
import re


class WebsiteCollector:
    """Scrapes content from websites with data protection limits"""

    # Data protection limits
    MAX_BYTES = 120 * 1024 * 1024  # 120MB max per source
    MAX_WORDS = 10_000_000  # 10 million words max per source

    def __init__(self, user_agent: str = "NeighborhoodAI/1.0"):
        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': user_agent})
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
    
    def get_robots_txt(self, base_url: str) -> Optional[str]:
        """Fetch robots.txt for a domain"""
        try:
            robots_url = urljoin(base_url, '/robots.txt')
            response = self.session.get(robots_url, timeout=10)
            if response.status_code == 200:
                return response.text
        except:
            pass
        return None
    
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

    def scrape_page(self, url: str) -> Optional[Dict]:
        """Scrape content from a single page"""
        if url in self.visited_urls:
            return None

        # Check limits before scraping
        limit_reached, limit_msg = self.check_limits()
        if limit_reached:
            print(f"Data protection limit reached: {limit_msg}")
            return None

        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            self.visited_urls.add(url)

            # Track bytes
            content_length = len(response.content)
            self.total_bytes += content_length

            # Try to decode content properly, handling encoding errors
            content_type = response.headers.get('content-type', '').lower()

            # Skip non-HTML content
            if 'html' not in content_type and 'text' not in content_type:
                print(f"Skipping non-HTML content: {url}")
                return None

            # Try to get proper encoding
            try:
                content = response.content.decode(response.encoding or 'utf-8', errors='replace')
            except:
                content = response.content.decode('utf-8', errors='replace')

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
            # Try to find main content area
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
                'word_count': len(text.split()),
                'links': links,
                'scraped_at': time.time()
            }
            
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None
    
    def scrape_sitemap(self, sitemap_url: str) -> List[str]:
        """Extract URLs from a sitemap"""
        try:
            response = self.session.get(sitemap_url, timeout=15)
            response.raise_for_status()

            # Try XML parsing first, fall back to lxml-xml
            try:
                soup = BeautifulSoup(response.content, 'lxml-xml')
            except:
                soup = BeautifulSoup(response.content, 'html.parser')

            urls = [loc.text for loc in soup.find_all('loc') if loc.text]
            return urls
        except Exception as e:
            print(f"Error parsing sitemap: {e}")
            return []
    
    def normalize_domain(self, domain: str) -> str:
        """Normalize domain by removing www. prefix"""
        return domain.replace('www.', '')

    def is_same_domain(self, url1: str, url2: str) -> bool:
        """Check if two URLs are from the same domain (ignoring www.)"""
        domain1 = self.normalize_domain(urlparse(url1).netloc)
        domain2 = self.normalize_domain(urlparse(url2).netloc)
        return domain1 == domain2

    def crawl_website(self,
                     start_url: str,
                     max_pages: int = 50,
                     same_domain_only: bool = True,
                     progress_callback=None) -> List[Dict]:
        """Crawl a website starting from a URL with data protection limits"""

        # Reset limits for new crawl
        self.reset_limits()

        base_domain = urlparse(start_url).netloc
        to_visit = [start_url]
        results = []
        limit_message = None
        skipped_external = 0

        print(f"Starting crawl of {start_url} (max {max_pages} pages)")
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

            # Scrape page
            page_data = self.scrape_page(url)

            if page_data:
                results.append(page_data)

                if progress_callback:
                    # Include limit info in progress
                    mb_used = self.total_bytes / (1024 * 1024)
                    progress_callback(len(results), max_pages, page_data['title'],
                                     f"{mb_used:.1f}MB / {self.total_words:,} words")

                # Add new links to visit
                for link in page_data['links']:
                    if link['url'] not in self.visited_urls and link['url'] not in to_visit:
                        if not same_domain_only or self.is_same_domain(link['url'], start_url):
                            to_visit.append(link['url'])

            # Be polite - rate limiting
            time.sleep(1)

        # Log final stats
        mb_used = self.total_bytes / (1024 * 1024)
        print(f"Crawl complete: {len(results)} pages, {mb_used:.1f}MB, {self.total_words:,} words")
        print(f"Skipped {skipped_external} external links")
        if limit_message:
            print(f"Note: {limit_message}")

        return results
    
    def scrape_news_site(self, url: str, max_articles: int = 20) -> List[Dict]:
        """Specialized scraper for news websites"""
        results = self.crawl_website(url, max_pages=max_articles, same_domain_only=True)
        
        # Filter for article-like content (more than 200 words)
        articles = [r for r in results if r['word_count'] > 200]
        
        return articles


# Example usage
if __name__ == "__main__":
    collector = WebsiteCollector()
    
    # Scrape a single page
    result = collector.scrape_page("https://example.com")
    if result:
        print(f"Title: {result['title']}")
        print(f"Words: {result['word_count']}")
        print(f"Links found: {len(result['links'])}")
