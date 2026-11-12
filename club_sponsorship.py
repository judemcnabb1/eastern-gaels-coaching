"""Eastern Gaels sponsorship ledger; all values stored in the dashboard SQLite database."""
import sqlite3, html
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs

def setup(c):
    c.execute("""CREATE TABLE IF NOT EXISTS club_sponsors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Potential',
        contact TEXT DEFAULT '', purpose_type TEXT NOT NULL DEFAULT 'General Club Finances',
        purpose_name TEXT DEFAULT '', pledged_cents INTEGER NOT NULL DEFAULT 0,
        notes TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS club_sponsor_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sponsor_id INTEGER NOT NULL, amount_cents INTEGER NOT NULL,
        paid_on TEXT NOT NULL, note TEXT DEFAULT '',
        FOREIGN KEY(sponsor_id) REFERENCES club_sponsors(id))""")
    c.commit()

def esc(v): return html.escape(str(v if v is not None else ''),quote=True)
def euro(cents): return '€'+format(cents/100,',.2f')
def cents(v):
    try:
        n=Decimal(str(v).strip())
        if not n.is_finite() or n<0 or n.as_tuple().exponent < -2: raise ValueError()
        x=int(n*100)
        if x>10**12:raise ValueError()
        return x
    except (InvalidOperation,ValueError):raise ValueError('Enter a valid non-negative euro amount (maximum two decimal places).')

def render(c,admin=False):
    setup(c)
    sponsors=c.execute("""SELECT s.*,COALESCE(SUM(p.amount_cents),0) received
      FROM club_sponsors s LEFT JOIN club_sponsor_payments p ON p.sponsor_id=s.id
      GROUP BY s.id ORDER BY CASE s.status WHEN 'Actual' THEN 0 ELSE 1 END,s.name""").fetchall()
    actual=[x for x in sponsors if x['status']=='Actual']
    potential=[x for x in sponsors if x['status']=='Potential']
    pledged=sum(x['pledged_cents'] for x in actual)
    received=sum(x['received'] for x in actual)
    outstanding=sum(max(0,x['pledged_cents']-x['received']) for x in actual)
    b=f"""<div class="hero"><div><div class="eyebrow">Club partnerships</div><h2>Club Sponsorship</h2><p>Track prospective and confirmed sponsors, funding allocations and payments.</p></div></div>
    <div class="grid"><div class="card kpi"><div class="stat">{len(potential)}</div><b>Potential sponsors</b></div>
    <div class="card kpi"><div class="stat">{len(actual)}</div><b>Actual sponsors</b></div>
    <div class="card kpi"><div class="stat">{euro(pledged)}</div><b>Confirmed sponsorship</b></div>
    <div class="card kpi"><div class="stat">{euro(received)}</div><b>Payments received</b></div>
    <div class="card kpi"><div class="stat">{euro(outstanding)}</div><b>Outstanding balances</b></div></div>
    <div class="card"><h3>Sponsorship register</h3><div class="tw"><table><thead><tr><th>Sponsor</th><th>Status</th><th>Contact</th><th>Allocated to</th><th>Amount</th><th>Received</th><th>Outstanding</th><th>Notes</th></tr></thead><tbody>"""
    for x in sponsors:
        allocation=x['purpose_type']+((': '+x['purpose_name']) if x['purpose_name'] else '')
        b+=f"<tr><td>{esc(x['name'])}</td><td>{esc(x['status'])}</td><td>{esc(x['contact'])}</td><td>{esc(allocation)}</td><td>{euro(x['pledged_cents'])}</td><td>{euro(x['received'])}</td><td>{euro(max(0,x['pledged_cents']-x['received']))}</td><td>{esc(x['notes'])}</td></tr>"
    if not sponsors:b+='<tr><td colspan="8">No sponsors entered yet.</td></tr>'
    b+='</tbody></table></div></div>'
    if admin:
        b+='''<div class="card"><h3>Add potential or actual sponsor</h3><form action="/club-sponsorship/save" method="post"><div class="grid">
        <label>Sponsor name<input name="name" required maxlength="180"></label>
        <label>Status<select name="status"><option>Potential</option><option>Actual</option></select></label>
        <label>Contact details<input name="contact" maxlength="250"></label>
        <label>Allocation<select name="purpose_type"><option>General Club Finances</option><option>Club Team</option><option>Club Project</option></select></label>
        <label>Team or project name<input name="purpose_name" maxlength="180" placeholder="Leave blank for general finances"></label>
        <label>Sponsorship amount (€)<input type="number" name="amount" min="0" step="0.01" value="0.00" required></label>
        <label>Notes<input name="notes" maxlength="1000"></label></div><div class="actions"><button type="submit">Save sponsor</button></div></form></div>'''
        if sponsors:
            b+='''<div class="card"><h3>Record payment received</h3><form action="/club-sponsorship/payment" method="post"><div class="grid"><label>Sponsor<select name="sponsor_id">'''
            for x in actual:b+=f'<option value="{x["id"]}">{esc(x["name"])}</option>'
            b+='''</select></label><label>Amount received (€)<input type="number" name="amount" min="0.01" step="0.01" required></label><label>Date received<input type="date" name="paid_on" required></label><label>Reference or note<input name="note" maxlength="300"></label></div><div class="actions"><button type="submit">Record payment</button></div></form></div>'''
            if not actual:b+='<p class="muted">Mark a sponsor as Actual before recording payments.</p>'
        b+='''<div class="card"><h3>Update sponsor details</h3><form action="/club-sponsorship/update" method="post"><div class="grid"><label>Sponsor<select name="sponsor_id">'''
        for x in sponsors:b+=f'<option value="{x["id"]}">{esc(x["name"])}</option>'
        b+='''</select></label><label>Status<select name="status"><option>Potential</option><option>Actual</option></select></label><label>Allocation<select name="purpose_type"><option>General Club Finances</option><option>Club Team</option><option>Club Project</option></select></label><label>Team or project name<input name="purpose_name" maxlength="180"></label><label>Revised sponsorship amount (€)<input name="amount" type="number" min="0" step="0.01" required></label></div><p class="muted">This updates the selected sponsor's status, allocation and committed amount; it does not change payment history.</p><div class="actions"><button type="submit">Update sponsor</button></div></form></div>'''
    return b

