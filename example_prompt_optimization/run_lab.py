"""Main Lab Runner for the OpenEvolve Prompt Optimization Lab.

Runnable from any shell with zero Google3 dependencies:
  export OPENAI_COMPATIBLE_API_KEY="your-api-key"
  python3 run_lab.py --iterations 20 --output-dir run_with_artifacts

Supports hands-on lab flags:
  --no-artifacts          Disable diagnostic failure-case artifacts (Exercise 2 ablation)
  --feature-dims D1 D2    Override MAP-Elites feature dimensions (Exercise 3 exploration)
"""

import argparse
import importlib.util
import os
import sys

# Auto-discover openevolve from pip or local repo path
_LOCAL_OE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../../third_party/py/openevolve")
)
try:
    import openevolve  # noqa: F401
except ImportError:
    if os.path.exists(os.path.join(_LOCAL_OE, "__init__.py")):
        spec = importlib.util.spec_from_file_location(
            "openevolve",
            os.path.join(_LOCAL_OE, "__init__.py"),
            submodule_search_locations=[_LOCAL_OE],
        )
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            sys.modules["openevolve"] = mod
            try:
                spec.loader.exec_module(mod)
            except ImportError:
                sys.modules.pop("openevolve", None)

try:
    from openevolve.api import run_evolution
    from openevolve.config import load_config
except ImportError:
    run_evolution = None  # type: ignore[assignment]
    load_config = None  # type: ignore[assignment]

from evaluator import evaluate
from test_harness import _print_comparison_report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run OpenEvolve Prompt Optimization Lab (Live Gemini API)"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=20,
        help="Number of evolutionary iterations (default: 20)",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to OpenEvolve YAML configuration file",
    )
    parser.add_argument(
        "--initial-program",
        type=str,
        default="initial_program.py",
        help="Path to initial baseline prompt program",
    )
    parser.add_argument(
        "--evaluator",
        type=str,
        default="evaluator.py",
        help="Path to evaluator script",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="lab_output",
        help="Directory to store checkpoints, logs, and best evolved prompt",
    )
    parser.add_argument(
        "--no-artifacts",
        action="store_true",
        help="Disable diagnostic failure artifacts in mutation prompts (Exercise 2 ablation)",
    )
    parser.add_argument(
        "--feature-dims",
        nargs="+",
        metavar="DIM",
        help="Override MAP-Elites feature dimensions (e.g. --feature-dims prompt_char_length label_f1)",
    )
    args = parser.parse_args()

    if run_evolution is None or load_config is None:
        print(
            "ERROR: `openevolve` is not installed in the current Python environment.\n"
            "Please install the standalone lab dependencies first:\n"
            "  pip install -r requirements.txt",
            file=sys.stderr,
        )
        sys.exit(1)

    if not os.environ.get("OPENAI_COMPATIBLE_API_KEY"):
        print(
            "ERROR: OPENAI_COMPATIBLE_API_KEY is not set in your shell environment.\n"
            "Please export your API key before launching evolution:\n"
            "  export OPENAI_COMPATIBLE_API_KEY='your-api-key'",
            file=sys.stderr,
        )
        sys.exit(1)

    config_obj = load_config(args.config)
    if args.no_artifacts:
        config_obj.prompt.include_artifacts = False
    if args.feature_dims:
        config_obj.database.feature_dimensions = list(args.feature_dims)

    print("=" * 74)
    print("OPENEVOLVE PROMPT OPTIMIZATION LAB")
    print(f"  Initial Program      : {args.initial_program}")
    print(f"  Evaluator            : {args.evaluator}")
    print(f"  Iterations           : {args.iterations}")
    print(f"  Artifact Feedback    : {config_obj.prompt.include_artifacts}")
    print(f"  MAP-Elites Features  : {config_obj.database.feature_dimensions}")
    print(f"  Output Directory     : {args.output_dir}")
    print("=" * 74)

    result = run_evolution(
        initial_program=args.initial_program,
        evaluator=args.evaluator,
        config=config_obj,
        iterations=args.iterations,
        output_dir=args.output_dir,
        cleanup=False,
    )

    os.makedirs(args.output_dir, exist_ok=True)
    best_program_path = os.path.join(args.output_dir, "best_program.py")
    with open(best_program_path, "w", encoding="utf-8") as f:
        f.write(result.best_code)

    print("\n" + "=" * 74)
    print("EVOLUTION COMPLETE!")
    print(f"  Best Combined Score : {result.best_score:.4f}")
    print(f"  Saved Best Program  : {best_program_path}")
    print("=" * 74)

    # Evaluate baseline vs evolved side-by-side
    print("\nRunning final side-by-side verification on full 18-ticket benchmark...")
    base_res = evaluate(args.initial_program)
    best_res = evaluate(best_program_path)
    _print_comparison_report(args.initial_program, base_res, best_program_path, best_res)


if __name__ == "__main__":
    main()
