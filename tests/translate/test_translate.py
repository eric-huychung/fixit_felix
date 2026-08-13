"""Tests for LLM interface and formula translation."""

from pathlib import Path

from felix.cache import Cache
from felix.llm import FakeProvider
from felix.models import FieldConstraint, ValidationRuleConstraint
from felix.translate import _build_user_prompt, translate_rule, translate_rules


def _sample_rule(**overrides: object) -> ValidationRuleConstraint:
    base = {
        "id": "03d000000000001AAA",
        "object_name": "Opportunity",
        "name": "Amount_Requires_Sponsor",
        "active": True,
        "namespace_prefix": None,
        "error_message": "Please contact your administrator.",
        "error_display_field": "Amount",
        "formula": "AND(Amount > 100000, ISBLANK(Executive_Sponsor__c))",
        "formula_hash": "hash-v1",
        "fields_referenced": ["Amount", "Executive_Sponsor__c"],
    }
    base.update(overrides)
    return ValidationRuleConstraint.model_validate(base)


def _sample_fields() -> list[FieldConstraint]:
    return [
        FieldConstraint(
            object_name="Opportunity",
            api_name="Amount",
            label="Amount",
            soap_type="xsd:double",
            required=False,
        ),
        FieldConstraint(
            object_name="Opportunity",
            api_name="Executive_Sponsor__c",
            label="Executive Sponsor",
            soap_type="xsd:string",
            required=False,
        ),
    ]


def test_fake_provider_records_calls_without_network() -> None:
    provider = FakeProvider("ok")
    assert provider.complete("sys", "user") == "ok"
    assert provider.calls == [("sys", "user")]


def test_outbound_prompt_contains_no_record_payload_keys() -> None:
    """Safety invariant: record data never reaches the LLM."""
    sample_record = {
        "Name": "Acme Mega Deal",
        "Amount": 250000,
        "StageName": "Prospecting",
        "AccountId": "001000000000001AAA",
        "CloseDate": "2026-12-01",
    }
    rule = _sample_rule()
    prompt = _build_user_prompt(
        rule,
        {"Amount": "Amount", "Executive_Sponsor__c": "Executive Sponsor"},
    )
    provider = FakeProvider()
    translate_rule(rule, _sample_fields(), provider)

    outbound = provider.calls[0][1]
    for key, value in sample_record.items():
        assert str(value) not in outbound
        # Field API names may appear (Amount, StageName as labels/refs) — values must not.
        if key not in {"Amount"}:  # Amount is a field name in the formula, not a value
            assert str(sample_record[key]) not in prompt
    assert "Acme Mega Deal" not in outbound
    assert "001000000000001AAA" not in outbound
    assert "250000" not in outbound


def test_translation_uses_cache_on_second_call(tmp_path: Path) -> None:
    provider = FakeProvider("Set Executive_Sponsor__c when Amount > 100000.")
    cache = Cache(tmp_path / "cache.sqlite")
    rule = _sample_rule()
    fields = _sample_fields()

    first = translate_rule(rule, fields, provider, cache=cache, org_id="00DORG")
    second = translate_rule(rule, fields, provider, cache=cache, org_id="00DORG")

    assert first.plain_english == second.plain_english
    assert len(provider.calls) == 1


def test_formula_change_invalidates_cache(tmp_path: Path) -> None:
    provider = FakeProvider("v1 text")
    cache = Cache(tmp_path / "cache.sqlite")
    fields = _sample_fields()

    rule_v1 = _sample_rule(formula_hash="hash-v1")
    translate_rule(rule_v1, fields, provider, cache=cache, org_id="00DORG")

    provider.response = "v2 text"
    rule_v2 = _sample_rule(
        formula_hash="hash-v2",
        formula="AND(Amount > 200000, ISBLANK(Executive_Sponsor__c))",
    )
    updated = translate_rule(rule_v2, fields, provider, cache=cache, org_id="00DORG")

    assert len(provider.calls) == 2
    assert updated.plain_english == "v2 text"


def test_rename_does_not_bust_cache(tmp_path: Path) -> None:
    """Cache key is (rule_id, formula_hash) — renaming the rule must not re-call."""
    provider = FakeProvider("cached meaning")
    cache = Cache(tmp_path / "cache.sqlite")
    fields = _sample_fields()

    translate_rule(_sample_rule(name="Old_Name"), fields, provider, cache=cache, org_id="00DORG")
    again = translate_rule(
        _sample_rule(name="New_Name"),
        fields,
        provider,
        cache=cache,
        org_id="00DORG",
    )

    assert len(provider.calls) == 1
    assert again.plain_english == "cached meaning"


def test_translate_rules_batch(tmp_path: Path) -> None:
    provider = FakeProvider("plain")
    rules = [
        _sample_rule(id="r1", formula_hash="h1"),
        _sample_rule(id="r2", formula_hash="h2", name="Other"),
    ]
    out = translate_rules(
        rules,
        _sample_fields(),
        provider,
        cache=Cache(tmp_path / "c.sqlite"),
        org_id="00DORG",
    )
    assert all(r.plain_english == "plain" for r in out)
    assert len(provider.calls) == 2