def save(c,path,body):
    setup(c)
    v=parse_qs(body.decode('utf-8'),keep_blank_values=True)
    def get(k):return (v.get(k,[''])[0] or '').strip()
    if path.endswith('/save'):
        name=get('name')
        if not name or len(name)>180:raise ValueError('Sponsor name is required.')
        status=get('status');kind=get('purpose_type')
        if status not in ('Potential','Actual') or kind not in ('General Club Finances','Club Team','Club Project'):raise ValueError('Invalid sponsorship category.')
        if kind!='General Club Finances' and not get('purpose_name'):raise ValueError('Enter a team or project name.')
        c.execute('INSERT INTO club_sponsors(name,status,contact,purpose_type,purpose_name,pledged_cents,notes) VALUES(?,?,?,?,?,?,?)',(name,status,get('contact')[:250],kind,get('purpose_name')[:180] if kind!='General Club Finances' else '',cents(get('amount')),get('notes')[:1000]))
    else:
        try:sid=int(get('sponsor_id'))
        except ValueError:raise ValueError('Select a sponsor.')
        row=c.execute('SELECT * FROM club_sponsors WHERE id=?',(sid,)).fetchone()
        if not row:raise ValueError('Sponsor not found.')
        if path.endswith('/payment'):
            if row['status']!='Actual':raise ValueError('Payments can only be recorded for actual sponsors.')
            amount=cents(get('amount'))
            if not amount:raise ValueError('Payment amount must be greater than zero.')
            import datetime
            try:datetime.date.fromisoformat(get('paid_on'))
            except ValueError:raise ValueError('Enter a valid payment date.')
            c.execute('INSERT INTO club_sponsor_payments(sponsor_id,amount_cents,paid_on,note) VALUES(?,?,?,?)',(sid,amount,get('paid_on'),get('note')[:300]))
        else:
            status=get('status');kind=get('purpose_type')
            if status not in ('Potential','Actual') or kind not in ('General Club Finances','Club Team','Club Project'):raise ValueError('Invalid sponsorship category.')
            if kind!='General Club Finances' and not get('purpose_name'):raise ValueError('Enter a team or project name.')
            c.execute('UPDATE club_sponsors SET status=?,purpose_type=?,purpose_name=?,pledged_cents=? WHERE id=?',(status,kind,get('purpose_name')[:180] if kind!='General Club Finances' else '',cents(get('amount')),sid))
    c.commit()
