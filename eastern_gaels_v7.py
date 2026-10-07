#!/usr/bin/env python3
import os,re,json,sqlite3,secrets,hashlib,hmac,csv,io,html,shutil,threading,time,tempfile,gc
from openpyxl import load_workbook
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs,urlencode
from http.cookies import SimpleCookie
from datetime import date,datetime,timedelta
import calendar
BASE=os.path.dirname(os.path.abspath(__file__))
DATA_DIR=os.environ.get('DATA_DIR', os.path.dirname(os.environ['DATABASE_PATH']) if os.environ.get('DATABASE_PATH') else BASE)
os.makedirs(DATA_DIR,exist_ok=True)
DB=os.environ.get('DATABASE_PATH',os.path.join(DATA_DIR,'eastern_gaels.db'))
SESS={}
DEMO_FILE=os.path.join(DATA_DIR,'demographics_current.json')
DEMO_SOURCE=os.path.join(BASE,'demographics.json')
def load_demo():
 p=DEMO_FILE if os.path.exists(DEMO_FILE) else DEMO_SOURCE
 if os.path.exists(p):
  try:
   with open(p,encoding='utf8') as f:d=json.load(f)
  except (OSError,json.JSONDecodeError): d={}
 else: d={}
 # Normalise current and legacy demographics field names.
 d.setdefault('catchment', d.get('areas', {}))
 d.setdefault('school_totals', d.get('schools', {}))
 d.setdefault('areas', d.get('catchment', {}))
 d.setdefault('schools', d.get('school_totals', {}))
 d.setdefault('age_totals', {})
 d.setdefault('age_areas', {})
 d.setdefault('age_schools', {})
 d.setdefault('games', {})
 d.setdefault('growth', {})
 d.setdefault('players_by_age', {})
 d.setdefault('juvenile_gender', {})
 d.setdefault('senior_adult_non_playing_count', 0)
 d.setdefault('senior_adult_non_playing_members', [])
 d.setdefault('senior_adult_ladies_count', 0)
 d.setdefault('senior_adult_ladies_members', [])
 d.setdefault('senior_adult_mens_count', 0)
 d.setdefault('senior_adult_mens_members', [])
 d.setdefault('upcoming_events', [])
 d.setdefault('warnings', [])
 return d
DEMO=load_demo()
COACH_FILE=os.path.join(DATA_DIR,"coaching_team_current.json")
COACH_SOURCE=os.path.join(BASE,"coaching_team.json")
def load_coaching():
 p=COACH_FILE if os.path.exists(COACH_FILE) else COACH_SOURCE
 if not os.path.exists(p): return {"coaches":{},"teams":{},"imported_at":None}
 with open(p,encoding="utf8") as f:d=json.load(f)
 d.setdefault("coaches",{});d.setdefault("teams",{});return d
COACHING=load_coaching()

# Google Drive automatic source feeds.
# Authentication is supplied through GOOGLE_SERVICE_ACCOUNT_JSON in the environment.
GOOGLE_DEMOGRAPHICS_SHEET_ID=os.environ.get('GOOGLE_DEMOGRAPHICS_SHEET_ID','1EIG_JZ-bDShJ2mbuI-hLdmTWLNZsaC5EbS4AdB3PMPo')
GOOGLE_SCHOOLS_SHEET_ID=os.environ.get('GOOGLE_SCHOOLS_SHEET_ID','1F4aC6kgQ3ajaa-fXHYxe_P7M7m_RGPpE0HRirnzkm78')
GOOGLE_SYNC_MINUTES=max(5,int(os.environ.get('GOOGLE_SYNC_MINUTES','5')))
GOOGLE_SYNC_ENABLED=os.environ.get('GOOGLE_SYNC_ENABLED','1').strip().lower() not in ('0','false','no','off')
GARDA_VETTING_FOLDER_ID=os.environ.get('GARDA_VETTING_FOLDER_ID','1MuoKe0MbW_cwd71GhjaO_yut1n7hHydu')
GOOGLE_OAUTH_CLIENT_ID=os.environ.get('GOOGLE_OAUTH_CLIENT_ID','').strip()
GOOGLE_OAUTH_CLIENT_SECRET=os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET','').strip()
GOOGLE_OAUTH_REDIRECT_URI=os.environ.get('GOOGLE_OAUTH_REDIRECT_URI','https://eastern-gaels-coaching.onrender.com/oauth2callback').strip()
GOOGLE_OAUTH_TOKEN_FILE=os.path.join(DATA_DIR,'google_drive_oauth.json')
GOOGLE_OAUTH_STATES={}
SYNC_STATUS_FILE=os.path.join(DATA_DIR,'google_sync_status.json')
SYNC_LOCK=threading.Lock()
GPO_COST_FILE=os.path.join(DATA_DIR,'gpo_costs_current.json')
def load_gpo_costs():
 try:
  with open(GPO_COST_FILE,encoding='utf8') as f:return json.load(f)
 except (OSError,json.JSONDecodeError):return {'years':{},'imported_at':None}
GPO_COSTS=load_gpo_costs()
def coach_key(x):
 k=" ".join(str(x or "").strip().upper().split());return {"KATE O SULLIVAN":"KATE SULLIVAN"}.get(k,k)
def parse_expiry_text(x):
 t=str(x or "").strip();m=re.search(r"(?i)expires\s+([A-Za-z]+)\s+(20\d{2})",t)
 if not m:return None
 try:
  month=datetime.strptime(m.group(1),"%B").month;year=int(m.group(2));return date(year,month,calendar.monthrange(year,month)[1]).isoformat()
 except:return None
def yn(x):
 t=str(x or '').strip().upper()
 if t in ('YES','Y','TRUE','1'): return 'Yes'
 if t in ('NO','N','FALSE','0'): return 'No'
 return 'Unknown'

def parse_schools_xlsx(path):
 wb=load_workbook(path,data_only=True,read_only=True);sessions=[];seq=1
 for ws in wb.worksheets:
  hdr=None;hi=None
  for i,row in enumerate(ws.iter_rows(min_row=1,max_row=min(12,ws.max_row or 12),values_only=True),start=1):
   norm=[str(v or '').strip().lower() for v in row]
   if 'date' in norm and 'school' in norm and 'coach' in norm:
    hdr={v:j for j,v in enumerate(norm) if v};hi=i;break
  if hdr is None: continue
  def cell(row,*names):
   for n in names:
    j=hdr.get(n)
    if j is not None and j<len(row): return row[j]
   return ''
  def dval(v):
   if isinstance(v,datetime): return v.date().isoformat()
   if isinstance(v,date): return v.isoformat()
   if isinstance(v,(int,float)):
    try:return (datetime(1899,12,30)+timedelta(days=float(v))).date().isoformat()
    except:return ''
   s=str(v or '').strip()
   if not s:return ''
   for fmt in ('%Y-%m-%d','%d/%m/%Y','%d-%m-%Y','%d %b %Y','%d %B %Y'):
    try:return datetime.strptime(s,fmt).date().isoformat()
    except:pass
   return s
  def tval(v):
   if isinstance(v,datetime): return v.strftime('%H:%M')
   if hasattr(v,'hour') and hasattr(v,'minute'): return f'{v.hour:02d}:{v.minute:02d}'
   if isinstance(v,(int,float)):
    secs=round((float(v)%1)*86400);return f'{(secs//3600)%24:02d}:{(secs%3600)//60:02d}'
   s=str(v or '').strip()
   if not s:return ''
   for fmt in ('%H:%M:%S','%H:%M','%I:%M %p'):
    try:return datetime.strptime(s,fmt).strftime('%H:%M')
    except:pass
   return s
  for row in ws.iter_rows(min_row=hi+1,values_only=True):
   raw_date=cell(row,'date');school=str(cell(row,'school') or '').strip()
   if raw_date in ('',None) or not school: continue
   sessions.append({'id':f'SCH-{seq:03d}','date':dval(raw_date),'day':str(cell(row,'day') or '').strip(),'school':school,'coach':str(cell(row,'coach') or '').strip(),'session':str(cell(row,'session / sport','session','title') or '').strip(),'start':tval(cell(row,'start time','start')),'end':tval(cell(row,'end time','end')),'group':str(cell(row,'group / year','class group','group') or '').strip(),'status':str(cell(row,'status') or 'Confirmed').strip(),'age':str(cell(row,'club age group','age group','age') or '').strip()});seq+=1
 if not sessions: raise ValueError('No school coaching sessions found. Expected columns including Date, School and Coach.')
 return sessions


def parse_gpo_costs_xlsx(path):
 wb=load_workbook(path,data_only=True,read_only=True)
 years={}
 for sheet_name in wb.sheetnames:
  m=re.match(r'(?i)^GPO\s+COST\s+(\d{4})\s*-\s*(\d{4})$',str(sheet_name).strip())
  if not m:continue
  ws=wb[sheet_name];entries=[]
  for row in ws.iter_rows(min_row=2,max_col=4,values_only=True):
   worked,school,cost,detail=(list(row)+[None]*4)[:4]
   school=str(school or '').strip()
   if not school:continue
   try:amount=float(cost or 0)
   except (TypeError,ValueError):
    s=re.sub(r'[^0-9.\-]','',str(cost or ''))
    try:amount=float(s or 0)
    except ValueError:amount=0.0
   entries.append({'day':str(worked or '').strip(),'school':school,'cost':round(amount,2),'detail':str(detail or '').strip()})
  label=f'{m.group(1)}/{m.group(2)[-2:]}'
  years[label]={'sheet':sheet_name,'total':round(sum(x['cost'] for x in entries),2),'entries':entries}
 wb.close()
 if not years:raise ValueError('No GPO Cost worksheets found.')
 return {'years':years,'imported_at':datetime.now().isoformat(timespec='seconds')}

def parse_coaching_xlsx(path):
 wb=load_workbook(path,data_only=True,read_only=True);ws=next((wb[n] for n in wb.sheetnames if clean_name(n).startswith('GARDA VETTING')),None)
 if ws is None:raise ValueError('Missing Garda Vetting & Safeguarding worksheet')
 coaches={}
 for row in ws.iter_rows(min_row=2,max_col=5,values_only=True):
  if not row[0]:continue
  k=coach_key(row[0]);coaches[k]={'name':' '.join(str(row[0]).strip().split()),'garda_vetted':yn(row[1]),'garda_expiry':parse_expiry_text(row[2]),'garda_expiry_text':str(row[2] or '').strip(),'safeguarding':yn(row[3]),'qualification':str(row[4] or 'Unknown').strip(),'teams':[]}
 qws=next((wb[n] for n in wb.sheetnames if clean_name(n).startswith('COACHES COURSE QUALIFICATION')),None)
 if qws:
  for row in qws.iter_rows(min_row=2,max_col=2,values_only=True):
   if not row[0]:continue
   k=coach_key(row[0]);q=str(row[1] or 'Unknown').strip()
   if k in coaches and q.upper() not in ('','UNKNOWN','NONE'):coaches[k]['qualification']=q
 pws=next((wb[n] for n in wb.sheetnames if clean_name(n).startswith('COACHES POOL SUMMARY')),None);teams={}
 if pws:
  for row in pws.iter_rows(min_row=2,values_only=True):
   if not row[0]:continue
   team=' '.join(str(row[0]).strip().upper().split());names=[]
   for raw in row[2:]:
    if not raw or not str(raw).strip():continue
    k=coach_key(raw)
    if k not in coaches:coaches[k]={'name':' '.join(str(raw).strip().title().split()),'garda_vetted':'Unknown','garda_expiry':None,'garda_expiry_text':'','safeguarding':'Unknown','qualification':'Unknown','teams':[]}
    names.append(coaches[k]['name']);coaches[k]['teams'].append(team)
   teams[team]=names
 return {'coaches':coaches,'teams':teams,'imported_at':datetime.now().isoformat(timespec='seconds')}

def expiry_bucket(c,today=None):
 today=today or date.today();v=str(c.get('garda_vetted',c.get('garda_status','Unknown'))).strip().upper()
 if v=='NO':return ('not_vetted',None)
 if v!='YES':return ('unknown',None)
 ex=c.get('garda_expiry')
 if not ex:return ('unknown_expiry',None)
 try:d=date.fromisoformat(ex);days=(d-today).days
 except:return ('unknown_expiry',None)
 if days<0:return ('expired',days)
 if days<=90:return ('urgent',days)
 if days<=180:return ('warning',days)
 return ('valid',days)


def clean_name(x):
 return ' '.join(str(x or '').strip().upper().split())
def num(x):
 try:return int(x or 0)
 except:return 0
def parse_integrated_tabs(wb):
 names=wb.sheetnames
 def get_sheet(prefix):
  return next((wb[n] for n in names if clean_name(n).startswith(clean_name(prefix))),None)
 coaches={};teams={};qual_summary={};events=[]
 def ensure(raw):
  if not raw or not str(raw).strip(): return None
  k=coach_key(raw)
  if k not in coaches:
   coaches[k]={'name':' '.join(str(raw).strip().split()),'garda_vetted':'Unknown','garda_expiry':None,'garda_expiry_text':'','safeguarding':'Unknown','qualification':'Unknown','teams':[]}
  return k
 # Dedicated Garda Vetting tab. "Expires Mon YYYY" means currently vetted with an expiry date.
 ws=get_sheet('Garda Vetting')
 if ws:
  for row in ws.iter_rows(min_row=2,max_col=3,values_only=True):
   k=ensure(row[0])
   if not k: continue
   status=str(row[1] or '').strip();up=status.upper();expiry_text=str(row[2] or '').strip()
   ex=parse_expiry_text(expiry_text) or parse_expiry_text(status)
   if up in ('COMPLIANT','YES','Y','CURRENT','VALID'):
    coaches[k]['garda_vetted']='Yes'
   elif up in ('EXPIRED','NO','N','NON-COMPLIANT','NON COMPLIANT'):
    coaches[k]['garda_vetted']='No'
   else:
    coaches[k]['garda_vetted']=yn(status)
   coaches[k]['garda_expiry']=ex
   coaches[k]['garda_expiry_text']=expiry_text or status
 # Dedicated Safeguarding tab.
 ws=get_sheet('Safeguarding')
 if ws:
  for row in ws.iter_rows(min_row=2,max_col=3,values_only=True):
   k=ensure(row[0])
   if not k: continue
   status=str(row[1] or '').strip();up=status.upper()
   if up in ('COMPLIANT','YES','Y','CURRENT','VALID'): coaches[k]['safeguarding']='Yes'
   elif up in ('EXPIRED','NO','N','NON-COMPLIANT','NON COMPLIANT'): coaches[k]['safeguarding']='No'
   else: coaches[k]['safeguarding']=yn(status)
 # Dedicated Coaching Qualifications tab: A:B is coach detail; D:E is chart summary.
 ws=get_sheet('Coaching Qualifications')
 if ws:
  for row in ws.iter_rows(min_row=2,max_col=5,values_only=True):
   k=ensure(row[0])
   if k:
    q=str(row[1] or '').strip()
    if q: coaches[k]['qualification']=q
   qname=str(row[3] or '').strip()
   if qname and row[4] not in (None,''):
    try: qual_summary[qname]=int(float(row[4]))
    except (TypeError,ValueError): pass
 # Coaching pool / teams from Coaches By Age Group.
 ws=get_sheet('Coaches By Age Group')
 if ws:
  for row in ws.iter_rows(min_row=2,values_only=True):
   team=' '.join(str(row[0] or '').strip().upper().split())
   if not team: continue
   members=[]
   for raw in row[2:]:
    k=ensure(raw)
    if not k: continue
    if team not in coaches[k]['teams']: coaches[k]['teams'].append(team)
    members.append(coaches[k]['name'])
   teams[team]=members
 # Upcoming Events: Event Type, Venue, Date, Time.
 ws=get_sheet('Upcoming Events')
 if ws:
  for row in ws.iter_rows(min_row=2,max_col=4,values_only=True):
   title=str(row[0] or '').strip()
   if not title: continue
   venue=str(row[1] or '').strip();dv=row[2];tv=row[3]
   if isinstance(dv,(datetime,date)):
    dsort=dv.strftime('%Y-%m-%d');ds=dv.strftime('%d %b %Y')
   elif isinstance(dv,(int,float)):
    try:
     dd=(datetime(1899,12,30)+timedelta(days=float(dv))).date();dsort=dd.isoformat();ds=dd.strftime('%d %b %Y')
    except: dsort=str(dv);ds=str(dv)
   else:
    ds=str(dv or '').strip();dsort=ds
   if isinstance(tv,(datetime,)): ts=tv.strftime('%H:%M')
   elif hasattr(tv,'hour'): ts=f'{tv.hour:02d}:{tv.minute:02d}'
   elif isinstance(tv,(int,float)):
    mins=round((float(tv)%1)*24*60);ts=f'{(mins//60)%24:02d}:{mins%60:02d}'
   else: ts=str(tv or '').strip()
   events.append({'event':title,'venue':venue,'date':ds,'time':ts,'sort_date':dsort})
 events.sort(key=lambda x:(x.get('sort_date','9999'),x.get('time','99:99')))
 return {'coaches':coaches,'teams':teams,'qualification_summary':qual_summary,'imported_at':datetime.now().isoformat(timespec='seconds')},events

