
"""
Revenue Scraper API

This Python backend extracts revenue information from company websites.
It uses Flask for the API and Beautiful Soup for web scraping.

To run this backend:
1. Install requirements: pip install -r requirements.txt
2. Run the server: python app.py
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
import time
from urllib.parse import urlparse, urljoin
import concurrent.futures

app = Flask(__name__)
CORS(app)  # Enable Cross-Origin Resource Sharing

# Constants similar to the JavaScript version
FINANCIAL_KEYWORDS = [
    'revenue', 'annual revenue', 'annual revenue 2024', 
    'annual revenue 2025', 'turnover 2024', 'turnover 2025',
    'sales', 'turnover', 'income', 'earnings',
    'financial results', 'financial highlights',
    'million', 'billion', 'trillion',
    'fiscal year', 'fy'
]

FINANCIAL_PATHS = [
    'investor', 'investors', 'investor-relations', 'ir',
    'about', 'about-us', 'company', 'corporate',
    'finance', 'financial', 'financials',
    'annual-report', 'quarterly-report',
    'results', 'earnings', 'press', 'news'
]

# Regex patterns to extract monetary values
MONETARY_PATTERNS = [
    # $X million/billion/trillion
    r'\$([\d,.]+)\s*(million|billion|trillion|m|b|t)',
    # X million/billion/trillion dollars
    r'([\d,.]+)\s*(million|billion|trillion)\s*(dollars|usd)',
    # €X million/billion/trillion
    r'€([\d,.]+)\s*(million|billion|trillion|m|b|t)',
    # £X million/billion/trillion
    r'£([\d,.]+)\s*(million|billion|trillion|m|b|t)',
    # ¥X million/billion/trillion
    r'¥([\d,.]+)\s*(million|billion|trillion|m|b|t)',
    # General revenue statement patterns
    r'revenue of \$([\d,.]+)\s*(million|billion|trillion|m|b|t)',
    r'revenue of ([\d,.]+)\s*(million|billion|trillion)\s*(dollars|usd)',
    r'revenue: \$([\d,.]+)\s*(million|billion|trillion|m|b|t)',
    r'revenue: ([\d,.]+)\s*(million|billion|trillion)\s*(dollars|usd)',
    r'revenue was \$([\d,.]+)\s*(million|billion|trillion|m|b|t)',
    r'revenue reached \$([\d,.]+)\s*(million|billion|trillion|m|b|t)',
    r'total revenue of \$([\d,.]+)\s*(million|billion|trillion|m|b|t)',
    r'([\d,.]+)\s*(million|billion|trillion)\s*in revenue'
]

# Request headers to simulate a real browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5'
}

def fetch_with_retry(url, max_retries=3, timeout=10):
    """Fetch URL content with retry logic"""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Attempt {attempt+1}/{max_retries} failed for {url}: {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
    
    return None

def find_financial_pages(base_url):
    """Find potential financial pages on a website"""
    try:
        # Parse the URL to get the domain
        parsed_url = urlparse(base_url)
        domain = parsed_url.netloc
        
        # Ensure we have a valid domain
        if not domain:
            if not base_url.startswith(('http://', 'https://')):
                base_url = 'https://' + base_url
                parsed_url = urlparse(base_url)
                domain = parsed_url.netloc
        
        # Get the homepage content
        homepage_url = f"{parsed_url.scheme or 'https'}://{domain}"
        html_content = fetch_with_retry(homepage_url)
        
        if not html_content:
            return []
        
        # Parse the HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all links on the page
        links = soup.find_all('a', href=True)
        
        # Collect potential financial pages
        financial_pages = []
        seen_urls = set()
        
        # Check each link against our financial paths
        for link in links:
            href = link['href']
            
            # Create absolute URL if it's relative
            if not href.startswith(('http://', 'https://')):
                href = urljoin(homepage_url, href)
            
            # Skip if we've already seen this URL
            if href in seen_urls:
                continue
            
            seen_urls.add(href)
            
            # Check if the URL path contains any of our financial keywords
            path = urlparse(href).path.lower()
            if any(keyword in path for keyword in FINANCIAL_PATHS):
                financial_pages.append(href)
        
        # Add additional potential financial pages
        for path in FINANCIAL_PATHS:
            financial_pages.append(f"{homepage_url}/{path}")
        
        # Add potential subdomains
        financial_pages.append(f"https://investors.{domain}")
        financial_pages.append(f"https://investor.{domain}")
        financial_pages.append(f"https://ir.{domain}")
        
        return list(set(financial_pages))  # Remove duplicates
    
    except Exception as e:
        print(f"Error finding financial pages for {base_url}: {e}")
        return []

def extract_revenue_figure(text):
    """Extract revenue figures from text using regex patterns"""
    for pattern in MONETARY_PATTERNS:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        
        for match in matches:
            # Get the matched text and surrounding context
            start_idx = max(0, match.start() - 50)
            end_idx = min(len(text), match.end() + 50)
            surrounding_text = text[start_idx:end_idx].lower()
            
            # Check if the match is in a revenue context
            has_revenue_context = any(keyword.lower() in surrounding_text for keyword in FINANCIAL_KEYWORDS)
            
            if has_revenue_context or 'revenue' in surrounding_text:
                # Format the match
                amount = match.group(1)
                scale = match.group(2).lower() if len(match.groups()) > 1 else ''
                
                # Determine the currency symbol
                prefix = ''
                if '$' in match.group(0):
                    prefix = '$'
                elif '€' in match.group(0):
                    prefix = '€'
                elif '£' in match.group(0):
                    prefix = '£'
                elif '¥' in match.group(0):
                    prefix = '¥'
                
                return f"{prefix}{amount} {scale}"
    
    return "Not Found"

def scrape_page_for_revenue(url):
    """Scrape a single page for revenue information"""
    try:
        html_content = fetch_with_retry(url)
        if not html_content:
            return ""
        
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract text content from the page
        text = soup.get_text(separator=' ', strip=True)
        
        # Look for paragraphs that might contain financial information
        paragraphs = soup.find_all(['p', 'div', 'section', 'table'])
        
        # Prioritize content that mentions financial keywords
        potential_financial_text = []
        
        for p in paragraphs:
            p_text = p.get_text(strip=True)
            if any(keyword.lower() in p_text.lower() for keyword in FINANCIAL_KEYWORDS):
                potential_financial_text.append(p_text)
        
        # Combine the financial paragraphs with higher weight
        combined_text = ' '.join(potential_financial_text) + ' ' + text
        
        return combined_text
    
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return ""

def scrape_url_for_revenue(url):
    """Main function to scrape a URL for revenue information"""
    try:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Find potential financial pages
        financial_pages = find_financial_pages(url)
        
        if not financial_pages:
            return "Not Found"
        
        # Scrape up to 5 pages concurrently
        pages_to_search = financial_pages[:5]
        combined_text = ""
        
        # Use concurrent futures for parallel scraping
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_url = {executor.submit(scrape_page_for_revenue, page): page for page in pages_to_search}
            
            for future in concurrent.futures.as_completed(future_to_url):
                page_url = future_to_url[future]
                try:
                    page_text = future.result()
                    combined_text += page_text + ' '
                except Exception as e:
                    print(f"Error processing {page_url}: {e}")
        
        # If we found some text, extract revenue figure
        if combined_text.strip():
            revenue_figure = extract_revenue_figure(combined_text)
            return revenue_figure
        
        return "Not Found"
    
    except Exception as e:
        print(f"Error in main scrape function for {url}: {e}")
        return "Not Found"

@app.route('/api/scrape', methods=['POST'])
def scrape_endpoint():
    """API endpoint to scrape a URL for revenue information"""
    try:
        data = request.get_json()
        
        if not data or 'url' not in data:
            return jsonify({'error': 'URL is required'}), 400
        
        url = data['url']
        revenue = scrape_url_for_revenue(url)
        
        return jsonify({
            'url': url,
            'revenue': revenue
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/batch-scrape', methods=['POST'])
def batch_scrape_endpoint():
    """API endpoint to scrape multiple URLs for revenue information"""
    try:
        data = request.get_json()
        
        if not data or 'urls' not in data or not isinstance(data['urls'], list):
            return jsonify({'error': 'A list of URLs is required'}), 400
        
        urls = data['urls']
        results = []
        
        # Process each URL
        for url in urls:
            revenue = scrape_url_for_revenue(url)
            results.append({
                'url': url,
                'revenue': revenue
            })
        
        return jsonify({'results': results})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
