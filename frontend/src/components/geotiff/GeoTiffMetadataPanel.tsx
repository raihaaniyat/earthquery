import React from 'react';
import { CopyIcon, CheckIcon, InfoIcon, GlobeIcon, LayersIcon, HardDriveIcon, AlertTriangleIcon } from 'lucide-react';
import { formatBytes } from '../../utils/geotiff';
import type { GeoTiffMetadata } from '../../types/geotiff';

interface Props {
  metadata: GeoTiffMetadata | null;
  onCopyCoordinates?: (text: string) => void;
}

export function GeoTiffMetadataPanel({ metadata, onCopyCoordinates }: Props) {
  const [copied, setCopied] = React.useState(false);

  if (!metadata) {
    return (
      <div className="geotiff-meta-empty">
        <InfoIcon size={24} style={{ color: 'var(--muted)', opacity: 0.6 }} />
        <p>Select or upload a GeoTIFF layer to inspect embedded geospatial metadata.</p>
      </div>
    );
  }

  const { wgs84Bounds, nativeBbox, resolution, origin } = metadata;

  const copyBbox = () => {
    const text = `West: ${wgs84Bounds.minLon.toFixed(6)}, South: ${wgs84Bounds.minLat.toFixed(6)}, East: ${wgs84Bounds.maxLon.toFixed(6)}, North: ${wgs84Bounds.maxLat.toFixed(6)}`;
    if (onCopyCoordinates) {
      onCopyCoordinates(text);
    } else {
      void navigator.clipboard.writeText(text);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="geotiff-metadata-card">
      <div className="meta-card-head">
        <div className="meta-title-group">
          <GlobeIcon size={16} style={{ color: 'var(--accent)' }} />
          <h4 title={metadata.fileName}>{metadata.fileName}</h4>
        </div>
        <button className="btn small" onClick={copyBbox} title="Copy geographic bounding box coordinates">
          {copied ? <CheckIcon size={12} style={{ color: 'var(--ok)' }} /> : <CopyIcon size={12} />}
          <span>{copied ? 'Copied' : 'Copy Bounds'}</span>
        </button>
      </div>

      {metadata.warnings.length > 0 && (
        <div className="meta-warning-banner">
          <AlertTriangleIcon size={14} style={{ color: 'var(--warn)', flexShrink: 0 }} />
          <span>{metadata.warnings[0]}</span>
        </div>
      )}

      <div className="meta-sections-grid">
        {/* Core & CRS */}
        <div className="meta-subgroup">
          <div className="subgroup-title">
            <GlobeIcon size={13} /> Coordinate Reference System
          </div>
          <dl className="meta-dl">
            <div>
              <dt>CRS Name</dt>
              <dd className="accent-text"><b>{metadata.crsName}</b></dd>
            </div>
            <div>
              <dt>EPSG Code</dt>
              <dd><code>{metadata.epsg ? `EPSG:${metadata.epsg}` : 'Non-standard / Geographic'}</code></dd>
            </div>
            <div>
              <dt>Origin (X, Y)</dt>
              <dd>{origin[0].toFixed(3)}, {origin[1].toFixed(3)}</dd>
            </div>
            <div>
              <dt>Pixel Resolution</dt>
              <dd>
                {Math.abs(resolution[0]).toFixed(4)} × {Math.abs(resolution[1]).toFixed(4)}
                {metadata.epsg === 4326 ? '° (deg)' : ' m (meters)'}
              </dd>
            </div>
          </dl>
        </div>

        {/* Geographic Extent (WGS84) */}
        <div className="meta-subgroup">
          <div className="subgroup-title">
            <GlobeIcon size={13} /> Geographic Extent (WGS 84)
          </div>
          <dl className="meta-dl">
            <div>
              <dt>Latitude Range</dt>
              <dd>{wgs84Bounds.minLat.toFixed(6)}° → {wgs84Bounds.maxLat.toFixed(6)}° N</dd>
            </div>
            <div>
              <dt>Longitude Range</dt>
              <dd>{wgs84Bounds.minLon.toFixed(6)}° → {wgs84Bounds.maxLon.toFixed(6)}° E</dd>
            </div>
            <div>
              <dt>Native Bounding Box</dt>
              <dd title={`[${nativeBbox.minX}, ${nativeBbox.minY}, ${nativeBbox.maxX}, ${nativeBbox.maxY}]`}>
                X: {nativeBbox.minX.toFixed(1)} → {nativeBbox.maxX.toFixed(1)}<br />
                Y: {nativeBbox.minY.toFixed(1)} → {nativeBbox.maxY.toFixed(1)}
              </dd>
            </div>
          </dl>
        </div>

        {/* Raster Properties */}
        <div className="meta-subgroup">
          <div className="subgroup-title">
            <LayersIcon size={13} /> Raster Specifications
          </div>
          <dl className="meta-dl">
            <div>
              <dt>Dimensions</dt>
              <dd>{metadata.width.toLocaleString()} × {metadata.height.toLocaleString()} px</dd>
            </div>
            <div>
              <dt>Bands (Channels)</dt>
              <dd>{metadata.numBands} {metadata.numBands >= 4 ? '(RGBA / Multi)' : metadata.numBands === 3 ? '(RGB)' : '(Grayscale)'}</dd>
            </div>
            <div>
              <dt>Data Type</dt>
              <dd><code>{metadata.dataType}</code></dd>
            </div>
            <div>
              <dt>NoData Value</dt>
              <dd>{metadata.noData !== null ? <code>{metadata.noData}</code> : '<None>'}</dd>
            </div>
          </dl>
        </div>

        {/* File & Encoding */}
        <div className="meta-subgroup">
          <div className="subgroup-title">
            <HardDriveIcon size={13} /> Storage & Encoding
          </div>
          <dl className="meta-dl">
            <div>
              <dt>File Size</dt>
              <dd>{formatBytes(metadata.fileSizeBytes)}</dd>
            </div>
            <div>
              <dt>Compression</dt>
              <dd>{metadata.compression}</dd>
            </div>
            <div>
              <dt>Photometric</dt>
              <dd>{metadata.photometric}</dd>
            </div>
            <div>
              <dt>Alpha Channel</dt>
              <dd>{metadata.hasAlpha ? 'Present (Transparency enabled)' : 'Opaque / None'}</dd>
            </div>
          </dl>
        </div>
      </div>
    </div>
  );
}
