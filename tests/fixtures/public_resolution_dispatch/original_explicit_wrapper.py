class FrozenOriginal:
    def resolve_native_inquiry(
        self,
        experiment_id: str,
        evidence_ref: str,
        *,
        enabled: bool = False,
        persist: bool = False,
        _now_override: str | None = None,
    ) -> dict[str, Any]:
        """Resolve one temporal native inquiry from one matching outcome transition.

        The interface is disabled and non-persisting by default. It does not
        increment the organism cycle or grant action authority.
        """
        if enabled is not True:
            raise RuntimeError("native inquiry outcome resolver is disabled by default")

        loaded = self.store.load()
        experiment = next(
            (
                item
                for item in loaded.get("experiments", [])
                if str(item.get("id")) == str(experiment_id)
            ),
            None,
        )
        if experiment is None:
            raise ValueError("native inquiry experiment was not found")
        if experiment.get("status") != "proposed":
            raise ValueError("native inquiry experiment is not proposed")
        if experiment.get("readiness") != "awaiting_native_evidence":
            raise ValueError("native inquiry experiment is not awaiting native evidence")

        native = experiment.get("native_inquiry")
        if not isinstance(native, dict):
            raise ValueError("experiment is not a native inquiry experiment")
        expected_relation = native.get("relation")
        if not isinstance(expected_relation, dict):
            raise ValueError("native inquiry relation is unavailable")
        sequence_floor = native.get(
            "resolution_evidence_floor_episode_sequence"
        )
        legacy_floor = native.get("resolution_evidence_floor_episode_count")
        if sequence_floor is not None:
            if type(sequence_floor) is not int or sequence_floor < 0:
                raise ValueError(
                    "native inquiry resolution evidence sequence floor is unavailable"
                )
        elif type(legacy_floor) is not int or legacy_floor < 0:
            raise ValueError("native inquiry resolution evidence floor is unavailable")

        episodes = loaded.get("episodes", [])
        episode_index = next(
            (
                index
                for index, item in enumerate(episodes)
                if str(item.get("id")) == str(evidence_ref)
            ),
            None,
        )
        episode = episodes[episode_index] if episode_index is not None else None
        if episode is None or episode.get("kind") != "native_inquiry_evidence":
            raise ValueError("native inquiry outcome evidence was not found")

        if sequence_floor is not None:
            evidence_sequence = episode_sequence(episode.get("id"))
            if evidence_sequence is None:
                raise ValueError(
                    "native inquiry outcome evidence has no monotonic episode sequence"
                )
            if evidence_sequence <= sequence_floor:
                raise ValueError("native inquiry outcome evidence predates the inquiry")
        else:
            next_episode_index = loaded.get("next_episode_index")
            if (
                type(next_episode_index) is int
                and next_episode_index != len(episodes) + 1
            ):
                raise ValueError(
                    "legacy native inquiry evidence floor cannot be used after "
                    "episode archival"
                )
            if episode_index < legacy_floor:
                raise ValueError("native inquiry outcome evidence predates the inquiry")
        try:
            payload = json.loads(str(episode.get("content") or ""))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("native inquiry outcome evidence is not valid JSON") from exc
        evidence = validate_native_evidence_payload(payload)
        relation = evidence.get("relation")
        if relation != expected_relation:
            raise ValueError("native inquiry outcome relation does not match experiment")

        grounding_observation_refs: set[str] = set()
        episodes_by_id = {
            str(item.get("id")): item
            for item in episodes
            if item.get("id")
        }
        for grounding_ref in native.get("evidence_refs", []):
            grounding_episode = episodes_by_id.get(str(grounding_ref))
            if (
                not isinstance(grounding_episode, dict)
                or grounding_episode.get("kind") != "native_inquiry_evidence"
            ):
                continue
            try:
                grounding_payload = json.loads(
                    str(grounding_episode.get("content") or "")
                )
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(
                    "native inquiry grounding evidence is not valid JSON"
                ) from exc
            grounding_evidence = validate_native_evidence_payload(grounding_payload)
            if grounding_evidence.get("relation") != expected_relation:
                continue
            grounding_observation_refs.update(
                str(ref) for ref in grounding_evidence.get("observation_refs", [])
            )

        outcome_observation_refs = {
            str(ref) for ref in evidence.get("observation_refs", [])
        }
        if not outcome_observation_refs - grounding_observation_refs:
            raise ValueError(
                "native inquiry outcome evidence contains no post-inquiry observation"
            )

        if evidence.get("measurement_kind") != "binary_transition_outcomes":
            raise ValueError(
                "native inquiry resolver currently supports temporal binary outcomes only"
            )
        if relation.get("kind") not in {
            "same_next_observation",
            "changes_next_observation",
        }:
            raise ValueError("native inquiry resolver requires a temporal relation")

        measurement = evidence.get("measurement")
        if not isinstance(measurement, dict):
            raise ValueError("native inquiry outcome measurement is unavailable")
        evaluable = int(measurement.get("evaluable", 0) or 0)
        confirmations = int(measurement.get("confirmations", 0) or 0)
        refutations = int(measurement.get("refutations", 0) or 0)
        if evaluable != 1 or confirmations + refutations != 1:
            raise ValueError(
                "native inquiry resolution requires exactly one evaluable transition"
            )
        if confirmations not in {0, 1} or refutations not in {0, 1}:
            raise ValueError("native inquiry outcome must be unambiguous")
        outcome = "supported" if confirmations == 1 else "falsified"

        state = loaded if persist else deepcopy(loaded)
        resolved_experiment = next(
            item
            for item in state["experiments"]
            if str(item.get("id")) == str(experiment_id)
        )
        now = _now_override or utc_now()
        cycle = int(state.get("cycles", 0) or 0)

        resolved_experiment["status"] = "completed"
        resolved_experiment["readiness"] = "resolved"
        resolved_experiment["outcome"] = outcome
        resolved_experiment["evidence_strength"] = 1.0
        resolved_experiment["evidence_refs"] = [str(evidence_ref)]
        resolved_experiment["completion_source"] = "native_evidence_contract"
        resolved_experiment["completed_at"] = now
        resolved_experiment["native_resolution"] = {
            "version": "native-inquiry-resolution-v1",
            "evidence_ref": str(evidence_ref),
            "relation": deepcopy(relation),
            "measurement_kind": evidence["measurement_kind"],
            "outcome": outcome,
        }
        resolved_experiment.setdefault("status_history", []).append(
            {
                "cycle": cycle,
                "from": "proposed",
                "to": "completed",
                "reason": "native_evidence_contract_resolved",
                "evidence_refs": [str(evidence_ref)],
                "outcome": outcome,
            }
        )

        reflection = {
            "id": f"R{len(state.get('reflections', [])) + 1:06d}",
            "source": "native_inquiry",
            "experiment_id": str(experiment_id),
            "evidence_ref": str(evidence_ref),
            "cycle": cycle,
            "outcome": outcome,
            "evidence_strength": 1.0,
            "lesson": (
                "One matching evaluable native transition "
                f"{outcome} the bounded temporal inquiry. Treat this as an "
                "experiment outcome, not as a general causal fact."
            ),
        }
        state.setdefault("reflections", []).append(reflection)

        if persist:
            self.store.save(state)

        return {
            "enabled": True,
            "persisted": bool(persist),
            "resolved": True,
            "experiment": deepcopy(resolved_experiment),
            "reflection": deepcopy(reflection),
            "evidence": deepcopy(evidence),
            "state": deepcopy(state),
        }
