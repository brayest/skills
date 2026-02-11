---
name: learning-design
description: This skill should be used when designing or implementing progressive learning systems based on cognitive science principles. Provides architecture patterns for module-based learning, metadata schemas for scaffolding and prerequisites, content design templates, validation checklists, and implementation guidelines for building educational tools that optimize knowledge acquisition through ZPD, Bloom's taxonomy, spaced repetition, and retrieval practice.
---

# Learning Design

## Purpose

Provide science-backed patterns for designing progressive learning systems that optimize knowledge acquisition. Cover cognitive science principles (Zone of Proximal Development, scaffolding, spaced repetition), architectural patterns for module-based systems, metadata schemas for tracking complexity and prerequisites, and validation tools for ensuring pedagogical soundness.

## When to Use This Skill

Use this skill when:
- Designing a progressive learning system for any domain (programming, languages, skills training)
- Building educational tools with module-based content delivery
- Creating learning platforms that adapt difficulty based on learner progress
- Implementing prerequisite-based learning paths
- Designing scaffolded learning experiences with systematic support withdrawal
- Validating existing educational content against cognitive science principles
- Setting up analytics to track learning effectiveness
- Building curriculum with appropriate cognitive load and complexity progression

## Core Learning Principles

Eight science-backed principles form the foundation of effective progressive learning:

### 1. Zone of Proximal Development (ZPD)

Teach content just beyond current ability—challenging but achievable with support.

**Implementation:**
- Map explicit prerequisites for each learning unit
- Track learner's demonstrated competencies
- Block access to advanced modules until foundations are solid
- Use prerequisite chains: `prerequisites: [0, 1, 2]`

**Example:**
```python
METADATA = {
    'id': 5,
    'prerequisites': [0, 1, 2, 4],  # Must complete these first
    'concepts': ['new_concept_a', 'new_concept_b'],
}
```

For detailed ZPD implementation patterns, research citations, and multi-domain examples, consult `references/learning-principles.md`.

### 2. Scaffolding with Systematic Withdrawal

Provide high support when concepts are new, gradually remove as competence increases.

**Scaffolding Levels:**
- **HIGH**: Step-by-step walkthroughs, heavy commenting, complete examples
- **MEDIUM**: Guided exercises, partial examples, conceptual hints
- **LOW**: Open-ended challenges, minimal guidance, integration tasks

**Progression Rule:** Reduce scaffolding gradually across 2-3 modules, never abruptly.

### 3. Comprehensible Input (i+1)

Expose learners to material that's 90-95% familiar, 5-10% new and inferrable from context.

**Implementation:**
- Limit new concepts per module (3-5 max)
- Reuse established patterns when introducing new ideas
- Provide context clues: comments, diagrams, working examples

**Anti-Pattern:**
```python
# BAD: 10 new concepts at once
Module 3: ['async', 'await', 'futures', 'tasks', 'coroutines',
           'event_loop', 'gather', 'create_task', 'run_until_complete']

# GOOD: Incremental introduction
Module 3: ['async', 'await', 'basic coroutine']
Module 4: ['asyncio.create_task', 'asyncio.gather']
Module 5: ['event loop', 'concurrency patterns']
```

### 4. Bloom's Taxonomy Progression

Cognitive complexity follows hierarchy: Remember → Understand → Apply → Analyze → Evaluate → Create.

**Module Tagging:**
- Early modules: **Remember** (recall facts, recognize patterns)
- Mid modules: **Understand** (explain concepts, compare approaches)
- Advanced modules: **Apply/Analyze** (solve problems, debug systems)
- Capstone modules: **Evaluate/Create** (design solutions, critique trade-offs)

**Rule:** Allow 2-3 modules at same Bloom level before advancing.

### 5. Spaced Repetition

Review information at increasing intervals for long-term retention.

