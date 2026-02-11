# Architecture Patterns for Progressive Learning Systems

This reference provides detailed architecture patterns, code implementations, and validation systems for building module-based progressive learning platforms. Use this when implementing the technical infrastructure that supports cognitive science principles.

---

## Table of Contents

1. [Module-Based Structure](#module-based-structure)
2. [Metadata-Driven Design](#metadata-driven-design)
3. [Progressive Complexity Ladder](#progressive-complexity-ladder)
4. [Dynamic Module Loading](#dynamic-module-loading)
5. [Prerequisite Graph Validation](#prerequisite-graph-validation)
6. [Progress Tracking](#progress-tracking)
7. [Fail-Fast Validation](#fail-fast-validation)
8. [Working Code Patterns](#working-code-patterns)

---

## Module-Based Structure

### Why Modular Architecture

Modularity enables:
- **Independent learning units** - Each module is self-contained
- **Reusable components** - Templates and patterns can be shared
- **Clear prerequisite mapping** - Dependencies are explicit
- **Easy maintenance** - Update one module without breaking others
- **Parallel development** - Multiple content creators can work simultaneously

### Directory Structure

```
learning_system/
├── modules/
│   ├── module_00/          # Foundation module (no prerequisites)
│   │   ├── __init__.py     # Exports MODULE dict
│   │   ├── metadata.py     # Learning objectives, prerequisites
│   │   ├── content.md      # Instructional content
│   │   ├── code.py         # Working example code
│   │   └── exercises/      # Optional practice problems
│   │       ├── exercise_1.py
│   │       └── exercise_2.py
│   ├── module_01/
│   ├── module_02/
│   └── ...
├── loader.py               # Dynamic module discovery
├── progress_tracker.py     # Learner state management
└── validators.py           # Prerequisite enforcement
```

### File Responsibilities

**`__init__.py`** - Package initialization and MODULE export:
```python
"""Module 0: Environment Setup"""
from .metadata import METADATA

# Export the complete module dict for loader
MODULE = {
    **METADATA,
    'package_path': __name__,
}

__all__ = ['MODULE']
```

**`metadata.py`** - Module metadata and learning objectives:
```python
from typing import Any

METADATA: dict[str, Any] = {
    'id': 0,
    'title': 'Module 0: Environment Setup',
    'description': 'Set up your Python environment with virtual environments and dependencies.',
    'bloom_level': 'Remember',
    'scaffolding_level': 'HIGH',
    'concepts': ['virtual environments', 'pip', 'dependencies', 'Python setup'],
    'prerequisites': [],  # Empty list for foundation modules
    'estimated_time_minutes': 15,
    'difficulty': 'BEGINNER',
    'workspace_path': 'workspace/module_0/setup.sh',
}
```

**`content.md`** - Instructional content in Markdown format (500-2000 words optimal)

**`code.py`** - Executable working code demonstrating concepts (see [Working Code Patterns](#working-code-patterns))

**`exercises/`** - Optional practice problems for retrieval practice

### Key Principles

1. **Self-Contained But Connected**
   - Each module can be understood independently
   - Dependencies are declared explicitly in prerequisites
   - No hidden coupling between modules

2. **Explicit Over Implicit**
   - All learning objectives stated in metadata
   - Prerequisites declared, not assumed
   - Scaffolding level clearly marked

3. **Validation at Every Level**
   - File structure validated automatically
   - Metadata schema enforced
   - Prerequisites checked before access
   - Code must be syntactically valid

---

## Metadata-Driven Design

### Why Metadata Matters

Explicit metadata makes learning systems:
- **Transparent** - Learners know exactly what they'll learn
- **Enforceable** - System can validate readiness before module access
- **Measurable** - Analytics can identify common sticking points
- **Maintainable** - Content creators have clear guidelines

### Complete Metadata Schema

```python
from typing import Any

METADATA: dict[str, Any] = {
    # === Required Fields ===
    'id': int,                          # Unique identifier (0, 1, 2, ...)
    'title': str,                       # Human-readable name
    'description': str,                 # Brief summary (1-2 sentences)
    'bloom_level': str,                 # Cognitive complexity level
    'scaffolding_level': str,           # Support level provided
    'concepts': list[str],              # What this module teaches
    'prerequisites': list[int],         # Required prior modules ([] if none)

    # === Optional Fields ===
    'estimated_time_minutes': int,      # Expected completion time
    'difficulty': str,                  # BEGINNER/INTERMEDIATE/ADVANCED
    'workspace_path': str,              # Path to executable code/exercises
    'version': str,                     # Content version for tracking changes
    'changelog': list[dict],            # Version history
}
```

### Field Constraints

**`bloom_level`** - Must be one of Bloom's taxonomy levels:
- `Remember` - Recall facts and basic concepts
- `Understand` - Explain ideas or concepts
- `Apply` - Use information in new situations
- `Analyze` - Draw connections among ideas
- `Evaluate` - Justify a decision or course of action
- `Create` - Produce new or original work

**`scaffolding_level`** - Must be one of three levels:
- `HIGH` - Step-by-step instructions, complete examples, minimal cognitive load
- `MEDIUM` - Hints and partial guidance, learner fills in gaps
- `LOW` - Minimal guidance, learner must apply prior knowledge independently

**`prerequisites`** - List of module IDs that must be completed first:
```python
# Module 0: Foundation (no prerequisites)
'prerequisites': []

# Module 5: Requires modules 0, 1, 2, 4 (but not 3)
'prerequisites': [0, 1, 2, 4]

# Module 10: Requires modules 0, 7, 8, 9
'prerequisites': [0, 7, 8, 9]
```

### Metadata Validation

```python
from typing import Any

BLOOM_LEVELS = {'Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create'}
SCAFFOLDING_LEVELS = {'HIGH', 'MEDIUM', 'LOW'}
DIFFICULTY_LEVELS = {'BEGINNER', 'INTERMEDIATE', 'ADVANCED'}

def validate_metadata(metadata: dict[str, Any]) -> list[str]:
    """
    Validate module metadata against schema.

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Required fields
    required_fields = {
        'id', 'title', 'description', 'bloom_level',
        'scaffolding_level', 'concepts', 'prerequisites'
    }

    for field in required_fields:
        if field not in metadata:
            errors.append(f"Missing required field: {field}")

    # Type validation
    if not isinstance(metadata.get('id'), int):
        errors.append("'id' must be an integer")

    if not isinstance(metadata.get('prerequisites'), list):
        errors.append("'prerequisites' must be a list")
    elif not all(isinstance(p, int) for p in metadata['prerequisites']):
        errors.append("All prerequisites must be integers")

    if not isinstance(metadata.get('concepts'), list):
        errors.append("'concepts' must be a list")
    elif not all(isinstance(c, str) for c in metadata['concepts']):
        errors.append("All concepts must be strings")

    # Enum validation
    if metadata.get('bloom_level') not in BLOOM_LEVELS:
        errors.append(f"bloom_level must be one of {BLOOM_LEVELS}")

    if metadata.get('scaffolding_level') not in SCAFFOLDING_LEVELS:
        errors.append(f"scaffolding_level must be one of {SCAFFOLDING_LEVELS}")

    if 'difficulty' in metadata and metadata['difficulty'] not in DIFFICULTY_LEVELS:
        errors.append(f"difficulty must be one of {DIFFICULTY_LEVELS}")

    # Business rules
    if metadata.get('concepts') == []:
        errors.append("'concepts' cannot be empty (what does this module teach?)")

    # Module cannot be its own prerequisite
    if metadata.get('id') in metadata.get('prerequisites', []):
        errors.append(f"Module {metadata['id']} cannot be its own prerequisite")

    return errors
```

---

## Progressive Complexity Ladder

### The Ladder Principle

Progressive complexity follows two dimensions simultaneously:
1. **Cognitive Load** (Bloom's Taxonomy) - Remember → Create
2. **Support Level** (Scaffolding) - HIGH → LOW

**Golden Rule:** Never increase cognitive load AND decrease scaffolding in the same step.

### Example Progression

```python
# Module 0: Foundation
{
    'id': 0,
    'bloom_level': 'Remember',
    'scaffolding_level': 'HIGH',
    'prerequisites': [],
}

# Module 1: Still foundational
{
    'id': 1,
    'bloom_level': 'Remember',
    'scaffolding_level': 'HIGH',
    'prerequisites': [0],
}

# Module 2: Same Bloom, maintain scaffolding
{
    'id': 2,
    'bloom_level': 'Remember',
    'scaffolding_level': 'HIGH',
    'prerequisites': [0, 1],
}

# Module 3: Increase cognitive load, maintain scaffolding
{
    'id': 3,
    'bloom_level': 'Understand',
    'scaffolding_level': 'HIGH',  # Still HIGH when introducing new Bloom level
    'prerequisites': [0, 1, 2],
}

# Module 4: Same Bloom, begin reducing scaffolding
{
    'id': 4,
    'bloom_level': 'Understand',
    'scaffolding_level': 'MEDIUM',  # Reduce scaffolding only after Bloom is stable
    'prerequisites': [0, 1, 2, 3],
}

# Module 5: Maintain both
{
    'id': 5,
    'bloom_level': 'Understand',
    'scaffolding_level': 'MEDIUM',
    'prerequisites': [0, 1, 2, 3, 4],
}

# Module 6: Increase cognitive load, increase scaffolding
{
    'id': 6,
    'bloom_level': 'Apply',
    'scaffolding_level': 'HIGH',  # Increase support when advancing Bloom
    'prerequisites': [0, 1, 2, 3, 4, 5],
}

# Module 7: Same Bloom, reduce scaffolding
{
    'id': 7,
    'bloom_level': 'Apply',
    'scaffolding_level': 'MEDIUM',
    'prerequisites': [0, 1, 2, 3, 4, 5, 6],
}

# Module 8: Same Bloom, further reduce scaffolding
{
    'id': 8,
    'bloom_level': 'Apply',
    'scaffolding_level': 'LOW',
    'prerequisites': [0, 1, 2, 3, 4, 5, 6, 7],
}

# Module 9: Increase cognitive load, increase scaffolding
{
    'id': 9,
    'bloom_level': 'Analyze',
    'scaffolding_level': 'MEDIUM',  # Not HIGH because learner is experienced
    'prerequisites': [0, 6, 7, 8],  # Can skip some if concepts are independent
}

# Module 10: Advanced module with minimal support
{
    'id': 10,
    'bloom_level': 'Create',
    'scaffolding_level': 'LOW',
    'prerequisites': [0, 6, 7, 8, 9],
}
```

### Progression Rules

1. **2-3 Modules Per Bloom Level**
   - Allow mastery before advancing
   - Align with spaced repetition principle
   - Build confidence through repeated success

2. **Gradual Scaffolding Reduction**
   - HIGH → MEDIUM → LOW (never skip levels)
   - Reduce only after Bloom level is stable
   - Can increase scaffolding when advancing Bloom

3. **Non-Linear Prerequisites**
   - Prerequisites form a DAG, not a chain
   - Later modules can skip intermediate modules if concepts are independent
   - Foundation module (id=0) typically required by all

4. **Validation Rules**
```python
def validate_progression_rules(modules: dict[int, dict]) -> list[str]:
    """Validate progressive complexity ladder rules."""
    errors = []

    bloom_order = ['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create']
    scaffolding_value = {'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}

    for module_id, module in modules.items():
        # Check against prerequisites
        for prereq_id in module['prerequisites']:
            if prereq_id not in modules:
                continue

            prereq = modules[prereq_id]

            # Get numeric values for comparison
            curr_bloom_idx = bloom_order.index(module['bloom_level'])
            prereq_bloom_idx = bloom_order.index(prereq['bloom_level'])
            curr_scaffolding = scaffolding_value[module['scaffolding_level']]
            prereq_scaffolding = scaffolding_value[prereq['scaffolding_level']]

            # Rule: If Bloom increases, scaffolding shouldn't decrease
            if curr_bloom_idx > prereq_bloom_idx and curr_scaffolding < prereq_scaffolding:
                errors.append(
                    f"Module {module_id}: Cannot increase Bloom level "
                    f"({prereq['bloom_level']} -> {module['bloom_level']}) "
                    f"AND decrease scaffolding "
                    f"({prereq['scaffolding_level']} -> {module['scaffolding_level']})"
                )

    return errors
```

---

## Dynamic Module Loading

### Loader Implementation

Production-grade module loader with caching and validation:

```python
"""Dynamic module loader for learning modules."""
import importlib
from pathlib import Path
from typing import Any

_MODULES_CACHE: dict[int, dict[str, Any]] | None = None


def discover_modules() -> dict[int, dict[str, Any]]:
    """
    Discover and load all modules from the modules/ directory.

    Returns:
        Dictionary mapping module_id -> module_dict

    Raises:
        ValueError: If module structure is invalid or duplicate IDs found
        FileNotFoundError: If modules directory or required files are missing
        ImportError: If module package cannot be imported
        AttributeError: If module doesn't export MODULE dict
    """
    modules_dir = Path(__file__).parent / "modules"

    if not modules_dir.exists():
        raise FileNotFoundError(f"Modules directory not found: {modules_dir}")

    modules: dict[int, dict[str, Any]] = {}

    # Find all module_XX directories
    module_dirs = sorted(modules_dir.glob("module_*"))

    if not module_dirs:
        raise ValueError(f"No modules found in {modules_dir}")

    for module_dir in module_dirs:
        if not module_dir.is_dir():
            continue

        # Validate structure
        _validate_module_structure(module_dir)

        # Import the module package
        module_name = module_dir.name
        package_path = f"app.learning.modules.{module_name}"

        try:
            module_pkg = importlib.import_module(package_path)
        except ImportError as e:
            raise ImportError(f"Failed to import {package_path}: {e}")

        # Get MODULE dict from __init__.py
        if not hasattr(module_pkg, "MODULE"):
            raise AttributeError(
                f"{package_path} must export MODULE dict in __all__"
            )

        module_data = module_pkg.MODULE
        module_id = module_data["id"]

        # Validate no duplicate IDs
        if module_id in modules:
            raise ValueError(
                f"Duplicate module ID {module_id} found in {module_dir.name}"
            )

        modules[module_id] = module_data

    return modules


def _validate_module_structure(module_dir: Path) -> None:
    """
    Validate that module directory has required files.

    Args:
        module_dir: Path to module directory

    Raises:
        FileNotFoundError: If required files are missing
    """
    required_files = ["__init__.py", "metadata.py", "content.md", "code.py"]

    missing_files = []
    for filename in required_files:
        file_path = module_dir / filename
        if not file_path.exists():
            missing_files.append(filename)

    if missing_files:
        raise FileNotFoundError(
            f"Required files missing in {module_dir.name}: {', '.join(missing_files)}\n"
            f"Every module must have: {', '.join(required_files)}"
        )


def load_module_content(content_path: Path) -> str:
    """
    Load markdown content from file.

    Args:
        content_path: Path to content.md file

    Returns:
        Markdown content as string

    Raises:
        FileNotFoundError: If content file doesn't exist
    """
    if not content_path.exists():
        raise FileNotFoundError(f"Content file not found: {content_path}")

    return content_path.read_text(encoding="utf-8")


def load_module_code(code_path: Path) -> str:
    """
    Load Python code from file.

    Args:
        code_path: Path to code.py file

    Returns:
        Python code as string

    Raises:
        FileNotFoundError: If code file doesn't exist
    """
    if not code_path.exists():
        raise FileNotFoundError(f"Code file not found: {code_path}")

    return code_path.read_text(encoding="utf-8")


def get_all_modules_dict() -> dict[int, dict[str, Any]]:
    """
    Get all modules (cached after first load).

    Returns:
        Dictionary mapping module_id -> module_dict

    Raises:
        Various exceptions from discover_modules() on first call
    """
    global _MODULES_CACHE

    if _MODULES_CACHE is None:
        _MODULES_CACHE = discover_modules()

    return _MODULES_CACHE


def clear_cache() -> None:
    """
    Clear the module cache. Useful for testing or hot-reloading.
    """
    global _MODULES_CACHE
    _MODULES_CACHE = None
```

### Usage Example

```python
from learning.loader import get_all_modules_dict

# Load all modules (cached)
modules = get_all_modules_dict()

# Access specific module
module_5 = modules[5]
print(module_5['title'])
print(module_5['prerequisites'])

# Get modules by Bloom level
analyze_modules = [
    m for m in modules.values()
    if m['bloom_level'] == 'Analyze'
]

# Get foundation modules (no prerequisites)
foundation_modules = [
    m for m in modules.values()
    if len(m['prerequisites']) == 0
]
```

---

## Prerequisite Graph Validation

### Why Graph Validation Matters

Prerequisite relationships form a Directed Acyclic Graph (DAG). Invalid graphs cause:
- **Circular dependencies** - Impossible to determine starting point
- **Orphaned modules** - Unreachable modules waste content creation effort
- **Broken learning paths** - Learners get stuck without clear progression

### DAG Validation Implementation

```python
from typing import Any

def validate_prerequisite_graph(modules: dict[int, dict[str, Any]]) -> None:
    """
    Ensure prerequisite graph is valid DAG.

    Raises:
        ValueError: If cycles or orphaned modules detected
    """
    # Build adjacency list
    graph = {mid: set(m['prerequisites']) for mid, m in modules.items()}

    # === Detect Cycles (DFS with recursion stack) ===
    def has_cycle(node: int, visited: set[int], rec_stack: set[int]) -> bool:
        """
        Detect cycles using depth-first search with recursion stack.

        Args:
            node: Current module ID
            visited: Set of all visited nodes
            rec_stack: Set of nodes in current recursion path

        Returns:
            True if cycle detected, False otherwise
        """
        visited.add(node)
        rec_stack.add(node)

        # Check all prerequisite neighbors
        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                # Recursively check unvisited neighbor
                if has_cycle(neighbor, visited, rec_stack):
                    return True
            elif neighbor in rec_stack:
                # Found back edge = cycle detected
                return True

        # Remove from recursion stack when backtracking
        rec_stack.remove(node)
        return False

    visited = set()
    for module_id in graph:
        if module_id not in visited:
            if has_cycle(module_id, visited, set()):
                raise ValueError(
                    f"Cycle detected in prerequisites involving module {module_id}"
                )

    # === Detect Unreachable Modules (Orphans) ===
    # Start from foundation modules (no prerequisites)
    foundation_modules = {mid for mid, prereqs in graph.items() if not prereqs}

    if not foundation_modules:
        raise ValueError("No foundation modules found (modules with no prerequisites)")

    # Iteratively expand reachable set
    reachable = foundation_modules.copy()
    changed = True

    while changed:
        changed = False
        for mid, prereqs in graph.items():
            if mid not in reachable and prereqs.issubset(reachable):
                # All prerequisites are reachable, so this module is too
                reachable.add(mid)
                changed = True

    # Find orphaned modules
    orphaned = set(graph.keys()) - reachable
    if orphaned:
        raise ValueError(
            f"Unreachable modules (check prerequisites): {sorted(orphaned)}\n"
            f"These modules cannot be reached from foundation modules: {sorted(foundation_modules)}"
        )


def find_learning_paths(
    modules: dict[int, dict[str, Any]],
    start_id: int,
    goal_id: int
) -> list[list[int]]:
    """
    Find all valid learning paths from start to goal module.

    Args:
        modules: Module dictionary
        start_id: Starting module ID
        goal_id: Goal module ID

    Returns:
        List of paths, where each path is a list of module IDs
    """
    graph = {mid: set(m['prerequisites']) for mid, m in modules.items()}

    def dfs_paths(current: int, goal: int, path: list[int]) -> list[list[int]]:
        """Find all paths using DFS."""
        if current == goal:
            return [path]

        paths = []
        # Find modules that have current as prerequisite
        for mid, prereqs in graph.items():
            if current in prereqs and mid not in path:
                paths.extend(dfs_paths(mid, goal, path + [mid]))

        return paths

    return dfs_paths(start_id, goal_id, [start_id])


def topological_sort(modules: dict[int, dict[str, Any]]) -> list[int]:
    """
    Return modules in topological order (prerequisites before dependents).

    Args:
        modules: Module dictionary

    Returns:
        List of module IDs in valid learning order

    Raises:
        ValueError: If graph has cycles
    """
    graph = {mid: set(m['prerequisites']) for mid, m in modules.items()}
    in_degree = {mid: len(prereqs) for mid, prereqs in graph.items()}

    # Start with modules that have no prerequisites
    queue = [mid for mid, degree in in_degree.items() if degree == 0]
    result = []

    while queue:
        # Process node with no remaining prerequisites
        current = queue.pop(0)
        result.append(current)

        # Reduce in-degree for dependent modules
        for mid, prereqs in graph.items():
            if current in prereqs:
                in_degree[mid] -= 1
                if in_degree[mid] == 0:
                    queue.append(mid)

    if len(result) != len(modules):
        raise ValueError("Cycle detected in prerequisite graph")

    return result
```

### Visualization

```python
def generate_graph_visualization(modules: dict[int, dict[str, Any]], output_path: str) -> None:
    """
    Generate prerequisite graph visualization using Graphviz.

    Args:
        modules: Module dictionary
        output_path: Path to save PNG file

    Requires:
        pip install graphviz
    """
    try:
        from graphviz import Digraph
    except ImportError:
        raise ImportError("Install graphviz: pip install graphviz")

    dot = Digraph(comment='Module Prerequisites')
    dot.attr(rankdir='TB')  # Top to bottom layout

    # Color by scaffolding level
    colors = {
        'HIGH': 'lightgreen',
        'MEDIUM': 'lightyellow',
        'LOW': 'lightcoral',
    }

    # Add nodes
    for module_id, module in modules.items():
        label = f"M{module_id}\n{module['bloom_level']}"
        color = colors.get(module['scaffolding_level'], 'white')
        dot.node(str(module_id), label, style='filled', fillcolor=color)

    # Add edges (prerequisites)
    for module_id, module in modules.items():
        for prereq_id in module['prerequisites']:
            dot.edge(str(prereq_id), str(module_id))

    # Render
    dot.render(output_path, format='png', cleanup=True)
    print(f"Graph saved to {output_path}.png")
```

---

## Progress Tracking

### Learner Progress Data Model

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass
class LearnerProgress:
    """Track learner's journey through modules."""
    learner_id: str
    completed_modules: set[int] = field(default_factory=set)
    current_module: int | None = None
    module_attempts: dict[int, int] = field(default_factory=dict)  # module_id -> attempt count
    exercise_scores: dict[str, float] = field(default_factory=dict)  # exercise_id -> score
    time_spent_minutes: dict[int, int] = field(default_factory=dict)  # module_id -> time
    last_active: datetime = field(default_factory=datetime.now)

    def can_access(self, module_id: int, modules: dict[int, dict[str, Any]]) -> bool:
        """
        Check if learner has completed all prerequisites for module.

        Args:
            module_id: Module to check access for
            modules: All modules dict

        Returns:
            True if all prerequisites completed, False otherwise
        """
        if module_id not in modules:
            return False

        prereqs = modules[module_id]['prerequisites']
        return all(p in self.completed_modules for p in prereqs)

    def get_available_modules(self, modules: dict[int, dict[str, Any]]) -> list[int]:
        """
        Return list of modules learner can currently access.

        Returns modules that:
        1. Have all prerequisites completed
        2. Are not yet completed
        """
        return [
            mid for mid, meta in modules.items()
            if mid not in self.completed_modules
            and self.can_access(mid, modules)
        ]

    def complete_module(self, module_id: int, time_minutes: int) -> None:
        """
        Mark module as completed and record time spent.

        Args:
            module_id: Module that was completed
            time_minutes: Time spent on module
        """
        self.completed_modules.add(module_id)
        self.time_spent_minutes[module_id] = time_minutes
        self.last_active = datetime.now()

    def record_attempt(self, module_id: int) -> None:
        """Increment attempt counter for module."""
        self.module_attempts[module_id] = self.module_attempts.get(module_id, 0) + 1

    def get_completion_rate(self, total_modules: int) -> float:
        """Calculate overall completion percentage."""
        return len(self.completed_modules) / total_modules if total_modules > 0 else 0.0

    def get_next_recommended_module(
        self,
        modules: dict[int, dict[str, Any]]
    ) -> int | None:
        """
        Recommend next module based on learning path.

        Strategy:
        1. Prefer modules with fewest prerequisites (foundational first)
        2. Break ties by module ID (sequential order)
        """
        available = self.get_available_modules(modules)

        if not available:
            return None

        # Sort by number of prerequisites, then by ID
        return min(
            available,
            key=lambda mid: (len(modules[mid]['prerequisites']), mid)
        )
```

### Progress Persistence

```python
import json
from pathlib import Path

def save_progress(progress: LearnerProgress, file_path: Path) -> None:
    """
    Save learner progress to JSON file.

    Args:
        progress: LearnerProgress instance
        file_path: Path to save JSON file
    """
    data = {
        'learner_id': progress.learner_id,
        'completed_modules': list(progress.completed_modules),
        'current_module': progress.current_module,
        'module_attempts': progress.module_attempts,
        'exercise_scores': progress.exercise_scores,
        'time_spent_minutes': progress.time_spent_minutes,
        'last_active': progress.last_active.isoformat(),
    }

    file_path.write_text(json.dumps(data, indent=2))


def load_progress(file_path: Path) -> LearnerProgress:
    """
    Load learner progress from JSON file.

    Args:
        file_path: Path to JSON file

    Returns:
        LearnerProgress instance

    Raises:
        FileNotFoundError: If file doesn't exist
    """
    data = json.loads(file_path.read_text())

    return LearnerProgress(
        learner_id=data['learner_id'],
        completed_modules=set(data['completed_modules']),
        current_module=data['current_module'],
        module_attempts=data['module_attempts'],
        exercise_scores=data['exercise_scores'],
        time_spent_minutes=data['time_spent_minutes'],
        last_active=datetime.fromisoformat(data['last_active']),
    )
```

---

## Fail-Fast Validation

### Principle

If prerequisites aren't met, fail loudly. No silent degradation, no warning messages, no "recommended" prerequisites.

### Implementation

```python
class PrerequisiteError(Exception):
    """Raised when learner attempts to access module without completing prerequisites."""
    pass


def validate_prerequisites(
    module_id: int,
    completed_modules: set[int],
    modules: dict[int, dict[str, Any]]
) -> None:
    """
    Validate learner has completed all prerequisites.

    Args:
        module_id: Module to access
        completed_modules: Set of module IDs learner has completed
        modules: All modules dict

    Raises:
        PrerequisiteError: If missing required modules
        KeyError: If module_id doesn't exist
    """
    if module_id not in modules:
        raise KeyError(f"Module {module_id} does not exist")

    module = modules[module_id]
    missing = set(module['prerequisites']) - completed_modules

    if missing:
        # Provide helpful error message
        missing_titles = [
            f"{mid}: {modules[mid]['title']}"
            for mid in sorted(missing)
            if mid in modules
        ]

        raise PrerequisiteError(
            f"Cannot access Module {module_id} ({module['title']}).\n"
            f"Complete these modules first:\n" +
            "\n".join(f"  - {title}" for title in missing_titles)
        )


# Example usage
try:
    validate_prerequisites(5, completed_modules={0, 1, 2}, modules=all_modules)
except PrerequisiteError as e:
    print(f"Access denied: {e}")
    # Show learner available modules instead
    available = get_available_modules(completed_modules, all_modules)
    print(f"Available modules: {available}")
```

---

## Working Code Patterns

### Code.py Template

Every `code.py` follows this structure:

```python
# === Module X: [Title] ===

# === Step 1: Imports ===
# Keep imports minimal and explicit
from library import SpecificClass, specific_function

# === Step 2: Setup/Configuration ===
# Create instances or configure settings
instance = SpecificClass(
    param1="value1",
    param2="value2"
)

# === Step 3: Execution ===
# Perform the main operation
result = instance.method()

# === Step 4: Examination ===
# Examine outputs to verify behavior
print(f"Result: {result}")
print(f"Type: {type(result).__name__}")

# === Step 5: Cleanup (if needed) ===
# Close connections, cleanup resources
instance.close()
```

### Scaffolding-Specific Patterns

**HIGH Scaffolding** - Complete step-by-step with explanations:
```python
# Module 1: Making Your First API Call

# Step 1: Import the HTTP client
# We use 'requests' library for simple HTTP operations
import requests

# Step 2: Define the API endpoint
# This is a free API that returns random user data
api_url = "https://api.example.com/users/1"

# Step 3: Make a GET request
# The .get() method fetches data from the URL
response = requests.get(api_url)

# Step 4: Examine the response
# Status code 200 means success
print(f"Status Code: {response.status_code}")

# Step 5: Parse the JSON response
# The .json() method converts response to Python dict
data = response.json()
print(f"User Name: {data['name']}")
print(f"User Email: {data['email']}")
```

**MEDIUM Scaffolding** - Hints and partial guidance:
```python
# Module 5: Handling API Errors

import requests

# Hint: Use try/except to handle potential errors
# Hint: requests.get() can raise exceptions

api_url = "https://api.example.com/users/999"

# TODO: Wrap the request in try/except
# TODO: Handle requests.exceptions.RequestException
# TODO: Check for non-200 status codes

response = requests.get(api_url)
response.raise_for_status()  # Raises exception for 4xx/5xx

data = response.json()
print(data)
```

**LOW Scaffolding** - Minimal guidance:
```python
# Module 10: Build a Rate-Limited API Client

# Build a client that:
# 1. Handles authentication via API key
# 2. Implements rate limiting (max 10 requests/minute)
# 3. Retries failed requests with exponential backoff
# 4. Logs all requests and responses

# Apply concepts from Modules 1, 5, 7, and 8
```

---

## Summary

These architecture patterns provide the foundation for building robust progressive learning systems:

1. **Module-Based Structure** - Self-contained, validated, easily extensible
2. **Metadata-Driven** - Explicit objectives, enforceable prerequisites
3. **Progressive Complexity** - Controlled increase in cognitive load and reduction in scaffolding
4. **Dynamic Loading** - Automatic module discovery with caching
5. **Graph Validation** - DAG enforcement prevents impossible learning paths
6. **Progress Tracking** - Rich learner state with recommendation logic
7. **Fail-Fast** - Prerequisites enforced strictly, errors surfaced immediately
8. **Working Code** - Every module includes executable examples

Use these patterns as templates when implementing learning systems in any domain.
