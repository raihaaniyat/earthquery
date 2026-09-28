import React, { useRef, useState } from 'react';
import { UploadCloudIcon, CheckCircle2Icon, AlertCircleIcon, FileIcon, Loader2Icon, SparklesIcon } from 'lucide-react';
import { loadGeoTiffFile } from '../../utils/geotiff';
import type { GeoTiffLayer, GeoTiffProcessState } from '../../types/geotiff';

interface Props {
  onLayerLoaded: (layer: GeoTiffLayer) => void;
  onError?: (error: string) => void;
}

export function GeoTiffUploader({ onLayerLoaded, onError }: Props) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [processState, setProcessState] = useState<GeoTiffProcessState>({
    stage: 'idle',
    message: ''
  });

  const handleFile = async (file: File) => {
    const name = file.name.toLowerCase();
    if (!name.endsWith('.tif') && !name.endsWith('.tiff')) {
      const msg = 'This file is not a valid GeoTIFF (.tif or .tiff).';
      setProcessState({ stage: 'error', message: msg, error: msg });
      onError?.(msg);
      return;
    }

    try {
      const layer = await loadGeoTiffFile(file, (state) => {
        setProcessState(state);
      });
      onLayerLoaded(layer);
      setTimeout(() => {
        setProcessState({ stage: 'idle', message: '' });
      }, 2500);
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : String(err);
      setProcessState({
        stage: 'error',
        message: errMsg,
        error: errMsg
      });
      onError?.(errMsg);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      void handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      void handleFile(e.target.files[0]);
      e.target.value = '';
    }
  };

  const loadSample = async (url: string, filename: string) => {
    try {
      setProcessState({ stage: 'reading', message: `Fetching sample ${filename}...`, progressPercent: 10 });
      const res = await fetch(url);
      if (!res.ok) throw new Error(`Failed to fetch sample (${res.statusText})`);
      const blob = await res.blob();
      const file = new File([blob], filename, { type: 'image/tiff' });
      await handleFile(file);
    } catch (err) {
      const msg = `Unable to load sample: ${String(err)}`;
      setProcessState({ stage: 'error', message: msg, error: msg });
      onError?.(msg);
    }
  };

  const isBusy = processState.stage !== 'idle' && processState.stage !== 'error' && processState.stage !== 'success';

  return (
    <div className="geotiff-uploader-container">
      <div
        className={`geotiff-dropzone ${dragOver ? 'dragover' : ''} ${isBusy ? 'busy' : ''}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => !isBusy && fileInputRef.current?.click()}
        role="button"
        tabIndex={0}
        aria-label="Upload GeoTIFF"
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".tif,.tiff,image/tiff"
          style={{ display: 'none' }}
          onChange={handleInputChange}
          disabled={isBusy}
        />

        <div className="dropzone-content">
          {isBusy ? (
            <div className="dropzone-status">
              <Loader2Icon className="spin" size={32} style={{ color: 'var(--accent)' }} />
              <div className="status-title">{processState.message}</div>
              {processState.progressPercent !== undefined && (
                <div className="progress-bar-bg">
                  <div
                    className="progress-bar-fill"
                    style={{ width: `${processState.progressPercent}%` }}
                  />
                </div>
              )}
            </div>
          ) : processState.stage === 'success' ? (
            <div className="dropzone-status success">
              <CheckCircle2Icon size={32} style={{ color: 'var(--ok)' }} />
              <div className="status-title">{processState.message}</div>
              <small className="muted">Zooming to exact geographic extent...</small>
            </div>
          ) : (
            <>
              <div className="dropzone-icon">
                <UploadCloudIcon size={34} style={{ color: 'var(--accent)' }} />
              </div>
              <div className="dropzone-prompt">
                <b>Click to upload</b> or drag & drop GeoTIFF
              </div>
              <span className="dropzone-hint">
                Supports <code>.tif</code> and <code>.tiff</code> · EPSG:4326, UTM, Web Mercator & projected CRS
              </span>
            </>
          )}
        </div>
      </div>

      {processState.stage === 'error' && (
        <div className="geotiff-error-notice">
          <AlertCircleIcon size={18} style={{ color: 'var(--danger)', flexShrink: 0 }} />
          <div className="error-text">
            <strong>GeoTIFF Error:</strong> {processState.error}
          </div>
          <button
            className="btn small"
            onClick={(e) => {
              e.stopPropagation();
              setProcessState({ stage: 'idle', message: '' });
            }}
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="sample-strip">
        <span className="sample-label">
          <SparklesIcon size={13} style={{ color: 'var(--accent)' }} /> Quick test samples:
        </span>
        <button
          className="btn small"
          onClick={() => void loadSample('/samples/bengaluru_4326.tif', 'bengaluru_s2_4326.tif')}
          disabled={isBusy}
          title="Bengaluru Sentinel-2 4-band GeoTIFF in EPSG:4326"
        >
          <FileIcon size={12} /> Bengaluru (EPSG:4326)
        </button>
        <button
          className="btn small"
          onClick={() => void loadSample('/samples/denver_utm_32613.tif', 'denver_s2_utm13.tif')}
          disabled={isBusy}
          title="Denver Colorado Sentinel-2 RGB in UTM Zone 13N (EPSG:32613)"
        >
          <FileIcon size={12} /> Denver (UTM Zone 13N)
        </button>
        <button
          className="btn small"
          onClick={() => void loadSample('/samples/test_geo_4326.tif', 'test_geo_4326.tif')}
          disabled={isBusy}
          title="Baseline small raster in EPSG:4326"
        >
          <FileIcon size={12} /> Test Raster (Small)
        </button>
      </div>
    </div>
  );
}