**Implementation:**
- Revisit core concepts in later modules (interleaved review)
- Include "refresher" sections recalling earlier patterns
- Use consistent vocabulary/patterns across modules

**Pattern:**
```markdown
# Module 10 explicitly revisits Module 3
Quick Recap: In Module 3, you learned X.
Now we're extending that concept to scenario Y.
```

### 6. Interleaving (Mixed Practice)

Mix related concepts rather than blocking identical practice—forces discrimination between similar ideas.

**Implementation:**
- Don't drill one concept to mastery before introducing next
- Later modules should combine concepts from multiple earlier modules
- Mix exercise types: problem A → B → A → C

**Anti-Pattern:**
```python
# BAD: Blocked practice
Module 5: 20 exercises all about async/await
Module 6: 20 exercises all about error handling

# GOOD: Interleaved practice
Module 5: Exercise 1 (async), Exercise 2 (error handling),
          Exercise 3 (async), Exercise 4 (combining both)
```

### 7. Retrieval Practice (Testing Effect)

Active recall produces stronger retention than re-reading.

**Implementation:**
- Include "try it yourself" challenges before showing solutions
- Use fill-in-the-blank, not multiple choice (generation > recognition)
- Provide immediate feedback after retrieval attempts

**Structure:**
1. Concept introduction (brief)
2. Challenge: "Before looking at solution, try implementing X"
3. Learner attempts (retrieval practice)
4. Solution revealed with explanation

### 8. Deliberate Practice with Immediate Feedback

Practice specific weaknesses with instant correction.

**Implementation:**
- Identify common failure points, create targeted exercises
- Provide feedback within seconds, not hours/days
- Allow unlimited retries with varied scenarios
- Focus on production gaps, not just comprehension

For detailed explanations of all 8 principles with research citations, implementation patterns, and multi-domain examples, consult `references/learning-principles.md`.

---

## Architecture & Implementation

### Module-Based Structure

```
learning_system/
├── modules/
│   ├── module_00/          # Foundation module
│   │   ├── __init__.py
│   │   ├── metadata.py     # Learning objectives, prerequisites
│   │   ├── content.md      # Instructional content
│   │   ├── code.py         # Working example code
│   │   └── exercises/      # Optional practice problems
│   ├── module_01/
│   └── ...
├── loader.py               # Dynamic module discovery
├── progress_tracker.py     # Learner state management
└── validators.py           # Prerequisite enforcement
```

**Key Principles:**
- Each module self-contained but aware of dependencies
- Explicit metadata prevents ambiguity
- Dynamic loading supports easy addition of new modules
- Validation ensures structural consistency

For complete architecture patterns, metadata schemas, prerequisite graph algorithms, and validation code, consult `references/architecture-patterns.md`.

### Metadata Schema

```python
METADATA = {
    'id': int,                          # Unique identifier
    'title': str,                       # Human-readable name
    'description': str,                 # Brief summary
    'bloom_level': str,                 # Remember/Understand/Apply/Analyze/Evaluate/Create
    'scaffolding_level': str,           # HIGH/MEDIUM/LOW
    'concepts': list[str],              # New concepts introduced (3-5 max)
    'prerequisites': list[int],         # Required prior modules
    'estimated_time_minutes': int,      # Completion estimate
    'difficulty': str,                  # BEGINNER/INTERMEDIATE/ADVANCED
    'workspace_path': str,              # Path to executable code/exercises
}
```

**Benefits:**
- Learners know exactly what they'll learn
- System can validate readiness before module access
- Analytics can identify common sticking points
- Content creators have clear guidelines

### Progressive Complexity Ladder

**Progression Rules:**

1. **Never increase Bloom level AND reduce scaffolding in same module**
   - ❌ Bad: Module 5 (Understand/LOW) after Module 4 (Remember/HIGH)
   - ✅ Good: Module 5 (Understand/HIGH) after Module 4 (Remember/HIGH)

