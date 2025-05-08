/**
 * Parse a CSV file into an array of rows
 */
export const parseCSV = (content: string): string[][] => {
  const rows: string[][] = [];
  let currentRow: string[] = [];
  let currentValue = '';
  let inQuotes = false;
  
  // Process character by character for accurate CSV parsing
  for (let i = 0; i < content.length; i++) {
    const char = content[i];
    const nextChar = i < content.length - 1 ? content[i + 1] : '';
    
    if (char === '"') {
      if (inQuotes && nextChar === '"') {
        // Escaped quote inside quoted value
        currentValue += '"';
        i++; // Skip the next quote
      } else {
        // Toggle quote mode
        inQuotes = !inQuotes;
      }
    } else if (char === ',' && !inQuotes) {
      // End of value
      currentRow.push(currentValue.trim());
      currentValue = '';
    } else if ((char === '\n' || char === '\r') && !inQuotes) {
      // End of line
      if (currentValue.length > 0 || currentRow.length > 0) {
        currentRow.push(currentValue.trim());
        if (currentRow.some(val => val.length > 0)) {
          rows.push(currentRow);
        }
        currentRow = [];
        currentValue = '';
      }
      
      // Skip \r\n combination
      if (char === '\r' && nextChar === '\n') {
        i++;
      }
    } else {
      // Regular character
      currentValue += char;
    }
  }
  
  // Add the last row if needed
  if (currentValue.length > 0 || currentRow.length > 0) {
    currentRow.push(currentValue.trim());
    if (currentRow.some(val => val.length > 0)) {
      rows.push(currentRow);
    }
  }
  
  return rows;
};

/**
 * Convert array of rows back to CSV string
 */
export const toCSV = (rows: string[][]): string => {
  return rows.map(row => 
    row.map(value => {
      // Quote values that contain commas, quotes, or newlines
      if (value.includes(',') || value.includes('"') || value.includes('\n') || value.includes('\r')) {
        // Escape quotes by doubling them
        return `"${value.replace(/"/g, '""')}"`;
      }
      return value;
    }).join(',')
  ).join('\n');
};

/**
 * Generate a downloadable CSV file
 */
export const downloadCSV = (rows: string[][], filename: string): void => {
  const csvContent = toCSV(rows);
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  
  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', filename);
  link.style.visibility = 'hidden';
  
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};

/**
 * Format currency value according to specified format (#,##0_);(#,##0)
 * Always return in USD ($) with proper formatting and full numbers
 */
export const formatCurrencyToUSD = (value: string): string => {
  // Handle 'Not Found' case
  if (value === "Not Found") {
    return value;
  }

  try {
    // Extract the numerical value and currency
    const numericMatch = value.match(/([\d,.]+)\s*(million|billion|trillion|m|b|t)?/i);
    
    if (!numericMatch) {
      return value; // Return original if pattern doesn't match
    }
    
    // Extract the numeric part and the scale
    let numericValue = parseFloat(numericMatch[1].replace(/,/g, ''));
    const scale = numericMatch[2]?.toLowerCase();
    
    // Apply scaling factor based on the unit
    if (scale) {
      if (scale === 'million' || scale === 'm') {
        numericValue *= 1000000;
      } else if (scale === 'billion' || scale === 'b') {
        numericValue *= 1000000000;
      } else if (scale === 'trillion' || scale === 't') {
        numericValue *= 1000000000000;
      }
    }
    
    // Handle currency conversion (simplified - in a real app we'd use exchange rates)
    // Here we assume a fixed conversion rate for demonstration
    if (value.includes('€')) {
      // Convert EUR to USD (example rate: 1 EUR = 1.1 USD)
      numericValue *= 1.1;
    } else if (value.includes('£')) {
      // Convert GBP to USD (example rate: 1 GBP = 1.3 USD)
      numericValue *= 1.3;
    } else if (value.includes('¥')) {
      // Convert JPY to USD (example rate: 1 USD = 150 JPY)
      numericValue /= 150;
    }
    
    // Format according to the specified pattern (#,##0_);(#,##0)
    const formatter = new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      maximumFractionDigits: 0,
      minimumFractionDigits: 0,
    });
    
    // Return the full number with proper formatting
    return formatter.format(numericValue);
  } catch (error) {
    console.error("Error formatting currency:", error);
    return value; // Return the original value in case of error
  }
};
