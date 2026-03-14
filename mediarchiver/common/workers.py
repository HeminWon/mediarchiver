import argparse
import os
from concurrent.futures import ThreadPoolExecutor

from tqdm import tqdm


def positive_int(value):
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("workers must be >= 1")
    return parsed


def resolve_worker_count(item_count, requested_workers=None, default_max_workers=4):
    if item_count <= 0:
        return 1
    cpu_count = os.cpu_count() or 1
    max_workers = default_max_workers if requested_workers is None else requested_workers
    return max(1, min(max_workers, cpu_count, item_count))


def map_with_workers(
    items,
    func,
    requested_workers=None,
    default_max_workers=4,
    progress_desc=None,
):
    if not items:
        return {}
    with ThreadPoolExecutor(
        max_workers=resolve_worker_count(
            len(items),
            requested_workers=requested_workers,
            default_max_workers=default_max_workers,
        )
    ) as executor:
        results_iter = executor.map(func, items)
        if progress_desc:
            results_iter = tqdm(results_iter, total=len(items), desc=progress_desc)
        return dict(zip(items, results_iter))