def parse_demographics_xlsx(path):
 wb=load_workbook(path,data_only=True,read_only=True)
 names=wb.sheetnames
 def find_sheet(prefix):
  for n in names:
   if clean_name(n).startswith(clean_name(prefix)):return wb[n]
  raise ValueError('Missing worksheet: '+prefix)
 def find_growth_sheet():
  # Flexible lookup: current name, legacy name, or a future name containing
  # both GROWTH and YEAR.
  for label in ('Juvenile Growth Year on Year','Growth Year on Year'):
   key=clean_name(label)
   for n in names:
    if clean_name(n).startswith(key):return wb[n]
  for n in names:
   key=clean_name(n)
   if 'GROWTH' in key and 'YEAR' in key:return wb[n]
  raise ValueError('Missing juvenile membership growth worksheet')
 agews=find_sheet('Age Group Numbers Breakdown')
 age_totals={};age_areas={};age_schools={};warnings=[]
 # Read the workbook's hard-coded juvenile Boys/Girls summary.
 juvenile_gender={}
 for row in agews.iter_rows(values_only=True):
  vals=list(row)
  for j,v in enumerate(vals):
   key=clean_name(v)
   if key in ('TOTAL BOYS','TOTAL GIRLS'):
    value=vals[j+1] if j+1<len(vals) else None
    juvenile_gender['Boys' if key=='TOTAL BOYS' else 'Girls']=num(value)
 for col,g in zip([1,4,7,10,13,16,19,22],['U12','U11','U10','U9','U8','U7','U6','U5']):
  areas={clean_name(agews.cell(r,col).value):num(agews.cell(r,col+1).value) for r in range(2,8) if agews.cell(r,col).value}
  schools={clean_name(agews.cell(r,col).value):num(agews.cell(r,col+1).value) for r in range(10,17) if agews.cell(r,col).value}
  total=num(agews.cell(8,col+1).value) or sum(areas.values())
  age_totals[g]=total;age_areas[g]=areas;age_schools[g]=schools
  if sum(areas.values())!=total:warnings.append(f'{g} area breakdown sums to {sum(areas.values())}, total is {total}')
  if sum(schools.values())!=total:warnings.append(f'{g} school breakdown sums to {sum(schools.values())}, total is {total}')
 def two_col(prefix,skip_totals=True):
  ws=find_sheet(prefix);d={}
  for row in ws.iter_rows(min_row=2,max_col=2,values_only=True):
   k=clean_name(row[0]);v=row[1]
   if not k or (skip_totals and k.startswith('TOTAL')):continue
   if v is None or str(v).strip()=='':continue
   d[k]=num(v)
  return d
 # Player-name worksheets: import only player name and school.
 # Discover sheets by their headers, not by worksheet name, so tabs such as
 # "U11 Players" or a default Excel name such as "Sheet10" are supported.
 # Deliberately ignore DOB, parent/guardian, phone, address and email fields.
 players_by_age={}
 for sheet_name in names:
  pws=wb[sheet_name]
  header_row=None;name_col=None;school_col=None;dob_col=None
  for r in range(1,min(11,(pws.max_row or 10)+1)):
   row_headers={}
   for c in range(1,min(21,(pws.max_column or 20)+1)):
    h=clean_name(pws.cell(r,c).value)
    row_headers[h]=c
   if 'PLAYER NAME' in row_headers and 'SCHOOL' in row_headers:
    header_row=r;name_col=row_headers['PLAYER NAME'];school_col=row_headers['SCHOOL'];dob_col=row_headers.get('DATE OF BIRTH');break
  if not (header_row and name_col and school_col):
   continue
  # First prefer an explicit Uxx / UNDER xx marker in the title or top rows.
  probe=sheet_name+' '+ ' '.join(str(v or '') for row in pws.iter_rows(min_row=1,max_row=min(6,pws.max_row or 6),max_col=min(10,pws.max_column or 10),values_only=True) for v in row)
  m=re.search(r'(?i)UNDER\s*(\d{1,2})',probe) or re.search(r'(?i)\bU\s*(\d{1,2})\b',probe)
  group=('U'+str(int(m.group(1)))) if m else None
  # If the sheet has a generic name, infer the group from DOB birth years and
  # the latest populated membership year (e.g. 2026 - 2015 = U11).
  if not group and dob_col:
   birth_years=[]
   for row in pws.iter_rows(min_row=header_row+1,max_col=dob_col,values_only=True):
    v=row[dob_col-1]
    if not v: continue
    y=None
    if hasattr(v,'year'): y=v.year
    else:
     mm=re.search(r'(19|20)\d{2}',str(v))
     if mm: y=int(mm.group(0))
    if y: birth_years.append(y)
   if birth_years:
    from collections import Counter
    birth_year=Counter(birth_years).most_common(1)[0][0]
    # Growth Year on Year is the authoritative programme year where available.
    try:
     gws=find_growth_sheet();years=[]
     for rr in gws.iter_rows(min_row=2,max_col=2,values_only=True):
      try:
       yy=int(float(rr[0])); total=rr[1]
       if 2000 <= yy <= 2100 and total is not None and str(total).strip(): years.append(yy)
      except (TypeError,ValueError): pass
     ref_year=max(years) if years else datetime.now().year
    except Exception:
     ref_year=datetime.now().year
    inferred=ref_year-birth_year
    if 4 <= inferred <= 18: group='U'+str(inferred)
  if not group:
   warnings.append(f'Could not determine age group for player worksheet: {sheet_name}')
   continue
  rows=[]
  for row in pws.iter_rows(min_row=header_row+1,max_col=max(name_col,school_col),values_only=True):
   player=' '.join(str(row[name_col-1] or '').strip().split())
   school=' '.join(str(row[school_col-1] or '').strip().split())
   if not player: continue
   if clean_name(player).startswith('UNDER '): continue
   rows.append({'name':player,'school':school})
  if rows: players_by_age[group]=rows

 # Actual player-list tabs are authoritative for membership by age group.
 # This prevents stale summary cells from leaving the dashboard one player behind.
 for g,rows in players_by_age.items():
  if g in age_totals:
   summary_total=age_totals[g]
   actual_total=len(rows)
   if summary_total!=actual_total:
    warnings.append(f'{g} summary total is {summary_total}; player tab contains {actual_total}. Using player-tab count.')
   age_totals[g]=actual_total

 # Senior Adult Non-Playing Members: count only the numbered member list,
 # not the yearly summary rows at the top of the worksheet.
 senior_adult_non_playing=[]
 try:
  aws=find_sheet('Senior Adult Non Playing Member')
  in_member_list=False
  for left,right in aws.iter_rows(min_row=1,max_col=2,values_only=True):
   right_text=' '.join(str(right or '').strip().split())
   if clean_name(right_text).startswith('SENIOR ADULT NON PLAYING MEMBERS'):
    in_member_list=True;continue
   if not in_member_list or not right_text:continue
   try: member_no=int(float(left))
   except (TypeError,ValueError):continue
   if member_no>=1:senior_adult_non_playing.append(right_text)
 except ValueError:
  warnings.append('Senior Adult Non Playing Member worksheet not found; adult non-playing count set to 0.')
 senior_adult_non_playing_count=len(senior_adult_non_playing)

 # Senior Adult Ladies Members: count only numbered rows with a member name.
 senior_adult_ladies=[]
 try:
  lws=find_sheet('Senior Adult Ladies Members')
  for left,right in lws.iter_rows(min_row=1,max_col=2,values_only=True):
   right_text=' '.join(str(right or '').strip().split())
   if not right_text:continue
   try: member_no=int(float(left))
   except (TypeError,ValueError):continue
   if 1<=member_no<1000:senior_adult_ladies.append(right_text)
 except ValueError:
  warnings.append('Senior Adult Ladies Members worksheet not found; ladies count set to 0.')
 senior_adult_ladies_count=len(senior_adult_ladies)

 # Senior Adult Mens Members: count only numbered rows with a member name.
 senior_adult_mens=[]
 try:
  mws=find_sheet('Senior Adult Mens Members')
  for left,right in mws.iter_rows(min_row=1,max_col=2,values_only=True):
   right_text=' '.join(str(right or '').strip().split())
   if not right_text:continue
   try: member_no=int(float(left))
   except (TypeError,ValueError):continue
   if 1<=member_no<1000:senior_adult_mens.append(right_text)
 except ValueError:
  warnings.append('Senior Adult Mens Members worksheet not found; mens count set to 0.')
 senior_adult_mens_count=len(senior_adult_mens)

 games=two_col('Games Played By Age Group')
 # Growth sheet uses Excel numeric years (e.g. 2023.0). Parse them as years
 # instead of passing them through clean_name(), which would produce '2023.0'.
 growthws=find_growth_sheet();growth={}
 for yr,val in growthws.iter_rows(min_row=2,max_col=2,values_only=True):
  try:
   year=int(float(yr))
  except (TypeError,ValueError):
   continue
  if year < 1900 or year > 2200 or val is None or str(val).strip()=='':
   continue
  growth[str(year)]=num(val)
 # Juvenile Membership Growth remains sourced from its dedicated worksheet.
 areas=two_col('Parish Catchment Areas')
 schools=two_col('Schools Catchment Areas')
 total_players=growth.get(max(growth.keys(),key=int),sum(age_totals.values())) if growth else sum(age_totals.values())
 if sum(areas.values())!=total_players:warnings.append(f'Parish catchment sums to {sum(areas.values())}, latest player total is {total_players}')
 if sum(schools.values())!=total_players:warnings.append(f'School catchment sums to {sum(schools.values())}, latest player total is {total_players}')
 coaching,events=parse_integrated_tabs(wb)
 return {'age_totals':age_totals,'age_areas':age_areas,'age_schools':age_schools,'games':games,'growth':growth,'areas':areas,'schools':schools,'catchment':areas,'school_totals':schools,'players_by_age':players_by_age,'juvenile_gender':juvenile_gender,'senior_adult_non_playing_count':senior_adult_non_playing_count,'senior_adult_non_playing_members':senior_adult_non_playing,'senior_adult_ladies_count':senior_adult_ladies_count,'senior_adult_ladies_members':senior_adult_ladies,'senior_adult_mens_count':senior_adult_mens_count,'senior_adult_mens_members':senior_adult_mens,'upcoming_events':events,'coaching':coaching,'warnings':warnings,'imported_at':datetime.now().isoformat(timespec='seconds')}


def load_sync_status():
 try:
  with open(SYNC_STATUS_FILE,encoding='utf8') as f:return json.load(f)
 except (OSError,json.JSONDecodeError):return {}

def save_sync_status(status):
 tmp=SYNC_STATUS_FILE+'.tmp'
 with open(tmp,'w',encoding='utf8') as f:json.dump(status,f,indent=2,ensure_ascii=False)
 os.replace(tmp,SYNC_STATUS_FILE)

def google_credentials():
 raw=os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON','').strip()
 if not raw:raise RuntimeError('GOOGLE_SERVICE_ACCOUNT_JSON is not configured')
 try:info=json.loads(raw)
 except json.JSONDecodeError as ex:raise RuntimeError('GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON') from ex
 from google.oauth2 import service_account
 return service_account.Credentials.from_service_account_info(
  info,scopes=['https://www.googleapis.com/auth/drive'])

def load_google_oauth_token():
 try:
  with open(GOOGLE_OAUTH_TOKEN_FILE,encoding='utf8') as f:return json.load(f)
 except (OSError,json.JSONDecodeError):return {}

def save_google_oauth_token(token):
 tmp=GOOGLE_OAUTH_TOKEN_FILE+'.tmp'
 with open(tmp,'w',encoding='utf8') as f:json.dump(token,f,indent=2)
 os.replace(tmp,GOOGLE_OAUTH_TOKEN_FILE)

def google_oauth_access_token():
 import requests
 token=load_google_oauth_token();refresh=token.get('refresh_token','')
 if not refresh:raise RuntimeError('Google Drive is not connected. Open Compliance and click Connect Google Drive first.')
 if not GOOGLE_OAUTH_CLIENT_ID or not GOOGLE_OAUTH_CLIENT_SECRET:raise RuntimeError('Google OAuth client ID/secret are not configured in Render.')
 r=requests.post('https://oauth2.googleapis.com/token',data={'client_id':GOOGLE_OAUTH_CLIENT_ID,'client_secret':GOOGLE_OAUTH_CLIENT_SECRET,'refresh_token':refresh,'grant_type':'refresh_token'},timeout=30)
 if r.status_code!=200:raise RuntimeError(f'Google OAuth refresh failed ({r.status_code}): {(r.text or "")[:300]}')
 return r.json().get('access_token','')

def google_upload_garda_form(filename,data,coach_name):
 import requests
 access=google_oauth_access_token()
 safe_coach=re.sub(r'[^A-Za-z0-9 ._\-]', '', str(coach_name or '')).strip() or 'Coach'
 ext=os.path.splitext(filename)[1].lower();stamp=datetime.now().strftime('%Y%m%d_%H%M%S');drive_name=f'{safe_coach} - Garda Vetting - {stamp}{ext}'
 metadata={'name':drive_name,'parents':[GARDA_VETTING_FOLDER_ID]};boundary='eg_'+secrets.token_hex(12)
 body=(f'--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n'+json.dumps(metadata)+f'\r\n--{boundary}\r\nContent-Type: application/octet-stream\r\n\r\n').encode()+data+f'\r\n--{boundary}--\r\n'.encode()
 r=requests.post('https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&fields=id,name,webViewLink',data=body,headers={'Authorization':'Bearer '+access,'Content-Type':f'multipart/related; boundary={boundary}'},timeout=60)
 if r.status_code not in (200,201):raise RuntimeError(f'Google Drive upload failed ({r.status_code}): {(r.text or "")[:300]}')
 return r.json()