2. **Limit new concepts per module**
   - 3-5 concepts max
   - Introduce supporting concepts before complex ones

3. **Ensure prerequisite transitivity**
   - If Module 5 needs Module 3, and Module 3 needs Module 1, Module 5 must list [1, 3]
   - Use scripts/validate_graph.py to check

4. **Prerequisites form coherent DAG, not linear chain**
   - No circular dependencies
   - No orphaned modules (except module 0)

**Example Progression:**
```python
Module 0: bloom='Remember', scaffolding='HIGH', prerequisites=[]
Module 1: bloom='Remember', scaffolding='HIGH', prerequisites=[0]
Module 3: bloom='Understand', scaffolding='MEDIUM', prerequisites=[0,1,2]
Module 6: bloom='Apply', scaffolding='MEDIUM', prerequisites=[0,1,2,3,4,5]
Module 10: bloom='Apply/Analyze', scaffolding='LOW', prerequisites=[0,7,8,9]
```

For detailed implementation, prerequisite graph validators, module loaders, and progress tracking code, consult `references/architecture-patterns.md`.

---

## Content Design

### Content.md Template

```markdown
# Module N: [Title]

## Overview
[2-3 sentences: What this module teaches and why it matters]

## Prerequisites
[What you should already know from previous modules]

## Core Concepts

### Concept 1: [Name]
[Explanation with examples]

**Why This Matters:**
[Real-world application or importance]

### Concept 2: [Name]
[...]

## Hands-On Example
[Step-by-step walkthrough of code.py]

## Try It Yourself
[Challenge requiring application of what was learned]

## What's Next
[Preview how these concepts will be used in upcoming modules]
```

**Guidelines:**
- Keep total reading time under 10 minutes
- Use analogies/metaphors for abstract concepts
- Link back to previous modules for context
- Forward-reference to create curiosity

### Code.py Patterns

**HIGH Scaffolding (Beginner Modules):**
```python
"""
Module N: [Title]
This code demonstrates [X, Y, Z].
Run it as-is first, then experiment with modifications.
"""

# === STEP 1: [Action] ===
# [Why we're doing this]
variable = function(parameter)
print(f"Step 1 result: {variable}")  # Show intermediate output

# === STEP 2: [Action] ===
# [Why this is necessary]
next_step = variable.method()
print(f"Step 2 result: {next_step}")

# === STEP 3: [Action] ===
# [Final result and explanation]
final = process(next_step)
print(f"Final result: {final}")
print(f"Notice how [key insight from output]")
```

**MEDIUM Scaffolding (Intermediate Modules):**
```python
"""
Module N: [Title]
Apply concepts from Modules [X, Y] to solve [problem].
Fill in the TODOs, then run to verify.
"""

# Setup (provided)
setup = Thing(config)

# TODO: Implement the pattern from Module X
result = None  # Replace this

# TODO: Handle edge case discussed in Module Y
# Your code here

# Verification (provided)
assert result is not None, "Complete the TODOs above"
print(f"Success! Result: {result}")
```

**LOW Scaffolding (Advanced Modules):**
```python
"""
Module N: [Title]

Build a [system/solution] that combines:
- Module X concept: [specific pattern]
- Module Y concept: [specific pattern]
- Module Z concept: [specific pattern]

Requirements:
1. [Functional requirement]
2. [Performance requirement]
3. [Error handling requirement]

No scaffolding provided—apply what you've learned.
"""

# Your implementation here
```

### Exercise Design

```python
{
    'id': 'module_03_exercise_01',
    'type': 'code_completion',  # or 'debugging', 'design'
    'difficulty': 'MEDIUM',
    'prompt': """
        Given this code:
        [starter code]
        Modify it to [specific objective].
    """,
    'hints': [
        "Remember the pattern from Module X",
        "What does the documentation say about parameter Y?"
    ],
    'solution': """[Complete solution with explanation]""",
    'test_cases': [
        {'input': X, 'expected_output': Y},
    ],
    'common_mistakes': [
        {
            'pattern': 'forgot to call method()',
            'feedback': 'You created the object but never invoked it.'
        }
    ]
}
```

