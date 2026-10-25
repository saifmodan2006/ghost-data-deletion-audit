"""Evidence-grounded, point-in-time deletion auditor. No sample labels at inference."""
from __future__ import annotations
import csv
import json
import re
import sqlite3
import hashlib
import unicodedata
from functools import lru_cache
from datetime import datetime, timedelta
from dataclasses import dataclass, replace
from pathlib import Path
from collections import defaultdict

def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))

def norm(value):
    return ' '.join(unicodedata.normalize('NFKC',str(value)).split()).casefold()

@lru_cache(maxsize=50000)
def value_tokens(value):
    value=norm(value)
    tokens={value}
    tokens.update(re.findall(r'[\w.+-]+@[\w.-]+|\buser_\d+\b|\b[a-f0-9]{64}\b',value))
    for phone in re.findall(r'\+\d[\d ()\u00a0.-]{6,}\d',value):
        digits=re.sub(r'\D','',phone)
        if 8<=len(digits)<=15:tokens.add('phone:'+digits)
    return frozenset(tokens)

def identity_tokens(raw):
    result=set()
    for value in leaves(raw):result.update(value_tokens(value))
    return result

def subject_references(raw):
    """Authoritative subject fields, excluding lookup keys and free-form prose."""
    result=set()
    if isinstance(raw,dict):
        for key,value in raw.items():
            if key in ('user_id','customer_reference','subject_reference','subject_ref') and isinstance(value,str) and re.fullmatch(r'user_\d+',value):result.add(norm(value))
            elif isinstance(value,(dict,list)):result.update(subject_references(value))
    elif isinstance(raw,list):
        for item in raw:result.update(subject_references(item))
    return result

