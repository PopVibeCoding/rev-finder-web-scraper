
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
import os

app = Flask(__name__)

# Enable CORS with specific origins for production readiness
CORS(app, resources={r"/api/*": {"origins": [
    "http://localhost:3000", 
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://192.168.6.186:5173",
    # Add your production domain here when deployed
]}})

# Constants similar to the JavaScript version but expanded
FINANCIAL_KEYWORDS = [
    'revenue', 'annual revenue', 'annual revenue 2024', 'annual revenue 2023',
    'annual revenue 2025', 'turnover 2024', 'turnover 2025', 'turnover 2023',
    'sales', 'turnover', 'income', 'earnings', 'net sales',
    'financial results', 'financial highlights', 'financial performance',
    'million', 'billion', 'trillion', 'yearly revenue', 'quarterly revenue',
    'fiscal year', 'fy', 'fy2024', 'fy2023', 'fy 2024', 'fy 2023',
    'annual report', '10-k', '10k', 'form 10-k', 'sec filing'
]

FINANCIAL_PAGES = [
    'investor', 'investors', 'investor-relations', 'ir',
    'about', 'about-us', 'company', 'corporate',
    'finance', 'financial', 'financials',
    'annual-report', 'quarterly-report', 'earnings-report',
    'results', 'earnings', 'press', 'news',
    'reports', 'financial-reports', 'annual-results',
    '10k', '10-k', 'sec-filings', 'sec'
]

# Enhanced regex patterns to extract monetary values with year context
MONETARY_PATTERNS = [
    # Patterns with year context (2023/2024)
    r'(?:20[23][0-9]|FY\s?(?:20)?[23][0-9]).*?revenue.*?\$([\d,.]+)\s*(million|billion|trillion|m|b|t)',
    r'revenue.*?(?:20[23][0-9]|FY\s?(?:20)?[23][0-9]).*?\$([\d,.]+)\s*(million|billion|trillion|m|b|t)',
    r'(?:20[23][0-9]|FY\s?(?:20)?[23][0-9]).*?sales.*?\$([\d,.]+)\s*(million|billion|trillion|m|b|t)',
    r'sales.*?(?:20[23][0-9]|FY\s?(?:20)?[23][0-9]).*?\$([\d,.]+)\s*(million|billion|trillion|m|b|t)',

    # Generic revenue patterns
    r'\$([\d,.]+)\s*(million|billion|trillion|m|b|t)\s*(?:in|of)?\s*(?:annual)?\s*revenue',
    r'revenue\s*(?:of|was|is|at|:)?\s*\$([\d,.]+)\s*(million|billion|trillion|m|b|t)',
    r'([\d,.]+)\s*(million|billion|trillion)\s*(?:dollars|usd)?\s*(?:in|of)?\s*(?:annual)?\s*revenue',
    
    # Currency symbols with values
    r'\$([\d,.]+)\s*(million|billion|trillion|m|b|t)',
    r'€([\d,.]+)\s*(million|billion|trillion|m|b|t)',
    r'£([\d,.]+)\s*(million|billion|trillion|m|b|t)',
    r'¥([\d,.]+)\s*(million|billion|trillion|m|b|t)',
    
    # Other revenue statement patterns
    r'revenue of \$([\d,.]+)\s*(million|billion|trillion|m|b|t)',
    r'revenue of ([\d,.]+)\s*(million|billion|trillion)\s*(dollars|usd)',
    r'revenue: \$([\d,.]+)\s*(million|billion|trillion|m|b|t)',
    r'revenue: ([\d,.]+)\s*(million|billion|trillion)\s*(dollars|usd)',
    r'revenue was \$([\d,.]+)\s*(million|billion|trillion|m|b|t)',
    r'revenue reached \$([\d,.]+)\s*(million|billion|trillion|m|b|t)',
    r'total revenue (?:of|was|is|:)? \$([\d,.]+)\s*(million|billion|trillion|m|b|t)',
    r'([\d,.]+)\s*(million|billion|trillion)\s*in (?:total)?\s*revenue',
    r'annual revenue (?:of|was|is|:)? \$([\d,.]+)\s*(million|billion|trillion|m|b|t)',
]

