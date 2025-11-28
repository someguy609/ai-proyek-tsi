def count_objects_in_regions(result, regions):
    """
    result: a single ultralytics result object (the item yielded by model.track)
    regions: list of dicts: {'name': 'zone1', 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}
    returns: { region_name: { class_label: count, ... }, ... }
    """
    names = getattr(result, "names", None)

    counts = {region['name']: {} for region in regions}

    try:
        boxes = result.boxes.xyxy.tolist()
        classes = result.boxes.cls.tolist()
    except Exception:
        return counts

    for box, cls in zip(boxes, classes):
        x1, y1, x2, y2 = box
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        cls_idx = int(cls)
        cls_name = names[cls_idx] if (names and cls_idx in names) else str(cls_idx)

        for region in regions:
            rx1, ry1, rx2, ry2 = region['x1'], region['y1'], region['x2'], region['y2']
            if rx1 <= cx <= rx2 and ry1 <= cy <= ry2:
                counts_region = counts[region['name']]
                counts_region[cls_name] = counts_region.get(cls_name, 0) + 1

    return counts