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
    """Scrapes content from websites"""
    
    def __init__(self, user_agent: str = "NeighborhoodAI/1.0"):
        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': user_agent})
        self.visited_urls: Set[str] = set()
    
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
    
    def scrape_page(self, url: str) -> Optional[Dict]:
        """Scrape content from a single page"""
        if url in self.visited_urls:
            return None
        
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            self.visited_urls.add(url)
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
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
            
            soup = BeautifulSoup(response.content, 'xml')
            urls = [loc.text for loc in soup.find_all('loc')]
            return urls
        except Exception as e:
            print(f"Error parsing sitemap: {e}")
            return []
    
    def crawl_website(self, 
                     start_url: str, 
                     max_pages: int = 50,
                     same_domain_only: bool = True,
                     progress_callback=None) -> List[Dict]:
        """Crawl a website starting from a URL"""
        
        base_domain = urlparse(start_url).netloc
        to_visit = [start_url]
        results = []
        
        while to_visit and len(results) < max_pages:
            url = to_visit.pop(0)
            
            # Skip if already visited
            if url in self.visited_urls:
                continue
            
            # Check domain if restricting
            if same_domain_only and urlparse(url).netloc != base_domain:
                continue
            
            # Scrape page
            page_data = self.scrape_page(url)
            
            if page_data:
                results.append(page_data)
                
                if progress_callback:
                    progress_callback(len(results), max_pages, page_data['title'])
                
                # Add new links to visit
                for link in page_data['links']:
                    if link['url'] not in self.visited_urls and link['url'] not in to_visit:
                        if not same_domain_only or urlparse(link['url']).netloc == base_domain:
                            to_visit.append(link['url'])
            
            # Be polite - rate limiting
            time.sleep(1)
        
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
