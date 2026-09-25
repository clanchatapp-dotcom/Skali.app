import { useParams, useNavigate, Link } from 'react-router-dom'
import { ArrowLeft, FileText, Shield, Users, Cookie } from 'lucide-react'

// Skali legal documents. These are the launch-safe baseline policies referenced from
// the sign-in screen and Settings. Company: Skali Ltd. Contact: privacy@skaliapp.com.
// Keep in sync with the published versions on skaliapp.com.

const LAST_UPDATED = '24 September 2026'

const DOCS = {
  terms: {
    title: 'Terms of Service',
    icon: FileText,
    body: [
      ['Who we are', 'Skali is operated by Skali Ltd ("Skali", "we", "us"), a company registered in the United Kingdom. By creating an account or using Skali you agree to these Terms.'],
      ['Eligibility', 'You must be at least 13 years old. Under-18 accounts are protected: adult\u2194minor contact, adult content and monetisation are blocked. Your date of birth is set once and cannot be changed. Providing a false age is a serious breach and may result in permanent removal.'],
      ['Your account', 'You are responsible for activity on your account and for keeping your credentials secure. Handles may be changed at most once every 60 days. We may suspend or terminate accounts that breach these Terms or our Content Policy.'],
      ['Acceptable use', 'You may not post illegal content, harass or threaten others, impersonate people, distribute spam, or attempt to bypass safety systems. Child sexual abuse material (CSAM) results in immediate termination without appeal and is reported to the relevant authorities.'],
      ['Content you post', 'You keep ownership of what you post. You grant Skali a licence to host and display it so the service can work. You are responsible for having the rights to what you share.'],
      ['Payments', 'All purchases (subscriptions, tips, shop items) are made on skaliapp.com. Skali is the Merchant of Record. Pricing, taxes and creator payouts are described at checkout. The mobile app may display your entitlements but does not sell digital goods in-app.'],
      ['Moderation & enforcement', 'We operate a strike and report system. Access to private data for lawful moderation or legal requests is strictly limited, requires a documented basis, and is recorded in an immutable audit log. We are not an end-to-end encrypted service.'],
      ['Termination & appeals', 'You can delete your account at any time from Settings. Enforcement decisions may be appealed within 12 months, except zero-tolerance terminations.'],
      ['Liability', 'Skali is provided "as is". To the extent permitted by law we are not liable for indirect or consequential loss. Nothing limits liability that cannot be limited by law.'],
      ['Changes & contact', 'We may update these Terms and will note the date above. Questions: legal@skaliapp.com.'],
    ],
  },
  privacy: {
    title: 'Privacy Policy',
    icon: Shield,
    body: [
      ['Controller', 'Skali Ltd is the data controller. We are registered with the UK Information Commissioner\u2019s Office (ICO). Contact our data team at privacy@skaliapp.com.'],
      ['What we collect', 'Account details (email, display name, date of birth/age band, handle), content you create, relationships (follows, inner circle), device/push tokens, and limited technical logs. We store your age-verification status \u2014 never your identity documents.'],
      ['How we use it', 'To run the service, keep the community safe, process payments (via our payment partners), and meet legal obligations. We do not sell your personal data.'],
      ['Direct messages', 'DMs are encrypted at rest (AES-256-GCM). Skali holds the key and can decrypt messages only for lawful moderation or a valid legal request. Every such access is logged. Skali is not marketed as end-to-end encrypted.'],
      ['Age & identity verification', 'Identity and age checks are performed by third-party providers (e.g. Yoti, OneID). We receive only a pass/fail status and store that status \u2014 we do not retain the underlying documents.'],
      ['Sharing', 'We share data with processors who host and secure the platform (e.g. cloud storage, payment PSPs, verification providers) under contract, and with authorities where legally required.'],
      ['Your rights', 'You may access, correct, export or delete your data, and object to certain processing. Delete your account any time from Settings. To exercise rights contact privacy@skaliapp.com; you may also complain to the ICO.'],
      ['Retention', 'We keep data while your account is active and for as long as needed for legal, safety and accounting purposes, then delete or anonymise it.'],
      ['International transfers', 'Where data is processed outside the UK/EEA we use appropriate safeguards (e.g. UK/EU standard contractual clauses).'],
    ],
  },
  content: {
    title: 'Content & Community Policy',
    icon: Users,
    body: [
      ['Our approach', 'Skali is a responsible adult social network. You control who sees what across Public, Followers and Inner Circle tiers. These rules keep the community safe.'],
      ['Zero tolerance', 'Child sexual abuse material, content sexualising minors, and credible threats of violence are removed immediately, the account is terminated without appeal, and the matter is reported to the authorities.'],
      ['Prohibited content', 'No harassment, hate speech or slurs, incitement to violence, doxxing, non-consensual intimate imagery, or illegal goods. Hateful terms are blocked; repeated attempts are logged and may lead to review.'],
      ['Adult (NSFW) content', 'Adult content is permitted only for verified adults who have turned on the NSFW Comfort Zone. It must be correctly labelled using Skali\u2019s NSFW categories. It is never shown to minors or to users who have not opted in, and never appears in sponsored placements by default.'],
      ['AI content', 'Media that is AI-generated, AI-assisted or AI-altered must be labelled. Unlabelled AI content can be reported.'],
      ['Reporting & enforcement', 'Anyone can report content or accounts. Upheld reports follow a graduated ladder \u2014 reminder, safety flag, temporary suspensions, and ultimately a ban for repeat or severe breaches.'],
      ['Appeals', 'Most enforcement can be appealed within 12 months. Zero-tolerance terminations cannot be appealed.'],
    ],
  },
  cookies: {
    title: 'Cookie Policy',
    icon: Cookie,
    body: [
      ['Essential storage only', 'Skali uses only the local storage and cookies needed to sign you in and remember your preferences (such as your session token and theme). We do not use advertising or cross-site tracking cookies.'],
      ['Session & preferences', 'A session token keeps you signed in on this device. Display preferences (theme, accent, text size) are stored locally so the app looks the way you left it.'],
      ['Analytics', 'If we introduce privacy-respecting, aggregate analytics in future, we will update this policy and, where required, ask for your consent first.'],
      ['Managing storage', 'You can clear this data by signing out or clearing your browser/app storage. Doing so will sign you out.'],
      ['Contact', 'Questions about cookies: privacy@skaliapp.com.'],
    ],
  },
} as const

