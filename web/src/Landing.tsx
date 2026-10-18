import TactileAction from './TactileAction'

type LandingProps = {
  onSignIn: () => void
  onGetStarted: () => void
}

const benefits = [
  ['01', 'Start with your real record'],
  ['02', 'See evidence behind each gap'],
  ['03', 'Plan around your weekly hours'],
  ['04', 'Keep every step in view'],
]

const features = [
  {
    number: '01',
    title: 'Read the record you already have',
    text: 'Bring coursework, projects, internships, and a resume into one clear skills profile.',
    icon: '↗',
    tone: 'sand',
  },
  {
    number: '02',
    title: 'Compare it with one real role',
    text: 'Separate must-haves from nice-to-haves and see where your evidence lines up.',
    icon: '⌕',
    tone: 'rose',
  },
  {
    number: '03',
    title: 'Turn the gap into a steady plan',
    text: 'Get prerequisite-ordered study goals that fit the hours you can actually give.',
    icon: '⌁',
    tone: 'sage',
  },
]

const faqs = [
  ['What can I use as my student record?', 'Paste your record or upload a resume or transcript. Project descriptions and internship experience help distinguish familiarity from skills you have built in practice.'],
  ['Can I choose how much time the plan takes?', 'Yes. Set a plan horizon and your available study hours per week. PlacementGap schedules the work within that budget and identifies anything that cannot fit.'],
  ['Where do the gap explanations come from?', 'Each requirement and evidence item links back to a source span in the job description or your profile. A course by itself is treated more cautiously than a project with described artifacts.'],
  ['Can I change my plan before it is finalized?', 'The analysis pauses at a review gate so you can approve the proposed plan, reject it with a note, or edit the schedule before the report is generated.'],
]

function Brand({ compact = false }: { compact?: boolean }) {
  return <span className={`public-brand ${compact ? 'compact' : ''}`}><img className="brand-emblem" src="/placementgap-growth-mark.png" alt="" /><span>PlacementGap</span></span>
}

