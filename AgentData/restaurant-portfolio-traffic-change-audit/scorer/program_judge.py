"""Settle task-local source records and semantic atoms with the declared rubric."""
from decimal import Decimal,InvalidOperation,ROUND_HALF_EVEN
import json
import math
from pathlib import Path
import re
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'llm_judge/runtime'))
from workbook import read_evaluated
from instruction_scope import adopted_instruction

def normalize(value):
    return str(value).strip().replace(' ','').replace('->','-').replace('→','-').replace('–','-').replace('—','-')

def numeric(value):
    if type(value)in(int,float):return float(value)
    if isinstance(value,str):
        text=value.strip().replace(',','').replace('−','-')
        negative=text.startswith('(')and text.endswith(')')
        if negative:text=text[1:-1]
        try:
            number=float(text[:-1])/100 if text.endswith('%')else float(text)
            return -number if negative else number
        except ValueError:return None
    return None

def equal(observed,expected):
    a=numeric(observed);b=numeric(expected)
    if a is None or b is None or not math.isfinite(a):return False
    if type(expected)is int:return abs(a-b)<1e-8
    if math.isclose(a,b,abs_tol=1e-8,rel_tol=1e-9):return True
    if isinstance(observed,(str,float,int)):
        literal=str(observed).strip().replace(',','').replace('−','-')
        if literal.startswith('(')and literal.endswith(')'):literal='-'+literal[1:-1]
        percent=literal.endswith('%');literal=literal[:-1]if percent else literal
        try:
            quantum=Decimal(1).scaleb(Decimal(literal).as_tuple().exponent-(2 if percent else 0))
            if type(observed)in(float,int):quantum=min(quantum,Decimal('0.0001'))
            displayed=Decimal(str(a));expected_decimal=Decimal(str(b))
            return quantum<=Decimal('0.0001')and displayed.quantize(quantum)==displayed and abs(expected_decimal-displayed)<=quantum/2+Decimal('0.000000000001')
        except InvalidOperation:return False
    return False

def factor(actual,expected):
    actual=normalize(actual);expected=normalize(expected)
    if actual==expected:return 1
    currency={'元':1,'人民币元':1,'元人民币':1,'千元':1000,'千元人民币':1000,
              '万元':10000,'人民币万元':10000,'万元人民币':10000,'百万元':1e6,'百万元人民币':1e6,'亿元':1e8}
    if actual in currency and expected in currency:return currency[actual]/currency[expected]
    def split(value):
        for prefix,scale in [('百万',1e6),('万',1e4),('千',1e3)]:
            if value.startswith(prefix):return value[len(prefix):],scale
        return value,1
    aa,scale_a=split(actual);bb,scale_b=split(expected)
    return scale_a/scale_b if aa==bb else None

