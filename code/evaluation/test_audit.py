"""Independent synthetic regression cases; no contest labels or corpus answers."""
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audit import Auditor, deletion_intent, read_csv

class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.write('user_identities.csv',[dict(user_id='user_101',name='Synthetic Tester',email='new@example.invalid',phone='+1 000 000 0001',email_hash='abc123',updated_at='2026-01-01T00:00:00Z')])
        self.write('user_audit_log.csv',[dict(audit_id='audit_test',user_id='user_101',event_time='2026-01-02T00:00:00Z',field_name='email',old_value='old@example.invalid',new_value='new@example.invalid')])
        self.write('system_activity.csv',[],['activity_id','event_time','event_type','source_system','target_system','resource_id','reported_result','details'])
        self.write('deletion_rules.csv',[dict(rule_id='r'+str(i),data_category=c,condition='Always',required_action=a) for i,(c,a) in enumerate([('USER_PROFILE','DELETE'),('SEARCH_INDEX_ENTRY','DELETE'),('SUPPORT_MESSAGE','REDACT'),('ACCOUNT_TOMBSTONE','REDACT'),('ANALYTICS_PROFILE','ANONYMIZE'),('SECURITY_AUDIT_LOG','RETAIN'),('BACKUP_ARCHIVE','RETAIN'),('CACHE_ENTRY','DELETE'),('PRODUCT_TELEMETRY','ANONYMIZE'),('EMAIL_DELIVERY_LOG','REDACT')])])
        self.entries=[]
    def tearDown(self):self.tmp.cleanup()
    def write(self,name,rows,fields=None):
        with (self.root/name).open('w',encoding='utf-8',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=fields or list(rows[0]));writer.writeheader();writer.writerows(rows)
    def evidence(self,rows,at='2026-02-01T00:00:00Z',extension='json',text=None):
        fid='evidence_test_'+str(len(self.entries))
        name=fid+'.'+extension
        (self.root/name).write_text(text if text is not None else json.dumps(dict(records=rows)),encoding='utf-8')
        self.entries.append(dict(file_id=fid,file_path=name,origin='test',captured_at=at))
    def run_case(self,text='Please delete my account.',email='new@example.invalid'):
        self.write('evidence_files.csv',self.entries)
        auditor=Auditor(self.root)
        request=dict(case_id='custom',email=email,requested_at='2026-01-15T00:00:00Z',reported_at='2026-01-20T00:00:00Z',reported_status='COMPLETE',audit_at='2026-02-02T00:00:00Z',request_text=text)
        result=auditor.audit(request)
        self.last_diagnostic=auditor.diagnostics.get('custom',{})
        return result['deletion_status'],json.loads(result['steps_json'])
    def test_non_deletion_requests(self):
        for text in ["Don't delete my account; send a copy.",'Please remove me from marketing lists only.','Correct my name without removing records.','Please change my email.']:
            self.assertFalse(deletion_intent(text))
    def test_multilingual_deletion(self):
        for text in ['Solicito la eliminación de mi cuenta.','Solicito a exclusão da conta.','Je demande la suppression du compte.','アカウントの削除を依頼します。','계정 삭제를 요청합니다.']:
            self.assertTrue(deletion_intent(text))
    def test_historical_email_and_decoy(self):
        self.evidence([dict(resource_id='search_101',email='OLD@example.invalid'),dict(resource_id='search_202',email='old.extra@example.invalid')])
        status,steps=self.run_case(email='old@example.invalid')
        self.assertEqual(status,'INCOMPLETE');self.assertEqual({s['resource_id'] for s in steps},{'search_101'})
    def test_cutoff_excludes_future_evidence(self):
        self.evidence([dict(resource_id='account_101',subject_reference='user_101',result='NOT_FOUND')])
        self.evidence([dict(resource_id='account_101',email='new@example.invalid',result='FOUND')],at='2026-03-01T00:00:00Z')
        status,steps=self.run_case();self.assertEqual(status,'COMPLETE');self.assertEqual(steps[0]['evidence_id'],'evidence_test_0')
    def test_flows_and_restore_before_deletion(self):
        self.evidence([dict(resource_id='account_101',email='new@example.invalid'),dict(resource_id='data_flow_101',customer_reference='user_101',enabled=True),dict(resource_id='backup_101',subject_reference='user_101',restore_allowed=True)])
        status,steps=self.run_case()
        actions=[s['operation'] for s in steps if s['phase']=='REMEDIATION']
        self.assertEqual(actions,['DISABLE_DATA_FLOW','BLOCK_RESTORE','DELETE_RECORD'])
        self.assertTrue(all(s['evidence_id']=='' for s in steps if s['phase']!='FINDING'))
    def test_retained_record_survives(self):
        self.evidence([dict(resource_id='audit_record_101',subject_reference='user_101',record_type='SECURITY_AUDIT_LOG')])
        status,steps=self.run_case();self.assertEqual(status,'COMPLETE');self.assertEqual(steps[0]['operation'],'VERIFY_RECORD_PRESENT')
    def test_tombstone_stable_reference_is_permitted(self):
        self.evidence([dict(resource_id='tombstone_101',subject_reference='user_101',name=None,email=None,phone=None,email_hash=None)])
        status,steps=self.run_case();self.assertEqual(status,'COMPLETE');self.assertEqual(steps[0]['operation'],'VERIFY_RECORD_REDACTED')
    def test_tombstone_direct_identifier_requires_redaction(self):
        self.evidence([dict(resource_id='tombstone_101',subject_reference='user_101',email='old@example.invalid')])
        status,steps=self.run_case();self.assertEqual(status,'INCOMPLETE');self.assertIn('REDACT_RECORD',[s['operation'] for s in steps])
    def test_shared_support_is_redacted(self):
        self.evidence([dict(resource_id='support_101',subject_reference='user_101',message_text='Contact new@example.invalid about the shared order')])
        status,steps=self.run_case();self.assertEqual(status,'INCOMPLETE');self.assertEqual(steps[1]['operation'],'REDACT_RECORD')
    def test_replica_survival_beats_absence(self):
        self.evidence([dict(resource_id='account_101',subject_reference='user_101',result='NOT_FOUND'),dict(resource_id='account_101',subject_reference='user_101',result='FOUND')])
        status,steps=self.run_case();self.assertEqual(status,'INCOMPLETE');self.assertEqual(steps[0]['operation'],'REPORT_REMAINING_RECORD')
    def test_interleaved_trace_identity(self):
        self.evidence([],extension='log',text='\n'.join([
            '2026-02-01T00:00:00Z service=account_service trace_id=a event=profile_lookup_started lookup_key=old@example.invalid',
            '2026-02-01T00:00:01Z service=account_service trace_id=b event=profile_lookup_started lookup_key=other@example.invalid',
            '2026-02-01T00:00:02Z service=account_service trace_id=b event=profile_lookup_completed resource_id=account_202 rows=1',
            '2026-02-01T00:00:03Z service=account_service trace_id=a event=profile_lookup_completed resource_id=account_101 rows=0']))
        status,steps=self.run_case();self.assertEqual(status,'COMPLETE');self.assertEqual({s['resource_id'] for s in steps},{'account_101'})
    def test_user_reference_boundary(self):
        self.evidence([dict(resource_id='search_101',customer_reference='user_101'),dict(resource_id='search_1010',customer_reference='user_1010')])
        status,steps=self.run_case();self.assertEqual({s['resource_id'] for s in steps},{'search_101'})
    def test_phone_format_is_normalized(self):
        self.evidence([dict(resource_id='search_101',phone='+10000000001')])
        status,steps=self.run_case();self.assertEqual(status,'INCOMPLETE');self.assertEqual(steps[0]['resource_id'],'search_101')
    def test_benign_support_text_is_not_pii(self):
        self.evidence([dict(resource_id='support_101',subject_reference='user_101',message_text='The parcel has been delivered.')])
        status,steps=self.run_case();self.assertEqual(status,'COMPLETE');self.assertEqual(steps[0]['operation'],'VERIFY_RECORD_REDACTED')
    def test_prior_compliant_resource_not_repeated(self):
        self.evidence([dict(resource_id='account_202',subject_reference='user_101',result='NOT_FOUND')],at='2026-01-10T00:00:00Z')
        self.evidence([dict(resource_id='account_101',subject_reference='user_101',result='NOT_FOUND')])
        status,steps=self.run_case();self.assertEqual(status,'COMPLETE');self.assertEqual({s['resource_id'] for s in steps},{'account_101'})
    def test_old_surviving_record_still_requires_remediation(self):
        self.evidence([dict(resource_id='search_202',email='old@example.invalid')],at='2026-01-10T00:00:00Z')
        self.evidence([dict(resource_id='account_101',subject_reference='user_101',result='NOT_FOUND')])
        status,steps=self.run_case();self.assertEqual(status,'INCOMPLETE');self.assertIn('search_202',{s['resource_id'] for s in steps if s['phase']=='FINDING'})
    def test_explicit_foreign_subject_overrides_shared_name(self):
        self.evidence([dict(resource_id='search_202',customer_reference='user_202',display_name='Synthetic Tester',email='other@example.invalid'),dict(resource_id='account_101',subject_reference='user_101',result='NOT_FOUND')])
        status,steps=self.run_case();self.assertEqual(status,'COMPLETE');self.assertEqual({s['resource_id'] for s in steps},{'account_101'})
    def test_negated_account_preferences(self):
        for text in ["I do not want to delete my account.","I don't want my account deleted.",'I am not asking for account deletion.','This is not an account-deletion request.']:
            self.assertFalse(deletion_intent(text),text)
    def test_retention_exception_keeps_account_authorization(self):
        self.assertTrue(deletion_intent('Do not delete security records. Please delete my account.'))
    def test_explicit_category_and_system_fields(self):
        self.evidence([dict(resource_id='lookup_custom',system_id='regional_cache',data_category='CACHE_ENTRY',email='new@example.invalid',state='PRESENT')])
        status,steps=self.run_case();self.assertEqual(status,'INCOMPLETE');self.assertEqual(steps[0]['system_id'],'regional_cache');self.assertEqual(steps[1]['operation'],'DELETE_RECORD')
    def test_telemetry_stable_subject_is_attributable(self):
        self.evidence([dict(resource_id='telemetry_101',customer_reference='user_101',session_count=7)])
        status,steps=self.run_case();self.assertEqual(status,'INCOMPLETE');self.assertEqual(steps[1]['operation'],'ANONYMIZE_RECORD')
    def test_email_delivery_redaction(self):
        self.evidence([dict(resource_id='email_log_101',subject_reference='user_101',recipient_email='old@example.invalid')])
        status,steps=self.run_case();self.assertEqual(status,'INCOMPLETE');self.assertEqual(steps[1]['operation'],'REDACT_RECORD')
    def test_row_observed_after_cutoff_is_excluded(self):
        self.evidence([dict(resource_id='account_101',subject_reference='user_101',result='NOT_FOUND')])
        self.evidence([dict(resource_id='account_101',email='new@example.invalid',observed_at='2026-03-01T00:00:00Z')])
        status,steps=self.run_case();self.assertEqual(status,'COMPLETE');self.assertEqual(steps[0]['evidence_id'],'evidence_test_0')
    def test_sparse_later_snapshot_does_not_prove_absence(self):
        self.evidence([],text=json.dumps({'snapshots':[
            dict(captured_at='2026-01-30T00:00:00Z',data_store='account_service',collection='customer_profiles',records=[dict(resource_id='account_101',customer_reference='user_101',email='new@example.invalid')]),
            dict(captured_at='2026-02-01T00:00:00Z',data_store='account_service',collection='customer_profiles',records=[dict(resource_id='account_202',customer_reference='user_202',email='other@example.invalid')])]}))
        status,steps=self.run_case();self.assertEqual(status,'INCOMPLETE');self.assertEqual(steps[0]['operation'],'REPORT_REMAINING_RECORD')
    def test_successful_operation_claim_does_not_override_readback(self):
        self.write('system_activity.csv',[dict(activity_id='activity_test',event_time='2026-01-20T00:00:00Z',event_type='DELETE_RECORD',source_system='deletion_worker',target_system='account_service',resource_id='account_101',reported_result='SUCCESS',details='Deletion completed for user_101.')])
        self.evidence([dict(resource_id='account_101',customer_reference='user_101',email='new@example.invalid')])
        status,steps=self.run_case();self.assertEqual(status,'INCOMPLETE');self.assertEqual(steps[0]['operation'],'REPORT_REMAINING_RECORD')
    def test_later_readback_beats_earlier_presence(self):
        self.evidence([dict(resource_id='account_101',email='new@example.invalid',observed_at='2026-01-31T00:00:00Z'),dict(resource_id='account_101',subject_reference='user_101',result='NOT_FOUND',observed_at='2026-02-01T00:00:00Z')])
        status,steps=self.run_case();self.assertEqual(status,'COMPLETE');self.assertEqual(steps[0]['operation'],'VERIFY_RECORD_ABSENT')
    def test_missing_profile_is_flagged_for_review(self):
        self.evidence([dict(resource_id='audit_record_101',subject_reference='user_101',record_type='SECURITY_AUDIT_LOG')])
        self.run_case();self.assertTrue(self.last_diagnostic['needs_review']);self.assertIn('MISSING_PROFILE_PROOF',self.last_diagnostic['review_reasons'])
    def test_later_write_invalidates_proof_confidence(self):
        self.write('system_activity.csv',[dict(activity_id='activity_test',event_time='2026-02-01T12:00:00Z',event_type='SYNC_RECORD',source_system='integration_service',target_system='account_service',resource_id='account_101',reported_result='SUCCESS',details='A synchronization wrote the profile for user_101.')])
        self.evidence([dict(resource_id='account_101',subject_reference='user_101',result='NOT_FOUND')])
        self.run_case();self.assertIn('LATER_WRITE_WITHOUT_READBACK',self.last_diagnostic['review_reasons'])
    def test_multilingual_negative_requests(self):
        for text in ['Je ne demande pas la suppression de mon compte.','No quiero eliminar mi cuenta.','Não solicito a exclusão da minha conta.','アカウントを削除しないでください。','계정을 삭제하지 마세요.']:
            self.assertFalse(deletion_intent(text),text)
    def test_name_in_support_body_requires_redaction(self):
        self.evidence([dict(resource_id='support_101',subject_reference='user_101',message_text='The recipient is Synthetic Tester. Please call before delivery.')])
        status,steps=self.run_case();self.assertEqual(status,'INCOMPLETE');self.assertEqual(steps[1]['operation'],'REDACT_RECORD')
    def test_catalog_claim_cannot_override_foreign_subject(self):
        self.write('system_activity.csv',[dict(activity_id='activity_test',event_time='2026-01-20T00:00:00Z',event_type='LINK_RESOURCE_IDENTITY',source_system='data_catalog',target_system='search_service',resource_id='search_202',reported_result='SUCCESS',details='Catalog linked search_202 to user_101.')])
        self.evidence([dict(resource_id='search_202',customer_reference='user_202',email='other@example.invalid'),dict(resource_id='account_101',subject_reference='user_101',result='NOT_FOUND')])
        status,steps=self.run_case();self.assertEqual(status,'COMPLETE');self.assertEqual({s['resource_id'] for s in steps},{'account_101'});self.assertIn('CONFLICTING_SUBJECT_EVIDENCE',self.last_diagnostic['review_reasons'])
    def test_shared_phone_alone_is_not_unique_identity(self):
        identities=read_csv(self.root/'user_identities.csv')
        identities.append(dict(user_id='user_202',name='Synthetic Tester',email='other@example.invalid',phone='+1 000 000 0001',email_hash='different_hash',updated_at='2026-01-01T00:00:00Z'))
        self.write('user_identities.csv',identities)
        self.evidence([dict(resource_id='search_202',phone='+10000000001'),dict(resource_id='account_101',subject_reference='user_101',result='NOT_FOUND')])
        status,steps=self.run_case();self.assertEqual(status,'COMPLETE');self.assertEqual({s['resource_id'] for s in steps},{'account_101'});self.assertIn('AMBIGUOUS_SHARED_IDENTIFIER',self.last_diagnostic['review_reasons'])

if __name__=='__main__':unittest.main()
