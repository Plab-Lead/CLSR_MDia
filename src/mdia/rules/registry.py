"""The manuscript's complete R001--R100 machine-sociolinguistic registry.

The support label is manuscript provenance, not the result of the current
execution.  Validation results therefore carry a separate execution status
and never promote a rule merely because this registry says ``full`` or
``strong``.
"""

from __future__ import annotations

from typing import Literal

from mdia.schemas import RuleSpec, RuleSupport

FAMILIES = {
    "A": "Receiver/listener rules",
    "B": "Speaker/publicness rules",
    "C": "Task-conditioned rules",
    "D": "Compression/redundancy rules",
    "E": "Routing/code-switching rules",
    "F": "Archive/evolution rules",
    "G": "Robustness, scale, and deployment rules",
}


# ID, manuscript taxonomy, title, manuscript hypothesis, manuscript support.
# These rows follow Supplementary Table 22 of MDia_Jul17.pdf exactly.
RULE_ROWS = [
    (
        "R001",
        "A",
        "Receiver-relative utility",
        "A dialect's utility depends on listener and task, not only on speaker quality.",
        "strong",
    ),
    (
        "R002",
        "A",
        "Listener openness asymmetry",
        "Listeners differ in how much they benefit from foreign dialects.",
        "full",
    ),
    (
        "R003",
        "A",
        "Expert resistance",
        "High-performing listeners may resist simplifying or foreign dialects.",
        "weak",
    ),
    (
        "R004",
        "A",
        "Compression-fragile listeners",
        "Some listeners lose accuracy when dialects are too compact.",
        "strong",
    ),
    (
        "R005",
        "A",
        "Listener variance dominance",
        "Receiver-side variation can dominate source-speaker variation in some tasks.",
        "partial",
    ),
    (
        "R006",
        "A",
        "Listener-specific parse fragility",
        "Parse failures and malformed final answers vary systematically by listener.",
        "weak",
    ),
    (
        "R007",
        "A",
        "Listener-specific verification demand",
        "Some listeners need explicit verification tags to retain correctness.",
        "weak",
    ),
    (
        "R008",
        "A",
        "Listener-specific redundancy preference",
        "Some listeners benefit from redundant structure while others prefer compact traces.",
        "weak",
    ),
    (
        "R009",
        "A",
        "Foreign-dialect risk",
        "Foreign dialects can harm listeners even when average transfer is positive.",
        "full",
    ),
    (
        "R010",
        "A",
        "Same-family listener accommodation",
        "Models from the same family or scale line transfer dialects more easily.",
        "boundary",
    ),
    (
        "R011",
        "A",
        "Cross-family listener friction",
        "Cross-family dialect transfer is more fragile than within-family transfer.",
        "boundary",
    ),
    (
        "R012",
        "A",
        "Small-listener scaffold benefit",
        "Smaller listeners can benefit from public scaffolding dialects.",
        "weak",
    ),
    (
        "R013",
        "A",
        "Large-listener simplification constraint",
        "Larger listeners may lose information under over-simplified dialects.",
        "weak",
    ),
    (
        "R014",
        "A",
        "Listener temperature sensitivity",
        "Listener route utility may change under decoding-temperature changes.",
        "boundary",
    ),
    (
        "R015",
        "A",
        "Listener answer-format brittleness",
        "Some listeners fail more often from answer-contract violations than reasoning errors.",
        "weak",
    ),
    (
        "R016",
        "B",
        "Public dialect asymmetry",
        "Some speakers produce more broadly adoptable dialects.",
        "full",
    ),
    (
        "R017",
        "B",
        "Weak-speaker teaching",
        "Lower raw-accuracy speakers can still teach foreign listeners.",
        "full",
    ),
    (
        "R018",
        "B",
        "Strong-speaker private dialects",
        "Strong speakers can produce private dialects that do not transfer broadly.",
        "weak",
    ),
    (
        "R019",
        "B",
        "Speaker variance dominance",
        "Source-dialect effects can dominate receiver effects in some tasks.",
        "weak",
    ),
    (
        "R020",
        "B",
        "Self-talk is not teaching",
        "A speaker's self dialect need not be its best teaching dialect.",
        "partial",
    ),
    (
        "R021",
        "B",
        "Private dialect specialization",
        "Some dialects are self-specialized and transfer poorly.",
        "weak",
    ),
    (
        "R022",
        "B",
        "Public bridge potential",
        "Public bridge dialects can help otherwise resistant speaker-listener pairs.",
        "unsupported",
    ),
    (
        "R023",
        "B",
        "Speaker concision-publicness tradeoff",
        "More concise speaker dialects can become less public.",
        "weak",
    ),
    (
        "R024",
        "B",
        "Speaker verifier-rich teaching",
        "Speakers that include verification operators can teach robustly.",
        "weak",
    ),
    (
        "R025",
        "B",
        "Speaker overcompression harm",
        "Speaker-side compression can remove information needed by foreign listeners.",
        "weak",
    ),
    (
        "R026",
        "B",
        "Speaker family style inheritance",
        "Speaker family affects dialect notation and transfer style.",
        "weak",
    ),
    (
        "R027",
        "B",
        "Speaker task-specialist transfer",
        "Task-specialist speakers transfer best within their task family.",
        "partial",
    ),
    (
        "R028",
        "B",
        "Speaker generalist bridge role",
        "Generalist speakers can serve as broad bridge dialect sources.",
        "weak",
    ),
    (
        "R029",
        "B",
        "Speaker profile beats raw score",
        "Speaker profile variables predict transfer better than raw benchmark score alone.",
        "weak",
    ),
    (
        "R030",
        "B",
        "Speaker dialect diversity advantage",
        "Speakers with diverse dialect pools provide better routing candidates.",
        "weak",
    ),
    (
        "R031",
        "C",
        "Task-conditioned transfer",
        "Speaker-listener gains differ across benchmark families.",
        "partial",
    ),
    (
        "R032",
        "C",
        "Hard-math verifier pressure",
        "Hard math tasks benefit from verifier-rich or longer dialects.",
        "partial",
    ),
    (
        "R033",
        "C",
        "Knowledge-QA redundancy pressure",
        "Knowledge QA tasks need redundancy around factual options and answer contracts.",
        "weak",
    ),
    (
        "R034",
        "C",
        "Code edge-case dialect pressure",
        "Code tasks require dialect fields for I/O contracts, edge cases, and complexity.",
        "boundary",
    ),
    (
        "R035",
        "C",
        "Tool-call schema-binding pressure",
        "Function-calling tasks favor explicit function-selection and argument-binding dialects.",
        "strong",
    ),
    (
        "R036",
        "C",
        "RAG evidence-chain pressure",
        "Evidence reasoning tasks require source IDs and relation-chain operators.",
        "boundary",
    ),
    (
        "R037",
        "C",
        "Narrative entity-state pressure",
        "Narrative tasks benefit from entity-state and evidence-tracking dialects.",
        "boundary",
    ),
    (
        "R038",
        "C",
        "Short-answer ceiling effect",
        "Near-saturated short-answer tasks show smaller accuracy gains.",
        "partial",
    ),
    (
        "R039",
        "C",
        "Benchmark headroom effect",
        "MDia gains are larger where baselines leave enough headroom.",
        "strong",
    ),
    (
        "R040",
        "C",
        "Long-context compression fragility",
        "Long-context tasks can fail if compression removes grounding details.",
        "weak",
    ),
    (
        "R041",
        "C",
        "Multi-hop relation tagging benefit",
        "Multi-hop tasks benefit from explicit relation tags.",
        "weak",
    ),
    (
        "R042",
        "C",
        "Symbolic transformation operator benefit",
        "Symbolic tasks benefit from typed operators and transformations.",
        "weak",
    ),
    (
        "R043",
        "C",
        "Commonsense narrative softness",
        "Commonsense narratives need softer, less over-symbolized dialects.",
        "boundary",
    ),
    (
        "R044",
        "C",
        "Retrieval noise amplification",
        "Retrieved evidence noise can amplify dialect mismatch.",
        "boundary",
    ),
    (
        "R045",
        "C",
        "Domain-specific dialect specialization",
        "Domain-specialized dialects transfer best within their domain.",
        "weak",
    ),
    (
        "R046",
        "D",
        "Cost-sensitive utility",
        "Token-efficient dialects can move the accuracy-token frontier.",
        "full",
    ),
    (
        "R047",
        "D",
        "Conciseness is not sufficient",
        "Lower token count alone does not predict correctness.",
        "unsupported",
    ),
    ("R048", "D", "Overcompression failure", "Large token compression can reduce accuracy.", "unsupported"),
    (
        "R049",
        "D",
        "Redundancy as listener insurance",
        "A little structured redundancy can protect foreign listeners.",
        "weak",
    ),
    (
        "R050",
        "D",
        "Verification tags can be worth their tokens",
        "Explicit check tags can improve net utility despite extra tokens.",
        "weak",
    ),
    (
        "R051",
        "D",
        "Symbol table reuse amortizes cost",
        "Reusable symbol tables become cost-effective across repeated tasks.",
        "weak",
    ),
    (
        "R052",
        "D",
        "Short operators survive frequent use",
        "Short stable operators work best when used repeatedly.",
        "weak",
    ),
    (
        "R053",
        "D",
        "Ambiguous abbreviations fail across listeners",
        "Unclear abbreviations increase cross-listener parse failures.",
        "weak",
    ),
    (
        "R054",
        "D",
        "Structured redundancy beats natural verbosity",
        "Structured redundancy is more efficient than verbose natural language.",
        "weak",
    ),
    (
        "R055",
        "D",
        "Token savings saturate before accuracy",
        "Beyond a threshold, extra compression no longer improves utility.",
        "weak",
    ),
    (
        "R056",
        "D",
        "Parser-compatible compactness",
        "Compactness is useful only if final answers remain parse-compatible.",
        "strong",
    ),
    (
        "R057",
        "D",
        "Answer-contract compression",
        "Answer contracts can be compressed safely when schema is explicit.",
        "strong",
    ),
    (
        "R058",
        "D",
        "Dialect entropy vs interpretability",
        "Higher symbol entropy can reduce foreign-listener interpretability.",
        "weak",
    ),
    (
        "R059",
        "D",
        "Compression helps easy tasks more",
        "Easy tasks tolerate stronger compression.",
        "partial",
    ),
    (
        "R060",
        "D",
        "Compression hurts hard tasks without verifier tags",
        "Hard tasks need verification to survive compression.",
        "weak",
    ),
    (
        "R061",
        "E",
        "Pragmatic code-switching",
        "Different task types favor different dialect sources.",
        "partial",
    ),
    (
        "R062",
        "E",
        "Archive routing advantage",
        "History-aware selection beats random or self-only dialect selection.",
        "weak",
    ),
    (
        "R063",
        "E",
        "Profile routing beats model-name routing",
        "Profile features outperform literal model-name routing.",
        "partial",
    ),
    (
        "R064",
        "E",
        "Task-aware routing beats global routing",
        "Task-conditioned routing beats a single global dialect choice.",
        "strong",
    ),
    (
        "R065",
        "E",
        "Route simplicity can beat over-composition",
        "Simple profile-aware routing can beat over-composed multi-dialect routing.",
        "full",
    ),
    (
        "R066",
        "E",
        "Bridge routing helps resistant pairs",
        "Bridge dialects help when direct transfer is risky.",
        "weak",
    ),
    (
        "R067",
        "E",
        "Composition helps hard tasks but not easy ones",
        "Multi-dialect composition is useful mainly for hard tasks.",
        "weak",
    ),
    (
        "R068",
        "E",
        "Random foreign routing is unsafe",
        "Randomly selected foreign dialects can cause negative transfer.",
        "strong",
    ),
    (
        "R069",
        "E",
        "Oracle gap reveals unused social information",
        "The archive contains unrealized gains beyond the implemented router.",
        "strong",
    ),
    (
        "R070",
        "E",
        "Route abstention protects against dialect mismatch",
        "Routing should abstain when mismatch risk is high.",
        "partial",
    ),
    (
        "R071",
        "E",
        "Route diversity improves ensemble robustness",
        "Diverse route candidates reduce brittleness.",
        "weak",
    ),
    (
        "R072",
        "E",
        "Majority vote is weaker than profile-aware vote",
        "Profile-aware routing beats unweighted votes over dialects.",
        "weak",
    ),
    (
        "R073",
        "E",
        "Cost-aware route selection changes winners",
        "Token-aware scoring changes which dialects are selected.",
        "strong",
    ),
    (
        "R074",
        "E",
        "Multi-round routing needs stopping discipline",
        "Extra routing rounds need stopping criteria to avoid cost blow-up.",
        "weak",
    ),
    (
        "R075",
        "E",
        "Rule-aware routing improves stability",
        "Validated rules can constrain routes and reduce failures.",
        "partial",
    ),
    ("R076", "F", "Dialect survival is task-specific", "Functional survival varies by benchmark.", "partial"),
    (
        "R077",
        "F",
        "Founder-effect proxy",
        "Removing source families disproportionately changes pooled outcomes.",
        "partial",
    ),
    (
        "R078",
        "F",
        "Borrowing proxy",
        "Functional influence is associated with token-structure shifts.",
        "unsupported",
    ),
    (
        "R079",
        "F",
        "Cross-generational influence is directed",
        "Source influence is directed and task-dependent.",
        "weak",
    ),
    (
        "R080",
        "F",
        "Generation depth improves then saturates",
        "More evolution generations help until validation utility saturates.",
        "boundary",
    ),
    (
        "R081",
        "F",
        "Archive diversity prevents early collapse",
        "Diverse archives prevent premature convergence to brittle dialects.",
        "partial",
    ),
    (
        "R082",
        "F",
        "Public dialects survive longer",
        "Public dialects persist under routing better than private dialects.",
        "partial",
    ),
    (
        "R083",
        "F",
        "Private dialects survive under self-heavy routing",
        "Self-heavy policies retain private dialects.",
        "weak",
    ),
    (
        "R084",
        "F",
        "Listener feedback reshapes dialect cards",
        "Listener outcomes should update dialect metadata.",
        "weak",
    ),
    (
        "R085",
        "F",
        "Benchmark mixing induces bridge dialects",
        "Mixed benchmark evolution can induce more public bridge dialects.",
        "weak",
    ),
    (
        "R086",
        "F",
        "Source removal reveals hidden dependency",
        "Leave-one-source analysis reveals hidden archive dependencies.",
        "partial",
    ),
    (
        "R087",
        "F",
        "Repeated transmission increases structure",
        "Repeated evolution/transmission increases dialect regularity.",
        "boundary",
    ),
    (
        "R088",
        "F",
        "Mutation repairs ambiguity more than it invents from scratch",
        "Mutation mainly repairs ambiguous conventions.",
        "boundary",
    ),
    (
        "R089",
        "F",
        "Archive age affects utility",
        "Older dialects can become stale under model/API drift.",
        "boundary",
    ),
    (
        "R090",
        "F",
        "Validation profile drift predicts test risk",
        "Validation/test profile drift predicts route failure.",
        "weak",
    ),
    (
        "R091",
        "G",
        "Scale does not monotonically increase publicness",
        "Scale does not guarantee public dialect utility.",
        "boundary",
    ),
    (
        "R092",
        "G",
        "Scale mismatch creates dialect mismatch",
        "Large scale gaps can make dialects harder to transfer.",
        "boundary",
    ),
    (
        "R093",
        "G",
        "Same-family scale transfer is easier than cross-family transfer",
        "Same-family scale transfer is easier than cross-family transfer.",
        "boundary",
    ),
    (
        "R094",
        "G",
        "API model drift changes social profiles",
        "Hosted model updates can change social/dialect profiles.",
        "boundary",
    ),
    (
        "R095",
        "G",
        "Cache-aware cost can change route preference",
        "Cache-aware accounting can change the selected route.",
        "weak",
    ),
    (
        "R096",
        "G",
        "Seed-stable rules are stronger than single-run rules",
        "Rules replicated across seeds are stronger than single-run patterns.",
        "partial",
    ),
    (
        "R097",
        "G",
        "Parse-failure diagnostics predict route failure",
        "Parse failure rates predict bad routes.",
        "weak",
    ),
    (
        "R098",
        "G",
        "Human-readable finalization is needed for auditability",
        "Final answers need readable contracts for audit and paper evaluation.",
        "strong",
    ),
    (
        "R099",
        "G",
        "Tool/RAG dialects require stricter answer contracts",
        "Tool/RAG dialects need stricter final schemas than short QA.",
        "strong",
    ),
    (
        "R100",
        "G",
        "Negative-transfer guards are essential for safe deployment",
        "Routes need guards against dialect mismatch and negative transfer.",
        "strong",
    ),
]


