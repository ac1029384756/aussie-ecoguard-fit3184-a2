import { useEffect, useId, useRef, useState } from 'react';
import { CalendarDays, ChevronLeft, ChevronRight } from 'lucide-react';

const months = [
  'January',
  'February',
  'March',
  'April',
  'May',
  'June',
  'July',
  'August',
  'September',
  'October',
  'November',
  'December',
];
const weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const pad = (value: number) => String(value).padStart(2, '0');
const localDay = (date: Date) =>
  `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;

/** App-rendered English controls: native date/time widgets follow the browser locale. */
export function DatePicker({
  label,
  value,
  onChange,
  min,
  max,
  disabled = false,
  withTime = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  min?: string;
  max?: string;
  disabled?: boolean;
  withTime?: boolean;
}) {
  const id = useId();
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [above, setAbove] = useState(false);
  const [view, setView] = useState(() => new Date());
  const selected = value.slice(0, 10);
  const time = value.slice(11) || '00:00';
  const [hour, minute] = time.split(':');
  const year = view.getFullYear();
  const month = view.getMonth();
  const offset = new Date(year, month, 1).getDay();
  const days = new Date(year, month + 1, 0).getDate();
  const yearStart = Math.min(new Date().getFullYear() - 100, year);
  const yearEnd = Math.max(new Date().getFullYear() + 20, year);
  const display = selected
    ? new Date(`${selected}T12:00:00`).toLocaleDateString('en-AU', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      }) + (withTime ? `, ${time}` : '')
    : withTime
      ? 'Choose date and time'
      : 'Choose date';
  function close() {
    setOpen(false);
    trigger.current?.focus();
  }
  function choose(day: string) {
    onChange(day + (withTime ? `T${time}` : ''));
    if (!withTime) close();
  }
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('pointerdown', outside);
    root.current?.querySelector<HTMLSelectElement>('select')?.focus();
    return () => document.removeEventListener('pointerdown', outside);
  }, [open]);
  useEffect(() => {
    if (disabled) setOpen(false);
  }, [disabled]);
  return (
    <div
      className="date-field"
      ref={root}
      onKeyDown={(event) => {
        if (open && event.key === 'Escape') {
          event.stopPropagation();
          close();
        }
      }}
    >
      <span id={`${id}-label`} className="date-label">
        {label}
      </span>
      <button
        ref={trigger}
        type="button"
        className="date-trigger"
        disabled={disabled}
        aria-labelledby={`${id}-label ${id}-value`}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? `${id}-calendar` : undefined}
        onClick={() => {
          if (!open) {
            setView(selected ? new Date(`${selected}T12:00:00`) : new Date());
            const bounds = trigger.current?.getBoundingClientRect();
            const height = withTime ? 390 : 340;
            setAbove(
              Boolean(bounds && bounds.top > height && window.innerHeight - bounds.bottom < height),
            );
          }
          setOpen(!open);
        }}
      >
        <span id={`${id}-value`}>{display}</span>
        <CalendarDays size={17} aria-hidden="true" />
      </button>
      {open && (
        <div
          className={`date-calendar${above ? ' above' : ''}`}
          id={`${id}-calendar`}
          role="dialog"
          aria-label={`${label} calendar`}
          lang="en"
        >
          <div className="date-month-row">
            <button
              type="button"
              className="icon-button"
              aria-label="Previous month"
              onClick={() => setView(new Date(year, month - 1, 1))}
            >
              <ChevronLeft size={16} />
            </button>
            <select
              aria-label="Month"
              value={month}
              onChange={(e) => setView(new Date(year, Number(e.target.value), 1))}
            >
              {months.map((name, index) => (
                <option key={name} value={index}>
                  {name}
                </option>
              ))}
            </select>
            <select
              aria-label="Year"
              value={year}
              onChange={(e) => setView(new Date(Number(e.target.value), month, 1))}
            >
              {Array.from({ length: yearEnd - yearStart + 1 }, (_, i) => yearStart + i).map(
                (item) => (
                  <option key={item}>{item}</option>
                ),
              )}
            </select>
            <button
              type="button"
              className="icon-button"
              aria-label="Next month"
              onClick={() => setView(new Date(year, month + 1, 1))}
            >
              <ChevronRight size={16} />
            </button>
          </div>
          <div className="date-days">
            {weekdays.map((day) => (
              <span key={day} className="date-weekday">
                {day}
              </span>
            ))}
            {Array.from({ length: offset }, (_, i) => (
              <span key={`blank-${i}`} />
            ))}
            {Array.from({ length: days }, (_, i) => {
              const day = `${year}-${pad(month + 1)}-${pad(i + 1)}`;
              return (
                <button
                  key={day}
                  type="button"
                  className={day === selected ? 'selected' : ''}
                  aria-label={`${i + 1} ${months[month]} ${year}`}
                  aria-pressed={day === selected}
                  aria-current={day === localDay(new Date()) ? 'date' : undefined}
                  disabled={Boolean(
                    (min && day < min.slice(0, 10)) || (max && day > max.slice(0, 10)),
                  )}
                  onClick={() => choose(day)}
                >
                  {i + 1}
                </button>
              );
            })}
          </div>
          {withTime && (
            <div className="date-time-row">
              <span>Local time (24-hour)</span>
              <select
                aria-label="Hour"
                value={hour}
                disabled={!selected}
                onChange={(e) => onChange(`${selected}T${e.target.value}:${minute}`)}
              >
                {Array.from({ length: 24 }, (_, i) => pad(i)).map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
              <span>:</span>
              <select
                aria-label="Minute"
                value={minute}
                disabled={!selected}
                onChange={(e) => onChange(`${selected}T${hour}:${e.target.value}`)}
              >
                {Array.from({ length: 60 }, (_, i) => pad(i)).map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </div>
          )}
          <div className="date-actions">
            <button
              type="button"
              className="text-button"
              onClick={() => {
                onChange('');
                close();
              }}
            >
              Clear
            </button>
            <button type="button" className="text-button" onClick={close}>
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
