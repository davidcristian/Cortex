//! Behavioral tests for the retry **gate**: `SeamMethod`, `RetryPlan`, the two `RetryPolicy`
//! helpers the probe budget is built from (`worst_case_backoff`, `within`), and the per-method
//! deadline that bounds an attempt rather than the wait before it.

use std::time::Duration;

use body_core::{
    DEFAULT_CALL_DEADLINE, DEFAULT_PROBE_BUDGET, DEFAULT_PROBE_DEADLINE, RetryPlan, RetryPolicy,
    SeamMethod, TransportError,
};

/// Every variant, so the invariant below is checked over the whole port rather than a sample.
/// A new variant makes `SeamMethod::repeatable`'s exhaustive match fail to compile, which is
/// the reminder to classify it and add it here.
const EVERY_METHOD: [SeamMethod; 11] = [
    SeamMethod::Health,
    SeamMethod::Converse,
    SeamMethod::ListSessions,
    SeamMethod::SessionMessages,
    SeamMethod::ListDueReminders,
    SeamMethod::AckReminder,
    SeamMethod::RenameSession,
    SeamMethod::DeleteSession,
    SeamMethod::SetSessionPinned,
    SeamMethod::GetPreferences,
    SeamMethod::SetPreference,
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
    // The pin is idempotent by value, yet still one attempt: a retry could re-assert a pinned
    // value the user's next toggle reversed (the uniform catalog-write convention).
    assert!(!SeamMethod::SetSessionPinned.repeatable());
    assert!(SeamMethod::GetPreferences.repeatable());
    assert!(!SeamMethod::SetPreference.repeatable());
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
        ..RetryPlan::default()
    };
    assert_eq!(generous.policy_for(SeamMethod::Converse), None);
    assert_eq!(generous.policy_for(SeamMethod::AckReminder), None);
    assert_eq!(generous.policy_for(SeamMethod::RenameSession), None);
    assert_eq!(generous.policy_for(SeamMethod::DeleteSession), None);
    assert_eq!(generous.policy_for(SeamMethod::SetSessionPinned), None);
}

#[test]
fn the_reads_share_one_schedule_and_the_probe_is_trimmed_to_its_budget() {
    let plan = RetryPlan {
        reads: patient(),
        probe_budget: Duration::from_secs(1),
        ..RetryPlan::default()
    };
    // Every read the user waits on gets the configured schedule verbatim.
    for method in [
        SeamMethod::ListSessions,
        SeamMethod::SessionMessages,
        SeamMethod::ListDueReminders,
    ] {
        assert_eq!(plan.policy_for(method), Some(patient()));
    }
    // The probe does not: two attempts at 250 ms plus the 500 ms wait between them is exactly
    // the 1 s budget, and a third attempt would need 2.25 s. The indicator therefore answers
    // within its budget while a session read is still allowed its 15.5 s of patience.
    let probe = plan.policy_for(SeamMethod::Health).unwrap();
    assert_eq!(probe.max_attempts, 2);
    assert_eq!(probe.worst_case_backoff(), Duration::from_millis(500));
    assert_eq!(
        probe.max_attempts * plan.probe_deadline + probe.worst_case_backoff(),
        plan.probe_budget
    );
    // Only the attempt count moved; the delays themselves are the configured ones.
    assert_eq!(probe.base_delay, patient().base_delay);
    assert_eq!(probe.max_delay, patient().max_delay);
    assert_eq!(probe.multiplier, patient().multiplier);
}

#[test]
fn the_default_budget_spends_the_probe_on_two_attempts_and_the_wait_between_them() {
    let plan = RetryPlan::default();
    assert_eq!(plan.reads, RetryPolicy::default());
    assert_eq!(plan.probe_budget, DEFAULT_PROBE_BUDGET);
    assert_eq!(plan.reads.worst_case_backoff(), Duration::from_millis(600));
    let probe = plan.policy_for(SeamMethod::Health).unwrap();
    assert_eq!(probe.max_attempts, 2);
    assert_eq!(
        probe.max_attempts * plan.probe_deadline + probe.worst_case_backoff(),
        Duration::from_millis(700)
    );
}

#[test]
fn a_bare_policy_reads_as_a_plan_with_the_default_budget() {
    let plan = RetryPlan::from(patient());
    assert_eq!(plan.reads, patient());
    assert_eq!(plan.probe_budget, DEFAULT_PROBE_BUDGET);
    assert_eq!(plan.probe_deadline, DEFAULT_PROBE_DEADLINE);
    assert_eq!(plan.call_deadline, DEFAULT_CALL_DEADLINE);
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
    // A free attempt is the old arithmetic, kept as the base case: only the waits are counted.
    let free = Duration::ZERO;
    // Fits already: untouched, including the exact-fit boundary (a schedule that spends
    // precisely the budget is inside it).
    assert_eq!(patient().within(Duration::from_mins(1), free), patient());
    assert_eq!(
        RetryPolicy::default().within(Duration::from_millis(600), free),
        RetryPolicy::default()
    );
    // One millisecond short of the last wait drops exactly that attempt.
    assert_eq!(
        RetryPolicy::default()
            .within(Duration::from_millis(599), free)
            .max_attempts,
        2
    );
    // A budget that buys nothing still buys the call itself: one attempt always survives.
    assert_eq!(patient().within(Duration::ZERO, free).max_attempts, 1);
    // A schedule with no retries to trim is returned as-is (the loop is never entered).
    let single = RetryPolicy {
        max_attempts: 1,
        ..patient()
    };
    assert_eq!(single.within(Duration::from_mins(10), free), single);
}

