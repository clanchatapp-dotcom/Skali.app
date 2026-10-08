"""Creator Analytics (Creator Studio > Analytics) — isolated, additive module.

Real data wherever the app already tracks it; anything not tracked yet is returned as
clearly-flagged SAMPLE data (`sample: [field, ...]`) so the UI can tag it.
"""
import io
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel

srv = None
SAMPLE_SKALI_FEE_RATE = 0.10  # placeholder platform cut, tuned later
HEARTBEAT_CAP = 45  # max seconds credited per watch heartbeat (client pings every 30s)


class PromoIn(BaseModel):
    code: str
    percent_off: float
    label: Optional[str] = ''
    max_uses: Optional[int] = None
    expires_on: Optional[str] = None  # YYYY-MM-DD; code switches off at the end of that day (UTC)


class MilestoneIn(BaseModel):
    kind: str
    value: int


def _now():
    return datetime.now(timezone.utc)


def _pct_change(cur: float, prev: float):
    if prev > 0:
        return round(((cur - prev) / prev) * 100, 1)
    return 100.0 if cur > 0 else None


async def _transactions(cid: str):
    return [t async for t in srv.db.transactions.find({'creator_id': cid}, {'_id': 0}).sort('created_at', -1).limit(1000)]


RANGES = {'month', '3m', 'all'}
SAMPLE_SCALE = {'month': 1.0, '3m': 2.9, 'all': 7.4}
COMPARE_LABEL = {'month': 'vs last month', '3m': 'vs previous 3 months', 'all': None}
SUB_MILESTONES = [1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000]
RENEWAL_MILESTONES = [1, 10, 25, 50, 100, 250, 500, 1000]


def _month_back(d, n):
    for _ in range(n):
        d = (d - timedelta(days=1)).replace(day=1)
    return d


def _bounds(rng: str):
    """(start_iso, prev_start_iso) for the selected range; (None, None) = all time."""
    if rng == 'all':
        return None, None
    first = _now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    span = 1 if rng == 'month' else 3
    start = _month_back(first, span - 1)
    return start.isoformat(), _month_back(start, span).isoformat()


def _in(created: str, start) -> bool:
    return start is None or (created or '') >= start


def _months(n: int):
    out, d = [], _now().replace(day=1)
    for _ in range(n):
        out.insert(0, d.strftime('%Y-%m'))
        d = (d - timedelta(days=1)).replace(day=1)
    return out


async def _milestone(cid: str, prof: dict):
    seen = prof.get('analytics_milestones') or {}
    active = await srv.db.subscriptions.count_documents({'creator_id': cid, 'status': 'active'})
    payments, buyers = 0, set()
    async for t in srv.db.transactions.find({'creator_id': cid, 'product': 'inner_circle', 'status': {'$ne': 'chargeback'}},
                                            {'_id': 0, 'buyer_id': 1}):
        payments += 1
        buyers.add(t.get('buyer_id'))
    renewals = max(0, payments - len(buyers))
    for kind, n, steps in [('subscribers', active, SUB_MILESTONES), ('renewals', renewals, RENEWAL_MILESTONES)]:
        reached = max([s for s in steps if n >= s], default=0)
        if reached and reached > int(seen.get(kind, 0) or 0):
            if kind == 'subscribers':
                msg = (f"{reached} {'person has' if reached == 1 else 'people have'} joined your Inner Circle. "
                       "That's real people choosing to be close to what you make. Take a breath and enjoy it.")
            else:
                msg = (f"Your Inner Circle has renewed {reached} {'time' if reached == 1 else 'times'}. "
                       "People keep coming back because what you share matters to them.")
            return {'kind': kind, 'value': reached, 'message': msg}
    return None


