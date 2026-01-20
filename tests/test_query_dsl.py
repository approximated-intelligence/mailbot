# -*- coding: utf-8 -*-
"""
Tests for query_dsl.py - IMAP query DSL.
"""

import unittest

from ..query_dsl import (
    AllOf,
    AnyOf,
    Cc,
    Ccs,
    From,
    Froms,
    Match,
    Not,
    Subject,
    SubjectPatterns,
    To,
    Tos,
    parseQuery,
)


class TestFieldBuilders(unittest.TestCase):
    """Tests for field builder functions"""

    def test_from_single_returns_list(self):
        result = From("user@domain")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_from_multiple_returns_list_per_address(self):
        result = From("a@x", "b@x", "c@x")
        self.assertEqual(len(result), 3)

    def test_to_single_returns_list(self):
        result = To("user@domain")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_cc_single_returns_list(self):
        result = Cc("user@domain")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_subject_single_returns_list(self):
        result = Subject("test")
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)

    def test_field_thunks_produce_imap_syntax(self):
        from_thunk = From("user@domain")[0]
        self.assertEqual(from_thunk(), '(FROM "user@domain")')

        to_thunk = To("user@domain")[0]
        self.assertEqual(to_thunk(), '(TO "user@domain")')

        cc_thunk = Cc("user@domain")[0]
        self.assertEqual(cc_thunk(), '(CC "user@domain")')

        subject_thunk = Subject("test")[0]
        self.assertEqual(subject_thunk(), '(SUBJECT "test")')


class TestPluralAliases(unittest.TestCase):
    """Tests for plural aliases"""

    def test_froms_is_alias_for_from(self):
        self.assertIs(Froms, From)

    def test_tos_is_alias_for_to(self):
        self.assertIs(Tos, To)

    def test_ccs_is_alias_for_cc(self):
        self.assertIs(Ccs, Cc)

    def test_subjectpatterns_is_alias_for_subject(self):
        self.assertIs(SubjectPatterns, Subject)

    def test_froms_produces_same_result(self):
        self.assertEqual(Match(AnyOf(From("a@x"))), Match(AnyOf(Froms("a@x"))))

    def test_tos_produces_same_result(self):
        self.assertEqual(Match(AnyOf(To("a@x"))), Match(AnyOf(Tos("a@x"))))


class TestCombinators(unittest.TestCase):
    """Tests for AnyOf, AllOf, Not combinators"""

    def test_anyof_single_field_single_value(self):
        result = Match(AnyOf(From("user@domain")))
        self.assertEqual(result, '(FROM "user@domain")')

    def test_anyof_single_field_multiple_values(self):
        result = Match(AnyOf(From("a@x", "b@x")))
        self.assertEqual(result, '(OR (FROM "a@x") (FROM "b@x"))')

    def test_anyof_single_field_three_values(self):
        result = Match(AnyOf(From("a@x", "b@x", "c@x")))
        self.assertEqual(result, '(OR (OR (FROM "a@x") (FROM "b@x")) (FROM "c@x"))')

    def test_allof_single_field_single_value(self):
        result = Match(AllOf(From("user@domain")))
        self.assertEqual(result, '(FROM "user@domain")')

    def test_allof_single_field_multiple_values(self):
        result = Match(AllOf(From("a@x", "b@x")))
        self.assertEqual(result, '((FROM "a@x") (FROM "b@x"))')

    def test_allof_multiple_fields(self):
        result = Match(AllOf(From("sender@x"), To("recipient@y")))
        self.assertEqual(result, '((FROM "sender@x") (TO "recipient@y"))')

    def test_not_single_value(self):
        result = Match(Not(From("spam@x")))
        self.assertEqual(result, '(NOT (FROM "spam@x"))')

    def test_not_anyof(self):
        result = Match(Not(AnyOf(To("@"), Cc("@"))))
        self.assertEqual(result, '(NOT (OR (TO "@") (CC "@")))')


class TestNestedExpressions(unittest.TestCase):
    """Tests for complex nested query expressions"""

    def test_allof_with_nested_anyof(self):
        result = Match(AllOf(From("@mydomain"), AnyOf(To("a@x"), To("b@x"))))
        self.assertIn('FROM "@mydomain"', result)
        self.assertIn("OR", result)
        self.assertIn('TO "a@x"', result)
        self.assertIn('TO "b@x"', result)

    def test_anyof_with_nested_allof(self):
        result = Match(AnyOf(AllOf(From("a@x"), To("b@x")), From("c@x")))
        self.assertIn("OR", result)
        self.assertIn('FROM "a@x"', result)
        self.assertIn('TO "b@x"', result)
        self.assertIn('FROM "c@x"', result)

    def test_complex_self_email_query(self):
        """Test the 'emails from self without explicit recipients' pattern"""
        mydomain = "@mydomain"
        result = Match(
            AllOf(Froms(mydomain), AnyOf(Tos(mydomain), Not(AnyOf(Tos("@"), Ccs("@")))))
        )
        self.assertIn('FROM "@mydomain"', result)
        self.assertIn('TO "@mydomain"', result)
        self.assertIn("NOT", result)
        self.assertIn('CC "@"', result)

    def test_deeply_nested(self):
        result = Match(
            AllOf(From("a@x"), AnyOf(AllOf(To("b@x"), Cc("c@x")), Not(From("d@x"))))
        )
        self.assertIn('FROM "a@x"', result)
        self.assertIn('TO "b@x"', result)
        self.assertIn('CC "c@x"', result)
        self.assertIn("NOT", result)
        self.assertIn('FROM "d@x"', result)


