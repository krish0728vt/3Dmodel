from __future__ import annotations


class DependencyGraphError(ValueError):
    """Raised when the parametric dependency graph is invalid."""


def topological_order(dependencies: dict[str, set[str]]) -> list[str]:
    visiting: set[str] = set()
    visited: set[str] = set()
    order: list[str] = []

    def visit(node: str, stack: list[str]) -> None:
        if node in visited:
            return
        if node in visiting:
            cycle = stack[stack.index(node) :] + [node] if node in stack else stack + [node]
            raise DependencyGraphError("PARAMETRIC DEPENDENCY CYCLE: " + " -> ".join(cycle))
        visiting.add(node)
        for dependency in sorted(dependencies.get(node, set())):
            if dependency in dependencies:
                visit(dependency, stack + [dependency])
        visiting.remove(node)
        visited.add(node)
        order.append(node)

    for node in sorted(dependencies):
        visit(node, [node])
    return order
