from __future__ import annotations

from pydantic import TypeAdapter

from parametrics.models import BinaryExpression, Expression, LiteralExpression, ParameterReferenceExpression


class ExpressionEvaluationError(ValueError):
    """Raised when a typed parametric expression cannot be evaluated."""


EXPRESSION_ADAPTER = TypeAdapter(Expression)


def _coerce_expression(expression: Expression | dict[str, object]) -> Expression:
    if isinstance(expression, dict):
        return EXPRESSION_ADAPTER.validate_python(expression)
    return expression


def expression_dependencies(expression: Expression) -> set[str]:
    expression = _coerce_expression(expression)
    if isinstance(expression, LiteralExpression):
        return set()
    if isinstance(expression, ParameterReferenceExpression):
        return {expression.parameter_id}
    if isinstance(expression, BinaryExpression):
        return expression_dependencies(expression.left) | expression_dependencies(expression.right)
    raise ExpressionEvaluationError(f"Unsupported expression node: {type(expression).__name__}")


def evaluate_expression(expression: Expression, parameters: dict[str, float]) -> float:
    expression = _coerce_expression(expression)
    if isinstance(expression, LiteralExpression):
        return float(expression.value)
    if isinstance(expression, ParameterReferenceExpression):
        if expression.parameter_id not in parameters:
            raise ExpressionEvaluationError(f"MISSING PARAMETER: {expression.parameter_id}")
        return float(parameters[expression.parameter_id])
    if isinstance(expression, BinaryExpression):
        left = evaluate_expression(expression.left, parameters)
        right = evaluate_expression(expression.right, parameters)
        if expression.expression_type == "add":
            return left + right
        if expression.expression_type == "subtract":
            return left - right
        if expression.expression_type == "multiply":
            return left * right
        if expression.expression_type == "divide":
            if right == 0:
                raise ExpressionEvaluationError("PARAMETRIC EXPRESSION DIVISION BY ZERO")
            return left / right
        if expression.expression_type == "min":
            return min(left, right)
        if expression.expression_type == "max":
            return max(left, right)
    raise ExpressionEvaluationError(f"Unsupported expression node: {type(expression).__name__}")


def literal_or_expression_value(value: float | Expression, parameters: dict[str, float]) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return evaluate_expression(value, parameters)
