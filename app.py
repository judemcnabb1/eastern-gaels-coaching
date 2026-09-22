#!/usr/bin/env python3
import os,re,json,sqlite3,secrets,hashlib,hmac,csv,io,html
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
from http.cookies import SimpleCookie
from datetime import date,datetime
BASE=os.path.dirname(os.path.abspath(__file__))
DATA_DIR=os.environ.get('DATA_DIR',BASE)
os.makedirs(DATA_DIR,exist_ok=True)
DB=os.environ.get('DATABASE_PATH',os.path.join(DATA_DIR,'eastern_gaels.db'))
SESS={}
def dbc(): c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def hp(p,s=None):
 s=s or secrets.token_bytes(16);return s.hex()+'$'+hashlib.pbkdf2_hmac('sha256',p.encode(),s,210000).hex()
def okpw(p,x):
 try:s,h=x.split('$');return hmac.compare_digest(hp(p,bytes.fromhex(s)).split('$')[1],h)
 except:return False
def init():
 c=dbc();c.executescript("""CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT,email TEXT UNIQUE,password TEXT,role TEXT,coach_name TEXT,active INTEGER DEFAULT 1);CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,date TEXT,day TEXT,school TEXT,coach TEXT,title TEXT,start TEXT,end TEXT,class_group TEXT,age_group TEXT,planned_status TEXT,actual_status TEXT DEFAULT 'Scheduled',attendance INTEGER,notes TEXT,updated_at TEXT);CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,ts TEXT,user_email TEXT,action TEXT,session_id TEXT,detail TEXT);""")
 if c.execute('select count(*) from sessions').fetchone()[0]==0:
  t=open(os.path.join(BASE,'data.js'),encoding='utf8').read();m=re.search(r'const DATA=(.*);\s*$',t,re.S)
  for s in json.loads(m.group(1)):
   c.execute('insert into sessions(id,date,day,school,coach,title,start,end,class_group,age_group,planned_status) values(?,?,?,?,?,?,?,?,?,?,?)',(s['id'],s['date'],s['day'],s['school'],s['coach'],s['session'],s['start'],s['end'],s['group'],s['age'],str(s['status']).strip()))
 c.commit();c.close()
def e(x):return html.escape(str(x or ''))
def fd(x):
 try:return datetime.strptime(x,'%Y-%m-%d').strftime('%a %d %b %Y')
 except:return x
