"""
PDF Collector
Extracts text and metadata from PDF documents
"""

import requests
from pypdf import PdfReader
from typing import Dict, Optional, List
import io
import re


class PDFCollector:
    """Extracts content from PDF files"""
    
    def __init__(self):
        self.session = requests.Session()
    
    def extract_from_url(self, pdf_url: str) -> Optional[Dict]:
        """Download and extract text from a PDF URL"""
        try:
            response = self.session.get(pdf_url, timeout=30)
            response.raise_for_status()
            
            # Read PDF from bytes
            pdf_file = io.BytesIO(response.content)
            return self.extract_from_file(pdf_file, source_url=pdf_url)
            
        except Exception as e:
            print(f"Error downloading PDF from {pdf_url}: {e}")
            return None
    
    def extract_from_file(self, file_path_or_buffer, source_url: Optional[str] = None) -> Optional[Dict]:
        """Extract text from a PDF file or buffer"""
        try:
            reader = PdfReader(file_path_or_buffer)
            
            # Get metadata
            metadata = {}
            if reader.metadata:
                metadata = {
                    'title': reader.metadata.get('/Title', ''),
                    'author': reader.metadata.get('/Author', ''),
                    'subject': reader.metadata.get('/Subject', ''),
                    'creator': reader.metadata.get('/Creator', ''),
                    'producer': reader.metadata.get('/Producer', ''),
                    'creation_date': reader.metadata.get('/CreationDate', '')
                }
            
            # Extract text from all pages
            pages = []
            full_text = []
            
            for i, page in enumerate(reader.pages):
                page_text = page.extract_text()
                pages.append({
                    'page_number': i + 1,
                    'text': page_text,
                    'word_count': len(page_text.split())
                })
                full_text.append(page_text)
            
            combined_text = '\n\n'.join(full_text)
            
            # Clean up text
            combined_text = re.sub(r'\s+', ' ', combined_text)
            combined_text = combined_text.strip()
            
            return {
                'source_url': source_url,
                'metadata': metadata,
                'num_pages': len(reader.pages),
                'pages': pages,
                'full_text': combined_text,
                'word_count': len(combined_text.split()),
                'title': metadata.get('title', 'Untitled PDF')
            }
            
        except Exception as e:
            print(f"Error extracting PDF: {e}")
            return None
    
    def extract_sections(self, text: str, chunk_size: int = 1000) -> List[Dict]:
        """Break PDF text into manageable sections"""
        words = text.split()
        sections = []
        
        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i + chunk_size])
            sections.append({
                'section_number': len(sections) + 1,
                'text': chunk,
                'word_count': len(chunk.split())
            })
        
        return sections
    
    def search_pdfs_in_website(self, base_url: str) -> List[str]:
        """Find PDF links on a website"""
        from bs4 import BeautifulSoup
        
        pdf_links = []
        
        try:
            response = self.session.get(base_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all PDF links
            for link in soup.find_all('a', href=True):
                href = link['href']
                if href.lower().endswith('.pdf'):
                    # Make absolute URL
                    from urllib.parse import urljoin
                    pdf_url = urljoin(base_url, href)
                    pdf_links.append(pdf_url)
            
        except Exception as e:
            print(f"Error searching for PDFs: {e}")
        
        return pdf_links
    
    def collect_pdfs_from_site(self, base_url: str, max_pdfs: int = 10, progress_callback=None) -> List[Dict]:
        """Find and extract PDFs from a website"""
        
        # Find PDF links
        pdf_urls = self.search_pdfs_in_website(base_url)[:max_pdfs]
        
        results = []
        for i, pdf_url in enumerate(pdf_urls):
            if progress_callback:
                progress_callback(i, len(pdf_urls), pdf_url)
            
            pdf_data = self.extract_from_url(pdf_url)
            if pdf_data:
                results.append(pdf_data)
        
        return results


# Example usage
if __name__ == "__main__":
    collector = PDFCollector()
    
    # Extract from a URL
    pdf_url = "https://example.com/document.pdf"
    result = collector.extract_from_url(pdf_url)
    
    if result:
        print(f"Title: {result['title']}")
        print(f"Pages: {result['num_pages']}")
        print(f"Words: {result['word_count']}")
