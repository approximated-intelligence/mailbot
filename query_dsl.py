# -*- coding: utf-8 -*-
"""
S-expression based DSL for IMAP query construction.
Converts composable query expressions to IMAP SEARCH syntax.

Usage:
    Match(AnyOf(Froms("user@a.com", "user@b.com")))
    Match(AllOf(Froms("@mydomain"), Tos("inbox@")))
    Match(AllOf(Froms("@mydomain"), AnyOf(Tos("@mydomain"), Not(AnyOf(Tos("@"), Ccs("@"))))))
"""


# Combinators
def or_combine(items):
    def reduce():
        result = items[0]()
        for item in items[1:]:
            result = f"(OR {result} {item()})"
        return result

    return reduce


def and_combine(items):
    def reduce():
        result = items[0]()
        for item in items[1:]:
            result = f"({result} {item()})"
        return result

    return reduce


def not_combine(items):
    return lambda: f'(NOT {" ".join(x() for x in items)})'


# Field builders - take multiple values, return list of thunks
def From(*args):
    return [lambda v=a: f'(FROM "{v}")' for a in args]


def To(*args):
    return [lambda v=a: f'(TO "{v}")' for a in args]


def Cc(*args):
    return [lambda v=a: f'(CC "{v}")' for a in args]


def Subject(*args):
    return [lambda v=a: f'(SUBJECT "{v}")' for a in args]


# Plural aliases - clearer API
Froms = From
Tos = To
Ccs = Cc
SubjectPatterns = Subject


# Combinator builders - flatten args and wrap
def AnyOf(*args):
    """Combine matchers with OR - any must match"""
    return [or_combine([x for a in args for x in a])]


def AllOf(*args):
    """Combine matchers with AND - all must match"""
    return [and_combine([x for a in args for x in a])]


def Not(*args):
    """Negate matchers"""
    return [not_combine([x for a in args for x in a])]


# Final evaluation
def parseQuery(expr):
    """Convert expression tree to IMAP SEARCH string"""
    return expr[0]() if len(expr) == 1 else or_combine(expr)()


Match = parseQuery
