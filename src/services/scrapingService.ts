
// This service connects to the Python backend for web scraping operations

import { formatCurrencyToUSD } from '../utils/csvUtils';

// Update to support both local and network address
const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
  ? 'http://127.0.0.1:5000' 
  : 'http://192.168.6.186:5000';

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * Makes a request to the Python backend with retry logic
 */
const makeRequestWithRetry = async <T>(
  url: string, 
  options: RequestInit = {}, 
  maxRetries = 3
): Promise<T> => {
  let lastError: Error | null = null;
  
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      // Add exponential backoff between retries
      if (attempt > 0) {
        const delay = Math.pow(2, attempt) * 1000; // 2, 4, 8... seconds
        await sleep(delay);
      }
      
      const response = await fetch(url, options);
      
      if (!response.ok) {
        throw new Error(`Server responded with status: ${response.status}`);
      }
      
      return await response.json() as T;
    } catch (error) {
      console.error(`Attempt ${attempt + 1}/${maxRetries} failed:`, error);
      lastError = error instanceof Error ? error : new Error(String(error));
      
      // Only continue if we haven't reached max retries
      if (attempt === maxRetries - 1) {
        throw new Error(`Failed after ${maxRetries} attempts: ${lastError.message}`);
      }
    }
  }
  
  // This should never happen due to the throw inside the loop
  throw new Error('Request failed with retry');
};

/**
 * Scrapes a URL for revenue information using the Python backend API
 */
export const scrapeUrlForRevenue = async (url: string): Promise<string> => {
  try {
    if (!url.startsWith('http')) {
      url = 'https://' + url;
    }
    
    const response = await makeRequestWithRetry<{ url: string; revenue: string }>(
      `${API_BASE_URL}/api/scrape`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      }
    );
    
    return response.revenue || "Not Found";
  } catch (error) {
    console.error(`Error calling Python scraper API for ${url}:`, error);
    return "Not Found";
  }
};

/**
 * Process CSV data by adding revenue information
 */
export const processCSVData = async (
  rows: string[][],
  onProgress: (progress: number, url: string, processedUrls: number) => void
): Promise<string[][]> => {
  // Make a copy of the input rows
  const outputRows = [...rows];
  
  // Add header for new column if needed
  if (outputRows.length > 0) {
    outputRows[0] = [...outputRows[0], "Web Company Revenue"];
  }
  
  // Process each row (skip header)
  for (let i = 1; i < outputRows.length; i++) {
    try {
      const url = outputRows[i][0];
      
      // Update progress
      onProgress(
        (i / (outputRows.length - 1)) * 100,
        url,
        i
      );
      
      // Scrape revenue for this URL
      const revenue = await scrapeUrlForRevenue(url);
      
      // Format the revenue in USD with proper formatting
      const formattedRevenue = formatCurrencyToUSD(revenue);
      
      // Add revenue to this row
      outputRows[i] = [...outputRows[i], formattedRevenue];
    } catch (error) {
      // Handle error for this row
      outputRows[i] = [...outputRows[i], "Not Found"];
    }
  }
  
  return outputRows;
};
