"""
TFT Timing Measurement Tool

Uses OpenCV to analyze recorded gameplay and extract timing data:
- Attack windup (frames from attack start to projectile/damage)
- Spell cast time (frames from cast start to effect)

Recording Requirements:
- 120+ FPS (240 preferred for precision)
- 1080p or higher resolution
- Isolated 1v1 fight (practice tool or controlled environment)
- No items on test champion (cleaner timing)

Usage:
    python measure_timing.py <video_file> [--champion <name>] [--fps <fps>]
"""

import cv2
import numpy as np
import json
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import List, Tuple, Optional
import sys


@dataclass
class TimingEvent:
    """A detected timing event in the video."""
    frame_number: int
    timestamp_ms: float
    event_type: str  # 'attack_start', 'projectile_spawn', 'damage', 'spell_cast', etc.
    confidence: float
    details: dict


@dataclass
class MeasurementResult:
    """Result of timing measurement for a champion."""
    champion_name: str
    video_fps: float
    events: List[TimingEvent]

    # Computed timing values
    attack_windup_frames: Optional[float] = None
    attack_windup_seconds: Optional[float] = None
    spell_cast_frames: Optional[float] = None
    spell_cast_seconds: Optional[float] = None


class HPBarDetector:
    """Detects HP bar changes to identify damage frames."""

    def __init__(self):
        # HP bar is typically green/yellow/red on dark background
        # These are HSV ranges for typical HP bar colors
        self.hp_green_lower = np.array([35, 100, 100])
        self.hp_green_upper = np.array([85, 255, 255])
        self.hp_yellow_lower = np.array([15, 100, 100])
        self.hp_yellow_upper = np.array([35, 255, 255])
        self.hp_red_lower = np.array([0, 100, 100])
        self.hp_red_upper = np.array([15, 255, 255])

        self.previous_hp_pixels = None
        self.hp_region = None  # Will be set during calibration

    def set_hp_region(self, x: int, y: int, w: int, h: int):
        """Manually set the HP bar region to monitor."""
        self.hp_region = (x, y, w, h)

    def detect_hp_change(self, frame: np.ndarray) -> Tuple[bool, float]:
        """
        Detect if HP changed between this frame and previous.
        Returns (changed, magnitude).
        """
        if self.hp_region is None:
            return False, 0.0

        x, y, w, h = self.hp_region
        roi = frame[y:y+h, x:x+w]

        # Convert to HSV for color detection
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # Create masks for HP bar colors
        mask_green = cv2.inRange(hsv, self.hp_green_lower, self.hp_green_upper)
        mask_yellow = cv2.inRange(hsv, self.hp_yellow_lower, self.hp_yellow_upper)
        mask_red = cv2.inRange(hsv, self.hp_red_lower, self.hp_red_upper)

        # Combined HP pixels
        hp_mask = mask_green | mask_yellow | mask_red
        hp_pixels = np.sum(hp_mask > 0)

        if self.previous_hp_pixels is None:
            self.previous_hp_pixels = hp_pixels
            return False, 0.0

        # Calculate change
        change = self.previous_hp_pixels - hp_pixels
        change_ratio = change / max(self.previous_hp_pixels, 1)

        self.previous_hp_pixels = hp_pixels

        # Significant HP drop (damage taken)
        if change_ratio > 0.02:  # 2% HP drop threshold
            return True, change_ratio

        return False, 0.0


class ProjectileDetector:
    """Detects projectile spawn using motion and color analysis."""

    def __init__(self):
        self.previous_frame = None
        self.background = None

    def detect_projectile(self, frame: np.ndarray, roi: Optional[Tuple[int,int,int,int]] = None) -> Tuple[bool, List[Tuple[int, int]]]:
        """
        Detect new moving objects (projectiles) in frame.
        Returns (detected, list of (x, y) positions).
        """
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        if roi:
            x, y, w, h = roi
            gray = gray[y:y+h, x:x+w]

        if self.previous_frame is None:
            self.previous_frame = gray
            return False, []

        # Frame difference
        diff = cv2.absdiff(self.previous_frame, gray)
        _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)

        # Find contours of moving objects
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        projectiles = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if 50 < area < 5000:  # Projectile-sized objects
                M = cv2.moments(contour)
                if M["m00"] > 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    projectiles.append((cx, cy))

        self.previous_frame = gray

        return len(projectiles) > 0, projectiles