async def _overview(cid: str, txns: list, rng: str, prof: dict) -> dict:
    start, prev = _bounds(rng)
    n_months = 12 if rng == 'all' else 6
    base = {'range': rng, 'compare_label': COMPARE_LABEL[rng], 'currency': 'GBP',
            'trend_months': _months(n_months), 'milestone': await _milestone(cid, prof)}
    if not txns:
        k = SAMPLE_SCALE[rng]
        trend = [120, 135, 150, 160, 175, 190, 210, 260, 305, 340, 401.1, 482.4][-n_months:]
        return {**base, 'revenue': round(482.40 * k, 2), 'revenue_prev': round(401.10 * k, 2) if prev else None,
                'revenue_growth_pct': 20.3 if prev else None,
                'new_subs': round(14 * k), 'new_subs_prev': round(11 * k) if prev else None,
                'subs_growth_pct': 27.3 if prev else None,
                'tips': round(96.50 * k, 2), 'tips_prev': round(104.0 * k, 2) if prev else None,
                'tips_growth_pct': -7.2 if prev else None,
                'pending_payout': 212.75, 'trend': trend,
                'sample': ['revenue', 'subs', 'tips', 'pending_payout', 'trend']}
    cur = {'rev': 0.0, 'tips': 0.0, 'subs': 0}
    old = {'rev': 0.0, 'tips': 0.0, 'subs': 0}
    buckets: dict[str, float] = {}
    for t in txns:
        if t.get('status') == 'chargeback':
            continue
        c = float(t.get('creator_net', 0) or 0)
        created = t.get('created_at', '')
        buckets[created[:7]] = buckets.get(created[:7], 0.0) + c
        if _in(created, start):
            bucket = cur
        elif prev and prev <= created < start:
            bucket = old
        else:
            continue
        bucket['rev'] += c
        if t.get('product') == 'tip':
            bucket['tips'] += c
        if t.get('product') == 'inner_circle':
            bucket['subs'] += 1
    growth = _pct_change if prev else (lambda a, b: None)
    bal = await srv._payout_doc(cid)
    return {**base, 'revenue': round(cur['rev'], 2), 'revenue_prev': round(old['rev'], 2) if prev else None,
            'revenue_growth_pct': growth(cur['rev'], old['rev']),
            'new_subs': cur['subs'], 'new_subs_prev': old['subs'] if prev else None,
            'subs_growth_pct': growth(cur['subs'], old['subs']),
            'tips': round(cur['tips'], 2), 'tips_prev': round(old['tips'], 2) if prev else None,
            'tips_growth_pct': growth(cur['tips'], old['tips']),
            'pending_payout': round(float(bal.get('pending', 0) or 0), 2),
            'currency': bal.get('currency', 'GBP'),
            'trend': [round(buckets.get(m, 0.0), 2) for m in base['trend_months']],
            'sample': [] if bal else ['pending_payout']}


async def expire_promos(cid: str):
    """Switch off codes whose end date has passed."""
    now = _now().isoformat()
    await srv.db.creator_promos.update_many({'creator_id': cid, 'active': True, 'expires_at': {'$ne': None, '$lt': now}},
                                            {'$set': {'active': False, 'ended_at': now, 'ended_reason': 'expired'}})


async def _promos(cid: str):
    await expire_promos(cid)
    active, ended = [], []
    async for p in srv.db.creator_promos.find({'creator_id': cid}, {'_id': 0}).sort('created_at', -1).limit(50):
        (active if p.get('active') else ended).append(p)
    return active, ended[:10]


