interface StatusBadgeProps {
  priority?: 'P1' | 'P2' | 'P3' | 'P4';
  status?: 'Reported' | 'Under Assessment' | 'Resources Assigned' | 'In Progress' | 'Resolved' | 'Closed' | 'Cancelled';
}

const PRIORITY_COLORS = {
  P1: { bg: '#FEE2E2', text: '#DC2626', label: 'P1' },  // red
  P2: { bg: '#FEF3C7', text: '#D97706', label: 'P2' },  // amber
  P3: { bg: '#FEF9C3', text: '#A16207', label: 'P3' },  // yellow
  P4: { bg: '#DBEAFE', text: '#1D4ED8', label: 'P4' },  // blue
};

export function StatusBadge({ priority, status }: StatusBadgeProps) {
  if (priority) {
    const config = PRIORITY_COLORS[priority];
    return (
      <span style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '3px 10px',
        borderRadius: '9999px',
        fontSize: '11px',
        fontWeight: 700,
        backgroundColor: config?.bg || '#F3F4F6',
        color: config?.text || '#111111',
        letterSpacing: '0.03em',
      }}>
        {config?.label || priority}
      </span>
    );
  }

  if (status) {
    const className = `status-badge badge-${status.toLowerCase().replace(/\s+/g, '-')}`;
    return <span className={className}>{status}</span>;
  }

  return null;
}