def google_export_xlsx(file_id,destination):
 from google.auth.transport.requests import AuthorizedSession
 creds=google_credentials();session=AuthorizedSession(creds)
 url=f'https://www.googleapis.com/drive/v3/files/{file_id}/export'
 r=session.get(url,params={'mimeType':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'},timeout=60)
 if r.status_code!=200:
  detail=(r.text or '')[:300]
  raise RuntimeError(f'Google Drive export failed ({r.status_code}): {detail}')
 with open(destination,'wb') as f:f.write(r.content)
 return len(r.content)

def activate_demographics_from_xlsx(path):
 global DEMO,COACHING
 parsed=parse_demographics_xlsx(path)  # validate completely before replacing live data
 integrated=parsed.pop('coaching',None)
 hist=os.path.join(DATA_DIR,'demographics_history');os.makedirs(hist,exist_ok=True)
 if os.path.exists(DEMO_FILE):
  shutil.copy2(DEMO_FILE,os.path.join(hist,'demographics_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.json'))
 tmp=DEMO_FILE+'.tmp'
 with open(tmp,'w',encoding='utf8') as f:json.dump(parsed,f,indent=2,ensure_ascii=False)
 os.replace(tmp,DEMO_FILE)
 if integrated:
  ctmp=COACH_FILE+'.tmp'
  with open(ctmp,'w',encoding='utf8') as f:json.dump(integrated,f,indent=2,ensure_ascii=False)
  os.replace(ctmp,COACH_FILE)
 DEMO=load_demo();COACHING=load_coaching()
 return {'juvenile_members':sum(DEMO.get('age_totals',{}).values()),
         'senior_mens':DEMO.get('senior_adult_mens_count',0),
         'senior_ladies':DEMO.get('senior_adult_ladies_count',0),
         'senior_non_playing':DEMO.get('senior_adult_non_playing_count',0)}

def session_sync_key(x):
 def gv(k,default=''):
  try:return x[k] if x[k] is not None else default
  except (KeyError,TypeError,IndexError):return x.get(k,default) if hasattr(x,'get') else default
 vals=[gv('date'),gv('school'),gv('coach'),gv('start'),gv('end'),
       gv('class_group',gv('group')),gv('title',gv('session'))]
 return '|'.join(' '.join(str(v or '').strip().lower().split()) for v in vals)

def activate_schools_from_xlsx(path):
 global GPO_COSTS
 sessions=parse_schools_xlsx(path)  # validate before touching the live schedule
 gpo=parse_gpo_costs_xlsx(path)
 c=dbc()
 try:
  # Preserve operational updates made in the dashboard. Google owns timetable
  # fields; the dashboard owns actual_status, attendance, notes and updated_at.
  locked={}
  for old in c.execute('select * from sessions').fetchall():
   if old['updated_at'] or old['attendance'] is not None or (old['notes'] or '').strip() or old['actual_status']!=old['planned_status']:
    locked[session_sync_key(old)]=(old['actual_status'],old['attendance'],old['notes'],old['updated_at'])
  c.execute('begin')
  c.execute('delete from sessions')
  for s in sessions:
   keep=locked.get(session_sync_key(s))
   actual,attendance,notes,updated=(keep if keep else (s['status'],None,None,None))
   c.execute('insert into sessions(id,date,day,school,coach,title,start,end,class_group,age_group,planned_status,actual_status,attendance,notes,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
    (s['id'],s['date'],s['day'],s['school'],s['coach'],s['session'],s['start'],s['end'],s['group'],s['age'],s['status'],actual,attendance,notes,updated))
  c.commit()
 except:
  c.rollback();raise
 finally:c.close()
 shutil.copy2(path,os.path.join(DATA_DIR,'schools_schedule_current.xlsx'))
 tmp=GPO_COST_FILE+'.tmp'
 with open(tmp,'w',encoding='utf8') as f:json.dump(gpo,f,indent=2,ensure_ascii=False)
 os.replace(tmp,GPO_COST_FILE);GPO_COSTS=load_gpo_costs()
 return {'sessions':len(sessions),'gpo_costs':{k:v.get('total',0) for k,v in GPO_COSTS.get('years',{}).items()}}

def sync_google_sources():
 if not GOOGLE_SYNC_ENABLED:return {'enabled':False}
 if not SYNC_LOCK.acquire(blocking=False):return {'enabled':True,'skipped':'sync already running'}
 status=load_sync_status()
 status['enabled']=True;status['last_attempt']=datetime.now().isoformat(timespec='seconds')
 status['interval_minutes']=GOOGLE_SYNC_MINUTES
 try:
  with tempfile.TemporaryDirectory(prefix='eg_google_sync_') as td:
   demo_path=os.path.join(td,'demographics.xlsx')
   schools_path=os.path.join(td,'schools.xlsx')
   # Each feed is independent: one failed source never prevents the other retaining
   # its last-known-good data.
   try:
    size=google_export_xlsx(GOOGLE_DEMOGRAPHICS_SHEET_ID,demo_path)
    summary=activate_demographics_from_xlsx(demo_path)
    status['demographics']={'ok':True,'last_success':datetime.now().isoformat(timespec='seconds'),
     'bytes':size,'summary':summary,'error':None}
   except Exception as ex:
    old=status.get('demographics',{})
    status['demographics']={'ok':False,'last_success':old.get('last_success'),
     'summary':old.get('summary'),'error':str(ex)}
   try:
    size=google_export_xlsx(GOOGLE_SCHOOLS_SHEET_ID,schools_path)
    summary=activate_schools_from_xlsx(schools_path)
    status['schools']={'ok':True,'last_success':datetime.now().isoformat(timespec='seconds'),
     'bytes':size,'summary':summary,'error':None}
   except Exception as ex:
    old=status.get('schools',{})
    status['schools']={'ok':False,'last_success':old.get('last_success'),
     'summary':old.get('summary'),'error':str(ex)}
   # openpyxl read-only workbooks can retain ZipFile handles briefly on Windows.
   # Force finalisation before TemporaryDirectory removes the downloaded XLSX files.
   gc.collect()
  save_sync_status(status)
  return status
 finally:
  SYNC_LOCK.release()

def google_sync_loop():
 # First sync shortly after startup, then repeat at the configured interval.
 time.sleep(3)
 while True:
  try:
   st=sync_google_sources()
   d=st.get('demographics',{});s=st.get('schools',{})
   print('Google sync:', 'demographics OK' if d.get('ok') else 'demographics FAILED',
         '|','schools OK' if s.get('ok') else 'schools FAILED')
   if s.get('ok'):print('GPO totals synced:',s.get('summary',{}).get('gpo_costs',{}))
   if d.get('error'):print('Demographics sync error:',d['error'])
   if s.get('error'):print('Schools sync error:',s['error'])
  except Exception as ex:
   print('Google sync unexpected error:',ex)
  time.sleep(GOOGLE_SYNC_MINUTES*60)

def dbc(): c=sqlite3.connect(DB);c.row_factory=sqlite3.Row;return c
def hp(p,s=None):
 s=s or secrets.token_bytes(16);return s.hex()+'$'+hashlib.pbkdf2_hmac('sha256',p.encode(),s,210000).hex()
def okpw(p,x):
 try:s,h=x.split('$');return hmac.compare_digest(hp(p,bytes.fromhex(s)).split('$')[1],h)
 except:return False
def init():
 c=dbc();c.executescript("""CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,name TEXT,email TEXT UNIQUE,password TEXT,role TEXT,coach_name TEXT,active INTEGER DEFAULT 1);CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,date TEXT,day TEXT,school TEXT,coach TEXT,title TEXT,start TEXT,end TEXT,class_group TEXT,age_group TEXT,planned_status TEXT,actual_status TEXT DEFAULT 'Scheduled',attendance INTEGER,notes TEXT,updated_at TEXT);CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,ts TEXT,user_email TEXT,action TEXT,session_id TEXT,detail TEXT);CREATE TABLE IF NOT EXISTS garda_forms(coach_key TEXT PRIMARY KEY,coach_name TEXT,drive_file_id TEXT,drive_name TEXT,web_view_link TEXT,uploaded_at TEXT);""")
 if c.execute('select count(*) from sessions').fetchone()[0]==0:
  data_path=os.path.join(BASE,'data.js')
  if os.path.exists(data_path):
   t=open(data_path,encoding='utf8').read();m=re.search(r'const DATA=(.*);\s*$',t,re.S)
  else:
   m=None
  seed=json.loads(m.group(1)) if m else []
  if isinstance(seed,dict): seed=seed.get('sessions',seed.get('schedule',[]))
  for s in seed:
   if not isinstance(s,dict): continue
   sid=s.get('id')
   if sid is None: continue
   c.execute('insert into sessions(id,date,day,school,coach,title,start,end,class_group,age_group,planned_status) values(?,?,?,?,?,?,?,?,?,?,?)',(sid,s.get('date',''),s.get('day',''),s.get('school',''),s.get('coach',''),s.get('session',s.get('title','')),s.get('start',''),s.get('end',''),s.get('group',s.get('class_group','')),s.get('age',s.get('age_group','')),str(s.get('status',s.get('planned_status',''))).strip()))
 c.commit();c.close()
def e(x):return html.escape(str(x or ''))
def fd(x):
 try:return datetime.strptime(x,'%Y-%m-%d').strftime('%a %d %b %Y')
 except:return x

CHART_COLORS=['#13A866','#2F80ED','#F2B720','#8B5CF6','#F06B5B','#19A7A0','#EC6FB0','#5B8DEF']
def svg_bar_chart(data,height=220):
 items=[(str(k),int(v)) for k,v in data.items()]
 if not items:return '<div class="chart-empty">No data available</div>'
 w=720;h=height;ml=42;mr=18;mt=28;mb=42;pw=w-ml-mr;ph=h-mt-mb;mx=max(v for _,v in items) or 1;n=len(items);gap=10;bw=max(12,(pw-gap*(n+1))/n)
 grid=''.join(f'<line x1="{ml}" y1="{mt+ph*i/4:.1f}" x2="{w-mr}" y2="{mt+ph*i/4:.1f}" stroke="#e8edf2" stroke-width="1"/>' for i in range(5))
 bars=[]
 for i,(k,v) in enumerate(items):
  bh=ph*v/mx;x=ml+gap+i*(bw+gap);y=mt+ph-bh;c=CHART_COLORS[i%len(CHART_COLORS)]
  bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="7" fill="{c}"/><text x="{x+bw/2:.1f}" y="{max(15,y-7):.1f}" text-anchor="middle" class="cv">{v}</text><text x="{x+bw/2:.1f}" y="{h-13}" text-anchor="middle" class="cl">{e(k)}</text>')
 return f'<div class="svgchart"><svg viewBox="0 0 {w} {h}" role="img">{grid}{"".join(bars)}</svg></div>'
def svg_line_area(data,height=230):
 items=[(str(k),int(v)) for k,v in data.items()]
 if not items:return '<div class="chart-empty">No data available</div>'
 w=720;h=height;ml=42;mr=20;mt=28;mb=38;pw=w-ml-mr;ph=h-mt-mb;mx=max(v for _,v in items) or 1;mn=min(v for _,v in items);base=max(0,mn-(mx-mn)*.35);rng=max(1,mx-base)
 pts=[]
 for i,(k,v) in enumerate(items):
  x=ml+(pw*i/(len(items)-1) if len(items)>1 else pw/2);y=mt+ph-(v-base)*ph/rng;pts.append((x,y,k,v))
 grid=''.join(f'<line x1="{ml}" y1="{mt+ph*i/4:.1f}" x2="{w-mr}" y2="{mt+ph*i/4:.1f}" stroke="#e8edf2" stroke-width="1"/>' for i in range(5))
 path=' '.join(('M' if i==0 else 'L')+f' {x:.1f} {y:.1f}' for i,(x,y,_,_) in enumerate(pts));area=path+f' L {pts[-1][0]:.1f} {mt+ph:.1f} L {pts[0][0]:.1f} {mt+ph:.1f} Z'
 labels=''.join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#fff" stroke="#13A866" stroke-width="3"/><text x="{x:.1f}" y="{max(15,y-10):.1f}" text-anchor="middle" class="cv">{v}</text><text x="{x:.1f}" y="{h-12}" text-anchor="middle" class="cl">{e(k)}</text>' for x,y,k,v in pts)
 return f'<div class="svgchart"><svg viewBox="0 0 {w} {h}"><defs><linearGradient id="ga" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#13A866" stop-opacity=".30"/><stop offset="1" stop-color="#13A866" stop-opacity=".02"/></linearGradient></defs>{grid}<path d="{area}" fill="url(#ga)"/><path d="{path}" fill="none" stroke="#13A866" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>{labels}</svg></div>'
def donut_chart(data,center='',subtitle=''):
 items=[(str(k),int(v)) for k,v in data.items() if int(v)>0];total=sum(v for _,v in items)
 if not total:return '<div class="chart-empty">No data available</div>'
 acc=0;stops=[]
 for i,(k,v) in enumerate(items):
  a=acc*100/total;acc+=v;b=acc*100/total;stops.append(f'{CHART_COLORS[i%len(CHART_COLORS)]} {a:.2f}% {b:.2f}%')
 legend=''.join(f'<span><i style="background:{CHART_COLORS[i%len(CHART_COLORS)]}"></i>{e(k)} <b>{v}</b></span>' for i,(k,v) in enumerate(items))
 return f'<div class="donut-wrap"><div class="donut-pro" style="background:conic-gradient({",".join(stops)})"><div><strong>{e(center or str(total))}</strong><small>{e(subtitle)}</small></div></div><div class="chart-legend">{legend}</div></div>'
def pie_chart(data):
 items=[(str(k),int(v)) for k,v in data.items() if int(v)>0];total=sum(v for _,v in items)
 if not total:return '<div class="chart-empty">No data available</div>'
 import math
 cx=135;cy=115;r=92;start=-90;parts=[];legend=[]
 for i,(k,v) in enumerate(items):
  sweep=360*v/total;end=start+sweep
  x1=cx+r*math.cos(math.radians(start));y1=cy+r*math.sin(math.radians(start))
  x2=cx+r*math.cos(math.radians(end));y2=cy+r*math.sin(math.radians(end))
  large=1 if sweep>180 else 0;c=CHART_COLORS[i%len(CHART_COLORS)]
  parts.append(f'<path d="M {cx} {cy} L {x1:.2f} {y1:.2f} A {r} {r} 0 {large} 1 {x2:.2f} {y2:.2f} Z" fill="{c}" stroke="#fff" stroke-width="2"/>')
  mid=start+sweep/2;lr=r*.66;lx=cx+lr*math.cos(math.radians(mid));ly=cy+lr*math.sin(math.radians(mid));pct=round(v*100/total)
  if sweep>=16:parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" dominant-baseline="middle" fill="#fff" font-size="13" font-weight="800">{pct}%</text>')
  legend.append(f'<span><i style="background:{c}"></i>{e(k)} <b>{pct}%</b></span>')
  start=end
 return f'<div class="pie-layout"><svg viewBox="0 0 270 230" role="img">{"".join(parts)}</svg><div class="chart-legend">{"".join(legend)}</div></div>'

def compliance_status_chart(data,rate):
 items=[(k,int(v)) for k,v in data.items() if int(v)>0]
 total=sum(v for _,v in items) or 1
 colors={'Compliant':'#07844b','Pending':'#F2B720','Expired':'#ff3b30','Not Required':'#98A2B3'}
 acc=0;stops=[]
 for k,v in items:
  a=acc*100/total;acc+=v;b=acc*100/total;stops.append(f'{colors.get(k,"#98A2B3")} {a:.2f}% {b:.2f}%')
 legend=''.join(f'<span><i style="background:{colors.get(k,"#98A2B3")}"></i>{e(k)} <b>{v}</b></span>' for k,v in data.items())
 return f'<div class="compliance-layout"><div class="compliance-ring" style="background:conic-gradient({",".join(stops)})"><div><strong>{int(rate)}%</strong><small>Compliant</small></div></div><div class="chart-legend">{legend}</div></div>'

def hbar_chart(data):
 items=[(str(k),int(v)) for k,v in data.items()];mx=max([v for _,v in items] or [1])
 return '<div class="hbars qual-bars">'+''.join(f'<div class="hbar"><span>{e(k)}</span><div><i style="width:{v*100/mx:.1f}%;background:linear-gradient(90deg,{CHART_COLORS[i%len(CHART_COLORS)]},{CHART_COLORS[(i+1)%len(CHART_COLORS)]})"></i></div><b>{v}</b></div>' for i,(k,v) in enumerate(items))+'</div>'


def adult_members_drilldown(group):
 mapping={
  'mens':('Senior Adult Mens Members','senior_adult_mens_members'),
  'ladies':('Senior Adult Ladies Members','senior_adult_ladies_members'),
  'non-playing':('Senior Adult Non-Playing Members','senior_adult_non_playing_members'),
 }
 if group not in mapping:return ''
 title,key=mapping[group]
 members=DEMO.get(key,[]) or []
 rows=''.join(f'<tr><td>{i}</td><td>{e(name)}</td></tr>' for i,name in enumerate(members,1))
 if not rows:rows='<tr><td colspan="2">No members found in the latest demographics upload.</td></tr>'
 return f"""<div class="card">
 <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap">
  <div><h2 style="margin:0">{title}</h2><small>{len(members)} members from the latest demographics spreadsheet</small></div>
  <a class="btn" href="/">← Back to Club Overview</a>
 </div>
 <div class="tw" style="margin-top:16px"><table><thead><tr><th>No.</th><th>Member Name</th></tr></thead><tbody>{rows}</tbody></table></div>
 </div>"""

def page(title,b,u=None):
 nav=''
 if u:
  nav=f'''<aside class="sidebar"><div class="brand"><img src="/club-jersey.png" alt="Eastern Gaels jersey"></div><nav class="side-nav"><a href="/" class="nav-home"><i><svg viewBox="0 0 24 24"><path d="M3 11.5 12 4l9 7.5M5.5 10.5V20h13v-9.5M9.5 20v-6h5v6"/></svg></i><span>Club Overview</span></a><div class="nav-label">CLUB</div><a href="/schedule"><i><svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4M17 3v4M3 10h18M8 14h2M14 14h2M8 17h2M14 17h2"/></svg></i><span>Schools Schedule</span></a><a href="/demographics"><i><svg viewBox="0 0 24 24"><circle cx="9" cy="8" r="3"/><circle cx="17" cy="9" r="2.5"/><path d="M3.5 20c.4-4 2.3-6 5.5-6s5.1 2 5.5 6M14 15c3.8-.7 6 1.1 6.5 5"/></svg></i><span>Club Demographics</span></a><a href="/coaching-team"><i><svg viewBox="0 0 24 24"><circle cx="12" cy="7" r="3"/><path d="M6 21v-2c0-4 2-6 6-6s6 2 6 6v2M17.5 4.5l1 1 2-2"/></svg></i><span>Coaches &amp; Teams</span></a><a href="/compliance"><i><svg viewBox="0 0 24 24"><path d="M12 3 20 6v6c0 5-3.2 8-8 9-4.8-1-8-4-8-9V6l8-3Zm-3.5 9 2.2 2.2 4.8-5"/></svg></i><span>Compliance</span></a><a href="/courses"><i><svg viewBox="0 0 24 24"><path d="m3 7 9-4 9 4-9 4-9-4ZM6 9.5V15c3 2.5 9 2.5 12 0V9.5M21 7v7"/></svg></i><span>Courses</span></a><a href="/games"><i><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="m12 7 3 2.2-1.1 3.5h-3.8L9 9.2 12 7ZM5 10l4 1m10-1-4 1M8 19l2-6m6 6-2-6"/></svg></i><span>Games Played</span></a><a href="/membership"><i><svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="3"/><circle cx="8.5" cy="11" r="2.2"/><path d="M5.5 16c.5-2 1.5-3 3-3s2.5 1 3 3M14 10h4M14 14h4"/></svg></i><span>Membership</span></a><div class="nav-label">MANAGE</div><a href="/reports"><i><svg viewBox="0 0 24 24"><path d="M5 21V10M12 21V4M19 21v-7M3 21h18"/></svg></i><span>Reports</span></a><a href="/admin"><i><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.4 1a8 8 0 0 0-1.7-1L14.5 3h-5L9 6.1a8 8 0 0 0-1.7 1l-2.4-1-2 3.4 2 1.5a7 7 0 0 0 0 2l-2 1.5 2 3.4 2.4-1a8 8 0 0 0 1.7 1l.5 3.1h5l.5-3.1a8 8 0 0 0 1.7-1l2.4 1 2-3.4-2-1.5a7 7 0 0 0 .1-1Z"/></svg></i><span>Admin</span></a></nav><div class="side-bottom"><div class="avatar">{e(u['name'][:1])}</div><div><div class="user">{e(u['name'])}</div><a href="/logout">Sign out</a></div></div><div class="designer-footer"><img src="/simple-analytics.png" alt="Simple Analytics"><strong>Presenting Data Analytics Simply.</strong><span>Designed by Jude McNabb</span><span>Drogheda, Meath</span><span>Contact 087-9217352</span></div></aside>'''
 return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)} · Eastern Gaels</title><style>
