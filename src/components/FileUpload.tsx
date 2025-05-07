
import { useState, useRef, DragEvent, ChangeEvent } from "react";
import { cn } from "@/lib/utils";
import { Upload, FileSpreadsheet } from "lucide-react";
import { Button } from "@/components/ui/button";

interface FileUploadProps {
  onFileSelected: (file: File) => void;
}

const FileUpload = ({ onFileSelected }: FileUploadProps) => {
  const [dragActive, setDragActive] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrag = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (file.name.endsWith('.csv')) {
        processFile(file);
      }
    }
  };

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (file.name.endsWith('.csv')) {
        processFile(file);
      }
    }
  };

  const handleClick = () => {
    inputRef.current?.click();
  };

  const processFile = (file: File) => {
    setFileName(file.name);
    onFileSelected(file);
  };

  return (
    <div 
      className={cn(
        "file-drop-area", 
        dragActive ? "drag-active" : "",
        fileName ? "border-green-500 bg-green-50" : ""
      )}
      onDragEnter={handleDrag}
      onDragLeave={handleDrag}
      onDragOver={handleDrag}
      onDrop={handleDrop}
      onClick={handleClick}
    >
      <input 
        ref={inputRef}
        type="file" 
        accept=".csv" 
        className="hidden"
        onChange={handleChange}
      />
      
      {!fileName ? (
        <div className="flex flex-col items-center justify-center gap-4">
          <div className="bg-primary/10 p-4 rounded-full">
            <Upload className="h-8 w-8 text-primary animate-bounce-slow" />
          </div>
          <div>
            <h3 className="text-lg font-semibold mb-1">Upload a CSV File</h3>
            <p className="text-sm text-muted-foreground">
              Drag and drop or click to upload
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              (Only .csv files are supported)
            </p>
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center gap-4">
          <div className="bg-green-100 p-4 rounded-full">
            <FileSpreadsheet className="h-8 w-8 text-green-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold mb-1">File Ready</h3>
            <p className="text-sm text-muted-foreground">{fileName}</p>
            <Button variant="outline" size="sm" className="mt-2">
              Change file
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};

export default FileUpload;
