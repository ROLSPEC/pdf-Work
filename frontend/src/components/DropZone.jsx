import { useDropzone } from "react-dropzone";
import { UploadSimple } from "@phosphor-icons/react";

export default function DropZone({ onFiles, multiple = false, accept, hint = "PDF up to 25MB", testId = "dropzone" }) {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: accept || { "application/pdf": [".pdf"] },
    multiple,
    onDrop: (files) => onFiles && onFiles(multiple ? files : files.slice(0, 1)),
  });
  return (
    <div
      {...getRootProps()}
      data-testid={testId}
      className={`relative brut brut-hover cursor-pointer bg-card px-6 py-16 text-center ${isDragActive ? "bg-primary/20 -translate-y-1" : ""}`}
    >
      <input {...getInputProps()} data-testid={`${testId}-input`} />
      {/* Corner tick marks */}
      <span className="absolute top-2 left-2 font-mono text-[10px] text-muted-foreground">↳ drop</span>
      <span className="absolute top-2 right-2 font-mono text-[10px] text-muted-foreground">.pdf</span>
      <span className="absolute bottom-2 left-2 font-mono text-[10px] text-muted-foreground">01 / 46</span>
      <span className="absolute bottom-2 right-2 font-mono text-[10px] text-muted-foreground">click ⌘</span>

      <div className={`mx-auto w-16 h-16 brut-sm bg-white text-ink flex items-center justify-center mb-4 ${isDragActive ? "sticker-rotate-l" : ""}`}>
        <UploadSimple size={28} weight="bold" />
      </div>
      <div className="font-display text-2xl">
        {isDragActive ? "DROP IT!" : "Drop file here"}
      </div>
      <div className="text-xs font-mono uppercase tracking-widest text-muted-foreground mt-2">
        — or click to browse — {hint} —
      </div>
    </div>
  );
}