:root{{--green:#0b4b2d;--green2:#11643b;--green3:#1f7a4b;--gold:#f3b61f;--blue:#4d8ee8;--purple:#9b6ee8;--coral:#ef766e;--teal:#25a6a1;--ink:#15241c;--muted:#738078;--bg:#f2f6fb;--line:#e4ebf2;--side:258px;--navy:#0e1b38;--cyan:#18b9b1;--pink:#e85ca4}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{font-family:"Segoe UI Variable","Aptos",Inter,"Segoe UI",system-ui,-apple-system,sans-serif;margin:0;background:var(--bg);color:var(--ink);font-size:14px}}.sidebar{{position:fixed;inset:0 auto 0 0;width:var(--side);background:radial-gradient(circle at 50% 10%,#08713e 0,#064b2d 28%,#03351f 70%,#022b1a 100%);color:white;padding:22px 15px 16px;display:flex;flex-direction:column;z-index:20;box-shadow:8px 0 30px #092d1b18}}.brand{{display:flex;align-items:center;gap:12px;padding:0 8px 18px;border-bottom:1px solid #ffffff1f}}.brand img{{width:88px;height:104px;border-radius:12px;object-fit:contain;background:white;border:1px solid #ffffff38;box-shadow:0 3px 12px #0003;padding:3px}}.brand strong{{display:block;letter-spacing:.9px;font-size:14px;font-weight:850}}.brand small{{display:block;color:#b9d5c4;margin-top:3px;font-size:11px}}.side-nav{{display:flex;flex-direction:column;gap:3px;margin-top:14px;flex:1 1 auto;min-height:0;overflow-y:auto;overflow-x:hidden;padding-bottom:8px;scrollbar-width:thin;scrollbar-color:#ffffff35 transparent}}.side-nav a{{color:#eaf5ee;text-decoration:none;padding:10px 11px;border-radius:10px;font-weight:650;display:flex;gap:11px;align-items:center;transition:.18s}}.side-nav a:hover{{background:#ffffff13;transform:translateX(2px)}}.side-nav a i{{font-style:normal;width:34px;height:34px;display:grid;place-items:center;color:#dff7e8;background:linear-gradient(145deg,#ffffff18,#ffffff08);border:1px solid #ffffff18;border-radius:10px;box-shadow:inset 0 1px 0 #ffffff18,0 4px 10px #001a0e26;transition:.18s ease;flex:0 0 34px}}.side-nav a i svg{{width:19px;height:19px;fill:none;stroke:currentColor;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round}}.side-nav a:hover i{{color:#fff;background:#ffffff20;border-color:#ffffff2e;transform:translateY(-1px) scale(1.04)}}.side-nav .nav-home i{{color:#17351f;background:linear-gradient(145deg,#ffd65a,#f3b61f);border-color:#ffe28a}}.side-nav .nav-home{{background:#ffffff12;border-left:3px solid var(--gold)}}.nav-label{{font-size:9px;letter-spacing:1.6px;color:#8fb59e;margin:16px 11px 5px;font-weight:850}}.side-bottom{{flex:0 0 auto;margin-top:8px;border-top:1px solid #ffffff1f;padding:13px 8px 0;display:flex;align-items:center;gap:10px}}.avatar{{width:34px;height:34px;border-radius:50%;background:#ffffff18;display:grid;place-items:center;font-weight:850;color:var(--gold)}}.side-bottom .user{{font-weight:750;font-size:12px}}.side-bottom a{{color:#bcd4c5;text-decoration:none;font-size:11px}}.designer-footer{{flex:0 0 auto;border-top:1px solid #ffffff1f;margin-top:12px;padding:12px 8px 10px;text-align:center;color:#bcd4c5;background:#022f1dcc;border-radius:0 0 10px 10px}}.designer-footer img{{display:block;width:100%;max-width:150px;height:58px;object-fit:contain;object-position:center;margin:0 auto 9px;border-radius:8px;border:1px solid #ffffff20;background:#fff}}.designer-footer strong{{display:block;color:#fff;font-size:10px;line-height:1.35;margin-bottom:5px}}.designer-footer span{{display:block;font-size:9px;line-height:1.45}}header{{margin-left:var(--side);background:#ffffffea;backdrop-filter:blur(14px);border-bottom:1px solid var(--line);padding:17px 28px;position:sticky;top:0;z-index:10;display:flex;align-items:center;justify-content:space-between}}header h1{{margin:0;color:var(--navy);font-size:21px;letter-spacing:-.4px}}header small{{color:var(--muted);font-weight:600}}main{{margin-left:var(--side);padding:27px 30px 50px;max-width:1580px}}h2{{font-size:22px;letter-spacing:-.5px;margin:4px 0 5px}}h3{{font-size:15px;margin:0 0 13px;color:#213a2a}}.eyebrow{{font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:var(--green3);font-weight:850}}.hero{{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;margin:3px 0 22px}}.hero h2{{font-size:28px;margin:4px 0}}.hero p{{margin:0;color:var(--muted)}}.card{{background:linear-gradient(180deg,#ffffff 0%,#fbfdff 100%);padding:19px;border-radius:16px;margin:14px 0;box-shadow:0 8px 24px #173b2510;border:1px solid #e7edf3}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}}.grid2{{display:grid;grid-template-columns:1.25fr 1fr;gap:14px}}.overview-charts{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin:14px 0}}.overview-charts .card{{min-width:0;padding:16px}}.overview-charts .section-title h3{{font-size:16px}}.overview-charts .card{{box-shadow:0 12px 28px #183b2a14,0 2px 5px #10251a0d;transform:translateZ(0)}}.overview-charts .svgchart svg{{filter:drop-shadow(0 7px 7px rgba(20,50,35,.12))}}.overview-charts .svgchart rect{{filter:drop-shadow(3px 5px 3px rgba(14,42,28,.18));transition:.18s ease;transform-box:fill-box;transform-origin:center}}.overview-charts .svgchart rect:hover{{filter:drop-shadow(4px 7px 4px rgba(14,42,28,.25));transform:translateY(-2px)}}.pie-layout svg{{filter:drop-shadow(7px 10px 7px rgba(12,43,28,.20));transform:perspective(700px) rotateX(7deg);transform-origin:center}}.pie-layout svg path{{filter:drop-shadow(1px 2px 1px rgba(0,0,0,.15))}}.compliance-ring{{box-shadow:0 14px 20px rgba(7,66,40,.20),inset 0 2px 3px rgba(255,255,255,.6),inset 0 -5px 8px rgba(0,0,0,.10)!important;transform:perspective(700px) rotateX(5deg)}}.compliance-ring>div{{box-shadow:inset 0 3px 5px rgba(15,45,30,.08),0 2px 5px rgba(255,255,255,.65)!important}}.qual-bars .hbar>div{{box-shadow:inset 0 2px 2px rgba(255,255,255,.75),0 4px 7px rgba(18,45,32,.10)}}.qual-bars .hbar i{{box-shadow:inset 0 3px 3px rgba(255,255,255,.28),inset 0 -3px 4px rgba(0,0,0,.13),3px 4px 5px rgba(18,45,32,.16)}}.pie-layout{{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(120px,.85fr);align-items:center;gap:8px;min-height:230px}}.pie-layout svg{{width:100%;height:auto;display:block}}.chart-legend{{display:flex;flex-direction:column;gap:10px;font-size:12px}}.chart-legend span{{display:grid;grid-template-columns:12px 1fr auto;align-items:center;gap:7px;white-space:nowrap}}.chart-legend i{{width:11px;height:11px;border-radius:50%;display:block}}.chart-legend b{{color:var(--navy);font-size:12px}}.compliance-layout{{display:grid;grid-template-columns:minmax(150px,1fr) minmax(135px,.85fr);align-items:center;gap:14px;min-height:230px}}.compliance-ring{{width:176px;height:176px;border-radius:50%;display:grid;place-items:center;margin:auto;box-shadow:inset 0 0 0 1px #ffffff}}.compliance-ring>div{{width:104px;height:104px;border-radius:50%;background:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;box-shadow:0 1px 6px #10251a12}}.compliance-ring strong{{font-size:31px;line-height:1;color:var(--navy)}}.compliance-ring small{{font-size:11px;color:#31455d;margin-top:5px}}.qual-bars{{padding-top:8px}}.qual-bars .hbar{{grid-template-columns:100px minmax(120px,1fr) 28px;gap:9px;margin:13px 0}}.qual-bars .hbar>span{{text-align:right;font-size:12px;color:#31415b}}.qual-bars .hbar>div{{height:18px;background:#edf1f6;border-radius:5px;overflow:hidden}}.qual-bars .hbar i{{display:block;height:100%;border-radius:5px}}.qual-bars .hbar>b{{font-size:12px;color:var(--navy)}}@media(max-width:1250px){{.overview-charts{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}@media(max-width:850px){{.overview-charts{{grid-template-columns:1fr}}}}.grid3{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}.kpi-grid{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px}}.kpi-grid .card{{margin:0}}.panel-title{{display:flex;align-items:center;gap:9px;font-weight:850;color:var(--navy)}}.panel-title:before{{content:"";width:28px;height:28px;border-radius:9px;background:linear-gradient(135deg,#e8f8ef,#dff2ff);box-shadow:inset 0 0 0 1px #ffffff}}.stat{{font-size:32px;font-weight:900;color:var(--navy);letter-spacing:-1.2px;line-height:1}}.kpi{{position:relative;overflow:hidden;padding:20px 20px 17px;border:0;box-shadow:0 5px 20px #173b250d}}.kpi:before{{content:'';position:absolute;inset:0 auto 0 0;width:4px;background:var(--accent,var(--green3))}}.kpi:nth-child(2){{--accent:var(--blue)}}.kpi:nth-child(3){{--accent:var(--purple)}}.kpi:nth-child(4){{--accent:var(--gold)}}.kpi:nth-child(5){{--accent:var(--coral)}}.kpi b{{display:block;margin-top:8px;font-size:12px}}.kpi small{{display:block;color:var(--muted);margin-top:3px;font-size:11px}}.metric-icon{{float:right;width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,#dcf8e8,#effcf5);display:grid;place-items:center;color:var(--green);font-weight:900}}.barrow{{display:grid;grid-template-columns:minmax(92px,1.25fr) 3fr 38px;gap:9px;align-items:center;margin:10px 0;font-size:12px}}.barrow b:first-child{{font-weight:650;color:#46554b}}.bartrack{{height:12px;background:#edf1f6;border-radius:999px;overflow:hidden}}.barfill{{height:100%;background:linear-gradient(90deg,#12b76a,#45d38d);border-radius:999px;min-width:2px}}.barrow:nth-child(4n+2) .barfill{{background:linear-gradient(90deg,#2f80ed,#6aa9ff)}}.barrow:nth-child(4n+3) .barfill{{background:linear-gradient(90deg,#7c3aed,#b06cff)}}.barrow:nth-child(4n+4) .barfill{{background:linear-gradient(90deg,#f5a400,#ffd24f)}}.chartlink{{color:inherit;text-decoration:none}}.chartlink .card{{transition:.18s}}.chartlink .card:hover{{transform:translateY(-2px);box-shadow:0 9px 25px #173b2515}}.progress{{height:8px;background:#e9eeea;border-radius:999px;overflow:hidden;margin-top:8px}}.progress span{{display:block;height:100%;background:linear-gradient(90deg,var(--green3),#55b97d)}}.donut{{width:142px;height:142px;border-radius:50%;margin:12px auto;display:grid;place-items:center;background:conic-gradient(var(--green3) 0 var(--done),var(--coral) var(--done) var(--cancel),var(--gold) var(--cancel) var(--closed),#dfe5e0 var(--closed) 100%)}}.donut:after{{content:'';width:86px;height:86px;background:white;border-radius:50%}}.legend{{display:flex;gap:12px;flex-wrap:wrap;font-size:12px}}.dot{{width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:5px;background:var(--green3)}}.muted{{color:var(--muted)}}.session{{border-left:4px solid var(--blue)}}.badge{{display:inline-block;padding:4px 9px;border-radius:999px;background:#e8f4ec;font-size:11px;font-weight:750}}.Completed{{background:#def3e6;color:#21643b}}.Cancelled{{background:#fde4e1;color:#9b3833}}.Rescheduled{{background:#fff0ca;color:#7a5900}}.expired,.urgent{{background:#fde4e1;color:#9b3833}}.warning{{background:#fff0ca;color:#7a5900}}.unknown{{background:#edf0f2;color:#59656a}}.valid{{background:#def3e6;color:#21643b}}button,.btn{{display:inline-block;border:0;background:var(--green);color:#fff;padding:10px 14px;border-radius:9px;font-weight:720;text-decoration:none;cursor:pointer;box-shadow:0 2px 8px #0b4b2d18}}button:hover,.btn:hover{{background:var(--green2)}}.secondary{{background:#edf1ee!important;color:#25352a!important;box-shadow:none!important}}input,select,textarea{{width:100%;padding:10px 11px;border:1px solid #ccd7cf;border-radius:9px;font:inherit;background:white}}label{{display:block;font-weight:700;margin:10px 0 5px;font-size:12px}}.row{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.actions{{display:flex;gap:7px;flex-wrap:wrap;margin-top:12px}}table{{width:100%;border-collapse:collapse;background:#fff}}th,td{{padding:11px 10px;border-bottom:1px solid var(--line);text-align:left}}th{{font-size:10px;text-transform:uppercase;letter-spacing:.7px;color:var(--muted);background:#fafbfa}}tr:hover td{{background:#fbfdfb}}.tw{{overflow:auto;border-radius:11px;border:1px solid var(--line)}}.login{{max-width:430px;margin:45px auto}}.quick{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}.quick a{{text-decoration:none;color:inherit;background:white;border:1px solid var(--line);border-radius:12px;padding:15px;transition:.18s}}.quick a:hover{{transform:translateY(-2px);border-color:#bfd3c5}}.quick b{{display:block;color:var(--green);margin-bottom:4px}}.pill{{display:inline-block;border-radius:999px;padding:5px 9px;font-size:10px;font-weight:800;background:#edf7f1;color:var(--green)}}.section-title{{display:flex;align-items:center;justify-content:space-between;margin:24px 0 7px}}.section-title h3{{margin:0;font-size:17px}}.spark{{height:92px;display:flex;align-items:flex-end;gap:8px;padding-top:10px}}.spark span{{flex:1;border-radius:7px 7px 2px 2px;background:linear-gradient(180deg,#4d8ee8,#82b1f0);min-height:8px;position:relative}}.spark span:nth-child(2){{background:linear-gradient(180deg,#9b6ee8,#b99bf0)}}.spark span:nth-child(3){{background:linear-gradient(180deg,#25a6a1,#72c9c4)}}.spark span:nth-child(4){{background:linear-gradient(180deg,#f3b61f,#f7d66f)}}.spark-labels{{display:flex;justify-content:space-around;font-size:10px;color:var(--muted);margin-top:5px}}.alert-list{{display:grid;gap:8px}}.alert-item{{padding:11px 12px;border-radius:10px;background:#fbf3dc;border-left:3px solid var(--gold);font-size:12px}}.alert-item.good{{background:#eaf6ee;border-color:var(--green3)}}
@media(max-width:1200px){{.kpi-grid{{grid-template-columns:repeat(3,1fr)}}}}@media(max-width:1050px){{.grid2,.grid3{{grid-template-columns:1fr}}.quick{{grid-template-columns:1fr 1fr}}}}
@media(max-width:800px){{:root{{--side:76px}}.brand div,.side-nav span,.nav-label,.side-bottom>div:not(.avatar),.designer-footer{{display:none}}.brand{{justify-content:center;padding-left:0;padding-right:0}}.brand img{{width:48px;height:48px}}.side-nav a{{justify-content:center;padding:10px 6px}}.side-nav a i{{width:28px}}header,main{{margin-left:var(--side)}}main{{padding:18px}}.hero{{align-items:flex-start;flex-direction:column}}}}
@media(max-width:650px){{.kpi-grid{{grid-template-columns:1fr 1fr}}}}@media(max-width:520px){{:root{{--side:0px}}.sidebar{{position:relative;width:100%;height:auto;padding:10px 12px;flex-direction:row;align-items:center}}.brand{{border:0;padding:0}}.brand img{{width:42px;height:42px}}.side-nav{{margin:0 0 0 auto;flex-direction:row}}.side-nav a{{display:none}}.side-nav a.nav-home{{display:flex;background:#ffffff12}}.side-bottom{{display:none}}header,main{{margin-left:0}}header{{padding:13px 15px}}main{{padding:14px}}.row,.quick{{grid-template-columns:1fr}}.grid{{grid-template-columns:1fr 1fr}}.kpi{{padding:16px}}.stat{{font-size:26px}}}}

/* ===== Eastern Gaels Executive Sports Dashboard ===== */
:root{{--side:222px;--green:#005b38;--green2:#007347;--green3:#07844b;--gold:#f5b400;--bg:#eef3f7}}
body{{background:linear-gradient(135deg,#eef4f8,#f8fbfd);color:#102038}}
.sidebar{{width:var(--side);padding:12px 12px 16px;background:linear-gradient(180deg,rgba(0,72,44,.93) 0%,rgba(0,58,37,.96) 67%,rgba(0,46,31,.90) 100%),url('/maiden-tower.png') center bottom/auto 42% no-repeat;box-shadow:7px 0 24px rgba(0,45,28,.18)}}
.brand{{height:222px;justify-content:center;align-items:flex-start;padding:0 0 6px;border:0}}
.brand img{{width:190px;height:210px;object-fit:contain;object-position:center top;padding:0;border:0;border-radius:0;background:transparent;box-shadow:none}}
.side-nav{{margin-top:0;gap:2px}}.side-nav a{{border-radius:7px;padding:10px 10px;font-size:13px;font-weight:750}}
.side-nav a.active,.side-nav .nav-home.active{{color:#062e20;background:linear-gradient(180deg,#ffd335,#efae00);border-left:0;box-shadow:0 4px 12px #0002}}
.side-nav a.active i{{color:#075d3d}}.side-nav .nav-home{{background:transparent;border-left:0}}.nav-label{{display:none}}
.side-bottom{{background:#003b28d9;border-radius:9px;padding:10px;margin-top:7px}}
.designer-footer{{background:#003722e8;border-radius:9px;margin-top:8px;padding:9px 7px}}.designer-footer img{{height:42px;margin-bottom:6px}}
header{{height:146px;margin-left:var(--side);padding:20px 30px;position:relative;overflow:hidden;border:0;color:#fff;background:linear-gradient(90deg,rgba(0,68,43,.94) 0%,rgba(0,68,43,.70) 38%,rgba(0,50,32,.20) 68%,rgba(0,43,28,.38) 100%),url('/maiden-tower.png') center 48%/cover no-repeat;box-shadow:0 5px 18px #173b2514}}
.club-head{{display:flex;flex-direction:column;text-shadow:0 2px 8px #001b12aa}}.club-head strong{{font-size:36px;line-height:1;font-weight:950;letter-spacing:-1px}}.club-head span{{font-size:19px;color:#ffc41c;font-weight:850;letter-spacing:4px;margin-top:5px}}.club-head small{{color:#fff;font-size:10px;letter-spacing:3px;margin-top:10px;font-weight:800}}
.head-right{{margin-left:auto;display:flex;align-items:center;gap:24px}}.head-right em{{font-family:"Segoe Script","Brush Script MT",cursive;font-size:25px;font-weight:800;color:#fff;text-shadow:0 2px 7px #003523}}.date-chip{{background:linear-gradient(180deg,#076544,#004b34);padding:12px 17px;border-radius:12px;font-weight:850;box-shadow:0 5px 14px #001d1438;border:1px solid #ffffff28}}
main{{margin-left:var(--side);padding:16px 18px 42px;max-width:none}}.hero{{display:none}}.kpi-grid{{gap:10px}}
.kpi-grid .card{{min-height:116px;border-radius:14px;border:1px solid #dce6eb;box-shadow:0 7px 17px rgba(26,54,43,.12);padding:17px 17px 14px;background:linear-gradient(180deg,#fff,#f9fbfc)}}
.kpi:before{{display:none}}.metric-icon{{float:left;width:58px;height:58px;margin-right:13px;border-radius:11px;background:linear-gradient(145deg,#0ba660,#006a40);color:#fff;box-shadow:inset 0 2px 4px #ffffff55,0 5px 10px #063c2828;font-size:18px}}
.kpi:nth-child(2) .metric-icon{{background:linear-gradient(145deg,#ffc92e,#df9800)}}.kpi:nth-child(3) .metric-icon{{background:linear-gradient(145deg,#2da9f2,#006db5)}}.kpi:nth-child(4) .metric-icon{{background:linear-gradient(145deg,#b249e5,#6c1ab2)}}.kpi:nth-child(5) .metric-icon{{background:linear-gradient(145deg,#54bf68,#07813d)}}
.kpi .stat{{font-size:34px;padding-top:4px}}.kpi b{{font-size:13px;margin-top:6px}}.kpi small{{font-size:10px}}
.overview-charts{{gap:10px;margin:10px 0}}.overview-charts .card{{margin:0;padding:58px 14px 13px;border-radius:13px;position:relative;overflow:hidden;border:1px solid #dce5e9;box-shadow:0 7px 17px rgba(26,54,43,.12);background:#fff}}
.overview-charts .section-title{{position:absolute;left:0;right:0;top:0;height:46px;margin:0;padding:0 16px;background:linear-gradient(180deg,#08724c,#005737);color:#fff;box-shadow:inset 0 1px #ffffff33;display:flex;align-items:center}}
.overview-charts .section-title h3{{color:#fff;font-size:16px;font-weight:850}}.overview-charts .section-title .pill{{background:#ffffff18;color:#fff}}.overview-charts .svgchart rect{{filter:drop-shadow(5px 6px 3px rgba(11,54,35,.20))}}
.pie-layout svg{{filter:drop-shadow(8px 11px 7px rgba(12,43,28,.24));transform:perspective(700px) rotateX(10deg)}}.qual-bars .hbar>div{{height:20px}}.compliance-ring{{width:184px;height:184px}}.compliance-ring>div{{width:108px;height:108px}}
main>.card:last-child{{border-radius:13px;border:1px solid #dce5e9;box-shadow:0 7px 17px rgba(26,54,43,.12);padding:55px 14px 12px;position:relative;overflow:hidden}}
main>.card:last-child>.section-title{{position:absolute;left:0;right:0;top:0;height:43px;margin:0;padding:0 15px;background:linear-gradient(180deg,#08724c,#005737);display:flex;align-items:center}}
main>.card:last-child>.section-title h3{{color:#fff}}main>.card:last-child>.section-title .pill{{background:#ffffff18;color:#fff}}.tw{{border-radius:7px}}th{{background:#dfe7ea;color:#152c26;font-weight:850}}td{{padding:8px 10px}}
@media(max-width:800px){{.brand{{height:74px}}.brand img{{width:62px;height:70px}}header{{height:110px}}.club-head strong{{font-size:25px}}.club-head span{{font-size:13px;letter-spacing:2px}}.club-head small,.head-right em{{display:none}}}}

.overview-title{{display:flex;align-items:end;justify-content:space-between;margin:0 0 10px;padding:0 3px}}
.overview-title small{{font-size:10px;letter-spacing:2px;color:#0a7650;font-weight:900}}
.overview-title h2{{margin:2px 0 0;font-size:23px;color:#12372b}}
.overview-title>span{{font-size:10px;font-weight:800;color:#527166;background:#e4f2eb;border:1px solid #cce3d7;border-radius:999px;padding:6px 10px}}
.kpi-grid .card{{position:relative;overflow:hidden}}
.kpi-grid .card:after{{content:"";position:absolute;right:-20px;bottom:-28px;width:85px;height:85px;border-radius:50%;background:rgba(8,116,73,.055)}}
.overview-charts .card{{min-height:330px}}
.overview-charts .card .svgchart{{padding-top:4px}}
.overview-charts .section-title:before{{content:"";width:8px;height:8px;border-radius:50%;background:#ffc421;margin-right:8px;box-shadow:0 0 0 3px #ffffff1c}}
.overview-charts .section-title h3{{margin-right:auto}}
.overview-charts .section-title{{justify-content:flex-start;gap:5px}}
.overview-charts .section-title .pill{{margin-left:auto}}
.chart-legend span{{font-weight:650;color:#324c43}}
main>.card:last-child>.section-title:before{{content:"";width:8px;height:8px;border-radius:50%;background:#ffc421;margin-right:8px}}

/* ===== V8 Compact Screen + Background Render Fix ===== */
:root{{--side:188px}}
.sidebar{{width:var(--side);padding:8px 9px 12px;background-color:#004c31;background-image:linear-gradient(180deg,rgba(0,74,46,.88) 0%,rgba(0,62,40,.94) 56%,rgba(0,49,32,.76) 100%),url('/maiden-tower.png');background-repeat:no-repeat,no-repeat;background-position:center center,center bottom;background-size:100% 100%,100% auto}}
.brand{{height:164px;padding:0;display:flex;align-items:flex-start;justify-content:center}}.brand img{{width:154px;height:158px;object-fit:contain;object-position:center top;filter:drop-shadow(0 7px 8px rgba(0,0,0,.22))}}
.side-nav a{{padding:7px 8px;font-size:11.5px;line-height:1.15}}.side-nav a i{{width:18px}}.side-bottom{{padding:7px;margin-top:5px}}.designer-footer{{padding:6px;margin-top:5px;font-size:9px}}
header{{margin-left:var(--side);height:108px;padding:14px 22px;background-color:#005538;background-image:linear-gradient(90deg,rgba(0,76,48,.95) 0%,rgba(0,76,48,.73) 43%,rgba(0,54,35,.24) 73%,rgba(0,46,30,.44) 100%),url('/maiden-tower.png');background-repeat:no-repeat,no-repeat;background-position:center center,center 58%;background-size:100% 100%,cover}}
.club-head strong{{font-size:29px}}.club-head span{{font-size:15px;letter-spacing:3px;margin-top:3px}}.club-head small{{font-size:8px;letter-spacing:2.3px;margin-top:7px}}.head-right{{gap:14px}}.head-right em{{font-size:20px}}.date-chip{{padding:9px 12px;font-size:11px}}
main{{margin-left:var(--side);padding:10px 12px 28px}}.overview-title{{margin-bottom:7px}}.overview-title h2{{font-size:19px}}.overview-title small,.overview-title>span{{font-size:8.5px}}
.kpi-grid{{gap:7px}}.kpi-grid .card{{min-height:88px;padding:10px 10px 8px;border-radius:10px}}.metric-icon{{width:43px;height:43px;margin-right:8px;border-radius:9px;font-size:14px}}.kpi .stat{{font-size:27px;padding-top:0}}.kpi b{{font-size:11px;margin-top:3px}}.kpi small{{font-size:8.5px}}
.overview-charts{{gap:7px;margin:7px 0}}.overview-charts .card{{min-height:265px;padding:45px 10px 8px;border-radius:10px}}.overview-charts .section-title{{height:37px;padding:0 11px}}.overview-charts .section-title h3{{font-size:13px}}.overview-charts .section-title .pill{{font-size:9px;padding:4px 7px}}
.pie-layout{{min-height:190px}}.compliance-layout{{min-height:190px}}.compliance-ring{{width:150px;height:150px}}.compliance-ring>div{{width:88px;height:88px}}.compliance-ring strong{{font-size:25px}}.qual-bars .hbar{{margin:9px 0}}.qual-bars .hbar>div{{height:16px}}
main>.card:last-child{{padding:43px 10px 8px;border-radius:10px}}main>.card:last-child>.section-title{{height:35px;padding:0 11px}}td,th{{padding:6px 8px;font-size:10px}}
@media(min-width:1500px){{main{{max-width:1450px;margin-right:auto}}.overview-charts .card{{min-height:280px}}}}
@media(max-width:1050px){{.overview-charts{{grid-template-columns:repeat(2,minmax(0,1fr))}}.kpi-grid{{grid-template-columns:repeat(3,minmax(0,1fr))}}}}
@media(max-width:760px){{:root{{--side:68px}}.brand{{height:70px}}.brand img{{width:62px;height:68px}}.sidebar{{background-size:100% 100%,auto 38%}}.side-nav a{{padding:8px 5px}}.side-nav a span{{display:none}}header{{height:92px;padding:12px 15px}}.club-head strong{{font-size:22px}}.club-head span{{font-size:11px}}.club-head small,.head-right em{{display:none}}.overview-charts{{grid-template-columns:1fr}}.kpi-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}

/* ===== V8 Balanced Scale + Background Graphics Fix ===== */
:root{{--side:205px}}
html,body{{min-height:100%;overflow-x:hidden}}
.sidebar{{
 width:var(--side);padding:9px 10px 12px;
 background-color:#004a31;
 background-image:
   linear-gradient(180deg,rgba(0,67,43,.84) 0%,rgba(0,61,39,.87) 48%,rgba(0,45,30,.58) 100%),
   url('/maiden-tower.png');
 background-repeat:no-repeat,no-repeat;
 background-position:center center,center bottom;
 background-size:100% 100%,auto 58%;
}}
.brand{{height:190px;padding:0;display:flex;justify-content:center;align-items:flex-start}}
.brand img{{width:172px;height:184px;object-fit:contain;object-position:center top;filter:drop-shadow(0 7px 9px rgba(0,0,0,.22))}}
.side-nav{{gap:1px}}.side-nav a{{padding:8px 9px;font-size:12px;min-height:34px}}
.side-bottom{{padding:8px;margin-top:6px;background:rgba(0,54,36,.72)}}
.designer-footer{{padding:7px;margin-top:6px;background:rgba(0,48,32,.74)}}

header{{
 margin-left:var(--side);height:125px;padding:16px 24px;
 background-color:#00553a;
 background-image:
   linear-gradient(90deg,rgba(0,73,46,.92) 0%,rgba(0,72,46,.62) 36%,rgba(0,55,36,.20) 69%,rgba(0,45,30,.48) 100%),
   url('/maiden-tower.png');
 background-repeat:no-repeat,no-repeat;
 background-position:center center,center 52%;
 background-size:100% 100%,cover;
}}
.club-head strong{{font-size:33px}}.club-head span{{font-size:17px;letter-spacing:3.5px;margin-top:4px}}
.club-head small{{font-size:9px;letter-spacing:2.5px;margin-top:8px}}
.head-right em{{font-size:23px}}.date-chip{{padding:10px 14px;font-size:11px}}

main{{margin-left:var(--side);padding:12px 14px 30px;max-width:none}}
.overview-title{{margin:0 0 8px}}.overview-title h2{{font-size:21px}}.overview-title small,.overview-title>span{{font-size:9px}}
.kpi-grid{{gap:8px}}.kpi-grid .card{{min-height:98px;padding:12px 12px 10px}}
.metric-icon{{width:48px;height:48px;margin-right:9px;font-size:15px}}.kpi .stat{{font-size:30px}}.kpi b{{font-size:11px}}.kpi small{{font-size:8.5px}}
.overview-charts{{gap:8px;margin:8px 0;grid-template-columns:repeat(3,minmax(0,1fr))}}
.overview-charts .card{{min-height:285px;padding:47px 11px 9px}}
.overview-charts .section-title{{height:39px;padding:0 12px}}.overview-charts .section-title h3{{font-size:14px}}.overview-charts .section-title .pill{{font-size:9px}}
.overview-charts svg{{max-height:225px}}
.pie-layout,.compliance-layout{{min-height:210px}}.compliance-ring{{width:158px;height:158px}}.compliance-ring>div{{width:92px;height:92px}}
.qual-bars .hbar{{margin:9px 0}}.qual-bars .hbar>div{{height:17px}}
main>.card:last-child{{padding:45px 11px 9px;min-height:120px}}
main>.card:last-child>.section-title{{height:37px;padding:0 12px}}
td,th{{padding:6px 8px;font-size:10px}}

@media(max-width:1250px){{
 :root{{--side:185px}}
 .brand{{height:165px}}.brand img{{width:150px;height:160px}}
 header{{height:110px}}
 .overview-charts .card{{min-height:255px}}
}}
@media(max-width:900px){{
 :root{{--side:70px}}.brand{{height:74px}}.brand img{{width:64px;height:70px}}
 .side-nav a span{{display:none}}
 header{{height:96px;padding:12px 15px}}
 .club-head strong{{font-size:23px}}.club-head span{{font-size:11px}}.club-head small,.head-right em{{display:none}}
 .overview-charts{{grid-template-columns:repeat(2,minmax(0,1fr))}}
 .kpi-grid{{grid-template-columns:repeat(3,minmax(0,1fr))}}
}}

.course-link-card{{position:relative;overflow:hidden;background:linear-gradient(145deg,#ffffff,#f2f8f5);border:1px solid #d5e7de}}
.course-link-card:after{{content:"";position:absolute;right:-34px;bottom:-44px;width:140px;height:140px;border-radius:50%;background:rgba(0,105,66,.07)}}
.course-badge{{display:inline-block;margin-bottom:10px;padding:5px 8px;border-radius:999px;background:#e4f3eb;color:#00633e;font-size:9px;font-weight:900;letter-spacing:1px}}
.course-link-card h3{{font-size:18px;color:#12382c;margin:2px 0 7px}}
.course-link-btn{{display:inline-flex;align-items:center;margin-top:12px;padding:10px 14px;border-radius:8px;background:linear-gradient(180deg,#08764e,#005b3b);color:#fff!important;text-decoration:none;font-weight:850;box-shadow:0 5px 12px rgba(0,75,47,.18)}}
.course-link-btn:hover{{transform:translateY(-1px);box-shadow:0 7px 15px rgba(0,75,47,.24)}}

.native-course-card{{overflow:hidden;background:linear-gradient(145deg,#fff,#f3f8f5)}}
.native-course-card h3{{font-size:18px;color:#12382c;margin:2px 0 10px}}
.course-preview{{border:1px solid #d5e5dd;border-radius:10px;background:#fff;padding:13px 14px}}
.course-preview>strong{{display:block;font-size:16px;color:#073f2d;margin-bottom:4px}}
.foundation-tag{{display:inline-block;padding:3px 7px;border-radius:999px;background:#edf5f1;color:#557168;font-size:8px;font-weight:850;letter-spacing:.5px}}
.course-preview p{{font-size:10px;line-height:1.5;color:#526a62;margin:9px 0}}
.course-facts{{display:grid;grid-template-columns:repeat(3,1fr);gap:5px}}
.course-facts span{{padding:7px 5px;border-radius:7px;background:#f1f7f4;color:#315a4c;font-size:8px;text-align:center}}
.course-facts b{{display:block;color:#006440;font-size:9px;margin-bottom:2px}}
.course-preview .course-note{{font-size:8.5px;margin-bottom:8px}}

/* ===== iPhone / small-screen responsive layout ===== */
@media(max-width:600px){{
 :root{{--side:0px}}
 html,body{{width:100%;max-width:100%;overflow-x:hidden}}
 body{{font-size:13px}}

 .sidebar{{
   position:relative!important;inset:auto!important;
   width:100%!important;height:58px!important;min-height:58px!important;
   padding:6px 8px!important;
   display:flex!important;flex-direction:row!important;align-items:center!important;
   background-color:#004a31!important;
   background-image:linear-gradient(90deg,rgba(0,73,46,.96),rgba(0,54,36,.90)),url('/maiden-tower.png')!important;
   background-position:center,center 56%!important;
   background-size:100% 100%,cover!important;
   box-shadow:0 3px 12px rgba(0,45,28,.16)!important;
 }}
 .brand{{height:46px!important;width:48px!important;min-width:48px!important;padding:0!important;border:0!important;align-items:center!important}}
 .brand img{{width:46px!important;height:46px!important;border-radius:7px!important;object-fit:contain!important;filter:none!important}}
 .side-nav{{
   margin:0 0 0 6px!important;padding:0 0 2px!important;
   display:flex!important;flex-direction:row!important;gap:3px!important;
   overflow-x:auto!important;overflow-y:hidden!important;white-space:nowrap!important;
   scrollbar-width:none!important;
 }}
 .side-nav::-webkit-scrollbar{{display:none}}
 .side-nav a{{display:flex!important;min-width:38px!important;height:38px!important;padding:6px!important;justify-content:center!important;border-radius:8px!important}}
 .side-nav a span,.nav-label{{display:none!important}}
 .side-nav a i{{width:24px!important;height:24px!important;font-size:14px!important}}
 .side-bottom,.designer-footer{{display:none!important}}

 header{{
   position:relative!important;top:auto!important;
   margin-left:0!important;width:100%!important;height:118px!important;
   padding:14px 14px!important;
   background-position:center,center 54%!important;background-size:100% 100%,cover!important;
 }}
 .club-head strong{{font-size:24px!important;line-height:1!important}}
 .club-head span{{font-size:11px!important;letter-spacing:2.1px!important;margin-top:5px!important}}
 .club-head small{{display:none!important}}
 .head-right{{align-self:flex-end!important}}
 .head-right em{{display:none!important}}
 .date-chip{{padding:8px 10px!important;font-size:10px!important;white-space:nowrap!important}}

 main{{margin-left:0!important;width:100%!important;max-width:100%!important;padding:12px 10px 28px!important}}
 .overview-title{{display:flex!important;align-items:flex-end!important;gap:8px!important;flex-wrap:wrap!important}}
 .overview-title h2{{font-size:23px!important;line-height:1.05!important;margin:2px 0!important}}
 .overview-title>span{{margin-left:auto!important;max-width:52%!important;font-size:8px!important;text-align:center!important;padding:6px 8px!important}}

 .kpi-grid{{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:8px!important}}
 .kpi-grid .card{{min-width:0!important;min-height:112px!important;padding:12px 10px!important}}
 .metric-icon{{width:38px!important;height:38px!important;margin-right:7px!important;font-size:13px!important}}
 .kpi .stat{{font-size:27px!important}}
 .kpi b{{font-size:11px!important;line-height:1.2!important}}
 .kpi small{{font-size:8.5px!important;line-height:1.25!important}}

 .overview-charts{{grid-template-columns:1fr!important;gap:9px!important;margin:9px 0!important}}
 .overview-charts .card{{width:100%!important;min-width:0!important;min-height:0!important;padding:45px 10px 10px!important}}
 .overview-charts svg{{width:100%!important;max-width:100%!important;height:auto!important;max-height:none!important}}
 .pie-layout,.compliance-layout{{grid-template-columns:1fr!important;min-height:0!important;gap:12px!important}}
 .chart-legend{{width:100%!important}}
 .compliance-ring{{width:150px!important;height:150px!important}}
 .compliance-ring>div{{width:88px!important;height:88px!important}}
 .qual-bars .hbar{{grid-template-columns:78px minmax(0,1fr) 24px!important;gap:6px!important}}
 .qual-bars .hbar>span{{font-size:10px!important}}

 .grid,.grid2,.grid3,.quick,.row{{grid-template-columns:1fr!important}}
 .card{{max-width:100%!important}}
 .course-facts{{grid-template-columns:1fr!important}}

 .grid2>*{{min-width:0!important}}
 .tw{{display:block!important;width:100%!important;max-width:100%!important;overflow-x:auto!important;overflow-y:hidden!important;-webkit-overflow-scrolling:touch!important;touch-action:pan-x pan-y!important;overscroll-behavior-x:contain}}
 table{{min-width:560px}}
 .compliance-scroll{{position:relative!important;width:100%!important;max-width:calc(100vw - 20px)!important;overflow-x:auto!important;overflow-y:hidden!important;-webkit-overflow-scrolling:touch!important;touch-action:pan-x!important}}
 .compliance-scroll table{{width:max-content!important;min-width:780px!important}}
 .compliance-scroll th,.compliance-scroll td{{white-space:nowrap!important}}
 .compliance-scroll td:last-child{{min-width:250px!important;white-space:normal!important}}
 .compliance-scroll td:first-child,.compliance-scroll th:first-child{{position:sticky!important;left:0!important;z-index:2!important;background:#fff!important;box-shadow:4px 0 8px rgba(0,0,0,.06)}}
 .compliance-scroll th:first-child{{background:#dfe7ea!important;z-index:3!important}}
 main>.card:last-child{{max-width:100%!important;overflow:hidden!important}}
}}
</style></head><body>{nav}<script>document.addEventListener('DOMContentLoaded',()=>{{let p=location.pathname;document.querySelectorAll('.side-nav a').forEach(a=>{{let h=a.getAttribute('href');if((h==='/'&&p==='/')||(h!=='/'&&p.startsWith(h)))a.classList.add('active')}})}})</script><header><div class="club-head"><strong>EASTERN GAELS</strong><span>GAELIC GAMES CLUB</span><small>OUR CLUB &nbsp;•&nbsp; OUR COMMUNITY &nbsp;•&nbsp; OUR FUTURE</small></div><div class="head-right"><em>More Than A Club</em><span class="date-chip">{datetime.now().strftime('%d %b %Y')}</span></div></header><main>{b}</main></body></html>'''
def card(s,admin=False):return f'''<div class="card session"><span class="badge {e(s['actual_status'])}">{e(s['actual_status'])}</span><h2>{e(s['school'])}</h2><div class="muted">{fd(s['date'])} · {e(s['start'])}–{e(s['end'])}</div><p><b>{e(s['coach'])}</b> · {e(s['class_group'])} · {e(s['age_group'])}<br>{e(s['title'])}</p><div class="actions"><a class="btn" href="/session?id={e(s['id'])}">Open session</a>{'<a class="btn secondary" href="/edit?id='+e(s['id'])+'">Edit</a>' if admin else ''}</div></div>'''
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def out(self,x,n=200,h=None):
  b=x.encode();self.send_response(n);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store, no-cache, must-revalidate, max-age=0');self.send_header('Pragma','no-cache');[(self.send_header(k,v)) for k,v in (h or {}).items()];self.end_headers();self.wfile.write(b)
 def red(self,x):self.send_response(303);self.send_header('Location',x);self.end_headers()
 def form(self):
  n=int(self.headers.get('Content-Length','0'));q=parse_qs(self.rfile.read(n).decode());return {k:(v if k=='ids' else v[-1]) for k,v in q.items()}
 def upload_file(self, field_name=None):
  n=int(self.headers.get('Content-Length','0'));raw=self.rfile.read(n);ct=self.headers.get('Content-Type','')
  m=re.search(r'boundary=(?:\"([^\"]+)\"|([^;]+))',ct)
  if not m:return None,None
  boundary=(m.group(1) or m.group(2)).strip().encode();parts=raw.split(b'--'+boundary)
  wanted=(('name="'+field_name+'"').encode() if field_name else None)
  for part in parts:
   head,sep,body=part.partition(b'\r\n\r\n')
   if not sep or b'filename=' not in head:continue
   if wanted and wanted not in head:continue
   fm=re.search(br'filename="([^"]*)"',head)
   name=fm.group(1).decode('utf-8',errors='ignore') if fm else 'upload.xlsx'
   # A multipart part ends with one CRLF before the next boundary. Remove only
   # that framing CRLF; rstrip() can corrupt the binary tail of an .xlsx ZIP.
   if body.endswith(b'\r\n'):body=body[:-2]
   return os.path.basename(name.replace('\\','/')),body
  return None,None
 def upload_file_with_field(self, file_field, text_field):
  n=int(self.headers.get('Content-Length','0'));raw=self.rfile.read(n);ct=self.headers.get('Content-Type','')
  m=re.search(r'boundary=(?:\"([^\"]+)\"|([^;]+))',ct)
  if not m:return None,None,''
  boundary=(m.group(1) or m.group(2)).strip().encode();name=None;data=None;text=''
  for part in raw.split(b'--'+boundary):
   head,sep,body=part.partition(b'\r\n\r\n')
   if not sep:continue
   if body.endswith(b'\r\n'):body=body[:-2]
   if (('name="'+file_field+'"').encode() in head) and b'filename=' in head:
    fm=re.search(br'filename="([^"]*)"',head);name=os.path.basename((fm.group(1).decode('utf-8',errors='ignore') if fm else 'upload').replace('\\','/'));data=body
   elif (('name="'+text_field+'"').encode() in head): text=body.decode('utf-8',errors='ignore').strip()
  return name,data,text
 def user(self):
  z=SimpleCookie(self.headers.get('Cookie'));sid=z.get('egsid');uid=SESS.get(sid.value) if sid else None
  if not uid:return None
  c=dbc();u=c.execute('select * from users where id=? and active=1',(uid,)).fetchone();c.close();return u
 def need(self):
  u=self.user()
  if not u:self.red('/login')
  return u
 def vis(self,u):return (' ',[])
 def do_GET(self):
  p=urlparse(self.path);path=p.path;q=parse_qs(p.query);c=dbc()
  if path=='/simple-analytics.png':
   c.close();pimg=os.path.join(BASE,'simple-analytics.png')
   try:
    with open(pimg,'rb') as f:data=f.read()
    self.send_response(200);self.send_header('Content-Type','image/png');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
   except:self.send_error(404)
   return
  if path in ('/club-jersey.jpg','/club-jersey.png'):
   c.close();pimg=os.path.join(BASE,'club-jersey.png')
   if not os.path.exists(pimg):self.send_error(404);return
   data=open(pimg,'rb').read();self.send_response(200);self.send_header('Content-Type','image/png');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
  if path=='/maiden-tower.png':
   c.close();pimg=os.path.join(BASE,'maiden-tower.png')
   if not os.path.exists(pimg):self.send_error(404);return
   data=open(pimg,'rb').read();self.send_response(200);self.send_header('Content-Type','image/png');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
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
  if path=='/google-oauth/start':
   if not GOOGLE_OAUTH_CLIENT_ID or not GOOGLE_OAUTH_CLIENT_SECRET:
    c.close();return self.out(page('Google Drive','<div class="card"><h2>Google OAuth is not configured in Render.</h2><a class="btn" href="/compliance">Back</a></div>',u),500)
   state=secrets.token_urlsafe(32);GOOGLE_OAUTH_STATES[state]={'uid':u['id'],'expires':time.time()+600}
   params={'client_id':GOOGLE_OAUTH_CLIENT_ID,'redirect_uri':GOOGLE_OAUTH_REDIRECT_URI,'response_type':'code','scope':'https://www.googleapis.com/auth/drive','access_type':'offline','prompt':'consent','state':state}
   c.close();return self.red('https://accounts.google.com/o/oauth2/v2/auth?'+urlencode(params))
  if path=='/oauth2callback':
   import requests
   state=q.get('state',[''])[0];code=q.get('code',[''])[0];err=q.get('error',[''])[0];st=GOOGLE_OAUTH_STATES.pop(state,None)
   if err or not st or st.get('uid')!=u['id'] or st.get('expires',0)<time.time() or not code:
    c.close();return self.out(page('Google Drive','<div class="card"><h2>Google Drive connection was not completed.</h2><p>'+e(err or 'Invalid or expired OAuth response.')+'</p><a class="btn" href="/compliance">Back</a></div>',u),400)
   r=requests.post('https://oauth2.googleapis.com/token',data={'client_id':GOOGLE_OAUTH_CLIENT_ID,'client_secret':GOOGLE_OAUTH_CLIENT_SECRET,'code':code,'grant_type':'authorization_code','redirect_uri':GOOGLE_OAUTH_REDIRECT_URI},timeout=30)
   if r.status_code!=200:
    c.close();return self.out(page('Google Drive',f'<div class="card"><h2>Could not connect Google Drive</h2><p>{e((r.text or "")[:500])}</p><a class="btn" href="/compliance">Back</a></div>',u),500)
   tok=r.json();oldtok=load_google_oauth_token();refresh=tok.get('refresh_token') or oldtok.get('refresh_token')
   if not refresh:
    c.close();return self.out(page('Google Drive','<div class="card"><h2>No refresh token was returned by Google.</h2><p>Please try Connect Google Drive again.</p><a class="btn" href="/compliance">Back</a></div>',u),500)
   save_google_oauth_token({'refresh_token':refresh,'connected_at':datetime.now().isoformat(timespec='seconds')})
   c.close();return self.red('/compliance')
  if path.startswith('/members/'):
   group=path.rstrip('/').split('/')[-1]
   body=adult_members_drilldown(group)
   if body:
    c.close()
    return self.out(page('Members',body,u))
  if path=='/':
   w,a=self.vis(u);ss=c.execute('select * from sessions '+w+' order by date,start',a).fetchall();c.close()
   years=sorted((int(y) for y in DEMO.get('growth',{}) if str(y).isdigit()));latest=years[-1] if years else datetime.now().year;prevyr=years[-2] if len(years)>1 else latest-1
   juvenile_members=sum(DEMO.get('age_totals',{}).values());adult_members=int(DEMO.get('senior_adult_non_playing_count',0));ladies_members=int(DEMO.get('senior_adult_ladies_count',0));mens_members=int(DEMO.get('senior_adult_mens_count',0));members=juvenile_members+adult_members+ladies_members+mens_members;prev=int(DEMO.get('growth',{}).get(str(prevyr),0));latest_juvenile=int(DEMO.get('growth',{}).get(str(latest),juvenile_members));gpct=round((latest_juvenile-prev)*100/prev) if prev else 0
   coaches=list(COACHING.get('coaches',{}).values());vetted=sum(str(x.get('garda_vetted','')).upper()=='YES' for x in coaches);safe=sum(str(x.get('safeguarding','')).upper()=='YES' for x in coaches);qual=sum(str(x.get('qualification','')).upper() not in ('','UNKNOWN','NONE','NO') for x in coaches)
   games=sum(int(v) for v in DEMO.get('games',{}).values());done=sum(x['actual_status']=='Completed' for x in ss);attendance=sum((x['attendance'] or 0) for x in ss if x['actual_status']=='Completed')
   growth=DEMO.get('growth',{});growth_chart=svg_bar_chart({str(y):int(growth.get(str(y),0)) for y in years[-6:]},230)
   ages=dict(sorted(DEMO.get('age_totals',{}).items(),key=lambda x:int(x[0][1:])));age_chart=svg_bar_chart(ages,230)
   catchment_chart=pie_chart(DEMO.get('catchment',{}))
   compliance_rate=round((vetted+safe)*100/(2*len(coaches))) if coaches else 0
   expired_count=sum(expiry_bucket(x)[0]=='expired' for x in coaches)
   compliant_count=sum(str(x.get('garda_vetted','')).upper()=='YES' and str(x.get('safeguarding','')).upper()=='YES' and expiry_bucket(x)[0]!='expired' for x in coaches)
   pending_count=max(0,len(coaches)-compliant_count-expired_count)
   compliance_rate=round(compliant_count*100/len(coaches)) if coaches else 0
   compliance_chart=compliance_status_chart({'Compliant':compliant_count,'Pending':pending_count,'Expired':expired_count,'Not Required':0},compliance_rate)
   quals=COACHING.get('qualification_summary',{}) or {}
   if not quals:
    for x in coaches:
     qv=str(x.get('qualification','Unknown') or 'Unknown').strip()
     if qv.upper() not in ('','UNKNOWN','NONE','NO'): quals[qv]=quals.get(qv,0)+1
   qual_chart=hbar_chart(quals)
   games_chart=svg_bar_chart(dict(sorted(DEMO.get('games',{}).items(),key=lambda x:str(x[0]))),230)
   juveniles=sum(v for k,v in ages.items() if str(k).upper().startswith('U'));adults=int(DEMO.get('senior_adult_non_playing_count',0))
   evs=DEMO.get('upcoming_events',[])[:6]
   evrows=''.join(f'<tr><td><b>{e(x.get("event",""))}</b></td><td>{e(x.get("venue",""))}</td><td>{e(x.get("date",""))}</td><td>{e(x.get("time",""))}</td></tr>' for x in evs)
   upcoming_html=('<div class="card" style="margin-top:14px"><div class="section-title"><h3>Upcoming Events</h3><span class="pill">'+str(len(DEMO.get('upcoming_events',[])))+' scheduled</span></div><div class="tw"><table><tr><th>Event</th><th>Venue</th><th>Date</th><th>Time</th></tr>'+evrows+'</table></div></div>') if evs else ''
   gpo_live=load_gpo_costs();gpo_years=gpo_live.get('years',{});gpo_current=gpo_years.get('2026/27',{});gpo_total=float(gpo_current.get('total',0) or 0)
   gender=DEMO.get('juvenile_gender',{}) or {};boys=int(gender.get('Boys',0) or 0);girls=int(gender.get('Girls',0) or 0);gender_total=boys+girls;boys_pct=round(boys*100/gender_total) if gender_total else 0;girls_pct=100-boys_pct if gender_total else 0
   b=f'''<div class="overview-title"><div><small>CLUB DASHBOARD</small><h2>Club Overview</h2></div><span>Live from latest club workbook</span></div><div class="kpi-grid"><div class="card kpi"><span class="metric-icon">M</span><div class="stat">{members}</div><b>Total Members</b><small>Latest membership total</small></div><div class="card kpi"><span class="metric-icon">J</span><div class="stat">{juveniles}</div><b>Juvenile Members</b><small>Age-group membership</small></div><div class="card kpi"><span class="metric-icon">B/G</span><div class="stat">{boys} / {girls}</div><b>Juvenile Boys v Girls</b><small>Boys {boys_pct}% · Girls {girls_pct}%</small></div><a href="/members/non-playing" class="card kpi" style="text-decoration:none;color:inherit;cursor:pointer"><span class="metric-icon">A</span><div class="stat">{adults}</div><b>Senior Adult Non-Playing Members</b><small>Tap to view members</small></a><a href="/members/ladies" class="card kpi" style="text-decoration:none;color:inherit;cursor:pointer"><span class="metric-icon">L</span><div class="stat">{ladies_members}</div><b>Senior Adult Ladies Members</b><small>Tap to view members</small></a><a href="/members/mens" class="card kpi" style="text-decoration:none;color:inherit;cursor:pointer"><span class="metric-icon">M</span><div class="stat">{mens_members}</div><b>Senior Adult Mens Members</b><small>Tap to view members</small></a><div class="card kpi"><span class="metric-icon">C</span><div class="stat">{len(coaches)}</div><b>Active Coaches</b><small>{qual} qualifications recorded</small></div><div class="card kpi"><span class="metric-icon">%</span><div class="stat">{compliance_rate}%</div><b>Compliance Rate</b><small>Vetting + safeguarding completion</small></div><a href="/gpo-costs" class="card kpi" style="text-decoration:none;color:inherit;cursor:pointer"><span class="metric-icon">€</span><div class="stat">€{gpo_total:,.0f}</div><b>GPO Coaching Cost</b><small>2026/27 to date · Tap to view</small></a></div><div class="overview-charts"><div class="card"><div class="section-title"><h3>Juvenile Membership Growth</h3><span class="pill">+{gpct}% latest YoY</span></div>{growth_chart}</div><div class="card"><div class="section-title"><h3>Juvenile Age Group Breakdown</h3><a href="/membership" class="pill">View</a></div>{age_chart}</div><div class="card"><div class="section-title"><h3>Juvenile Membership Catchment</h3></div>{catchment_chart}</div><div class="card"><div class="section-title"><h3>Compliance Status</h3><a href="/compliance" class="pill">View</a></div>{compliance_chart}</div><div class="card"><div class="section-title"><h3>Coach Qualifications</h3><a href="/courses" class="pill">View</a></div>{qual_chart}</div><div class="card"><div class="section-title"><h3>Games Played</h3><a href="/games" class="pill">View</a></div>{games_chart}</div></div>{upcoming_html}''';return self.out(page('Club Overview',b,u))
  if path=='/today':
   d=q.get('date',[date.today().isoformat()])[0];w,a=self.vis(u);con='and' if 'where' in w else 'where';r=c.execute('select * from sessions '+w+con+' date=? order by start',a+[d]).fetchall();c.close();b=f'<div class="hero"><div><div class="eyebrow">Schools programme</div><h2>Selected Day</h2></div></div><form class="card"><label>Date</label><div class="row"><input type="date" name="date" value="{e(d)}"><button>Show date</button></div></form>'+(''.join(card(x,True) for x in r) if r else '<div class="card">No coaching scheduled for this date.</div>');return self.out(page('Schools Schedule',b,u))
  if path=='/gpo-costs':
   c.close();years=load_gpo_costs().get('years',{})
   cards=''.join(f'<div class="card kpi"><div class="stat">€{float(v.get("total",0)):,.0f}</div><b>{e(y)} GPO Cost</b><small>{len(v.get("entries",[]))} recorded coaching visits</small></div>' for y,v in sorted(years.items()))
   sections=''
   for y,v in sorted(years.items(),reverse=True):
    rows=''.join(f'<tr><td>{e(x.get("day",""))}</td><td>{e(x.get("school",""))}</td><td>€{float(x.get("cost",0)):,.2f}</td><td>{e(x.get("detail",""))}</td></tr>' for x in v.get('entries',[]))
    sections+=f'<div class="card"><div class="section-title"><h3>{e(y)} GPO Coaching Costs</h3><span class="pill">Total €{float(v.get("total",0)):,.2f}</span></div><div class="tw"><table><tr><th>Day Worked</th><th>School</th><th>Cost</th><th>Detail</th></tr>{rows}</table></div></div>'
   b=f'<div class="overview-title"><div><small>SCHOOLS PROGRAMME</small><h2>GPO Coaching Cost</h2></div><span>Automatically synced from the Schools workbook</span></div><div class="grid">{cards}</div>{sections}<div class="actions"><a class="btn secondary" href="/">← Back to Club Overview</a></div>'
   return self.out(page('GPO Coaching Cost',b,u))
  if path=='/schedule':
   w,a=self.vis(u);r=c.execute('select * from sessions '+w+' order by date,start',a).fetchall();c.close();trs=''.join(f'<tr><td>{fd(x["date"])}</td><td><a href="/session?id={e(x["id"])}">{e(x["school"])}</a></td><td>{e(x["coach"])}</td><td>{e(x["class_group"])}</td><td><span class="badge {e(x["actual_status"])}">{e(x["actual_status"])}</span></td></tr>' for x in r);b=f'''<div class="hero"><div><div class="eyebrow">Schools programme</div><h2>Schools Schedule</h2><p>Search and manage all school coaching sessions.</p></div><a class="btn" href="/today">Today / selected day</a></div><div class="card"><input id="s" placeholder="Search school, coach, class or date…" oninput="f()"></div><div class="tw"><table id="t"><tr><th>Date</th><th>School</th><th>Coach</th><th>Class</th><th>Status</th></tr>{trs}</table></div><script>function f(){{let q=s.value.toLowerCase();document.querySelectorAll('#t tr').forEach((r,i)=>{{if(i)r.style.display=r.innerText.toLowerCase().includes(q)?'':'none'}})}}</script>''';return self.out(page('Schedule',b,u))
  if path=='/schools':
   w,a=self.vis(u);r=c.execute('select school,count(*) n,sum(actual_status="Completed") done from sessions '+w+' group by school order by school',a).fetchall();c.close();return self.out(page('Schools','<h2>Schools</h2><div class="grid">'+''.join(f'<div class="card"><h3>{e(x["school"])}</h3><div class="stat">{x["done"]}</div><div class="muted">completed of {x["n"]} scheduled</div></div>' for x in r)+'</div>',u))
  if path=='/session':
   s=c.execute('select * from sessions where id=?',(q.get('id',[''])[0],)).fetchone();c.close()
   if not s:return self.out(page('Not found','<div class="card">Session not found.</div>',u),404)
   opts=''.join('<option'+(' selected' if s['actual_status']==x else '')+'>'+x+'</option>' for x in ['Scheduled','Completed','Cancelled','School Closed','Rescheduled']);b=card(s,True)+f'''<div class="card"><form method="post"><input type="hidden" name="id" value="{e(s['id'])}"><label>Status</label><select name="status">{opts}</select><label>Attendance / children coached</label><input type="number" min="0" name="attendance" value="{e(s['attendance'])}"><label>Session notes</label><textarea name="notes" rows="5">{e(s['notes'])}</textarea><div class="actions"><button>Save session record</button></div></form></div>''';return self.out(page('Session',b,u))
  if path=='/demographics':
   c.close();years=sorted((int(y) for y in DEMO.get('growth',{}) if str(y).isdigit()));latest_year=years[-1] if years else datetime.now().year;prev_year=years[-2] if len(years)>1 else latest_year-1;total=DEMO.get('growth',{}).get(str(latest_year),sum(DEMO.get('age_totals',{}).values()));prev=DEMO.get('growth',{}).get(str(prev_year),0);growthpct=round((total-prev)*100/prev) if prev else 0;games=sum(DEMO.get('games',{}).values())
   def bars(data):
    mx=max([int(v) for v in data.values()] or [1]);return ''.join(f'<div class="barrow"><b>{e(k)}</b><div class="bartrack"><div class="barfill" style="width:{int(v)*100/mx:.0f}%"></div></div><b>{int(v)}</b></div>' for k,v in data.items())
   age=dict(sorted(DEMO['age_totals'].items(),key=lambda x:int(x[0][1:])))
   agelinks=''.join(f'<a class="chartlink" href="/demographics/age?group={e(k)}"><div class="card"><h3>{e(k)}</h3><div class="stat">{int(v)}</div><div class="muted">players · tap for catchment & schools</div></div></a>' for k,v in age.items())
   b=f'''<div class="eyebrow">Club profile</div><h2>Club Demographics</h2><p class="muted">Eastern Gaels player profile · {latest_year}</p><div class="grid"><div class="card kpi"><div class="stat">{total}</div><b>Players</b><small>{latest_year} club population</small></div><div class="card kpi"><div class="stat">+{growthpct}%</div><b>Year-on-year growth</b><small>{prev} players in {prev_year}</small></div><div class="card kpi"><div class="stat">{len(DEMO['age_totals'])}</div><b>Age groups</b><small>U5 through U12</small></div><div class="card kpi"><div class="stat">{games}</div><b>Games played</b><small>recorded in source workbook</small></div></div><div class="grid2"><div class="card chart-card"><h3>Membership growth</h3>{svg_line_area(DEMO['growth'])}</div><div class="card chart-card"><h3>Players by age group</h3>{svg_bar_chart(age)}</div></div><div class="grid2"><div class="card chart-card"><h3>Where our players live</h3>{donut_chart(DEMO['catchment'],subtitle='players')}</div><div class="card chart-card"><h3>Schools represented</h3>{hbar_chart(DEMO['school_totals'])}</div></div><div class="card chart-card"><h3>Games played by team</h3>{svg_bar_chart(DEMO['games'])}</div><h3>Age-group detail</h3><div class="grid">{agelinks}</div>''';return self.out(page('Club Demographics',b,u))
  if path=='/demographics/age':
   c.close();g=q.get('group',[''])[0].upper()
   if g not in DEMO['age_totals']:return self.red('/demographics')
   def bars2(data):
    mx=max([int(v) for v in data.values()] or [1]);return ''.join(f'<div class="barrow"><b>{e(k)}</b><div class="bartrack"><div class="barfill" style="width:{int(v)*100/mx:.0f}%"></div></div><b>{int(v)}</b></div>' for k,v in data.items())
   players=DEMO.get('players_by_age',{}).get(g,[]);prows=''.join(f'<tr><td>{e(x.get("name",""))}</td><td>{e(x.get("school",""))}</td></tr>' for x in players);plist=(f'<div class="card"><h3>{e(g)} Players</h3><p class="muted">{len(players)} player names imported. Only player name and school are stored/displayed.</p><div class="tw"><table><tr><th>Player Name</th><th>School</th></tr>{prows}</table></div></div>' if players else '<div class="card"><h3>Players</h3><p class="muted">No player-name list has been imported for this age group yet.</p></div>');total=int(DEMO['age_totals'][g]);b=f'''<div class="actions"><a class="btn secondary" href="/demographics">← Demographics</a></div><h2>{e(g)} Demographics</h2><div class="card kpi"><div class="stat">{total}</div><b>{e(g)} players</b><small>2026</small></div>{plist}<div class="grid"><div class="card"><h3>Residential catchment</h3>{bars2(DEMO['age_areas'][g])}</div><div class="card"><h3>School breakdown</h3>{bars2(DEMO['age_schools'][g])}</div></div><div class="card"><p class="muted">Figures are imported from the updated Eastern Gaels demographics workbook. Zero-value categories are retained so the source structure remains visible.</p></div>''';return self.out(page(g+' Demographics',b,u))
  if path=='/coaching-team':
   c.close();coaches=list(COACHING.get('coaches',{}).values());teams=COACHING.get('teams',{});buckets={'expired':0,'urgent':0,'warning':0,'unknown':0,'unknown_expiry':0,'not_vetted':0,'valid':0}
   for x in coaches:buckets[expiry_bucket(x)[0]]+=1
   vetted=sum(str(x.get('garda_vetted',x.get('garda_status',''))).strip().upper()=='YES' for x in coaches);safe=sum(str(x.get('safeguarding','')).strip().upper()=='YES' for x in coaches);qual=sum(str(x.get('qualification','')).strip().upper() not in ('','UNKNOWN','NONE','NO') for x in coaches);rows='';order={'expired':0,'urgent':1,'warning':2,'unknown_expiry':3,'not_vetted':4,'unknown':5,'valid':6}
   labels={'expired':'Expired','urgent':'Expires <=90 days','warning':'Expires <=180 days','unknown_expiry':'Vetted - expiry missing','not_vetted':'Not vetted','unknown':'Vetting unknown','valid':'Vetted / valid'}
   for x in sorted(coaches,key=lambda z:(order[expiry_bucket(z)[0]],z.get('name',''))):
    bucket,days=expiry_bucket(x);expiry=x.get('garda_expiry_text') or x.get('garda_expiry') or '-';detail=('Expired '+str(abs(days))+' days ago' if bucket=='expired' and days is not None else (str(days)+' days remaining' if days is not None else expiry));sv=str(x.get('safeguarding','Unknown'));qv=str(x.get('qualification','Unknown'))
    rows+=f'<tr><td><b>{e(x.get("name"))}</b></td><td>{e(x.get("garda_vetted",x.get("garda_status","Unknown")))}</td><td><span class="badge {bucket}">{labels[bucket]}</span><br><small>{e(detail)}</small></td><td>{e(sv)}</td><td>{e(qv)}</td><td>{e(", ".join(x.get("teams",[])))}</td></tr>'
   teamcards=''.join(f'<div class="card"><h3>{e(k)}</h3><div class="stat">{len(v)}</div><div class="muted">coaches</div><p>{e(", ".join(v))}</p></div>' for k,v in teams.items())
   b=f'''<div class="eyebrow">People & teams</div><h2>Coaches & Teams</h2><p class="muted">Garda Vetting and Safeguarding are tracked independently. Vetting expiry warnings apply only when Garda Vetted is Yes.</p><div class="grid"><div class="card kpi"><div class="stat">{len(coaches)}</div><b>Total coaches</b></div><div class="card kpi"><div class="stat">{vetted}</div><b>Garda vetted</b><small>of {len(coaches)}</small></div><div class="card kpi"><div class="stat">{safe}</div><b>Safeguarding completed</b><small>of {len(coaches)}</small></div><div class="card kpi"><div class="stat">{qual}</div><b>Qualified coaches</b></div><div class="card kpi"><div class="stat">{buckets['expired']+buckets['urgent']}</div><b>Vetting expiry action</b><small>expired / within 90 days</small></div></div><div class="card"><h3>Coach compliance</h3><div class="tw"><table><tr><th>Coach</th><th>Garda Vetted</th><th>Vetting Expiry</th><th>Safeguarding</th><th>Qualification</th><th>Teams</th></tr>{rows}</table></div></div><h3>Coaching pool</h3><div class="grid">{teamcards}</div>'''
   return self.out(page('Coaching Team',b,u))
  if path=='/compliance':
   coaches=list(COACHING.get('coaches',{}).values());total=len(coaches);vetted=sum(str(x.get('garda_vetted','')).upper()=='YES' for x in coaches);safe=sum(str(x.get('safeguarding','')).upper()=='YES' for x in coaches);action=sum(expiry_bucket(x)[0] in ('expired','urgent') for x in coaches);rows='';drive_connected=bool(load_google_oauth_token().get('refresh_token'))
   forms={r['coach_key']:dict(r) for r in c.execute('select * from garda_forms').fetchall()};c.close()
   for x in sorted(coaches,key=lambda z:z.get('name','')):
    bucket,days=expiry_bucket(x);exp=x.get('garda_expiry_text') or x.get('garda_expiry') or '-';raw_coach=x.get('name','');coach=e(raw_coach);form=forms.get(coach_key(raw_coach));form_status=(f'<span class="badge valid">✓ Uploaded</span> <a class="btn" href="{e(form.get("web_view_link"))}" target="_blank" rel="noopener noreferrer">View file ↗</a><br><small>Uploaded {e(form.get("uploaded_at","").replace("T"," "))}</small>' if form and form.get('web_view_link') else '<span class="badge unknown">Not uploaded</span>');rows+=f'<tr><td><b>{coach}</b></td><td>{e(x.get("garda_vetted","Unknown"))}</td><td><span class="badge {bucket}">{e(exp)}</span></td><td>{e(x.get("safeguarding","Unknown"))}</td><td><div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:8px">{form_status}</div><form method="post" action="/compliance/garda-upload" enctype="multipart/form-data" style="display:flex;gap:6px;align-items:center;flex-wrap:wrap"><input type="hidden" name="coach_name" value="{coach}"><input type="file" name="garda_file" accept=".pdf,.jpg,.jpeg,.png" required style="max-width:180px"><button type="submit">{"Replace" if form else "Upload"}</button></form></td></tr>'
   b=f'''<div class="hero"><div><div class="eyebrow">Governance</div><h2>Compliance</h2><p>Garda Vetting and Safeguarding tracked independently.</p></div></div><div class="grid"><div class="card kpi"><div class="stat">{vetted}</div><b>Garda vetted</b><small>of {total} coaches</small></div><div class="card kpi"><div class="stat">{safe}</div><b>Safeguarding completed</b><small>of {total} coaches</small></div><div class="card kpi"><div class="stat">{action}</div><b>Expiry action</b><small>expired / within 90 days</small></div></div><div class="grid2"><div class="card chart-card"><h3>Overall compliance</h3>{donut_chart({"Garda vetted":vetted,"Garda outstanding":max(0,total-vetted),"Safeguarding":safe,"Safeguarding outstanding":max(0,total-safe)},center=str(round((vetted+safe)*100/(2*total)))+"%",subtitle="complete")}</div><div class="card"><h3>Coach compliance</h3><p class="muted">Upload Garda Vetting forms directly to the club's restricted Google Drive folder. PDF, JPG and PNG accepted.</p>{'<p><span class="badge valid">Google Drive connected</span></p>' if drive_connected else '<p><a class="btn" href="/google-oauth/start">Connect Google Drive</a></p>'}<div class="tw compliance-scroll" role="region" aria-label="Coach compliance table. Swipe left and right to see all columns." tabindex="0"><table><tr><th>Coach</th><th>Garda Vetted</th><th>Vetting Expiry</th><th>Safeguarding</th><th>Vetting Form</th></tr>{rows}</table></div></div></div>''';return self.out(page('Compliance',b,u))
  if path=='/courses':
   c.close();coaches=list(COACHING.get('coaches',{}).values());quals={}
   for x in coaches:qv=str(x.get('qualification','Unknown') or 'Unknown').strip();quals[qv]=quals.get(qv,0)+1
   mx=max(quals.values() or [1]);bars=''.join(f'<div class="barrow"><b>{e(k)}</b><div class="bartrack"><div class="barfill" style="width:{v*100/mx:.0f}%"></div></div><b>{v}</b></div>' for k,v in quals.items());rows=''.join(f'<tr><td>{e(x.get("name"))}</td><td>{e(x.get("qualification","Unknown"))}</td></tr>' for x in sorted(coaches,key=lambda z:z.get('name','')))
   b=f'''<div class="hero"><div><div class="eyebrow">Coach development</div><h2>Courses & Qualifications</h2><p>Current coaching qualifications from the Coaching Team workbook.</p></div></div><div class="grid2"><div class="card chart-card"><h3>Qualification mix</h3>{hbar_chart(quals)}</div><div class="card native-course-card"><div class="course-badge">MEATH GAA · COACH EDUCATION</div><h3>Upcoming Coaching Courses</h3><div class="course-preview"><strong>Introduction to Gaelic Games</strong><span class="foundation-tag">Foundation Award</span><p>This course replaces the Foundation Award for coaches starting on the coaching ladder across GAA, LGFA &amp; Camogie.</p><div class="course-facts"><span><b>Midweek</b> 7pm–10pm</span><span><b>Saturday</b> 9:30am–2pm</span><span><b>Cost</b> €15 per person</span></div><p class="course-note">All listed dates must be attended for certification. Places must be booked in advance.</p><a class="course-link-btn" href="https://meath.gaa.ie/coaching-games/coach-education/courses/introduction-to-gaelic-games-foundation-award/" target="_blank" rel="noopener noreferrer">View Course &amp; Express Interest ↗</a></div></div></div><div class="card"><div class="tw"><table><tr><th>Coach</th><th>Qualification</th></tr>{rows}</table></div></div>''';return self.out(page('Courses',b,u))
  if path=='/games':
   c.close();games=DEMO.get('games',{});total=sum(int(v) for v in games.values());mx=max([int(v) for v in games.values()] or [1]);bars=''.join(f'<div class="barrow"><b>{e(k)}</b><div class="bartrack"><div class="barfill" style="width:{int(v)*100/mx:.0f}%"></div></div><b>{int(v)}</b></div>' for k,v in games.items())
   b=f'''<div class="hero"><div><div class="eyebrow">Playing programme</div><h2>Games Played</h2><p>Games activity by team / age group.</p></div></div><div class="grid"><div class="card kpi"><div class="stat">{total}</div><b>Total games</b><small>Recorded in source workbook</small></div><div class="card kpi"><div class="stat">{len(games)}</div><b>Teams reporting</b></div></div><div class="card chart-card"><h3>Games by team</h3>{svg_bar_chart(games,260)}</div>''';return self.out(page('Games Played',b,u))
  if path=='/membership':
   c.close();ages=dict(sorted(DEMO.get('age_totals',{}).items(),key=lambda x:int(x[0][1:])));years=sorted((int(y) for y in DEMO.get('growth',{}) if str(y).isdigit()));latest=years[-1] if years else datetime.now().year;total=int(DEMO.get('growth',{}).get(str(latest),sum(ages.values())));cards=''.join(f'<a class="chartlink" href="/demographics/age?group={e(k)}"><div class="card kpi"><div class="stat">{int(v)}</div><b>{e(k)}</b><small>View player names & school</small></div></a>' for k,v in ages.items())
   b=f'''<div class="hero"><div><div class="eyebrow">Club population</div><h2>Membership</h2><p>Age-group membership with player-name drill-downs.</p></div></div><div class="grid"><div class="card kpi"><div class="stat">{total}</div><b>Total members</b><small>{latest}</small></div><div class="card kpi"><div class="stat">{len(ages)}</div><b>Age groups</b></div></div><div class="section-title"><h3>Members by age group</h3><span class="pill">Tap an age group</span></div><div class="grid">{cards}</div>''';return self.out(page('Membership',b,u))
  if path=='/reports':
   w,a=self.vis(u)
   ss=c.execute('select * from sessions '+w+' order by date,start',a).fetchall()
   total=len(ss);done=sum(x['actual_status']=='Completed' for x in ss);cancelled=sum(x['actual_status']=='Cancelled' for x in ss);closed=sum(x['actual_status']=='School Closed' for x in ss);scheduled=sum(x['actual_status']=='Scheduled' for x in ss);attendance=sum((x['attendance'] or 0) for x in ss if x['actual_status']=='Completed')
   # Coaching hours must come ONLY from sessions whose live dashboard
   # status is Completed.  Use total_seconds() so an invalid end time that
   # is earlier than the start time cannot wrap around and add ~24 hours.
   completed_sessions=[x for x in ss if str(x['actual_status'] or '').strip()=='Completed']
   hours=0.0
   for x in completed_sessions:
    if x['start'] and x['end']:
     try:
      st=datetime.strptime(str(x['start']).strip(),'%H:%M')
      en=datetime.strptime(str(x['end']).strip(),'%H:%M')
      duration=(en-st).total_seconds()/3600
      if duration > 0:
       hours+=duration
     except (TypeError,ValueError):
      pass
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
   c.close();b=f'''<h2>Coaching Dashboard</h2><p class="muted">Live summary of the 2026–2027 schools coaching programme.</p><div class="grid"><div class="card kpi"><div class="stat">{done}</div><b>Sessions completed</b><small>of {total} planned</small></div><div class="card kpi"><div class="stat">{pct}%</div><b>Programme complete</b><small>{scheduled} still scheduled</small></div><div class="card kpi"><div class="stat">{hours:.1f}</div><b>Coaching hours</b><small>completed sessions</small></div><div class="card kpi"><div class="stat">{attendance}</div><b>Recorded attendance</b><small>total contacts entered</small></div></div><div class="grid"><div class="card"><h3>Completed sessions by month</h3>{monthbars}</div><div class="card"><h3>Session status</h3><div class="donut" style="--done:{d1}%;--cancel:{d2}%;--closed:{d3}%"></div><div class="legend"><span><i class="dot"></i>Completed {done}</span><span>Cancelled {cancelled}</span><span>School closed {closed}</span><span>Scheduled {scheduled}</span></div></div></div><div class="grid"><div class="card"><h3>Completed by school</h3>{schoolbars}</div><div class="card"><h3>Completed by coach</h3>{coachbars}</div></div><h3>School progress</h3><div class="grid">{schoolcards}</div><div class="actions"><a class="btn" href="/export.csv">Download CSV report</a></div>''';return self.out(page('Dashboard',b,u))
  if path=='/reports/detail':
   school=q.get('school',[''])[0];coach=q.get('coach',[''])[0];w,a=self.vis(u);con='and' if 'where' in w else 'where';extra='';vals=list(a);title='Completed sessions'
   if school:extra=' school=?';vals.append(school);title=school
   elif coach:extra=' coach=?';vals.append(coach);title=coach
   else:extra=" actual_status='Completed'"
   r=c.execute('select * from sessions '+w+con+extra+' order by date,start',vals).fetchall();c.close();rows=''.join(f'<tr><td>{fd(x["date"])}</td><td>{e(x["school"])}</td><td>{e(x["coach"])}</td><td>{e(x["class_group"])}</td><td><span class="badge {e(x["actual_status"])}">{e(x["actual_status"])}</span></td><td>{e(x["attendance"])}</td></tr>' for x in r);return self.out(page('Report detail',f'<h2>{e(title)}</h2><p class="muted">{len(r)} sessions</p><div class="tw"><table><tr><th>Date</th><th>School</th><th>Coach</th><th>Class</th><th>Status</th><th>Attendance</th></tr>{rows}</table></div><div class="actions"><a class="btn secondary" href="/reports">Back to dashboard</a></div>',u))
  if path=='/admin':
   us=c.execute('select * from users order by role,name').fetchall();co=[x[0] for x in c.execute('select distinct coach from sessions order by coach')];now=datetime.now();today=now.date().isoformat();clock=now.strftime('%H:%M');overdue=c.execute("select count(*) from sessions where actual_status='Scheduled' and (date < ? or (date = ? and coalesce(end,start,'23:59') < ?))",(today,today,clock)).fetchone()[0];c.close();opts=''.join(f'<option>{e(x)}</option>' for x in co);rows=''.join(f'<tr><td>{e(x["name"])}</td><td>{e(x["email"])}</td><td>{'Super Admin' if x['role']=='admin' else 'Full Access'}</td><td>{e(x["coach_name"])}</td></tr>' for x in us);b=f'''<div class="eyebrow">System management</div><h2>Administration</h2><div class="card"><h3>Past due sessions</h3><div class="stat">{overdue}</div><p class="muted">Scheduled sessions whose date/time has passed. Cancelled, School Closed, Rescheduled and already Completed sessions are not included.</p><div class="actions"><a class="btn" href="/admin/past-due">Review past sessions</a></div></div><div class="grid">{('<div class="card"><h3>User Management</h3><p class="muted">Super Admin only. New users receive Full Access to operational features.</p><form method="post" action="/admin/user"><label>Name</label><input name="name" required><label>Email</label><input type="email" name="email" required><label>Temporary password</label><input type="password" minlength="8" name="password" required><label>Timetable coach (optional)</label><select name="coach_name"><option value="">— None —</option>'+opts+'</select><div class="actions"><button>Create Full Access user</button></div></form></div>') if u['role']=='admin' else ''}<div class="card"><h3>Add session</h3><form method="post" action="/admin/session"><label>Date</label><input type="date" name="date" required><label>School</label><input name="school" required><label>Coach</label><input name="coach" required><div class="row"><div><label>Start</label><input type="time" name="start"></div><div><label>End</label><input type="time" name="end"></div></div><label>Class group</label><input name="class_group"><label>Age group</label><input name="age_group"><label>Title</label><input name="title" value="GAA Coaching"><div class="actions"><button>Add session</button></div></form></div></div><div class="card"><h3>Update Demographics</h3><p class="muted">Upload the latest Eastern Gaels workbook. Demographics, Garda Vetting, Safeguarding, Coaching Qualifications and Upcoming Events are read from their dedicated tabs. The app validates demographics and shows a preview before anything is changed.</p><form method="post" action="/admin/demographics/preview" enctype="multipart/form-data"><label>Demographics workbook (.xlsx)</label><input type="file" name="demographics_file" accept=".xlsx" required><div class="actions"><button>Upload & preview</button></div></form></div><div class="card"><h3>Update Schools Coaching Timetable</h3><p class="muted">Upload the latest Schools GAA Coaching Timetable. This replaces the existing Schools Schedule so revised dates, coaches, statuses and sessions do not create duplicates.</p><form method="post" action="/admin/schools/upload" enctype="multipart/form-data"><label>Schools coaching timetable (.xlsx)</label><input type="file" name="schools_file" accept=".xlsx" required><div class="actions"><button>Upload schools timetable</button></div></form></div><div class="card"><h3>Update Coaching Team</h3><p class="muted">Upload the latest Garda vetting, safeguarding, qualifications and coaching pool workbook.</p><form method="post" action="/admin/coaching-team/upload" enctype="multipart/form-data"><label>Coaching details workbook (.xlsx)</label><input type="file" name="coaching_file" accept=".xlsx" required><div class="actions"><button>Upload coaching details</button></div></form></div>{('<div class="card"><h3>Users</h3><div class="tw"><table><tr><th>Name</th><th>Email</th><th>Access</th><th>Timetable coach</th></tr>'+rows+'</table></div></div>') if u['role']=='admin' else ''}''';return self.out(page('Admin',b,u))
  if path=='/admin/past-due':
   now=datetime.now();today=now.date().isoformat();clock=now.strftime('%H:%M');r=c.execute("select * from sessions where actual_status='Scheduled' and (date < ? or (date = ? and coalesce(end,start,'23:59') < ?)) order by date,start",(today,today,clock)).fetchall();c.close()
   rows=''.join(f'<tr><td><input form="bulk" type="checkbox" name="ids" value="{e(x["id"])}" checked></td><td>{fd(x["date"])}</td><td>{e(x["school"])}</td><td>{e(x["coach"])}</td><td>{e(x["start"])}–{e(x["end"])}</td><td><a href="/session?id={e(x["id"])}">Open</a></td></tr>' for x in r)
   if not r:b='<h2>Past due sessions</h2><div class="card"><h3>All caught up</h3><p>There are no past-due sessions still marked Scheduled.</p><a class="btn secondary" href="/admin">Back to Admin</a></div>'
   else:b=f'''<h2>Past due sessions</h2><div class="card"><p>Review the sessions below. Untick anything that was not actually completed, then mark the selected sessions Completed.</p><form id="bulk" method="post" action="/admin/past-due"><div class="actions"><button>Mark selected as Completed</button><button type="button" class="secondary" onclick="document.querySelectorAll('input[name=ids]').forEach(x=>x.checked=true)">Select all</button><button type="button" class="secondary" onclick="document.querySelectorAll('input[name=ids]').forEach(x=>x.checked=false)">Clear</button></div></form></div><div class="tw"><table><tr><th>Complete?</th><th>Date</th><th>School</th><th>Coach</th><th>Time</th><th></th></tr>{rows}</table></div>'''
   return self.out(page('Past due sessions',b,u))
  if path=='/admin/demographics/preview':
   c.close();pending=os.path.join(DATA_DIR,'demographics_pending.json')
   if not os.path.exists(pending):return self.red('/admin')
   nd=json.load(open(pending,encoding='utf8'));old=load_demo();latest=lambda d:max((int(y) for y in d.get('growth',{}) if str(y).isdigit()),default=2026);ny=latest(nd);oy=latest(old);nt=nd.get('growth',{}).get(str(ny),sum(nd.get('age_totals',{}).values()));ot=old.get('growth',{}).get(str(oy),sum(old.get('age_totals',{}).values()));
   changes=''.join(f'<tr><td>{e(g)}</td><td>{old.get("age_totals",{}).get(g,0)}</td><td>{nd.get("age_totals",{}).get(g,0)}</td><td>{nd.get("age_totals",{}).get(g,0)-old.get("age_totals",{}).get(g,0):+d}</td></tr>' for g in ['U5','U6','U7','U8','U9','U10','U11','U12'])
   warns=''.join(f'<li>{e(x)}</li>' for x in nd.get('warnings',[])) or '<li>No validation warnings.</li>'
   b=f'''<h2>Preview demographics import</h2><div class="grid"><div class="card kpi"><div class="stat">{ot}</div><b>Current players</b><small>{oy}</small></div><div class="card kpi"><div class="stat">{nt}</div><b>Uploaded players</b><small>{ny}</small></div><div class="card kpi"><div class="stat">{nt-ot:+d}</div><b>Change</b><small>players</small></div></div><div class="card"><h3>Age-group changes</h3><div class="tw"><table><tr><th>Age</th><th>Current</th><th>Uploaded</th><th>Change</th></tr>{changes}</table></div></div><div class="card"><h3>Validation</h3><ul>{warns}</ul><p class="muted">Warnings do not block import; review them before confirming.</p></div><div class="card"><form method="post" action="/admin/demographics/confirm"><div class="actions"><button>Confirm import</button><a class="btn secondary" href="/admin">Cancel</a></div></form></div>'''
   return self.out(page('Preview demographics',b,u))
  if path=='/edit':
   s=c.execute('select * from sessions where id=?',(q.get('id',[''])[0],)).fetchone();c.close()
   if not s:return self.red('/schedule')
   b=f'''<h2>Edit session</h2><div class="card"><form method="post"><input type="hidden" name="id" value="{e(s['id'])}"><label>Date</label><input type="date" name="date" value="{e(s['date'])}" required><label>School</label><input name="school" value="{e(s['school'])}" required><label>Coach</label><input name="coach" value="{e(s['coach'])}" required><div class="row"><div><label>Start</label><input type="time" name="start" value="{e(s['start'])}"></div><div><label>End</label><input type="time" name="end" value="{e(s['end'])}"></div></div><label>Class</label><input name="class_group" value="{e(s['class_group'])}"><label>Age group</label><input name="age_group" value="{e(s['age_group'])}"><label>Title</label><input name="title" value="{e(s['title'])}"><div class="actions"><button>Save changes</button></div></form></div>''';return self.out(page('Edit',b,u))
  if path=='/export.csv':
   r=c.execute('select * from sessions order by date,start').fetchall();c.close();o=io.StringIO();w=csv.writer(o);w.writerow(r[0].keys() if r else []);[w.writerow(tuple(x)) for x in r];b=o.getvalue().encode();self.send_response(200);self.send_header('Content-Type','text/csv');self.send_header('Content-Disposition','attachment; filename="eastern-gaels-report.csv"');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
  c.close();return self.out(page('Not found','<div class="card">Page not found.</div>',u),404)
 def do_POST(self):
  global DEMO,COACHING
  p=urlparse(self.path).path
  if p=='/compliance/garda-upload':
   u=self.need()
   if not u:return self.out('Forbidden',403)
   name,data,coach=self.upload_file_with_field('garda_file','coach_name')
   allowed=('.pdf','.jpg','.jpeg','.png')
   if not data or not name or not name.lower().endswith(allowed):return self.out(page('Upload error','<div class="card"><h2>Please choose a PDF, JPG or PNG Garda Vetting form.</h2><a class="btn" href="/compliance">Back</a></div>',u),400)
   if len(data)>15*1024*1024:return self.out(page('Upload error','<div class="card"><h2>File is too large.</h2><p>Maximum size is 15 MB.</p><a class="btn" href="/compliance">Back</a></div>',u),400)
   if coach_key(coach) not in COACHING.get('coaches',{}):return self.out(page('Upload error','<div class="card"><h2>Coach was not recognised.</h2><a class="btn" href="/compliance">Back</a></div>',u),400)
   try:
    uploaded=google_upload_garda_form(name,data,coach)
    file_id=str(uploaded.get('id',''));drive_name=str(uploaded.get('name',''));view_link=str(uploaded.get('webViewLink','')) or ('https://drive.google.com/file/d/'+file_id+'/view' if file_id else '')
    c=dbc();c.execute('insert into garda_forms(coach_key,coach_name,drive_file_id,drive_name,web_view_link,uploaded_at) values(?,?,?,?,?,?) on conflict(coach_key) do update set coach_name=excluded.coach_name,drive_file_id=excluded.drive_file_id,drive_name=excluded.drive_name,web_view_link=excluded.web_view_link,uploaded_at=excluded.uploaded_at',(coach_key(coach),coach,file_id,drive_name,view_link,datetime.now().isoformat(timespec='seconds')));c.commit();c.close()
   except Exception as ex:return self.out(page('Upload error',f'<div class="card"><h2>Could not upload Garda Vetting form</h2><p>{e(ex)}</p><a class="btn" href="/compliance">Back</a></div>',u),500)
   return self.red('/compliance')
  if p=='/admin/coaching-team/upload':
   u=self.need()
   if not u:return self.out('Forbidden',403)
   name,data=self.upload_file('coaching_file')
   if not data or not name.lower().endswith('.xlsx'):return self.out(page('Upload error','<div class="card"><h2>Please choose a valid .xlsx file.</h2><a class="btn" href="/admin">Back</a></div>',u),400)
   tmp=os.path.join(DATA_DIR,'coaching_team_upload.xlsx')
   try:
    open(tmp,'wb').write(data);parsed=parse_coaching_xlsx(tmp);json.dump(parsed,open(COACH_FILE,'w',encoding='utf8'),indent=2);globals()['COACHING']=load_coaching()
   except Exception as ex:return self.out(page('Upload error',f'<div class="card"><h2>Could not read coaching workbook</h2><p>{e(ex)}</p><a class="btn" href="/admin">Back</a></div>',u),400)
   return self.red('/coaching-team')
  if p=='/admin/schools/upload':
   u=self.need()
   if not u:return self.out('Forbidden',403)
   name,data=self.upload_file('schools_file')
   if not data or not name.lower().endswith('.xlsx'):return self.out(page('Upload error','<div class="card"><h2>Please choose a valid .xlsx file.</h2><a class="btn" href="/admin">Back</a></div>',u),400)
   tmp=os.path.join(DATA_DIR,'schools_schedule_upload.xlsx')
   try:
    open(tmp,'wb').write(data);sessions=parse_schools_xlsx(tmp);gpo=parse_gpo_costs_xlsx(tmp)
    c=dbc()
    # Replace timetable fields, but retain dashboard-owned session outcomes.
    locked={}
    for old in c.execute('select * from sessions').fetchall():
     if old['updated_at'] or old['attendance'] is not None or (old['notes'] or '').strip() or old['actual_status']!=old['planned_status']:
      locked[session_sync_key(old)]=(old['actual_status'],old['attendance'],old['notes'],old['updated_at'])
    c.execute('delete from sessions')
    for s in sessions:
     keep=locked.get(session_sync_key(s))
     actual,attendance,notes,updated=(keep if keep else (s['status'],None,None,None))
     c.execute('insert into sessions(id,date,day,school,coach,title,start,end,class_group,age_group,planned_status,actual_status,attendance,notes,updated_at) values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
      (s['id'],s['date'],s['day'],s['school'],s['coach'],s['session'],s['start'],s['end'],s['group'],s['age'],s['status'],actual,attendance,notes,updated))
    c.commit();c.close()
    shutil.copy2(tmp,os.path.join(DATA_DIR,'schools_schedule_current.xlsx'))
    json.dump(gpo,open(GPO_COST_FILE,'w',encoding='utf8'),indent=2,ensure_ascii=False);globals()['GPO_COSTS']=load_gpo_costs()
   except Exception as ex:
    return self.out(page('Upload error',f'<div class="card"><h2>Could not read schools timetable</h2><p>{e(ex)}</p><a class="btn" href="/admin">Back</a></div>',u),400)
   return self.red('/schedule')
  if p=='/admin/demographics/preview':
   u=self.need()
   if not u:return self.out('Forbidden',403)
   name,data=self.upload_file('demographics_file')
   if not data or not name.lower().endswith('.xlsx'):return self.out(page('Upload error','<div class="card"><h2>Please choose a valid .xlsx file.</h2><a class="btn" href="/admin">Back</a></div>',u),400)
   tmp=os.path.join(DATA_DIR,'demographics_upload.xlsx')
   try:
    open(tmp,'wb').write(data)
    parsed=parse_demographics_xlsx(tmp)
    # Save preview copy, but also activate the uploaded workbook immediately.
    # This removes the old two-step state problem where the preview contained
    # the new player but the dashboard continued reading demographics_current.json.
    json.dump(parsed,open(os.path.join(DATA_DIR,'demographics_pending.json'),'w',encoding='utf8'),indent=2,ensure_ascii=False)
    json.dump(parsed,open(DEMO_FILE,'w',encoding='utf8'),indent=2,ensure_ascii=False)
    globals()['DEMO']=load_demo()
    integrated=parsed.get('coaching')
    if integrated:
     json.dump(integrated,open(COACH_FILE,'w',encoding='utf8'),indent=2,ensure_ascii=False)
     globals()['COACHING']=load_coaching()
   except Exception as ex:
    return self.out(page('Upload error',f'<div class="card"><h2>Could not read workbook</h2><p>{e(ex)}</p><a class="btn" href="/admin">Back</a></div>',u),400)
   return self.red('/demographics')
  f=self.form();c=dbc()
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
  if p=='/admin/demographics/confirm':
   pending=os.path.join(DATA_DIR,'demographics_pending.json')
   if os.path.exists(pending):
    hist=os.path.join(DATA_DIR,'demographics_history');os.makedirs(hist,exist_ok=True)
    if os.path.exists(DEMO_FILE):shutil.copy2(DEMO_FILE,os.path.join(hist,'demographics_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.json'))
    else:shutil.copy2(DEMO_SOURCE,os.path.join(hist,'demographics_initial_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.json'))
    os.replace(pending,DEMO_FILE);DEMO=load_demo()
    integrated=DEMO.get('coaching')
    if integrated:
     json.dump(integrated,open(COACH_FILE,'w',encoding='utf8'),indent=2);COACHING=load_coaching()
   c.close();return self.red('/demographics')
  if p=='/session':
   s=c.execute('select * from sessions where id=?',(f.get('id'),)).fetchone()
   if not s:c.close();return self.out('Forbidden',403)
   a=f.get('attendance','');a=int(a) if a.isdigit() else None;c.execute('update sessions set actual_status=?,attendance=?,notes=?,updated_at=? where id=?',(f.get('status'),a,f.get('notes',''),datetime.now().isoformat(timespec='seconds'),f['id']));c.execute('insert into audit(ts,user_email,action,session_id,detail) values(?,?,?,?,?)',(datetime.now().isoformat(timespec='seconds'),u['email'],'update_session',f['id'],f.get('status')));c.commit();c.close();return self.red('/session?id='+f['id'])
  if p=='/admin/past-due':
   ids=f.get('ids',[]);ids=[ids] if isinstance(ids,str) else ids;now=datetime.now();today=now.date().isoformat();clock=now.strftime('%H:%M');changed=0
   for sid in ids:
    r=c.execute("select * from sessions where id=? and actual_status='Scheduled' and (date < ? or (date = ? and coalesce(end,start,'23:59') < ?))",(sid,today,today,clock)).fetchone()
    if r:
     c.execute("update sessions set actual_status='Completed',updated_at=? where id=?",(now.isoformat(timespec='seconds'),sid));c.execute('insert into audit(ts,user_email,action,session_id,detail) values(?,?,?,?,?)',(now.isoformat(timespec='seconds'),u['email'],'bulk_complete_past_due',sid,'Completed'));changed+=1
   c.commit();c.close();return self.red('/admin/past-due')
  if p=='/admin/user' and u['role']=='admin':
   try:c.execute('insert into users(name,email,password,role,coach_name) values(?,?,?,?,?)',(f['name'],f['email'].lower(),hp(f['password']),'full',f.get('coach_name') or None));c.commit()
   except sqlite3.IntegrityError:pass
   c.close();return self.red('/admin')
  if p=='/admin/session':
   sid='s'+secrets.token_hex(5);day=datetime.strptime(f['date'],'%Y-%m-%d').strftime('%A');c.execute('insert into sessions(id,date,day,school,coach,title,start,end,class_group,age_group,planned_status) values(?,?,?,?,?,?,?,?,?,?,?)',(sid,f['date'],day,f['school'],f['coach'],f.get('title'),f.get('start'),f.get('end'),f.get('class_group'),f.get('age_group'),'Confirmed'));c.commit();c.close();return self.red('/session?id='+sid)
  if p=='/edit':
   day=datetime.strptime(f['date'],'%Y-%m-%d').strftime('%A');c.execute('update sessions set date=?,day=?,school=?,coach=?,start=?,end=?,class_group=?,age_group=?,title=?,updated_at=? where id=?',(f['date'],day,f['school'],f['coach'],f.get('start'),f.get('end'),f.get('class_group'),f.get('age_group'),f.get('title'),datetime.now().isoformat(timespec='seconds'),f['id']));c.commit();c.close();return self.red('/session?id='+f['id'])
  c.close();return self.red('/')
if __name__=='__main__':
 init()
 # On a clean V8 install, preload the bundled master workbook automatically.
 bundled=os.path.join(BASE,'eastern gaels demographics (26).xlsx')
 if os.path.exists(bundled) and not os.path.exists(DEMO_FILE):
  try:
   fresh=parse_demographics_xlsx(bundled)
   integrated=fresh.pop('coaching',None)
   with open(DEMO_FILE,'w',encoding='utf8') as f: json.dump(fresh,f,indent=2,ensure_ascii=False)
   if integrated:
    with open(COACH_FILE,'w',encoding='utf8') as f: json.dump(integrated,f,indent=2,ensure_ascii=False)
   DEMO=load_demo();COACHING=load_coaching()
   print('Loaded latest Eastern Gaels workbook data.')
  except Exception as ex:
   print('Workbook preload warning:',ex)
 if GOOGLE_SYNC_ENABLED:
  threading.Thread(target=google_sync_loop,name='google-drive-sync',daemon=True).start()
  print(f'Google Drive auto-sync enabled every {GOOGLE_SYNC_MINUTES} minutes.')
 else:
  print('Google Drive auto-sync disabled.')
 port=int(os.environ.get('PORT','8010'))
 print('*** EASTERN GAELS V8 - RENDER PRODUCTION ***')
 print(f'Open http://localhost:{port}')
 ThreadingHTTPServer(('0.0.0.0',port),H).serve_forever()
