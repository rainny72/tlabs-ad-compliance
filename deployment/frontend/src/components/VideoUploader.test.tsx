import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import VideoUploader from './VideoUploader';

vi.mock('../services/api', () => ({
  getUploadUrl: vi.fn(),
}));

import { getUploadUrl } from '../services/api';
const mockGetUploadUrl = vi.mocked(getUploadUrl);

function createFile(name: string, size: number, type = 'video/mp4'): File {
  const buffer = new ArrayBuffer(size);
  return new File([buffer], name, { type });
}

describe('VideoUploader', () => {
  const onUploadComplete = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders file input and upload button', () => {
    render(<VideoUploader onUploadComplete={onUploadComplete} />);
    expect(screen.getByLabelText('Select video file')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /upload/i })).toBeDisabled();
  });

  it('shows file name and size after selection', () => {
    render(<VideoUploader onUploadComplete={onUploadComplete} />);
    const input = screen.getByLabelText('Select video file');
    const file = createFile('test.mp4', 1024 * 1024);
    fireEvent.change(input, { target: { files: [file] } });
    expect(screen.getByText(/test\.mp4/)).toBeInTheDocument();
    expect(screen.getByText(/1\.0 MB/)).toBeInTheDocument();
  });

  it('rejects unsupported file types', () => {
    render(<VideoUploader onUploadComplete={onUploadComplete} />);
    const input = screen.getByLabelText('Select video file');
    const file = createFile('test.txt', 100);
    fireEvent.change(input, { target: { files: [file] } });
    expect(screen.getByRole('alert')).toHaveTextContent('Unsupported file type');
  });

  it('rejects files exceeding 25MB', () => {
    render(<VideoUploader onUploadComplete={onUploadComplete} />);
    const input = screen.getByLabelText('Select video file');
    const file = createFile('big.mp4', 26 * 1024 * 1024);
    fireEvent.change(input, { target: { files: [file] } });
    expect(screen.getByRole('alert')).toHaveTextContent('File too large');
  });

  it('accepts valid video extensions (mov, avi, mkv)', () => {
    render(<VideoUploader onUploadComplete={onUploadComplete} />);
    const input = screen.getByLabelText('Select video file');

    for (const ext of ['mov', 'avi', 'mkv']) {
      const file = createFile(`video.${ext}`, 1000);
      fireEvent.change(input, { target: { files: [file] } });
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    }
  });

  it('enables upload button after valid file selection', () => {
    render(<VideoUploader onUploadComplete={onUploadComplete} />);
    const input = screen.getByLabelText('Select video file');
    const file = createFile('test.mp4', 1000);
    fireEvent.change(input, { target: { files: [file] } });
    expect(screen.getByRole('button', { name: /upload/i })).toBeEnabled();
  });

  it('calls onUploadComplete after successful upload', async () => {
    mockGetUploadUrl.mockResolvedValue({
      uploadUrl: 'https://s3.example.com/presigned',
      s3Key: 'uploads/user1/123_test.mp4',
    });

    // Mock XMLHttpRequest
    const xhrMock: Partial<XMLHttpRequest> = {
      open: vi.fn(),
      setRequestHeader: vi.fn(),
      send: vi.fn(function (this: XMLHttpRequest) {
        // Simulate successful upload
        if (this.onload) {
          Object.defineProperty(this, 'status', { value: 200 });
          this.onload(new ProgressEvent('load'));
        }
      }),
      upload: { onprogress: null } as unknown as XMLHttpRequestUpload,
    };
    vi.spyOn(window, 'XMLHttpRequest').mockImplementation(
      () => xhrMock as XMLHttpRequest,
    );

    render(<VideoUploader onUploadComplete={onUploadComplete} />);
    const input = screen.getByLabelText('Select video file');
    const file = createFile('test.mp4', 1000);
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole('button', { name: /upload/i }));

    await waitFor(() => {
      expect(onUploadComplete).toHaveBeenCalledWith(
        'uploads/user1/123_test.mp4',
        'test.mp4',
      );
    });
  });

  it('shows error on upload failure', async () => {
    mockGetUploadUrl.mockRejectedValue(new Error('Network error'));

    render(<VideoUploader onUploadComplete={onUploadComplete} />);
    const input = screen.getByLabelText('Select video file');
    const file = createFile('test.mp4', 1000);
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole('button', { name: /upload/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Network error');
    });
  });
});
