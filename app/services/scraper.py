from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import time
import re

class WebScraper:
    def __init__(self, headless=True):
        self.headless = headless
        self.driver = None
        self._setup_driver()
    
    def _setup_driver(self):
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.implicitly_wait(10)
    
    def scrape_url(self, url, allowed_domains=None):
        """Scrape a single URL and return content"""
        try:
            if allowed_domains and not self._is_domain_allowed(url, allowed_domains):
                return None
            
            self.driver.get(url)
            time.sleep(2)
            
            title = self.driver.title
            content = self._extract_text_content()
            
            return {
                'url': url,
                'title': title,
                'content': content,
                'domain': urlparse(url).netloc
            }
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None
    
    def scrape_with_depth(self, initial_urls, depth=1, allowed_domains=None):
        """Scrape URLs with specified depth"""
        scraped_data = []
        visited_urls = set()
        
        urls_to_scrape = [(url, 1) for url in initial_urls]
        
        while urls_to_scrape:
            current_url, current_depth = urls_to_scrape.pop(0)
            
            if current_url in visited_urls or current_depth > depth:
                continue
            
            visited_urls.add(current_url)
            
            page_data = self.scrape_url(current_url, allowed_domains)
            if page_data:
                page_data['depth_level'] = current_depth
                scraped_data.append(page_data)
                
                if current_depth < depth:
                    new_urls = self._extract_links(current_url, allowed_domains)
                    for new_url in new_urls:
                        if new_url not in visited_urls:
                            urls_to_scrape.append((new_url, current_depth + 1))
        
        return scraped_data
    
    def _extract_text_content(self):
        """Extract clean text content from the current page"""
        try:
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            for script in soup(["script", "style", "nav", "header", "footer"]):
                script.decompose()
            
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text
        except Exception as e:
            print(f"Error extracting text content: {e}")
            return ""
    
    def _extract_links(self, base_url, allowed_domains=None):
        """Extract internal links from the current page"""
        try:
            links = []
            elements = self.driver.find_elements(By.TAG_NAME, "a")
            
            for element in elements:
                href = element.get_attribute("href")
                if href:
                    full_url = urljoin(base_url, href)
                    if self._is_valid_url(full_url) and self._is_domain_allowed(full_url, allowed_domains):
                        links.append(full_url)
            
            return list(set(links))
        except Exception as e:
            print(f"Error extracting links: {e}")
            return []
    
    def _is_valid_url(self, url):
        """Check if URL is valid and not a file download"""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            
            excluded_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.zip', '.rar']
            return not any(url.lower().endswith(ext) for ext in excluded_extensions)
        except:
            return False
    
    def _is_domain_allowed(self, url, allowed_domains):
        """Check if URL domain is in allowed domains list"""
        if not allowed_domains:
            return True
        
        try:
            domain = urlparse(url).netloc.lower()
            return any(domain.endswith(allowed_domain.lower()) for allowed_domain in allowed_domains)
        except:
            return False
    
    def close(self):
        """Close the webdriver"""
        if self.driver:
            self.driver.quit()