_REGRESSION_IDS = {
    "R003",
    "R004",
    "R012",
    "R013",
    "R023",
    "R029",
    "R032",
    "R038",
    "R039",
    "R040",
    "R046",
    "R047",
    "R048",
    "R050",
    "R051",
    "R052",
    "R053",
    "R055",
    "R058",
    "R059",
    "R060",
    "R073",
    "R074",
    "R080",
    "R087",
    "R089",
    "R090",
    "R091",
    "R092",
    "R094",
    "R095",
    "R097",
}
_PERMUTATION_IDS = {
    "R001",
    "R002",
    "R005",
    "R006",
    "R007",
    "R008",
    "R014",
    "R015",
    "R016",
    "R019",
    "R026",
    "R030",
    "R031",
    "R033",
    "R034",
    "R035",
    "R036",
    "R037",
    "R041",
    "R042",
    "R043",
    "R044",
    "R045",
    "R061",
    "R063",
    "R076",
    "R079",
    "R081",
    "R084",
    "R085",
    "R096",
    "R098",
    "R099",
}
_DESCRIPTIVE_IDS = {"R069", "R078", "R088"}
_TWO_SIDED_IDS = {"R003", "R014", "R026", "R047", "R061", "R076", "R079", "R089", "R091", "R094", "R096"}
_NEGATIVE_IDS = {"R023", "R025", "R040", "R048", "R053", "R058"}


