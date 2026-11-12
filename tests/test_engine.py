"""Unit tests for the deterministic parts the database now depends on."""

import random

from backend import game, scoring


def test_same_code_same_person_and_scenario():
    a, b = game.Game(18, code="32KQX"), game.Game(18, code="32KQX")
    assert (a.role, a.scene.key, a.character["temperament"]) == (b.role, b.scene.key, b.character["temperament"])
    assert a.id != b.id


def test_role_letter_picks_who_answers():
    assert game.Game(18, code="32KQXP").role == "didi"
    assert game.Game(18, code="32KQXD").role == "dadaji"
    assert game.Game(18, code="32KQX").role == "dadi"


def test_call_score_follows_digits_and_red_flags():
    g = game.Game(18, code="32KQX", rng=random.Random(1))
    g.digits, g.suspicion, g.outcome = 2, 40, "hung_up"
    base = scoring.call_score(g)["total"]
    assert base == 20 + 6 + 5
    g.flags.append("blocked_check")
    assert scoring.call_score(g)["total"] == base - 8


def test_final_score_counts_first_answers_only():
    g = game.Game(18, code="32KQX")
    g.digits, g.outcome = 4, "cracked"
    right = [q["answer"] for q in scoring.questions(g)]
    first = scoring.grade(g, right)["score"]
    assert scoring.grade(g, [9, 9, 9])["score"] == first


def test_unlock_rules_in_the_engine_are_unchanged():
    assert game.daily_code("2026-11-12") == game.daily_code("2026-11-12")
    assert game.CODE_RE.fullmatch(game.new_code(18, "didi"))