# Request headers to simulate a real browser for better crawling
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Referer': 'https://www.google.com/',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'cross-site',
    'Cache-Control': 'max-age=0'
}

def fetch_with_retry(url, max_retries=3, timeout=15):
    """Fetch URL content with retry logic and better error handling"""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.exceptions.SSLError:
            # Try without HTTPS if SSL fails
            if url.startswith('https://'):
                try:
                    http_url = url.replace('https://', 'http://')
                    print(f"SSL Error, trying HTTP: {http_url}")
                    response = requests.get(http_url, headers=HEADERS, timeout=timeout)
                    response.raise_for_status()
                    return response.text
                except Exception:
                    pass
            if attempt == max_retries - 1:
                raise
        except requests.RequestException as e:
            print(f"Attempt {attempt+1}/{max_retries} failed for {url}: {e}")
            if attempt == max_retries - 1:
                raise
            delay = 2 ** attempt  # Exponential backoff
            time.sleep(delay)
    
    return None

def normalize_url(url):
    """Normalize URL to ensure it has a scheme and is properly formatted"""
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    # Remove trailing slash if present
    if url.endswith('/'):
        url = url[:-1]
        
    return url

def get_domain(url):
    """Extract domain from URL"""
    url = normalize_url(url)
    parsed_url = urlparse(url)
    return parsed_url.netloc

def find_financial_pages(base_url, max_pages=10):
    """Find potential financial pages on a website with improved search"""
    try:
        base_url = normalize_url(base_url)
        domain = get_domain(base_url)
        
        # Get the homepage content
        homepage_url = f"https://{domain}"
        try:
            html_content = fetch_with_retry(homepage_url)
        except:
            try:
                html_content = fetch_with_retry(f"http://{domain}")
            except:
                return []
        
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
            href = link.get('href', '').strip()
            if not href or href.startswith('#') or href.startswith('javascript:'):
                continue
                
            # Create absolute URL if it's relative
            if not href.startswith(('http://', 'https://')):
                href = urljoin(homepage_url, href)
            
            # Ensure the link is from the same domain
            link_domain = get_domain(href)
            if domain not in link_domain and link_domain not in domain:
                continue
                
            # Skip if we've already seen this URL
            if href in seen_urls:
                continue
            
            seen_urls.add(href)
            
            # Enhanced check for financial pages:
            # 1. Check URL path for financial keywords
            path = urlparse(href).path.lower()
            
            # 2. Check link text for financial keywords
            link_text = link.get_text().lower()
            
            if (any(keyword in path for keyword in FINANCIAL_PAGES) or
                any(keyword in link_text for keyword in FINANCIAL_KEYWORDS)):
                financial_pages.append(href)
        
        # Add additional potential financial pages
        for path in FINANCIAL_PAGES:
            financial_pages.append(f"{homepage_url}/{path}")
        
        # Add potential subdomains for investor relations
        financial_pages.append(f"https://investors.{domain}")
        financial_pages.append(f"https://investor.{domain}")
        financial_pages.append(f"https://ir.{domain}")
        financial_pages.append(f"http://investors.{domain}")
        financial_pages.append(f"http://investor.{domain}")
        financial_pages.append(f"http://ir.{domain}")
        
        # Specific pages that often contain revenue information
        financial_pages.append(f"{homepage_url}/about")
        financial_pages.append(f"{homepage_url}/about-us")
        financial_pages.append(f"{homepage_url}/annual-report")
        financial_pages.append(f"{homepage_url}/financial-results")
        
        # Limit to unique URLs and max_pages
        return list(set(financial_pages))[:max_pages]
    
    except Exception as e:
        print(f"Error finding financial pages for {base_url}: {e}")
        return []

