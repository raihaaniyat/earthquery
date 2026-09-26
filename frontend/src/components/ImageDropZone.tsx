import React, { useState } from 'react';
import { PlusIcon, XIcon, FileImageIcon } from 'lucide-react';
import { formatBytes } from '../utils/files';
import type { AttachedImage } from '../types/app';

interface ImageDropZoneProps {
  label: string;
  hint: string;
  image: AttachedImage | null;
  onFile: (file: File) => void;
  onClear: () => void;
}

export function ImageDropZone({ label, hint, image, onFile, onClear }: ImageDropZoneProps) {
  const [dragging, setDragging] = useState(false);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) onFile(f);
  };

  return (
    <div
      className={`drop${image ? ' has-image' : ''}${dragging ? ' dragging' : ''}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}>
      
      {image ?
      <>
          {image.previewable ?
        <img className="drop-preview" src={image.url} alt={`${label} preview`} /> :

        <div className="curtain-empty">
              <FileImageIcon size={22} />
              <span>Preview not supported in the browser — file kept for backend upload.</span>
            </div>
        }
          <span className="drop-tag">{label}</span>
          <div className="drop-caption">
            <span>
              {image.name} · {image.previewable ? `${image.width}×${image.height}` : formatBytes(image.size)}
            </span>
            <label className="btn small file-btn">
              Replace
              <input
              type="file"
              accept="image/png,image/jpeg,image/webp,.tif,.tiff"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) onFile(f);
                e.target.value = '';
              }} />
            
            </label>
            <button className="btn small" onClick={onClear} aria-label={`Remove ${label} image`}>
              <XIcon size={12} />
            </button>
          </div>
        </> :

      <>
          <PlusIcon size={22} />
          <strong>{label}</strong>
          <p>{hint}</p>
          <label className="btn small file-btn">
            Browse
            <input
            type="file"
            accept="image/png,image/jpeg,image/webp,.tif,.tiff"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onFile(f);
              e.target.value = '';
            }} />
          
          </label>
        </>
      }
    </div>);

}