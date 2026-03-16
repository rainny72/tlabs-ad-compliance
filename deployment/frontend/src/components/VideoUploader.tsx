import { useState, useRef } from 'react';
import { getUploadUrl } from '../services/api';

const ACCEPTED_EXTENSIONS = ['mp4', 'mov', 'avi', 'mkv'];
const ACCEPT_STRING = ACCEPTED_EXTENSIONS.map((ext) => `.${ext}`).join(',');
const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25MB

const CONTENT_TYPE_MAP: Record<string, string> = {
  mp4: 'video/mp4',
  mov: 'video/quicktime',
  avi: 'video/x-msvideo',
  mkv: 'video/x-matroska',
};

export interface VideoUploaderProps {
  onUploadComplete: (s3Key: string, filename: string) => void;
  onFileSelected?: (file: File | null) => void;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getExtension(filename: string): string {
  return filename.split('.').pop()?.toLowerCase() ?? '';
}

export default function VideoUploader({ onUploadComplete, onFileSelected }: VideoUploaderProps) {
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    setError(null);
    setProgress(0);
    const selected = e.target.files?.[0];
    if (!selected) return;

    const ext = getExtension(selected.name);
    if (!ACCEPTED_EXTENSIONS.includes(ext)) {
      setError(`Unsupported file type. Accepted: ${ACCEPTED_EXTENSIONS.join(', ')}`);
      setFile(null);
      return;
    }

    if (selected.size > MAX_FILE_SIZE) {
      setError(`File too large. Maximum size is ${formatFileSize(MAX_FILE_SIZE)}.`);
      setFile(null);
      return;
    }

    setFile(selected);
    onFileSelected?.(selected);
  }

  async function handleUpload() {
    if (!file) return;
    setError(null);
    setUploading(true);
    setProgress(0);

    try {
      const ext = getExtension(file.name);
      const contentType = CONTENT_TYPE_MAP[ext] ?? 'application/octet-stream';
      const { uploadUrl, s3Key } = await getUploadUrl(file.name, contentType);

      await new Promise<void>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('PUT', uploadUrl);
        xhr.setRequestHeader('Content-Type', contentType);

        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            setProgress(Math.round((e.loaded / e.total) * 100));
          }
        };

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve();
          } else {
            reject(new Error(`Upload failed with status ${xhr.status}`));
          }
        };

        xhr.onerror = () => reject(new Error('Network error during upload'));
        xhr.send(file);
      });

      onUploadComplete(s3Key, file.name);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Upload failed. Please try again.';
      setError(message);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: '1.5rem' }}>
      <div>
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPT_STRING}
          onChange={handleFileChange}
          disabled={uploading}
          aria-label="Select video file"
        />
      </div>

      {file && (
        <p style={{ margin: '0.75rem 0', color: '#555' }}>
          {file.name} ({formatFileSize(file.size)})
        </p>
      )}

      {error && (
        <p role="alert" style={{ color: '#d32f2f', margin: '0.75rem 0' }}>
          {error}
        </p>
      )}

      {uploading && (
        <div style={{ margin: '0.75rem 0' }}>
          <div
            style={{
              width: '100%',
              height: 8,
              backgroundColor: '#e0e0e0',
              borderRadius: 4,
              overflow: 'hidden',
            }}
          >
            <div
              role="progressbar"
              aria-valuenow={progress}
              aria-valuemin={0}
              aria-valuemax={100}
              style={{
                width: `${progress}%`,
                height: '100%',
                backgroundColor: '#1976d2',
                transition: 'width 0.2s',
              }}
            />
          </div>
          <p style={{ fontSize: '0.875rem', color: '#555', marginTop: 4 }}>{progress}%</p>
        </div>
      )}

      <button
        onClick={handleUpload}
        disabled={!file || uploading}
        style={{
          marginTop: '0.5rem',
          padding: '0.5rem 1.5rem',
          cursor: !file || uploading ? 'not-allowed' : 'pointer',
          backgroundColor: file && !uploading ? '#1976d2' : '#e0e0e0',
          color: file && !uploading ? '#fff' : '#999',
          border: 'none',
          borderRadius: 6,
          fontWeight: 600,
          fontSize: '0.9rem',
          transition: 'background-color 0.2s',
        }}
      >
        {uploading ? 'Uploading...' : 'Upload'}
      </button>
    </div>
  );
}
