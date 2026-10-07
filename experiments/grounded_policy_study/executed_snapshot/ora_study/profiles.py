"""Distinct frozen study and single real-software-fixture profiles.

A request JSON cannot select or modify these profiles. Trusted entrypoint code
chooses one; the scientific entry stays disabled. The six-call fixture also
requires the parent's exact-source go-ahead before it may be invoked.
"""
from types import MappingProxyType
from .protocol import registry
SCIENTIFIC_PROFILE=MappingProxyType({"name":"prospective_study_v4","data_kind":"scientific",
    "discovery_count":32,"case_ids":tuple(registry()["arm_case_ids"]),
    "setup_transitions":256,"owned_transitions":128,"probe_transitions":128,"transition_ceiling":512,
    "producer_calls":64,"capsule_validations":1986,"checker_reconstructions":4486})
INVARIANT_PROFILE=MappingProxyType({"name":"one_native_invariant_pair_v1","data_kind":"software_fixture",
    "discovery_count":2,"case_ids":("native-invariant.R","native-invariant.W"),
    "setup_transitions":2,"owned_transitions":4,"probe_transitions":0,"transition_ceiling":6,
    "producer_calls":2,"capsule_validations":64,"checker_reconstructions":146,
    "normal_api_workers":12,"terminal_reconcile_workers":1,"saved_reporter_workers":1,
    "automatic_retries":0,"science_result":None})
