"""Read-only checks of existing A/B data and report; never executes solvers."""
from pathlib import Path
import csv
import hashlib
import json
import math
import re
import statistics
import subprocess
from collections import Counter

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
REPORT = ROOT / "docs/AB_STAGE_REPORT_DRAFT_2026-10-28.md"
NOTE = ROOT / "docs/AB_REPORT_REVIEW_2026-10-28.md"

def read_json(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))

def read_csv(path):
    with (ROOT / path).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))

def sha(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()

def close(a, b):
    assert math.isclose(float(a), float(b), rel_tol=1e-12, abs_tol=1e-14), (a, b)

def key(row):
    return (str(row["job_id"]), int(row["n"]), row["mode"],
            int(row["processes"]), row["exchange"])

summary = read_json("evidence/ab_final_2026-10-28/summary.json")
scaling = read_json("evidence/ab_summary_2026-10-28/summary.json")
previous = read_json("evidence/ab_final_2026-10-28/final_review.json")
initial = read_json("evidence/ab_report_review_2026-10-28/initial_review.json")
snapshot = read_json("evidence/ab_report_review_2026-10-28/repository_files_before.json")
assert summary["status"] == scaling["status"] == previous["status"] == "PASS"
assert summary["completed_experiments"] == [1, 3, 2]
assert summary["main_performance"] == scaling["performance"]

main = summary["main_performance"]
main_map = {key(row): row for row in main}
csv_main = read_csv("evidence/ab_summary_2026-10-28/performance_comparison.csv")
samples = read_csv("evidence/ab_summary_2026-10-28/measurement_samples.csv")
assert len(main) == len(csv_main) == 45
assert len(samples) == 450
assert Counter(row["warmup"] for row in samples) == {"True": 45, "False": 405}
for row in main:
    selected = [r for r in samples if key(r) == key(row)]
    formal = [r for r in selected if r["warmup"] == "False"]
    assert len(selected) == 10 and len(formal) == 9
    assert sorted(int(r["repeat_index"]) for r in formal) == list(range(9))
    times = [float(r["compute_seconds"]) for r in formal]
    assert times == row["samples_seconds"]
    assert statistics.median(times) == row["median_seconds"]
    assert min(times) == row["min_seconds"] and max(times) == row["max_seconds"]
    close(statistics.stdev(times) / statistics.mean(times) * 100, row["sample_cv_percent"])
    own_serial = main_map[(row["job_id"], row["n"], "serial", 1, "none")]["median_seconds"]
    assert row["serial_baseline_seconds"] == own_serial
    close(own_serial / row["median_seconds"], row["serial_speedup"])
    close(row["serial_speedup"] / row["processes"], row["serial_efficiency"])
    if row["mode"] == "mpi":
        own_p1 = main_map[(row["job_id"], row["n"], "mpi", 1, row["exchange"])]["median_seconds"]
        assert row["mpi_p1_baseline_seconds"] == own_p1
        close(own_p1 / row["median_seconds"], row["mpi_speedup"])
        close(row["mpi_speedup"] / row["processes"], row["mpi_efficiency"])
for row in csv_main:
    original = main_map[key(row)]
    for column in ("median_seconds", "min_seconds", "max_seconds", "sample_cv_percent",
                   "serial_baseline_seconds", "serial_speedup", "serial_efficiency",
                   "mpi_p1_baseline_seconds", "mpi_speedup", "mpi_efficiency"):
        if original[column] is None:
            assert row[column] == ""
        else:
            assert float(row[column]) == original[column]

diagnostic = summary["wait_diagnostic_groups_data"]
diagnostic_map = {(r["n"], r["p"], r["exchange"]): r for r in diagnostic}
assert len(diagnostic) == 9
for row in diagnostic:
    times = row["samples_seconds"]
    assert len(times) == 5 and statistics.median(times) == row["median_seconds"]
    assert min(times) == row["min_seconds"] and max(times) == row["max_seconds"]
    close(statistics.stdev(times) / statistics.mean(times) * 100, row["sample_cv_percent"])
for row in read_csv("evidence/ab_final_2026-10-28/diagnostic_performance.csv"):
    original = diagnostic_map[(int(row["n"]), int(row["p"]), row["exchange"])]
    for column in ("median_seconds", "min_seconds", "max_seconds", "sample_cv_percent", "max_over_min"):
        assert float(row[column]) == original[column]
for row in summary["wait_diagnostic_comparisons"]:
    base = diagnostic_map[(row["n"], row["p"], row["baseline"])]
    candidate = diagnostic_map[(row["n"], row["p"], row["candidate"])]
    close(100 * (1 - candidate["median_seconds"] / base["median_seconds"]),
          row["ratio_of_medians_reduction_percent"])
    reductions = [100 * (1 - c / b) for b, c in zip(base["samples_seconds"], candidate["samples_seconds"])]
    assert reductions == row["round_reductions_percent"]
    assert statistics.median(reductions) == row["median_of_round_reductions_percent"]
    assert sum(c < b for b, c in zip(base["samples_seconds"], candidate["samples_seconds"])) == row["candidate_faster_rounds"]

text = REPORT.read_text(encoding="utf-8")
table_lines = [line for line in text.splitlines() if line.startswith("| ")]
table_values_checked = 0
for line in table_lines:
    cells = [cell.strip() for cell in line.strip("|").split("|")]
    if re.fullmatch(r"\d{7} / IN-\d+", cells[0]):
        job, host = cells[0].split(" / ")
        n = int(cells[1])
        serial = main_map[(job, n, "serial", 1, "none")]
        sr = main_map[(job, n, "mpi", 12, "sendrecv")]
        ov = main_map[(job, n, "mpi", 12, "overlap")]
        assert serial["host"] == host
        expected = [f"{serial['median_seconds']:.6f}"]
        expected += [f"{sr[field]:.{places}f} / {ov[field]:.{places}f}"
                     for field, places in (("median_seconds", 6), ("serial_speedup", 3), ("mpi_speedup", 3))]
        assert cells[2:] == expected, (cells, expected)
        table_values_checked += 7
    elif re.fullmatch(r"(1024|2048) / (2|12)", cells[0]):
        n, p = map(int, cells[0].split(" / "))
        expected = [f"{diagnostic_map[(n,p,e)]['median_seconds']:.6f}"
                    for e in ("sendrecv", "immediate", "overlap")]
        comparison = next(r for r in summary["wait_diagnostic_comparisons"]
                          if (r["n"],r["p"],r["baseline"],r["candidate"]) == (n,p,"immediate","overlap"))
        percent = f"{comparison['ratio_of_medians_reduction_percent']:+.2f}%".replace("-", "\u2212")
        expected += [percent, f"{comparison['candidate_faster_rounds']}/5"]
        assert cells[1:] == expected, (cells, expected)
        table_values_checked += 5
assert table_values_checked == 50

asym = read_csv("evidence/ab_summary_2026-10-28/asymmetric_validation.csv")
validation = read_csv("evidence/ab_final_2026-10-28/diagnostic_validation.csv")
assert len(asym) == 31
assert Counter(r["mode"] for r in asym) == {"serial": 7, "mpi": 24}
assert max(float(r["independent_grid_max_difference"]) for r in asym) == 8.881784197001252e-16
asym_stops = [r for r in asym if int(r["n"]) == 7 and float(r["tolerance"]) > 0]
assert len(asym_stops) == 7 and {int(r["iterations"]) for r in asym_stops} == {330}
assert {float(r["max_error"]) for r in asym_stops} == {1.2454925979454856e-11}
assert {float(r["residual_inf"]) for r in asym_stops} == {2.519300323911011e-10}
assert len(validation) == 45
assert Counter(r["kind"] for r in validation) == {"original": 18, "diagnostic": 27}
full = [r for r in validation if r["full_grid_max_difference"] != ""]
assert len(full) == 35 and len(validation) - len(full) == 10
assert max(float(r["full_grid_max_difference"]) for r in full) == 2.220446049250313e-16
stops = [r for r in validation if int(r["n"]) == 7 and float(r["tolerance"]) > 0]
assert len(stops) == 5 and {int(r["iterations"]) for r in stops} == {324}
assert {float(r["max_error"]) for r in stops} == {1.1444623027045964e-11}
assert {float(r["residual_inf"]) for r in stops} == {2.3145219074649503e-10}
assert summary["total_structured_validation_numerical"] == 352 + len(asym) + len(validation) == 428
assert summary["total_structured_full_grid_executions"] == 172 + len(asym) + len(full) == 238
assert summary["total_expected_rejections"] == 16
assert summary["total_performance_executions"] == 450 + 54 == 504
assert summary["total_performance_formal_samples"] == 405 + 45 == 450

comm = read_csv("evidence/ab_summary_2026-10-28/communication_comparison.csv")
for job, shown in (("1500222", "16.61"), ("1501884", "14.01")):
    row = next(r for r in comm if r["job_id"] == job and int(r["n"]) == 2048 and int(r["processes"]) == 2)
    assert f"{float(row['ratio_of_medians_reduction_percent']):.2f}" == shown

# Confirm preservation of every pre-existing file, not only tracked Git files.
changed = []
missing = []
for relative, old in snapshot.items():
    path = ROOT / relative
    if not path.is_file():
        missing.append(relative)
    elif path.stat().st_size != old["bytes"] or sha(path) != old["sha256"]:
        changed.append(relative)
assert not missing, missing
assert changed == ["docs/AB_STAGE_REPORT_DRAFT_2026-10-28.md"], changed
backup = OUT / "stage_report_before_editorial_review.md"
assert sha(backup) == initial["backup_sha256"] == previous["reviewed_file_sha256"]["docs/AB_STAGE_REPORT_DRAFT_2026-10-28.md"]
assert len(previous["raw_archives"]) == 7
assert sum(r["files"] for r in previous["raw_archives"]) == 2271
for archive in previous["raw_archives"]:
    assert snapshot[archive["path"]]["sha256"] == archive["sha256"]
    assert sha(ROOT / archive["path"]) == archive["sha256"]

head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
assert head == initial["git_head_before"]
old_status = set((OUT / "git_status_before.txt").read_text(encoding="utf-8").splitlines())
new_status_text = subprocess.check_output(["git", "status", "--porcelain=v1", "-uall"],
                                        cwd=ROOT, text=True, encoding="utf-8")
new_status = set(new_status_text.splitlines())
assert not (old_status - new_status), sorted(old_status - new_status)
(OUT / "git_status_after.txt").write_text(new_status_text, encoding="utf-8")

links = []
for document in (REPORT, NOTE):
    contents = document.read_text(encoding="utf-8")
    assert "\ufffd" not in contents
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", contents):
        if "://" in target or target.startswith("#"):
            continue
        path = (document.parent / target.split("#")[0]).resolve()
        assert path.is_file() or path == (OUT / "review_checks.json"), (document, target)
        links.append(path)
old_text = backup.read_text(encoding="utf-8")
def prose_words(value):
    return len("\n".join(line for line in value.splitlines() if not line.startswith("|")).split())
result = {
    "status": "PASS",
    "date": "2026-10-28",
    "scope": "Local document/data checks only; no solver execution or new experiment",
    "report": REPORT.relative_to(ROOT).as_posix(),
    "report_sha256": sha(REPORT),
    "report_backup_sha256": sha(backup),
    "review_note_sha256": sha(NOTE),
    "scaling_groups_recomputed": 45,
    "scaling_execution_records_cross_checked": 450,
    "diagnostic_groups_recomputed": 9,
    "diagnostic_comparisons_recomputed": 9,
    "main_report_numeric_table_entries_checked": table_values_checked,
    "asymmetric_validation_records_checked": 31,
    "diagnostic_validation_records_checked": 45,
    "markdown_local_links_checked": len(links),
    "preexisting_files": len(snapshot),
    "unchanged_preexisting_files": len(snapshot) - len(changed),
    "changed_preexisting_files": changed,
    "missing_preexisting_files": missing,
    "archive_sha256_rechecked": 7,
    "historical_member_audit_record": {"files":2271, "member_audit_repeated_this_turn":False},
    "plot_review": {
        "visually_reviewed_this_turn": [
            "evidence/ab_summary_2026-10-28/round_times.png",
            "evidence/ab_summary_2026-10-28/dual_scale_scaling.png",
            "evidence/ab_summary_2026-10-28/historical_context.png",
            "evidence/vanda_1502229_mpi_wait/round_times.png"],
        "round_trace_scope": "1501884 shows serial and P1/4/12, not P2; all nine rounds of displayed configurations.",
        "figures_modified": False},
    "word_count_method": "Whitespace tokens; prose excludes Markdown table rows.",
    "words_before": len(old_text.split()),
    "words_after": len(text.split()),
    "prose_words_before": prose_words(old_text),
    "prose_words_after": prose_words(text),
    "prose_reduction_percent": 100 * (1 - prose_words(text)/prose_words(old_text)),
    "git_head_unchanged": True,
    "preexisting_git_status_entries_preserved": True,
    "git_committed_or_pushed": False,
    "email_sent": False,
    "human_confirmation": "Names/IDs, actual contributions, individual understanding, final review remain pending."
}
(OUT / "review_checks.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
assert all(path.is_file() for path in links)
print(json.dumps({k:result[k] for k in (
    "status","main_report_numeric_table_entries_checked","unchanged_preexisting_files",
    "changed_preexisting_files","archive_sha256_rechecked","markdown_local_links_checked",
    "words_before","words_after","prose_words_before","prose_words_after","prose_reduction_percent"
)}, ensure_ascii=False))
