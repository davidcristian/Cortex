//! Behavioral tests for the retry **gate**: `SeamMethod`, `RetryPlan`, and the two
//! `RetryPolicy` helpers the probe budget is built from (`worst_case_backoff`, `within`).
//!
//! Pure data, so no fakes and no runtime are needed here; the decorator's behavior *under* a
//! plan is exercised against the `FlakyTransport`/`FakeSleeper` fakes in `retry.rs`. What this
//! file pins is the part that must be able to say **no**: a plan that cannot refuse a call
//! with an effect is a gate that cannot fail, which AGENTS.md counts as a defect.

use std::time::Duration;

use body_core::{DEFAULT_PROBE_BUDGET, RetryPlan, RetryPolicy, SeamMethod, TransportError};

/// Every variant, so the invariant below is checked over the whole port rather than a sample.
/// A new variant makes `SeamMethod::repeatable`'s exhaustive match fail to compile, which is
/// the reminder to classify it and add it here.
const EVERY_METHOD: [SeamMethod; 8] = [
    SeamMethod::Health,
    SeamMethod::Converse,
    SeamMethod::ListSessions,
    SeamMethod::SessionMessages,
    SeamMethod::ListDueReminders,
    SeamMethod::AckReminder,
    SeamMethod::RenameSession,
    SeamMethod::DeleteSession,
];

/// A deliberately patient read schedule: 6 attempts, 500 ms base, ×2, 10 s cap, so its
/// backoffs are 500 ms / 1 s / 2 s / 4 s / 8 s and its worst case is 15.5 s. This is what
/// someone who wants a session read to survive a slow brain restart would configure.
fn patient() -> RetryPolicy {
    RetryPolicy {
        max_attempts: 6,
        base_delay: Duration::from_millis(500),
        multiplier: 2,
        max_delay: Duration::from_secs(10),
    }
}

#[test]
fn repeatable_marks_exactly_the_calls_a_repeat_cannot_change() {
    // The four reads are views of a store they do not touch.
    assert!(SeamMethod::Health.repeatable());
    assert!(SeamMethod::ListSessions.repeatable());
    assert!(SeamMethod::SessionMessages.repeatable());
    assert!(SeamMethod::ListDueReminders.repeatable());
    // A turn may append messages, run tools, and stream output before it fails.
    assert!(!SeamMethod::Converse.repeatable());
    // The ack's *effect* is idempotent brain-side; its *answer* is not, which is the case
    // that shows repeatability is two tests, not one.
    assert!(!SeamMethod::AckReminder.repeatable());
    // The rename is a plain write: a repeat over a lost reply could re-apply a stale label.
    assert!(!SeamMethod::RenameSession.repeatable());
    // The delete is a destructive write: a silent retry could destroy a re-materialized chat.
    assert!(!SeamMethod::DeleteSession.repeatable());
}

#[test]
fn the_plan_hands_out_a_schedule_exactly_when_the_call_is_repeatable() {
    // The invariant that makes the gate meaningful: nothing else may decide this. If a
    // future edit lets an unrepeatable method through, `policy_for` answers `Some` and this
    // fails, whichever side of the pair was changed.
    let plan = RetryPlan::default();
    for method in EVERY_METHOD {
        assert_eq!(
            plan.policy_for(method).is_some(),
            method.repeatable(),
            "{method:?} disagrees with its own repeatability",
        );
    }
}

#[test]
fn a_refused_method_gets_no_schedule_however_generous_the_plan() {
    // No amount of configured patience buys a retry for a call with an effect.
    let generous = RetryPlan {
        reads: patient(),
        probe_budget: Duration::from_mins(10),
    };
    assert_eq!(generous.policy_for(SeamMethod::Converse), None);
    assert_eq!(generous.policy_for(SeamMethod::AckReminder), None);
    assert_eq!(generous.policy_for(SeamMethod::RenameSession), None);
    assert_eq!(generous.policy_for(SeamMethod::DeleteSession), None);
}

#[test]
fn the_reads_share_one_schedule_and_the_probe_is_trimmed_to_its_budget() {
    let plan = RetryPlan {
        reads: patient(),
        probe_budget: Duration::from_secs(1),
    };
    // Every read the user waits on gets the configured schedule verbatim.
    for method in [
        SeamMethod::ListSessions,
        SeamMethod::SessionMessages,
        SeamMethod::ListDueReminders,
    ] {
        assert_eq!(plan.policy_for(method), Some(patient()));
    }
    // The probe does not: 500 ms fits the 1 s budget and 500 + 1000 does not, so it keeps
    // two attempts. The indicator therefore answers within ~500 ms while a session read is
    // still allowed its 15.5 s of patience.
    let probe = plan.policy_for(SeamMethod::Health).unwrap();
    assert_eq!(probe.max_attempts, 2);
    assert_eq!(probe.worst_case_backoff(), Duration::from_millis(500));
    assert!(probe.worst_case_backoff() <= plan.probe_budget);
    // Only the attempt count moved; the delays themselves are the configured ones.
    assert_eq!(probe.base_delay, patient().base_delay);
    assert_eq!(probe.max_delay, patient().max_delay);
    assert_eq!(probe.multiplier, patient().multiplier);
}

