#!/usr/bin/env python3
"""
Validate prerequisite dependency graph is a valid DAG.

Checks:
- No circular dependencies
- No orphaned (unreachable) modules
- Progression rules (scaffolding/Bloom) are followed
- All prerequisite references are valid

Usage:
    python validate_graph.py <modules-directory> [--visualize] [--output graph.png]

Example:
    python validate_graph.py ./modules
    python validate_graph.py ./modules --visualize --output prereq_graph.png
"""

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any


# Bloom's taxonomy order
BLOOM_ORDER = ['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create']

# Scaffolding numeric values
SCAFFOLDING_VALUE = {'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}


def discover_modules(modules_dir: Path) -> dict[int, dict[str, Any]]:
    """
    Discover and load all modules from directory.

    Args:
        modules_dir: Path to modules directory

    Returns:
        Dictionary mapping module_id -> metadata

    Raises:
        ValueError: If module structure is invalid
    """
    modules = {}

    # Find all module_XX directories
    module_dirs = sorted(modules_dir.glob("module_*"))

    if not module_dirs:
        raise ValueError(f"No modules found in {modules_dir}")

    for module_dir in module_dirs:
        if not module_dir.is_dir():
            continue

        metadata_path = module_dir / 'metadata.py'
        if not metadata_path.exists():
            print(f"⚠️ Warning: {module_dir.name} missing metadata.py, skipping")
            continue

        try:
            # Import metadata module
            spec = importlib.util.spec_from_file_location('metadata', metadata_path)
            if spec is None or spec.loader is None:
                print(f"⚠️ Warning: Failed to load {module_dir.name}/metadata.py, skipping")
                continue

            metadata_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(metadata_module)

            if not hasattr(metadata_module, 'METADATA'):
                print(f"⚠️ Warning: {module_dir.name}/metadata.py missing METADATA, skipping")
                continue

            metadata = metadata_module.METADATA
            module_id = metadata.get('id')

            if module_id is None:
                print(f"⚠️ Warning: {module_dir.name} metadata missing 'id', skipping")
                continue

            if module_id in modules:
                raise ValueError(f"Duplicate module ID {module_id} in {module_dir.name}")

            modules[module_id] = metadata

        except Exception as e:
            print(f"⚠️ Warning: Error loading {module_dir.name}: {e}, skipping")
            continue

    return modules


def validate_prerequisite_references(modules: dict[int, dict[str, Any]]) -> list[str]:
    """
    Check that all prerequisite IDs reference existing modules.

    Args:
        modules: Module dictionary

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    for module_id, metadata in modules.items():
        prereqs = metadata.get('prerequisites', [])

        for prereq_id in prereqs:
            if prereq_id not in modules:
                errors.append(
                    f"Module {module_id} ({metadata.get('title', 'Unknown')}) "
                    f"references non-existent prerequisite: {prereq_id}"
                )

    return errors


def detect_cycles(modules: dict[int, dict[str, Any]]) -> list[str]:
    """
    Detect circular dependencies using DFS.

    Args:
        modules: Module dictionary

    Returns:
        List of errors describing cycles (empty if none)
    """
    errors = []

    # Build adjacency list
    graph = {mid: set(m.get('prerequisites', [])) for mid, m in modules.items()}

    def has_cycle(node: int, visited: set[int], rec_stack: set[int]) -> bool:
        """DFS cycle detection with recursion stack."""
        visited.add(node)
        rec_stack.add(node)

        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                if has_cycle(neighbor, visited, rec_stack):
                    return True
            elif neighbor in rec_stack:
                # Found back edge = cycle
                return True

        rec_stack.remove(node)
        return False

    visited: set[int] = set()

    for module_id in graph:
        if module_id not in visited:
            if has_cycle(module_id, visited, set()):
                errors.append(
                    f"Circular dependency detected involving module {module_id} "
                    f"({modules[module_id].get('title', 'Unknown')})"
                )

    return errors


def detect_orphans(modules: dict[int, dict[str, Any]]) -> list[str]:
    """
    Detect unreachable (orphaned) modules.

    Args:
        modules: Module dictionary

    Returns:
        List of errors describing orphans (empty if none)
    """
    errors = []

    # Build adjacency list
    graph = {mid: set(m.get('prerequisites', [])) for mid, m in modules.items()}

    # Find foundation modules (no prerequisites)
    foundation_modules = {mid for mid, prereqs in graph.items() if not prereqs}

    if not foundation_modules:
        errors.append("No foundation modules found (modules with empty prerequisites list)")
        return errors

    # Iteratively expand reachable set
    reachable = foundation_modules.copy()
    changed = True

    while changed:
        changed = False
        for mid, prereqs in graph.items():
            if mid not in reachable and prereqs.issubset(reachable):
                reachable.add(mid)
                changed = True

    # Find orphaned modules
    orphaned = set(graph.keys()) - reachable

    if orphaned:
        orphan_details = [
            f"{mid} ({modules[mid].get('title', 'Unknown')})"
            for mid in sorted(orphaned)
        ]

        errors.append(
            f"Unreachable modules (cannot be reached from foundation modules):\n" +
            "\n".join(f"  - {detail}" for detail in orphan_details) +
            f"\n  Foundation modules: {sorted(foundation_modules)}"
        )

    return errors


def validate_progression_rules(modules: dict[int, dict[str, Any]]) -> list[str]:
    """
    Validate progressive complexity ladder rules.

    Rules:
    - Don't increase Bloom level AND decrease scaffolding simultaneously

    Args:
        modules: Module dictionary

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    for module_id, module in modules.items():
        for prereq_id in module.get('prerequisites', []):
            if prereq_id not in modules:
                continue  # Already caught by prerequisite reference validation

            prereq = modules[prereq_id]

            # Get Bloom levels
            curr_bloom = module.get('bloom_level')
            prereq_bloom = prereq.get('bloom_level')

            if curr_bloom not in BLOOM_ORDER or prereq_bloom not in BLOOM_ORDER:
                continue  # Skip if invalid Bloom levels (caught by module validation)

            curr_bloom_idx = BLOOM_ORDER.index(curr_bloom)
            prereq_bloom_idx = BLOOM_ORDER.index(prereq_bloom)

            # Get scaffolding levels
            curr_scaffolding = module.get('scaffolding_level')
            prereq_scaffolding = prereq.get('scaffolding_level')

            if curr_scaffolding not in SCAFFOLDING_VALUE or prereq_scaffolding not in SCAFFOLDING_VALUE:
                continue  # Skip if invalid scaffolding (caught by module validation)

            curr_scaffolding_val = SCAFFOLDING_VALUE[curr_scaffolding]
            prereq_scaffolding_val = SCAFFOLDING_VALUE[prereq_scaffolding]

            # Rule: Don't increase Bloom AND decrease scaffolding
            if curr_bloom_idx > prereq_bloom_idx and curr_scaffolding_val < prereq_scaffolding_val:
                errors.append(
                    f"Module {module_id} ({module.get('title', 'Unknown')}) violates progression rules:\n"
                    f"  Increases Bloom level: {prereq_bloom} -> {curr_bloom}\n"
                    f"  AND decreases scaffolding: {prereq_scaffolding} -> {curr_scaffolding}\n"
                    f"  (relative to prerequisite Module {prereq_id})\n"
                    f"  → Maintain or increase scaffolding when advancing Bloom level"
                )

    return errors


def generate_visualization(
    modules: dict[int, dict[str, Any]],
    output_path: str
) -> None:
    """
    Generate prerequisite graph visualization using Graphviz.

    Args:
        modules: Module dictionary
        output_path: Path to save PNG file

    Raises:
        ImportError: If graphviz not installed
    """
    try:
        from graphviz import Digraph
    except ImportError:
        raise ImportError(
            "Graphviz not installed. Install with: pip install graphviz\n"
            "Also requires system graphviz: brew install graphviz (macOS) or apt-get install graphviz (Linux)"
        )

    dot = Digraph(comment='Module Prerequisites')
    dot.attr(rankdir='TB')  # Top to bottom layout
    dot.attr('node', shape='box', style='rounded,filled')

    # Color by scaffolding level
    colors = {
        'HIGH': 'lightgreen',
        'MEDIUM': 'lightyellow',
        'LOW': 'lightcoral',
    }

    # Add nodes
    for module_id, module in modules.items():
        label = (
            f"M{module_id}\n"
            f"{module.get('bloom_level', 'Unknown')}\n"
            f"({module.get('scaffolding_level', 'Unknown')})"
        )
        color = colors.get(module.get('scaffolding_level'), 'white')
        dot.node(str(module_id), label, fillcolor=color)

    # Add edges (prerequisites)
    for module_id, module in modules.items():
        for prereq_id in module.get('prerequisites', []):
            if prereq_id in modules:  # Only add edge if prereq exists
                dot.edge(str(prereq_id), str(module_id))

    # Render
    output_base = output_path.replace('.png', '')
    dot.render(output_base, format='png', cleanup=True)
    print(f"📊 Graph visualization saved to: {output_base}.png")


def format_validation_report(
    modules_dir: Path,
    modules: dict[int, dict[str, Any]],
    all_errors: list[str]
) -> str:
    """Format validation report for display."""
    report = [
        f"\n{'='*70}",
        f"Prerequisite Graph Validation: {modules_dir}",
        f"{'='*70}\n",
        f"Found {len(modules)} modules\n",
    ]

    if not all_errors:
        report.append("✅ All graph validation checks passed!\n")
        report.append("Graph is a valid DAG:")
        report.append("  - ✅ No circular dependencies")
        report.append("  - ✅ No orphaned modules")
        report.append("  - ✅ Progression rules followed")
        report.append("  - ✅ All prerequisite references valid")
    else:
        report.append(f"❌ Found {len(all_errors)} graph validation error(s):\n")

        for i, error in enumerate(all_errors, 1):
            # Add spacing between errors for readability
            report.append(f"Error {i}:")
            for line in error.split('\n'):
                report.append(f"  {line}")
            report.append("")

        report.append("📝 Fix these issues and run validation again.")

    report.append(f"{'='*70}\n")

    return '\n'.join(report)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Validate prerequisite dependency graph.'
    )

    parser.add_argument(
        'modules_dir',
        type=str,
        help='Path to modules directory (e.g., ./modules)'
    )

    parser.add_argument(
        '--visualize',
        action='store_true',
        help='Generate graph visualization (requires graphviz)'
    )

    parser.add_argument(
        '--output',
        type=str,
        default='prereq_graph.png',
        help='Output path for visualization (default: prereq_graph.png)'
    )

    args = parser.parse_args()

    try:
        modules_dir = Path(args.modules_dir)

        if not modules_dir.exists():
            print(f"❌ Error: Modules directory not found: {modules_dir}", file=sys.stderr)
            return 1

        if not modules_dir.is_dir():
            print(f"❌ Error: Path is not a directory: {modules_dir}", file=sys.stderr)
            return 1

        # Discover modules
        print(f"🔍 Discovering modules in {modules_dir}...")
        modules = discover_modules(modules_dir)

        if not modules:
            print(f"❌ Error: No valid modules found in {modules_dir}", file=sys.stderr)
            return 1

        print(f"   Found {len(modules)} modules")

        # Run validation checks
        all_errors = []

        print("🔍 Validating prerequisite references...")
        errors = validate_prerequisite_references(modules)
        all_errors.extend(errors)

        print("🔍 Detecting circular dependencies...")
        errors = detect_cycles(modules)
        all_errors.extend(errors)

        print("🔍 Detecting orphaned modules...")
        errors = detect_orphans(modules)
        all_errors.extend(errors)

        print("🔍 Validating progression rules...")
        errors = validate_progression_rules(modules)
        all_errors.extend(errors)

        # Display report
        report = format_validation_report(modules_dir, modules, all_errors)
        print(report)

        # Generate visualization if requested
        if args.visualize:
            print("📊 Generating graph visualization...")
            try:
                generate_visualization(modules, args.output)
            except ImportError as e:
                print(f"⚠️ Warning: {e}", file=sys.stderr)
                print("   Skipping visualization")

        return 0 if len(all_errors) == 0 else 1

    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
