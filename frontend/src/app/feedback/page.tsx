'use client';
import { useState, useEffect } from 'react';
import { useSearchParams } from 'next/navigation';
import { CheckCircle, AlertCircle, ClipboardList } from 'lucide-react';
import { PageHeading } from '@/components/layout/PageHeading';
import { api } from '@/lib/api';
import type { ApiError } from '@/lib/api';

import { Suspense } from 'react';

type SubmitState = 'idle' | 'submitting' | 'success' | 'error';

function FeedbackForm() {
  const searchParams = useSearchParams();
  const prefilledId = searchParams.get('incident_id') || '';

  const [incidentId, setIncidentId] = useState(prefilledId);
  const [actualPriority, setActualPriority] = useState('');
  const [actualClosure, setActualClosure] = useState(false);
  const [actualResolutionTime, setActualResolutionTime] = useState('');
  const [officersUsed, setOfficersUsed] = useState('');
  const [barricadesUsed, setBarricadesUsed] = useState('');
  const [remarks, setRemarks] = useState('');

  const [submitState, setSubmitState] = useState<SubmitState>('idle');
  const [errorMsg, setErrorMsg] = useState('');

  // Pre-fill from URL param
  useEffect(() => {
    if (prefilledId) setIncidentId(prefilledId);
  }, [prefilledId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!incidentId.trim() || !actualPriority) return;

    setSubmitState('submitting');
    setErrorMsg('');

    try {
      await api.feedback.submitExtended({
        incident_id: incidentId.trim(),
        actual_priority: actualPriority,
        actual_closure: actualClosure,
        actual_resolution_time: actualResolutionTime ? parseInt(actualResolutionTime) : 0,
        officers_used: officersUsed ? parseInt(officersUsed) : 0,
        barricades_used: barricadesUsed ? parseInt(barricadesUsed) : 0,
        remarks: remarks.trim() || undefined,
      });
      setSubmitState('success');
    } catch (err) {
      setErrorMsg((err as ApiError).message || 'Submission failed. Please try again.');
      setSubmitState('error');
    }
  };

  const handleReset = () => {
    setIncidentId(prefilledId);
    setActualPriority('');
    setActualClosure(false);
    setActualResolutionTime('');
    setOfficersUsed('');
    setBarricadesUsed('');
    setRemarks('');
    setSubmitState('idle');
    setErrorMsg('');
  };

  return (
    <>
      <PageHeading title={
        <>
          <span
            style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              width: 36, height: 36, borderRadius: 10, backgroundColor: '#CDFF50', flexShrink: 0,
            }}
          >
            <ClipboardList size={18} color="#111111" strokeWidth={2.5} />
          </span>
          Incident Feedback
        </>
      } />

      <div className="flex-1 px-7 pb-7 overflow-auto">
        <div style={{ maxWidth: 600 }}>

          {submitState === 'success' ? (
            <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, padding: '48px 32px', textAlign: 'center' }}>
              <div style={{ width: 64, height: 64, borderRadius: '50%', background: '#D1FAE5', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <CheckCircle size={30} style={{ color: '#059669' }} />
              </div>
              <div>
                <div style={{ fontSize: 20, fontWeight: 700, marginBottom: 6 }}>Feedback Submitted</div>
                <div style={{ fontSize: 13, color: '#6B7280', lineHeight: 1.6 }}>
                  Thank you. Your ground-truth data helps improve the AI model's accuracy for future incidents.
                </div>
              </div>
              <button className="btn-secondary" onClick={handleReset} style={{ marginTop: 8 }}>
                Submit Another
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

              <div className="card">
                <div style={{ fontSize: 11, fontWeight: 700, color: '#A0A0A0', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 16 }}>
                  Incident Reference
                </div>
                <div className="form-group">
                  <label htmlFor="incident_id" className="form-label">Incident ID *</label>
                  <input
                    id="incident_id"
                    type="text"
                    className="form-input"
                    value={incidentId}
                    onChange={e => setIncidentId(e.target.value)}
                    placeholder="e.g. INC-2024-000001"
                    required
                  />
                </div>
              </div>

              <div className="card">
                <div style={{ fontSize: 11, fontWeight: 700, color: '#A0A0A0', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 16 }}>
                  Actual Outcome
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  <div className="form-group">
                    <label htmlFor="actual_priority" className="form-label">Actual Priority *</label>
                    <select
                      id="actual_priority"
                      className="form-input"
                      value={actualPriority}
                      onChange={e => setActualPriority(e.target.value)}
                      required
                    >
                      <option value="">Select priority…</option>
                      <option value="P1">P1 — Critical</option>
                      <option value="P2">P2 — High</option>
                      <option value="P3">P3 — Medium</option>
                      <option value="P4">P4 — Low</option>
                    </select>
                  </div>

                  <div className="form-group">
                    <label htmlFor="actual_resolution_time" className="form-label">Actual Resolution Time (min)</label>
                    <input
                      id="actual_resolution_time"
                      type="number"
                      className="form-input"
                      value={actualResolutionTime}
                      onChange={e => setActualResolutionTime(e.target.value)}
                      min={0}
                      placeholder="e.g. 45"
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="officers_used" className="form-label">Officers Used</label>
                    <input
                      id="officers_used"
                      type="number"
                      className="form-input"
                      value={officersUsed}
                      onChange={e => setOfficersUsed(e.target.value)}
                      min={0}
                      placeholder="e.g. 4"
                    />
                  </div>

                  <div className="form-group">
                    <label htmlFor="barricades_used" className="form-label">Barricades Used</label>
                    <input
                      id="barricades_used"
                      type="number"
                      className="form-input"
                      value={barricadesUsed}
                      onChange={e => setBarricadesUsed(e.target.value)}
                      min={0}
                      placeholder="e.g. 2"
                    />
                  </div>
                </div>

                <div className="form-group" style={{ marginTop: 8 }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer', userSelect: 'none' }}>
                    <input
                      id="actual_closure"
                      type="checkbox"
                      className="map-checkbox"
                      checked={actualClosure}
                      onChange={e => setActualClosure(e.target.checked)}
                      style={{ width: 16, height: 16, borderRadius: 4 }}
                    />
                    <span className="form-label" style={{ marginBottom: 0 }}>Road closure occurred</span>
                  </label>
                </div>
              </div>

              <div className="card">
                <div style={{ fontSize: 11, fontWeight: 700, color: '#A0A0A0', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 16 }}>
                  Additional Notes
                </div>
                <div className="form-group">
                  <label htmlFor="remarks" className="form-label">Remarks</label>
                  <textarea
                    id="remarks"
                    className="form-input"
                    value={remarks}
                    onChange={e => setRemarks(e.target.value)}
                    placeholder="Any additional notes about how the incident was handled…"
                    rows={4}
                    style={{ resize: 'vertical', lineHeight: 1.6 }}
                  />
                </div>
              </div>

              {submitState === 'error' && errorMsg && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px', background: 'rgba(229,62,62,0.08)', borderRadius: 12, fontSize: 13, color: '#E53E3E', border: '1px solid rgba(229,62,62,0.15)' }}>
                  <AlertCircle size={16} />
                  {errorMsg}
                </div>
              )}

              <div style={{ display: 'flex', gap: 10 }}>
                <button
                  id="submit-feedback-btn"
                  type="submit"
                  className="btn-primary"
                  disabled={submitState === 'submitting' || !incidentId.trim() || !actualPriority}
                  style={{ flex: 1, justifyContent: 'center', padding: 14, fontSize: 14 }}
                >
                  {submitState === 'submitting' ? 'Submitting…' : 'Submit Feedback'}
                </button>
                <button type="button" className="btn-secondary" onClick={handleReset}>
                  Reset
                </button>
              </div>

            </form>
          )}
        </div>
      </div>
    </>
  );
}

export default function FeedbackPage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <FeedbackForm />
    </Suspense>
  );
}