#[test]
fn the_default_budget_does_not_bind_the_default_schedule() {
    // The plan is a no-op on the shipped configuration: 200 + 400 ms fits 1 s, so the probe
    // keeps all three attempts and the pre-plan behavior is unchanged by default.
    let plan = RetryPlan::default();
    assert_eq!(plan.reads, RetryPolicy::default());
    assert_eq!(plan.probe_budget, DEFAULT_PROBE_BUDGET);
    assert_eq!(plan.policy_for(SeamMethod::Health), Some(plan.reads));
    assert_eq!(plan.reads.worst_case_backoff(), Duration::from_millis(600));
}

#[test]
fn a_bare_policy_reads_as_a_plan_with_the_default_budget() {
    let plan = RetryPlan::from(patient());
    assert_eq!(plan.reads, patient());
    assert_eq!(plan.probe_budget, DEFAULT_PROBE_BUDGET);
    // Copy + Eq + Debug, as `RetryPolicy` is.
    let copy = plan;
    assert_eq!(copy, plan);
    assert_ne!(plan, RetryPlan::default());
    assert!(format!("{plan:?}").contains("RetryPlan"));
}

#[test]
fn the_refusal_schedule_can_never_buy_a_second_attempt() {
    // What a refused method is run on. It has to be inert under every input the retry loop
    // can hand it, because it is the whole of the refusal once the loop executes it: one
    // attempt, no wait, and no transient error able to argue for another go.
    let once = RetryPolicy::ONCE;
    assert_eq!(once.max_attempts, 1);
    assert_eq!(once.worst_case_backoff(), Duration::ZERO);
    assert_eq!(once.delay(0), Duration::ZERO);
    for error in [
        TransportError::Connection(String::from("refused")),
        TransportError::Rpc {
            code: String::from("Unavailable"),
            message: String::from("store down"),
        },
    ] {
        assert_eq!(
            once.backoff(0, &error),
            None,
            "{error:?} bought a retry out of the refusal schedule"
        );
    }
}

#[test]
fn worst_case_backoff_sums_every_wait_a_schedule_can_spend() {
    assert_eq!(
        patient().worst_case_backoff(),
        Duration::from_millis(15_500)
    );
    // A single-try schedule never waits, and neither does the degenerate zero-attempt one
    // (the subtraction saturates rather than wrapping to four billion waits).
    let single = RetryPolicy {
        max_attempts: 1,
        ..patient()
    };
    assert_eq!(single.worst_case_backoff(), Duration::ZERO);
    assert_eq!(
        RetryPolicy {
            max_attempts: 0,
            ..patient()
        }
        .worst_case_backoff(),
        Duration::ZERO
    );
    // A schedule whose delays already saturate reports the ceiling instead of panicking.
    let enormous = RetryPolicy {
        max_attempts: 3,
        base_delay: Duration::MAX,
        multiplier: 2,
        max_delay: Duration::MAX,
    };
    assert_eq!(enormous.worst_case_backoff(), Duration::MAX);
}

#[test]
fn within_trims_attempts_until_the_schedule_fits_the_budget() {
    // Fits already: untouched, including the exact-fit boundary (a schedule that spends
    // precisely the budget is inside it).
    assert_eq!(patient().within(Duration::from_mins(1)), patient());
    assert_eq!(
        RetryPolicy::default().within(Duration::from_millis(600)),
        RetryPolicy::default()
    );
    // One millisecond short of the last wait drops exactly that attempt.
    assert_eq!(
        RetryPolicy::default()
            .within(Duration::from_millis(599))
            .max_attempts,
        2
    );
    // A budget that buys nothing still buys the call itself: one attempt always survives.
    assert_eq!(patient().within(Duration::ZERO).max_attempts, 1);
    // A schedule with no retries to trim is returned as-is (the loop is never entered).
    let single = RetryPolicy {
        max_attempts: 1,
        ..patient()
    };
    assert_eq!(single.within(Duration::from_mins(10)), single);
}