def extract_revenue_with_context(text, prefer_recent=True):
    """Extract revenue figures from text with enhanced context awareness"""
    all_matches = []
    
    # Process text to make pattern matching more reliable
    text = text.lower()
    
    # Replace common abbreviations
    text = text.replace('$b', '$ billion').replace('$m', '$ million').replace('$t', '$ trillion')
    text = text.replace('$bn', '$ billion').replace('$mn', '$ million').replace('$tn', '$ trillion')
    
    # Specific search for 2024 or 2023 revenue (prioritizing 2024)
    year_specific_patterns = [
        r'(?:2024|fy\s?(?:20)?24).*?revenue.*?\$([\d,.]+)\s*(million|billion|trillion|m|b|t)',
        r'revenue.*?(?:2024|fy\s?(?:20)?24).*?\$([\d,.]+)\s*(million|billion|trillion|m|b|t)',
        r'(?:2024|fy\s?(?:20)?24).*?sales.*?\$([\d,.]+)\s*(million|billion|trillion|m|b|t)',
        r'sales.*?(?:2024|fy\s?(?:20)?24).*?\$([\d,.]+)\s*(million|billion|trillion|m|b|t)',
        r'(?:2023|fy\s?(?:20)?23).*?revenue.*?\$([\d,.]+)\s*(million|billion|trillion|m|b|t)',
        r'revenue.*?(?:2023|fy\s?(?:20)?23).*?\$([\d,.]+)\s*(million|billion|trillion|m|b|t)',
        r'(?:2023|fy\s?(?:20)?23).*?sales.*?\$([\d,.]+)\s*(million|billion|trillion|m|b|t)',
        r'sales.*?(?:2023|fy\s?(?:20)?23).*?\$([\d,.]+)\s*(million|billion|trillion|m|b|t)',
    ]
    
    # First try to find year-specific matches (2024/2023)
    for pattern in year_specific_patterns:
        matches = re.finditer(pattern, text, re.IGNORECASE)
        
        for match in matches:
            # Get surrounding text for context validation
            start_idx = max(0, match.start() - 100)
            end_idx = min(len(text), match.end() + 100)
            context = text[start_idx:end_idx].lower()
            
            # Skip if this appears to be about profits, not revenue
            if ('profit' in context and 'revenue' not in context) or ('net income' in context and 'revenue' not in context):
                continue
                
            # Extract match details
            amount = match.group(1)
            scale = match.group(2).lower() if len(match.groups()) > 1 else ''
            
            # Determine year - prioritize 2024, then 2023
            year = None
            if '2024' in context or 'fy24' in context or 'fy 24' in context or 'fy2024' in context or 'fy 2024' in context:
                year = 2024
            elif '2023' in context or 'fy23' in context or 'fy 23' in context or 'fy2023' in context or 'fy 2023' in context:
                year = 2023
            
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
            
            # Score the match by relevance (quality of context)
            score = 0
            if year == 2024:
                score += 100  # Heavily prioritize 2024 data
            elif year == 2023:
                score += 50   # Next prioritize 2023 data
                
            # Additional context scoring
            if 'annual revenue' in context:
                score += 30
            elif 'revenue' in context:
                score += 20
            elif 'sales' in context:
                score += 15
                
            if 'million' in scale or 'm' == scale:
                value_str = f"{prefix}{amount} million"
            elif 'billion' in scale or 'b' == scale:
                value_str = f"{prefix}{amount} billion"
            elif 'trillion' in scale or 't' == scale:
                value_str = f"{prefix}{amount} trillion"
            else:
                value_str = f"{prefix}{amount}"
                
            all_matches.append({
                'value': value_str,
                'score': score,
                'year': year,
                'context': context
            })
    
    # If no year-specific matches found, try generic patterns
    if not all_matches:
        for pattern in MONETARY_PATTERNS:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            for match in matches:
                # Get surrounding text for context validation
                start_idx = max(0, match.start() - 100)
                end_idx = min(len(text), match.end() + 100)
                context = text[start_idx:end_idx].lower()
                
                # Check if match is in a revenue context
                has_revenue_context = (
                    'revenue' in context or
                    'sales' in context or
                    'turnover' in context
                )
                
                # Skip if not in revenue context or if it appears to be about profit
                if not has_revenue_context or ('profit' in context and 'revenue' not in context):
                    continue
                    
                # Extract match details
                amount = match.group(1)
                scale = match.group(2).lower() if len(match.groups()) > 1 else ''
                
                # Determine year from context
                year = None
                if '2024' in context or 'fy24' in context or 'fy 24' in context:
                    year = 2024
                elif '2023' in context or 'fy23' in context or 'fy 23' in context:
                    year = 2023
                    
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
                
                # Score the match by relevance
                score = 0
                if year == 2024:
                    score += 50
                elif year == 2023:
                    score += 25
                    
                # Additional context scoring
                if 'annual revenue' in context:
                    score += 20
                elif 'revenue' in context:
                    score += 15
                elif 'sales' in context:
                    score += 10
                
                if 'million' in scale or 'm' == scale:
                    value_str = f"{prefix}{amount} million"
                elif 'billion' in scale or 'b' == scale:
                    value_str = f"{prefix}{amount} billion" 
                elif 'trillion' in scale or 't' == scale:
                    value_str = f"{prefix}{amount} trillion"
                else:
                    value_str = f"{prefix}{amount}"
                    
                all_matches.append({
                    'value': value_str,
                    'score': score,
                    'year': year,
                    'context': context
                })
    
    # Sort by score (most relevant first)
    all_matches.sort(key=lambda x: x['score'], reverse=True)
    
    # Return the best match, or "Not Found"
    if all_matches:
        return all_matches[0]['value']
    return "Not Found"

