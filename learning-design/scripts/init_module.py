#!/usr/bin/env python3
"""
Initialize a new learning module with proper structure and templates.

Usage:
    python init_module.py <id> "<title>" --path <output-dir> [--scaffolding HIGH|MEDIUM|LOW]

Example:
    python init_module.py 5 "Module 5: API Authentication" --path ./modules --scaffolding MEDIUM
"""

import argparse
import sys
from pathlib import Path
from typing import Literal

ScaffoldingLevel = Literal['HIGH', 'MEDIUM', 'LOW']


def create_module_directory(module_id: int, output_path: Path) -> Path:
    """
    Create module directory structure.

    Args:
        module_id: Module ID number
        output_path: Base path for modules directory

    Returns:
        Path to created module directory

    Raises:
        FileExistsError: If module directory already exists
    """
    module_dir = output_path / f"module_{module_id:02d}"

    if module_dir.exists():
        raise FileExistsError(f"Module directory already exists: {module_dir}")

    module_dir.mkdir(parents=True, exist_ok=False)
    print(f"✅ Created directory: {module_dir}")

    return module_dir


def generate_metadata_template(module_id: int, title: str, scaffolding: ScaffoldingLevel) -> str:
    """Generate metadata.py template with TODO placeholders."""
    return f'''"""Metadata for {title}"""
from typing import Any

METADATA: dict[str, Any] = {{
    # === Identity ===
    'id': {module_id},
    'title': '{title}',
    'description': 'TODO: Brief 1-2 sentence summary of module objectives',

    # === Learning Design ===
    'bloom_level': 'TODO: Remember|Understand|Apply|Analyze|Evaluate|Create',
    'scaffolding_level': '{scaffolding}',
    'concepts': [
        'TODO: concept_1',
        'TODO: concept_2',
        'TODO: concept_3',
    ],
    'prerequisites': [],  # TODO: Add prerequisite module IDs

    # === Logistics ===
    'estimated_time_minutes': 0,  # TODO: Estimate completion time
    'difficulty': 'TODO: BEGINNER|INTERMEDIATE|ADVANCED',
    'workspace_path': 'workspace/module_{module_id:02d}/example.py',

    # === Version Control ===
    'version': '1.0',
    'changelog': [
        {{'version': '1.0', 'date': 'YYYY-MM-DD', 'changes': 'Initial version'}},
    ],
}}
'''


def generate_init_template(module_id: int) -> str:
    """Generate __init__.py template."""
    return f'''"""Module {module_id} - Learning module package"""
from .metadata import METADATA

# Export the complete module dict for loader
MODULE = {{
    **METADATA,
    'package_path': __name__,
}}

__all__ = ['MODULE']
'''


def generate_content_template_high_scaffolding(module_id: int, title: str) -> str:
    """Generate content.md template for HIGH scaffolding level."""
    return f'''# {title}

## Overview

TODO: Write 2-3 sentences answering:
- What will learner be able to DO after this module?
- Why does this matter? (Real-world application)

**Learning Objectives:**
- TODO: [Verb] [What]
- TODO: [Verb] [What]
- TODO: [Verb] [What]

**Time Estimate:** XX minutes

---

## Prerequisites

**Required Knowledge:**
- Module X: [Concept] - We'll build on this by [extension]
- Module Y: [Concept] - You'll apply this to [new context]

**Why These Prerequisites Matter:**
TODO: Connect the dots - show how prior knowledge enables this module

---

## Core Concepts

### Concept 1: [Name]

TODO: Clear definition in 1-2 sentences

**Example:**
```python
# TODO: Concrete example demonstrating the concept
```

**Why This Matters:**
TODO: Real-world application or importance

**Common Pitfall:**
❌ **Wrong Approach:**
```python
# TODO: Anti-pattern example
```

✅ **Right Approach:**
```python
# TODO: Correct pattern
```

---

### Concept 2: [Name]

TODO: Follow same structure

---

### Concept 3: [Name]

TODO: Maximum 3-4 concepts per module

---

## Hands-On Example

**What We're Building:**
TODO: One sentence describing the goal

See `code.py` for the complete working example.

---

## Try It Yourself

**Challenge:**
TODO: Task that requires applying what was just learned

**Hints:**
1. TODO: First hint - subtle
2. TODO: Second hint - more direct

**Success Criteria:**
- [ ] TODO: Requirement 1
- [ ] TODO: Requirement 2

---

## Summary

**What You Learned:**
- ✅ TODO: Concept 1 in one sentence
- ✅ TODO: Concept 2 in one sentence
- ✅ TODO: Concept 3 in one sentence

---

## What's Next

**Upcoming Modules:**
- **Module [N+1]:** [Title] - You'll use [this module's concept] to [next step]
'''


