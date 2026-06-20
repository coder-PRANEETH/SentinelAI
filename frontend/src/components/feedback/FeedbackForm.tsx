'use client';
import { useState } from 'react';
import { api, FeedbackBody, FeedbackResponse } from '@/lib/api';
import { Loader2 } from 'lucide-react';
import type { ApiError } from '@/lib/api';

/**
 * FeedbackForm — shown when operator marks incident as RESOLVED.
 * - Predicted values shown greyed out for comparison.
 * - Skip button is always present (labelled "Skip for now", not "Cancel").
 * - POST to /incident-feedback on submit.
 * - model_drift_alert=true → shows additional notice.
 */

interface FeedbackFormProps {
  incidentId: string;
  predictedPriority?: string;
  predictedResolutionMinutes?: number;
  predictedRoadClosure?: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const PRIORITIES = ['P1', 'P2', 'P3', 'P4'];

export function FeedbackForm({
  incidentId,
  predictedPriority,
  predictedResolutionMinutes,
  predictedRoadClosure,
  onClose,
  onSuccess,
}: FeedbackFormProps) {
  const [actualPriority, setActualPriority] = useState(predictedPriority ?? 'P1');
  const [actualResolution, setActualResolution] = useState('');
  const [roadClosure, setRoadClosure] = useState<boolean | null>(null);
  const [outcome, setOutcome] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [driftAlert, setDriftAlert] = useState('');

  const handleSubmit = async () => {
    if (!actualResolution || roadClosure === null) {
      setError('Please fill in all required fields.');
      return;
    }

    setIsSubmitting(true);
    setError('');

    try {
      const body: FeedbackBody = {
        incident_id: incidentId,
        actual_priority: actualPriority,
        actual_resolution_time_minutes: parseInt(actualResolution, 10),
        road_closure_occurred: roadClosure,
        outcome_description: outcome || undefined,
      };
      const res: FeedbackResponse = await api.feedback.submit(body);

      if (res.model_drift_alert) {
        setDriftAlert(res.drift_reason ?? 'This case has been flagged for model review.');
      } else {
        onSuccess();
      }
    } catch (err) {
      const e = err as ApiError;
      setError(e.message || 'Failed to submit feedback.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="dialog-overlay" role="dialog" aria-modal="true">
      <div className="dialog-content" style={{ maxWidth: '520px' }}>
        <h3 style={{ fontSize: '15px', fontWeight: 700, marginBottom: '4px' }}>Incident Closed — Submit Ground Truth</h3>
        <p style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '20px' }}>
          Help improve the AI model by confirming what actually happened.
        </p>

        {/* Priority comparison */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
          <div className="form-group">
            <label className="form-label">Predicted Priority</label>
            <input
              type="text"
              className="input"
              value={predictedPriority ?? '—'}
              readOnly
              style={{ opacity: 0.45, cursor: 'not-allowed', background: '#F5F6F4' }}
            />
          </div>
          <div className="form-group">
            <label htmlFor="actual-priority" className="form-label">Actual Priority *</label>
            <select
              id="actual-priority"
              className="select"
              value={actualPriority}
              onChange={e => setActualPriority(e.target.value)}
            >
              {PRIORITIES.map(p => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
        </div>

        {/* Resolution comparison */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
          <div className="form-group">
            <label className="form-label">Predicted Resolution</label>
            <input
              type="text"
              className="input"
              value={predictedResolutionMinutes ? `${predictedResolutionMinutes} min` : '—'}
              readOnly
              style={{ opacity: 0.45, cursor: 'not-allowed', background: '#F5F6F4' }}
            />
          </div>
          <div className="form-group">
            <label htmlFor="actual-resolution" className="form-label">Actual Resolution (min) *</label>
            <input
              id="actual-resolution"
              type="number"
              min={0}
              className="input"
              value={actualResolution}
              onChange={e => setActualResolution(e.target.value)}
              placeholder="e.g. 45"
            />
          </div>
        </div>

        {/* Road closure */}
        <div style={{ marginBottom: '16px' }}>
          <div className="form-label" style={{ marginBottom: '8px' }}>
            Road Closure Occurred? *
            {predictedRoadClosure !== undefined && (
              <span style={{ fontWeight: 400, marginLeft: '6px', color: 'var(--color-text-secondary)' }}>
                (Predicted: {predictedRoadClosure ? 'Yes' : 'No'})
              </span>
            )}
          </div>
          <div style={{ display: 'flex', gap: '10px' }}>
            <button
              type="button"
              id="road-closure-yes"
              className={roadClosure === true ? 'btn-primary' : 'btn-secondary'}
              style={{ flex: 1, justifyContent: 'center', padding: '8px' }}
              onClick={() => setRoadClosure(true)}
            >
              Yes
            </button>
            <button
              type="button"
              id="road-closure-no"
              className={roadClosure === false ? 'btn-primary' : 'btn-secondary'}
              style={{ flex: 1, justifyContent: 'center', padding: '8px' }}
              onClick={() => setRoadClosure(false)}
            >
              No
            </button>
          </div>
        </div>

        {/* Outcome description */}
        <div className="form-group" style={{ marginBottom: '16px' }}>
          <label htmlFor="outcome-description" className="form-label">Outcome Description</label>
          <textarea
            id="outcome-description"
            className="textarea"
            rows={3}
            value={outcome}
            onChange={e => setOutcome(e.target.value)}
            placeholder="Brief description of how the incident was resolved…"
          />
        </div>

        {/* Drift alert */}
        {driftAlert && (
          <div className="warning-banner" style={{ marginBottom: '16px' }}>
            ⚠️ {driftAlert}
            <button className="btn-secondary" style={{ marginLeft: 'auto', padding: '4px 12px', fontSize: '11px' }} onClick={onSuccess}>
              Continue
            </button>
          </div>
        )}

        {/* Error */}
        {error && (
          <div style={{ padding: '8px 12px', background: 'rgba(229,62,62,0.08)', borderRadius: '6px', fontSize: '12px', color: 'var(--p1)', marginBottom: '16px' }}>
            {error}
          </div>
        )}

        {/* Actions */}
        <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
          <button id="skip-feedback" className="btn-secondary" onClick={onClose} disabled={isSubmitting}>
            Skip for now
          </button>
          <button id="submit-feedback" className="btn-primary" onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? <><Loader2 size={13} className="animate-spin" /> Submitting…</> : 'Submit Feedback'}
          </button>
        </div>
      </div>
    </div>
  );
}