def scrape_page_for_revenue(url):
    """Scrape a single page for revenue information with improved extraction"""
    try:
        html_content = fetch_with_retry(url)
        if not html_content:
            return ""
        
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract text content from the page
        page_text = soup.get_text(separator=' ', strip=True)
        
        # Look for sections that might contain financial information
        financial_sections = []
        
        # Check headings for financial indicators
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        for heading in headings:
            heading_text = heading.get_text(strip=True).lower()
            if any(keyword in heading_text for keyword in FINANCIAL_KEYWORDS):
                # Get the next siblings until next heading
                current = heading.next_sibling
                section_text = heading_text + " "
                
                while current and not current.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    if hasattr(current, 'get_text'):
                        section_text += current.get_text(strip=True) + " "
                    elif hasattr(current, 'string') and current.string:
                        section_text += current.string + " "
                    current = current.next_sibling
                    
                financial_sections.append(section_text)
        
        # Look for paragraphs that might contain financial information
        for tag in ['p', 'div', 'section', 'table', 'tr', 'td']:
            elements = soup.find_all(tag)
            for elem in elements:
                elem_text = elem.get_text(strip=True)
                if any(keyword in elem_text.lower() for keyword in FINANCIAL_KEYWORDS):
                    financial_sections.append(elem_text)
        
        # Combine all text with priority to financial sections
        combined_text = ' '.join(financial_sections) + ' ' + page_text
        
        return combined_text
    
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return ""

def scrape_url_for_revenue(url):
    """Enhanced main function to scrape a URL for revenue information"""
    try:
        url = normalize_url(url)
        
        # Find potential financial pages
        financial_pages = find_financial_pages(url)
        
        if not financial_pages:
            # If no financial pages found, try the main URL
            financial_pages = [url]
        
        # Scrape up to 8 pages concurrently
        pages_to_search = financial_pages[:8]
        all_text = []
        
        # Use concurrent futures for parallel scraping
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            future_to_url = {executor.submit(scrape_page_for_revenue, page): page for page in pages_to_search}
            
            for future in concurrent.futures.as_completed(future_to_url):
                page_url = future_to_url[future]
                try:
                    page_text = future.result()
                    if page_text.strip():
                        all_text.append(page_text)
                except Exception as e:
                    print(f"Error processing {page_url}: {e}")
        
        # If we found some text, extract revenue figure
        if all_text:
            combined_text = ' '.join(all_text)
            revenue_figure = extract_revenue_with_context(combined_text)
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

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for AWS"""
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    # Get port from environment variable for AWS compatibility
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
