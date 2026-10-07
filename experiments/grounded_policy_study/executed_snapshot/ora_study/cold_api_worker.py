"""Disabled native API adapter source for review; NEVER executed in this task.

The admission constant can change only in a newly reviewed source freeze after
whole-run resource proof and the parent's explicit scientific instruction. No
runtime flag, environment variable, input JSON or caller boolean can enable it.
"""
SCIENTIFIC_ADMISSION_REVIEWED = False

def execute_native_stage(request, api_root):
    if SCIENTIFIC_ADMISSION_REVIEWED is not True:
        raise RuntimeError("Scientific adapter disabled: combined review and execution instruction absent")
    # A future launcher must exec a fresh -I -S -B interpreter, sanitized env,
    # resource allocation and source freeze BEFORE reaching this import. Only
    # sys has been used to locate the approved API package; no numeric imports.
    import sys
    if any(name in sys.modules for name in ("fractions", "decimal", "numbers", "_decimal", "_pydecimal")):
        raise RuntimeError("Cold API numerical boundary contaminated")
    sys.path.insert(0, str(api_root)+"/experiments")
    import grounded_policy_v2
    from grounded_policy_v2.executive import GroundedExecutive
    # Import the controller's pure stage adapter only after v2 pins numerics.
    from ora_study.native_transport import serve_bound_api, exchange_stdio
    from ora_study.call_accounting import CallAccounting
    identities={
      (sys.modules["grounded_policy_v2.executive"].__file__,"validate_capsule"):"capsule_validation",
      (sys.modules["grounded_policy_v2.policy"].__file__,"build_cohort"):"producer",
      (sys.modules["grounded_policy_v2.policy"].__file__,"verify_cohort"):"cohort_proof",
      (sys.modules["grounded_policy_v2.policy"].__file__,"verify_evaluation"):"decision_proof",
      (sys.modules["grounded_policy_v2.policy"].__file__,"_reconstruct_cohort"):"checker_reconstruction",
      (sys.modules["grounded_policy_v2.policy"].__file__,"evaluate"):"selecting_backend",
      (sys.modules["open_object_world_challenge"].__file__,"transition"):"transition",
    }
    def count_exchange(message):
        exchange_stdio(message)
        return True
    with CallAccounting(identities,count_exchange):
        return serve_bound_api(GroundedExecutive, request, exchange_stdio)

if __name__ == "__main__":
    raise SystemExit("Scientific worker unavailable until whole-run admission is reviewed")