def leaves(obj):
    if isinstance(obj, dict):
        for value in obj.values():
            yield from leaves(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from leaves(value)
    elif obj is not None:
        yield str(obj)

COLLECTIONS = {
    'customer_profiles': ('account_service', 'USER_PROFILE'),
    'customer_search_documents': ('search_service', 'SEARCH_INDEX_ENTRY'),
    'customer_analytics_reports': ('analytics_platform', 'ANALYTICS_PROFILE'),
    'customer_analytics_profiles': ('analytics_platform', 'ANALYTICS_PROFILE'),
    'support_conversations': ('support_platform', 'SUPPORT_MESSAGE'),
    'support_records': ('support_platform', 'SUPPORT_MESSAGE'),
    'ticket_attachments': ('support_platform', 'SUPPORT_ATTACHMENT'),
    'customer_export_jobs': ('export_service', 'USER_EXPORT'),
    'customer_exports': ('export_service', 'USER_EXPORT'),
    'connector_configurations': ('integration_service', 'DATA_FLOW'),
    'connector_subscriptions': ('integration_service', 'DATA_FLOW'),
    'backup_catalog': ('backup_service', 'BACKUP_ARCHIVE'),
    'backup_restore_entries': ('backup_service', 'BACKUP_ARCHIVE'),
    'security_audit_events': ('security_service', 'SECURITY_AUDIT_LOG'),
    'security_audit_records': ('security_service', 'SECURITY_AUDIT_LOG'),
    'deleted_customer_references': ('identity_service', 'ACCOUNT_TOMBSTONE'),
    'retained_order_records': ('legal_service', 'LEGAL_HOLD_RECORD'),
    'legal_hold_records': ('legal_service', 'LEGAL_HOLD_RECORD'),
    'cache_entries': ('cache_service', 'CACHE_ENTRY'),
    'secondary_identifiers': ('identity_service', 'SECONDARY_IDENTIFIER'),
    'product_telemetry': ('telemetry_service', 'PRODUCT_TELEMETRY'),
    'marketing_profiles': ('marketing_platform', 'MARKETING_PROFILE'),
    'email_delivery_logs': ('notification_service', 'EMAIL_DELIVERY_LOG'),
}
PREFIXES = {'account': ('account_service','USER_PROFILE'), 'search':('search_service','SEARCH_INDEX_ENTRY'),
    'analytics':('analytics_platform','ANALYTICS_PROFILE'), 'support':('support_platform','SUPPORT_MESSAGE'),
    'export':('export_service','USER_EXPORT'), 'data_flow':('integration_service','DATA_FLOW'),
    'backup':('backup_service','BACKUP_ARCHIVE'), 'audit_record':('security_service','SECURITY_AUDIT_LOG'),
    'legal_hold':('legal_service','LEGAL_HOLD_RECORD'), 'tombstone':('identity_service','ACCOUNT_TOMBSTONE'),
    'marketing':('marketing_platform','MARKETING_PROFILE'), 'object':('object_storage','SUPPORT_ATTACHMENT'),
    'cache':('cache_service','CACHE_ENTRY'), 'telemetry':('telemetry_service','PRODUCT_TELEMETRY'),
    'secondary_identifier':('identity_service','SECONDARY_IDENTIFIER'), 'email_log':('notification_service','EMAIL_DELIVERY_LOG')}

def metadata(resource, collection=''):
    if collection in COLLECTIONS:
        return COLLECTIONS[collection]
    for prefix in sorted(PREFIXES, key=len, reverse=True):
        if resource.startswith(prefix+'_'):
            return PREFIXES[prefix]
    return '', ''

def nonempty(v):
    return v is not None and norm(v) not in ('', 'null', 'none', '[redacted]', 'redacted', 'n/a', '-')

def pii(obj, include_reference=False):
    """Inspect stored fields, never query selectors or observation metadata."""
    if not isinstance(obj, dict):
        return False
    direct = ('email','phone','full_name','display_name','requester_name','customer_name','recipient_name','owner_name','contact_name','email_hash','matched_value','correlation_key')
    refs = ('user_id','customer_reference','subject_reference','subject_ref')
    for key,value in obj.items():
        if key in ('query','lookup_key','match_key','subject_key','resource_id','observed_at','updated_at','recorded_at'):
            continue
        if isinstance(value,dict):
            if pii(value,include_reference): return True
        elif isinstance(value,list):
            if any(pii(x,include_reference) for x in value): return True
        elif nonempty(value):
            if key in ('message_text','message_excerpt','body','text'):
                if re.search(r'[\w.+-]+@[\w.-]+|\+\d[\d ()-]{6,}\d|\b[a-fA-F0-9]{64}\b',str(value)):
                    return True
            elif key=='name' or any(token in key for token in direct) or (include_reference and key in refs):
                return True
    return False

@dataclass
class Observation:
    system: str
    resource: str
    category: str
    state: str
    at: str
    available: str
    evidence: str
    raw: dict
    rank: int = 2

class Auditor:
    def __init__(self, dataset, cache=None):
        self.dataset=Path(dataset)
        self.cache=Path(cache or self.dataset.parent/'.audit_cache')
        self.cache.mkdir(parents=True,exist_ok=True)
        self.identities=read_csv(self.dataset/'user_identities.csv')
        self.identities_by_id={row['user_id']:row for row in self.identities}
        self.history=read_csv(self.dataset/'user_audit_log.csv')
        self.history_by_field=defaultdict(list)
        for row in self.history:self.history_by_field[(row['user_id'],row['field_name'])].append(row)
        self.activities=read_csv(self.dataset/'system_activity.csv')
        self.rules={r['data_category']:r['required_action'] for r in read_csv(self.dataset/'deletion_rules.csv')}
        self.observations=[]
        self.scopes=[]
        self.extraction=[]
        self.ocr_calls=0
        self.ocr_cache_hits=0
        self.model_calls=defaultdict(int)
        self.diagnostics={}
        self._ocr=None
        for entry in read_csv(self.dataset/'evidence_files.csv'):
            self.ingest(entry)
        self.observation_index=defaultdict(set)
        self.observations_by_resource=defaultdict(list)
        for i,observation in enumerate(self.observations):
            for token in identity_tokens(observation.raw):self.observation_index[token].add(i)
            self.observations_by_resource[(observation.system,observation.resource)].append(i)
        self.activity_index=defaultdict(set)
        for i,activity in enumerate(self.activities):
            for token in identity_tokens(activity['details']):self.activity_index[token].add(i)

    def add(self, row, entry, at=None, system='', category='', state='', collection='', rank=2):
        resource=row.get('resource_id','')
        if not resource: return
        default_system,default_category=metadata(resource,collection)
        system=system or row.get('system_id') or row.get('origin_system') or row.get('system') or row.get('data_store') or default_system
        category=category or row.get('record_type') or row.get('data_category') or row.get('category') or default_category
        if not category: return
        at=at or row.get('observed_at') or row.get('recorded_at') or row.get('captured_at') or row.get('event_time') or entry['captured_at']
        result=row.get('result',row.get('state',''))
        if not state and result in ('FOUND','NOT_FOUND','PRESENT','ABSENT','IDENTIFIABLE','ANONYMIZED','REDACTED','ACTIVE','DISABLED','BLOCKED'):
            state={'FOUND':'PRESENT','NOT_FOUND':'ABSENT'}.get(result,result)
        if not state:
            if category=='DATA_FLOW': state='ACTIVE' if row.get('enabled') in (True,1,'true','1') else 'DISABLED'
            elif category=='BACKUP_ARCHIVE': state='ACTIVE' if row.get('restore_allowed') in (True,1,'true','1') else 'BLOCKED'
            elif category=='USER_PROFILE' and (row.get('status_code') in (404,'404') or row.get('rows') in (0,'0')): state='ABSENT'
            elif category=='SEARCH_INDEX_ENTRY' and (row.get('hits',{}).get('total')==0 or row.get('total_hits') in (0,'0') or result=='miss'): state='ABSENT'
            elif category in ('SUPPORT_MESSAGE','EMAIL_DELIVERY_LOG','ACCOUNT_TOMBSTONE'): state='IDENTIFIABLE' if pii(row) else 'REDACTED'
            elif category in ('ANALYTICS_PROFILE','PRODUCT_TELEMETRY'): state='IDENTIFIABLE' if pii(row,True) else 'ANONYMIZED'
            else: state='PRESENT'
        self.observations.append(Observation(system,resource,category,state,at,entry['captured_at'],entry['file_id'],row,rank))

    def ingest(self, entry):
        path=(self.dataset/entry['file_path']).resolve()
        if not path.is_relative_to(self.dataset.resolve()):
            raise ValueError('Evidence path outside dataset')
        before=len(self.observations)
        if path.suffix=='.json': self.parse_json(json.loads(path.read_text(encoding='utf-8')),entry)
        elif path.suffix=='.sql': self.parse_sql(path.read_text(encoding='utf-8'),entry)
        elif path.suffix=='.log': self.parse_log(path.read_text(encoding='utf-8'),entry)
        elif path.suffix=='.txt': self.parse_text(path.read_text(encoding='utf-8'),entry)
        elif path.suffix=='.pdf':
            from pypdf import PdfReader
            text='\n'.join(page.extract_text() or '' for page in PdfReader(path).pages)
            (self.cache/(entry['file_id']+'.txt')).write_text(text,encoding='utf-8')
            self.parse_document(text,entry)
        elif path.suffix=='.png': self.parse_image(path,entry)
        else: raise ValueError(f'Unsupported evidence: {path}')
        self.extraction.append((entry['file_id'],path.name,len(self.observations)-before))

    def parse_json(self, doc, entry):
        for snapshot in doc.get('snapshots',[]):
            system=snapshot.get('data_store','')
            collection=snapshot.get('collection','')
            at=snapshot.get('captured_at',entry['captured_at'])
            records=snapshot.get('records',[])
            self.scopes.append((system,collection,at,entry['captured_at'],entry['file_id'],{r.get('resource_id') for r in records}))
            for row in records:self.add(row,entry,row.get('recorded_at',at),system=row.get('system',system),collection=collection)
        for row in doc.get('records',[]): self.add(row,entry,collection=doc.get('collection',''))
        for system,groups in doc.get('service_exports',{}).items():
            for group,records in groups.items():
                for row in records:
                    self.add(row,entry,system=system)

    def parse_sql(self, sql, entry):
        # A private in-memory connection; never execute evidence against a real DB.
        db=sqlite3.connect(':memory:')
        db.row_factory=sqlite3.Row
        def authorizer(action,a,b,c,d):
            if action in (sqlite3.SQLITE_ATTACH,sqlite3.SQLITE_DETACH):return sqlite3.SQLITE_DENY
            if action==sqlite3.SQLITE_FUNCTION and (b or '').lower() in ('load_extension','writefile','readfile'):return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        db.set_authorizer(authorizer)
        db.executescript(sql)
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for table in tables:
            if not re.fullmatch(r'\w+',table):raise ValueError('Unsafe table name')
            rows=[dict(r) for r in db.execute('SELECT * FROM "'+table+'"')]
            if table=='snapshot_scope':continue
            if rows and 'record_json' in rows[0]:
                groups=defaultdict(list)
                for row in rows:
                    raw=json.loads(row['record_json'])
                    self.add(raw,entry,system=row['origin_system'],collection=row['collection_name'],rank=3)
                    groups[(row['origin_system'],row['collection_name'])].append(raw['resource_id'])
                for (system,collection),ids in groups.items():self.scopes.append((system,collection,entry['captured_at'],entry['captured_at'],entry['file_id'],set(ids)))
            else:
                collection=table
                if table.startswith('customer_profiles'):collection='customer_profiles'
                if table.startswith('search_documents'):collection='customer_search_documents'
                system,category=COLLECTIONS.get(collection,('',''))
                if not category: continue
                self.scopes.append((system,collection,entry['captured_at'],entry['captured_at'],entry['file_id'],{r['resource_id'] for r in rows}))
                for row in rows:self.add(row,entry,system=system,collection=collection,rank=3)
        db.close()

    def parse_text(self,text,entry):
        for line in text.splitlines():
            m=re.match(r'- (\S+) \| (\S+) \| (\S+) \| (\S+) \| (\S+) \| (.*)',line)
            if m:
                at,system,resource,category,result,subject=m.groups()
                self.add(dict(resource_id=resource,subject_reference=subject,result=result),entry,at,system,category)

    def parse_log(self,text,entry):
        traces=defaultdict(dict)
        for line in text.splitlines():
            at_match=re.search(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ',line)
            if not at_match:continue
            at=at_match[0]
            # Cloud function logs quote an entire nested key/value message.
            line=line.replace('\\"','"')
            if '{' in line:
                try: row=json.loads(line[line.index('{'):])
                except ValueError:continue
            else:
                row={m[1]:m[2] if m[2] is not None else m[3] for m in re.finditer(r'(\w+)=(?:"([^"]*)"|([^\s]+))',line)}
                cloud=re.search(r'requestId=(\S+).*?function=(\S+)',line)
                bracket=re.search(r'\[\w+\] \[([^\]]+)\] \[([^\]]+)\] (\w+):',line)
                pipe=re.search(r'\| \w+ \| (\S+) \| (\S+) \| (\w+) \|',line)
                syslog=re.search(r'<\d+>1 \S+ (\S+) (\S+) - -',line)
                if cloud:
                    row['trace_id'],row['service']=cloud.groups()
                    # Reparse nested content after removing the message wrapper.
                    nested=line.split('message="',1)[-1].rstrip('"')
                    row.update({m[1]:m[2] if m[2] is not None else m[3] for m in re.finditer(r'(\w+)=(?:"([^"]*)"|([^\s]+))',nested)})
                elif bracket:row['service'],row['trace_id'],row['event']=bracket.groups()
                elif pipe:row['service'],row['trace_id'],row['event']=pipe.groups()
                elif syslog:row['service'],row['trace_id']=syslog.groups()
            trace=row.get('trace_id','')
            if trace:
                traces[trace].update(row)
                row=dict(traces[trace])
            event=row.get('event','')
            resource=row.get('resource_id','')
            if not resource:continue
            system=row.get('system') or row.get('service','')
            category=row.get('record_type','')
            state=''
            if event=='record_lookup':pass
            elif event=='profile_lookup_completed':state='ABSENT' if row.get('rows') in ('0',0) else 'PRESENT'
            elif event=='index_query_completed':state='ABSENT' if row.get('result')=='miss' or row.get('total_hits')=='0' else 'PRESENT'
            elif event in ('message_pii_scan','attachment_pii_scan'):state='IDENTIFIABLE' if event=='message_pii_scan' else 'PRESENT'
            elif event in ('analytics_profile_read','analytics_profile_read_completed','analytics_identity_scan'):pass
            elif event in ('contact_lookup_completed','contact_query_completed'):category='SECONDARY_IDENTIFIER' if resource.startswith('support_') else 'MARKETING_PROFILE';state='PRESENT'
            elif event=='connector_heartbeat':state='ACTIVE'
            elif event=='connector_config_read_completed':pass
            elif event in ('restore_candidate_evaluated','restore_policy_read_completed'):state='ACTIVE' if row.get('restore_allowed') in ('true','1') or row.get('eligible') in ('true','1') else 'BLOCKED'
            elif event in ('audit_record_read_completed','export_download_check_completed','export_metadata_read_completed'):state='PRESENT'
            elif event=='support_ticket_read_completed':pass
            else:continue
            if event=='audit_record_read_completed' and not category:category='SECURITY_AUDIT_LOG'
            if system=='support_replica':system='support_platform'
            self.add(row,entry,at,system,category,state)

    def parse_document(self,text,entry):
        # Shared pipe-delimited extraction used by business registers.
        self.parse_text(text,entry)
        lines=text.splitlines()
        for line in lines:
            parts=[p.strip() for p in line.split('|')]
            if len(parts)>=5 and re.fullmatch(r'\w+_\d+',parts[0]):
                resource,system,category,result=parts[:4]
                self.add(dict(resource_id=resource,result=result,subject_reference=' '.join(parts[4:])),entry,system=system,category=category)
        # Explicit identifiers in natural business documents, with catalog joins
        # for external statement/attachment references.
        category=''
        if 'DELIVERY ADDRESS CORRECTION REQUEST' in text:category='SUPPORT_ATTACHMENT'
        elif 'COMPLIANCE JOURNAL' in text:category='SECURITY_AUDIT_LOG'
        elif 'CUSTOMER STATEMENT' in text:category='USER_EXPORT'
        if category:
            resources=set(re.findall(r'\b(?:support|audit_record|export)_\d+\b',text))
            for activity in self.activities:
                if activity['event_type']=='LINK_RESOURCE_IDENTITY':
                    external=re.search(r'\(([^)]+)\)',activity['details'])
                    if external and external[1] in text:resources.add(activity['resource_id'])
            for resource in resources:
                system,_=metadata(resource)
                self.add(dict(resource_id=resource,document_text=text),entry,system=system,category=category,state='PRESENT')

    def parse_image(self,path,entry):
        key=hashlib.sha256(path.read_bytes()).hexdigest()
        target=self.cache/(key+'.ocr.json')
        if target.exists():
            lines=json.loads(target.read_text(encoding='utf-8'))
            self.ocr_cache_hits+=1
        else:
            from rapidocr_onnxruntime import RapidOCR
            if self._ocr is None:
                self._ocr=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=2)
                models=[('ch_PP-OCRv4_det_infer',self._ocr.text_det.infer.session),('ch_ppocr_mobile_v2.0_cls_infer',self._ocr.text_cls.infer.session),('ch_PP-OCRv4_rec_infer',self._ocr.text_rec.session.session)]
                for name,session in models:
                    original=session.run
                    def counted(*args,_name=name,_original=original,**kwargs):
                        self.model_calls[_name]+=1
                        return _original(*args,**kwargs)
                    session.run=counted
            result,_=self._ocr(str(path))
            self.ocr_calls+=1
            lines=result or []
            target.write_text(json.dumps(lines),encoding='utf-8')
        text='\n'.join(x[1] for x in lines)
        (self.cache/(entry['file_id']+'.txt')).write_text(text,encoding='utf-8')
        surface={
            'account_admin_portal':('account_service','USER_PROFILE','account'),
            'search_index_admin':('search_service','SEARCH_INDEX_ENTRY','search'),
            'integration_admin':('integration_service','DATA_FLOW','data_flow'),
            'analytics_platform':('analytics_platform','ANALYTICS_PROFILE','analytics'),
            'export_service':('export_service','USER_EXPORT','export'),
            'support_platform':('support_platform','SUPPORT_MESSAGE','support'),
            'backup_service':('backup_service','BACKUP_ARCHIVE','backup'),
            'security_service':('security_service','SECURITY_AUDIT_LOG','audit_record'),
            'identity_service':('identity_service','ACCOUNT_TOMBSTONE','tombstone'),
            'object_storage':('object_storage','SUPPORT_ATTACHMENT','object'),
            'marketing_platform':('marketing_platform','MARKETING_PROFILE','marketing'),
        }
        if entry['origin'] not in surface:raise ValueError('Unknown image surface '+entry['origin'])
        system,category,prefix=surface[entry['origin']]
        resources=set(re.findall(r'\b'+prefix+r'_\d+\b',text))
        for activity in self.activities:
            if activity['event_type']=='LINK_RESOURCE_IDENTITY':
                external=re.search(r'\(([^)]+)\)',activity['details'])
                if external and external[1] in text and activity['target_system']==system:
                    resources.add(activity['resource_id'])
        # Row-aligned OCR preserves associations and prevents adjacent decoy
        # customers in tables from contaminating the selected subject.
        for resource in resources:
            positions=[sum(p[1] for p in box)/4 for box,value,score in lines if resource in value]
            row_text='\n'.join(value for box,value,score in lines if any(abs(sum(p[1] for p in box)/4-y)<14 for y in positions))
            identifiers=re.findall(r'[\w.+-]+@[\w.-]+|\buser_\d+\b',row_text)
            if not identifiers:
                # Single-record detail screens have identity fields in cards.
                if len(resources)==1:row_text=text
                else:continue
            raw=dict(resource_id=resource,screen_text=row_text)
            state='ACTIVE' if category in ('DATA_FLOW','BACKUP_ARCHIVE') else 'IDENTIFIABLE' if category in ('ANALYTICS_PROFILE','SUPPORT_MESSAGE','ACCOUNT_TOMBSTONE') else 'PRESENT'
            if category=='ACCOUNT_TOMBSTONE' and not re.search(r'[\w.+-]+@[\w.-]+|\+\d[\d ()-]{6,}',text):state='REDACTED'
            self.add(raw,entry,system=system,category=category,state=state)

    @lru_cache(maxsize=1024)
    def aliases_at(self,cutoff):
        aliases=defaultdict(set)
        for row in self.identities:
            uid=row['user_id'];aliases[uid].add(norm(uid))
            for key in ('name','email','phone','email_hash'):
                value=row[key]
                if row['updated_at']>cutoff:
                    changes=sorted((h for h in self.history_by_field[(uid,key)] if h['event_time']>cutoff),key=lambda h:h['event_time'],reverse=True)
                    for h in changes:value=h['old_value']
                if value:aliases[uid].update(value_tokens(value))
        for row in self.history:
            if row['event_time']<=cutoff:
                for key in ('old_value','new_value'):
                    if row[key]:aliases[row['user_id']].update(value_tokens(row[key]))
        return aliases

    @staticmethod
    def matches(raw,aliases):
        return not identity_tokens(raw).isdisjoint(aliases)

    def audit(self,request):
        if not deletion_intent(request['request_text']):return {'case_id':request['case_id'],'deletion_status':'NOT_APPLICABLE','steps_json':'[]'}
        cutoff=request['audit_at']
        aliases=self.aliases_at(cutoff)
        users=[u for u,a in aliases.items() if norm(request['email']) in a]
        if len(users)!=1:raise ValueError(f"Ambiguous or missing subject for {request['case_id']}")
        subject=set(aliases[users[0]])
        shared=set().union(*(values&subject for uid,values in aliases.items() if uid!=users[0]))
        subject.difference_update(shared)
        valid_indices={i for i,o in enumerate(self.observations) if o.at<=cutoff and o.available<=cutoff}
        observations=[self.observations[i] for i in valid_indices]
        hits=set().union(*(self.observation_index.get(token,set()) for token in subject))&valid_indices
        weak_hits=set().union(*(self.observation_index.get(token,set()) for token in shared))&valid_indices
        ambiguous_identity=any(not subject_references(self.observations[i].raw) for i in weak_hits-hits)
        # A shared name/phone must not override an explicit different subject.
        hits={i for i in hits if not subject_references(self.observations[i].raw) or norm(users[0]) in subject_references(self.observations[i].raw) or self.observations[i].category in ('SUPPORT_MESSAGE','EMAIL_DELIVERY_LOG')}
        relevant={(self.observations[i].system,self.observations[i].resource) for i in hits}
        activity_hits=set().union(*(self.activity_index.get(token,set()) for token in subject))
        for i in activity_hits:
            a=self.activities[i]
            if a['event_time']<=cutoff:
                relevant.add((a['target_system'],a['resource_id']))
        # Traverse explicit cross-resource references (for example a search
        # document's source_resource_id) to recover deleted source profiles.
        changed=True
        while changed:
            linked=set()
            for o in observations:
                if (o.system,o.resource) in relevant:
                    for value in leaves(o.raw):
                        for resource in re.findall(r'\b(?:account|search|analytics|support|export|data_flow|backup|audit_record|legal_hold|tombstone|object|marketing)_\d+\b',value):
                            system,category=metadata(resource)
                            if system:linked.add((system,resource))
            changed=bool(linked-relevant)
            relevant.update(linked)
        # Legacy operation logs omit subjects. Use a narrow workflow completion
        # window only to discover resource candidates; never as proof of state.
        reported=datetime.fromisoformat(request['reported_at'].replace('Z','+00:00'))
        lower=(reported-timedelta(minutes=15)).isoformat().replace('+00:00','Z')
        upper=(reported+timedelta(minutes=15)).isoformat().replace('+00:00','Z')
        has_profile=any(metadata(resource)[1]=='USER_PROFILE' for system,resource in relevant)
        fallback=[]
        for a in self.activities:
            if lower<=a['event_time']<=min(upper,cutoff) and a['source_system']=='deletion_worker' and a['event_type'] in ('DELETE_RECORD','ANONYMIZE_RECORD','REDACT_RECORD'):
                key=(a['target_system'],a['resource_id'])
                resource_indices=set(self.observations_by_resource.get(key,[]))&valid_indices
                owner_observations=resource_indices&hits
                other_owner=any(any(re.fullmatch(r'user_\d+',v) and norm(v) not in subject for v in leaves(self.observations[i].raw)) for i in resource_indices)
                if owner_observations:relevant.add(key)
                elif not other_owner and not has_profile and not relevant:fallback.append(a)
        if fallback:
            # Only one nearest event, never every unrelated job in a window.
            nearest=min(fallback,key=lambda a:abs((datetime.fromisoformat(a['event_time'].replace('Z','+00:00'))-reported).total_seconds()))
            relevant.add((nearest['target_system'],nearest['resource_id']))
        selected={}
        conflicting_subjects=[]
        subject_scopes={(o.evidence,o.at) for o in observations if (o.system,o.resource) in relevant}
        for key in relevant:
            candidates=[self.observations[i] for i in self.observations_by_resource.get(key,[]) if i in valid_indices]
            has_direct_candidates=bool(candidates)
            # A full profile snapshot can prove absence of a previously identified row.
            for system,collection,at,available,evidence,ids in self.scopes:
                if system==key[0] and at<=cutoff and available<=cutoff and key[1] not in ids and ((evidence,at) in subject_scopes or not has_direct_candidates):
                    default_system,category=metadata(key[1],collection)
                    if category=='USER_PROFILE' and key[1].startswith('account_'):
                        candidates.append(Observation(system,key[1],category,'ABSENT',at,available,evidence,{},1))
            if not candidates:continue
            # At equal snapshot time any surviving replica is a violation.
            def severity(o):return o.state in ('PRESENT','IDENTIFIABLE','ACTIVE')
            latest=max(candidates,key=lambda o:(o.at,o.rank,severity(o),o.available,o.evidence))
            refs=subject_references(latest.raw)
            if refs and norm(users[0]) not in refs and latest.category not in ('SUPPORT_MESSAGE','EMAIL_DELIVERY_LOG'):
                conflicting_subjects.append(latest.resource)
                continue
            selected[key]=latest
        # A record already compliant before this request is not a current
        # remediation dependency. Keep surviving/active historical copies, and
        # include previously compliant resources only when a later write could
        # have recreated identifying data.
        stale=[]
        recreating={'SYNC_RECORD','INDEX_RECORD','UPDATE_RECORD','CREATE_EXPORT','RESTORE_BACKUP','REFRESH_CACHE'}
        for key,o in selected.items():
            if o.at<request['requested_at'] and o.state in ('ABSENT','REDACTED','ANONYMIZED','DISABLED','BLOCKED'):
                later_write=any(a['resource_id']==o.resource and a['target_system']==o.system and request['requested_at']<=a['event_time']<=cutoff and a['event_type'] in recreating for a in self.activities)
                if not later_write:stale.append(key)
        excluded_stale=len(stale) if len(stale)<len(selected) else 0
        if excluded_stale:
            for key in stale:del selected[key]
        unsupported_current=[]
        for key,o in selected.items():
            if o.state in ('ABSENT','REDACTED','ANONYMIZED','DISABLED','BLOCKED') and any(a['resource_id']==o.resource and a['target_system']==o.system and o.at<a['event_time']<=cutoff and a['event_type'] in recreating for a in self.activities):unsupported_current.append(o.resource)
        subject_name=norm(self.identities_by_id[users[0]]['name'])
        if subject_name:
            def named_in_body(raw):
                if isinstance(raw,dict):
                    for key,value in raw.items():
                        if key in ('message_text','message_excerpt','body','text') and isinstance(value,str) and re.search(r'(?<!\w)'+re.escape(subject_name)+r'(?!\w)',norm(value)):return True
                        if isinstance(value,(dict,list)) and named_in_body(value):return True
                elif isinstance(raw,list):return any(named_in_body(value) for value in raw)
                return False
            for key,o in selected.items():
                if o.state=='REDACTED' and o.category in ('SUPPORT_MESSAGE','EMAIL_DELIVERY_LOG','ACCOUNT_TOMBSTONE') and named_in_body(o.raw):selected[key]=replace(o,state='IDENTIFIABLE')
        findings=[];remediation=[];verification=[]
        for observation in selected.values():
            finding,remedy,verify=self.policy(observation)
            if finding:findings.append(step('FINDING',observation,finding,observation.evidence))
            if remedy:remediation.append(step('REMEDIATION',observation,remedy,''))
            if verify:verification.append(step('VERIFICATION',observation,verify,observation.evidence))
        status='INCOMPLETE' if findings else 'COMPLETE'
        if not selected:raise ValueError(f"No evidence for {request['case_id']}")
        if findings:
            for item in verification:item['evidence_id']=''
        steps=sorted(findings+remediation+verification,key=step_key)
        for i,item in enumerate(steps,1):item['step_no']=i
        has_profile_evidence=any(o.category=='USER_PROFILE' for o in selected.values())
        review_reasons=[]
        if not has_profile_evidence:review_reasons.append('MISSING_PROFILE_PROOF')
        if fallback:review_reasons.append('TEMPORAL_IDENTITY_HEURISTIC')
        if unsupported_current:review_reasons.append('LATER_WRITE_WITHOUT_READBACK')
        if conflicting_subjects:review_reasons.append('CONFLICTING_SUBJECT_EVIDENCE')
        if ambiguous_identity:review_reasons.append('AMBIGUOUS_SHARED_IDENTIFIER')
        if all(o.at<request['requested_at'] for o in selected.values()):review_reasons.append('ONLY_PRE_REQUEST_EVIDENCE')
        self.diagnostics[request['case_id']]=dict(subject=users[0],resources=len(selected),has_profile_evidence=has_profile_evidence,temporal_candidate_used=bool(fallback),prior_compliant_resources_excluded=excluded_stale,unverified_later_writes=sorted(unsupported_current),needs_review=bool(review_reasons),review_reasons=review_reasons,chosen=[dict(system=o.system,resource=o.resource,category=o.category,state=o.state,evidence=o.evidence,observed_at=o.at,available_at=o.available) for o in sorted(selected.values(),key=lambda o:(o.system,o.resource))])
        return dict(case_id=request['case_id'],deletion_status=status,steps_json=json.dumps(steps,separators=(',',':')))

    def policy(self,o):
        action=self.rules.get(o.category)
        if o.category=='DATA_FLOW':return ('REPORT_ACTIVE_DATA_FLOW','DISABLE_DATA_FLOW','VERIFY_DATA_FLOW_DISABLED') if o.state=='ACTIVE' else ('','','VERIFY_DATA_FLOW_DISABLED')
        if o.category=='BACKUP_ARCHIVE':return ('REPORT_RESTORE_RISK','BLOCK_RESTORE','VERIFY_RESTORE_BLOCKED') if o.state=='ACTIVE' else ('','','VERIFY_RESTORE_BLOCKED')
        if action=='RETAIN':return ('','','VERIFY_RECORD_PRESENT')
        if action=='DELETE':return ('REPORT_REMAINING_RECORD','DELETE_RECORD','VERIFY_RECORD_ABSENT') if o.state!='ABSENT' else ('','','VERIFY_RECORD_ABSENT')
        if action=='REDACT':return ('REPORT_EXPOSED_PII','REDACT_RECORD','VERIFY_RECORD_REDACTED') if o.state not in ('REDACTED','ABSENT') else ('','','VERIFY_RECORD_REDACTED')
        if action=='ANONYMIZE':return ('REPORT_EXPOSED_PII','ANONYMIZE_RECORD','VERIFY_RECORD_ANONYMIZED') if o.state not in ('ANONYMIZED','ABSENT') else ('','','VERIFY_RECORD_ANONYMIZED')
        raise ValueError(f'Unmapped policy category: {o.category}')

OPERATIONS=[('FINDING','REPORT_REMAINING_RECORD','PRESENT'),('FINDING','REPORT_EXPOSED_PII','PRESENT'),('FINDING','REPORT_ACTIVE_DATA_FLOW','ACTIVE'),('FINDING','REPORT_RESTORE_RISK','ACTIVE'),('REMEDIATION','DISABLE_DATA_FLOW','DISABLED'),('REMEDIATION','BLOCK_RESTORE','BLOCKED'),('REMEDIATION','DELETE_RECORD','ABSENT'),('REMEDIATION','REDACT_RECORD','REDACTED'),('REMEDIATION','ANONYMIZE_RECORD','ANONYMIZED'),('VERIFICATION','VERIFY_RECORD_ABSENT','ABSENT'),('VERIFICATION','VERIFY_RECORD_PRESENT','PRESENT'),('VERIFICATION','VERIFY_RECORD_REDACTED','REDACTED'),('VERIFICATION','VERIFY_RECORD_ANONYMIZED','ANONYMIZED'),('VERIFICATION','VERIFY_DATA_FLOW_DISABLED','DISABLED'),('VERIFICATION','VERIFY_RESTORE_BLOCKED','BLOCKED')]
ORDER={op:i for i,(_,op,_) in enumerate(OPERATIONS)}
STATES={op:state for _,op,state in OPERATIONS}
def step(phase,o,operation,evidence):
    return dict(step_no=0,phase=phase,system_id=o.system,resource_id=o.resource,operation=operation,state=STATES[operation],evidence_id=evidence)
def step_key(s):return ORDER[s['operation']],s['system_id'],s['resource_id']

def deletion_intent(text):
    text=norm(text).replace('’',"'")
    # A retention exception concerns its object, not authorization to erase the
    # account. Remove only these explicit policy exceptions before negation.
    text=re.sub(r"\b(?:do not|don't|never)\s+(?:delete|erase|remove)\s+(?:the |my |any )?(?:security|legal|retained|shared)\b[^.;!?]*",'',text)
    negative=(r"\b(?:do not|don't|never)\s+(?:want\s+(?:to\s+)?)?(?:delete|close|erase)",r"\b(?:do not|don't)\s+want\b[^.;!?]*\b(?:deleted|closed|erased)",r"\bnot asking\s+(?:for|to)\s+(?:an? |the |my )?(?:account[- ]+)?(?:delet|clos|eras)",r"\bnot (?:a |an )?(?:account[- ]+)?(?:deletion|delete)[- ]+request",r'not a request to erase',r'marketing lists only',r'without removing',r'information request',r'\bne\s+(?:demande|souhaite|veux)\s+pas\b[^.;!?]*(?:suppression|supprimer|effac)',r'\bno\s+(?:quiero|solicito|deseo)\b[^.;!?]*(?:elimin|borr)',r'\bnão\s+(?:quero|solicito|desejo)\b[^.;!?]*(?:exclu|apaga|elimin)',r'削除(?:しない|をしない|しません|は依頼していません)',r'삭제(?:하지\s*마|를\s*원하지|를\s*요청하지)')
    if any(re.search(p,text) for p in negative):return False
    positive=(r'delet',r'eras',r'clos(?:e|ed|ing).*account',r'account.*clos(?:e|ed)',r'remov.*(?:account|profile|personal|search result|records)',r'suppression',r'elimina',r'exclusão',r'削除',r'삭제',r'account itself is gone',r'old report saying my account still existed',r'privacy page still says my request failed',r'no longer need this account')
    return any(re.search(p,text) for p in positive)
