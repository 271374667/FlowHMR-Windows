"""Shared CLI/Web adapter for RGBMocap's native SMPL-H correction pipeline."""

import copy
import time

import numpy as np
import torch
from scipy.spatial.transform import Rotation

from flowhmr.core.math.geometry import rot6d_to_rotation_matrix


class PostprocessPipeline:
    """Run RGBMocap's flat-ground contact correction on the CPU."""

    def __init__(self, body_model, smpl_mesh):
        try:
            from rgbmocap_correction.correction import backend
            from rgbmocap_correction.correction_settings import correction_options
        except ImportError as exc:
            raise ImportError(
                "Post-processing requires RGBMocapCorrection and KimodoMotionCorrection. "
                "Install ./third_party/RGBMocapCorrection and "
                "./third_party/KimodoMotionCorrection; see docs/install.md."
            ) from exc
        try:
            native = backend()
        except ImportError as exc:
            raise ImportError("Build KimodoMotionCorrection first; see docs/install.md.") from exc
        if getattr(native, "rgb_mocap_anatomical_version", 0) != 1:
            raise RuntimeError("Reinstall the bundled KimodoMotionCorrection with anatomical IK support")
        if body_model is None or smpl_mesh is None:
            raise ValueError("Post-processing requires the SMPL-H skeleton and mesh")
        self.body_model = body_model
        self.smpl_mesh = smpl_mesh
        self._mesh_cpu = copy.deepcopy(smpl_mesh).cpu().float().eval()
        self._correction_options = correction_options
        self.configure()

    @classmethod
    def default(cls, body_model=None, smpl_mesh=None):
        return cls(body_model, smpl_mesh)

    def configure(self, height_m=None, *, preset="normal", sole_fit_strength=0.0):
        self.options = self._correction_options({"auto_floor": height_m is None, "floor": height_m, "preset": preset})
        self.sole_fit_strength = sole_fit_strength
        self.last_report = None

    @torch.no_grad()
    def run(self, output: dict, *, cancel_check=None, **kwargs) -> dict:
        from rgbmocap_correction.correction import correct_arrays, prepare_contacts, sole_metrics
        from rgbmocap_correction.flow_correction import SoleGeometry, contact_probabilities
        from rgbmocap_correction.flow_export import proper_rotations
        from rgbmocap_correction.hand_lock import apply as apply_hands

        started = time.perf_counter()
        check = cancel_check or (lambda: None)
        check()
        rot6d, trans, shapes = output["rot6d"], output["trans"], output["shapes"]
        if rot6d.ndim != 4 or rot6d.shape[0] != 1 or rot6d.shape[2:] != (52, 6):
            raise ValueError("Expected SMPL-H rotations (1, T, 52, 6)")
        length = rot6d.shape[1]
        if length == 0 or trans.shape != (1, length, 3) or shapes.shape != (1, 1, 16):
            raise ValueError("Expected nonempty trans (1, T, 3) and shapes (1, 1, 16)")
        contacts = output.get("foot_contacts")
        if contacts is None or contacts.shape != (1, length, 4):
            raise ValueError("Expected foot_contacts (1, T, 4): left ankle/toe, right ankle/toe")
        if not all(torch.isfinite(value).all().item() for value in (rot6d, trans, shapes, contacts)):
            raise ValueError("Post-processing inputs must be finite")

        # Match mocap/flow_correction.py: native shaped SMPL-H, four sole probes,
        # orthonormalized body rotations and pelvis positions (not SMPL trans).
        geometry = SoleGeometry(self._mesh_cpu, shapes.detach().float().cpu().reshape(1, 16))
        body_rot6d_cpu = rot6d[0, :, :22].detach().float().cpu()
        local = proper_rotations(rot6d_to_rotation_matrix(body_rot6d_cpu).numpy())
        quats = Rotation.from_matrix(local.reshape(-1, 3, 3)).as_quat()
        quats = quats.reshape(length, 22, 4)[..., [3, 0, 1, 2]].astype(np.float32)
        roots = trans[0].float().cpu().numpy() + geometry.rest[0]
        probabilities = contact_probabilities({"foot_contacts": contacts.detach().float().cpu()}, length)
        def sample(positions, rotations):
            values = np.empty((length, 4, 3), np.float32)
            for start in range(0, length, 128):
                check()
                values[start:start + 128] = geometry.sample(positions[start:start + 128], rotations[start:start + 128])[0]
            return values

        probes = sample(roots, quats)

        options = self.options
        fps = float(kwargs.get("fps", 30.0))
        floor = None if options["auto_floor"] else options["floor"]
        ranges = None if options["foot_lock"] else [[], []]

        def plan_contacts(values, height):
            return prepare_contacts(values, probabilities, fps, height, options["preset"], ranges, options["mode"])

        source_probes = probes
        plan = fitted = None
        if self.sole_fit_strength > 0 and options["foot_lock"] and options["mode"] == "flat":
            from .runtime_sole_alignment import fit_sole_input

            plan = plan_contacts(probes, floor)
            contact_floor = plan[4]

            def evaluate(candidate):
                values = sample(roots, candidate)
                return values, plan_contacts(values, contact_floor)

            quats, probes, plan, fitted = fit_sole_input(
                geometry.rest[:22], roots, quats, probes, probabilities, fps, plan, evaluate,
                strength=self.sole_fit_strength,
            )
            if fitted.any():
                floor = contact_floor

        fixed_roots, fixed_quats, report = correct_arrays(
            geometry.rest[:22], roots, quats, probes, probabilities, fps, floor,
            preset=options["preset"], contact_ranges=ranges,
            pelvis_offset=options["pelvis_offset"], mode=options["mode"], emit=lambda *args, **kw: check(),
            foot_enabled=options["foot_lock"],
        )
        report["hand_lock"] = apply_hands(
            geometry.rest[:22], roots, quats, fixed_roots, fixed_quats,
            geometry.palm_offsets, fps, options["mode"], report["floor"],
            options["preset"], None, options["hand_lock"],
        )
        report["warning"] = " ".join(filter(None, (report["warning"], report["hand_lock"]["warning"])))
        if not np.isfinite(fixed_roots).all() or not np.isfinite(fixed_quats).all():
            raise RuntimeError("RGBMocap correction returned non-finite motion")

        # Keep the upstream physical-sole diagnostics alongside the native IK report.
        after = sample(fixed_roots, fixed_quats)
        active, anchors, *_ = plan if plan is not None else plan_contacts(probes, floor)
        report.update(sole_metrics(probes, after, probabilities, active, anchors, report["segments"], fps, options["preset"], report["floor"], options["mode"]))
        if (report["full_lock_surface_error_max_m"] or 0) > .01 or report["contact_sole_penetration_over_1cm"]:
            report["warning"] = " ".join(filter(None, (report["warning"], "Some physical sole contacts remain unresolved; inspect floor height and timing.")))

        if fitted is not None:
            report["sole_fit"] = {"strength": self.sole_fit_strength, "adjusted": int(fitted.sum())}
            if fitted.any():
                for label, values in (("before", source_probes), ("after", after)):
                    gap = np.abs(values[:, ::2, 1] - values[:, 1::2, 1])[fitted]
                    report["sole_fit"][f"gap_{label}_p95_mm"] = float(np.quantile(gap, .95) * 1000)
                report["method"] += "; level stable soles"

        result = dict(output)
        result["rot6d"] = rot6d.clone()
        result["trans"] = trans.clone()
        matrices = Rotation.from_quat(fixed_quats[..., [1, 2, 3, 0]].reshape(-1, 4)).as_matrix().reshape(length, 22, 3, 3)
        # Same publication rule as RGBMocap: retain the source when there is no
        # contact; fingers and trunk stay untouched, arms require hand contacts.
        if length > 1:
            joints = ((1, 2, 4, 5, 7, 8) if report["contacts"] else ())
            joints += ((13, 14, 16, 17, 18, 19, 20, 21) if report["hand_lock"]["contacts"] else ())
            for joint in joints:
                value = matrices[:, joint, :, :2].reshape(length, 6).astype(np.float32)
                result["rot6d"][0, :, joint] = torch.as_tensor(value, device=rot6d.device, dtype=rot6d.dtype)
            if report["contacts"]:
                value = (fixed_roots - geometry.rest[0]).astype(np.float32)
                result["trans"][0] = torch.as_tensor(value, device=trans.device, dtype=trans.dtype)
        result["root_rot6d"] = result["rot6d"][:, :, 0]
        result["body_rot6d"] = result["rot6d"][:, :, 1:]
        for key in ("local_joints_positions", "smooth_root_pos", "pelvis_world"):
            result.pop(key, None)
        result["source"] = "initial"
        result["method"] = report["method"]
        report["elapsed_seconds"] = time.perf_counter() - started
        self.last_report = report
        print(f"  [RGBMocap correction] {length} frames, preset={report['preset']}, floor={report['floor']:+.3f} m, "
              f"contacts={report['contacts']}, {report['elapsed_seconds']:.2f}s")
        if fitted is not None:
            print(f"  [sole fit] {report['sole_fit']}")
        if report["warning"]:
            print(f"  [RGBMocap correction] {report['warning']}")
        return result