async def _subscribers(cid: str, rng: str) -> dict:
    start, _ = _bounds(rng)
    active_promos, ended_promos = await _promos(cid)
    subs = [s async for s in srv.db.subscriptions.find({'creator_id': cid}, {'_id': 0}).sort('updated_at', -1)]
    if not subs:
        base, k = _now(), SAMPLE_SCALE[rng]
        churn = round(3 * k)
        return {'range': rng, 'active': 38, 'churn': churn, 'churn_rate': round(churn / (38 + churn) * 100, 1),
                'renewals': [{'name': n, 'handle': h, 'renews_at': (base + timedelta(days=dd)).isoformat(), 'price': p}
                             for n, h, dd, p in [('Maya R.', 'maya', 2, 15.0), ('Jon B.', 'jonb', 5, 15.0),
                                                 ('Aisha K.', 'aishak', 9, 30.0), ('Leo T.', 'leot', 13, 15.0)]],
                'promos': active_promos, 'ended_promos': ended_promos,
                'sample': ['active', 'churn', 'renewals']}
    active = [s for s in subs if s.get('status') == 'active']
    churned = [s for s in subs if s.get('status') == 'canceled' and _in(s.get('updated_at', ''), start)]
    renewals = []
    for s in active[:20]:
        ent = await srv.db.entitlements.find_one({'user_id': s['buyer_id'], 'creator_id': cid, 'type': 'inner_circle'}, {'_id': 0})
        buyer = await srv.db.profiles.find_one({'id': s['buyer_id']}, {'_id': 0, 'handle': 1, 'display_name': 1})
        renewals.append({'name': (buyer or {}).get('display_name', 'Unknown'), 'handle': (buyer or {}).get('handle', ''),
                         'renews_at': (ent or {}).get('period_end'), 'price': s.get('price')})
    renewals.sort(key=lambda r: r.get('renews_at') or '9999')
    total = len(active) + len(churned)
    return {'range': rng, 'active': len(active), 'churn': len(churned),
            'churn_rate': round(len(churned) / total * 100, 1) if total else 0.0,
            'renewals': renewals, 'promos': active_promos, 'ended_promos': ended_promos, 'sample': []}


async def _shop(cid: str, rng: str) -> dict:
    start, _ = _bounds(rng)
    products = [p async for p in srv.db.shop_products.find({'creator_id': cid, 'active': True}, {'_id': 0})]
    sample = []
    if not await srv.db.shop_orders.count_documents({'creator_id': cid}):
        sample.append('orders')
        base = _now()
        orders = [{'id': f'sample-{i}', 'title': t, 'kind': k, 'gross': g, 'fulfilment_status': f,
                   'created_at': (base - timedelta(days=i * 2)).isoformat()}
                  for i, (t, k, g, f) in enumerate([('Skali Hoodie', 'physical', 42.0, 'in_production'),
                                                     ('Wallpaper Pack', 'digital', 4.99, 'delivered'),
                                                     ('Logo Tee', 'physical', 24.0, 'shipped'),
                                                     ('Preset Bundle', 'digital', 9.99, 'delivered')])]
    else:
        q = {'creator_id': cid, **({'created_at': {'$gte': start}} if start else {})}
        orders = [o async for o in srv.db.shop_orders.find(q, {'_id': 0}).sort('created_at', -1).limit(100)]
    downloads = [o for o in orders if o.get('kind') == 'digital']
    stock_cycle = ['in_stock', 'low', 'in_stock', 'out']
    inventory = [{'title': p['title'], 'kind': p['kind'],
                  'status': 'in_stock' if p['kind'] == 'digital' else stock_cycle[i % 4]}
                 for i, p in enumerate(products)]
    if not inventory:
        inventory = [{'title': 'Skali Hoodie', 'kind': 'physical', 'status': 'low'},
                     {'title': 'Logo Tee', 'kind': 'physical', 'status': 'in_stock'},
                     {'title': 'Sticker Sheet', 'kind': 'physical', 'status': 'out'},
                     {'title': 'Wallpaper Pack', 'kind': 'digital', 'status': 'in_stock'}]
    sample.append('inventory')  # Printful stock sync not connected yet
    return {'range': rng, 'orders_count': len(orders), 'orders': orders,
            'downloads_count': len(downloads), 'downloads': downloads[:20],
            'inventory': inventory, 'sample': sample}