**Exercise Types by Scaffolding Level:**
- **HIGH**: Fill-in-blank with hints, "spot the bug", modify working code
- **MEDIUM**: Write function matching spec, debug with minimal hints, combine 2-3 concepts
- **LOW**: Design from requirements, open-ended challenges, integrate multiple modules

For complete content.md templates, code.py patterns for all scaffolding levels, and exercise design schemas, consult `references/content-design.md`.

---

## Validation & Quality

### Quick Validation Checklist

Before publishing a module, verify:

- [ ] Learning objective is specific and measurable
- [ ] Bloom level appropriate for sequence position
- [ ] Scaffolding decreases as learner progresses (not constant)
- [ ] Prerequisites explicitly listed and form valid DAG
- [ ] New concepts limited to 3-5 max
- [ ] Working code example included and tested
- [ ] Content includes "why" explanations, not just "how"
- [ ] Exercises require retrieval/generation, not recognition
- [ ] Immediate feedback provided on learner attempts
- [ ] Prior concepts revisited (spaced repetition)
- [ ] Module references where concepts will be used next
- [ ] Estimated completion time is realistic
- [ ] Content 500-2000 words (not too brief/long)

### Validation Scripts

Use provided scripts for automated validation:

**Initialize new module:**
```bash
python scripts/init_module.py <id> "<title>" --path ./modules/ [--scaffolding HIGH|MEDIUM|LOW]
```

**Validate individual module:**
```bash
python scripts/validate_module.py modules/module_05/
```
Checks: required files, metadata schema, prerequisites, code syntax, content length

**Validate prerequisite graph:**
```bash
python scripts/validate_graph.py modules/ [--visualize]
```
Checks: no cycles, no orphans, transitivity, progression rules

**Analyze learner metrics:**
```bash
python scripts/analyze_metrics.py --data learner_analytics.json
```
Reports: completion rates, time vs estimates, retry rates, problem modules

For detailed validation code, metrics interpretation, and testing strategies, consult `references/validation-tools.md` and `references/implementation-guide.md`.

---

## Common Pitfalls

Top 10 mistakes to avoid:

1. **Curse of Knowledge** — Skipping "obvious" steps beginners need
   - Solution: Have beginners review content; track support questions

2. **Scope Creep** — Teaching too many concepts per module
   - Solution: Enforce 3-5 concept limit; move extras to appendix

3. **Insufficient Scaffolding Reduction** — Same support level throughout
   - Solution: Plan reduction upfront (1-3 HIGH, 4-7 MEDIUM, 8+ LOW)

4. **Broken Prerequisites** — Module assumes knowledge not listed
   - Solution: Automated validation with concept mapping

5. **Teaching Patterns, Not Principles** — Memorization without understanding
   - Solution: Explain "why" before "how"; include "what if" sections

6. **No Interleaving/Spacing** — Never revisiting earlier concepts
   - Solution: Explicitly reference prior modules; design capstone integrating 5-10 concepts

7. **Passive Learning Only** — No active retrieval or production
   - Solution: Every module requires generation (writing code, not reading it)

8. **Ignoring Cognitive Load** — Too many new things simultaneously
   - Solution: Track "novelty budget" of max 3-5 new items per module

9. **Inadequate Feedback** — Learners don't know if they're right
   - Solution: Immediate automated feedback; show solution after 2-3 failed attempts

10. **Building for Yourself** — Designing for experts, not beginners
    - Solution: User testing with actual beginners; analytics-driven iteration

For detailed explanations with before/after examples, detection methods, and root cause analysis, consult `references/common-pitfalls.md`.

---

## Metrics & Analytics

### Key Metrics to Track

