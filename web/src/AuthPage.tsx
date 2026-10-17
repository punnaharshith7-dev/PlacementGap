import { useEffect, useRef, useState } from 'react'

export type PlacementUser = { id: string; full_name: string; email: string; phone: string | null }
type AuthMode = 'signin' | 'signin_code' | 'verify_login' | 'signup' | 'verify_signup' | 'forgot' | 'reset'
type ProviderName = 'google' | 'microsoft' | 'github'

const providerLabels: Array<{ id: ProviderName; label: string; mark: string }> = [
  { id: 'google', label: 'Google', mark: 'G' },
  { id: 'microsoft', label: 'Microsoft', mark: '▦' },
  { id: 'github', label: 'GitHub', mark: '◉' },
]
const api = (path: string) => `${import.meta.env.VITE_API_URL ?? ''}${path}`
const OTP_LENGTH = 6

function OtpCodeInput({ value, onChange, disabled = false, success = false }: { value: string; onChange: (next: string) => void; disabled?: boolean; success?: boolean }) {
  const inputs = useRef<Array<HTMLInputElement | null>>([])
  const pendingFocus = useRef<number | null>(null)
  const focusAt = (index: number) => inputs.current[Math.max(0, Math.min(index, OTP_LENGTH - 1))]?.focus()

  useEffect(() => {
    const target = pendingFocus.current ?? Math.min(value.length, OTP_LENGTH - 1)
    pendingFocus.current = null
    if (!disabled && !success) focusAt(target)
  }, [disabled, success, value])

  const fillFrom = (index: number, raw: string) => {
    const incoming = raw.replace(/\D/g, '').slice(0, OTP_LENGTH - index)
    if (!incoming) return
    const digits = value.split('')
    for (let offset = 0; offset < incoming.length; offset += 1) {
      digits[index + offset] = incoming[offset]
    }
    pendingFocus.current = Math.min(index + incoming.length, OTP_LENGTH - 1)
    onChange(digits.join('').slice(0, OTP_LENGTH))
  }

  const pasteCode = (event: React.ClipboardEvent<HTMLInputElement>, index: number) => {
    const pasted = event.clipboardData.getData('text').replace(/\D/g, '')
    if (!pasted) return
    event.preventDefault()
    fillFrom(index, pasted)
  }

  return <div className={`otp-control ${success ? 'is-success' : ''}`}>
    <div className="otp-digit-row" role="group" aria-label="Six-digit verification code">
      {Array.from({ length: OTP_LENGTH }, (_, index) => {
        const digit = value[index] ?? ''
        return <input
          key={index}
          ref={element => { inputs.current[index] = element }}
          className={`otp-digit ${digit ? 'has-value' : ''}`}
          type="text"
          inputMode="numeric"
          pattern="[0-9]*"
          autoComplete={index === 0 ? 'one-time-code' : 'off'}
          aria-label={`Digit ${index + 1} of ${OTP_LENGTH}`}
          aria-describedby="otp-entry-hint"
          value={digit}
          maxLength={index === 0 ? OTP_LENGTH : 1}
          required
          disabled={disabled || success || index > value.length}
          onChange={event => fillFrom(index, event.currentTarget.value)}
          onPaste={event => pasteCode(event, index)}
          onKeyDown={event => {
            if (event.key === 'Backspace' || event.key === 'Delete') {
              event.preventDefault()
              if (value[index]) { pendingFocus.current = index; onChange(value.slice(0, index) + value.slice(index + 1)) }
              else if (index > 0) { pendingFocus.current = index - 1; onChange(value.slice(0, index - 1) + value.slice(index)) }
            } else if (event.key === 'ArrowLeft' && index > 0) {
              event.preventDefault(); focusAt(index - 1)
            } else if (event.key === 'ArrowRight' && index < OTP_LENGTH - 1 && index < value.length) {
              event.preventDefault(); focusAt(index + 1)
            }
          }}
        />
      })}
    </div>
    <small className="otp-entry-hint" id="otp-entry-hint">Type the code, paste all six digits, or use your device’s email-code autofill.</small>
    {success && <div className="otp-success-message" role="status" aria-live="polite"><span className="otp-success-mark" aria-hidden="true">✓</span><span><b>Code verified</b><small>Opening your PlacementGap workspace…</small></span></div>}
  </div>
}