export default function Landing({ onSignIn, onGetStarted }: LandingProps) {
  return <div className="landing-page">
    <header className="public-nav">
      <a className="brand-link" href="#top" aria-label="PlacementGap home"><Brand /></a>
      <nav className="public-links" aria-label="Main navigation">
        <a href="#how-it-works">How it works</a><a href="#inside">What you get</a><a href="#faq">FAQ</a>
      </nav>
      <div className="public-actions"><TactileAction size="micro" onClick={onSignIn}>Sign in</TactileAction><TactileAction size="compact" onClick={onGetStarted}>Get started</TactileAction></div>
    </header>

    <main id="top">
      <section className="hero-section">
        <div className="hero-orbit orbit-one" /><div className="hero-orbit orbit-two" />
        <div className="hero-content">
          <div className="hero-kicker"><span className="kicker-mark">✳</span> CAREER GROWTH, WITH A PLAN</div>
          <h1>Your next role,<br /><em>within reach.</em></h1>
          <p className="hero-copy">Bring your real academic and project record. Pick a role you want. Get a grounded, week-by-week plan for closing the skills gap.</p>
          <div className="hero-actions"><TactileAction className="tactile-large" onClick={onGetStarted}>Build my plan</TactileAction><TactileAction className="tactile-large" onClick={() => document.getElementById('how-it-works')?.scrollIntoView({ behavior: 'smooth' })}>See how it works</TactileAction></div>
          <div className="hero-proof"><span className="proof-icon">✓</span><span>Source-linked evidence</span><i /><span>Hours that add up</span><i /><span>Built around your goal</span></div>
        </div>
        <div className="hero-preview" aria-label="Sample PlacementGap skills report">
          <div className="preview-window">
            <div className="preview-top"><span className="window-dots"><i /><i /><i /></span><span>YOUR ROLE SNAPSHOT</span><span className="preview-status"><i /> MATCHING</span></div>
            <div className="preview-body">
              <div className="preview-heading"><div><small>SOFTWARE ENGINEER · SAMPLE</small><b>Your next steps, at a glance.</b></div><span className="preview-arrow">↗</span></div>
              <div className="preview-metrics"><div><strong>08</strong><small>skills reviewed</small></div><div><strong>03</strong><small>to build next</small></div><div><strong>06<span>w</span></strong><small>planned together</small></div></div>
              <div className="preview-divider" />
              <div className="preview-row"><span className="preview-skill"><i className="skill-dot ready" /> Python</span><span className="preview-evidence">PROJECT · P. 02</span><b className="status-ready">EVIDENCE FOUND</b></div>
              <div className="preview-row"><span className="preview-skill"><i className="skill-dot learning" /> Docker</span><span className="preview-evidence">NO SOURCE MATCH</span><b className="status-learning">BUILD NEXT</b></div>
              <div className="preview-row"><span className="preview-skill"><i className="skill-dot learning" /> Unit testing</span><span className="preview-evidence">COURSE · P. 01</span><b className="status-learning">PRACTICE MORE</b></div>
              <div className="preview-plan"><span className="plan-spark">✳</span><span><small>YOUR FIRST MILESTONE</small><b>Set up a test suite</b></span><span className="plan-time">3.5 h</span></div>
            </div>
          </div>
          <div className="floating-note"><span>↳</span><div><small>EVERY CLAIM</small><b>points to its source</b></div></div>
        </div>
        <div className="hero-bottom-label"><span>01 / 04</span><span>FROM YOUR RECORD TO YOUR NEXT MOVE</span><span>SCROLL TO EXPLORE ↓</span></div>
      </section>

      <section className="benefit-strip" aria-label="PlacementGap principles">
        {benefits.map(([number, label]) => <div className="benefit-item" key={number}><span>{number}</span><b>{label}</b><i>✳</i></div>)}
      </section>

      <section className="section-block process-section" id="how-it-works">
        <div className="section-heading"><div><span className="eyebrow light-eyebrow">A CLEARER WAY FORWARD</span><h2>Start where you are.<br /><em>Build from there.</em></h2></div><p>No generic course lists. Just the skills this role asks for, what your record already shows, and the right next step.</p></div>
        <div className="feature-grid" id="inside">
          {features.map(item => <article className={`feature-card ${item.tone}`} key={item.number}>
            <div className="feature-top"><span>{item.number} / THE PROCESS</span><span className="feature-icon">{item.icon}</span></div>
            <h3>{item.title}</h3><p>{item.text}</p><span className="feature-rule" /><span className="feature-more">BUILT AROUND YOUR EVIDENCE <b>↗</b></span>
          </article>)}
        </div>
      </section>

      <section className="section-block evidence-section">
        <div className="evidence-art">
          <div className="evidence-paper">
            <div className="paper-kicker">PLACEMENTGAP · EVIDENCE NOTE</div><div className="paper-title">A claim should<br />come with a <em>source.</em></div>
            <div className="paper-quote"><span>“</span><p>Built and deployed a REST API using Python and PostgreSQL.</p></div>
            <div className="paper-source"><span>PROFILE · PROJECTS</span><b>Page 02 · Lines 08–09</b><i>↗</i></div>
            <div className="paper-stamp">SOURCE<br />LINKED</div>
          </div>
          <div className="orbit-caption"><span>01</span> YOUR RECORD STAYS IN THE LOOP</div>
        </div>
        <div className="evidence-copy"><span className="eyebrow light-eyebrow">THOUGHTFUL BY DESIGN</span><h2>See why a skill<br />is a <em>gap.</em></h2><p>Each finding is grounded in the job description and your own record. See the excerpt, the interpretation, and the level the role expects before you decide what to work on.</p>
          <ul className="check-list"><li><span>✓</span> Evidence spans you can inspect</li><li><span>✓</span> Coursework and projects weighed differently</li><li><span>✓</span> Unmatched requirements stay visible</li></ul>
          <TactileAction onClick={onGetStarted}>Explore your fit</TactileAction>
        </div>
      </section>

      <section className="section-block rhythm-section">
        <div className="rhythm-title"><span className="eyebrow light-eyebrow">A PLAN THAT RESPECTS YOUR TIME</span><h2>Make room for the<br /><em>work that matters.</em></h2><p>Choose your weeks. Set your study hours. Your learning goals get ordered, balanced, and broken into sessions you can follow.</p></div>
        <div className="week-card">
          <div className="week-card-head"><div><small>YOUR LEARNING RHYTHM</small><b>Software Engineer · 6 weeks</b></div><span>8 h / WEEK</span></div>
          {[['WEEK 01', 'Git foundations', '4h', 49], ['WEEK 02', 'Docker basics', '3.5h', 43], ['WEEK 03', 'Unit testing', '5h', 63], ['WEEK 04', 'Build a portfolio project', '6h', 75]].map(([week, label, duration, progress]) => <div className="week-line" key={String(week)}><span>{week}</span><b>{label}</b><i><em style={{ width: `${progress}%` }} /></i><small>{duration}</small></div>)}
          <div className="week-card-foot"><span>PREREQUISITES COME FIRST</span><b>24h planned <i>↗</i></b></div>
        </div>
      </section>

      <section className="section-block quote-section">
        <div className="quote-mark">“</div><span className="eyebrow light-eyebrow">A BETTER KIND OF CAREER PLAN</span>
        <blockquote>Less guessing what to learn.<br />More knowing <em>why it matters.</em></blockquote>
        <div className="quote-credits"><span>PLACEMENTGAP PRINCIPLE</span><i /><span>YOUR RECORD. YOUR ROLE. YOUR NEXT STEP.</span></div>
      </section>

      <section className="section-block faq-section" id="faq">
        <div className="faq-intro"><span className="eyebrow light-eyebrow">GOOD QUESTIONS</span><h2>Before you<br /><em>get started.</em></h2><p>A few details about how PlacementGap turns your record into a plan.</p><TactileAction onClick={onGetStarted}>Try PlacementGap</TactileAction></div>
        <div className="faq-list">{faqs.map(([question, answer], index) => <details className="faq-item" key={question} open={index === 0}><summary><span>{question}</span><i>+</i></summary><p>{answer}</p></details>)}</div>
      </section>

      <section className="closing-section"><div className="closing-stamp">PG <i>✳</i></div><span className="eyebrow">YOUR NEXT CHAPTER STARTS HERE</span><h2>Choose the role.<br /><em>We’ll map the steps.</em></h2><TactileAction className="tactile-large" onClick={onGetStarted}>Build my learning plan</TactileAction><small>Start with your record. Leave with a plan you can trust.</small></section>
    </main>

    <footer className="public-footer"><div className="footer-top"><div className="footer-brand"><a className="brand-link" href="#top"><Brand /></a><p>Evidence-grounded career planning<br />for the role you want next.</p></div><div className="footer-nav"><span>EXPLORE</span><a href="#how-it-works">How it works</a><a href="#inside">What you get</a><a href="#faq">FAQ</a></div><div className="footer-nav"><span>YOUR WORKSPACE</span><button onClick={onSignIn}>Open workspace</button><button onClick={onGetStarted}>Create an account</button><a href="#top">Back to top ↑</a></div><div className="footer-signoff">Make your next move<br /><em>with a little more clarity.</em></div></div><div className="footer-bottom"><Brand compact /><span>© 2026 PLACEMENTGAP</span><span>YOUR RECORD IS YOURS.</span></div></footer>
  </div>
}