#[test]
fn within_counts_the_attempts_and_not_only_the_waits() {
    let budget = Duration::from_millis(700);
    let costly = Duration::from_millis(500);
    assert_eq!(
        RetryPolicy::default()
            .within(budget, Duration::ZERO)
            .max_attempts,
        3
    );
    assert_eq!(
        RetryPolicy::default().within(budget, costly).max_attempts,
        1
    );
    // The boundary: two attempts plus the 200 ms between them is exactly 1.2 s.
    assert_eq!(
        RetryPolicy::default()
            .within(Duration::from_millis(1200), costly)
            .max_attempts,
        2
    );
    assert_eq!(
        RetryPolicy::default()
            .within(Duration::from_millis(1199), costly)
            .max_attempts,
        1
    );
    // An attempt too expensive for the budget still gets made, which is what makes the bound
    // `max(budget, attempt)` rather than `budget`: patience is what a budget can refuse.
    let trimmed = patient().within(Duration::from_millis(10), Duration::from_secs(30));
    assert_eq!(trimmed.max_attempts, 1);
    // Saturating arithmetic: an attempt cost that overflows the sum cannot wrap into a budget
    // that suddenly fits, so the schedule is trimmed rather than lengthened.
    assert_eq!(
        patient()
            .within(Duration::from_hours(1), Duration::MAX)
            .max_attempts,
        1
    );
    // The other end of the same arithmetic: a budget nothing can exhaust trims nothing, even
    // when every term in the sum has saturated.
    assert_eq!(
        patient().within(Duration::MAX, Duration::MAX).max_attempts,
        patient().max_attempts
    );
}

#[test]
fn the_probe_can_never_outlive_the_budget_it_is_trimmed_to() {
    for reads in [RetryPolicy::default(), patient(), RetryPolicy::ONCE] {
        for probe_budget in [
            Duration::ZERO,
            Duration::from_millis(700),
            Duration::from_secs(30),
        ] {
            for probe_deadline in [
                Duration::ZERO,
                Duration::from_millis(250),
                Duration::from_secs(10),
            ] {
                let plan = RetryPlan {
                    reads,
                    probe_budget,
                    probe_deadline,
                    ..RetryPlan::default()
                };
                let probe = plan.policy_for(SeamMethod::Health).unwrap();
                let worst = probe.max_attempts * probe_deadline + probe.worst_case_backoff();
                assert!(
                    worst <= probe_budget.max(probe_deadline),
                    "a {reads:?} probe under {probe_budget:?}/{probe_deadline:?} can spend {worst:?}"
                );
                assert!(
                    probe.max_attempts >= 1,
                    "a budget bought away the call itself"
                );
            }
        }
    }
}

#[test]
fn every_call_but_the_turn_is_bounded_by_a_deadline() {
    let plan = RetryPlan::default();
    for method in EVERY_METHOD {
        assert_eq!(
            plan.deadline_for(method).is_some(),
            method != SeamMethod::Converse,
            "{method:?} disagrees with the one exemption",
        );
    }
    assert_eq!(plan.deadline_for(SeamMethod::Converse), None);
    // The probe's deadline is its own, because the indicator renders its answer; every other
    // call shares the general one, writes included.
    assert_eq!(
        plan.deadline_for(SeamMethod::Health),
        Some(DEFAULT_PROBE_DEADLINE)
    );
    for method in [
        SeamMethod::ListSessions,
        SeamMethod::SessionMessages,
        SeamMethod::ListDueReminders,
        SeamMethod::AckReminder,
        SeamMethod::RenameSession,
        SeamMethod::DeleteSession,
        SeamMethod::SetSessionPinned,
        SeamMethod::GetPreferences,
        SeamMethod::SetPreference,
    ] {
        assert_eq!(
            plan.deadline_for(method),
            Some(DEFAULT_CALL_DEADLINE),
            "{method:?} was bounded by something other than the call deadline",
        );
    }
    // The two are separately configurable, so a tighter dot never tightens a read.
    let split = RetryPlan {
        probe_deadline: Duration::from_millis(40),
        call_deadline: Duration::from_secs(90),
        ..RetryPlan::default()
    };
    assert_eq!(
        split.deadline_for(SeamMethod::Health),
        Some(Duration::from_millis(40))
    );
    assert_eq!(
        split.deadline_for(SeamMethod::ListSessions),
        Some(Duration::from_secs(90))
    );
}
