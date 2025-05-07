
import { Progress } from "@/components/ui/progress";
import { Globe, Clock, CheckCircle, AlertCircle } from "lucide-react";

type Status = 'processing' | 'completed' | 'error';

interface ProcessingStatusProps {
  status: Status;
  progress: number;
  totalUrls: number;
  processedUrls: number;
  currentUrl?: string;
  error?: string;
}

const ProcessingStatus = ({
  status,
  progress,
  totalUrls,
  processedUrls,
  currentUrl,
  error
}: ProcessingStatusProps) => {
  return (
    <div className="border rounded-lg p-6 bg-card">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-medium">Processing Status</h3>
        {status === 'processing' && (
          <div className="flex items-center gap-2 text-amber-600">
            <Clock className="h-4 w-4 animate-pulse-slow" />
            <span className="text-sm font-medium">Processing</span>
          </div>
        )}
        {status === 'completed' && (
          <div className="flex items-center gap-2 text-green-600">
            <CheckCircle className="h-4 w-4" />
            <span className="text-sm font-medium">Complete</span>
          </div>
        )}
        {status === 'error' && (
          <div className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-4 w-4" />
            <span className="text-sm font-medium">Error</span>
          </div>
        )}
      </div>
      
      <Progress value={progress} className="mb-2" />
      
      <div className="flex justify-between text-sm text-muted-foreground mb-6">
        <span>Progress: {progress.toFixed(0)}%</span>
        <span>{processedUrls} of {totalUrls} URLs processed</span>
      </div>
      
      {status === 'processing' && currentUrl && (
        <div className="border rounded p-3 bg-background">
          <div className="flex items-center gap-2 text-sm mb-1">
            <Globe className="h-4 w-4 text-primary" />
            <span className="font-medium">Currently processing:</span>
          </div>
          <p className="text-sm break-all pl-6">{currentUrl}</p>
        </div>
      )}

      {status === 'error' && error && (
        <div className="border border-red-200 rounded p-3 bg-red-50 text-red-800">
          <div className="flex items-center gap-2 text-sm mb-1">
            <AlertCircle className="h-4 w-4" />
            <span className="font-medium">Error:</span>
          </div>
          <p className="text-sm break-all pl-6">{error}</p>
        </div>
      )}
    </div>
  );
};

export default ProcessingStatus;