async def _finance(cid: str, txns: list, rng: str = 'all') -> dict:
    start, _ = _bounds(rng)
    sample = ['fee_rate']
    if await srv.db.payouts.count_documents({'creator_id': cid}):
        q = {'creator_id': cid, **({'created_at': {'$gte': start}} if start else {})}
        payouts = [p async for p in srv.db.payouts.find(q, {'_id': 0}).sort('created_at', -1).limit(50)]
    else:
        sample.append('payouts')
        base = _now()
        amounts = [388.20, 341.75, 296.40, 270.10, 244.90, 210.00]
        payouts = [{'id': f'sample-{i}', 'amount': a, 'status': 'paid', 'currency': 'GBP',
                    'created_at': (base - timedelta(days=28 * i + 3)).isoformat()}
                   for i, a in enumerate(amounts)]
        payouts = [p for p in payouts if _in(p['created_at'], start)]
    totals = {'gross': 0.0, 'vat': 0.0, 'psp_fee': 0.0, 'skali_fee': 0.0, 'creator_net': 0.0}
    by_month: dict[str, dict] = {}
    for t in txns:
        if t.get('status') == 'chargeback' or not _in(t.get('created_at', ''), start):
            continue
        m = (t.get('created_at') or '')[:7]
        md = by_month.setdefault(m, {'month': m, **{k: 0.0 for k in totals}})
        for k in totals:
            v = float(t.get(k, 0) or 0)
            totals[k] = round(totals[k] + v, 2)
            md[k] = round(md[k] + v, 2)
    if not txns:
        sample.append('fees')
        n = {'month': 1, '3m': 3, 'all': 6}[rng]
        by_month, d = {}, _now().replace(day=1)
        for g in [482.4, 401.1, 366.5, 340.0, 305.0, 260.0][:n]:
            m = d.strftime('%Y-%m')
            d = (d - timedelta(days=1)).replace(day=1)
            by_month[m] = {'month': m, 'gross': g, 'vat': round(g / 6, 2), 'psp_fee': round(g * 0.029, 2),
                           'skali_fee': round(g / 1.2 * SAMPLE_SKALI_FEE_RATE, 2), 'creator_net': round(g * 0.72, 2)}
        totals = {k: round(sum(x[k] for x in by_month.values()), 2) for k in totals}
    tax_docs = sorted(by_month.values(), key=lambda x: x['month'], reverse=True)
    for d in tax_docs:
        d['title'] = f"Earnings summary {d['month']}"
    return {'range': rng, 'payouts': payouts, 'fees': totals, 'fee_rate': SAMPLE_SKALI_FEE_RATE,
            'tax_docs': tax_docs, 'sample': sample}


async def _is_inner(host_id: str, viewer_id: str) -> bool:
    if await srv.db.subscriptions.find_one({'creator_id': host_id, 'buyer_id': viewer_id, 'status': 'active'}):
        return True
    return bool(await srv.db.inner.find_one({'owner_id': host_id, 'member_id': viewer_id, 'status': 'accepted'}))


async def _avg_watch(cid: str, start):
    q = {'host_id': cid, 'is_inner': True, **({'started_at': {'$gte': start}} if start else {})}
    total, n = 0.0, 0
    async for w in srv.db.watch_sessions.find(q, {'_id': 0, 'seconds': 1}):
        total += float(w.get('seconds', 0) or 0)
        n += 1
    return (round(total / n / 60, 1) if n else None), n


