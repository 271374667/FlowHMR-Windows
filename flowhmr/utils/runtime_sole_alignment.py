"""Level the feet on sustained flat support before the existing contact IK."""

import numpy as np
from scipy.spatial.transform import Rotation

from .runtime_capabilities import SOLE_FIT_REFERENCE_STRENGTH


def level_support_ankles(rest, roots, quats, probes, probabilities, fps, plan, *, strength=SOLE_FIT_REFERENCE_STRENGTH):
    """Return ankle targets and the spans that can safely use them.

    A single heel/toe signal, a large tilt, or a fast roll may be an intentional
    pivot. Only correct moderate, sustained two-point contacts inside a stance.
    """
    from rgbmocap_correction.correction import fk, intervals

    n = len(quats)
    desired = quats.copy()
    applied = np.zeros((n, 2), dtype=bool)
    if strength <= 0:
        return desired, applied
    _, world = fk(rest, roots, quats)
    _, _, _, _, floor, segments = plan
    heel_to_toe = probes[:, 1::2] - probes[:, ::2]
    both = probabilities.reshape(n, 2, 2).min(axis=2) >= 0.65
    reference = SOLE_FIT_REFERENCE_STRENGTH
    scale = min(strength / reference, 1.0)
    boost = max(0.0, (strength - reference) / (1 - reference))
    guard = max(1, round((0.07 - 0.03 * boost) * fps))
    fade = max(2, round(0.10 * fps))
    minimum = max(2 * fade + 1, round(0.22 * fps))
    max_gap = 0.04 + 0.012 * boost
    min_up = np.cos(np.deg2rad(15 + 5 * boost))

    for foot, (knee, ankle) in enumerate(((4, 7), (5, 8))):
        line = heel_to_toe[:, foot].astype(np.float64)
        heading = line.copy()
        heading[:, 1] = 0
        span = np.linalg.norm(heading, axis=1)
        heading /= np.maximum(span[:, None], 1e-8)
        forward = line / np.maximum(np.linalg.norm(line, axis=1, keepdims=True), 1e-8)
        side = world[:, ankle, :, 0]
        side = side - (side * forward).sum(axis=1, keepdims=True) * forward
        side /= np.maximum(np.linalg.norm(side, axis=1, keepdims=True), 1e-8)
        normal = np.cross(forward, side)
        gap = line[:, 1]
        gap_rate = np.abs(np.diff(gap, prepend=gap[0])) * fps
        gap_rate[:-1] = np.maximum(gap_rate[:-1], gap_rate[1:])
        lower = probes[:, 2 * foot:2 * foot + 2, 1].min(axis=1)
        candidate = (both[:, foot] & (span > 0.05) & (np.abs(gap) < max_gap)
                     & (gap_rate < 0.22) & (normal[:, 1] > min_up)
                     & (np.abs(lower - floor) < 0.12))
        up = np.broadcast_to([0., 1., 0.], heading.shape)
        target = np.stack((np.cross(up, heading), up, heading), axis=-1)
        source = np.stack((side, normal, forward), axis=-1)

        for segment in segments:
            if segment["foot"] != foot:
                continue
            first, end = segment["start"] + guard, segment["end"] - guard
            if end - first < minimum:
                continue
            for left, right in intervals(candidate[first:end]):
                count = right - left
                if count < minimum:
                    continue
                window = slice(first + left, first + right)
                # Keep the projected toe direction while leveling pitch and roll.
                delta = target[window] @ source[window].swapaxes(-2, -1)
                vector = Rotation.from_matrix(delta).as_rotvec()
                if np.linalg.norm(vector, axis=1).max() < np.deg2rad(0.5):
                    continue
                phase = np.clip(np.minimum(np.arange(1, count + 1), np.arange(count, 0, -1))
                                / (fade + 1), 0, 1)
                weight = phase * phase * (3 - 2 * phase)
                # Above the reference, settle sooner without rotating past the
                # level target. Keep two-point confidence and the roll guard.
                weight = scale * (weight + boost * weight * (1 - weight))
                ankle_world = Rotation.from_rotvec(vector * weight[:, None]).as_matrix() @ world[window, ankle]
                local = world[window, knee].swapaxes(-2, -1) @ ankle_world
                desired[window, ankle] = Rotation.from_matrix(local).as_quat()[:, [3, 0, 1, 2]]
                applied[window, foot] = True

    return desired, applied


