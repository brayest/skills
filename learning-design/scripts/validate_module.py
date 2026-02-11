#!/usr/bin/env python3
"""
Validate module structure and content quality.

Usage:
    python validate_module.py <module-path>

Example:
    python validate_module.py ./modules/module_05
"""

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any


# Valid enum values
BLOOM_LEVELS = {'Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create'}
SCAFFOLDING_LEVELS = {'HIGH', 'MEDIUM', 'LOW'}
DIFFICULTY_LEVELS = {'BEGINNER', 'INTERMEDIATE', 'ADVANCED'}

# Content constraints
MIN_WORD_COUNT = 500
MAX_WORD_COUNT = 2000
MAX_CONCEPTS = 5


def validate_file_structure(module_dir: Path) -> list[str]:
    """
    Validate required files exist.

    Args:
        module_dir: Path to module directory

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    required_files = ['__init__.py', 'metadata.py', 'content.md', 'code.py']

    for filename in required_files:
        file_path = module_dir / filename
        if not file_path.exists():
            errors.append(f"Missing required file: {filename}")

    return errors


def load_metadata(module_dir: Path) -> tuple[dict[str, Any] | None, list[str]]:
    """
    Load and return module metadata.

    Args:
        module_dir: Path to module directory

    Returns:
        Tuple of (metadata dict or None, list of errors)
    """
    errors = []
    metadata_path = module_dir / 'metadata.py'

    try:
        # Import metadata module dynamically
        spec = importlib.util.spec_from_file_location('metadata', metadata_path)
        if spec is None or spec.loader is None:
            errors.append("Failed to load metadata.py")
            return None, errors

        metadata_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(metadata_module)

        if not hasattr(metadata_module, 'METADATA'):
            errors.append("metadata.py must export METADATA dict")
            return None, errors

        return metadata_module.METADATA, errors

    except Exception as e:
        errors.append(f"Failed to load metadata: {e}")
        return None, errors


def validate_metadata_schema(metadata: dict[str, Any]) -> list[str]:
    """
    Validate metadata has required fields and correct types.

    Args:
        metadata: Metadata dictionary

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
            errors.append(f"Metadata missing required field: '{field}'")

    # Type validation
    if 'id' in metadata and not isinstance(metadata['id'], int):
        errors.append(f"'id' must be an integer, got {type(metadata['id']).__name__}")

    if 'title' in metadata and not isinstance(metadata['title'], str):
        errors.append(f"'title' must be a string, got {type(metadata['title']).__name__}")

    if 'description' in metadata and not isinstance(metadata['description'], str):
        errors.append(f"'description' must be a string, got {type(metadata['description']).__name__}")

    if 'prerequisites' in metadata:
        if not isinstance(metadata['prerequisites'], list):
            errors.append(f"'prerequisites' must be a list, got {type(metadata['prerequisites']).__name__}")
        elif not all(isinstance(p, int) for p in metadata['prerequisites']):
            errors.append("All prerequisites must be integers")

    if 'concepts' in metadata:
        if not isinstance(metadata['concepts'], list):
            errors.append(f"'concepts' must be a list, got {type(metadata['concepts']).__name__}")
        elif not all(isinstance(c, str) for c in metadata['concepts']):
            errors.append("All concepts must be strings")

    # Enum validation
    if 'bloom_level' in metadata and metadata['bloom_level'] not in BLOOM_LEVELS:
        errors.append(
            f"Invalid bloom_level: '{metadata['bloom_level']}'. "
            f"Must be one of: {', '.join(sorted(BLOOM_LEVELS))}"
        )

    if 'scaffolding_level' in metadata and metadata['scaffolding_level'] not in SCAFFOLDING_LEVELS:
        errors.append(
            f"Invalid scaffolding_level: '{metadata['scaffolding_level']}'. "
            f"Must be one of: {', '.join(sorted(SCAFFOLDING_LEVELS))}"
        )

    if 'difficulty' in metadata and metadata['difficulty'] not in DIFFICULTY_LEVELS:
        errors.append(
            f"Invalid difficulty: '{metadata['difficulty']}'. "
            f"Must be one of: {', '.join(sorted(DIFFICULTY_LEVELS))}"
        )

    # Business rules
    if metadata.get('concepts') == []:
        errors.append("'concepts' list cannot be empty (what does this module teach?)")

    if len(metadata.get('concepts', [])) > MAX_CONCEPTS:
        errors.append(
            f"Too many concepts ({len(metadata['concepts'])}). "
            f"Maximum {MAX_CONCEPTS} recommended. Consider splitting into multiple modules."
        )

    if 'id' in metadata and 'prerequisites' in metadata:
        if metadata['id'] in metadata['prerequisites']:
            errors.append(f"Module {metadata['id']} cannot be its own prerequisite")

    # Check for TODO placeholders
    for field in ['title', 'description', 'bloom_level', 'difficulty']:
        if field in metadata and 'TODO' in str(metadata[field]):
            errors.append(f"'{field}' contains TODO placeholder - needs completion")

    if 'concepts' in metadata:
        for concept in metadata['concepts']:
            if 'TODO' in str(concept):
                errors.append(f"'concepts' contains TODO placeholder: '{concept}'")

    return errors