async def _health(cid: str, prof: dict, rng: str = 'month') -> dict:
    settings = srv._health_settings(prof)
    if settings['hidden']:
        return {'range': rng, 'settings': settings, 'metrics': None, 'sample': []}
    start, _ = _bounds(rng)
    since = {'$gte': start} if start else {'$exists': True}
    avg_watch, watch_sessions = await _avg_watch(cid, start)
    active = await srv.db.subscriptions.count_documents({'creator_id': cid, 'status': 'active'})
    churned = await srv.db.subscriptions.count_documents({'creator_id': cid, 'status': 'canceled', 'updated_at': since})
    if not (active + churned):
        k = SAMPLE_SCALE[rng]
        return {'range': rng, 'settings': settings,
                'sample': ['returning_subscribers', 'renewal_rate', 'retention', 'inner_circle_messages'],
                'metrics': {'returning_subscribers': 24, 'renewal_rate': 86.4, 'retention': 91.2,
                            'avg_watch_time': avg_watch, 'watch_sessions': watch_sessions,
                            'inner_circle_messages': round(132 * k)}}
    counts: dict[str, int] = {}
    async for t in srv.db.transactions.find({'creator_id': cid, 'product': 'inner_circle', 'status': {'$ne': 'chargeback'}}, {'_id': 0, 'buyer_id': 1}):
        if t.get('buyer_id'):
            counts[t['buyer_id']] = counts.get(t['buyer_id'], 0) + 1
    renewals = await srv.db.transactions.count_documents({'creator_id': cid, 'product': 'inner_circle', 'status': {'$ne': 'chargeback'}, 'created_at': since})
    sub_ids = [s['buyer_id'] async for s in srv.db.subscriptions.find({'creator_id': cid, 'status': 'active'}, {'_id': 0, 'buyer_id': 1}) if s.get('buyer_id')]
    ic = await srv.db.dms.count_documents({'participants': cid, 'sender_id': {'$in': sub_ids}, 'created_at': since}) if sub_ids else 0
    return {'range': rng, 'settings': settings, 'sample': [], 'metrics': {
        'returning_subscribers': sum(1 for n in counts.values() if n >= 2),
        'renewal_rate': round(min(renewals / active, 1) * 100, 1) if active else 0.0,
        'retention': round(active / (active + churned) * 100, 1),
        'avg_watch_time': avg_watch, 'watch_sessions': watch_sessions,
        'inner_circle_messages': ic}}


async def _finance_rows(u: dict, rng: str = 'all'):
    txns = await _transactions(u['id'])
    fin = await _finance(u['id'], txns, rng)
    start, _ = _bounds(rng)
    return [t for t in txns if _in(t.get('created_at', ''), start)], fin


