import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import * as cognito from 'aws-amplify/auth';
import { AuthPage } from '../auth/AuthPage';

const auth = vi.hoisted(() => ({ refresh: vi.fn(), expired: false, enterLocal: vi.fn() }));
vi.mock('../auth/AuthProvider', () => ({ useAuth: () => auth }));
vi.mock('../config', () => ({ authConfigured: true, config: { devMode: false } }));
vi.mock('aws-amplify/auth', () => ({
  signIn: vi.fn(),
  signUp: vi.fn(),
  confirmSignUp: vi.fn(),
  resendSignUpCode: vi.fn(),
  confirmSignIn: vi.fn(),
  resetPassword: vi.fn(),
  confirmResetPassword: vi.fn(),
}));

beforeEach(() => {
  vi.resetAllMocks();
  auth.expired = false;
});
afterEach(cleanup);
const email = 'explorer@example.invalid';
const password = 'Test-only-Password9!';
async function identity(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Email address'), email);
  await user.type(screen.getByLabelText('Password'), password);
}

it('registers required attributes, confirms email, and returns to sign-in', async () => {
  const user = userEvent.setup();
  vi.mocked(cognito.signUp).mockResolvedValue({
    isSignUpComplete: false,
    nextStep: {
      signUpStep: 'CONFIRM_SIGN_UP',
      codeDeliveryDetails: { deliveryMedium: 'EMAIL', destination: email, attributeName: 'email' },
    },
  });
  vi.mocked(cognito.confirmSignUp).mockResolvedValue({
    isSignUpComplete: true,
    nextStep: { signUpStep: 'DONE' },
  });
  render(<AuthPage />);
  await user.click(screen.getByRole('button', { name: 'Create an account' }));
  await identity(user);
  await user.type(screen.getByLabelText('First name'), 'Sam');
  await user.type(screen.getByLabelText('Last name'), 'Explorer');
  await user.click(screen.getByRole('button', { name: 'Create account' }));
  await screen.findByRole('button', { name: 'Verify email' });
  expect(cognito.signUp).toHaveBeenCalledWith({
    username: email,
    password,
    options: { userAttributes: { email, given_name: 'Sam', family_name: 'Explorer' } },
  });
  await user.type(screen.getByLabelText('Verification code'), '123456');
  await user.click(screen.getByRole('button', { name: 'Verify email' }));
  await screen.findByText('Email verified. You can now sign in.');
  expect(cognito.confirmSignUp).toHaveBeenCalledWith({
    username: email,
    confirmationCode: '123456',
  });
  expect(screen.getByLabelText('Password')).toHaveValue('');
});

