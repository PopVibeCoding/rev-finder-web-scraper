
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/use-toast";
import FileUpload from "@/components/FileUpload";
import ProcessingStatus from "@/components/ProcessingStatus";
import ResultsTable from "@/components/ResultsTable";
import { parseCSV, downloadCSV } from "@/utils/csvUtils";
import { processCSVData } from "@/services/scrapingService";
import { Database, FileSearch, Download } from "lucide-react";

type AppStatus = "idle" | "processing" | "completed" | "error";

interface ResultData {
  url: string;
  revenue: string;
}

const Index = () => {
  const { toast } = useToast();
  const [status, setStatus] = useState<AppStatus>("idle");
  const [progress, setProgress] = useState(0);
  const [currentUrl, setCurrentUrl] = useState<string>("");
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [processedUrls, setProcessedUrls] = useState(0);
  const [totalUrls, setTotalUrls] = useState(0);
  const [results, setResults] = useState<ResultData[]>([]);
  const [processedData, setProcessedData] = useState<string[][]>([]);
  const [error, setError] = useState<string>("");

  const handleFileSelected = (file: File) => {
    setCsvFile(file);
    setStatus("idle");
    setProgress(0);
    setResults([]);
    setProcessedData([]);
    setError("");
  };

  const handleProcess = async () => {
    if (!csvFile) {
      toast({
        title: "Error",
        description: "Please upload a CSV file first.",
        variant: "destructive",
      });
      return;
    }

    try {
      setStatus("processing");
      setProgress(0);
      setCurrentUrl("");
      setProcessedUrls(0);
      setResults([]);
      setError("");

      // Read file content
      const content = await csvFile.text();
      const rows = parseCSV(content);
      
      if (rows.length < 2) {
        throw new Error("CSV file doesn't contain enough data or is improperly formatted");
      }
      
      setTotalUrls(rows.length - 1); // Minus header row

      // Process the data
      const enrichedData = await processCSVData(
        rows,
        (progress, url, processed) => {
          setProgress(progress);
          setCurrentUrl(url);
          setProcessedUrls(processed);
        }
      );

      // Store the processed data
      setProcessedData(enrichedData);
      
      // Extract results for preview
      const resultData: ResultData[] = [];
      for (let i = 1; i < enrichedData.length; i++) {
        resultData.push({
          url: enrichedData[i][0],
          revenue: enrichedData[i][enrichedData[i].length - 1] || "Not Found",
        });
      }
      setResults(resultData);
      setStatus("completed");

      toast({
        title: "Processing Complete",
        description: `Successfully processed ${rows.length - 1} URLs.`,
      });
    } catch (err) {
      setStatus("error");
      const errorMessage = err instanceof Error ? err.message : "An unknown error occurred";
      setError(errorMessage);
      
      toast({
        title: "Processing Failed",
        description: errorMessage,
        variant: "destructive",
      });
    }
  };

  const handleDownload = () => {
    if (processedData.length > 0) {
      const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
      downloadCSV(processedData, `revenue-enriched-${timestamp}.csv`);
      
      toast({
        title: "Download Complete",
        description: "Your enriched CSV file has been downloaded.",
      });
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-card">
        <div className="container py-4">
          <div className="flex items-center gap-2">
            <FileSearch className="h-6 w-6 text-primary" />
            <h1 className="text-2xl font-bold">Web Revenue Extractor</h1>
          </div>
          <p className="text-muted-foreground mt-1">
            Enrich your CSV data with company revenue information from websites
          </p>
        </div>
      </header>
      
      <main className="container py-8">
        <div className="grid gap-8 md:grid-cols-2 lg:grid-cols-3">
          <div className="lg:col-span-1">
            <div className="sticky top-8 space-y-6">
              <div className="border rounded-lg p-6 bg-card">
                <h2 className="text-xl font-semibold mb-4">
                  How It Works
                </h2>
                <ol className="space-y-4">
                  <li className="flex gap-4">
                    <div className="bg-primary/10 rounded-full p-2 h-8 w-8 flex items-center justify-center text-primary font-medium">
                      1
                    </div>
                    <div className="flex-1">
                      <h3 className="font-medium">Upload CSV</h3>
                      <p className="text-sm text-muted-foreground">
                        Upload a CSV file with website URLs in the first column
                      </p>
                    </div>
                  </li>
                  
                  <li className="flex gap-4">
                    <div className="bg-primary/10 rounded-full p-2 h-8 w-8 flex items-center justify-center text-primary font-medium">
                      2
                    </div>
                    <div className="flex-1">
                      <h3 className="font-medium">Process Data</h3>
                      <p className="text-sm text-muted-foreground">
                        Our system will extract revenue data from each website
                      </p>
                    </div>
                  </li>
                  
                  <li className="flex gap-4">
                    <div className="bg-primary/10 rounded-full p-2 h-8 w-8 flex items-center justify-center text-primary font-medium">
                      3
                    </div>
                    <div className="flex-1">
                      <h3 className="font-medium">Download Results</h3>
                      <p className="text-sm text-muted-foreground">
                        Get your enriched CSV with revenue information added
                      </p>
                    </div>
                  </li>
                </ol>
              </div>
              
              <FileUpload onFileSelected={handleFileSelected} />
              
              <div className="flex flex-col gap-3">
                <Button 
                  onClick={handleProcess} 
                  disabled={!csvFile || status === "processing"}
                  className="flex gap-2"
                >
                  <Database className="h-4 w-4" />
                  Process URLs
                </Button>
                
                <Button 
                  onClick={handleDownload} 
                  variant="outline" 
                  disabled={status !== "completed"}
                  className="flex gap-2"
                >
                  <Download className="h-4 w-4" />
                  Download Enriched CSV
                </Button>
              </div>
            </div>
          </div>
          
          <div className="md:col-span-2 space-y-8">
            {(status === "processing" || status === "completed" || status === "error") && (
              <ProcessingStatus 
                status={status}
                progress={progress}
                totalUrls={totalUrls}
                processedUrls={processedUrls}
                currentUrl={currentUrl}
                error={error}
              />
            )}
            
            {status === "completed" && results.length > 0 && (
              <ResultsTable results={results} />
            )}
            
            {status === "idle" && (
              <div className="rounded-lg border border-dashed bg-card/50 p-12">
                <div className="text-center space-y-4">
                  <Database className="h-12 w-12 text-muted-foreground mx-auto opacity-50" />
                  <h3 className="text-xl font-medium">Ready to Process</h3>
                  <p className="text-muted-foreground max-w-md mx-auto">
                    Upload a CSV file with company URLs, then click "Process URLs" 
                    to begin extracting revenue information.
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
      
      <footer className="border-t py-6 mt-20">
        <div className="container">
          <p className="text-center text-sm text-muted-foreground">
            Web Revenue Extractor — A powerful tool to extract revenue data from company websites
          </p>
        </div>
      </footer>
    </div>
  );
};

export default Index;
