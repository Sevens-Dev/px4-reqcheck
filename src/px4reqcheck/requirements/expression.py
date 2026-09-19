"""Small, non-executable expression language for numeric thresholds."""

from __future__ import annotations

import ast
import operator
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

BinaryOperator = Literal["+", "-", "*", "/"]

_BINARY: dict[type[ast.operator], object] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_COMPARE: dict[type[ast.cmpop], object] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}


@dataclass(frozen=True)
class ParsedExpression:
    text: str
    tree: ast.Expression
    names: frozenset[str]
    condition: bool

    def evaluate_number(self, values: Mapping[str, float]) -> float:
        if self.condition:
            raise ValueError("condition cannot be evaluated as a number")
        return float(_evaluate(self.tree.body, values))

    def evaluate_condition(self, values: Mapping[str, float]) -> bool:
        if not self.condition:
            raise ValueError("numeric expression cannot be evaluated as a condition")
        result = _evaluate(self.tree.body, values)
        if not isinstance(result, bool):
            raise ValueError("condition did not return a boolean")
        return result


def parse_expression(text: str, *, condition: bool = False) -> ParsedExpression:
    try:
        parsed = ast.parse(text, mode="eval")
    except SyntaxError as error:
        raise ValueError(f"invalid expression: {text}") from error
    names: set[str] = set()
    _validate(parsed.body, names, condition=condition)
    return ParsedExpression(text, parsed, frozenset(names), condition)


def _validate(node: ast.AST, names: set[str], *, condition: bool) -> None:
    if isinstance(node, ast.Name):
        names.add(node.id)
        return
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError("only numeric constants are allowed")
        return
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        _validate(node.left, names, condition=False)
        _validate(node.right, names, condition=False)
        return
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        _validate(node.operand, names, condition=False)
        return
    if condition and isinstance(node, ast.Compare) and len(node.ops) == len(node.comparators) == 1:
        if type(node.ops[0]) not in _COMPARE:
            raise ValueError("comparison operator is not allowed")
        _validate(node.left, names, condition=False)
        _validate(node.comparators[0], names, condition=False)
        return
    raise ValueError(f"expression node is not allowed: {type(node).__name__}")


def _evaluate(node: ast.AST, values: Mapping[str, float]) -> float | bool:
    if isinstance(node, ast.Name):
        if node.id not in values:
            raise ValueError(f"missing expression value: {node.id}")
        return float(values[node.id])
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp):
        operation = _BINARY[type(node.op)]
        if not callable(operation):
            raise ValueError("invalid binary operator")
        return float(operation(_evaluate(node.left, values), _evaluate(node.right, values)))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -float(_evaluate(node.operand, values))
    if isinstance(node, ast.Compare):
        operation = _COMPARE[type(node.ops[0])]
        if not callable(operation):
            raise ValueError("invalid comparison operator")
        return bool(operation(_evaluate(node.left, values), _evaluate(node.comparators[0], values)))
    raise ValueError(f"unvalidated expression node: {type(node).__name__}")