async function post<T>(path: string, body: Record<string, string>): Promise<T> {
  const response = await fetch(api(path), {
    method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  const result = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'We couldn’t complete that request. Please try again.')
  return result as T
}

export default function AuthPage({ initialMode, onAuthenticated, onHome }: {
  initialMode: 'signin' | 'signup'
  onAuthenticated: (user: PlacementUser) => void
  onHome: () => void
}) {
  const [mode, setMode] = useState<AuthMode>(initialMode)
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [password, setPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [code, setCode] = useState('')
  const [challengeId, setChallengeId] = useState('')
  const [developmentCode, setDevelopmentCode] = useState('')
  const [providerReady, setProviderReady] = useState<Record<ProviderName, boolean>>({ google: false, microsoft: false, github: false })
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(false)
  const [otpVerified, setOtpVerified] = useState(false)

  useEffect(() => {
    setMode(initialMode)
    const queryError = new URLSearchParams(window.location.search).get('auth_error')
    if (queryError) setError('Sign-in didn’t finish. Check the provider setup and try again.')
    void fetch(api('/auth/providers'), { credentials: 'include' }).then(response => response.json()).then(result => setProviderReady(result.providers ?? {})).catch(() => undefined)
  }, [initialMode])

  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setError(''); setNotice(''); setLoading(true)
    try {
      if (mode === 'signin') {
        const result = await post<{ user: PlacementUser }>('/auth/login', { email, password })
        onAuthenticated(result.user)
      } else if (mode === 'signin_code') {
        const result = await post<{ challenge_id: string; development_code?: string; message: string }>('/auth/login-code', { email })
        setChallengeId(result.challenge_id); setDevelopmentCode(result.development_code ?? ''); setCode(result.development_code ?? ''); setOtpVerified(false)
        setNotice(result.message); setMode('verify_login')
      } else if (mode === 'signup') {
        const result = await post<{ challenge_id: string; development_code?: string; message: string }>('/auth/signup', { full_name: fullName, email, phone, password })
        setChallengeId(result.challenge_id); setDevelopmentCode(result.development_code ?? ''); setCode(result.development_code ?? ''); setOtpVerified(false)
        setNotice(result.message); setMode('verify_signup')
      } else if (mode === 'verify_signup') {
        const result = await post<{ user: PlacementUser }>('/auth/verify', { challenge_id: challengeId, code })
        setOtpVerified(true)
        await new Promise(resolve => window.setTimeout(resolve, 1100))
        onAuthenticated(result.user)
      } else if (mode === 'verify_login') {
        const result = await post<{ user: PlacementUser }>('/auth/login-verify', { challenge_id: challengeId, code })
        setOtpVerified(true)
        await new Promise(resolve => window.setTimeout(resolve, 1100))
        onAuthenticated(result.user)
      } else if (mode === 'forgot') {
        const result = await post<{ challenge_id?: string; development_code?: string; message: string }>('/auth/forgot', { email })
        if (result.challenge_id) {
          setChallengeId(result.challenge_id); setDevelopmentCode(result.development_code ?? ''); setCode(result.development_code ?? '')
          setOtpVerified(false)
          setNotice(result.message); setMode('reset')
        } else setNotice(result.message)
      } else {
        const result = await post<{ user: PlacementUser }>('/auth/reset', { challenge_id: challengeId, code, new_password: newPassword })
        setOtpVerified(true)
        await new Promise(resolve => window.setTimeout(resolve, 1100))
        onAuthenticated(result.user)
      }
    } catch (exception) {
      setError(exception instanceof Error ? exception.message : 'We couldn’t complete that request.')
    } finally { setLoading(false) }
  }

  const chooseProvider = (provider: ProviderName) => {
    if (!providerReady[provider]) {
      setError(`${providerLabels.find(item => item.id === provider)?.label} sign-in needs its OAuth client ID and secret configured by the site owner.`)
      return
    }
    window.location.assign(api(`/auth/${provider}/start`))
  }

  const titles: Record<AuthMode, { kicker: string; title: string; body: string }> = {
    signin: { kicker: 'WELCOME BACK', title: 'Good to see you.', body: 'Sign in to continue your career plan.' },
    signin_code: { kicker: 'PASSWORDLESS SIGN IN', title: 'Use your email code.', body: 'We’ll send a one-time code to the email on your account.' },
    verify_login: { kicker: 'ONE QUICK CHECK', title: 'Check your inbox.', body: `Enter the six-digit sign-in code sent to ${email}.` },
    signup: { kicker: 'YOUR NEXT STEP STARTS HERE', title: 'Make room to grow.', body: 'Create an account and start with the experience you already have.' },
    verify_signup: { kicker: 'ONE QUICK CHECK', title: 'Check your inbox.', body: `Enter the six-digit code we sent to ${email}.` },
    forgot: { kicker: 'ACCOUNT RECOVERY', title: 'Let’s get you back in.', body: 'Enter the email address on your account and we’ll send a reset code.' },
    reset: { kicker: 'SECURE YOUR ACCOUNT', title: 'Choose a new password.', body: 'Verify the email code, then set a fresh password for your account.' },
  }
  const current = titles[mode]
  const showProviders = mode === 'signin' || mode === 'signup'
  const isOtpMode = mode === 'verify_signup' || mode === 'verify_login' || mode === 'reset'

  return <div className="auth-page">
    <aside className="auth-story">
      <button className="auth-brand-button" onClick={onHome} aria-label="PlacementGap home"><span className="public-brand"><img className="brand-emblem" src="/placementgap-growth-mark.png" alt="" /><span>PlacementGap</span></span></button>
      <div className="auth-story-copy"><span className="eyebrow">YOUR RECORD. YOUR NEXT MOVE.</span><h2>Keep your<br />ambition <em>in focus.</em></h2><p>Every requirement in context. Every claim tied to evidence. A plan that fits your week.</p></div>
      <div className="auth-story-note"><span className="story-note-icon">✳</span><div><small>YOUR CAREER PLAN</small><b>Grounded in what you’ve done.<br />Built for where you want to go.</b></div></div>
      <div className="auth-story-foot"><span>PLACEMENTGAP · 2026</span><span>MADE FOR THE NEXT STEP</span></div>
    </aside>
    <main className="auth-main">
      <div className="auth-mobile-brand"><button className="auth-brand-button" onClick={onHome}><span className="public-brand"><img className="brand-emblem" src="/placementgap-growth-mark.png" alt="" /><span>PlacementGap</span></span></button><button className="auth-home-link" onClick={onHome}>← Home</button></div>
      <div className="auth-card">
        <div className="auth-heading"><span className="eyebrow light-eyebrow">{current.kicker}</span><h1>{current.title}</h1><p>{current.body}</p></div>
        {showProviders && <><div className="provider-grid">{providerLabels.map(provider => <button className="provider-button" key={provider.id} onClick={() => chooseProvider(provider.id)} type="button"><span className={`provider-mark ${provider.id}`}>{provider.mark}</span><span>Continue with {provider.label}</span><span className="provider-arrow">↗</span></button>)}</div><div className="auth-or"><span>OR USE YOUR EMAIL</span></div></>}
        <form className="auth-form" onSubmit={submit}>
          {mode === 'signup' && <label>Full name<input autoComplete="name" value={fullName} onChange={event => setFullName(event.target.value)} placeholder="Your full name" required minLength={2} maxLength={100} /></label>}
          {(mode === 'signin' || mode === 'signin_code' || mode === 'signup' || mode === 'forgot') && <label>Email address<input autoComplete="email" type="email" value={email} onChange={event => setEmail(event.target.value)} placeholder="you@example.com" required /></label>}
          {mode === 'signup' && <label>Phone number<input autoComplete="tel" type="tel" value={phone} onChange={event => setPhone(event.target.value)} placeholder="+1 555 010 0000" required /></label>}
          {mode === 'signin' && <label>Password<input autoComplete="current-password" type="password" value={password} onChange={event => setPassword(event.target.value)} placeholder="Your password" required /><button className="inline-link forgot-link" type="button" onClick={() => { setMode('forgot'); setError(''); setNotice('') }}>Forgot password?</button></label>}
          {mode === 'signup' && <label>Password<input autoComplete="new-password" type="password" value={password} onChange={event => setPassword(event.target.value)} placeholder="At least 8 characters" required minLength={8} maxLength={128} /><small className="field-hint">Use at least 8 characters.</small></label>}
          {isOtpMode && <label className="otp-field-label">Six-digit verification code<OtpCodeInput value={code} onChange={setCode} disabled={loading} success={otpVerified} /></label>}
          {mode === 'reset' && <label>New password<input autoComplete="new-password" type="password" value={newPassword} onChange={event => setNewPassword(event.target.value)} placeholder="At least 8 characters" required minLength={8} maxLength={128} /></label>}
          {notice && <div className="auth-notice">{notice}</div>}
          {isOtpMode && developmentCode && <div className="otp-message-card" role="status"><span className="otp-message-icon" aria-hidden="true">✉</span><span className="otp-message-copy"><small>LOCAL EMAIL · VERIFICATION CODE</small><b>{developmentCode} is your verification code.</b><small>Email delivery is off in local mode; this code is shown for testing.</small></span><button className="otp-fill-button" type="button" onClick={() => { setCode(developmentCode); document.querySelector<HTMLInputElement>('.otp-digit-row input:last-child')?.focus() }}>Fill code</button></div>}
          {isOtpMode && !developmentCode && <div className="otp-delivery-card" role="status"><span className="otp-message-icon" aria-hidden="true">✉</span><span className="otp-message-copy"><small>EMAIL · VERIFICATION</small><b>Code sent to {email}</b><small>Use the newest six-digit code from your inbox.</small></span><span className="otp-sent-indicator" aria-label="Email sent" /></div>}
          {error && <div className="auth-error" role="alert">{error}</div>}
          <button className="pill-action dark auth-submit" disabled={loading || (isOtpMode && code.length !== OTP_LENGTH)}>{loading ? 'Please wait…' : mode === 'signin' ? 'Sign in' : mode === 'signin_code' ? 'Send sign-in code' : mode === 'verify_login' ? 'Verify and sign in' : mode === 'signup' ? 'Create account' : mode === 'verify_signup' ? 'Verify email' : mode === 'forgot' ? 'Send reset code' : 'Reset password'}<span>↗</span></button>
        </form>
        {mode === 'signin' && <p className="auth-switch">New to PlacementGap? <button className="inline-link" onClick={() => { setMode('signup'); setError(''); setNotice('') }}>Create an account</button></p>}
        {mode === 'signin' && <p className="auth-switch">Prefer not to use a password? <button className="inline-link" onClick={() => { setMode('signin_code'); setError(''); setNotice('') }}>Sign in with an email code</button></p>}
        {mode === 'signin_code' && <p className="auth-switch">Want to use your password? <button className="inline-link" onClick={() => { setMode('signin'); setError(''); setNotice('') }}>Back to password sign in</button></p>}
        {mode === 'signup' && <p className="auth-switch">Already have an account? <button className="inline-link" onClick={() => { setMode('signin'); setError(''); setNotice('') }}>Sign in</button></p>}
        {(mode === 'verify_signup' || mode === 'verify_login' || mode === 'reset') && <p className="auth-switch">Wrong email address? <button className="inline-link" onClick={() => { setMode(mode === 'reset' ? 'forgot' : mode === 'verify_login' ? 'signin_code' : 'signup'); setChallengeId(''); setCode(''); setDevelopmentCode(''); setError(''); setNotice('') }}>Go back</button></p>}
        {mode === 'forgot' && <p className="auth-switch"><button className="inline-link" onClick={() => { setMode('signin'); setError(''); setNotice('') }}>← Back to sign in</button></p>}
        <div className="auth-safe"><span>✳</span>Your profile stays yours. Sign in to see your saved work.</div>
      </div>
      <button className="auth-home-desktop" onClick={onHome}>← Back to PlacementGap</button>
    </main>
  </div>
}
