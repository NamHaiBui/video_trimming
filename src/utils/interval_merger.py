from typing import List

def merge_intervals(intervals:List[List[float]]) -> List[List[float]]:
    """
    Merge overlapping intervals.
    
    Args:
        intervals (List[List[int]]): List of intervals to merge.
        
    Returns:
        List[List[int]]: Merged intervals.
    """
    if not intervals:
        return []

    # Sort intervals by start time
    intervals.sort(key=lambda x: x[0])
    merged = [intervals[0]]
    for current in intervals[1:]:
        last_merged = merged[-1]
        if current[0] <= last_merged[1]:
            last_merged[1] = max(last_merged[1], current[1])
        else:
            merged.append(current)
    
    return merged
    