def build_router() -> APIRouter:
    async def _require_creator_account(u: dict = Depends(srv.get_current_user)):
        if not (u.get('is_creator') or u.get('creator_override') or srv.monetisation_ok(u)):
            raise srv.HTTPException(403, 'Turn on your creator account first.')
        return u

    r = APIRouter(prefix='/api/creator/analytics')

    @r.get('')
    async def analytics(range: str = 'month', u: dict = Depends(_require_creator_account)):
        rng = range if range in RANGES else 'month'
        prof = await srv.db.profiles.find_one({'id': u['id']}, {'_id': 0}) or {}
        txns = await _transactions(u['id'])
        return {'range': rng, 'overview': await _overview(u['id'], txns, rng, prof),
                'subscribers': await _subscribers(u['id'], rng), 'shop': await _shop(u['id'], rng),
                'finance': await _finance(u['id'], txns, rng), 'health': await _health(u['id'], prof, rng)}

    @r.get('/promos')
    async def list_promos(u: dict = Depends(_require_creator_account)):
        active, ended = await _promos(u['id'])
        return {'promos': active, 'ended_promos': ended}

    @r.post('/promos')
    async def create_promo(body: PromoIn, u: dict = Depends(_require_creator_account)):
        code = (body.code or '').strip().upper()
        if not re.fullmatch(r'[A-Z0-9]{3,20}', code):
            raise srv.HTTPException(400, 'Code must be 3-20 letters or numbers')
        pct = float(body.percent_off or 0)
        if not 5 <= pct <= 90:
            raise srv.HTTPException(400, 'Discount must be between 5% and 90%')
        if body.max_uses is not None and body.max_uses < 1:
            raise srv.HTTPException(400, 'Max uses must be at least 1')
        expires_at = None
        if (body.expires_on or '').strip():
            try:
                day = datetime.strptime(body.expires_on.strip()[:10], '%Y-%m-%d').replace(tzinfo=timezone.utc)
            except ValueError:
                raise srv.HTTPException(400, 'End date must be a valid date')
            if day.date() < _now().date():
                raise srv.HTTPException(400, 'End date must be today or later')
            expires_at = (day + timedelta(days=1) - timedelta(seconds=1)).isoformat()
        if await srv.db.creator_promos.find_one({'creator_id': u['id'], 'code': code, 'active': True}):
            raise srv.HTTPException(400, 'You already have an active code with that name')
        doc = {'id': str(uuid.uuid4()), 'creator_id': u['id'], 'code': code, 'percent_off': round(pct, 1),
               'label': (body.label or '').strip()[:80] or f'{round(pct)}% off Inner Circle',
               'max_uses': body.max_uses, 'expires_at': expires_at, 'uses': 0, 'active': True,
               'created_at': _now().isoformat()}
        await srv.db.creator_promos.insert_one(dict(doc))
        return doc

    @r.post('/promos/{promo_id}/end')
    async def end_promo(promo_id: str, u: dict = Depends(_require_creator_account)):
        res = await srv.db.creator_promos.update_one({'id': promo_id, 'creator_id': u['id'], 'active': True},
                                                     {'$set': {'active': False, 'ended_at': _now().isoformat()}})
        if not res.matched_count:
            raise srv.HTTPException(404, 'Promo not found or already ended')
        return {'ok': True}

    @r.post('/milestones/dismiss')
    async def dismiss_milestone(body: MilestoneIn, u: dict = Depends(_require_creator_account)):
        if body.kind not in ('subscribers', 'renewals'):
            raise srv.HTTPException(400, 'Unknown milestone')
        await srv.db.profiles.update_one({'id': u['id']}, {'$max': {f'analytics_milestones.{body.kind}': int(body.value)}})
        return {'ok': True}

    @r.get('/export.csv')
    async def export_csv(range: str = 'all', u: dict = Depends(_require_creator_account)):
        txns, fin = await _finance_rows(u, range if range in RANGES else 'all')
        is_sample = 'fees' in fin['sample']
        rows = ['section,date_or_month,label,gross,vat,psp_fee,skali_fee,creator_net,status,sample']
        for t in txns:
            rows.append(','.join(str(x) for x in ['transaction', t.get('created_at', ''), t.get('product', ''), t.get('gross', 0),
                                                  t.get('vat', 0), t.get('psp_fee', 0), t.get('skali_fee', 0), t.get('creator_net', 0), t.get('status', ''), 'no']))
        for d in fin['tax_docs']:
            rows.append(','.join(str(x) for x in ['monthly_summary', d['month'], d['title'], d['gross'], d['vat'], d['psp_fee'],
                                                  d['skali_fee'], d['creator_net'], '', 'yes' if is_sample else 'no']))
        for p in fin['payouts']:
            rows.append(','.join(str(x) for x in ['payout', p.get('created_at', ''), 'payout', p.get('amount', 0), '', '', '', p.get('amount', 0),
                                                  p.get('status', ''), 'yes' if 'payouts' in fin['sample'] else 'no']))
        f = fin['fees']
        rows.append(','.join(str(x) for x in ['totals', '', fin['range'], f['gross'], f['vat'], f['psp_fee'], f['skali_fee'], f['creator_net'], '', 'yes' if is_sample else 'no']))
        return PlainTextResponse('\n'.join(rows), media_type='text/csv',
                                 headers={'Content-Disposition': 'attachment; filename="skali-analytics-finance.csv"'})

    @r.get('/export.pdf')
    async def export_pdf(range: str = 'all', u: dict = Depends(_require_creator_account)):
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas as pdfcanvas
        _, fin = await _finance_rows(u, range if range in RANGES else 'all')
        buf = io.BytesIO()
        c = pdfcanvas.Canvas(buf, pagesize=A4)
        w, h = A4
        y = h - 25 * mm
        c.setFont('Helvetica-Bold', 18); c.drawString(20 * mm, y, 'Skali - Creator finance summary')
        y -= 8 * mm
        c.setFont('Helvetica', 9); c.setFillGray(0.35)
        c.drawString(20 * mm, y, f"@{u.get('handle', '')}  -  {_now().strftime('%Y-%m-%d')}  -  Summary from Skali data, not an official tax form")
        c.setFillGray(0)
        if fin['sample']:
            y -= 6 * mm
            c.setFont('Helvetica-Oblique', 8); c.drawString(20 * mm, y, f"SAMPLE data included for: {', '.join(fin['sample'])}")
        y -= 12 * mm
        c.setFont('Helvetica-Bold', 11); c.drawString(20 * mm, y, 'Skali fee breakdown')
        y -= 7 * mm
        c.setFont('Helvetica', 10)
        for label, key in [('Gross', 'gross'), ('VAT', 'vat'), ('Processing', 'psp_fee'), ('Skali fee', 'skali_fee'), ('Net', 'creator_net')]:
            c.drawString(24 * mm, y, label); c.drawRightString(w - 20 * mm, y, f"GBP {fin['fees'][key]:.2f}"); y -= 6 * mm
        y -= 6 * mm
        c.setFont('Helvetica-Bold', 11); c.drawString(20 * mm, y, 'Monthly summaries (tax documents)')
        y -= 7 * mm
        c.setFont('Helvetica', 9)
        for d in fin['tax_docs']:
            if y < 30 * mm:
                c.showPage(); y = h - 25 * mm; c.setFont('Helvetica', 9)
            c.drawString(24 * mm, y, d['month']); c.drawRightString(130 * mm, y, f"Gross {d['gross']:.2f}")
            c.drawRightString(w - 20 * mm, y, f"Net {d['creator_net']:.2f}"); y -= 5 * mm
        y -= 6 * mm
        c.setFont('Helvetica-Bold', 11); c.drawString(20 * mm, y, 'Payout history')
        y -= 7 * mm
        c.setFont('Helvetica', 9)
        for p in fin['payouts']:
            if y < 20 * mm:
                c.showPage(); y = h - 25 * mm; c.setFont('Helvetica', 9)
            c.drawString(24 * mm, y, (p.get('created_at') or '')[:10]); c.drawString(80 * mm, y, str(p.get('status', '')))
            c.drawRightString(w - 20 * mm, y, f"GBP {float(p.get('amount', 0) or 0):.2f}"); y -= 5 * mm
        c.showPage(); c.save()
        buf.seek(0)
        return StreamingResponse(buf, media_type='application/pdf',
                                 headers={'Content-Disposition': 'attachment; filename="skali-analytics-finance.pdf"'})

    return r


