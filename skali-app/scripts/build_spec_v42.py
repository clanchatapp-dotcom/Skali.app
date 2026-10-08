import io, urllib.request
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                ListFlowable, ListItem, HRFlowable)
from pypdf import PdfReader, PdfWriter

SPEC_URL = "https://customer-assets-wrfwihn1.emergentagent.net/job_auth-consolidation-3/artifacts/regz9k34_CLANCHAT%20PDF%20PRODUCT%20SPECS.pdf"
urllib.request.urlretrieve(SPEC_URL, "/tmp/spec_src.pdf")

BRAND = colors.HexColor('#6d28d9'); INK = colors.HexColor('#0f1117'); MUT = colors.HexColor('#475569')
ss = getSampleStyleSheet()
H1 = ParagraphStyle('H1', parent=ss['Title'], fontName='Helvetica-Bold', fontSize=22, textColor=BRAND, spaceAfter=4, alignment=0)
SUB = ParagraphStyle('SUB', parent=ss['Normal'], fontSize=10, textColor=MUT, spaceAfter=14)
H2 = ParagraphStyle('H2', parent=ss['Heading2'], fontName='Helvetica-Bold', fontSize=14, textColor=INK, spaceBefore=14, spaceAfter=6)
BODY = ParagraphStyle('BODY', parent=ss['Normal'], fontSize=10.5, leading=15, spaceAfter=6)
NOTE = ParagraphStyle('NOTE', parent=ss['Normal'], fontSize=9.5, leading=13, textColor=MUT, spaceBefore=8)

def bullets(items):
    return ListFlowable([ListItem(Paragraph(t, BODY), leftIndent=8) for t in items],
                        bulletType='bullet', bulletColor=BRAND, start='circle', leftIndent=14)

flow = []

# ---- Addendum 1: Creator Support System ----
flow += [Paragraph('Creator Support System', H1),
         Paragraph('Addendum &mdash; Conduct, Upheld Reports &amp; Escalation Ladder', SUB),
         HRFlowable(width='100%', thickness=1, color=BRAND, spaceAfter=12),
         Paragraph('Progressive enforcement based on <b>upheld reports</b> (reports confirmed as violations by moderation). Escalation is cumulative across the lifetime of an account.', BODY),
         Paragraph('Escalation Ladder', H2)]
rows = [['Upheld reports', 'Action taken'],
        ['1', 'Automated reminder: &ldquo;Please be mindful of your conduct. Continued violations may result in restrictions.&rdquo;'],
        ['3', 'Internal &ldquo;Creator Safety&rdquo; flag. Creators see: &ldquo;This account has a history of upheld harassment or abusive behaviour. Please exercise caution.&rdquo;'],
        ['5', '7-day suspension + mandatory re-acceptance of the rules, with a warning of harsher punishments.'],
        ['7', '30-day suspension + final warning.'],
        ['10', 'Permanent ban.']]
data = [[Paragraph(f'<b>{r[0]}</b>', ParagraphStyle('c', parent=BODY, textColor=(colors.white if i==0 else INK), alignment=1)),
         Paragraph(r[1], ParagraphStyle('d', parent=BODY, textColor=(colors.white if i==0 else INK)))] for i,r in enumerate(rows)]
t = Table(data, colWidths=[30*mm,135*mm]); t.setStyle(TableStyle([
    ('BACKGROUND',(0,0),(-1,0),BRAND),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#f5f3ff'),colors.white]),
    ('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#c4b5fd')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
    ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
flow += [t,
         Paragraph('Rehabilitation &amp; Appeals', H2),
         bullets(['<b>12 months of good behaviour</b> (no new upheld reports) entitles an account to appeal to have strikes removed, resetting their standing.']),
         Paragraph('Zero-Tolerance (Automatic Termination, No Appeal)', H2),
         Paragraph('Upheld reports involving <b>threats, violence, or recurring targeted harassment</b> (and comparable severe conduct) result in <b>automatic account termination with no ability to appeal</b>, bypassing the ladder.', BODY)]

# ---- Addendum 2: Revised Monetisation (supersedes p.13) ----
from reportlab.platypus import PageBreak
flow += [PageBreak(),
         Paragraph('Revised Monetisation &amp; Payment Structure', H1),
         Paragraph('Addendum v4.2 &mdash; SUPERSEDES the revenue-split table on p.13', SUB),
         HRFlowable(width='100%', thickness=1, color=BRAND, spaceAfter=12),
         Paragraph('The revenue split has been updated. Merchandise is now 10%. Super Comments and Digital Downloads have been <b>removed</b> as revenue streams. All other rates unchanged.', BODY)]
mrows = [['Revenue stream', 'ClanChat cut', 'Creator keeps'],
         ['ClanChat Premium (platform sub)', '100%', '\u2014'],
         ['Paid Inner Circle subscriptions (Tier 3)', '10%', '90%'],
         ['Tips from followers', '7.5%', '92.5%'],
         ['Live stream tips', '7.5%', '92.5%'],
         ['Merchandise \u2014 native store (Printful)', '10%', '90%']]
md = [[Paragraph(f'<b>{c}</b>' if i==0 else c, ParagraphStyle('m', parent=BODY, textColor=(colors.white if i==0 else INK), alignment=(0 if j==0 else 1))) for j,c in enumerate(r)] for i,r in enumerate(mrows)]
mt = Table(md, colWidths=[95*mm,35*mm,35*mm]); mt.setStyle(TableStyle([
    ('BACKGROUND',(0,0),(-1,0),BRAND),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#f5f3ff'),colors.white]),
    ('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#c4b5fd')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),
    ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
flow += [mt,
         Paragraph('Removed revenue streams', H2),
         bullets(['<b>Super Comments (live)</b> — removed.', '<b>Digital Downloads</b> — removed.']),
         Paragraph('Unchanged', H2),
         bullets(['Payment rails: Stripe (UK/EU/US/AU/RoW), Xsolla (gaming/microtransactions), \u042emoney (Russia/CIS).',
                  'Payouts scheduled per creator in local currency, with full payout history and zero hidden fees.',
                  'ClanChat Premium remains a platform subscription (\u00a33\u2013\u00a35/mo TBC) with 100% to ClanChat, no creator involved.']),
         Paragraph('Creator pitch: keep 90\u201392.5% of everything earned.', NOTE)]

buf = io.BytesIO()
SimpleDocTemplate(buf, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm, topMargin=18*mm, bottomMargin=18*mm).build(flow)
buf.seek(0)

w = PdfWriter()
for p in PdfReader("/tmp/spec_src.pdf").pages: w.add_page(p)
for p in PdfReader(buf).pages: w.add_page(p)
out = "/app/public/ClanChat_Product_Spec_v4.2.pdf"
with open(out, 'wb') as f: w.write(f)
print("wrote", out, len(PdfReader(out).pages), "pages")
