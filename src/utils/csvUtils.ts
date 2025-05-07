
/**
 * Parse a CSV file into an array of rows
 */
export const parseCSV = (content: string): string[][] => {
  const rows = content.split('\n').map(row => {
    // Handle quoted values that might contain commas
    const matches = row.match(/(".*?"|[^",\s]+)(?=\s*,|\s*$)/g) || [];
    return matches.map(value => value.replace(/^"|"$/g, '').trim());
  });
  
  // Filter out empty rows
  return rows.filter(row => row.length > 0 && row.some(cell => cell.trim() !== ''));
};

/**
 * Convert array of rows back to CSV string
 */
export const toCSV = (rows: string[][]): string => {
  return rows.map(row => 
    row.map(value => 
      // Quote values that contain commas
      value.includes(',') ? `"${value}"` : value
    ).join(',')
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
