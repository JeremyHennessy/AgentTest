"""Source-qualified call-entry/return evidence for future native worker review.

No policy hooks are replaced. A profile callback observes only code identity,
not locals. Only a transition return tuple is canonically hashed to distinguish a computed result from an exceptional exit. The trusted controller persists entry records
and acknowledges before execution continues; lost evidence remains unknown and
invalid. Tests profile only authored scalar functions.
"""
import sys
from .protocol import digest
from .ledger import IntegrityError

class CallAccounting:
    def __init__(self, identities, exchange):
        # (exact compiled filename, function name) -> declared counter category
        self.identities=dict(identities)
        self.exchange=exchange
        self.serial=0
        self.open_calls={}
        self.previous=None
    def _profile(self, frame, event, arg):
        key=(frame.f_code.co_filename,frame.f_code.co_name)
        category=self.identities.get(key)
        if category is None:
            return
        if event=="call":
            self.serial+=1
            call_id=self.serial
            self.open_calls[id(frame)]=(call_id,category)
            reply=self.exchange({"event":"actual_call_entered","call_id":call_id,"category":category})
            if reply is not True:
                raise IntegrityError("Controller did not persist call-entry charge")
        elif event=="return":
            item=self.open_calls.pop(id(frame),None)
            if item is None:
                raise IntegrityError("Unregistered call return")
            call_id,category=item
            message={"event":"actual_call_exited","call_id":call_id,"category":category}
            if category=="transition":
                message["computed_result_sha256"]=(digest({"world":arg[0],"receipt":arg[1]}) if isinstance(arg,tuple) and len(arg)==2 and all(isinstance(v,dict) for v in arg) else None)
            reply=self.exchange(message)
            if reply is not True:
                raise IntegrityError("Controller did not persist call-return record")
    def __enter__(self):
        self.previous=sys.getprofile()
        if self.previous is not None:
            raise IntegrityError("Existing profiler changes the frozen accounting boundary")
        sys.setprofile(self._profile)
        return self
    def __exit__(self,typ,error,traceback):
        sys.setprofile(self.previous)
        # A call-return does not claim successful durable completion; persistence
        # proof belongs to the native API result and separate ledger receipts.
        return False
