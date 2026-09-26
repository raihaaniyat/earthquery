import React, { useState } from 'react';
import { ImageOffIcon } from 'lucide-react';

export function SafeThumb({ src, alt }: {src: string | null;alt: string;}) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) {
    return (
      <span title="Preview unavailable" style={{ display: 'grid', placeItems: 'center' }}>
        <ImageOffIcon size={18} />
      </span>);

  }
  return <img src={src} alt={alt} loading="lazy" onError={() => setFailed(true)} />;
}