# Implementation Guide for Progressive Learning Systems

This reference provides the complete end-to-end implementation workflow for building progressive learning systems. Follow these steps to create effective, science-backed learning experiences.

---

## Table of Contents

1. [Implementation Workflow](#implementation-workflow)
2. [Module Development Process](#module-development-process)
3. [Validation Systems](#validation-systems)
4. [Metrics Tracking and Analysis](#metrics-tracking-and-analysis)
5. [A/B Testing and Iteration](#ab-testing-and-iteration)
6. [Deployment and Maintenance](#deployment-and-maintenance)

---

## Implementation Workflow

### Phase 1: Define Learning Objectives

**Start with outcomes, not content.** Ask: "What should learners be able to DO after completing this course?"

#### Step 1.1: Identify Terminal Objectives

```python
# Example: Python Programming Course

terminal_objectives = {
    'primary': [
        "Build a REST API with authentication and database integration",
        "Deploy a web application to a production environment",
        "Debug and fix errors in existing Python applications",
    ],
    'secondary': [
        "Read and understand Python codebases written by others",
        "Write unit tests for Python functions and classes",
        "Use version control (Git) for collaborative development",
    ]
}
```

#### Step 1.2: Decompose into Module-Level Objectives

Work backward from terminal objectives to identify required modules:

```python
def decompose_objectives(terminal_objective: str) -> list[dict]:
    """
    Break down terminal objective into module-level objectives.

    Returns:
        List of module objectives with estimated Bloom levels
    """
    # Example for "Build a REST API with authentication"

    modules = [
        {
            'objective': 'Make HTTP requests to existing APIs',
            'bloom_level': 'Remember',
            'scaffolding': 'HIGH',
            'concepts': ['HTTP methods', 'requests library', 'JSON'],
        },
        {
            'objective': 'Parse and validate JSON data',
            'bloom_level': 'Understand',
            'scaffolding': 'HIGH',
            'concepts': ['JSON schema', 'data validation', 'error handling'],
        },
        {
            'objective': 'Create basic Flask routes',
            'bloom_level': 'Apply',
            'scaffolding': 'MEDIUM',
            'concepts': ['Flask app', 'routing', 'HTTP methods'],
        },
        {
            'objective': 'Implement token-based authentication',
            'bloom_level': 'Apply',
            'scaffolding': 'MEDIUM',
            'concepts': ['JWT tokens', 'authentication middleware', 'headers'],
        },
        {
            'objective': 'Design and build a complete REST API',
            'bloom_level': 'Create',
            'scaffolding': 'LOW',
            'concepts': ['API design', 'CRUD operations', 'authentication', 'error handling'],
        }
    ]

    return modules
```

#### Step 1.3: Map Prerequisite Dependencies

```python
def build_prerequisite_map(modules: list[dict]) -> dict[int, list[int]]:
    """
    Determine which modules depend on which.

    Rules:
    - Foundation modules (Bloom: Remember) have no prerequisites
    - Each new Bloom level requires mastery of previous level
    - Concepts build on each other logically
    """
    # Manual mapping based on concept dependencies
    prerequisite_map = {
        0: [],           # HTTP requests (foundation)
        1: [0],          # JSON parsing (needs HTTP knowledge)
        2: [0, 1],       # Flask routes (needs HTTP + JSON)
        3: [0, 1, 2],    # Authentication (needs all previous)
        4: [0, 1, 2, 3], # Complete API (integrates all)
    }

    return prerequisite_map
```

---

### Phase 2: Design Module Structure

#### Step 2.1: Create Module Template

For each module objective from Phase 1, create a module directory:

```bash
modules/
├── module_00/
│   ├── __init__.py
│   ├── metadata.py
│   ├── content.md
│   ├── code.py
│   └── exercises/
│       └── exercise_01.py
```

#### Step 2.2: Define Metadata

```python
# modules/module_00/metadata.py

from typing import Any

METADATA: dict[str, Any] = {
    # === Identity ===
    'id': 0,
    'title': 'Module 0: Making HTTP Requests',
    'description': 'Learn to fetch data from web APIs using the requests library.',

    # === Learning Design ===
    'bloom_level': 'Remember',
    'scaffolding_level': 'HIGH',
    'concepts': ['HTTP GET', 'requests library', 'JSON responses'],
    'prerequisites': [],

    # === Logistics ===
    'estimated_time_minutes': 15,
    'difficulty': 'BEGINNER',
    'workspace_path': 'workspace/module_0/example.py',

    # === Version Control ===
    'version': '1.0',
    'changelog': [
        {'version': '1.0', 'date': '2026-02-10', 'changes': 'Initial version'},
    ],
}
```

#### Step 2.3: Write Content

Use the [content.md template](content-design.md#contentmd-template) from content-design reference.

**Key Principles:**
1. Start with learning objectives (what learner will be able to DO)
2. Connect to prerequisites (how prior knowledge enables this)
3. Introduce 2-4 concepts maximum
4. Provide concrete examples before abstract explanations
5. Include working code walkthrough
6. End with practice challenge

#### Step 2.4: Create Working Code

Use the [code.py patterns](content-design.md#codepy-patterns-by-scaffolding-level) from content-design reference.

**Template Selection:**
- **Modules 0-3:** HIGH scaffolding (step-by-step with extensive comments)
- **Modules 4-7:** MEDIUM scaffolding (TODOs with hints)
- **Modules 8+:** LOW scaffolding (requirements only)

---

### Phase 3: Validate Structure

#### Step 3.1: Module-Level Validation

Run validation on each module:

```python
from pathlib import Path

def validate_module(module_dir: Path) -> list[str]:
    """
    Validate module structure and content quality.

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Check 1: Required files exist
    required_files = ['__init__.py', 'metadata.py', 'content.md', 'code.py']
    for filename in required_files:
        if not (module_dir / filename).exists():
            errors.append(f"Missing required file: {filename}")

    if errors:  # Don't continue if files missing
        return errors

    # Check 2: Metadata is valid
    try:
        # Import metadata module dynamically
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "metadata",
            module_dir / "metadata.py"
        )
        metadata_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(metadata_module)
        metadata = metadata_module.METADATA
    except Exception as e:
        errors.append(f"Failed to load metadata: {e}")
        return errors

    # Check 3: Required metadata fields
    required_fields = {
        'id', 'title', 'description', 'bloom_level',
        'scaffolding_level', 'concepts', 'prerequisites'
    }
    for field in required_fields:
        if field not in metadata:
            errors.append(f"Metadata missing required field: {field}")

    # Check 4: Metadata field types
    if not isinstance(metadata.get('id'), int):
        errors.append("Metadata 'id' must be an integer")

    if not isinstance(metadata.get('prerequisites'), list):
        errors.append("Metadata 'prerequisites' must be a list")

    if not isinstance(metadata.get('concepts'), list):
        errors.append("Metadata 'concepts' must be a list")

    # Check 5: Enum values
    valid_bloom = {'Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create'}
    if metadata.get('bloom_level') not in valid_bloom:
        errors.append(f"Invalid bloom_level: {metadata.get('bloom_level')}")

    valid_scaffolding = {'HIGH', 'MEDIUM', 'LOW'}
    if metadata.get('scaffolding_level') not in valid_scaffolding:
        errors.append(f"Invalid scaffolding_level: {metadata.get('scaffolding_level')}")

    # Check 6: Code is syntactically valid
    code_file = module_dir / 'code.py'
    try:
        code = code_file.read_text()
        compile(code, str(code_file), 'exec')
    except SyntaxError as e:
        errors.append(f"Code has syntax error at line {e.lineno}: {e.msg}")
    except Exception as e:
        errors.append(f"Failed to validate code: {e}")

    # Check 7: Content word count
    content_file = module_dir / 'content.md'
    try:
        content = content_file.read_text()
        word_count = len(content.split())

        if word_count < 500:
            errors.append(f"Content too brief ({word_count} words, minimum 500)")
        elif word_count > 2000:
            errors.append(f"Content too long ({word_count} words, maximum 2000)")
    except Exception as e:
        errors.append(f"Failed to read content: {e}")

    # Check 8: Concepts are non-empty
    if metadata.get('concepts') == []:
        errors.append("'concepts' list cannot be empty")

    return errors


# Usage
module_path = Path("modules/module_00")
errors = validate_module(module_path)

if errors:
    print("❌ Validation failed:")
    for error in errors:
        print(f"  - {error}")
else:
    print("✅ Module validation passed")
```

#### Step 3.2: Graph-Level Validation

Validate the entire prerequisite graph:

```python
def validate_prerequisite_graph(modules: dict[int, dict]) -> list[str]:
    """
    Validate prerequisite graph is a valid DAG.

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Build adjacency list
    graph = {mid: set(m['prerequisites']) for mid, m in modules.items()}

    # Check 1: Prerequisites reference existing modules
    for module_id, prereqs in graph.items():
        for prereq_id in prereqs:
            if prereq_id not in modules:
                errors.append(
                    f"Module {module_id} references non-existent prerequisite: {prereq_id}"
                )

    if errors:  # Don't continue if references are broken
        return errors

    # Check 2: No circular dependencies
    def has_cycle(node: int, visited: set[int], rec_stack: set[int]) -> bool:
        """DFS cycle detection."""
        visited.add(node)
        rec_stack.add(node)

        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                if has_cycle(neighbor, visited, rec_stack):
                    return True
            elif neighbor in rec_stack:
                return True

        rec_stack.remove(node)
        return False

    visited = set()
    for module_id in graph:
        if module_id not in visited:
            if has_cycle(module_id, visited, set()):
                errors.append(f"Circular dependency detected involving module {module_id}")

    # Check 3: No orphaned modules
    # Start from foundation modules
    foundation = {mid for mid, prereqs in graph.items() if not prereqs}

    if not foundation:
        errors.append("No foundation modules found (modules with empty prerequisites)")
        return errors

    # Iteratively expand reachable set
    reachable = foundation.copy()
    changed = True

    while changed:
        changed = False
        for mid, prereqs in graph.items():
            if mid not in reachable and prereqs.issubset(reachable):
                reachable.add(mid)
                changed = True

    orphaned = set(graph.keys()) - reachable
    if orphaned:
        errors.append(
            f"Orphaned modules (unreachable from foundation): {sorted(orphaned)}\n"
            f"Foundation modules: {sorted(foundation)}"
        )

    # Check 4: Progressive complexity rules
    bloom_order = ['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create']
    scaffolding_value = {'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}

    for module_id, module in modules.items():
        for prereq_id in module['prerequisites']:
            if prereq_id not in modules:
                continue

            prereq = modules[prereq_id]

            curr_bloom_idx = bloom_order.index(module['bloom_level'])
            prereq_bloom_idx = bloom_order.index(prereq['bloom_level'])
            curr_scaffolding = scaffolding_value[module['scaffolding_level']]
            prereq_scaffolding = scaffolding_value[prereq['scaffolding_level']]

            # Rule: Don't increase Bloom AND decrease scaffolding
            if curr_bloom_idx > prereq_bloom_idx and curr_scaffolding < prereq_scaffolding:
                errors.append(
                    f"Module {module_id}: Cannot increase Bloom "
                    f"({prereq['bloom_level']} -> {module['bloom_level']}) "
                    f"AND decrease scaffolding "
                    f"({prereq['scaffolding_level']} -> {module['scaffolding_level']})"
                )

    return errors


# Usage
from loader import get_all_modules_dict

modules = get_all_modules_dict()
errors = validate_prerequisite_graph(modules)

if errors:
    print("❌ Graph validation failed:")
    for error in errors:
        print(f"  - {error}")
else:
    print("✅ Prerequisite graph is valid")
```

---

## Module Development Process

### Iterative Module Creation

For each module, follow this sequence:

```
1. Define learning objective (what learner can DO)
   ↓
2. Identify prerequisite knowledge needed
   ↓
3. List 2-4 core concepts to teach
   ↓
4. Write working code example
   ↓
5. Write content.md around the code
   ↓
6. Create metadata.py
   ↓
7. Validate module structure
   ↓
8. Test code execution
   ↓
9. Peer review for clarity
   ↓
10. Deploy and gather metrics
```

### Module Creation Checklist

```markdown
## Module N: [Title] - Development Checklist

### Planning
- [ ] Learning objective defined (specific, measurable action verb)
- [ ] Prerequisites identified and documented
- [ ] Core concepts listed (2-4 max)
- [ ] Bloom level determined
- [ ] Scaffolding level chosen (matches learner readiness)

### Content
- [ ] code.py written and tested (executes without errors)
- [ ] code.py follows scaffolding pattern (HIGH/MEDIUM/LOW)
- [ ] content.md written using template
- [ ] content.md word count 500-2000
- [ ] metadata.py created with all required fields
- [ ] __init__.py exports MODULE dict

### Validation
- [ ] Module validation passes (all files present, valid syntax)
- [ ] Code compiles without syntax errors
- [ ] Prerequisites reference existing modules only
- [ ] No circular dependencies introduced

### Quality
- [ ] Peer reviewed for clarity
- [ ] Working code verified by running it
- [ ] Examples are concrete, not abstract
- [ ] Exercises test the learning objective directly

### Integration
- [ ] Prerequisite graph updated
- [ ] Module discoverable by loader
- [ ] Ready for learner testing
```

---

## Metrics Tracking and Analysis

### What to Measure

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class ModuleAnalytics:
    """Analytics for a single module."""
    module_id: int

    # Completion metrics
    started_count: int           # How many learners started this module
    completed_count: int         # How many finished
    completion_rate: float       # completed / started

    # Time metrics
    estimated_time_minutes: int
    actual_time_median: int      # Median time to complete
    actual_time_p90: int         # 90th percentile time

    # Difficulty indicators
    retry_count: int             # How many times learners restarted module
    retry_rate: float            # retries / started

    # Exercise performance
    exercise_attempts: dict[str, int]        # exercise_id -> total attempts
    exercise_success_rate: dict[str, float]  # exercise_id -> success rate

    # Prerequisite violations
    premature_access_attempts: int  # How many tried to skip prerequisites

    def get_red_flags(self) -> list[str]:
        """Identify problems with this module."""
        flags = []

        if self.completion_rate < 0.70:
            flags.append(f"Low completion rate ({self.completion_rate:.1%}) - too difficult?")

        if self.actual_time_median > 2 * self.estimated_time_minutes:
            flags.append(
                f"Time estimate off ({self.actual_time_median}min actual vs "
                f"{self.estimated_time_minutes}min estimated)"
            )

        if self.retry_rate > 0.30:
            flags.append(f"High retry rate ({self.retry_rate:.1%}) - unclear instructions?")

        for ex_id, success_rate in self.exercise_success_rate.items():
            if success_rate < 0.50:
                flags.append(
                    f"Exercise {ex_id} low success rate ({success_rate:.1%}) - "
                    "concept not taught well?"
                )

        if self.premature_access_attempts > 50:
            flags.append(
                f"Many prerequisite skip attempts ({self.premature_access_attempts}) - "
                "make dependencies clearer?"
            )

        return flags


def analyze_module_metrics(
    module_id: int,
    learner_data: list[dict]
) -> ModuleAnalytics:
    """
    Calculate analytics for a module from learner data.

    Args:
        module_id: Module to analyze
        learner_data: List of learner progress dicts

    Returns:
        ModuleAnalytics with calculated metrics
    """
    started = [l for l in learner_data if module_id in l.get('started_modules', [])]
    completed = [l for l in learner_data if module_id in l.get('completed_modules', [])]

    started_count = len(started)
    completed_count = len(completed)
    completion_rate = completed_count / started_count if started_count > 0 else 0.0

    # Time metrics
    completion_times = [
        l['time_spent'][module_id]
        for l in completed
        if module_id in l.get('time_spent', {})
    ]

    actual_time_median = sorted(completion_times)[len(completion_times) // 2] if completion_times else 0
    actual_time_p90 = sorted(completion_times)[int(len(completion_times) * 0.9)] if completion_times else 0

    # Retry metrics
    retry_count = sum(
        l.get('module_attempts', {}).get(module_id, 1) - 1
        for l in learner_data
    )
    retry_rate = retry_count / started_count if started_count > 0 else 0.0

    # Exercise metrics
    exercise_attempts = {}
    exercise_success_rate = {}

    for learner in learner_data:
        for ex_id, attempts in learner.get('exercise_attempts', {}).items():
            if not ex_id.startswith(f'module_{module_id:02d}_'):
                continue

            exercise_attempts[ex_id] = exercise_attempts.get(ex_id, 0) + attempts
            if learner.get('exercise_scores', {}).get(ex_id, 0) > 0.5:
                exercise_success_rate[ex_id] = exercise_success_rate.get(ex_id, 0) + 1

    for ex_id in exercise_attempts:
        if ex_id in exercise_success_rate:
            exercise_success_rate[ex_id] /= exercise_attempts[ex_id]

    # Prerequisite violations
    premature_access = sum(
        1 for l in learner_data
        if module_id in l.get('prerequisite_violations', [])
    )

    return ModuleAnalytics(
        module_id=module_id,
        started_count=started_count,
        completed_count=completed_count,
        completion_rate=completion_rate,
        estimated_time_minutes=0,  # Load from metadata
        actual_time_median=actual_time_median,
        actual_time_p90=actual_time_p90,
        retry_count=retry_count,
        retry_rate=retry_rate,
        exercise_attempts=exercise_attempts,
        exercise_success_rate=exercise_success_rate,
        premature_access_attempts=premature_access,
    )
```

### Interpreting Red Flags

| Metric | Threshold | Interpretation | Action |
|--------|-----------|----------------|--------|
| Completion Rate | < 70% | Module too difficult or prerequisites missing | Review prerequisites, simplify content, increase scaffolding |
| Actual Time | > 2x estimate | Poor scaffolding or scope too large | Split into 2 modules, add more examples, increase scaffolding |
| Retry Rate | > 30% | Instructions unclear or exercises too hard | Rewrite instructions, add examples, reduce exercise difficulty |
| Exercise Success | < 50% | Concept not adequately taught | Add more examples, increase practice, improve explanation |
| Prerequisite Violations | > 50 attempts | Dependencies unclear | Make prerequisites more visible, add roadmap |

---

## A/B Testing and Iteration

### Versioning Strategy

```python
# modules/module_05/metadata.py

METADATA = {
    'id': 5,
    'version': '2.1',
    'changelog': [
        {
            'version': '2.1',
            'date': '2026-02-15',
            'changes': 'Increased scaffolding based on metrics',
            'reason': 'Completion rate was 62%, retry rate 38%'
        },
        {
            'version': '2.0',
            'date': '2026-02-01',
            'changes': 'Restructured from HIGH to MEDIUM scaffolding',
            'reason': 'Users found v1.0 too hand-holdy'
        },
        {
            'version': '1.0',
            'date': '2026-01-15',
            'changes': 'Initial version'
        },
    ],
    # ... rest of metadata
}
```

### A/B Testing Implementation

```python
def get_module_variant(module_id: int, learner_id: str) -> str:
    """
    Assign learner to A/B test variant.

    Uses consistent hashing to ensure same learner always gets same variant.

    Returns:
        'control' or 'variant'
    """
    # Hash learner_id to get consistent assignment
    variant_num = hash(f"{module_id}_{learner_id}") % 100

    # 50/50 split
    return 'variant' if variant_num < 50 else 'control'


def load_module_content(module_id: int, learner_id: str) -> str:
    """
    Load content file based on A/B test variant.

    Directory structure:
    module_05/
        content.md          # Control version
        content_v2.md       # Variant version
    """
    variant = get_module_variant(module_id, learner_id)

    if variant == 'control':
        file_path = f'modules/module_{module_id:02d}/content.md'
    else:
        file_path = f'modules/module_{module_id:02d}/content_v2.md'

    return Path(file_path).read_text()


def compare_variants(module_id: int, learner_data: list[dict]) -> dict:
    """
    Compare performance between control and variant.

    Returns statistical comparison of key metrics.
    """
    control_learners = [
        l for l in learner_data
        if get_module_variant(module_id, l['learner_id']) == 'control'
    ]

    variant_learners = [
        l for l in learner_data
        if get_module_variant(module_id, l['learner_id']) == 'variant'
    ]

    control_metrics = analyze_module_metrics(module_id, control_learners)
    variant_metrics = analyze_module_metrics(module_id, variant_learners)

    return {
        'control': {
            'n': len(control_learners),
            'completion_rate': control_metrics.completion_rate,
            'median_time': control_metrics.actual_time_median,
            'retry_rate': control_metrics.retry_rate,
        },
        'variant': {
            'n': len(variant_learners),
            'completion_rate': variant_metrics.completion_rate,
            'median_time': variant_metrics.actual_time_median,
            'retry_rate': variant_metrics.retry_rate,
        },
        'winner': determine_winner(control_metrics, variant_metrics),
    }


def determine_winner(control: ModuleAnalytics, variant: ModuleAnalytics) -> str:
    """
    Determine which variant performed better.

    Criteria (in order of importance):
    1. Completion rate (higher is better)
    2. Time efficiency (closer to estimate is better)
    3. Retry rate (lower is better)
    """
    # Need statistical significance (at least 30 completions each)
    if control.completed_count < 30 or variant.completed_count < 30:
        return 'insufficient_data'

    # Primary metric: completion rate
    if abs(control.completion_rate - variant.completion_rate) > 0.05:
        return 'variant' if variant.completion_rate > control.completion_rate else 'control'

    # Secondary metric: time accuracy
    control_time_diff = abs(control.actual_time_median - control.estimated_time_minutes)
    variant_time_diff = abs(variant.actual_time_median - variant.estimated_time_minutes)

    if abs(control_time_diff - variant_time_diff) > 5:
        return 'variant' if variant_time_diff < control_time_diff else 'control'

    # Tertiary metric: retry rate
    if abs(control.retry_rate - variant.retry_rate) > 0.05:
        return 'variant' if variant.retry_rate < control.retry_rate else 'control'

    return 'tie'
```

---

## Deployment and Maintenance

### Pre-Deployment Checklist

```markdown
## Pre-Deployment Checklist

### Validation
- [ ] All modules pass validation (structure, syntax, metadata)
- [ ] Prerequisite graph is valid DAG (no cycles, no orphans)
- [ ] All code examples execute without errors
- [ ] Content word counts within 500-2000 range

### Testing
- [ ] Manual testing of complete learning path
- [ ] Code examples tested on fresh environment
- [ ] Prerequisites enforce correctly
- [ ] Module loader discovers all modules

### Quality
- [ ] Peer review completed for all modules
- [ ] Examples are concrete and runnable
- [ ] Learning objectives are clear and measurable
- [ ] Scaffolding matches learner readiness

### Documentation
- [ ] README with setup instructions
- [ ] Module roadmap/graph visualization
- [ ] Troubleshooting guide
- [ ] Contribution guidelines (if open source)

### Infrastructure
- [ ] Analytics tracking implemented
- [ ] Progress persistence working
- [ ] Error logging configured
- [ ] Backup strategy in place
```

### Ongoing Maintenance

**Weekly:**
- Review analytics dashboard for red flags
- Monitor completion rates and time metrics
- Check for new prerequisite violation patterns

**Monthly:**
- Deep dive into low-performing modules
- A/B test results analysis
- Content updates based on learner feedback
- Dependency graph optimization

**Quarterly:**
- Major version updates for underperforming modules
- Curriculum restructuring based on data
- Add new advanced modules if completion rates high
- Retire or merge redundant modules

---

## Summary

Effective implementation follows this cycle:

1. **Define Objectives** - Start with what learners will DO
2. **Design Modules** - Work backward to required knowledge
3. **Validate Structure** - Ensure consistency and quality
4. **Deploy and Measure** - Track real learner performance
5. **Analyze Metrics** - Identify problems and opportunities
6. **Iterate Content** - A/B test improvements
7. **Repeat** - Continuous improvement based on data

Key principle: **Let data guide iteration, not opinions.** Metrics reveal where learners struggle, enabling targeted improvements.