def _fit_remaining_pitch(rest, roots, quats, probes, applied, fps, boost):
    """Close the remaining heel/toe gap measured on the actual skinned foot."""
    from rgbmocap_correction.correction import fk, intervals

    _, world = fk(rest, roots, quats)
    refined = quats.copy()
    adjusted = np.zeros_like(applied)
    fade = max(2, round(0.10 * fps))
    for foot, (knee, ankle) in enumerate(((4, 7), (5, 8))):
        delta = (probes[:, 2 * foot + 1] - probes[:, 2 * foot]).astype(np.float64)
        span = np.linalg.norm(delta[:, [0, 2]], axis=1)
        axis = np.stack((delta[:, 2], np.zeros(len(delta)), -delta[:, 0]), axis=1)
        axis /= np.maximum(span[:, None], 1e-8)
        # Keep half a millimetre of clearance in the estimate. The lowest
        # skin vertices can change as the foot rotates, so leave a margin.
        error = np.sign(delta[:, 1]) * np.maximum(np.abs(delta[:, 1]) - 0.0005, 0)
        pitch = np.clip(np.arctan2(error, np.maximum(span, 0.05)), -np.deg2rad(6), np.deg2rad(6))
        for start, end in intervals(applied[:, foot]):
            window = slice(start, end)
            count = end - start
            phase = np.minimum(np.minimum(np.arange(1, count + 1), np.arange(count, 0, -1)) / (fade + 1), 1)
            weight = 0.85 * boost * phase * phase * (3 - 2 * phase)
            if not np.any(pitch[window]):
                continue
            rotation = Rotation.from_rotvec(axis[window] * (pitch[window] * weight)[:, None]).as_matrix()
            local = world[window, knee].swapaxes(-2, -1) @ rotation @ world[window, ankle]
            refined[window, ankle] = Rotation.from_matrix(local).as_quat()[:, [3, 0, 1, 2]]
            adjusted[window, foot] = True
    return refined, adjusted


def _keep_contact_timing(original, desired, applied, active, evaluate, fps):
    """Revert any proposed spans that would change the contact mask."""
    from rgbmocap_correction.correction import intervals

    if applied.any():
        fitted, fitted_plan = evaluate(desired)
        changed = (active != fitted_plan[0]).any(axis=1)
        if changed.any():
            # Revert entire fades near a timing change instead of cutting an
            # ankle adjustment mid-stance. Fall back if the change persists.
            margin = max(2, round(0.15 * fps))
            for foot, ankle in enumerate((7, 8)):
                for start, end in intervals(applied[:, foot]):
                    if changed[max(0, start - margin):end + margin].any():
                        desired[start:end, ankle] = original[start:end, ankle]
                        applied[start:end, foot] = False
            if applied.any():
                fitted, fitted_plan = evaluate(desired)
        if applied.any() and np.array_equal(active, fitted_plan[0]):
            return fitted, fitted_plan
    return None


def fit_sole_input(rest, roots, quats, probes, probabilities, fps, plan, evaluate, *, strength=SOLE_FIT_REFERENCE_STRENGTH):
    """Level stable contacts without changing the solver's stance timing."""
    desired, applied = level_support_ankles(rest, roots, quats, probes, probabilities, fps, plan, strength=strength)
    fit = _keep_contact_timing(quats, desired, applied, plan[0], evaluate, fps)
    if fit is None:
        applied.fill(False)
        return quats, probes, plan, applied
    fitted, fitted_plan = fit

    reference = SOLE_FIT_REFERENCE_STRENGTH
    if strength > reference:
        boost = (strength - reference) / (1 - reference)
        refined, adjusted = _fit_remaining_pitch(rest, roots, desired, fitted, applied, fps, boost)
        refinement = _keep_contact_timing(desired, refined, adjusted, plan[0], evaluate, fps)
        if refinement is not None:
            desired = refined
            fitted, fitted_plan = refinement
    return desired, fitted, fitted_plan, applied
