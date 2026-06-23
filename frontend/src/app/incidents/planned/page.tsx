'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { PageHeading } from '@/components/layout/PageHeading';
import { LoadingState } from '@/components/shared/LoadingState';
import { ReadinessBar } from '@/components/shared/ReadinessBar';
import { api } from '@/lib/api';
import { getDispatchRecommendation, getStation } from '@/api/finalEndpointsApi';
import { Users, Shield, MapPin, Calendar, Clock, AlertTriangle, Loader2, Mic, MicOff } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useWebSpeech } from '@/hooks/useWebSpeech';

export default function PlannedEventPage() {
  const router = useRouter();
  
  const [eventCause, setEventCause] = useState('public_event');
  const [location, setLocation] = useState('');
  const [corridor, setCorridor] = useState('');
  const [description, setDescription] = useState('');
  const [scale, setScale] = useState('medium');
  
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [forecast, setForecast] = useState<any>(null);

  const { isListening, toggleListening } = useWebSpeech({
    onTranscript: (text) => {
      setDescription(prev => prev ? `${prev} ${text}` : text);
    }
  });

  // Feedback State
  const [showFeedback, setShowFeedback] = useState(false);
  const [actualPriority, setActualPriority] = useState('low');
  const [actualResolution, setActualResolution] = useState<number>(60);
  const [actualClosure, setActualClosure] = useState(false);
  const [feedbackResponse, setFeedbackResponse] = useState<any>(null);
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!location || !description) return;
    
    setIsSubmitting(true);
    try {
      // 1. Get severity/impact assessment via /predict
      const predictRes = await api.predict.run({
        raw_transcript: `Planned Event: ${eventCause} at ${location}. Details: ${description}. Scale: ${scale}.`,
        location: location,
        corridor: corridor || location,
        event_type_grouped: 'planned',
        event_cause: eventCause,
      });
      
      // 2. Get historical context & resource recommendation via /dispatch
      const payload = {
        incident_text: `Planned Event: ${eventCause} at ${location}. Details: ${description}.`,
        corridor: corridor || undefined,
        search_top_k: 20,
      };
      const dispatchRes = await getDispatchRecommendation(payload);
      
      const resources = await getStation(dispatchRes.dispatch.recommended_station);
      
      setForecast({
        predict: predictRes,
        dispatch: dispatchRes.dispatch,
        historical: dispatchRes.historical_context,
        recommendedResources: dispatchRes.recommended_resources,
        stationResources: resources,
      });
    } catch (err) {
      console.error(err);
      alert('Failed to generate forecast.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleFeedbackSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!forecast?.predict?.incident_id) return;
    
    setIsSubmittingFeedback(true);
    try {
      const res = await api.feedback.submitExtended({
        incident_id: forecast.predict.incident_id,
        actual_priority: actualPriority,
        actual_resolution_time: actualResolution,
        actual_closure: actualClosure,
        officers_used: forecast.recommendedResources?.officers || 0,
        barricades_used: forecast.recommendedResources?.barricades || 0,
      });
      setFeedbackResponse(res);
    } catch (err) {
      console.error(err);
      alert('Failed to submit feedback.');
    } finally {
      setIsSubmittingFeedback(false);
    }
  };

  return (
    <>
      <PageHeading title="Log Planned Event" />
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2 }} className="flex-1 px-4 md:px-7 pb-7 overflow-auto flex flex-col lg:flex-row gap-6">
        
        {/* Form Column */}
        <div className="flex-1 flex flex-col gap-6 max-w-2xl">
          <div className="card">
            <h3 className="text-sm font-bold text-text-1 mb-4">Event Details</h3>
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              
              <div className="form-group">
                <label className="form-label">Event Type</label>
                <select className="select" value={eventCause} onChange={e => setEventCause(e.target.value)}>
                  <option value="public_event">Public Event / Rally</option>
                  <option value="procession">Procession / Festival</option>
                  <option value="vip_movement">VIP Movement</option>
                  <option value="protest">Protest / Demonstration</option>
                </select>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="form-group">
                  <label className="form-label">Location (Junction/Landmark)</label>
                  <input className="form-input" required value={location} onChange={e => setLocation(e.target.value)} placeholder="e.g. MG Road" />
                </div>
                <div className="form-group">
                  <label className="form-label">Corridor (Optional)</label>
                  <input className="form-input" value={corridor} onChange={e => setCorridor(e.target.value)} placeholder="e.g. Outer Ring Road" />
                </div>
              </div>
              
              <div className="form-group">
                <label className="form-label">Expected Scale</label>
                <select className="select" value={scale} onChange={e => setScale(e.target.value)}>
                  <option value="small">Small (&lt; 500 people)</option>
                  <option value="medium">Medium (500 - 5,000 people)</option>
                  <option value="large">Large (&gt; 5,000 people)</option>
                </select>
              </div>
              
              <div className="form-group">
                <div className="flex items-center justify-between">
                  <label className="form-label">Description / Impact Notes</label>
                  <button 
                    type="button"
                    onClick={toggleListening}
                    className={`flex items-center gap-2 px-2 py-1 rounded transition-colors text-xs font-semibold
                      ${isListening ? 'bg-red-500/10 text-red-500 hover:bg-red-500/20' : 'bg-surface text-text-2 hover:bg-black/5 hover:text-text-1'}`}
                  >
                    {isListening ? (
                      <><MicOff size={14} className="animate-pulse" /> Recording...</>
                    ) : (
                      <><Mic size={14} /> Dictate</>
                    )}
                  </button>
                </div>
                <textarea className="textarea" required rows={3} value={description} onChange={e => setDescription(e.target.value)} placeholder="Describe expected route or impact..." />
              </div>

              <button type="submit" className={`btn-accent mt-2 hover:scale-[1.02] active:scale-95 transition-all focus:ring-2 focus:ring-gray-400 focus:outline-none ${isSubmitting ? 'opacity-80' : ''}`} disabled={isSubmitting}>
                {isSubmitting ? <span className="flex items-center gap-2 justify-center"><Loader2 size={14} className="animate-spin" /> Generating Forecast...</span> : 'Generate Impact Forecast'}
              </button>
            </form>
          </div>
        </div>

        {/* Forecast Column */}
        <AnimatePresence>
          {forecast && (
            <motion.div 
              initial={{ opacity: 0, x: 20 }} 
              animate={{ opacity: 1, x: 0 }} 
              exit={{ opacity: 0, x: 20 }}
              transition={{ type: 'spring', damping: 25, stiffness: 200 }}
              className="flex-1 flex flex-col gap-6 max-w-2xl"
            >
              <div className="card" style={{ background: 'var(--bg)', border: '2px solid var(--lime)' }}>
              <h3 className="text-sm font-bold text-text-1 mb-4 flex items-center gap-2">
                <AlertTriangle size={18} color="var(--lime)" /> Event Impact Forecast
              </h3>
              
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="bg-surface p-4 rounded-xl">
                  <div className="text-[11px] text-text-2 uppercase font-bold tracking-wider mb-1">Impact Severity</div>
                  <div className="text-2xl font-bold">{forecast.predict.predictions.predicted_priority}</div>
                </div>
                <div className="bg-surface p-4 rounded-xl">
                  <div className="text-[11px] text-text-2 uppercase font-bold tracking-wider mb-1">Closure Probability</div>
                  <div className="text-2xl font-bold">{forecast.predict.predictions.road_closure_probability}%</div>
                </div>
              </div>

              <div className="bg-surface p-4 rounded-xl mb-6">
                <div className="text-[11px] text-text-2 uppercase font-bold tracking-wider mb-2">Recommended Deployment</div>
                <div className="text-sm text-accent mb-4">{forecast.recommendedResources?.justification}</div>
                {forecast.recommendedResources?.suggested_diversion_route && (
                  <div className="text-sm text-amber-500 font-medium mb-4 p-2 bg-amber-500/10 rounded border border-amber-500/20">
                    {forecast.recommendedResources.suggested_diversion_route}
                  </div>
                )}
                <div className="grid grid-cols-2 gap-4">
                  <div className="flex items-center gap-3">
                    <div className="bg-bg p-2 rounded-lg"><Users size={16} /></div>
                    <div>
                      <div className="text-xl font-bold">{forecast.recommendedResources?.officers}</div>
                      <div className="text-xs text-text-2">Officers</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="bg-bg p-2 rounded-lg"><Shield size={16} /></div>
                    <div>
                      <div className="text-xl font-bold">{forecast.recommendedResources?.barricades}</div>
                      <div className="text-xs text-text-2">Barricades</div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="bg-surface p-4 rounded-xl mb-6">
                <div className="text-[11px] text-text-2 uppercase font-bold tracking-wider mb-2">Historical Context</div>
                <div className="text-sm">
                  Based on <strong>{forecast.historical.similar_cases}</strong> similar planned events:
                  <ul className="list-disc ml-5 mt-2 space-y-1">
                    <li>Most common outcome: {forecast.historical.most_common_outcome || 'N/A'}</li>
                    <li>Avg clearance time: {forecast.historical.average_resolution_time} mins</li>
                  </ul>
                </div>
              </div>

              <div className="bg-surface p-4 rounded-xl">
                <div className="text-[11px] text-text-2 uppercase font-bold tracking-wider mb-2 flex justify-between">
                  <span>Recommended Station</span>
                  <span className="text-lime">Readiness: {Math.round(forecast.dispatch.readiness_score)}</span>
                </div>
                <div className="text-lg font-bold mb-2">{forecast.dispatch.recommended_station}</div>
                <ReadinessBar score={forecast.dispatch.readiness_score} />
              </div>

              {!showFeedback && !feedbackResponse && (
                <button 
                  onClick={() => setShowFeedback(true)}
                  className="btn-outline mt-2 w-full flex justify-center items-center gap-2"
                >
                  <Clock size={16} /> Resolve Event & Submit Feedback
                </button>
              )}

              {showFeedback && !feedbackResponse && (
                <div className="card mt-4 border border-text-2/20">
                  <h3 className="text-sm font-bold text-text-1 mb-4 flex items-center gap-2">
                    Submit Post-Event Feedback
                  </h3>
                  <form onSubmit={handleFeedbackSubmit} className="flex flex-col gap-4">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="form-group">
                        <label className="form-label">Actual Priority</label>
                        <select className="select" value={actualPriority} onChange={e => setActualPriority(e.target.value)}>
                          <option value="low">Low</option>
                          <option value="high">High</option>
                        </select>
                      </div>
                      <div className="form-group">
                        <label className="form-label">Actual Duration (mins)</label>
                        <input type="number" className="form-input" required value={actualResolution} onChange={e => setActualResolution(Number(e.target.value))} />
                      </div>
                    </div>
                    <div className="form-group flex items-center gap-2">
                      <input type="checkbox" id="closure" checked={actualClosure} onChange={e => setActualClosure(e.target.checked)} />
                      <label htmlFor="closure" className="text-sm">Road Closure Actually Required?</label>
                    </div>
                    <button type="submit" className="btn-primary mt-2" disabled={isSubmittingFeedback}>
                      {isSubmittingFeedback ? 'Submitting...' : 'Submit Feedback'}
                    </button>
                  </form>
                </div>
              )}

              {feedbackResponse && (
                <div className={`p-4 rounded-xl mt-4 border ${feedbackResponse.model_drift_alert ? 'bg-red-500/10 border-red-500/50' : 'bg-lime/10 border-lime/50'}`}>
                  <h3 className={`text-sm font-bold mb-2 ${feedbackResponse.model_drift_alert ? 'text-red-400' : 'text-lime'}`}>
                    {feedbackResponse.model_drift_alert ? '⚠️ Model Drift Alert Triggered' : '✅ Feedback Logged Successfully'}
                  </h3>
                  <div className="text-sm">
                    {feedbackResponse.drift_reason ? (
                      <span><strong>Reason:</strong> {feedbackResponse.drift_reason}</span>
                    ) : (
                      <span>Model predictions were within acceptable thresholds.</span>
                    )}
                  </div>
                </div>
              )}

            </div>
          </motion.div>
        )}
        </AnimatePresence>

      </motion.div>
    </>
  );
}
