import pytest

from cortex_core import TaintLedger
from cortex_core.access_claim import claims_no_access, unsearched_files_claim

_RECORDED = (
    "I'm sorry, but I don't have access to your personal files or a \"budget spreadsheet\" unless "
    "you provide it or tell me where it is located.  If you have a file saved in a directory I can "
    "access, please let me know the path."
)


@pytest.mark.parametrize(
    "reply",
    [
        "I'd be happy to remember that! Could you please provide the address from your lease?",
        "Could you please tell me where your lease is located, or point me toward the folder?",
        "If you have a file saved in a directory I can access, please let me know the path.",
        "If I can't access the file, I will ask you for the total.",
        "Once you give me access, I can read it.",
        "Don't I have access to your files?",
        "So I cannot access the folder you named?",
        "Can you give me access to the folder?",
        "I can access the folder you named.",
        "The lease is accessible to you, so paste the address here.",
        "You have access to the lease, so paste the address here.",
        "Noted. I'll keep that in mind.",
    ],
)
def test_a_reply_that_states_no_lack_of_access_is_not_a_claim(reply: str) -> None:
    assert not claims_no_access(reply)


@pytest.mark.parametrize(
    "reply",
    [
        _RECORDED,
        "I'm sorry, but I don't have access to your invoices or any previous records.",
        "I do not have access to your lease.",
        "I don\u2019t have any access to your files.",
        "Sorry, I can't access your spreadsheet. Please paste the total.",
        "I cannot access files on your computer.",
        "I'm unable to access your documents.",
        "I am not able to access that folder.",
        "Noted.\nI have no access to the file, so please tell me the address.",
        "The assistant doesn't have access to your files.",
        "The file appears to be unavailable or inaccessible.",
        "If you like, I can keep it in mind. I don't have access to your lease.",
    ],
)
def test_a_reply_that_says_it_has_no_access_is_a_claim(reply: str) -> None:
    assert claims_no_access(reply)


def test_the_claim_needs_a_sidecar_call_refused_this_turn() -> None:
    assert not unsearched_files_claim(TaintLedger(), _RECORDED)
    assert unsearched_files_claim(TaintLedger(sidecar_refused=True), _RECORDED)
    assert not unsearched_files_claim(TaintLedger(sidecar_refused=True), "Noted the address.")
