import React from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { CircleCheckIcon, CircleAlertIcon, InfoIcon } from 'lucide-react';
import { useApp } from '../contexts/AppContext';

export function Toast() {
  const { toastState } = useApp();
  return (
    <div aria-live="polite" role="status">
      <AnimatePresence>
        {toastState &&
        <motion.div
          key={toastState.id}
          className={`toast tone-${toastState.tone}`}
          initial={{ opacity: 0, y: 8, scale: 0.96 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 8 }}
          transition={{ duration: 0.18, ease: [0.23, 1, 0.32, 1] }}>
          
            {toastState.tone === 'success' ?
          <CircleCheckIcon size={15} /> :
          toastState.tone === 'error' ?
          <CircleAlertIcon size={15} /> :

          <InfoIcon size={15} />
          }
            {toastState.message}
          </motion.div>
        }
      </AnimatePresence>
    </div>);

}