_EVIDENCE = {
    "A": "validation speaker-listener transfer observations",
    "B": "validation speaker publicness and self-versus-foreign transfer observations",
    "C": "validation transfer observations joined to public task-family metadata",
    "D": "validation per-item accuracy, token, and parse observations",
    "E": "router-validation paired route-policy observations",
    "F": "live evolution records or explicitly labelled fixed-archive proxy records",
    "G": "versioned robustness, scale, seed, and deployment diagnostics",
}
_IMPLICATION = {
    "A": "Condition route scores on listener profile and parse risk.",
    "B": "Prefer measured public or teaching utility over raw speaker score.",
    "C": "Use task-conditioned dialect pools and route weights.",
    "D": "Optimize measured accuracy-token utility rather than compression alone.",
    "E": "Use validation-only routing with explicit negative-transfer guards.",
    "F": "Preserve archive diversity and label fixed-archive cross-generation analyses as proxies.",
    "G": "Log versions, seeds, cache cost, and failures before deployment.",
}


RuleTestType = Literal["paired_bootstrap", "permutation", "regression", "descriptive"]
RuleDirection = Literal["positive", "negative", "two_sided", "noninferior", "descriptive"]


def _contract(rule_id: str) -> tuple[RuleTestType, tuple[str, ...], str, str]:
    if rule_id in _DESCRIPTIVE_IDS:
        return ("descriptive", ("estimate",), "reported_effect", "descriptive")
    if rule_id in _REGRESSION_IDS:
        return ("regression", ("predictor", "outcome"), "ordinary_least_squares_slope", "item")
    if rule_id in _PERMUTATION_IDS:
        return ("permutation", ("group", "value"), "between_group_mean_variance", "item")
    return ("paired_bootstrap", ("treatment", "control"), "mean_paired_difference", "item")