class AnimationStateDetector:
    """Detects animation state changes (idle, attacking, casting)."""

    def __init__(self):
        self.templates = {}  # Will store animation templates
        self.previous_state = None

    def detect_state_change(self, frame: np.ndarray, champion_roi: Tuple[int,int,int,int]) -> Tuple[bool, str]:
        """
        Detect if champion animation state changed.
        Returns (changed, new_state).
        """
        x, y, w, h = champion_roi
        roi = frame[y:y+h, x:x+w]

        # Use histogram comparison for state detection
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
        cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)

        # Simple state detection based on motion
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        # Could expand this to match known animation templates
        current_state = "unknown"
        changed = self.previous_state != current_state
        self.previous_state = current_state

        return changed, current_state


class DamageNumberDetector:
    """Detects floating damage numbers (most reliable damage indicator)."""

    def __init__(self):
        # Damage numbers are typically white/yellow text
        self.text_lower = np.array([0, 0, 200])  # White-ish
        self.text_upper = np.array([180, 50, 255])

    def detect_damage_numbers(self, frame: np.ndarray) -> List[Tuple[int, int, str]]:
        """
        Detect damage numbers in frame.
        Returns list of (x, y, estimated_value).
        """
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        # Mask for white/bright text
        mask = cv2.inRange(hsv, self.text_lower, self.text_upper)

        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        damage_numbers = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if 100 < area < 3000:  # Text-sized regions
                x, y, w, h = cv2.boundingRect(contour)
                # Damage numbers are typically wider than tall
                if w > h * 0.5:
                    damage_numbers.append((x + w//2, y + h//2, "?"))

        return damage_numbers


class TimingMeasurer:
    """Main class for measuring champion timing from video."""

    def __init__(self, video_path: str, fps: Optional[float] = None):
        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path)

        if not self.cap.isOpened():
            raise ValueError(f"Could not open video: {video_path}")

        self.fps = fps or self.cap.get(cv2.CAP_PROP_FPS)
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        print(f"Video: {self.width}x{self.height} @ {self.fps} FPS, {self.frame_count} frames")

        # Detectors
        self.hp_detector = HPBarDetector()
        self.projectile_detector = ProjectileDetector()
        self.damage_detector = DamageNumberDetector()

        # Results
        self.events: List[TimingEvent] = []

    def calibrate_regions(self):
        """
        Interactive calibration to set detection regions.
        User clicks to define: champion position, target HP bar, etc.
        """
        print("\n=== CALIBRATION MODE ===")
        print("Click to define regions. Press 'n' for next region, 'q' to finish.")

        ret, frame = self.cap.read()
        if not ret:
            print("Could not read first frame")
            return

        regions = {}
        current_region = "target_hp_bar"
        clicks = []

        def mouse_callback(event, x, y, flags, param):
            nonlocal clicks
            if event == cv2.EVENT_LBUTTONDOWN:
                clicks.append((x, y))
                print(f"  Click at ({x}, {y})")

        cv2.namedWindow("Calibration")
        cv2.setMouseCallback("Calibration", mouse_callback)

        region_names = ["target_hp_bar", "champion_area", "projectile_area"]
        region_idx = 0

        while True:
            display = frame.copy()

            # Draw existing regions
            for name, (x, y, w, h) in regions.items():
                cv2.rectangle(display, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.putText(display, name, (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

            # Draw current clicks
            for cx, cy in clicks:
                cv2.circle(display, (cx, cy), 5, (0, 0, 255), -1)

            # Instructions
            if region_idx < len(region_names):
                text = f"Define: {region_names[region_idx]} (click top-left, then bottom-right)"
            else:
                text = "Press 'q' to finish calibration"
            cv2.putText(display, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            cv2.imshow("Calibration", display)
            key = cv2.waitKey(1) & 0xFF

            if key == ord('q'):
                break
            elif key == ord('n') or len(clicks) >= 2:
                if len(clicks) >= 2 and region_idx < len(region_names):
                    x1, y1 = clicks[0]
                    x2, y2 = clicks[1]
                    regions[region_names[region_idx]] = (
                        min(x1, x2), min(y1, y2),
                        abs(x2 - x1), abs(y2 - y1)
                    )
                    print(f"  Set {region_names[region_idx]}: {regions[region_names[region_idx]]}")
                    region_idx += 1
                clicks = []

        cv2.destroyAllWindows()

        # Apply calibration
        if "target_hp_bar" in regions:
            self.hp_detector.set_hp_region(*regions["target_hp_bar"])

        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Reset to start
        return regions

    def analyze_video(self, show_preview: bool = True) -> List[TimingEvent]:
        """
        Analyze entire video for timing events.
        """
        print("\n=== ANALYZING VIDEO ===")

        frame_num = 0
        events = []

        while True:
            ret, frame = self.cap.read()
            if not ret:
                break

            timestamp_ms = (frame_num / self.fps) * 1000

            # Check for HP changes (damage)
            hp_changed, hp_magnitude = self.hp_detector.detect_hp_change(frame)
            if hp_changed:
                event = TimingEvent(
                    frame_number=frame_num,
                    timestamp_ms=timestamp_ms,
                    event_type="damage",
                    confidence=min(hp_magnitude * 10, 1.0),
                    details={"hp_drop_ratio": hp_magnitude}
                )
                events.append(event)
                print(f"  Frame {frame_num}: DAMAGE (HP drop: {hp_magnitude:.1%})")

            # Check for projectiles
            proj_detected, proj_positions = self.projectile_detector.detect_projectile(frame)
            if proj_detected:
                event = TimingEvent(
                    frame_number=frame_num,
                    timestamp_ms=timestamp_ms,
                    event_type="projectile",
                    confidence=0.7,
                    details={"positions": proj_positions}
                )
                events.append(event)

            # Check for damage numbers
            damage_nums = self.damage_detector.detect_damage_numbers(frame)
            if damage_nums:
                event = TimingEvent(
                    frame_number=frame_num,
                    timestamp_ms=timestamp_ms,
                    event_type="damage_number",
                    confidence=0.8,
                    details={"numbers": damage_nums}
                )
                events.append(event)

            # Show preview
            if show_preview and frame_num % 10 == 0:
                display = frame.copy()
                cv2.putText(display, f"Frame: {frame_num}", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.imshow("Analysis", display)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            frame_num += 1
            if frame_num % 100 == 0:
                print(f"  Processed {frame_num}/{self.frame_count} frames...")

        if show_preview:
            cv2.destroyAllWindows()

        self.events = events
        return events

    def compute_timing(self, champion_name: str) -> MeasurementResult:
        """
        Compute timing values from detected events.
        """
        result = MeasurementResult(
            champion_name=champion_name,
            video_fps=self.fps,
            events=self.events
        )

        # Find damage events and compute attack timing
        damage_events = [e for e in self.events if e.event_type == "damage"]

        if len(damage_events) >= 2:
            # Calculate average time between damage events (attack cycle)
            intervals = []
            for i in range(1, len(damage_events)):
                interval = damage_events[i].frame_number - damage_events[i-1].frame_number
                intervals.append(interval)

            avg_interval = sum(intervals) / len(intervals)
            print(f"\nAverage attack interval: {avg_interval:.1f} frames ({avg_interval/self.fps*1000:.0f}ms)")

            # Attack windup is typically 30-50% of attack time
            # This is a rough estimate - needs refinement
            estimated_windup = avg_interval * 0.35
            result.attack_windup_frames = estimated_windup
            result.attack_windup_seconds = estimated_windup / self.fps

        return result

    def interactive_frame_step(self):
        """
        Step through video frame by frame for manual timing.
        Press 'a' to mark attack start, 'd' to mark damage, etc.
        """
        print("\n=== INTERACTIVE FRAME STEPPING ===")
        print("Controls:")
        print("  SPACE/RIGHT: Next frame")
        print("  LEFT: Previous frame")
        print("  'a': Mark attack start")
        print("  'd': Mark damage frame")
        print("  'p': Mark projectile spawn")
        print("  's': Mark spell cast")
        print("  'q': Quit and save")

        frame_num = 0
        markers = []

        while True:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
            ret, frame = self.cap.read()
            if not ret:
                break

            # Draw frame info
            display = frame.copy()
            timestamp_ms = (frame_num / self.fps) * 1000
            cv2.putText(display, f"Frame: {frame_num} | Time: {timestamp_ms:.1f}ms",
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            # Draw markers
            for m in markers:
                if m['frame'] == frame_num:
                    cv2.putText(display, f">>> {m['type'].upper()} <<<",
                               (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            cv2.imshow("Frame Step", display)
            key = cv2.waitKey(0) & 0xFF

            if key == ord('q'):
                break
            elif key == ord(' ') or key == 83:  # Space or Right arrow
                frame_num = min(frame_num + 1, self.frame_count - 1)
            elif key == 81:  # Left arrow
                frame_num = max(frame_num - 1, 0)
            elif key == ord('a'):
                markers.append({'frame': frame_num, 'type': 'attack_start', 'time_ms': timestamp_ms})
                print(f"  Marked ATTACK START at frame {frame_num}")
            elif key == ord('d'):
                markers.append({'frame': frame_num, 'type': 'damage', 'time_ms': timestamp_ms})
                print(f"  Marked DAMAGE at frame {frame_num}")
            elif key == ord('p'):
                markers.append({'frame': frame_num, 'type': 'projectile', 'time_ms': timestamp_ms})
                print(f"  Marked PROJECTILE at frame {frame_num}")
            elif key == ord('s'):
                markers.append({'frame': frame_num, 'type': 'spell_cast', 'time_ms': timestamp_ms})
                print(f"  Marked SPELL CAST at frame {frame_num}")

        cv2.destroyAllWindows()

        # Compute timing from markers
        self._compute_from_markers(markers)
        return markers

    def _compute_from_markers(self, markers: List[dict]):
        """Compute timing values from manual markers."""
        attack_starts = [m for m in markers if m['type'] == 'attack_start']
        damage_frames = [m for m in markers if m['type'] == 'damage']
        projectiles = [m for m in markers if m['type'] == 'projectile']

        print("\n=== TIMING RESULTS ===")

        # Match attack starts with damage/projectile
        for i, start in enumerate(attack_starts):
            # Find next damage after this attack start
            next_damage = None
            for d in damage_frames:
                if d['frame'] > start['frame']:
                    next_damage = d
                    break

            if next_damage:
                windup_frames = next_damage['frame'] - start['frame']
                windup_ms = windup_frames / self.fps * 1000
                print(f"Attack {i+1}: {windup_frames} frames windup ({windup_ms:.1f}ms)")

    def close(self):
        self.cap.release()
        cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(description="Measure TFT champion timing from video")
    parser.add_argument("video", help="Path to video file")
    parser.add_argument("--champion", "-c", default="Unknown", help="Champion name")
    parser.add_argument("--fps", type=float, help="Override video FPS")
    parser.add_argument("--mode", choices=["auto", "interactive", "calibrate"],
                       default="interactive", help="Analysis mode")
    parser.add_argument("--output", "-o", help="Output JSON file")

    args = parser.parse_args()

    measurer = TimingMeasurer(args.video, args.fps)

    try:
        if args.mode == "calibrate":
            regions = measurer.calibrate_regions()
            events = measurer.analyze_video()
        elif args.mode == "auto":
            events = measurer.analyze_video()
        else:  # interactive
            markers = measurer.interactive_frame_step()
            events = markers

        result = measurer.compute_timing(args.champion)

        # Save results
        if args.output:
            output_data = {
                "champion": args.champion,
                "video_fps": measurer.fps,
                "events": [
                    {
                        "frame": e.frame_number if isinstance(e, TimingEvent) else e['frame'],
                        "time_ms": e.timestamp_ms if isinstance(e, TimingEvent) else e['time_ms'],
                        "type": e.event_type if isinstance(e, TimingEvent) else e['type'],
                    }
                    for e in events
                ],
                "timing": {
                    "attack_windup_frames": result.attack_windup_frames,
                    "attack_windup_seconds": result.attack_windup_seconds,
                }
            }

            with open(args.output, 'w') as f:
                json.dump(output_data, f, indent=2)
            print(f"\nSaved results to: {args.output}")

    finally:
        measurer.close()


if __name__ == "__main__":
    main()