it('resends a verification code and preserves input after a wrong code', async () => {
  const user = userEvent.setup();
  vi.mocked(cognito.confirmSignUp).mockRejectedValue(new Error('Incorrect verification code.'));
  render(<AuthPage />);
  await user.click(screen.getByRole('button', { name: 'Verify an existing account' }));
  await user.type(screen.getByLabelText('Email address'), email);
  await user.click(screen.getByRole('button', { name: 'Resend verification code' }));
  await screen.findByText('A fresh verification code is on its way.');
  expect(cognito.resendSignUpCode).toHaveBeenCalledWith({ username: email });
  await user.type(screen.getByLabelText('Verification code'), '000000');
  await user.click(screen.getByRole('button', { name: 'Verify email' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect verification code.');
  expect(screen.getByLabelText('Verification code')).toHaveValue('000000');
});

it('signs in successfully and refreshes the application identity', async () => {
  const user = userEvent.setup();
  vi.mocked(cognito.signIn).mockResolvedValue({
    isSignedIn: true,
    nextStep: { signInStep: 'DONE' },
  });
  render(<AuthPage />);
  await identity(user);
  await user.click(screen.getByRole('button', { name: /^Sign in$/ }));
  await waitFor(() => expect(auth.refresh).toHaveBeenCalledOnce());
  expect(screen.getByLabelText('Password')).toHaveValue('');
});

it('handles a temporary password challenge without changing the challenge account', async () => {
  const user = userEvent.setup();
  vi.mocked(cognito.signIn).mockResolvedValue({
    isSignedIn: false,
    nextStep: { signInStep: 'CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED' },
  });
  vi.mocked(cognito.confirmSignIn).mockResolvedValue({
    isSignedIn: true,
    nextStep: { signInStep: 'DONE' },
  });
  render(<AuthPage />);
  await identity(user);
  await user.click(screen.getByRole('button', { name: /^Sign in$/ }));
  await screen.findByLabelText('New password');
  expect(screen.getByLabelText('Email address')).toBeDisabled();
  await user.type(screen.getByLabelText('First name'), 'Sam');
  await user.type(screen.getByLabelText('Last name'), 'Explorer');
  await user.type(screen.getByLabelText('New password'), password);
  await user.click(screen.getByRole('button', { name: 'Set password & continue' }));
  await waitFor(() => expect(auth.refresh).toHaveBeenCalledOnce());
  expect(cognito.confirmSignIn).toHaveBeenCalledWith({
    challengeResponse: password,
    options: { userAttributes: { given_name: 'Sam', family_name: 'Explorer' } },
  });
});

it('resets a forgotten password and clears the code and password', async () => {
  const user = userEvent.setup();
  vi.mocked(cognito.resetPassword).mockResolvedValue({
    isPasswordReset: false,
    nextStep: {
      resetPasswordStep: 'CONFIRM_RESET_PASSWORD_WITH_CODE',
      codeDeliveryDetails: { deliveryMedium: 'EMAIL', destination: email, attributeName: 'email' },
    },
  });
  render(<AuthPage />);
  await user.click(screen.getByRole('button', { name: 'Forgot password?' }));
  await user.type(screen.getByLabelText('Email address'), email);
  await user.click(screen.getByRole('button', { name: 'Send reset code' }));
  await screen.findByLabelText('New password');
  await user.type(screen.getByLabelText('Verification code'), '123456');
  await user.type(screen.getByLabelText('New password'), password);
  await user.click(screen.getByRole('button', { name: 'Update password' }));
  await screen.findByText('Password updated. Sign in with your new password.');
  expect(cognito.confirmResetPassword).toHaveBeenCalledWith({
    username: email,
    confirmationCode: '123456',
    newPassword: password,
  });
  expect(screen.getByLabelText('Password')).toHaveValue('');
});

it('prevents navigation and duplicate requests while signing in', async () => {
  const user = userEvent.setup();
  let resolve!: (value: Awaited<ReturnType<typeof cognito.signIn>>) => void;
  vi.mocked(cognito.signIn).mockReturnValue(
    new Promise((done) => {
      resolve = done;
    }),
  );
  render(<AuthPage />);
  await identity(user);
  await user.click(screen.getByRole('button', { name: /^Sign in$/ }));
  expect(screen.getByRole('button', { name: 'Create an account' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Forgot password?' })).toBeDisabled();
  expect(screen.getByLabelText('Email address')).toBeDisabled();
  resolve({ isSignedIn: true, nextStep: { signInStep: 'DONE' } });
  await waitFor(() => expect(auth.refresh).toHaveBeenCalledOnce());
  expect(cognito.signIn).toHaveBeenCalledOnce();
});

it('shows sign-in errors and an explicit expired-session message', async () => {
  const user = userEvent.setup();
  auth.expired = true;
  vi.mocked(cognito.signIn).mockRejectedValue(new Error('Incorrect username or password.'));
  render(<AuthPage />);
  expect(screen.getByText('Your session expired. Please sign in again.')).toBeVisible();
  await identity(user);
  await user.click(screen.getByRole('button', { name: /^Sign in$/ }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect username or password.');
  expect(screen.getByLabelText('Email address')).toHaveValue(email);
});