type DocKey = keyof typeof DOCS
const ORDER: DocKey[] = ['terms', 'privacy', 'content', 'cookies']

export default function Legal() {
  const { doc } = useParams<{ doc?: string }>()
  const nav = useNavigate()
  const active: DocKey = (doc && (doc in DOCS) ? doc : 'terms') as DocKey
  const current = DOCS[active]

  return (
    <div className="min-h-full bg-ink text-slate-200" data-testid="legal-page">
      <div className="max-w-2xl mx-auto px-4 py-6">
        <button data-testid="legal-back-button" onClick={() => nav(-1)}
          className="flex items-center gap-2 text-sm text-slate-400 hover:text-slate-200 transition mb-5">
          <ArrowLeft className="h-4 w-4" /> Back
        </button>

        <h1 className="text-2xl font-bold mb-1">Skali Legal</h1>
        <p className="text-xs text-slate-500 mb-5">Skali Ltd &middot; Last updated {LAST_UPDATED}</p>

        <div className="flex gap-2 overflow-x-auto pb-2 mb-6" data-testid="legal-tabs">
          {ORDER.map(k => {
            const D = DOCS[k]
            const Icon = D.icon
            const on = k === active
            return (
              <Link key={k} to={`/legal/${k}`} data-testid={`legal-tab-${k}`}
                className={`flex-shrink-0 flex items-center gap-2 rounded-full px-4 py-2 text-sm border transition ${on ? 'bg-brand text-white border-brand' : 'bg-panel text-slate-300 border-edge hover:border-slate-500'}`}>
                <Icon className="h-4 w-4" /> {D.title}
              </Link>
            )
          })}
        </div>

        <div className="bg-panel border border-edge rounded-2xl p-5" data-testid="legal-content">
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <current.icon className="h-5 w-5 text-brand" /> {current.title}
          </h2>
          <div className="space-y-5">
            {current.body.map(([heading, text]) => (
              <section key={heading}>
                <h3 className="font-semibold text-slate-200 mb-1">{heading}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{text}</p>
              </section>
            ))}
          </div>
        </div>

        <p className="text-[11px] text-slate-600 mt-6 text-center">
          These in-app summaries reflect the full policies published at skaliapp.com.
        </p>
      </div>
    </div>
  )
}
