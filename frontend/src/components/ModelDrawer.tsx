import React, { useEffect, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { XIcon } from 'lucide-react';
import { useApp } from '../contexts/AppContext';
import { models } from '../data/models';
import type { ModelSettings } from '../types/app';

export function ModelDrawer() {
  const { drawerOpen, closeDrawer, modelSettings, updateModelSettings, toast } = useApp();
  const [draft, setDraft] = useState<ModelSettings>(modelSettings);

  useEffect(() => {
    if (drawerOpen) setDraft(modelSettings);
  }, [drawerOpen, modelSettings]);

  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && closeDrawer();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [drawerOpen, closeDrawer]);

  const apply = () => {
    updateModelSettings({ ...draft, routing: draft.model === 'Auto' ? 'auto' : draft.routing });
    closeDrawer();
    toast('Model configuration saved', 'success');
  };

  return (
    <AnimatePresence>
      {drawerOpen &&
      <motion.div
        className="drawer"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.2 }}
        onMouseDown={(e) => e.target === e.currentTarget && closeDrawer()}>
        
          <motion.div
          className="drawer-panel"
          role="dialog"
          aria-modal="true"
          aria-labelledby="drawer-title"
          initial={{ x: 40, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: 40, opacity: 0 }}
          transition={{ duration: 0.24, ease: [0.23, 1, 0.32, 1] }}>
          
            <div className="drawer-head">
              <h2 id="drawer-title">Diagnostic Model Override</h2>
              <button className="close" onClick={closeDrawer} aria-label="Close">
                <XIcon size={18} />
              </button>
            </div>
            <p className="drawer-intro">
              SatQuery AI automatically routes queries based on input modality and scientific intent. Ordinary users do not need to choose a model. Use this drawer only for diagnostic benchmarking or developer override.
            </p>
            {models.map((m) =>
          <label key={m.id} className={`model-option${draft.model === m.id ? ' active' : ''}`}>
                <input
              type="radio"
              name="model"
              value={m.id}
              checked={draft.model === m.id}
              onChange={() => setDraft((d) => ({ ...d, model: m.id, routing: m.id === 'Auto' ? 'auto' : 'manual' }))} />
            
                <span>
                  <strong>{m.title}</strong>
                  <small>{m.description}</small>
                </span>
              </label>
          )}
            <div className="drawer-section">
              <b>Advanced model controls</b>
              <div className="config-row" style={{ marginTop: 12 }}>
                <label className="field-label" htmlFor="dr-validation">Validation</label>
                <select
                id="dr-validation"
                value={draft.validation ? 'on' : 'off'}
                onChange={(e) => setDraft((d) => ({ ...d, validation: e.target.value === 'on' }))}>
                
                  <option value="on">Enabled</option>
                  <option value="off">Disabled</option>
                </select>
              </div>
              <div className="config-row">
                <label className="field-label" htmlFor="dr-compare">Comparison mode</label>
                <select
                id="dr-compare"
                value={draft.comparisonMode}
                onChange={(e) => setDraft((d) => ({ ...d, comparisonMode: e.target.value as ModelSettings['comparisonMode'] }))}>
                
                  <option value="before-after">Before / After</option>
                  <option value="optical-sar">Optical-SAR Fusion</option>
                  <option value="single">Single image</option>
                  <option value="multi-date">Multi-date</option>
                </select>
              </div>
              <div className="config-row">
                <label className="field-label" htmlFor="dr-output">Output</label>
                <select
                id="dr-output"
                value={draft.output}
                onChange={(e) => setDraft((d) => ({ ...d, output: e.target.value as ModelSettings['output'] }))}>
                
                  <option value="visual">Visual + explanation</option>
                  <option value="mask">Map mask</option>
                  <option value="data">Data + visual</option>
                </select>
              </div>
            </div>
            <button className="btn primary block" style={{ marginTop: 8 }} onClick={apply}>
              Apply configuration
            </button>
          </motion.div>
        </motion.div>
      }
    </AnimatePresence>);

}