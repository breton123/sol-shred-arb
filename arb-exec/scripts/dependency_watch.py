"""Observed-write invalidation for RPC-snapshot shadow candidates.

This journal proves what was observed, never absence of missing feed messages.
"""
import base64
from collections import deque
import hashlib
import json
import threading


def account_digest(account):
    if account is None:return None
    body=[account['owner'],account['lamports'],bool(account.get('executable')),
          hashlib.sha256(base64.b64decode(account['data'][0],validate=True)).hexdigest()]
    return hashlib.sha256(json.dumps(body,separators=(',',':')).encode()).hexdigest()


class DependencyWatch:
    def __init__(self,capacity=20000):
        self.lock=threading.Lock();self.capacity=capacity;self.generation=None
        self.active=False;self.slot=0;self.sequence=0;self.events=deque();self.evicted_through=0

    def apply(self,event):
        with self.lock:
            if event['kind']=='generation':
                self.generation=event['generation'];self.active=True;self.slot=0
                self.events.clear();self.sequence=0;self.evicted_through=0
                return
            if event.get('generation')!=self.generation:return
            if event['kind']=='disconnect':self.active=False;return
            if event['kind']=='slot':self.slot=max(self.slot,event['slot']);return
            if event['kind']!='account':return
            self.sequence+=1;self.events.append((self.sequence,dict(event)))
            if len(self.events)>self.capacity:
                self.evicted_through=self.events.popleft()[0]

    def begin(self):
        with self.lock:return {'generation':self.generation,'sequence':self.sequence,'observed_slot':self.slot,'active':self.active}

    def check(self,ticket,snapshot_slot,digests):
        with self.lock:
            if not self.active:return {'reason':'stream_disconnected'}
            if ticket['generation']!=self.generation:return {'reason':'generation_changed'}
            if ticket['sequence']<self.evicted_through:return {'reason':'journal_gap'}
            if self.slot<snapshot_slot:return {'reason':'stream_watermark_behind','observed_slot':self.slot}
            for sequence,event in self.events:
                if sequence<=ticket['sequence'] or event['key'] not in digests:continue
                if event['slot']>=snapshot_slot and event['digest']!=digests[event['key']]:
                    return {'reason':'observed_dependency_change','key':event['key'],'event_slot':event['slot'],
                            'event_sequence':sequence,'snapshot_slot':snapshot_slot}
            return {'reason':'no_observed_change','observed_slot':self.slot,'sequence':self.sequence,
                    'complete_feed_certified':False}
