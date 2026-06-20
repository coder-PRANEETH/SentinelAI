interface TabNavProps {
  tabs: string[];
  active: string;
  onChange: (tab: string) => void;
}

export function TabNav({ tabs, active, onChange }: TabNavProps) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        padding: '12px 24px 16px',
        overflowX: 'auto',
        scrollbarWidth: 'none',
      }}
    >
      {tabs.map((tab) => (
        <button
          key={tab}
          onClick={() => onChange(tab)}
          style={{
            padding: '7px 18px',
            borderRadius: '9999px',
            fontSize: '13px',
            fontWeight: tab === active ? 600 : 500,
            whiteSpace: 'nowrap',
            cursor: 'pointer',
            border: tab === active
              ? '1.5px solid #111111'            /* active: dark border */
              : '1.5px solid #DEDEDE',            /* inactive: medium gray border */
            backgroundColor: tab === active
              ? '#111111'                         /* active: dark fill */
              : '#FFFFFF',                        /* inactive: white */
            color: tab === active
              ? '#FFFFFF'                         /* active: white text */
              : '#444444',                        /* inactive: dark gray text */
            transition: 'all 0.15s ease',
            lineHeight: 1,
            outline: 'none',
            boxShadow: tab === active
              ? 'none'
              : '0 1px 2px rgba(0,0,0,0.06)',    /* subtle shadow on inactive tabs */
          }}
        >
          {tab}
        </button>
      ))}
    </div>
  );
}
