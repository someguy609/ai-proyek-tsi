def count_objects_in_regions(result, regions, counts):
    """
    result: a single ultralytics result object (the item yielded by model.track)
    regions: list of dicts: {'name': 'zone1', 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2}
    counts: running mapping preserved between frames:
            { region_name: { class_label: set(ids), ... }, ... }
    returns: updated counts (same structure)
    """
    if counts is None:
        counts = {}

    # resolve class names mapping from model (if available)
    names = getattr(result, "names", None)
    if names:
        # names can be dict or list-like
        try:
            class_list = list(names.values()) if isinstance(names, dict) else list(names)
        except Exception:
            class_list = None
    else:
        class_list = None

    # ensure every region has an entry and every known class exists with an empty set
    for region in regions:
        rname = region['name']
        counts.setdefault(rname, {})
        if class_list:
            for cname in class_list:
                counts[rname].setdefault(cname, set())

    try:
        boxes = result.boxes.xyxy.tolist()
        classes = result.boxes.cls.tolist()
        ids = result.boxes.id.tolist()
    except Exception:
        # no detections -> return counts with zeroed classes preserved
        return counts

    for box, cls, id_ in zip(boxes, classes, ids):
        x1, y1, x2, y2 = box
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        cls_idx = int(cls)
        if names:
            try:
                cls_name = names[cls_idx] if isinstance(names, (list, tuple)) else names.get(cls_idx, str(cls_idx))
            except Exception:
                cls_name = str(cls_idx)
        else:
            cls_name = str(cls_idx)

        for region in regions:
            rx1, ry1, rx2, ry2 = region['x1'], region['y1'], region['x2'], region['y2']
            if rx1 <= cx <= rx2 and ry1 <= cy <= ry2:
                rname = region['name']
                counts.setdefault(rname, {})
                counts[rname].setdefault(cls_name, set())
                try:
                    counts[rname][cls_name].add(int(id_))
                except Exception:
                    # ignore malformed id
                    pass

    return counts