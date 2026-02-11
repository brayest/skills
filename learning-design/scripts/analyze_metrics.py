#!/usr/bin/env python3
"""
Analyze learner metrics to identify problem modules and improvement opportunities.

Expected JSON format:
{
    "modules": {
        "0": {"title": "...", "estimated_time_minutes": 15},
        "1": {...}
    },
    "learners": [
        {
            "learner_id": "user123",
            "started_modules": [0, 1, 2],
            "completed_modules": [0, 1],
            "time_spent": {"0": 18, "1": 25},
            "module_attempts": {"0": 1, "1": 2},
            "exercise_scores": {"module_01_ex_01": 0.85, ...},
            "prerequisite_violations": []
        },
        ...
    ]
}

Usage:
    python analyze_metrics.py --data learner_analytics.json [--module MODULE_ID]

Example:
    python analyze_metrics.py --data analytics.json
    python analyze_metrics.py --data analytics.json --module 5
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# Red flag thresholds
MIN_COMPLETION_RATE = 0.70
MAX_TIME_MULTIPLIER = 2.0
MAX_RETRY_RATE = 0.30
MIN_EXERCISE_SUCCESS = 0.50


@dataclass
class ModuleMetrics:
    """Analytics for a single module."""
    module_id: int
    title: str
    started_count: int
    completed_count: int
    completion_rate: float
    estimated_time_minutes: int
    actual_time_median: int
    actual_time_p90: int
    retry_count: int
    retry_rate: float
    exercise_success_rates: dict[str, float]
    premature_access_attempts: int

    def get_red_flags(self) -> list[str]:
        """Identify problems with this module."""
        flags = []

        if self.completion_rate < MIN_COMPLETION_RATE:
            flags.append(
                f"Low completion rate ({self.completion_rate:.1%} < {MIN_COMPLETION_RATE:.1%}) "
                "- module too difficult or prerequisites missing"
            )

        if self.estimated_time_minutes > 0 and self.actual_time_median > MAX_TIME_MULTIPLIER * self.estimated_time_minutes:
            flags.append(
                f"Time estimate off ({self.actual_time_median}min actual vs "
                f"{self.estimated_time_minutes}min estimated, "
                f"{self.actual_time_median / self.estimated_time_minutes:.1f}x multiplier) "
                "- poor scaffolding or scope too large"
            )

        if self.retry_rate > MAX_RETRY_RATE:
            flags.append(
                f"High retry rate ({self.retry_rate:.1%} > {MAX_RETRY_RATE:.1%}) "
                "- unclear instructions or exercises too hard"
            )

        for ex_id, success_rate in self.exercise_success_rates.items():
            if success_rate < MIN_EXERCISE_SUCCESS:
                flags.append(
                    f"Exercise {ex_id} low success rate ({success_rate:.1%} < {MIN_EXERCISE_SUCCESS:.1%}) "
                    "- concept not adequately taught"
                )

        if self.premature_access_attempts > 50:
            flags.append(
                f"Many prerequisite skip attempts ({self.premature_access_attempts}) "
                "- make dependencies clearer"
            )

        return flags


def load_analytics_data(data_path: Path) -> dict[str, Any]:
    """
    Load analytics JSON file.

    Args:
        data_path: Path to JSON analytics file

    Returns:
        Analytics data dictionary

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file isn't valid JSON
    """
    if not data_path.exists():
        raise FileNotFoundError(f"Analytics file not found: {data_path}")

    with open(data_path, 'r') as f:
        data = json.load(f)

    # Validate structure
    if 'modules' not in data:
        raise ValueError("Analytics JSON missing 'modules' key")

    if 'learners' not in data:
        raise ValueError("Analytics JSON missing 'learners' key")

    return data


def calculate_module_metrics(
    module_id: int,
    module_info: dict[str, Any],
    learner_data: list[dict[str, Any]]
) -> ModuleMetrics:
    """
    Calculate analytics for a single module.

    Args:
        module_id: Module ID
        module_info: Module metadata from analytics
        learner_data: List of learner progress dicts

    Returns:
        ModuleMetrics with calculated values
    """
    # Filter learners who interacted with this module
    started = [
        l for l in learner_data
        if module_id in l.get('started_modules', [])
    ]

    completed = [
        l for l in learner_data
        if module_id in l.get('completed_modules', [])
    ]

    started_count = len(started)
    completed_count = len(completed)
    completion_rate = completed_count / started_count if started_count > 0 else 0.0

    # Time metrics
    completion_times = [
        l['time_spent'].get(str(module_id), 0)
        for l in completed
        if str(module_id) in l.get('time_spent', {})
    ]

    if completion_times:
        sorted_times = sorted(completion_times)
        actual_time_median = sorted_times[len(sorted_times) // 2]
        actual_time_p90 = sorted_times[int(len(sorted_times) * 0.9)]
    else:
        actual_time_median = 0
        actual_time_p90 = 0

    # Retry metrics
    retry_count = sum(
        l.get('module_attempts', {}).get(str(module_id), 1) - 1
        for l in learner_data
    )
    retry_rate = retry_count / started_count if started_count > 0 else 0.0

    # Exercise metrics
    exercise_success_rates = {}
    exercise_attempts = {}

    for learner in learner_data:
        for ex_id, score in learner.get('exercise_scores', {}).items():
            # Only count exercises from this module
            if not ex_id.startswith(f'module_{module_id:02d}_'):
                continue

            # Track attempts
            attempts = learner.get('exercise_attempts', {}).get(ex_id, 1)
            exercise_attempts[ex_id] = exercise_attempts.get(ex_id, 0) + attempts

            # Track successes (score > 0.5)
            if score > 0.5:
                exercise_success_rates[ex_id] = exercise_success_rates.get(ex_id, 0) + 1

    # Calculate success rates
    for ex_id in exercise_attempts:
        if ex_id in exercise_success_rates:
            exercise_success_rates[ex_id] /= exercise_attempts[ex_id]
        else:
            exercise_success_rates[ex_id] = 0.0

    # Prerequisite violations
    premature_access = sum(
        1 for l in learner_data
        if module_id in l.get('prerequisite_violations', [])
    )

    return ModuleMetrics(
        module_id=module_id,
        title=module_info.get('title', 'Unknown'),
        started_count=started_count,
        completed_count=completed_count,
        completion_rate=completion_rate,
        estimated_time_minutes=module_info.get('estimated_time_minutes', 0),
        actual_time_median=actual_time_median,
        actual_time_p90=actual_time_p90,
        retry_count=retry_count,
        retry_rate=retry_rate,
        exercise_success_rates=exercise_success_rates,
        premature_access_attempts=premature_access,
    )


def format_module_report(metrics: ModuleMetrics) -> str:
    """Format detailed module metrics report."""
    report = [
        f"\n{'='*70}",
        f"Module {metrics.module_id}: {metrics.title}",
        f"{'='*70}\n",
        "📊 Core Metrics:",
        f"  Started: {metrics.started_count} learners",
        f"  Completed: {metrics.completed_count} learners",
        f"  Completion Rate: {metrics.completion_rate:.1%}",
        "",
        "⏱️  Time Metrics:",
        f"  Estimated: {metrics.estimated_time_minutes} minutes",
        f"  Actual (Median): {metrics.actual_time_median} minutes",
        f"  Actual (90th percentile): {metrics.actual_time_p90} minutes",
        "",
        "🔄 Engagement:",
        f"  Total Retries: {metrics.retry_count}",
        f"  Retry Rate: {metrics.retry_rate:.1%}",
        f"  Prerequisite Skip Attempts: {metrics.premature_access_attempts}",
        "",
    ]

    if metrics.exercise_success_rates:
        report.append("✏️  Exercise Success Rates:")
        for ex_id, rate in sorted(metrics.exercise_success_rates.items()):
            status = "✅" if rate >= MIN_EXERCISE_SUCCESS else "❌"
            report.append(f"  {status} {ex_id}: {rate:.1%}")
        report.append("")

    # Red flags
    red_flags = metrics.get_red_flags()
    if red_flags:
        report.append("🚩 RED FLAGS:")
        for flag in red_flags:
            report.append(f"  ⚠️  {flag}")
        report.append("")

        report.append("💡 RECOMMENDED ACTIONS:")
        if metrics.completion_rate < MIN_COMPLETION_RATE:
            report.append("  - Review prerequisites - may be missing foundational knowledge")
            report.append("  - Increase scaffolding level")
            report.append("  - Simplify content or split into multiple modules")

        if metrics.actual_time_median > MAX_TIME_MULTIPLIER * metrics.estimated_time_minutes:
            report.append("  - Reduce scope - module trying to teach too much")
            report.append("  - Add more examples and explanations")
            report.append("  - Update time estimate to match reality")

        if metrics.retry_rate > MAX_RETRY_RATE:
            report.append("  - Rewrite instructions for clarity")
            report.append("  - Add more examples and hints")
            report.append("  - Reduce exercise difficulty")

        for ex_id, rate in metrics.exercise_success_rates.items():
            if rate < MIN_EXERCISE_SUCCESS:
                report.append(f"  - Improve teaching of concept tested by {ex_id}")
                report.append("    → Add more examples")
                report.append("    → Increase practice opportunities")

        if metrics.premature_access_attempts > 50:
            report.append("  - Make prerequisites more visible in UI")
            report.append("  - Add prerequisite roadmap/graph")
    else:
        report.append("✅ No red flags detected - module performing well!")

    report.append(f"{'='*70}\n")

    return '\n'.join(report)


def format_summary_report(
    all_metrics: dict[int, ModuleMetrics],
    total_learners: int
) -> str:
    """Format overall summary report."""
    report = [
        f"\n{'='*70}",
        f"Learning System Analytics Summary",
        f"{'='*70}\n",
        f"Total Learners: {total_learners}",
        f"Total Modules: {len(all_metrics)}\n",
    ]

    # Count problem modules
    problem_modules = [
        (mid, m) for mid, m in all_metrics.items()
        if len(m.get_red_flags()) > 0
    ]

    if problem_modules:
        report.append(f"🚩 Modules with Issues: {len(problem_modules)}/{len(all_metrics)}\n")

        for module_id, metrics in sorted(problem_modules):
            flag_count = len(metrics.get_red_flags())
            report.append(
                f"  Module {module_id}: {metrics.title} "
                f"({flag_count} issue{'s' if flag_count > 1 else ''})"
            )

        report.append("\n📋 Priority Actions (ordered by impact):\n")

        # Sort by severity (completion rate is highest priority)
        severity_scores = []
        for module_id, metrics in problem_modules:
            score = 0
            if metrics.completion_rate < 0.50:
                score += 10  # Critical
            elif metrics.completion_rate < MIN_COMPLETION_RATE:
                score += 5   # High priority

            if metrics.retry_rate > 0.50:
                score += 8   # Critical
            elif metrics.retry_rate > MAX_RETRY_RATE:
                score += 4   # High priority

            severity_scores.append((score, module_id, metrics))

        for rank, (score, module_id, metrics) in enumerate(
            sorted(severity_scores, reverse=True)[:5], 1
        ):
            report.append(f"  {rank}. Module {module_id}: {metrics.title}")
            report.append(f"     Completion: {metrics.completion_rate:.1%}, Retry: {metrics.retry_rate:.1%}")

    else:
        report.append("✅ All modules performing within acceptable ranges!")

    report.append(f"\n{'='*70}\n")

    report.append("Run with --module <id> to see detailed analysis for specific modules.")

    return '\n'.join(report)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Analyze learner metrics to identify problem modules.'
    )

    parser.add_argument(
        '--data',
        type=str,
        required=True,
        help='Path to analytics JSON file'
    )

    parser.add_argument(
        '--module',
        type=int,
        help='Analyze specific module ID (default: all modules)'
    )

    args = parser.parse_args()

    try:
        data_path = Path(args.data)

        # Load analytics data
        print(f"📂 Loading analytics from: {data_path}")
        analytics = load_analytics_data(data_path)

        modules_info = analytics['modules']
        learner_data = analytics['learners']

        print(f"   Found {len(modules_info)} modules, {len(learner_data)} learners\n")

        # Calculate metrics
        all_metrics = {}

        for module_id_str, module_info in modules_info.items():
            module_id = int(module_id_str)
            metrics = calculate_module_metrics(module_id, module_info, learner_data)
            all_metrics[module_id] = metrics

        # Display reports
        if args.module is not None:
            # Single module report
            if args.module not in all_metrics:
                print(f"❌ Error: Module {args.module} not found in analytics", file=sys.stderr)
                return 1

            report = format_module_report(all_metrics[args.module])
            print(report)

        else:
            # Summary report for all modules
            report = format_summary_report(all_metrics, len(learner_data))
            print(report)

        return 0

    except FileNotFoundError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1

    except (json.JSONDecodeError, ValueError) as e:
        print(f"❌ Error parsing analytics file: {e}", file=sys.stderr)
        return 1

    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
