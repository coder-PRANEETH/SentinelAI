'use client';
import { useState, FormEvent } from 'react';
import { PageHeading } from '@/components/layout/PageHeading';
import { LoadingState, EmptyState } from '@/components/shared/LoadingState';
import { StatusBadge } from '@/components/shared/StatusBadge';
import { historicalSearch, HistoricalSearchResponse } from '@/api/finalEndpointsApi';
import type { FinalApiError } from '@/api/finalEndpointsApi';
import { Search, AlertTriangle, ChevronDown, ChevronRight, Clock, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Skeleton } from '@/components/shared/Skeleton';

/**
 * Historical Incident Viewer.
 * POST /historical-search on explicit submit (not on keystroke).
 * Min 3 characters before search enabled.
 * Low confidence warning when < 3 results.
 */
type HistoryResults = HistoricalSearchResponse & { low_confidence_warning: boolean };

export default function HistoryPage({ hideHeading = false }: { hideHeading?: boolean }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<HistoryResults | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState('');
  const [expandedRow, setExpandedRow] = useState<number | null>(null);

  const handleSearch = async (e: FormEvent) => {
    e.preventDefault();
    if (query.trim().length < 3) return;
    setIsSearching(true);
    setError('');
    setResults(null);

    try {
      const payload = { query: query.trim(), top_k: 15 };
      const res = await historicalSearch(payload.query, payload.top_k);
      setResults({ ...res, low_confidence_warning: res.total_similar < 3 });
    } catch (err) {
      const e = err as FinalApiError;
      setError(e.message || 'Search failed.');
    } finally {
      setIsSearching(false);
    }
  };

  const SimilarityBar = ({ score }: { score: number }) => {
    const pct = Math.round(score * 100);
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <div style={{ width: '60px', height: '6px', background: 'var(--border)', borderRadius: '3px', overflow: 'hidden' }}>
          <div style={{ width: `${pct}%`, height: '100%', background: 'var(--ink)', borderRadius: '3px' }} />
        </div>
        <span style={{ fontSize: '11px', fontWeight: 600, minWidth: '32px' }}>{pct}%</span>
      </div>
    );
  };

  return (
    <>
      {!hideHeading && (
        <PageHeading title={
          <>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: '36px',
                height: '36px',
                borderRadius: '10px',
                backgroundColor: '#CDFF50',
                flexShrink: 0,
              }}
            >
              <Clock size={18} color="#111111" strokeWidth={2.5} />
            </span>
            Historical Incident Viewer
          </>
        } />
      )}
      <motion.div 
        initial="hidden" animate="visible" 
        variants={{ visible: { transition: { staggerChildren: 0.1 } } }}
        className="flex-1 px-4 md:px-7 pb-7 overflow-auto"
      >

          {/* Search bar */}
          <motion.form variants={{ hidden: { opacity: 0, y: 15 }, visible: { opacity: 1, y: 0 } }} onSubmit={handleSearch} style={{ marginBottom: '24px' }}>
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
              <div style={{ flex: 1, position: 'relative' }}>
                <Search size={14} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--muted)' }} />
                <input
                  id="historical-search-input"
                  type="text"
                  className="form-input"
                  style={{ paddingLeft: '36px', fontSize: '14px', borderRadius: '9999px', height: '42px' }}
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  placeholder='Search historical incidents… e.g. "heavy vehicle Tumkur Road peak hour"'
                />
              </div>
              <button
                id="historical-search-submit"
                type="submit"
                className="btn-accent hover:scale-[1.02] active:scale-95 transition-all focus:ring-2 focus:ring-gray-300 focus:outline-none"
                style={{ height: '42px', display: 'flex', alignItems: 'center', gap: '8px' }}
                disabled={query.trim().length < 3 || isSearching}
              >
                {isSearching ? <><Loader2 size={14} className="animate-spin" /> Searching…</> : 'Search'}
              </button>
            </div>
            {query.length > 0 && query.length < 3 && (
              <p style={{ marginTop: '6px', fontSize: '11px', color: 'var(--muted)' }}>
                Type at least 3 characters to search.
              </p>
            )}
          </motion.form>

          {/* Error */}
          {error && (
            <div style={{ padding: '10px 14px', background: 'rgba(229,62,62,0.08)', borderRadius: '8px', fontSize: '12px', color: 'var(--p1)', marginBottom: '16px' }}>
              {error}
            </div>
          )}

          {/* Loading */}
          {isSearching && (
            <motion.div variants={{ hidden: { opacity: 0, y: 15 }, visible: { opacity: 1, y: 0 } }} className="card flex flex-col gap-4 p-6">
              <Skeleton height={40} />
              <Skeleton height={40} />
              <Skeleton height={40} />
            </motion.div>
          )}

          {/* Results */}
          {results && !isSearching && (
            <motion.div variants={{ hidden: { opacity: 0, y: 15 }, visible: { opacity: 1, y: 0 } }}>
              {/* Low confidence warning */}
              {results.low_confidence_warning && (
                <div className="warning-banner" style={{ marginBottom: '16px' }}>
                  <AlertTriangle size={14} style={{ color: 'var(--warn)', flexShrink: 0, marginTop: '1px' }} />
                  <span>Fewer than 3 similar cases found. Results may not be representative.</span>
                </div>
              )}

              {/* Summary row */}
              <div style={{ fontSize: '12px', color: 'var(--muted)', marginBottom: '12px' }}>
                Found <strong>{results.total_similar}</strong> similar incidents &nbsp;·&nbsp;
                Avg resolution: <strong>{results.average_resolution_time ?? '—'} min</strong> &nbsp;·&nbsp;
                Most common priority: <strong>{results.historical_priority ?? '—'}</strong> &nbsp;·&nbsp;
                Most common outcome: <strong>{results.most_common_outcome ?? '—'}</strong>
              </div>

              {/* Results table */}
              {results.similar_cases.length === 0 ? (
                <EmptyState message="No matching historical incidents found. Try a different query." />
              ) : (
                <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                  <div className="overflow-x-auto">
                    <table className="data-table min-w-[800px] w-full">
                      <thead>
                      <tr>
                        <th>Match</th>
                        <th>Corridor</th>
                        <th>Priority</th>
                        <th>Cause</th>
                        <th>Vehicle</th>
                        <th>Resolution</th>
                        <th></th>
                      </tr>
                    </thead>
                    <motion.tbody initial="hidden" animate="visible" variants={{ visible: { transition: { staggerChildren: 0.05 } } }}>
                      {results.similar_cases.map((c, i) => (
                        <AnimatePresence key={i} initial={false}>
                          <motion.tr
                            variants={{ hidden: { opacity: 0, x: -10 }, visible: { opacity: 1, x: 0 } }}
                            onClick={() => setExpandedRow(expandedRow === i ? null : i)}
                            className="hover:bg-gray-50 transition-colors cursor-pointer"
                          >
                            <td><SimilarityBar score={c.similarity_score} /></td>
                            <td style={{ fontWeight: 500 }}>{c.corridor || '—'}</td>
                            <td>
                              {c.priority ? <StatusBadge priority={c.priority as 'P1' | 'P2' | 'P3' | 'P4'} /> : '—'}
                            </td>
                            <td style={{ color: 'var(--muted)' }}>{c.event_cause || '—'}</td>
                            <td style={{ color: 'var(--muted)' }}>{c.veh_type || '—'}</td>
                            <td>{c.resolution_mins ? `${c.resolution_mins} min` : '—'}</td>
                            <td>
                              {expandedRow === i
                                ? <ChevronDown size={14} style={{ color: 'var(--muted)' }} />
                                : <ChevronRight size={14} style={{ color: 'var(--muted)' }} />}
                            </td>
                          </motion.tr>
                          {expandedRow === i && (
                            <tr>
                              <td colSpan={7} style={{ padding: 0 }}>
                                <motion.div 
                                  initial={{ height: 0, opacity: 0 }} 
                                  animate={{ height: 'auto', opacity: 1 }} 
                                  exit={{ height: 0, opacity: 0 }} 
                                  style={{ background: 'var(--bg)', padding: '16px 20px', overflow: 'hidden' }}
                                >
                                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                                    <div><span style={{ color: 'var(--muted)' }}>Junction:</span> {c.junction || '—'}</div>
                                    <div><span style={{ color: 'var(--muted)' }}>Police Station:</span> {c.police_station || '—'}</div>
                                    <div><span style={{ color: 'var(--muted)' }}>Status:</span> {c.status || '—'}</div>
                                    <div><span style={{ color: 'var(--muted)' }}>Similarity:</span> {Math.round(c.similarity_score * 100)}%</div>
                                  </div>
                                </motion.div>
                              </td>
                            </tr>
                          )}
                        </AnimatePresence>
                      ))}
                    </motion.tbody>
                  </table>
                  </div>
                </div>
              )}
            </motion.div>
          )}

          {/* Initial state */}
          {!results && !isSearching && (
            <motion.div variants={{ hidden: { opacity: 0, y: 15 }, visible: { opacity: 1, y: 0 } }}>
              <EmptyState
                message="Enter a query to search historical incidents. Try corridor names, incident types, or vehicle descriptions."
              />
            </motion.div>
          )}
      </motion.div>
    </>
  );
}