def generate_content_template_medium_scaffolding(module_id: int, title: str) -> str:
    """Generate content.md template for MEDIUM scaffolding level."""
    return f'''# {title}

## Overview

TODO: What will learner be able to DO after this module?

**Learning Objectives:**
- TODO: Apply [concept from earlier module] to [new context]
- TODO: Combine [X] and [Y] to solve [problem]

**Time Estimate:** XX minutes

---

## Prerequisites Review

Before starting, refresh these concepts:
- **Module X:** [Quick one-sentence reminder]
- **Module Y:** [Quick one-sentence reminder]

---

## Core Concepts

### Concept 1: [Name]

TODO: Definition and explanation

**Your Turn:**
Apply the pattern from Module X to implement [new requirement].

Hints:
- Remember the three-step process from Module X
- Check return types carefully

---

### Concept 2: [Name]

TODO: Definition and explanation

---

## Challenge

TODO: Open-ended problem requiring combination of prior concepts + new learning

**Requirements:**
1. TODO: Functional requirement
2. TODO: Functional requirement

**Hints Available:**
See bottom of this file if stuck.

---

## Summary

**Skills Acquired:**
- TODO: What can learner now DO
- TODO: How does this extend prior knowledge

---

## Hints

<details>
<summary>Click to reveal hints</summary>

**Hint 1:** TODO: Subtle guidance
**Hint 2:** TODO: More direct
**Hint 3:** TODO: Almost gives solution away

</details>
'''


def generate_content_template_low_scaffolding(module_id: int, title: str) -> str:
    """Generate content.md template for LOW scaffolding level."""
    return f'''# {title}

## Project Objectives

TODO: Define what learner will build/solve

**Requirements:**
1. TODO: Functional requirement combining Concept X from Module A
2. TODO: Functional requirement combining Concept Y from Module B
3. TODO: Functional requirement combining Concept Z from Module C
4. TODO: Non-functional requirement (performance/security/reliability)

**Constraints:**
- TODO: Constraint 1
- TODO: Constraint 2

---

## Success Criteria

- [ ] TODO: Measurable outcome 1
- [ ] TODO: Measurable outcome 2
- [ ] TODO: Measurable outcome 3

---

## Design Considerations

TODO: Questions learner should think about before implementing:
- How will you handle [edge case]?
- What data structures make sense for [requirement]?
- How will you ensure [non-functional requirement]?

---

## Resources

**Review These Modules:**
- Module X: [Relevant concept]
- Module Y: [Relevant concept]
- Module Z: [Relevant concept]

**Documentation:**
- TODO: Link to relevant docs

---

## Implementation

No scaffolding provided. Apply what you've learned.

See `code.py` for starter template (minimal scaffolding).
'''


def generate_code_template_high_scaffolding(module_id: int, title: str) -> str:
    """Generate code.py template for HIGH scaffolding level."""
    return f'''"""
{title}

This code demonstrates [X, Y, Z] step-by-step.

Instructions:
1. Read through the code first (don't run yet)
2. Predict what each step will output
3. Run the code and compare with your predictions
4. Experiment with modifications suggested at the end
"""

# ============================================================================
# STEP 1: [Action Verb] - [What]
# ============================================================================
# TODO: Explain WHY this step is necessary
# TODO: Explain WHAT we're doing

# TODO: Add your code here

print("Step 1 Complete: TODO: What was accomplished")
print()

# ============================================================================
# STEP 2: [Action Verb] - [What]
# ============================================================================
# TODO: Explain how this builds on Step 1

# TODO: Add your code here

print("Step 2 Complete: TODO: What was accomplished")
print()

# ============================================================================
# STEP 3: [Action Verb] - [What]
# ============================================================================
# TODO: Explain the final transformation/action

# TODO: Add your code here

print("Step 3 Complete: TODO: What was accomplished")
print()

# ============================================================================
# VERIFICATION
# ============================================================================

print("✅ All steps completed successfully!")
print("   TODO: Key insight from output")

# ============================================================================
# TRY THESE MODIFICATIONS
# ============================================================================
"""
Experiment with these changes to deepen understanding:

1. TODO: Suggested modification 1
2. TODO: Suggested modification 2
3. TODO: Suggested modification 3

What do you notice?
"""
'''


