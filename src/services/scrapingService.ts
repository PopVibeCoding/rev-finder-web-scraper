
// This is a mock service to simulate the API calls that would be made to a Python backend
// In a real application, these would be API calls to a backend service

const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

// Simulate different revenue responses
const revenueResponses = [
  "$45 million",
  "€12.3B",
  "$1.2 billion",
  "¥350 million",
  "£89.7M",
  "$750M annual revenue",
  "Not Found",
  "Revenue: $230 million",
  "Annual revenue of $5.7B",
  "$120-150M revenue"
];

/**
 * Simulates a scraping operation for a single URL
 */
export const scrapeUrlForRevenue = async (url: string): Promise<string> => {
  // Simulate network request and processing time
  await sleep(Math.random() * 2000 + 1000);
  
  // Simulate failures for some URLs
  if (Math.random() < 0.2 || !url.startsWith('http')) {
    return "Not Found";
  }
  
  // Return a random revenue response
  return revenueResponses[Math.floor(Math.random() * revenueResponses.length)];
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
      
      // Add revenue to this row
      outputRows[i] = [...outputRows[i], revenue];
    } catch (error) {
      // Handle error for this row
      outputRows[i] = [...outputRows[i], "Not Found"];
    }
  }
  
  return outputRows;
};
