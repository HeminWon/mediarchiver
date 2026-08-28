from tqdm import tqdm


def map_with_progress(items, func, progress_desc=None):
    if not items:
        return {}
    if progress_desc:
        results = {}
        with tqdm(total=len(items), desc=progress_desc) as progress:
            for item in items:
                results[item] = func(item)
                progress.update(1)
        return results
    return {item: func(item) for item in items}