def page(title,b,u=None):
 nav=''
 if u:
  nav='<nav><a href="/">Today</a><a href="/schedule">Schedule</a><a href="/schools">Schools</a><a href="/reports">Reports</a>'+('<a href="/admin">Admin</a>' if u['role']=='admin' else '')+'<i></i><span>'+e(u['name'])+'</span><a href="/logout">Log out</a></nav>'
 return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)} · Eastern Gaels</title><style>:root{{--g:#164d2c;--bg:#f3f6f3;--m:#657269}}*{{box-sizing:border-box}}body{{font-family:system-ui;margin:0;background:var(--bg);color:#18231b}}header{{background:var(--g);color:#fff;padding:18px}}header div,main{{max-width:1100px;margin:auto}}header h1{{margin:0;font-size:22px}}nav{{display:flex;gap:5px;align-items:center;background:#fff;padding:8px max(12px,calc((100% - 1100px)/2));box-shadow:0 1px 8px #0001;overflow:auto}}nav a{{color:var(--g);font-weight:700;text-decoration:none;padding:8px}}nav i{{flex:1}}nav span{{white-space:nowrap;color:var(--m)}}main{{padding:18px}}.card{{background:#fff;padding:18px;border-radius:14px;margin:14px 0;box-shadow:0 2px 12px #0000000d}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}}.stat{{font-size:30px;font-weight:800;color:var(--g)}}.kpi{{position:relative;overflow:hidden}}.kpi small{{display:block;color:var(--m);margin-top:3px}}.barrow{{display:grid;grid-template-columns:minmax(120px,1.4fr) 3fr 52px;gap:10px;align-items:center;margin:11px 0}}.bartrack{{height:14px;background:#edf1ed;border-radius:999px;overflow:hidden}}.barfill{{height:100%;background:var(--g);border-radius:999px;min-width:2px}}.chartlink{{color:inherit;text-decoration:none}}.progress{{height:9px;background:#e8eee9;border-radius:999px;overflow:hidden;margin-top:8px}}.progress span{{display:block;height:100%;background:var(--g)}}.donut{{width:150px;height:150px;border-radius:50%;margin:12px auto;display:grid;place-items:center;background:conic-gradient(#164d2c 0 var(--done),#b85c5c var(--done) var(--cancel),#d8a82d var(--cancel) var(--closed),#dfe5e0 var(--closed) 100%)}}.donut:after{{content:'';width:92px;height:92px;background:white;border-radius:50%}}.legend{{display:flex;gap:12px;flex-wrap:wrap;font-size:13px}}.dot{{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:5px;background:#164d2c}}.muted{{color:var(--m)}}.session{{border-left:5px solid #267345}}.badge{{display:inline-block;padding:4px 9px;border-radius:999px;background:#e5f2e8;font-size:12px;font-weight:700}}.Completed{{background:#dff2e4}}.Cancelled{{background:#f7dddd}}.Rescheduled{{background:#fff0cc}}button,.btn{{display:inline-block;border:0;background:var(--g);color:#fff;padding:10px 13px;border-radius:9px;font-weight:700;text-decoration:none;cursor:pointer}}.secondary{{background:#e8eee9!important;color:#18231b!important}}input,select,textarea{{width:100%;padding:10px;border:1px solid #ccd5ce;border-radius:8px;font:inherit}}label{{display:block;font-weight:700;margin:10px 0 5px}}.row{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.actions{{display:flex;gap:7px;flex-wrap:wrap;margin-top:12px}}table{{width:100%;border-collapse:collapse;background:#fff}}th,td{{padding:10px;border-bottom:1px solid #e4e9e5;text-align:left}}th{{font-size:12px;color:var(--m)}}.tw{{overflow:auto;border-radius:12px}}.login{{max-width:430px;margin:45px auto}}@media(max-width:650px){{main{{padding:12px}}.row{{grid-template-columns:1fr}}nav span{{display:none}}}}</style></head><body><header><div><h1>Eastern Gaels Schools Coaching</h1><small>2026–2027 Programme</small></div></header>{nav}<main>{b}</main></body></html>'''
def card(s,admin=False):return f'''<div class="card session"><span class="badge {e(s['actual_status'])}">{e(s['actual_status'])}</span><h2>{e(s['school'])}</h2><div class="muted">{fd(s['date'])} · {e(s['start'])}–{e(s['end'])}</div><p><b>{e(s['coach'])}</b> · {e(s['class_group'])} · {e(s['age_group'])}<br>{e(s['title'])}</p><div class="actions"><a class="btn" href="/session?id={e(s['id'])}">Open session</a>{'<a class="btn secondary" href="/edit?id='+e(s['id'])+'">Edit</a>' if admin else ''}</div></div>'''
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def out(self,x,n=200,h=None):
  b=x.encode();self.send_response(n);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(b)));[(self.send_header(k,v)) for k,v in (h or {}).items()];self.end_headers();self.wfile.write(b)
 def red(self,x):self.send_response(303);self.send_header('Location',x);self.end_headers()
 def form(self):
  n=int(self.headers.get('Content-Length','0'));q=parse_qs(self.rfile.read(n).decode());return {k:(v if k=='ids' else v[-1]) for k,v in q.items()}
 def user(self):
  z=SimpleCookie(self.headers.get('Cookie'));sid=z.get('egsid');uid=SESS.get(sid.value) if sid else None
  if not uid:return None
  c=dbc();u=c.execute('select * from users where id=? and active=1',(uid,)).fetchone();c.close();return u
 def need(self):
  u=self.user()
  if not u:self.red('/login')
  return u
 def vis(self,u):return (' where coach=? ',[u['coach_name'] or u['name']]) if u['role']=='coach' else (' ',[])
 def do_GET(self):
  p=urlparse(self.path);path=p.path;q=parse_qs(p.query);c=dbc()
  if path=='/setup':
   if c.execute('select count(*) from users').fetchone()[0]:c.close();return self.red('/login')
   c.close();return self.out(page('Setup','<div class="card login"><h2>Create administrator</h2><p class="muted">First-run setup.</p><form method="post"><label>Name</label><input name="name" required><label>Email</label><input name="email" type="email" required><label>Password</label><input name="password" type="password" minlength="8" required><div class="actions"><button>Create admin</button></div></form></div>'))
  if path=='/login':
   if not c.execute('select count(*) from users').fetchone()[0]:c.close();return self.red('/setup')
   c.close();return self.out(page('Login','<div class="card login"><h2>Log in</h2><form method="post"><label>Email</label><input name="email" type="email" required><label>Password</label><input name="password" type="password" required><div class="actions"><button>Log in</button></div></form></div>'))
  if path=='/logout':
   z=SimpleCookie(self.headers.get('Cookie'));sid=z.get('egsid');SESS.pop(sid.value,None) if sid else None;c.close();self.send_response(303);self.send_header('Location','/login');self.send_header('Set-Cookie','egsid=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax');self.end_headers();return
  u=self.need()
  if not u:c.close();return
  if path=='/':
   d=q.get('date',[date.today().isoformat()])[0];w,a=self.vis(u);con='and' if 'where' in w else 'where';r=c.execute('select * from sessions '+w+con+' date=? order by start',a+[d]).fetchall();c.close();b=f'<h2>Today / Selected Day</h2><form class="card"><label>Date</label><div class="row"><input type="date" name="date" value="{e(d)}"><button>Show date</button></div></form>'+(''.join(card(x,u['role']=='admin') for x in r) if r else '<div class="card">No coaching scheduled for this date.</div>');return self.out(page('Today',b,u))
  if path=='/schedule':
   w,a=self.vis(u);r=c.execute('select * from sessions '+w+' order by date,start',a).fetchall();c.close();trs=''.join(f'<tr><td>{fd(x["date"])}</td><td><a href="/session?id={e(x["id"])}">{e(x["school"])}</a></td><td>{e(x["coach"])}</td><td>{e(x["class_group"])}</td><td><span class="badge {e(x["actual_status"])}">{e(x["actual_status"])}</span></td></tr>' for x in r);b=f'''<h2>Full Schedule</h2><div class="card"><input id="s" placeholder="Search school, coach, class or date…" oninput="f()"></div><div class="tw"><table id="t"><tr><th>Date</th><th>School</th><th>Coach</th><th>Class</th><th>Status</th></tr>{trs}</table></div><script>function f(){{let q=s.value.toLowerCase();document.querySelectorAll('#t tr').forEach((r,i)=>{{if(i)r.style.display=r.innerText.toLowerCase().includes(q)?'':'none'}})}}</script>''';return self.out(page('Schedule',b,u))
  if path=='/schools':
   w,a=self.vis(u);r=c.execute('select school,count(*) n,sum(actual_status="Completed") done from sessions '+w+' group by school order by school',a).fetchall();c.close();return self.out(page('Schools','<h2>Schools</h2><div class="grid">'+''.join(f'<div class="card"><h3>{e(x["school"])}</h3><div class="stat">{x["done"]}</div><div class="muted">completed of {x["n"]} scheduled</div></div>' for x in r)+'</div>',u))
  if path=='/session':
   s=c.execute('select * from sessions where id=?',(q.get('id',[''])[0],)).fetchone();c.close()
   if not s:return self.out(page('Not found','<div class="card">Session not found.</div>',u),404)
   if u['role']=='coach' and s['coach']!=(u['coach_name'] or u['name']):return self.out(page('Forbidden','<div class="card">Another coach owns this session.</div>',u),403)
   opts=''.join('<option'+(' selected' if s['actual_status']==x else '')+'>'+x+'</option>' for x in ['Scheduled','Completed','Cancelled','School Closed','Rescheduled']);b=card(s,u['role']=='admin')+f'''<div class="card"><form method="post"><input type="hidden" name="id" value="{e(s['id'])}"><label>Status</label><select name="status">{opts}</select><label>Attendance / children coached</label><input type="number" min="0" name="attendance" value="{e(s['attendance'])}"><label>Session notes</label><textarea name="notes" rows="5">{e(s['notes'])}</textarea><div class="actions"><button>Save session record</button></div></form></div>''';return self.out(page('Session',b,u))
  if path=='/reports':
   w,a=self.vis(u)
   ss=c.execute('select * from sessions '+w+' order by date,start',a).fetchall()
   total=len(ss);done=sum(x['actual_status']=='Completed' for x in ss);cancelled=sum(x['actual_status']=='Cancelled' for x in ss);closed=sum(x['actual_status']=='School Closed' for x in ss);scheduled=sum(x['actual_status']=='Scheduled' for x in ss);attendance=sum((x['attendance'] or 0) for x in ss if x['actual_status']=='Completed')
   hours=0.0
   for x in ss:
    if x['actual_status']=='Completed' and x['start'] and x['end']:
     try:
      st=datetime.strptime(x['start'],'%H:%M');en=datetime.strptime(x['end'],'%H:%M');hours+=max(0,(en-st).seconds/3600)
     except:pass
   pct=round(done*100/total) if total else 0
   byschool={};bycoach={};bymonth={}
   for x in ss:
    for dct,key in ((byschool,x['school']),(bycoach,x['coach'])):
     z=dct.setdefault(key,[0,0]);z[1]+=1;z[0]+=x['actual_status']=='Completed'
    if x['actual_status']=='Completed':
     try:key=datetime.strptime(x['date'],'%Y-%m-%d').strftime('%b %Y')
     except:key=x['date'][:7]
     bymonth[key]=bymonth.get(key,0)+1
   maxschool=max(1,max([v[0] for v in byschool.values()] or [0]));maxcoach=max(1,max([v[0] for v in bycoach.values()] or [0]));maxmonth=max(1,max(list(bymonth.values()) or [0]))
   schoolbars=''.join(f'<a class="chartlink" href="/reports/detail?school={e(k)}"><div class="barrow"><b>{e(k)}</b><div class="bartrack"><div class="barfill" style="width:{v[0]*100/maxschool:.0f}%"></div></div><b>{v[0]}</b></div></a>' for k,v in sorted(byschool.items()))
   coachbars=''.join(f'<a class="chartlink" href="/reports/detail?coach={e(k)}"><div class="barrow"><b>{e(k)}</b><div class="bartrack"><div class="barfill" style="width:{v[0]*100/maxcoach:.0f}%"></div></div><b>{v[0]}</b></div></a>' for k,v in sorted(bycoach.items()))
   monthbars=''.join(f'<div class="barrow"><b>{e(k)}</b><div class="bartrack"><div class="barfill" style="width:{v*100/maxmonth:.0f}%"></div></div><b>{v}</b></div>' for k,v in bymonth.items()) or '<p class="muted">No completed sessions yet.</p>'
   schoolcards=''.join(f'<a class="chartlink" href="/reports/detail?school={e(k)}"><div class="card"><h3>{e(k)}</h3><div class="stat">{v[0]} / {v[1]}</div><div class="muted">sessions completed · {round(v[0]*100/v[1]) if v[1] else 0}%</div><div class="progress"><span style="width:{v[0]*100/v[1] if v[1] else 0:.0f}%"></span></div></div></a>' for k,v in sorted(byschool.items()))
   d1=pct;d2=min(100,d1+(cancelled*100/total if total else 0));d3=min(100,d2+(closed*100/total if total else 0))
   c.close();b=f'''<h2>Coaching Dashboard</h2><p class="muted">Live summary of the 2026–2027 schools coaching programme.</p><div class="grid"><div class="card kpi"><div class="stat">{done}</div><b>Sessions completed</b><small>of {total} planned</small></div><div class="card kpi"><div class="stat">{pct}%</div><b>Programme complete</b><small>{scheduled} still scheduled</small></div><div class="card kpi"><div class="stat">{hours:.1f}</div><b>Coaching hours</b><small>completed sessions</small></div><div class="card kpi"><div class="stat">{attendance}</div><b>Recorded attendance</b><small>total contacts entered</small></div></div><div class="grid"><div class="card"><h3>Completed sessions by month</h3>{monthbars}</div><div class="card"><h3>Session status</h3><div class="donut" style="--done:{d1}%;--cancel:{d2}%;--closed:{d3}%"></div><div class="legend"><span><i class="dot"></i>Completed {done}</span><span>Cancelled {cancelled}</span><span>School closed {closed}</span><span>Scheduled {scheduled}</span></div></div></div><div class="grid"><div class="card"><h3>Completed by school</h3>{schoolbars}</div><div class="card"><h3>Completed by coach</h3>{coachbars}</div></div><h3>School progress</h3><div class="grid">{schoolcards}</div>{'<div class="actions"><a class="btn" href="/export.csv">Download CSV report</a></div>' if u['role']=='admin' else ''}''';return self.out(page('Dashboard',b,u))
  if path=='/reports/detail':
   school=q.get('school',[''])[0];coach=q.get('coach',[''])[0];w,a=self.vis(u);con='and' if 'where' in w else 'where';extra='';vals=list(a);title='Completed sessions'
   if school:extra=' school=?';vals.append(school);title=school
   elif coach:extra=' coach=?';vals.append(coach);title=coach
   else:extra=" actual_status='Completed'"
   r=c.execute('select * from sessions '+w+con+extra+' order by date,start',vals).fetchall();c.close();rows=''.join(f'<tr><td>{fd(x["date"])}</td><td>{e(x["school"])}</td><td>{e(x["coach"])}</td><td>{e(x["class_group"])}</td><td><span class="badge {e(x["actual_status"])}">{e(x["actual_status"])}</span></td><td>{e(x["attendance"])}</td></tr>' for x in r);return self.out(page('Report detail',f'<h2>{e(title)}</h2><p class="muted">{len(r)} sessions</p><div class="tw"><table><tr><th>Date</th><th>School</th><th>Coach</th><th>Class</th><th>Status</th><th>Attendance</th></tr>{rows}</table></div><div class="actions"><a class="btn secondary" href="/reports">Back to dashboard</a></div>',u))
  if path=='/admin':
   if u['role']!='admin':c.close();return self.out(page('Forbidden','<div class="card">Admin access required.</div>',u),403)
   us=c.execute('select * from users order by role,name').fetchall();co=[x[0] for x in c.execute('select distinct coach from sessions order by coach')];now=datetime.now();today=now.date().isoformat();clock=now.strftime('%H:%M');overdue=c.execute("select count(*) from sessions where actual_status='Scheduled' and (date < ? or (date = ? and coalesce(end,start,'23:59') < ?))",(today,today,clock)).fetchone()[0];c.close();opts=''.join(f'<option>{e(x)}</option>' for x in co);rows=''.join(f'<tr><td>{e(x["name"])}</td><td>{e(x["email"])}</td><td>{e(x["role"])}</td><td>{e(x["coach_name"])}</td></tr>' for x in us);b=f'''<h2>Administration</h2><div class="card"><h3>Past due sessions</h3><div class="stat">{overdue}</div><p class="muted">Scheduled sessions whose date/time has passed. Cancelled, School Closed, Rescheduled and already Completed sessions are not included.</p><div class="actions"><a class="btn" href="/admin/past-due">Review past sessions</a></div></div><div class="grid"><div class="card"><h3>Add user</h3><form method="post" action="/admin/user"><label>Name</label><input name="name" required><label>Email</label><input type="email" name="email" required><label>Temporary password</label><input type="password" minlength="8" name="password" required><label>Role</label><select name="role"><option>coach</option><option>admin</option></select><label>Timetable coach</label><select name="coach_name"><option value="">— None —</option>{opts}</select><div class="actions"><button>Create user</button></div></form></div><div class="card"><h3>Add session</h3><form method="post" action="/admin/session"><label>Date</label><input type="date" name="date" required><label>School</label><input name="school" required><label>Coach</label><input name="coach" required><div class="row"><div><label>Start</label><input type="time" name="start"></div><div><label>End</label><input type="time" name="end"></div></div><label>Class group</label><input name="class_group"><label>Age group</label><input name="age_group"><label>Title</label><input name="title" value="GAA Coaching"><div class="actions"><button>Add session</button></div></form></div></div><div class="card"><h3>Users</h3><div class="tw"><table><tr><th>Name</th><th>Email</th><th>Role</th><th>Timetable coach</th></tr>{rows}</table></div></div>''';return self.out(page('Admin',b,u))
  if path=='/admin/past-due':
   if u['role']!='admin':c.close();return self.out(page('Forbidden','<div class="card">Admin access required.</div>',u),403)
   now=datetime.now();today=now.date().isoformat();clock=now.strftime('%H:%M');r=c.execute("select * from sessions where actual_status='Scheduled' and (date < ? or (date = ? and coalesce(end,start,'23:59') < ?)) order by date,start",(today,today,clock)).fetchall();c.close()
   rows=''.join(f'<tr><td><input form="bulk" type="checkbox" name="ids" value="{e(x["id"])}" checked></td><td>{fd(x["date"])}</td><td>{e(x["school"])}</td><td>{e(x["coach"])}</td><td>{e(x["start"])}–{e(x["end"])}</td><td><a href="/session?id={e(x["id"])}">Open</a></td></tr>' for x in r)
   if not r:b='<h2>Past due sessions</h2><div class="card"><h3>All caught up</h3><p>There are no past-due sessions still marked Scheduled.</p><a class="btn secondary" href="/admin">Back to Admin</a></div>'
   else:b=f'''<h2>Past due sessions</h2><div class="card"><p>Review the sessions below. Untick anything that was not actually completed, then mark the selected sessions Completed.</p><form id="bulk" method="post" action="/admin/past-due"><div class="actions"><button>Mark selected as Completed</button><button type="button" class="secondary" onclick="document.querySelectorAll('input[name=ids]').forEach(x=>x.checked=true)">Select all</button><button type="button" class="secondary" onclick="document.querySelectorAll('input[name=ids]').forEach(x=>x.checked=false)">Clear</button></div></form></div><div class="tw"><table><tr><th>Complete?</th><th>Date</th><th>School</th><th>Coach</th><th>Time</th><th></th></tr>{rows}</table></div>'''
   return self.out(page('Past due sessions',b,u))
  if path=='/edit':
   if u['role']!='admin':c.close();return self.out('Forbidden',403)
   s=c.execute('select * from sessions where id=?',(q.get('id',[''])[0],)).fetchone();c.close()
   if not s:return self.red('/schedule')
   b=f'''<h2>Edit session</h2><div class="card"><form method="post"><input type="hidden" name="id" value="{e(s['id'])}"><label>Date</label><input type="date" name="date" value="{e(s['date'])}" required><label>School</label><input name="school" value="{e(s['school'])}" required><label>Coach</label><input name="coach" value="{e(s['coach'])}" required><div class="row"><div><label>Start</label><input type="time" name="start" value="{e(s['start'])}"></div><div><label>End</label><input type="time" name="end" value="{e(s['end'])}"></div></div><label>Class</label><input name="class_group" value="{e(s['class_group'])}"><label>Age group</label><input name="age_group" value="{e(s['age_group'])}"><label>Title</label><input name="title" value="{e(s['title'])}"><div class="actions"><button>Save changes</button></div></form></div>''';return self.out(page('Edit',b,u))
  if path=='/export.csv':
   if u['role']!='admin':c.close();return self.out('Forbidden',403)
   r=c.execute('select * from sessions order by date,start').fetchall();c.close();o=io.StringIO();w=csv.writer(o);w.writerow(r[0].keys() if r else []);[w.writerow(tuple(x)) for x in r];b=o.getvalue().encode();self.send_response(200);self.send_header('Content-Type','text/csv');self.send_header('Content-Disposition','attachment; filename="eastern-gaels-report.csv"');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
  c.close();return self.out(page('Not found','<div class="card">Page not found.</div>',u),404)
 def do_POST(self):
  p=urlparse(self.path).path;f=self.form();c=dbc()
  if p=='/setup':
   if c.execute('select count(*) from users').fetchone()[0]:c.close();return self.red('/login')
   c.execute('insert into users(name,email,password,role) values(?,?,?,?)',(f['name'],f['email'].lower(),hp(f['password']),'admin'));c.commit();c.close();return self.red('/login')
  if p=='/login':
   u=c.execute('select * from users where email=? and active=1',(f.get('email','').lower(),)).fetchone();c.close()
   if not u or not okpw(f.get('password',''),u['password']):return self.out(page('Login','<div class="card login"><h2>Incorrect email or password</h2><a class="btn" href="/login">Try again</a></div>'),401)
   sid=secrets.token_urlsafe(32);SESS[sid]=u['id'];self.send_response(303);self.send_header('Location','/');secure='; Secure' if os.environ.get('COOKIE_SECURE','0')=='1' else ''
   self.send_header('Set-Cookie',f'egsid={sid}; Path=/; HttpOnly; SameSite=Lax{secure}');self.end_headers();return
  u=self.need()
  if not u:c.close();return
  if p=='/session':
   s=c.execute('select * from sessions where id=?',(f.get('id'),)).fetchone()
   if not s or (u['role']=='coach' and s['coach']!=(u['coach_name'] or u['name'])):c.close();return self.out('Forbidden',403)
   a=f.get('attendance','');a=int(a) if a.isdigit() else None;c.execute('update sessions set actual_status=?,attendance=?,notes=?,updated_at=? where id=?',(f.get('status'),a,f.get('notes',''),datetime.now().isoformat(timespec='seconds'),f['id']));c.execute('insert into audit(ts,user_email,action,session_id,detail) values(?,?,?,?,?)',(datetime.now().isoformat(timespec='seconds'),u['email'],'update_session',f['id'],f.get('status')));c.commit();c.close();return self.red('/session?id='+f['id'])
  if p=='/admin/past-due' and u['role']=='admin':
   ids=f.get('ids',[]);ids=[ids] if isinstance(ids,str) else ids;now=datetime.now();today=now.date().isoformat();clock=now.strftime('%H:%M');changed=0
   for sid in ids:
    r=c.execute("select * from sessions where id=? and actual_status='Scheduled' and (date < ? or (date = ? and coalesce(end,start,'23:59') < ?))",(sid,today,today,clock)).fetchone()
    if r:
     c.execute("update sessions set actual_status='Completed',updated_at=? where id=?",(now.isoformat(timespec='seconds'),sid));c.execute('insert into audit(ts,user_email,action,session_id,detail) values(?,?,?,?,?)',(now.isoformat(timespec='seconds'),u['email'],'bulk_complete_past_due',sid,'Completed'));changed+=1
   c.commit();c.close();return self.red('/admin/past-due')
  if p=='/admin/user' and u['role']=='admin':
   try:c.execute('insert into users(name,email,password,role,coach_name) values(?,?,?,?,?)',(f['name'],f['email'].lower(),hp(f['password']),f['role'],f.get('coach_name') or None));c.commit()
   except sqlite3.IntegrityError:pass
   c.close();return self.red('/admin')
  if p=='/admin/session' and u['role']=='admin':
   sid='s'+secrets.token_hex(5);day=datetime.strptime(f['date'],'%Y-%m-%d').strftime('%A');c.execute('insert into sessions(id,date,day,school,coach,title,start,end,class_group,age_group,planned_status) values(?,?,?,?,?,?,?,?,?,?,?)',(sid,f['date'],day,f['school'],f['coach'],f.get('title'),f.get('start'),f.get('end'),f.get('class_group'),f.get('age_group'),'Confirmed'));c.commit();c.close();return self.red('/session?id='+sid)
  if p=='/edit' and u['role']=='admin':
   day=datetime.strptime(f['date'],'%Y-%m-%d').strftime('%A');c.execute('update sessions set date=?,day=?,school=?,coach=?,start=?,end=?,class_group=?,age_group=?,title=?,updated_at=? where id=?',(f['date'],day,f['school'],f['coach'],f.get('start'),f.get('end'),f.get('class_group'),f.get('age_group'),f.get('title'),datetime.now().isoformat(timespec='seconds'),f['id']));c.commit();c.close();return self.red('/session?id='+f['id'])
  c.close();return self.red('/')
if __name__=='__main__':init();port=int(os.environ.get('PORT','8000'));print(f'Open http://localhost:{port}');ThreadingHTTPServer(('0.0.0.0',port),H).serve_forever()
