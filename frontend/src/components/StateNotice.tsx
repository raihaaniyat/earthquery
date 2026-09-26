import React from 'react';
import {
  LoaderCircleIcon,
  CircleCheckIcon,
  InboxIcon,
  TriangleAlertIcon,
  WifiOffIcon,
  CircleAlertIcon,
  PlugZapIcon,
  InfoIcon,
  RefreshCwIcon } from
'lucide-react';
import type { RequestState } from '../types/app';

interface StateNoticeProps {
  state: RequestState<unknown>;
  idleText?: string;
  loadingText?: string;
  successText?: string;
  onRetry?: () => void;
}

const TITLES = {
  empty: 'No data',
  error: 'API error',
  network: 'Network failure',
  invalid: 'Invalid AOI, date or input',
  unconfigured: 'Backend not connected'
} as const;

export function StateNotice({ state, idleText, loadingText, successText, onRetry }: StateNoticeProps) {
  if (state.status === 'idle') {
    if (!idleText) return null;
    return (
      <div className="change-status tone-idle">
        <InfoIcon size={15} />
        <span className="msg-text">{idleText}</span>
      </div>);

  }
  if (state.status === 'loading') {
    return (
      <div className="change-status tone-loading" role="status">
        <LoaderCircleIcon size={15} className="spin" />
        <span className="msg-text">{state.message ?? loadingText ?? 'Loading…'}</span>
      </div>);

  }
  if (state.status === 'success') {
    if (!successText) return null;
    return (
      <div className="change-status tone-success">
        <CircleCheckIcon size={15} />
        <span className="msg-text">{successText}</span>
      </div>);

  }
  const Icon =
  state.status === 'empty' ?
  InboxIcon :
  state.status === 'error' ?
  TriangleAlertIcon :
  state.status === 'network' ?
  WifiOffIcon :
  state.status === 'invalid' ?
  CircleAlertIcon :
  PlugZapIcon;
  const retryable = onRetry && (state.status === 'error' || state.status === 'network' || state.status === 'empty');
  return (
    <div className={`change-status tone-${state.status}`} role="alert">
      <Icon size={15} />
      <div>
        <b>{TITLES[state.status]}</b>
        <span className="msg-text">{state.message}</span>
      </div>
      {retryable &&
      <button className="btn small notice-action" onClick={onRetry}>
          <RefreshCwIcon size={12} /> Retry
        </button>
      }
    </div>);

}