**Completion Rate**
- % of learners who complete module after starting
- **Target:** >70%
- **Red Flag:** <70% indicates module too difficult or prerequisite gap

**Time to Complete**
- Actual time vs estimated time
- **Red Flag:** Actual > 2x estimate indicates poor scaffolding or scope creep

**Retry Rate**
- % of learners who restart module after initial attempt
- **Target:** <30%
- **Red Flag:** >30% indicates confusing instructions or missing prerequisites

**Exercise Success**
- First-attempt success rate on exercises
- **Target:** >50%
- **Red Flag:** <50% indicates concept not adequately taught

**Prerequisite Violations**
- How often learners try to skip ahead
- High violations indicate unclear prerequisites or impatient learners

### What Metrics Reveal

```python
analytics = {
    'module_01': {'completion': 0.95},  # High = appropriate difficulty
    'module_05': {'completion': 0.60},  # Low = too hard or prerequisite gap
    'module_05': {'time': 65, 'estimate': 30},  # 2.2x = needs work
    'module_07': {'retry': 0.41},  # >30% = confusing or hard
    'module_04_ex_02': {'success': 0.31},  # <50% = needs redesign
}
```

**Action Items:**
- Module 5: Check prerequisites, reduce scope, improve scaffolding
- Module 7: Clarify instructions, add examples
- Module 4 Ex 2: Add hints, break into smaller steps

For detailed metrics tracking implementation, A/B testing patterns, and iteration workflow, consult `references/implementation-guide.md`.

---

## Key Principles

All learning design follows these principles:

1. **Fail-Fast Prerequisites** — Block access if prerequisites not met, no silent degradation
2. **Explicit Metadata** — All learning objectives, scaffolding, dependencies documented
3. **Progressive Complexity** — Never increase cognitive load AND reduce scaffolding simultaneously
4. **Comprehensible Input** — Limit new concepts to 3-5 per module
5. **Working Code First** — Every module includes immediately executable examples
6. **Retrieval Over Recognition** — Exercises require generation, not multiple choice
7. **Spaced Interleaving** — Later modules revisit and combine earlier concepts
8. **Measure What Matters** — Track completion, time, retries, exercise success

---

## Implementation Workflow

### For New Learning Systems

**1. Define Learning Objectives**
- Start with what learner should be able to DO
- Work backward to determine prerequisites
- Identify minimal concepts needed

**2. Design Module Sequence**
- Map concepts to modules (3-5 concepts per module)
- Define prerequisites (form DAG, no cycles)
- Assign Bloom levels and scaffolding levels
- Validate with `scripts/validate_graph.py`

**3. Create Content**
- Use templates from `references/content-design.md`
- Include working examples and exercises
- Apply appropriate scaffolding for level
- Validate with `scripts/validate_module.py`

**4. Implement Progress Tracking**
- Track completed modules, attempts, time
- Enforce prerequisite validation
- Collect metrics (completion, retry, success rates)

**5. Iterate Based on Data**
- Identify low-completion modules
- Fix broken prerequisites
- Adjust scaffolding or cognitive load
- Improve exercises with low success rates

### For Existing Systems

**1. Audit Current State**
- Run validation scripts on existing modules
- Check prerequisite graph for cycles/orphans
- Review metrics for red flags

**2. Prioritize Issues**
- Fix structural problems first (broken prerequisites)
- Address low-completion modules
- Improve scaffolding progression
- Add missing retrieval practice

**3. Refactor Incrementally**
- One module at a time
- Test with learners
- Monitor metrics for improvement

---

## Decision Trees

### Choosing Scaffolding Level

**When to use HIGH Scaffolding:**
- Modules 1-3 in sequence
- Introducing entirely new domain/syntax
- Target audience: complete beginners
- Pattern: Step-by-step walkthroughs, heavy commenting, complete annotated examples