def build_watch_router() -> APIRouter:
    w = APIRouter(prefix='/api/watch')

    @w.post('/{live_id}/heartbeat')
    async def heartbeat(live_id: str, u: dict = Depends(srv.get_current_user)):
        """Viewer ping every ~30s while watching. Watch time counts toward Creator Health
        only for the host's Inner Circle members."""
        s = await srv.db.live_streams.find_one({'id': live_id}, {'_id': 0, 'host_id': 1, 'status': 1})
        if not s or s.get('status') != 'live' or s['host_id'] == u['id']:
            return {'ok': True, 'tracked': False}
        now = _now()
        key = {'live_id': live_id, 'viewer_id': u['id']}
        ws = await srv.db.watch_sessions.find_one(key, {'_id': 0})
        if ws:
            delta = max(0.0, min((now - datetime.fromisoformat(ws['last_seen'])).total_seconds(), HEARTBEAT_CAP))
            await srv.db.watch_sessions.update_one(key, {'$inc': {'seconds': round(delta, 1)}, '$set': {'last_seen': now.isoformat()}})
        else:
            await srv.db.watch_sessions.insert_one({**key, 'id': str(uuid.uuid4()), 'host_id': s['host_id'],
                                                    'is_inner': await _is_inner(s['host_id'], u['id']),
                                                    'started_at': now.isoformat(), 'last_seen': now.isoformat(), 'seconds': 0.0})
        return {'ok': True, 'tracked': True}

    return w


def setup(app, server_module):
    global srv
    srv = server_module
    app.include_router(build_router())
    app.include_router(build_watch_router())