def build_registry() -> tuple[RuleSpec, ...]:
    """Return the immutable, ID-ordered registry and assert complete coverage."""

    rules: list[RuleSpec] = []
    for rule_id, taxonomy, title, hypothesis, support in RULE_ROWS:
        test_type, features, statistic, unit = _contract(rule_id)
        direction: RuleDirection
        if rule_id in _TWO_SIDED_IDS:
            direction = "two_sided"
        elif rule_id in _NEGATIVE_IDS:
            direction = "negative"
        elif test_type == "descriptive":
            direction = "descriptive"
        else:
            direction = "positive"
        exceptions: tuple[str, ...] = ()
        if support in {"boundary", "unsupported"}:
            exceptions = (
                "The manuscript reports boundary or unsupported evidence; do not use this rule as a positive route prior.",
            )
        rules.append(
            RuleSpec(
                rule_id=rule_id,
                family=taxonomy,
                title=title,
                hypothesis=hypothesis,
                manuscript_support=RuleSupport(support),
                eligible_records="validation records with all declared features and a stable item-level unit ID",
                unit_of_analysis=unit,
                features=features,
                statistic=statistic,
                direction=direction,
                # The manuscript archive reports support scores, but does not
                # publish a fresh inferential effect threshold for this rule.
                # Validators must not silently substitute one.
                threshold=None,
                test_type=test_type,
                evidence_stream=_EVIDENCE[taxonomy],
                exceptions=exceptions,
                routing_implication=_IMPLICATION[taxonomy],
                proxy=taxonomy == "F",
            )
        )
    expected = [f"R{index:03d}" for index in range(1, 101)]
    actual = [rule.rule_id for rule in rules]
    if actual != expected:
        raise RuntimeError("rule registry must contain each ID R001 through R100 exactly once")
    return tuple(rules)


RULE_REGISTRY = build_registry()


def get_rule(rule_id: str) -> RuleSpec:
    try:
        return next(rule for rule in RULE_REGISTRY if rule.rule_id == rule_id)
    except StopIteration as exc:
        raise KeyError(f"unknown rule ID: {rule_id}") from exc


__all__ = ["FAMILIES", "RULE_REGISTRY", "RULE_ROWS", "build_registry", "get_rule"]
