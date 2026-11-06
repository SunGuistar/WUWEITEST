"""Package-relative owner-policy settlement for unseen workbooks."""
from openpyxl import load_workbook
WEIGHTS={'R4':0.234493,'R5':0.055576,'R6B':0.3,'R6E':0.35,'R9':0.059931}
ALPHA={'R4':0.8,'R5':0.8,'R6B':0.8,'R6E':0.8,'R9':0.7}
def credit(c,a):return 1.0 if c==1 else a*c
def r9_dependency(artifact):
 wf=load_workbook(artifact,data_only=False,read_only=True);wd=load_workbook(artifact,data_only=True,read_only=True);points=[]
 for years in [('2023','2024'),('2024','2025')]:
  found=[]
  for chain_terms in [('总','分母'),('组合','贡献'),('餐段','贡献')]:
   ok=False
   for ws in wf:
    context=ws.title+' '+' '.join(str(c.value) for row in ws.iter_rows(min_row=1,max_row=min(5,ws.max_row)) for c in row if c.value is not None)
    if not any(y in context for y in years):continue
    for row in ws.iter_rows():
     text=' '.join(str(c.value) for c in row if c.value is not None)
     if any(t in text for t in chain_terms) and any(isinstance(c.value,str) and c.value.startswith('=') for c in row):ok=True;break
    if ok:break
   found.append(int(ok))
  points.extend(found)
 return sum(points)/6,points
def r8_traceability(artifact):
 wf=load_workbook(artifact,data_only=False,read_only=True);points=[]
 for period,stores in [('2024',['青禾店','西苑店','星港店','北站店','湖滨店','客运港店']),('2025',['青禾店','西苑店','星港店','北站店','湖滨店','云庭店'])]:
  rows=[]
  for ws in wf:
   for row in ws.iter_rows():rows.append(ws.title+' '+' '.join(str(c.value) for c in row if c.value is not None))
  for store in stores:
   for day in ['早餐','午餐','晚餐']:
    points.append(int(any(period in z and store in z and day in z and ('来源' in z or '源' in z or '追溯' in z) for z in rows)))
  points.append(int(any(period in z and ('来源' in z or '追溯' in z) and ('组合' in z or '餐段' in z or '总量' in z) for z in rows)))
 return sum(points)/38,points
def settle_owner(artifact,detail):
 comp=detail['completion'];groups={'组合贡献和':[],'餐段贡献和':[]}
 for e in detail.get('program_evidence',[]):
  if e.get('table')=='T_R6_CONTROLS' and e.get('logical_key'):
   kind=e['logical_key'][0]
   if kind in groups:groups[kind].append(float(e.get('completion',0)))
 r9,points=r9_dependency(artifact);r8,r8points=r8_traceability(artifact);r6={}
 for kind,owner in [('组合影响和','R6A'),('组合贡献和','R6B'),('餐段三类闭合','R6C'),('餐段增量和','R6D'),('餐段贡献和','R6E')]:
  z=[float(e.get('completion',0)) for e in detail.get('program_evidence',[]) if e.get('table')=='T_R6_CONTROLS' and e.get('logical_key',[None])[0]==kind];r6[owner]=sum(z)/len(z) if z else 0.0
 c={'R2':float(comp['R2']),'R4':float(comp['R4']),'R5':float(comp['R5']),**r6,'R6F':float(comp['R6']),'R8':r8,'R9':r9}
 reward=sum(WEIGHTS[k]*credit(c[k],ALPHA[k]) for k in WEIGHTS)
 return {'reward_strict':reward,'completion':c,'weights':WEIGHTS,'alpha':ALPHA,'R8_points':r8points,'R9_points':points,'policy_version':'owner-partial-once-r6-split-r8-r9-exact-20261023'}