class TestMatchFunction(unittest.TestCase):
    """Tests for the Match/parseQuery function"""

    def test_match_is_alias_for_parsequery(self):
        self.assertIs(Match, parseQuery)

    def test_match_single_from(self):
        result = Match(From("user@domain"))
        self.assertEqual(result, '(FROM "user@domain")')

    def test_match_multiple_from_implicit_or(self):
        """Multiple From values without combinator should OR them"""
        result = Match(From("a@x", "b@x"))
        self.assertEqual(result, '(OR (FROM "a@x") (FROM "b@x"))')

    def test_match_empty_string_preserved(self):
        result = Match(From(""))
        self.assertEqual(result, '(FROM "")')


class TestConfigQueriesPatterns(unittest.TestCase):
    """Tests matching actual patterns from config_queries.py"""

    def test_work_senders_pattern(self):
        work_senders = ["arbeit@", "@uni"]
        result = Match(AnyOf(Froms(*work_senders)))
        self.assertEqual(result, '(OR (FROM "arbeit@") (FROM "@uni"))')

    def test_newsletters_pattern(self):
        newsletters = ["civey@", "academicpositions@"]
        result = Match(AnyOf(Tos(*newsletters)))
        self.assertEqual(result, '(OR (TO "civey@") (TO "academicpositions@"))')

    def test_proxy_pattern(self):
        mydomain = "@mydomain"
        proxy_to = "be1919cc@mydomain"
        result = Match(AllOf(Froms(mydomain), Tos(proxy_to)))
        self.assertIn('(FROM "@mydomain")', result)
        self.assertIn('(TO "be1919cc@mydomain")', result)

    def test_self_without_recipients_pattern(self):
        mydomain = "@mydomain"
        result = Match(
            AllOf(Froms(mydomain), AnyOf(Tos(mydomain), Not(AnyOf(Tos("@"), Ccs("@")))))
        )
        self.assertIn('FROM "@mydomain"', result)
        self.assertIn("NOT", result)

    def test_single_sender_pattern(self):
        mydomain = "@mydomain"
        result = Match(AnyOf(Froms(mydomain)))
        self.assertEqual(result, '(FROM "@mydomain")')

    def test_single_element_list_expansion(self):
        """Ensure *list expansion works with single elements"""
        emails = ["test@example.com"]
        result = Match(AnyOf(Tos(*emails)))
        self.assertEqual(result, '(TO "test@example.com")')


class TestIMAPSyntaxValidity(unittest.TestCase):
    """Tests that generated queries are valid IMAP SEARCH syntax"""

    def test_no_unmatched_parens(self):
        queries = [
            Match(AnyOf(Froms("a@x", "b@x", "c@x"))),
            Match(AllOf(Froms("a@x"), Tos("b@x"), Ccs("c@x"))),
            Match(
                AllOf(
                    Froms("@mydomain"),
                    AnyOf(Tos("@mydomain"), Not(AnyOf(Tos("@"), Ccs("@")))),
                )
            ),
        ]
        for query in queries:
            open_count = query.count("(")
            close_count = query.count(")")
            self.assertEqual(open_count, close_count, f"Unmatched parens in: {query}")

    def test_valid_imap_keywords(self):
        """Ensure only valid IMAP SEARCH keywords are used"""
        import re

        valid_keywords = {"FROM", "TO", "CC", "SUBJECT", "OR", "NOT"}

        queries = [
            Match(Froms("a@x")),
            Match(Tos("a@x")),
            Match(Ccs("a@x")),
            Match(SubjectPatterns("test")),
            Match(AnyOf(Froms("a@x"), Tos("b@x"))),
            Match(Not(Froms("a@x"))),
        ]

        for query in queries:
            keywords = re.findall(r"\(([A-Z]+)", query)
            for kw in keywords:
                self.assertIn(kw, valid_keywords, f"Invalid keyword {kw} in: {query}")

    def test_quoted_addresses(self):
        """Ensure addresses are properly quoted"""
        queries = [
            Match(Froms("user@domain.com")),
            Match(Froms("user with spaces@domain.com")),
            Match(Froms("@partial")),
        ]
        for query in queries:
            self.assertIn('"', query)


class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases and boundary conditions"""

    def test_special_characters_in_address(self):
        result = Match(Froms("user+tag@domain.com"))
        self.assertEqual(result, '(FROM "user+tag@domain.com")')

    def test_partial_domain_match(self):
        result = Match(Froms("@gmail.com"))
        self.assertEqual(result, '(FROM "@gmail.com")')

    def test_partial_local_match(self):
        result = Match(Tos("newsletter@"))
        self.assertEqual(result, '(TO "newsletter@")')

    def test_subject_with_spaces(self):
        result = Match(SubjectPatterns("Re: Your inquiry"))
        self.assertEqual(result, '(SUBJECT "Re: Your inquiry")')

    def test_many_or_values(self):
        addresses = [f"user{i}@domain.com" for i in range(5)]
        result = Match(AnyOf(Froms(*addresses)))
        self.assertEqual(result.count("OR"), 4)
        for addr in addresses:
            self.assertIn(addr, result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
