#!/usr/bin/env python3
"""Replay bound semantic measurements; recompute all program evidence and V3 settlement."""
import hashlib
import json
import os
import subprocess
import tempfile
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def main():
    artifact = Path(sys.argv[1])
    if artifact.is_dir():
        artifact = artifact / "门店客流变化归因说明.xlsx"
    if not artifact.is_file() or not artifact.stat().st_size:
        return {"strict_score": 0.0, "reward_strict": 0.0,
                "rewards": {"strict": 0.0}, "reason": "Missing required workbook"}
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    frozen_policy = json.loads((HERE / "frozen_owner_policy.json").read_text())
    if digest in frozen_policy["artifacts"]:
        measured = frozen_policy["artifacts"][digest]
        return {"strict_score": measured["reward"], "reward_strict": measured["reward"],
                "rewards": {"strict": measured["reward"]}, "artifact_sha256": digest,
                "replay_mode": "frozen-owner-ledger-exact-policy", "policy_version": frozen_policy["policy_version"],
                "matrix_sha256": frozen_policy["matrix_sha256"], "completion": measured["completion"],
                "reward_fraction": measured["reward_fraction"], "historical_rewards_overwritten": False}
    try:
        from openpyxl import load_workbook
        physical = load_workbook(artifact, read_only=True, data_only=False)
        physical.close()
    except Exception as error:
        return {"strict_score": 0.0, "reward_strict": 0.0,
                "rewards": {"strict": 0.0}, "reason": "Required workbook is physically unreadable",
                "physical_error": type(error).__name__}
    from program_judge import score
    from bound_cache import load_recorded
    from fresh_owner_policy import settle_owner
    mode = os.environ.get("LLM_JUDGE_MODE", "replay")
    if mode == "replay":
        record = load_recorded(artifact, HERE / "semantic-cache", HERE, recorded_version=True)
    elif mode == "fresh":
        manifest = json.loads((HERE / "semantic-cache/manifest.json").read_text())
        for name, expected in manifest["runtime_sha256"].items():
            if hashlib.sha256((HERE / name).read_bytes()).hexdigest() != expected:
                raise ValueError("Runtime/source binding mismatch: " + name)
        output = Path(os.environ.get("LLM_JUDGE_OUTPUT_DIR") or tempfile.mkdtemp(prefix="restaurant-fresh-"))
        cache = Path(os.environ.get("LLM_JUDGE_CACHE_DIR", str(HERE / "llm_judge/cache")))
        command = [sys.executable, str(HERE / "llm_judge/judge.py"), "--mode", "fresh", "--refresh",
                   "--artifact", str(artifact), "--output", str(output), "--cache-dir", str(cache)]
        run = subprocess.run(command, capture_output=True, text=True)
        if run.returncode:
            raise RuntimeError("Fresh semantic judge failed: " + run.stderr[-1200:])
        record = json.loads((output / "llm_judge_result.json").read_text())
        if record["artifact_sha256"] != digest:
            raise ValueError("Fresh semantic artifact binding mismatch")
    else:
        raise ValueError("LLM_JUDGE_MODE must be replay or fresh")
    decision = record["decision"]
    detail = score(artifact, decision)
    detail["semantic_items"] = {
        key: item["completion"] for key, item in decision["items"].items()
    }
    calibrated = settle_owner(artifact, detail)
    reward = 0.0 if detail["evaluator_instruction_adoption"] else calibrated["reward_strict"]
    detail.update(strict_score=reward, reward_strict=reward, rewards={"strict": reward},
                  calibrated_settlement=calibrated, replay_mode=("bound-semantic-program-recompute" if mode == "replay" else "actual-fresh-semantic-program-recompute"),
                  semantic_measurement=record,
                  artifact_sha256=digest, semantic_context_sha256=record["context_sha256"])
    return detail


if __name__ == "__main__":
    try:
        print(json.dumps(main(), ensure_ascii=False))
    except Exception as error:
        print(json.dumps({"judge_error": str(error), "status": "PENDING_JUDGE_ERROR"}))
        raise SystemExit(1)
