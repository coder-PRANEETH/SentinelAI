'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { PageHeading } from '@/components/layout/PageHeading';
import { LoadingState } from '@/components/shared/LoadingState';
import { ReadinessBar } from '@/components/shared/ReadinessBar';
import { api } from '@/lib/api';
import { getDispatchRecommendation, getStation } from '@/api/finalEndpointsApi';
import { Users, Shield, MapPin, Calendar, Clock, AlertTriangle } from 'lucide-react';

export default function PlannedEventPage() {
  const router = useRouter();
  
  const [eventCause, setEventCause] = useState('public_event');
  const [location, setLocation] = useState('');
  const [corridor, setCorridor] = useState('');
  const [description, setDescription] = useState('');
  const [scale, setScale] = useState('medium');
  
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [forecast, setForecast] = useState<any>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!location || !description) return;
    
    setIsSubmitting(true);
    try {
      console.log("BUTTON CLICKED");
      // 1. Get severity/impact assessment via /predict
      const predictRes = await api.predict.run({
        raw_transcript: `Planned Event: ${eventCause} at ${location}. Details: ${description}. Scale: ${scale}.`,
        location: location,
        corridor: corridor || location,
      });
      
      // 2. Get historical context & resource recommendation via /dispatch
      const payload = {
        incident_text: `Planned Event: ${eventCause} at ${location}. Details: ${description}.`,
        corridor: corridor || undefined,
        search_top_k: 20,
      };
      console.log("PAYLOAD", payload);
      console.log("BEFORE FETCH");
      const dispatchRes = await getDispatchRecommendation(payload);
      console.log("AFTER FETCH");
      console.log("RESPONSE", dispatchRes);
      
      const resources = await getStation(dispatchRes.dispatch.recommended_station);
      
      setForecast({
        predict: predictRes,
        dispatch: dispatchRes.dispatch,
        historical: dispatchRes.historical_context,
        recommendedResources: dispatchRes.recommended_resources,
        stationResources: resources,
      });
    } catch (err) {
      console.error("REQUEST FAILED", err);
      console.error(err);
      alert('Failed to generate forecast.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <PageHeading title="Log Planned Event" />
      <div className="flex-1 px-7 pb-7 overflow-auto flex gap-6">
        
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

              <div className="grid grid-cols-2 gap-4">
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
                <label className="form-label">Description / Impact Notes</label>
                <textarea className="textarea" required rows={3} value={description} onChange={e => setDescription(e.target.value)} placeholder="Describe expected route or impact..." />
              </div>

              <button type="submit" className="btn-accent mt-2" disabled={isSubmitting}>
                {isSubmitting ? <LoadingState message="Generating Forecast..." size="sm" /> : 'Generate Impact Forecast'}
              </button>
            </form>
          </div>
        </div>

        {/* Forecast Column */}
        {forecast && (
          <div className="flex-1 flex flex-col gap-6 max-w-2xl">
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

            </div>
          </div>
        )}

      </div>
    </>
  );
}
