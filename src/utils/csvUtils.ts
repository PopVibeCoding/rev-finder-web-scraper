
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
