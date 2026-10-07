//! A headless client for one handoff turn against a real brain, `#[ignore]`d so it never runs in
//! CI. It approves a confirm card only when `CORTEX_HANDOFF_DECISION` is `approve`; run it with
//! `just rpc-handoff approve` or `just rpc-handoff deny`.

use std::pin::pin;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use body_core::{BrainTransport, ConfirmDecision, TurnEvent};
use body_rpc::BrainRpcClient;
use tokio::sync::{mpsc, watch};
use tokio_stream::StreamExt;
use tokio_stream::wrappers::UnboundedReceiverStream;

const ESCALATE_TOOL_NAME: &str = "escalate_to_brain";
const SWAPPING: &str = "swapping";
const DRAINING_DETAIL: &str = "pausing delegated work before the model swap";
const LOADING_DETAIL: &str = "loading the deep model; this takes a few minutes";
const WORKING_DETAIL: &str = "the deep model is working on this";
const RESTORING_DETAIL: &str = "bringing the usual assistant back";
const PHASES: [&str; 4] = [
    DRAINING_DETAIL,
    LOADING_DETAIL,
    WORKING_DETAIL,
    RESTORING_DETAIL,
];
const DEFAULT_PROMPT: &str = "Hand this task to the deep model now by calling the \
    escalate_to_brain tool, and leave the answer to the deep model: in two sentences, explain why \
    the sum of the first n odd numbers is n squared.";

/// What the command line told the client to do with an `escalate_to_brain` card.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Decision {
    Approve,
    Deny,
}

/// How much of the swap the run expects: every phase, or an ordered prefix cut by a kill.
#[derive(Clone, Copy, PartialEq, Eq)]
enum Expect {
    Complete,
    Cut,
}

fn env_or(name: &str, default: &str) -> String {
    std::env::var(name)
        .ok()
        .filter(|value| !value.is_empty())
        .unwrap_or_else(|| default.to_owned())
}

fn decision() -> Decision {
    match env_or("CORTEX_HANDOFF_DECISION", "").as_str() {
        "approve" => Decision::Approve,
        "deny" => Decision::Deny,
        other => panic!("CORTEX_HANDOFF_DECISION must be approve or deny, got {other:?}"),
    }
}

fn expect() -> Expect {
    match env_or("CORTEX_HANDOFF_EXPECT", "complete").as_str() {
        "complete" => Expect::Complete,
        "cut" => Expect::Cut,
        other => panic!("CORTEX_HANDOFF_EXPECT must be complete or cut, got {other:?}"),
    }
}

fn session_id() -> String {
    let nanos = match SystemTime::now().duration_since(UNIX_EPOCH) {
        Ok(elapsed) => elapsed.as_nanos(),
        Err(error) => panic!("system clock predates the unix epoch: {error}"),
    };
    env_or(
        "CORTEX_HANDOFF_SESSION",
        &format!("live-handoff-{}-{nanos}", std::process::id()),
    )
}

/// Reads `Health` on its own connection every `period` until `done` changes, one line per read.
async fn poll_health(
    client: BrainRpcClient,
    started: Instant,
    period: Duration,
    mut done: watch::Receiver<bool>,
) {
    loop {
        let line = match client.health().await {
            Ok(health) => format!("ready={} detail={:?}", health.ready, health.detail),
            Err(error) => format!("error={error}"),
        };
        println!("+{} health {line}", started.elapsed().as_millis());
        tokio::select! {
            () = tokio::time::sleep(period) => {}
            _ = done.changed() => return,
        }
    }
}

/// The swapping details seen, checked against the order the conductor sends them in.
fn check_phases(seen: &[String], expect: Expect) {
    let mut order: Vec<usize> = seen
        .iter()
        .map(
            |detail| match PHASES.iter().position(|phase| phase == detail) {
                Some(index) => index,
                None => panic!("an unknown swapping detail arrived: {detail:?}"),
            },
        )
        .collect();
    // The brain sends a swap's detail again when a wait nested in it closes, such as the deep
    // model's generation or a tool call it made, so a detail may repeat in place.
    order.dedup();
    let in_order = order.iter().enumerate().all(|(at, index)| *index == at);
    match expect {
        Expect::Complete => assert!(
            in_order && order.len() == PHASES.len(),
            "expected the four swapping details in order, saw {seen:?}"
        ),
        Expect::Cut => assert!(
            in_order && order.len() >= 2,
            "expected an ordered prefix of the swap reaching loading, saw {seen:?}"
        ),
    }
}