def validate_code_syntax(module_dir: Path) -> list[str]:
    """
    Validate Python code is syntactically correct.

    Args:
        module_dir: Path to module directory

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    code_file = module_dir / 'code.py'

    try:
        code = code_file.read_text()

        # Check if file is basically empty (just comments/whitespace)
        lines = [line.strip() for line in code.split('\n') if line.strip() and not line.strip().startswith('#')]
        if len(lines) == 0:
            errors.append("code.py appears to be empty (no executable code)")
            return errors

        # Compile code to check syntax
        compile(code, str(code_file), 'exec')

    except SyntaxError as e:
        errors.append(f"Code has syntax error at line {e.lineno}: {e.msg}")
    except Exception as e:
        errors.append(f"Failed to validate code: {e}")

    return errors


def validate_content_quality(module_dir: Path) -> list[str]:
    """
    Validate content.md quality and length.

    Args:
        module_dir: Path to module directory

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    content_file = module_dir / 'content.md'

    try:
        content = content_file.read_text()
        word_count = len(content.split())

        if word_count < MIN_WORD_COUNT:
            errors.append(
                f"Content too brief ({word_count} words, minimum {MIN_WORD_COUNT}). "
                "Add more examples, explanations, or exercises."
            )
        elif word_count > MAX_WORD_COUNT:
            errors.append(
                f"Content too long ({word_count} words, maximum {MAX_WORD_COUNT}). "
                "Consider splitting into multiple modules to avoid cognitive overload."
            )

        # Check for TODO placeholders
        if 'TODO:' in content or 'TODO ' in content:
            todo_count = content.count('TODO')
            errors.append(
                f"Content contains {todo_count} TODO placeholder(s) - needs completion"
            )

        # Check for basic markdown structure
        if '# ' not in content:
            errors.append("Content missing markdown headings (should start with # Title)")

        # Check for code examples
        if '```' not in content:
            errors.append("Content missing code examples (no ``` code blocks found)")

    except Exception as e:
        errors.append(f"Failed to read content: {e}")

    return errors


def validate_module(module_dir: Path) -> tuple[bool, list[str]]:
    """
    Run all validation checks on a module.

    Args:
        module_dir: Path to module directory

    Returns:
        Tuple of (is_valid, list of errors)
    """
    all_errors = []

    # Check 1: File structure
    errors = validate_file_structure(module_dir)
    all_errors.extend(errors)

    # If files missing, can't continue
    if errors:
        return False, all_errors

    # Check 2: Metadata
    metadata, errors = load_metadata(module_dir)
    all_errors.extend(errors)

    if metadata is not None:
        errors = validate_metadata_schema(metadata)
        all_errors.extend(errors)

    # Check 3: Code syntax
    errors = validate_code_syntax(module_dir)
    all_errors.extend(errors)

    # Check 4: Content quality
    errors = validate_content_quality(module_dir)
    all_errors.extend(errors)

    return len(all_errors) == 0, all_errors


def format_error_report(module_dir: Path, errors: list[str]) -> str:
    """Format validation errors for display."""
    report = [
        f"\n{'='*60}",
        f"Module Validation Report: {module_dir.name}",
        f"{'='*60}\n",
    ]

    if not errors:
        report.append("✅ All validation checks passed!\n")
    else:
        report.append(f"❌ Found {len(errors)} validation error(s):\n")

        for i, error in enumerate(errors, 1):
            report.append(f"  {i}. {error}")

        report.append("\n📝 Fix these issues and run validation again.")

    report.append(f"{'='*60}\n")

    return '\n'.join(report)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Validate module structure and content quality.'
    )

    parser.add_argument(
        'module_path',
        type=str,
        help='Path to module directory (e.g., ./modules/module_05)'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show detailed validation information'
    )

    args = parser.parse_args()

    try:
        module_path = Path(args.module_path)

        if not module_path.exists():
            print(f"❌ Error: Module directory not found: {module_path}", file=sys.stderr)
            return 1

        if not module_path.is_dir():
            print(f"❌ Error: Path is not a directory: {module_path}", file=sys.stderr)
            return 1

        # Run validation
        is_valid, errors = validate_module(module_path)

        # Display report
        report = format_error_report(module_path, errors)
        print(report)

        # Verbose output
        if args.verbose and is_valid:
            print("Validation details:")
            print(f"  - ✅ File structure complete")
            print(f"  - ✅ Metadata schema valid")
            print(f"  - ✅ Code syntax correct")
            print(f"  - ✅ Content quality acceptable")

        return 0 if is_valid else 1

    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