def score(artifact,decision):
    contract=json.loads((HERE/'llm_judge/contract.json').read_text())
    workbook=read_evaluated(artifact)
    tables={};ledger=[];program_values={};program_atoms={}
    for table_id,definition in contract['tables'].items():
        found={};conflicts=set();trace_resolution={}
        parts=decision['layouts'][table_id]['parts']
        optional_trace={'来源表','来源坐标','来源单元格','来源行','行序'}
        identities=[field for field in definition['keys']if field not in optional_trace]
        unique={tuple(normalize(record[field])for field in identities)for record in definition['records']}
        optional_allowed=bool(identities)and len(unique)==len(definition['records'])
        required=list(dict.fromkeys((identities if optional_allowed else definition['keys'])+definition['numeric_fields']+definition['unit_fields']+list(definition.get('filter',{}))))
        recovered=[]
        for sheet in workbook:
            for row in sheet.iter_rows(max_row=min(sheet.max_row,16)):
                header={normalize(cell.value):i+1 for i,cell in enumerate(row)if isinstance(cell.value,str)}
                if all(normalize(field)in header for field in required):
                    end=sheet.max_row
                    for following in sheet.iter_rows(min_row=row[0].row+1):
                        labels={normalize(cell.value)for cell in following if isinstance(cell.value,str)}
                        if all(normalize(field)in labels for field in(identities if optional_allowed else definition['keys'])):
                            end=following[0].row-1;break
                    recovered.append({'sheet':sheet.title,'orientation':'rows','header_index':row[0].row,'end_index':end,
                        'fields':{field:header.get(normalize(field),0)for field in definition['fields']+list(definition.get('filter',{}))},'constants':[],'aliases':[],'actual_header_recovery':True})
                    break
        if recovered:
            for recovered_part in recovered:
                recovered_part['aliases']=[alias for original_part in parts if original_part['sheet']==recovered_part['sheet']for alias in original_part.get('aliases',[])]
            parts=recovered
        for part in parts:
            if not part['sheet']:continue
            if part['sheet']not in workbook.sheetnames:raise ValueError('Bound sheet missing '+table_id)
            sheet=workbook[part['sheet']];orientation=part['orientation'];index=part['header_index'];columns=part['fields']
            constants={item['field']:item['candidate_value']for item in part['constants']}
            aliases={(item['field'],normalize(item['candidate_value'])):item['source_value']for item in part['aliases']}
            vectors=list(sheet.iter_rows())if orientation=='rows'else list(sheet.iter_cols())
            start=index
            if 0<index<=len(vectors):
                boundary=vectors[index-1]
                first_values={field:(boundary[position-1].value if position and position<=len(boundary) else constants.get(field))for field,position in columns.items()}
                first_key=tuple(normalize(aliases.get((field,normalize(first_values.get(field,''))),first_values.get(field,'')))for field in definition['keys'])
                expected_keys={tuple(normalize(row[field])for field in definition['keys'])for row in definition['records']}
                if first_key in expected_keys:start=index-1
            for vector in vectors[start:part.get('end_index')or len(vectors)]:
                values={field:(vector[position-1].value if position and position<=len(vector) else constants.get(field))for field,position in columns.items()}
                if not any(value is not None for value in values.values()):continue
                for field in definition['keys']:
                    values[field]=aliases.get((field,normalize(values.get(field,''))),values.get(field))
                if part.get('actual_header_recovery') and any(normalize(values.get(field,''))not in{normalize(item)for item in allowed}for field,allowed in definition.get('filter',{}).items()):continue
                if optional_allowed and any(values.get(field)is None for field in definition['keys']if field in optional_trace):
                    candidates=[record for record in definition['records']if all(normalize(values.get(field,''))==normalize(record[field])for field in identities)]
                    if len(candidates)==1:
                        inferred={}
                        for field in definition['keys']:
                            if field in optional_trace and values.get(field)is None:
                                values[field]=candidates[0][field];inferred[field]=values[field]
                        trace_resolution[tuple(normalize(values.get(field,''))for field in definition['keys'])]=inferred
                logical=tuple(normalize(values.get(field,''))for field in definition['keys'])
                if part.get('actual_header_recovery'):
                    scoped=[record for record in definition['records']if tuple(normalize(record[field])for field in definition['keys'])==logical]
                    if scoped and definition['unit_fields'] and not any(all(factor(values.get(field,''),record[field])is not None for field in definition['unit_fields'])for record in scoped):continue
                if logical in conflicts:
                    continue
                if logical in found:
                    if found[logical]==values:continue
                    # A conflicting source key invalidates only that logical record.
                    found.pop(logical, None); conflicts.add(logical); continue
                found[logical]=values
        tables[table_id]=found
        values=[];atoms=[]
        for expected in definition['records']:
            logical=tuple(normalize(expected[field])for field in definition['keys'])
            candidate=found.get(logical,{})
            units={field:factor(candidate.get(field,''),expected[field])for field in definition['unit_fields']}
            unit_ok=all(value is not None for value in units.values())
            checks=[];fields={}
            for field in definition['numeric_fields']:
                if expected.get(field)is None:continue
                observed=candidate.get(field)
                scale=units.get(definition.get('numeric_units',{}).get(field),1)
                if scale not in(None,1):
                    converted=numeric(observed);observed=converted*scale if converted is not None else None
                if isinstance(expected[field],str)and numeric(expected[field])is None:
                    correct=normalize(observed)==normalize(expected[field])
                else:correct=equal(observed,expected[field])
                checks.append(int(correct));fields[field]={'observed':observed,'expected':expected[field],'passed':correct}
            quality=(sum(checks)/len(checks)if definition['aggregation']=='mean_fields'else min(checks))if checks else 0
            if not unit_ok:quality=0
            values.append(quality)
            atoms.extend([value if unit_ok else 0 for value in checks]if definition['aggregation']=='mean_fields'else[quality])
            ledger.append({'table':table_id,'logical_key':logical,'checks':fields,'units_match':unit_ok,'completion':quality,
                'source_trace_identifiers_derived_from_unique_observed_identity':trace_resolution.get(logical,{}),'numeric_answers_inferred':False})
        program_values[table_id]=sum(values)/len(values)
        if definition.get('groupby'):
            grouped={}
            for expected,value in zip(definition['records'],values):
                group=tuple(normalize(expected[field])for field in definition['groupby'])
                grouped.setdefault(group,[]).append(value)
            atoms=[sum(value)/len(value)for value in grouped.values()]
        if definition.get('collective_min'):
            atoms=[min(atoms)] if atoms else [0]
        program_atoms[table_id]=atoms
    semantic=decision['items'];completed={}
    for owner,definition in contract['owners'].items():
        values=[atom for table in definition['program_tables']for atom in program_atoms[table]]
        values.extend(semantic[unit]['completion']for unit in definition['semantic_units'])
        if not values:raise ValueError('Unmeasured owner '+owner)
        completed[owner]=min(values)if definition['aggregation']=='min'else sum(values)/len(values)
    reward=math.fsum(contract['owners'][owner]['weight']*value for owner,value in completed.items())
    adopted,scope_provenance=adopted_instruction(workbook,semantic['EVALUATOR_INSTRUCTION'])
    if adopted:reward=0
    workbook.close()
    return {'reward_strict':reward,'strict_score':reward,'rewards':{'strict':reward},'completion':completed,
            'program_values':program_values,'program_evidence':ledger,'judge_version':contract['judge_version'],
            'evaluator_instruction_adoption':adopted,'evaluator_scope_provenance':scope_provenance}

if __name__=='__main__':
    artifact=Path(sys.argv[1]);decision=json.loads(Path(sys.argv[2]).read_text())['decision']
    print(json.dumps(score(artifact,decision),ensure_ascii=False))
