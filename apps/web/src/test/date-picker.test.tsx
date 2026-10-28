import { useState } from 'react';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, expect, it } from 'vitest';
import { DatePicker } from '../components/DatePicker';

afterEach(cleanup);
function Field({ withTime = false, min, max }: { withTime?: boolean; min?: string; max?: string }) {
  const [value, setValue] = useState(withTime ? '2024-02-28T09:15' : '2024-02-28');
  return (
    <>
      <DatePicker
        label="Observed"
        value={value}
        onChange={setValue}
        withTime={withTime}
        min={min}
        max={max}
      />
      <output>{value}</output>
    </>
  );
}
it('uses English months and weekdays and selects leap day with an ISO date', async () => {
  const user = userEvent.setup();
  const { container } = render(<Field />);
  expect(container.querySelector('input[type="date"],input[type="datetime-local"]')).toBeNull();
  await user.click(screen.getByRole('button', { name: 'Observed 28 Feb 2024' }));
  expect(screen.getByRole('combobox', { name: 'Month' })).toHaveDisplayValue('February');
  expect(screen.getByText('Thu')).toBeVisible();
  await user.click(screen.getByRole('button', { name: '29 February 2024' }));
  expect(screen.getByRole('status')).toHaveTextContent('2024-02-29');
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});
it('preserves local time while changing dates and supports English time selectors', async () => {
  const user = userEvent.setup();
  render(<Field withTime />);
  await user.click(screen.getByRole('button', { name: 'Observed 28 Feb 2024, 09:15' }));
  await user.click(screen.getByRole('button', { name: '29 February 2024' }));
  await user.selectOptions(screen.getByRole('combobox', { name: 'Hour' }), '14');
  await user.selectOptions(screen.getByRole('combobox', { name: 'Minute' }), '30');
  await user.click(screen.getByRole('button', { name: 'Done' }));
  expect(screen.getByRole('status')).toHaveTextContent('2024-02-29T14:30');
  expect(screen.getByRole('button', { name: 'Observed 29 Feb 2024, 14:30' })).toHaveFocus();
});
it('respects date boundaries and clears an optional date', async () => {
  const user = userEvent.setup();
  render(<Field min="2024-02-28" max="2024-02-29" />);
  await user.click(screen.getByRole('button', { name: 'Observed 28 Feb 2024' }));
  expect(screen.getByRole('button', { name: '27 February 2024' })).toBeDisabled();
  await user.click(screen.getByRole('button', { name: 'Next month' }));
  expect(screen.getByRole('button', { name: '1 March 2024' })).toBeDisabled();
  await user.click(screen.getByRole('button', { name: 'Clear' }));
  expect(screen.getByRole('status')).toBeEmptyDOMElement();
  expect(screen.getByRole('button', { name: 'Observed Choose date' })).toHaveFocus();
});
it('closes with Escape without changing the selected date', async () => {
  const user = userEvent.setup();
  render(<Field />);
  await user.click(screen.getByRole('button', { name: 'Observed 28 Feb 2024' }));
  await user.keyboard('{Escape}');
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(screen.getByRole('status')).toHaveTextContent('2024-02-28');
});
