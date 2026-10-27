import { useEffect, useRef, useState } from 'react'
import { FileCheck2, ShieldCheck } from 'lucide-react'

export default function TermsAgreementModal({ onAccept }) {
  const dialog = useRef(null)
  const heading = useRef(null)
  const [acknowledged, setAcknowledged] = useState(false)
  const [declined, setDeclined] = useState(false)

  useEffect(() => {
    const element = dialog.current
    element.showModal()
    heading.current?.focus()
    return () => element.close()
  }, [])

  useEffect(() => { heading.current?.focus() }, [declined])

  return (
    <div className="terms-entry">
      <div className="terms-entry-brand" aria-hidden="true">CLARA<span>Clinical information workspace</span></div>
      <dialog ref={dialog} className="terms-dialog" aria-labelledby="terms-title"
        aria-describedby="terms-intro" onCancel={event => event.preventDefault()}>
        <header className="terms-header">
          <span className="terms-symbol" aria-hidden="true"><ShieldCheck size={22} /></span>
          <div>
            <p className="terms-eyebrow">CLARA / Research and evaluation</p>
            <h1 id="terms-title" ref={heading} tabIndex={-1}>
              {declined ? 'Your choice is respected' : 'Terms of Service and Confidentiality Agreement'}
            </h1>
          </div>
        </header>

        {declined ? <>
          <div className="terms-body terms-declined">
            <p id="terms-intro">You have not accepted the agreement. CLARA’s records and chat remain closed.</p>
            <p>You may close this tab, or review the agreement if you wish to continue.</p>
          </div>
          <footer className="terms-footer">
            <button type="button" className="primary-button" onClick={() => { setAcknowledged(false); setDeclined(false) }}>Review agreement</button>
          </footer>
        </> : <>
          <div className="terms-body" tabIndex={0} role="region" aria-label="Agreement text">
            <p id="terms-intro">Welcome to <strong>CLARA</strong>. Please read this agreement before entering the web application. By selecting <strong>I agree and continue</strong>, you acknowledge that you have read, understood, and accepted the terms below.</p>

            <section aria-labelledby="terms-use">
              <h2 id="terms-use"><span>1</span>Information System Only</h2>
              <ul>
                <li><strong>Intended use:</strong> CLARA is an academic research prototype for organizing, retrieving, and reviewing clinical records and reference information. It is intended for research, demonstration, and system evaluation.</li>
                <li><strong>Not a medical diagnosis or treatment service:</strong> Displayed records, AI-generated responses, summaries, alerts, guideline excerpts, and model estimates are informational only. They do not constitute a medical diagnosis, prescription, treatment plan, or emergency service.</li>
                <li><strong>Professional review:</strong> CLARA does not replace a qualified healthcare professional’s judgment. Do not use its outputs alone to make clinical decisions. Verify information against the original source documents and appropriate professional guidance.</li>
              </ul>
            </section>

            <section aria-labelledby="terms-confidentiality">
              <h2 id="terms-confidentiality"><span>2</span>Access and Confidentiality</h2>
              <ul>
                <li><strong>Responsible access:</strong> Use CLARA only for the research or evaluation activities provided by the research team. Do not disclose, redistribute, or publish record contents, screenshots, or downloaded PDFs without authorization.</li>
                <li><strong>Stored information:</strong> CLARA stores extracted patient records and source PDFs on the system’s server. Saved conversations are also stored in the browser used to access the application; avoid leaving them accessible on shared devices.</li>
                <li><strong>Name removal:</strong> The current demo records use patient IDs instead of names. Other details, including dates and record identifiers, may remain. Treat the records as confidential; name removal does not make them fully anonymous.</li>
                <li><strong>AI processing:</strong> When AI chat is used, your question and selected record or guideline excerpts may be sent to the configured AI provider, currently Groq, to generate a response. Do not enter personal names, contact details, or other identifying information.</li>
                {import.meta.env.VITE_RESPONDENT_DEMO === 'true' && <li><strong>Online demo access:</strong> The online demo uses Vercel and Microsoft Dev Tunnels to deliver the application and relay requests and responses to the research computer. Record information and chat content pass through these services when you use the demo.</li>}
              </ul>
            </section>

            <section aria-labelledby="terms-retention">
              <h2 id="terms-retention"><span>3</span>Data Handling and Retention</h2>
              <ul>
                <li><strong>Approved records:</strong> Use only the demo records supplied or approved by the research team. Access to a record does not grant permission to copy it, share it, or use it for another purpose.</li>
                <li><strong>Saved conversations:</strong> You may delete saved conversations through the conversation history controls. Deleting a conversation does not delete its underlying patient records or source PDFs.</li>
                <li><strong>Record requests:</strong> Contact the research team for questions about access, corrections, retention, or removal of study records. CLARA does not currently provide account registration or automatic account-wide data deletion.</li>
              </ul>
            </section>

            <section aria-labelledby="terms-evaluation">
              <h2 id="terms-evaluation"><span>4</span>Record Use and Evaluation Guidelines</h2>
              <ul>
                <li><strong>Evaluation use:</strong> Follow the assigned tasks and provide honest feedback about usability, clarity, and system behavior. Do not enter real patient information into the evaluation chat.</li>
                <li><strong>Source limitations:</strong> PDF formatting, missing text, incomplete records, and incorrect dates can affect extraction and retrieval. AI responses may also contain errors or omit relevant information.</li>
                <li><strong>Verification:</strong> Review the cited source and PDF page where available. Report discrepancies to the research team instead of treating the generated response as a verified clinical conclusion.</li>
              </ul>
            </section>

            <section aria-labelledby="terms-responsibility">
              <h2 id="terms-responsibility"><span>5</span>Limitations and User Responsibility</h2>
              <ul>
                <li><strong>Research prototype:</strong> CLARA is provided for academic evaluation without a guarantee of uninterrupted availability, completeness, or accuracy.</li>
                <li><strong>Use of outputs:</strong> Users are responsible for verifying information and for decisions made using the system. The research team and developers do not provide medical care through CLARA.</li>
                <li><strong>Limitation of liability:</strong> To the extent permitted by applicable law, the research team and developers are not liable for decisions or outcomes arising from reliance on CLARA’s outputs. Nothing in this agreement excludes rights or responsibilities that cannot lawfully be excluded.</li>
              </ul>
            </section>
          </div>

          <footer className="terms-footer">
            <label className="terms-acknowledgment">
              <input type="checkbox" checked={acknowledged} onChange={event => setAcknowledged(event.target.checked)} />
              <span>I have read and understood this agreement, including that CLARA is an information system only.</span>
            </label>
            <div className="terms-actions">
              <button type="button" className="text-button" onClick={() => setDeclined(true)}>I do not agree</button>
              <button type="button" className="primary-button" disabled={!acknowledged} onClick={onAccept}>
                <FileCheck2 size={16} aria-hidden="true" />I agree and continue
              </button>
            </div>
          </footer>
        </>}
      </dialog>
    </div>
  )
}