**When to use MEDIUM Scaffolding:**
- Modules 4-7 in sequence
- Learners have foundation but not mastery
- Target audience: intermediate learners
- Pattern: Guided exercises with hints, partial examples, conceptual guidance

**When to use LOW Scaffolding:**
- Modules 8+ in sequence
- Learners ready for independence
- Target audience: advanced learners
- Pattern: Open-ended challenges, minimal guidance, integration tasks

**Critical Rule:** Reduce scaffolding gradually across 2-3 modules, never abruptly.

### Choosing Bloom Level

**Remember (Modules 1-3):**
- Objective: Recall facts, recognize patterns
- Questions: "What does function X do?" "Which method handles Y?"
- Exercises: Identify correct syntax, match concepts to definitions

**Understand (Modules 4-6):**
- Objective: Explain concepts, compare approaches
- Questions: "Why does pattern X work better than Y?" "What happens if you change Z?"
- Exercises: Explain code behavior, predict outcomes

**Apply (Modules 7-9):**
- Objective: Solve problems, debug systems
- Questions: "Use pattern X to solve problem Y" "Fix this broken code"
- Exercises: Write functions, implement features, debug errors

**Analyze/Evaluate (Modules 10-12):**
- Objective: Compare solutions, identify trade-offs
- Questions: "Which approach is better for scenario X?" "Critique this implementation"
- Exercises: Optimization challenges, architecture review

**Create (Capstone):**
- Objective: Design solutions from scratch
- Questions: "Build a system that..." "Architect a solution for..."
- Exercises: End-to-end projects, open-ended design challenges

**Critical Rule:** Allow 2-3 modules at same Bloom level before advancing.

### Complexity Progression Rules

1. **Never increase Bloom AND reduce scaffolding simultaneously**
   - Increment one dimension at a time
   - Allow learners to adapt to each change

2. **Enforce 3-5 concept limit per module**
   - Track "novelty budget"
   - Move extras to separate modules

3. **Validate prerequisite transitivity**
   - Use `scripts/validate_graph.py`
   - Manual review of concept dependencies

4. **Ensure DAG structure**
   - No circular dependencies
   - All modules (except 0) reachable from module 0

---

## Resources

This skill includes bundled resources for different aspects of learning design:

### scripts/

Executable Python scripts for automating module creation and validation:

- **init_module.py** — Scaffold new module directories with templates
- **validate_module.py** — Check individual module structure and quality
- **validate_graph.py** — Validate prerequisite dependency graph (cycles, orphans, progression rules)
- **analyze_metrics.py** — Analyze learner metrics and identify problem modules

Scripts may be executed without loading into context.

### references/

In-depth documentation for each aspect of learning design:

- **learning-principles.md** — Deep dive into 8 cognitive science principles with research citations and implementation patterns
- **architecture-patterns.md** — Module structure, metadata schemas, prerequisite graph algorithms, validation code
- **content-design.md** — Content.md templates, code.py patterns for HIGH/MEDIUM/LOW scaffolding, exercise design schemas
- **implementation-guide.md** — Step-by-step implementation process, metrics tracking, iteration workflow
- **common-pitfalls.md** — Detailed explanations of 10 common mistakes with before/after examples and solutions

Reference files are loaded into context as needed when Claude determines they're relevant.

---

## Getting Started

To apply these patterns:

1. **Read Core Principles** — `references/learning-principles.md` for cognitive science foundation
2. **Choose Architecture** — `references/architecture-patterns.md` for module structure
3. **Design Content** — `references/content-design.md` for templates and examples
4. **Validate Quality** — Use scripts to check structure and metrics
5. **Implement & Measure** — `references/implementation-guide.md` for tracking and iteration

For immediate action:
- Use `scripts/init_module.py` to scaffold new module directories
- Use `scripts/validate_module.py` to check structural quality
- Use `scripts/validate_graph.py` to verify prerequisite dependencies
- Use `scripts/analyze_metrics.py` to identify problem modules
