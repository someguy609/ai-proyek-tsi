def count_objects_in_regions(result, regions, counts):
    """
    result: a single ultralytics result object (the item yielded by model.track)
    regions: list of dicts with 'name', 'x1', 'y1', 'x2', 'y2', 'type' ('box' or 'line')
    counts: running mapping for counting:
            { region_name: { class_label: {'entered': set(ids), 'count': int}, ... }, ... }
    returns: updated counts (same structure)
    """
    if counts is None:
        counts = {}

    # Initialize previous positions tracking if not exists
    if 'previous_positions' not in counts:
        counts['previous_positions'] = {}

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

    # ensure every region has an entry
    for region in regions:
        rname = region['name']
        counts.setdefault(rname, {})
        if class_list:
            for cname in class_list:
                counts[rname].setdefault(cname, {'entered': set(), 'count': 0})

    try:
        boxes = result.boxes.xyxy.tolist()
        classes = result.boxes.cls.tolist()
        ids = result.boxes.id.tolist()
    except Exception:
        # no detections -> return counts unchanged
        return counts

    # Current positions of all tracks
    current_positions = {}
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

        track_id = int(id_)
        current_positions[track_id] = {
            'center': (cx, cy),
            'class': cls_name
        }

    # Process each region
    for region in regions:
        rname = region['name']
        region_type = region.get('type', 'box')

        if region_type == 'box':
            # Box logic: count entries into the area
            current_in_box = {}
            for track_id, pos in current_positions.items():
                cx, cy = pos['center']
                rx1, ry1, rx2, ry2 = region['x1'], region['y1'], region['x2'], region['y2']
                if rx1 <= cx <= rx2 and ry1 <= cy <= ry2:
                    cls_name = pos['class']
                    if cls_name not in current_in_box:
                        current_in_box[cls_name] = set()
                    current_in_box[cls_name].add(track_id)

            # Count new entries per class
            for cls_name, track_ids in current_in_box.items():
                if cls_name not in counts[rname]:
                    counts[rname][cls_name] = {'entered': set(), 'count': 0}

                entered_set = counts[rname][cls_name]['entered']
                new_entries = track_ids - entered_set
                counts[rname][cls_name]['count'] += len(new_entries)
                entered_set.update(new_entries)

        elif region_type == 'line':
            # Line logic: count crossings
            # Line from (x1,y1) to (x2,y2) - we'll count crossings from left to right
            x1, y1, x2, y2 = region['x1'], region['y1'], region['x2'], region['y2']

            # Determine line orientation and crossing direction
            if abs(x2 - x1) > abs(y2 - y1):  # horizontal line
                is_horizontal = True
                crossing_threshold = min(x1, x2) + abs(x2 - x1) / 2  # middle of line
            else:  # vertical line
                is_horizontal = False
                crossing_threshold = min(y1, y2) + abs(y2 - y1) / 2

            for track_id, pos in current_positions.items():
                cx, cy = pos['center']
                cls_name = pos['class']

                if cls_name not in counts[rname]:
                    counts[rname][cls_name] = {'entered': set(), 'count': 0}

                # Check if this track crossed the line
                prev_pos = counts['previous_positions'].get(track_id)
                if prev_pos is None:
                    counts['previous_positions'][track_id] = (cx, cy)
                    continue

                prev_cx, prev_cy = prev_pos
                current_side = cx if is_horizontal else cy
                prev_side = prev_cx if is_horizontal else prev_cy

                # Check for crossing (one side to other side of threshold)
                if ((prev_side < crossing_threshold and current_side >= crossing_threshold) or
                    (prev_side > crossing_threshold and current_side <= crossing_threshold)):
                    # Check if track hasn't already been counted for this crossing
                    if track_id not in counts[rname][cls_name]['entered']:
                        counts[rname][cls_name]['count'] += 1
                        counts[rname][cls_name]['entered'].add(track_id)

                # Update previous position
                counts['previous_positions'][track_id] = (cx, cy)

    return counts
