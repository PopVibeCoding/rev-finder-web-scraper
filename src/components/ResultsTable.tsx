
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ExternalLink, DollarSign, AlertCircle } from "lucide-react";

interface ResultData {
  url: string;
  revenue: string;
}

interface ResultsTableProps {
  results: ResultData[];
}

const ResultsTable = ({ results }: ResultsTableProps) => {
  // Only show first 5 rows in preview
  const previewResults = results.slice(0, 5);
  
  return (
    <div className="border rounded-lg p-6 bg-card">
      <h3 className="text-lg font-medium mb-4">Results Preview</h3>
      <div className="rounded-md border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[60%]">URL</TableHead>
              <TableHead>Web Company Revenue</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {previewResults.map((row, index) => (
              <TableRow key={index}>
                <TableCell className="font-mono text-sm">
                  <div className="flex items-center gap-2 truncate">
                    <ExternalLink className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                    <span className="truncate">{row.url}</span>
                  </div>
                </TableCell>
                <TableCell>
                  {row.revenue === "Not Found" ? (
                    <div className="flex items-center gap-2 text-amber-600">
                      <AlertCircle className="h-4 w-4" />
                      <span>{row.revenue}</span>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 text-green-600">
                      <DollarSign className="h-4 w-4" />
                      <span>{row.revenue}</span>
                    </div>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {results.length > 5 && (
        <p className="text-xs text-muted-foreground mt-2 text-right">
          Showing 5 of {results.length} results
        </p>
      )}
    </div>
  );
};

export default ResultsTable;