#[tokio::test(flavor = "multi_thread", worker_threads = 2)]
#[ignore = "live handoff: needs a real brain with escalation on and a deep tier (just rpc-handoff)"]
async fn one_turn_sends_the_decision_its_command_line_names() {
    let decision = decision();
    let expect = expect();
    let addr = env_or("CORTEX_BRAIN_ADDR", "http://127.0.0.1:23051");
    let token = std::env::var("CORTEX_SEAM_TOKEN")
        .ok()
        .filter(|t| !t.is_empty());
    let prompt = env_or("CORTEX_HANDOFF_PROMPT", DEFAULT_PROMPT);
    let health_ms: u64 = match env_or("CORTEX_HANDOFF_HEALTH_MS", "2000").parse() {
        Ok(ms) => ms,
        Err(error) => panic!("CORTEX_HANDOFF_HEALTH_MS is not a whole number: {error}"),
    };
    let connect =
        |what: &str| match BrainRpcClient::connect_lazy_with_token(&addr, token.as_deref()) {
            Ok(client) => client,
            Err(error) => panic!("cannot build the {what} client for {addr}: {error}"),
        };
    let turn_client = connect("turn");
    let health_client = connect("health");
    let session = session_id();

    let (stop, stopped) = watch::channel(false);
    let started = Instant::now();
    let poller = (health_ms > 0).then(|| {
        tokio::spawn(poll_health(
            health_client,
            started,
            Duration::from_millis(health_ms),
            stopped,
        ))
    });
    println!("+0 turn session={session} decision={decision:?} prompt={prompt:?}");

    let (answers, decisions) = mpsc::unbounded_channel::<ConfirmDecision>();
    let mut events = pin!(turn_client.converse(
        &session,
        &prompt,
        Vec::new(),
        UnboundedReceiverStream::new(decisions),
    ));
    let mut escalations = 0_usize;
    let mut phases: Vec<String> = Vec::new();
    let ended = loop {
        let event = match events.next().await {
            Some(Ok(event)) => event,
            Some(Err(error)) => break Err(format!("transport error: {error}")),
            None => break Err(String::from("the stream ended without a terminal event")),
        };
        println!("+{} {event:?}", started.elapsed().as_millis());
        match event {
            TurnEvent::ConfirmRequest {
                confirm_id,
                tool_name,
                ..
            } => {
                let approved = tool_name == ESCALATE_TOOL_NAME && decision == Decision::Approve;
                escalations += usize::from(tool_name == ESCALATE_TOOL_NAME);
                println!(
                    "+{} answer {confirm_id} {tool_name} approved={approved}",
                    started.elapsed().as_millis()
                );
                if answers
                    .send(ConfirmDecision {
                        confirm_id,
                        approved,
                    })
                    .is_err()
                {
                    break Err(String::from("the decision stream closed before an answer"));
                }
            }
            TurnEvent::Status { state, detail } if state == SWAPPING => phases.push(detail),
            TurnEvent::Complete { .. } => break Ok(()),
            TurnEvent::Failed { code, message } => break Err(format!("failed [{code}] {message}")),
            _ => {}
        }
    };
    drop(answers);
    let _ = stop.send(true);
    if let Some(poller) = poller {
        let _ = poller.await;
    }
    println!(
        "+{} end escalations={escalations} phases={phases:?} ended={ended:?}",
        started.elapsed().as_millis()
    );

    if let Err(why) = ended {
        panic!("the turn on session {session} did not complete: {why}");
    }
    match decision {
        Decision::Approve => {
            assert!(
                escalations >= 1,
                "no {ESCALATE_TOOL_NAME} confirm arrived on session {session}"
            );
            check_phases(&phases, expect);
        }
        Decision::Deny => assert!(
            phases.is_empty(),
            "a denied turn still swapped on session {session}: {phases:?}"
        ),
    }
}

fn details(phases: &[usize]) -> Vec<String> {
    phases.iter().map(|at| PHASES[*at].to_owned()).collect()
}

#[test]
fn a_detail_repeated_in_place_still_reads_as_the_whole_swap() {
    check_phases(&details(&[0, 1, 2, 2, 3]), Expect::Complete);
    check_phases(&details(&[0, 1, 2, 2, 2, 3, 3]), Expect::Complete);
}

#[test]
fn a_kill_after_the_working_detail_repeats_it_and_is_still_a_prefix() {
    check_phases(&details(&[0, 1, 2, 2]), Expect::Cut);
}

#[test]
#[should_panic(expected = "the four swapping details in order")]
fn two_details_in_the_wrong_order_fail() {
    check_phases(&details(&[0, 2, 1, 3]), Expect::Complete);
}

#[test]
#[should_panic(expected = "the four swapping details in order")]
fn a_complete_turn_without_the_restore_fails() {
    check_phases(&details(&[0, 1, 2, 2]), Expect::Complete);
}

#[test]
#[should_panic(expected = "an ordered prefix of the swap reaching loading")]
fn a_cut_turn_that_never_reached_loading_fails() {
    check_phases(&details(&[0, 0]), Expect::Cut);
}

#[test]
#[should_panic(expected = "an unknown swapping detail arrived")]
fn a_detail_outside_the_four_fails() {
    check_phases(
        &[String::from("waiting for another request's handoff")],
        Expect::Cut,
    );
}
