
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
from urllib.parse import urlparse, urljoin, quote_plus
import concurrent.futures
import os
import libretranslatepy
import json
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# Initialize LibreTranslate client
def initialize_libre_translate():
    try:
        # Check if LIBRETRANSLATE_URL is set in environment variables
        libretranslate_url = os.environ.get('LIBRETRANSLATE_URL', 'https://libretranslate.com')
        libretranslate_api_key = os.environ.get('LIBRETRANSLATE_API_KEY', '')
        
        print(f"Initializing LibreTranslate with URL: {libretranslate_url}")
        translator = libretranslatepy.LibreTranslateAPI(libretranslate_url, api_key=libretranslate_api_key)
        
        # Test connection by getting available languages
        languages = translator.languages()
        print(f"LibreTranslate available languages: {languages}")
        return translator
    except Exception as e:
        print(f"Error initializing LibreTranslate: {e}")
        print("Translation features may not be available")
        return None

# Initialize LibreTranslate on startup
TRANSLATOR = initialize_libre_translate()

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

# Common paths that might contain revenue information
FINANCIAL_PAGES = [
    'about', 'about-us', 'about-company', 'company', 'corporate',
    'investor', 'investors', 'investor-relations', 'financials',
    'financial-information', 'annual-report', 'annual-reports',
    'reports', 'results', 'earnings', 'press', 'press-releases',
    'news', 'media', 'company-information'
]

# Year priority order: 2025, 2024, 2023
PRIORITY_YEARS = ['2025', '2024', '2023']

# Languages to look for when country is provided
COUNTRY_LANGUAGE_MAP = {
    'USA': 'en',
    'United States': 'en',
    'UK': 'en',
    'United Kingdom': 'en',
    'France': 'fr',
    'Germany': 'de',
    'Spain': 'es',
    'Italy': 'it',
    'Japan': 'ja',
    'China': 'zh',
    'Russia': 'ru',
    'Brazil': 'pt',
    'Mexico': 'es',
    'Canada': 'en',
    'India': 'en',
    'Australia': 'en',
    'Netherlands': 'nl',
    'Sweden': 'sv',
    'Norway': 'no',
    'Denmark': 'da',
    'Finland': 'fi',
    'South Korea': 'ko',
    'Portugal': 'pt',
    'Greece': 'el',
    'Turkey': 'tr',
    # Add more country-language mappings as needed
}