def generate_code_template_medium_scaffolding(module_id: int, title: str) -> str:
    """Generate code.py template for MEDIUM scaffolding level."""
    return f'''"""
{title}

Apply concepts from Module [X] and Module [Y] to solve [problem].

Instructions:
1. Review the TODOs marked in the code
2. Implement each TODO using patterns you've learned
3. Run the code to verify your implementation
"""

# ============================================================================
# SETUP (Provided)
# ============================================================================

# TODO: Add setup code here

print("Setup complete")
print()

# ============================================================================
# TODO 1: Implement the pattern from Module X
# ============================================================================
# Hint: TODO: Add helpful hint
# Hint: TODO: Add helpful hint

# Your code here:
# TODO: Replace this with your implementation

# ============================================================================
# TODO 2: Handle the edge case from Module Y
# ============================================================================
# Hint: TODO: Add helpful hint

# Your code here:
# TODO: Replace this with your implementation

# ============================================================================
# TODO 3: Combine and verify
# ============================================================================

# Your code here:
# TODO: Replace this with your implementation

# ============================================================================
# VERIFICATION (Provided)
# ============================================================================

# TODO: Add assertion checks
print("✅ All TODOs completed!")
'''


def generate_code_template_low_scaffolding(module_id: int, title: str) -> str:
    """Generate code.py template for LOW scaffolding level."""
    return f'''"""
{title}

Build [system/solution] that demonstrates mastery of [topic].

Requirements:
1. TODO: Functional requirement using Concept X from Module A
2. TODO: Functional requirement using Concept Y from Module B
3. TODO: Functional requirement using Concept Z from Module C
4. TODO: Non-functional requirement

Constraints:
- TODO: Constraint 1
- TODO: Constraint 2

Success Criteria:
- [ ] TODO: Measurable outcome 1
- [ ] TODO: Measurable outcome 2
- [ ] TODO: Measurable outcome 3

No scaffolding provided - apply what you've learned.
"""

# Your implementation here
'''


def write_module_files(
    module_dir: Path,
    module_id: int,
    title: str,
    scaffolding: ScaffoldingLevel
) -> None:
    """
    Write all module files with appropriate templates.

    Args:
        module_dir: Path to module directory
        module_id: Module ID number
        title: Module title
        scaffolding: Scaffolding level (HIGH/MEDIUM/LOW)
    """
    # Write metadata.py
    metadata_content = generate_metadata_template(module_id, title, scaffolding)
    (module_dir / "metadata.py").write_text(metadata_content)
    print(f"✅ Created: metadata.py")

    # Write __init__.py
    init_content = generate_init_template(module_id)
    (module_dir / "__init__.py").write_text(init_content)
    print(f"✅ Created: __init__.py")

    # Write content.md (scaffolding-appropriate)
    content_generators = {
        'HIGH': generate_content_template_high_scaffolding,
        'MEDIUM': generate_content_template_medium_scaffolding,
        'LOW': generate_content_template_low_scaffolding,
    }
    content_content = content_generators[scaffolding](module_id, title)
    (module_dir / "content.md").write_text(content_content)
    print(f"✅ Created: content.md ({scaffolding} scaffolding)")

    # Write code.py (scaffolding-appropriate)
    code_generators = {
        'HIGH': generate_code_template_high_scaffolding,
        'MEDIUM': generate_code_template_medium_scaffolding,
        'LOW': generate_code_template_low_scaffolding,
    }
    code_content = code_generators[scaffolding](module_id, title)
    (module_dir / "code.py").write_text(code_content)
    print(f"✅ Created: code.py ({scaffolding} scaffolding)")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Initialize a new learning module with proper structure and templates.'
    )

    parser.add_argument(
        'id',
        type=int,
        help='Module ID number (e.g., 5 for module_05)'
    )

    parser.add_argument(
        'title',
        type=str,
        help='Module title (e.g., "Module 5: API Authentication")'
    )

    parser.add_argument(
        '--path',
        type=str,
        required=True,
        help='Output directory for modules (e.g., ./modules)'
    )

    parser.add_argument(
        '--scaffolding',
        type=str,
        choices=['HIGH', 'MEDIUM', 'LOW'],
        default='HIGH',
        help='Scaffolding level (default: HIGH)'
    )

    args = parser.parse_args()

    try:
        output_path = Path(args.path)

        # Create module directory
        module_dir = create_module_directory(args.id, output_path)

        # Write all module files
        write_module_files(
            module_dir=module_dir,
            module_id=args.id,
            title=args.title,
            scaffolding=args.scaffolding
        )

        print(f"\n🎉 Module {args.id} initialized successfully!")
        print(f"   Location: {module_dir}")
        print(f"   Scaffolding: {args.scaffolding}")
        print("\n📝 Next steps:")
        print(f"   1. Edit {module_dir}/metadata.py (replace TODOs)")
        print(f"   2. Write {module_dir}/content.md")
        print(f"   3. Implement {module_dir}/code.py")
        print(f"   4. Run validation: python validate_module.py {module_dir}")

        return 0

    except FileExistsError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1

    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
