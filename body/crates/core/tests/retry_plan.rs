use std::time::Duration;

use body_core::{
    ANNOUNCED_DEADLINE_GRACE_MS, DEFAULT_CALL_DEADLINE, DEFAULT_PROBE_BUDGET,
    DEFAULT_PROBE_DEADLINE, RetryPlan, RetryPolicy, SeamMethod, TransportError, TurnGaps,
};

/// Every variant, so the invariant below is checked over the whole port rather than a sample.
const EVERY_METHOD: [SeamMethod; 11] = [
    SeamMethod::Health,
    SeamMethod::Converse,
    SeamMethod::ListSessions,
    SeamMethod::SessionMessages,
    SeamMethod::ListDueReminders,
    SeamMethod::AckReminder,
    SeamMethod::RenameSession,
    SeamMethod::DeleteSession,
    SeamMethod::SetSessionHoisted,
    SeamMethod::GetPreferences,
    SeamMethod::SetPreference,
];

/// A long read schedule: 6 attempts, 500 ms base, ×2, 10 s cap, so its backoffs are 500 ms / 1 s /
/// 2 s / 4 s / 8 s and its worst case is 15.5 s. This is what someone who wants a session read to
/// survive a slow brain restart would configure.
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
    assert!(SeamMethod::Health.repeatable());
    assert!(SeamMethod::ListSessions.repeatable());
    assert!(SeamMethod::SessionMessages.repeatable());
    assert!(SeamMethod::ListDueReminders.repeatable());
    assert!(!SeamMethod::Converse.repeatable());
    assert!(!SeamMethod::AckReminder.repeatable());
    assert!(!SeamMethod::RenameSession.repeatable());
    assert!(!SeamMethod::DeleteSession.repeatable());
    assert!(!SeamMethod::SetSessionHoisted.repeatable());
    assert!(SeamMethod::GetPreferences.repeatable());
    assert!(!SeamMethod::SetPreference.repeatable());
}

#[test]
fn the_plan_hands_out_a_schedule_exactly_when_the_call_is_repeatable() {
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
    let generous = RetryPlan {
        reads: patient(),
        probe_budget: Duration::from_mins(10),
        ..RetryPlan::default()
    };
    assert_eq!(generous.policy_for(SeamMethod::Converse), None);
    assert_eq!(generous.policy_for(SeamMethod::AckReminder), None);
    assert_eq!(generous.policy_for(SeamMethod::RenameSession), None);
    assert_eq!(generous.policy_for(SeamMethod::DeleteSession), None);
    assert_eq!(generous.policy_for(SeamMethod::SetSessionHoisted), None);
}

#[test]
fn the_reads_share_one_schedule_and_the_probe_is_trimmed_to_its_budget() {
    let plan = RetryPlan {
        reads: patient(),
        probe_budget: Duration::from_secs(1),
        ..RetryPlan::default()
    };
    for method in [
        SeamMethod::ListSessions,
        SeamMethod::SessionMessages,
        SeamMethod::ListDueReminders,
    ] {
        assert_eq!(plan.policy_for(method), Some(patient()));
    }
    let probe = plan.policy_for(SeamMethod::Health).unwrap();
    assert_eq!(probe.max_attempts, 2);
    assert_eq!(probe.worst_case_backoff(), Duration::from_millis(500));
    assert_eq!(
        probe.max_attempts * plan.probe_deadline + probe.worst_case_backoff(),
        plan.probe_budget
    );
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
    let copy = plan;
    assert_eq!(copy, plan);
    assert_ne!(plan, RetryPlan::default());
    assert!(format!("{plan:?}").contains("RetryPlan"));
}

#[test]
fn the_refusal_schedule_can_never_buy_a_second_attempt() {
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
    let free = Duration::ZERO;
    assert_eq!(patient().within(Duration::from_mins(1), free), patient());
    assert_eq!(
        RetryPolicy::default().within(Duration::from_millis(600), free),
        RetryPolicy::default()
    );
    assert_eq!(
        RetryPolicy::default()
            .within(Duration::from_millis(599), free)
            .max_attempts,
        2
    );
    assert_eq!(patient().within(Duration::ZERO, free).max_attempts, 1);
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
    let trimmed = patient().within(Duration::from_millis(10), Duration::from_secs(30));
    assert_eq!(trimmed.max_attempts, 1);
    assert_eq!(
        patient()
            .within(Duration::from_hours(1), Duration::MAX)
            .max_attempts,
        1
    );
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
fn every_call_is_bounded_by_exactly_one_of_the_two_clocks() {
    let plan = RetryPlan::default();
    for method in EVERY_METHOD {
        assert_ne!(
            plan.deadline_for(method).is_some(),
            plan.gaps_for(method).is_some(),
            "{method:?} is bounded by both clocks or by neither",
        );
    }
    assert_eq!(
        plan.gaps_for(SeamMethod::Converse),
        Some(TurnGaps::default())
    );
    let tuned = RetryPlan {
        turn_gaps: TurnGaps {
            first: Duration::from_secs(7),
            idle: Duration::from_secs(11),
            ..TurnGaps::default()
        },
        ..RetryPlan::default()
    };
    assert_eq!(tuned.gaps_for(SeamMethod::Converse), Some(tuned.turn_gaps));
    assert_eq!(tuned.deadline_for(SeamMethod::Converse), None);
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
        SeamMethod::SetSessionHoisted,
        SeamMethod::GetPreferences,
        SeamMethod::SetPreference,
    ] {
        assert_eq!(
            plan.deadline_for(method),
            Some(DEFAULT_CALL_DEADLINE),
            "{method:?} was bounded by something other than the call deadline",
        );
    }
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

#[test]
fn the_announced_deadline_outlives_the_enforced_one_on_every_call_that_has_one() {
    let grace = Duration::from_millis(ANNOUNCED_DEADLINE_GRACE_MS);
    for plan in [
        RetryPlan::default(),
        RetryPlan {
            probe_deadline: Duration::from_millis(40),
            call_deadline: Duration::from_secs(90),
            ..RetryPlan::default()
        },
        RetryPlan {
            probe_deadline: Duration::from_millis(1),
            call_deadline: Duration::from_millis(2),
            ..RetryPlan::default()
        },
    ] {
        for method in EVERY_METHOD {
            let Some(enforced) = plan.deadline_for(method) else {
                assert_eq!(plan.announced_deadline_for(method), None);
                continue;
            };
            let announced = plan
                .announced_deadline_for(method)
                .expect("a bounded call announces the bound it is under");
            assert!(
                announced > enforced,
                "{method:?} would announce {announced:?}, which the body's own {enforced:?} \
                 does not beat",
            );
            assert_eq!(announced, enforced + grace);
        }
    }
}

#[test]
fn a_deadline_at_the_end_of_time_still_announces_something_a_clock_can_hold() {
    let plan = RetryPlan {
        call_deadline: Duration::MAX,
        ..RetryPlan::default()
    };
    assert_eq!(
        plan.announced_deadline_for(SeamMethod::ListSessions),
        Some(Duration::MAX)
    );
}