# Trusted financial news sources for search queries
TRUSTED_SOURCES = [
    'investing.com',
    'reuters.com',
    'bloomberg.com',
    'cnbc.com',
    'wsj.com',
    'ft.com',
    'finance.yahoo.com',
    'seekingalpha.com',
    'marketwatch.com',
    'fool.com',
    'forbes.com',
    'businessinsider.com',
    'nasdaq.com',
    'sec.gov'
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

def translate_keywords(keywords, target_language):
    """Translate financial keywords to target language using LibreTranslate"""
    try:
        # Skip translation if target language is English or translator not available
        if target_language == 'en' or TRANSLATOR is None:
            return keywords
            
        translated = []
        for keyword in keywords:
            try:
                result = TRANSLATOR.translate(keyword, "en", target_language)
                translated.append(result.lower())
            except Exception as e:
                print(f"Error translating keyword '{keyword}': {e}")
                translated.append(keyword)  # Keep original if translation fails
                
        return translated
    except Exception as e:
        print(f"Translation service error: {e}")
        return keywords  # Return original keywords if translation fails

def get_language_for_country(country):
    """Get language code for a given country"""
    if not country:
        return 'en'
        
    # Normalize country name by removing spaces and converting to lowercase
    normalized_country = country.strip().lower()
    
    for c, lang in COUNTRY_LANGUAGE_MAP.items():
        if c.lower() == normalized_country:
            return lang
            
    return 'en'  # Default to English if country not found

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
    
    # Year-specific patterns with priority: 2025, 2024, 2023
    year_specific_patterns = []
    
    # Generate patterns for each priority year
    for year in PRIORITY_YEARS:
        short_year = year[-2:]  # Get last 2 digits (e.g., "23" from "2023")
        year_patterns = [
            f'(?:{year}|fy\\s?(?:20)?{short_year}).*?revenue.*?\\$([\d,.]+)\\s*(million|billion|trillion|m|b|t)',
            f'revenue.*?(?:{year}|fy\\s?(?:20)?{short_year}).*?\\$([\d,.]+)\\s*(million|billion|trillion|m|b|t)',
            f'(?:{year}|fy\\s?(?:20)?{short_year}).*?sales.*?\\$([\d,.]+)\\s*(million|billion|trillion|m|b|t)',
            f'sales.*?(?:{year}|fy\\s?(?:20)?{short_year}).*?\\$([\d,.]+)\\s*(million|billion|trillion|m|b|t)',
        ]
        year_specific_patterns.extend(year_patterns)
    
    # Generic revenue patterns (from existing code)
    monetary_patterns = [
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
        
        # New broader patterns (per requirements)
        r'revenue[^$\d]{0,10}[\$€£¥]?\s?([\d,.]+)\s*(million|billion|trillion|m|b|t)?',
        r'[\$€£¥]\s?([\d,.]+)\s*(million|billion|trillion|m|b|t)?\s*(?:in|of)?\s*revenue',
        r'annual (?:revenue|sales|turnover)[^$\d]{0,20}[\$€£¥]?\s?([\d,.]+)',
        r'(?:revenue|sales) (?:for|in) (?:20[23][0-9]|FY\s?(?:20)?[23][0-9])[^$\d]{0,15}[\$€£¥]?\s?([\d,.]+)',
    ]
    
    # First try to find year-specific matches (2025/2024/2023)
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
            
            # Determine year - prioritize 2025, then 2024, then 2023
            year = None
            for priority_year in PRIORITY_YEARS:
                short_year = priority_year[-2:]  # Last 2 digits
                year_patterns = [
                    priority_year, 
                    f'fy{short_year}',
                    f'fy {short_year}', 
                    f'fy20{short_year}', 
                    f'fy 20{short_year}'
                ]
                if any(p in context for p in year_patterns):
                    year = int(priority_year)
                    break
            
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
            
            # Score based on year priority
            if year == 2025:
                score += 200  # Highest priority
            elif year == 2024:
                score += 100  # Medium priority
            elif year == 2023:
                score += 50   # Lowest priority
                
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
        for pattern in monetary_patterns:
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

def search_duckduckgo_for_revenue(company_name, country=None, domain=None):
    """Search DuckDuckGo for company revenue information"""
    try:
        print(f"Searching DuckDuckGo for {company_name} revenue...")
        search_results = []
        
        # Create a search query that combines the company name, revenue, country and year
        search_queries = []
        
        # Build site-specific search if we have a domain
        site_query = ""
        if domain:
            site_query = f"site:{domain} OR "
        
        # Build search query including trusted financial sources
        trusted_sites_query = " OR ".join([f"site:{site}" for site in TRUSTED_SOURCES[:5]])  # Limit to 5 sites
        
        # Generate queries for each priority year
        for year in PRIORITY_YEARS:
            query = f"{site_query}{company_name} revenue {year} {country or ''} ({trusted_sites_query})"
            search_queries.append(query)
        
        # Search DuckDuckGo
        for query in search_queries[:2]:  # Limit to 2 queries to avoid rate limiting
            escaped_query = quote_plus(query)
            search_url = f"https://html.duckduckgo.com/html/?q={escaped_query}"
            
            try:
                response = requests.get(
                    search_url,
                    headers=HEADERS,
                    timeout=15
                )
                response.raise_for_status()
                
                # Parse HTML response
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract result snippets
                results = soup.find_all('div', {'class': 'result__snippet'})
                if not results:
                    # Alternative class names
                    results = soup.find_all('div', {'class': ['snippet', 'result-snippet']})
                
                for result in results[:5]:  # Get top 5 results
                    result_text = result.get_text(strip=True)
                    search_results.append(result_text)
                    
                # Also get the result links to potentially scrape them
                result_links = soup.find_all('a', {'class': 'result__a'}) 
                if not result_links:
                    result_links = soup.find_all('a', {'class': ['result-link', 'result__url']})
                
                result_urls = []
                for link in result_links[:3]:  # Top 3 links
                    href = link.get('href')
                    if href and not href.startswith('/'):
                        result_urls.append(href)
                
                # Try to scrape content from the result URLs
                for url in result_urls:
                    try:
                        content = fetch_with_retry(url, max_retries=1, timeout=10)
                        if content:
                            page_soup = BeautifulSoup(content, 'html.parser')
                            # Extract paragraphs that might contain revenue info
                            for p in page_soup.find_all(['p', 'div']):
                                p_text = p.get_text(strip=True)
                                if any(keyword in p_text.lower() for keyword in FINANCIAL_KEYWORDS):
                                    search_results.append(p_text)
                    except Exception as e:
                        print(f"Error scraping search result URL {url}: {e}")
                        continue
                        
            except Exception as e:
                print(f"Error searching DuckDuckGo: {e}")
                continue
        
        # Combine all search result texts
        all_text = " ".join(search_results)
        
        # Try to extract revenue information
        if all_text:
            revenue_figure = extract_revenue_with_context(all_text)
            if revenue_figure != "Not Found":
                return revenue_figure
                
        return "Not Found"
        
    except Exception as e:
        print(f"Error in DuckDuckGo search: {e}")
        return "Not Found"

def search_google_for_revenue(company_name, country=None, domain=None):
    """Search Google for company revenue information using default and local language"""
    try:
        print(f"Searching Google for {company_name} revenue...")
        search_results = []
        
        # Check if SerpAPI key is available
        serp_api_key = os.environ.get('SERPAPI_KEY')
        if serp_api_key:
            try:
                return search_serpapi_for_revenue(company_name, country, domain, serp_api_key)
            except Exception as e:
                print(f"SerpAPI error: {e}. Falling back to direct Google scraping.")
                
        # Determine the language to use based on the country
        local_language = get_language_for_country(country) if country else None
        
        # Build search queries with proper year priorities
        search_queries = []
        
        # English queries with priority years
        for year in PRIORITY_YEARS:
            # Base query format
            base_query = f"{company_name} annual revenue {year}"
            
            # Add domain-specific search if available
            if domain:
                search_queries.append(f"site:{domain} {base_query}")
                
            # Add trusted financial sites
            trusted_sites = " OR ".join([f"site:{site}" for site in TRUSTED_SOURCES[:3]])
            search_queries.append(f"{base_query} {country or ''} ({trusted_sites})")
            search_queries.append(f"{company_name} financial results {year} {country or ''}")
        
        # Add local language queries if available
        if local_language and local_language != 'en':
            # Translate key terms using LibreTranslate
            try:
                if TRANSLATOR:
                    # Translate key financial terms
                    revenue_translation = TRANSLATOR.translate("annual revenue", "en", local_language).lower()
                    financial_translation = TRANSLATOR.translate("financial results", "en", local_language).lower()
                    
                    # Add localized queries with years
                    for year in PRIORITY_YEARS:
                        search_queries.append(f"{company_name} {revenue_translation} {year}")
                        search_queries.append(f"{company_name} {financial_translation} {year}")
            except Exception as e:
                print(f"Translation error: {e}")
        
        # Search each query (limit to 3 to avoid rate limiting)
        for query in search_queries[:3]:
            search_url = f"https://www.google.com/search?q={quote_plus(query)}"
            try:
                html_content = fetch_with_retry(search_url)
                if not html_content:
                    continue
                    
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Extract search result descriptions
                search_results_elements = soup.select(".BNeawe, .st, .aCOpRe")
                
                for result in search_results_elements:
                    result_text = result.get_text(strip=True)
                    search_results.append(result_text)
                    
                # Try to extract links to financial pages
                result_links = soup.select("a[href^='/url?']")
                result_urls = []
                
                for link in result_links[:3]:  # Process top 3 links
                    href = link.get('href', '')
                    if 'url?' in href:
                        # Extract the actual URL from Google's redirect
                        url_param = href.split('url=')[1].split('&')[0] if 'url=' in href else ''
                        if url_param:
                            result_urls.append(url_param)
                
                # Try to scrape the result URLs
                for url in result_urls:
                    try:
                        content = fetch_with_retry(url, max_retries=2, timeout=10)
                        if content:
                            page_soup = BeautifulSoup(content, 'html.parser')
                            # Extract paragraphs with financial keywords
                            for elem in page_soup.find_all(['p', 'div', 'table']):
                                elem_text = elem.get_text(strip=True)
                                if any(kw in elem_text.lower() for kw in FINANCIAL_KEYWORDS):
                                    search_results.append(elem_text)
                    except Exception as e:
                        print(f"Error scraping search result URL {url}: {e}")
                        continue
                    
            except Exception as e:
                print(f"Error searching Google for query '{query}': {e}")
        
        # Combine all search result text
        all_text = " ".join(search_results)
        
        # Try to extract revenue information from the combined search results
        if all_text:
            revenue_figure = extract_revenue_with_context(all_text)
            if revenue_figure != "Not Found":
                return revenue_figure
                
        # If Google search doesn't work, try DuckDuckGo as fallback
        return search_duckduckgo_for_revenue(company_name, country, domain)
        
    except Exception as e:
        print(f"Error in Google search function: {e}")
        # Try DuckDuckGo as fallback
        return search_duckduckgo_for_revenue(company_name, country, domain)

def search_serpapi_for_revenue(company_name, country=None, domain=None, api_key=None):
    """Search using SerpAPI for company revenue information"""
    if not api_key:
        print("No SerpAPI key found. Skipping SerpAPI search.")
        return "Not Found"
        
    try:
        print(f"Searching via SerpAPI for {company_name} revenue...")
        
        # Build the query with domain, company name, country, and trusted sources
        domain_part = f"site:{domain} OR " if domain else ""
        trusted_sources = " OR ".join([f"site:{site}" for site in TRUSTED_SOURCES[:3]])
        
        # Build the search query for the most recent year
        query = f"{domain_part}{company_name} annual revenue {PRIORITY_YEARS[0]} {country or ''} ({trusted_sources})"
        
        # Make request to SerpAPI
        params = {
            'api_key': api_key,
            'q': query,
            'num': 10,  # Get top 10 results
        }
        
        response = requests.get('https://serpapi.com/search', params=params)
        response.raise_for_status()
        
        data = response.json()
        
        # Process the search results
        search_results = []
        
        # Extract snippets from organic results
        if 'organic_results' in data:
            for result in data['organic_results'][:5]:  # Limit to top 5
                if 'snippet' in result:
                    search_results.append(result['snippet'])
                    
                # Try to fetch and scrape the linked pages
                if 'link' in result:
                    try:
                        content = fetch_with_retry(result['link'], max_retries=1, timeout=10)
                        if content:
                            soup = BeautifulSoup(content, 'html.parser')
                            # Extract paragraphs with financial keywords
                            for p in soup.find_all(['p', 'div', 'table']):
                                p_text = p.get_text(strip=True)
                                if any(kw in p_text.lower() for kw in FINANCIAL_KEYWORDS):
                                    search_results.append(p_text)
                    except Exception as e:
                        print(f"Error scraping result link {result['link']}: {e}")
        
        # Add any knowledge graph data if available
        if 'knowledge_graph' in data and 'description' in data['knowledge_graph']:
            search_results.append(data['knowledge_graph']['description'])
            
        # Add answer box if available
        if 'answer_box' in data and 'snippet' in data['answer_box']:
            search_results.append(data['answer_box']['snippet'])
            
        # Combine all text
        all_text = " ".join(search_results)
        
        # Extract revenue figure
        if all_text:
            revenue_figure = extract_revenue_with_context(all_text)
            if revenue_figure != "Not Found":
                return revenue_figure
                
        return "Not Found"
        
    except Exception as e:
        print(f"Error in SerpAPI search: {e}")
        return "Not Found"

def scrape_url_for_revenue(url, customer_name=None, country=None):
    """Enhanced main function to scrape a URL for revenue information"""
    try:
        url = normalize_url(url)
        domain = get_domain(url)
        
        print(f"Processing: URL={url}, Customer={customer_name}, Country={country}")
        
        # Find potential financial pages
        financial_pages = find_financial_pages(url)
        
        if not financial_pages:
            # If no financial pages found, try the main URL
            financial_pages = [url]
        
        print(f"Found {len(financial_pages)} potential financial pages to scrape")
        
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
            if revenue_figure != "Not Found":
                print(f"Found revenue from website: {revenue_figure}")
                return revenue_figure
        
        # If no revenue found on website and customer name is provided, try search engines
        if customer_name:
            print(f"No revenue found on website, trying search engines for {customer_name}...")
            # Try Google search first (which includes SerpAPI if available)
            revenue_from_search = search_google_for_revenue(customer_name, country, domain)
            
            if revenue_from_search != "Not Found":
                print(f"Found revenue from search: {revenue_from_search}")
                return revenue_from_search
                
            # If Google fails, try DuckDuckGo directly
            revenue_from_ddg = search_duckduckgo_for_revenue(customer_name, country, domain)
            if revenue_from_ddg != "Not Found":
                print(f"Found revenue from DuckDuckGo: {revenue_from_ddg}")
                return revenue_from_ddg
        
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
        customer_name = data.get('customerName')  # Optional customer name
        country = data.get('country')  # Optional headquarter country
        
        print(f"API request received - URL: {url}, Customer: {customer_name}, Country: {country}")
        revenue = scrape_url_for_revenue(url, customer_name, country)
        
        return jsonify({
            'url': url,
            'revenue': revenue,
            'customerName': customer_name,
            'country': country
        })
    
    except Exception as e:
        print(f"API error: {str(e)}")
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
