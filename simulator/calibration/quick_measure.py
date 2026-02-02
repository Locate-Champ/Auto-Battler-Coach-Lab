"""
Quick Timing Measurement Tool

Simplified tool for rapidly measuring champion timing.
Just mark attack starts and damage frames - computes windup automatically.

Usage:
    python quick_measure.py <video_file> --champion <name>

Keyboard:
    SPACE: Next frame
    BACKSPACE: Previous frame
    1: Mark attack START
    2: Mark DAMAGE received
    3: Mark PROJECTILE spawn
    ENTER: Compute and show results
    S: Save results
    Q: Quit
"""

import cv2
import numpy as np
import json
import sys
from pathlib import Path
from datetime import datetime


class QuickMeasure:
    def __init__(self, video_path: str, champion: str, scale: float = 2.0):
        self.video_path = video_path
        self.champion = champion
        self.scale = scale  # Display scaling factor
        self.cap = cv2.VideoCapture(video_path)

        if not self.cap.isOpened():
            raise ValueError(f"Cannot open: {video_path}")

        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # Scaled display dimensions
        self.display_width = int(self.width * scale)
        self.display_height = int(self.height * scale)

        # Markers
        self.attack_starts = []
        self.damage_frames = []
        self.projectile_frames = []

        print(f"Video: {self.width}x{self.height} @ {self.fps:.1f} FPS")
        print(f"Display: {self.display_width}x{self.display_height} (scale: {scale}x)")
        print(f"Total frames: {self.total_frames} ({self.total_frames/self.fps:.1f}s)")
        print(f"Champion: {champion}")

    def run(self):
        frame_idx = 0
        paused = True

        print("\n" + "="*60)
        print("CONTROLS")
        print("="*60)
        print("NAVIGATION:")
        print("  SPACE / RIGHT  : Next frame (+1)")
        print("  BACKSPACE/LEFT : Previous frame (-1)")
        print("  UP / W         : Jump forward 30 frames (~1 sec)")
        print("  DOWN / S key   : Jump backward 30 frames (~1 sec)")
        print("  D              : Jump forward 150 frames (~5 sec)")
        print("  A              : Jump backward 150 frames (~5 sec)")
        print("  F              : Jump forward 300 frames (~10 sec)")
        print("  R              : Jump backward 300 frames (~10 sec)")
        print("  G              : Go to specific frame (type in console)")
        print("")
        print("MARKING:")
        print("  1 : Mark attack START")
        print("  2 : Mark DAMAGE received")
        print("  3 : Mark PROJECTILE spawn")
        print("  Z : Undo last marker")
        print("")
        print("ACTIONS:")
        print("  ENTER : Compute and show results")
        print("  S     : Save results to file (SHIFT+S)")
        print("  P     : Toggle play/pause")
        print("  Q     : Quit")
        print("="*60 + "\n")

        while True:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = self.cap.read()

            if not ret:
                print("End of video")
                break

            # Scale up the frame for display
            if self.scale != 1.0:
                frame = cv2.resize(frame, (self.display_width, self.display_height),
                                   interpolation=cv2.INTER_LINEAR)

            # Draw UI
            display = self._draw_ui(frame, frame_idx)
            cv2.imshow("Quick Measure - TFT Timing Tool", display)

            key = cv2.waitKey(0 if paused else 30) & 0xFF

            if key == ord('q'):
                break
            # Frame-by-frame navigation
            elif key == ord(' ') or key == 83 or key == 3:  # SPACE or RIGHT arrow
                frame_idx = min(frame_idx + 1, self.total_frames - 1)
            elif key == 8 or key == 81 or key == 2:  # BACKSPACE or LEFT arrow
                frame_idx = max(frame_idx - 1, 0)
            # Jump navigation (30 frames = ~1 sec at 30fps)
            elif key == 82 or key == 0 or key == ord('w'):  # UP arrow or W
                frame_idx = min(frame_idx + 30, self.total_frames - 1)
                print(f"  >> Jump to frame {frame_idx} ({frame_idx/self.fps:.1f}s)")
            elif key == 84 or key == 1:  # DOWN arrow (not 's' - reserved for save)
                frame_idx = max(frame_idx - 30, 0)
                print(f"  << Jump to frame {frame_idx} ({frame_idx/self.fps:.1f}s)")
            # Big jumps (150 frames = ~5 sec)
            elif key == ord('d'):
                frame_idx = min(frame_idx + 150, self.total_frames - 1)
                print(f"  >>> Jump to frame {frame_idx} ({frame_idx/self.fps:.1f}s)")
            elif key == ord('a'):
                frame_idx = max(frame_idx - 150, 0)
                print(f"  <<< Jump to frame {frame_idx} ({frame_idx/self.fps:.1f}s)")
            # Huge jumps (300 frames = ~10 sec)
            elif key == ord('f'):
                frame_idx = min(frame_idx + 300, self.total_frames - 1)
                print(f"  >>>> Jump to frame {frame_idx} ({frame_idx/self.fps:.1f}s)")
            elif key == ord('r'):
                frame_idx = max(frame_idx - 300, 0)
                print(f"  <<<< Jump to frame {frame_idx} ({frame_idx/self.fps:.1f}s)")
            # Go to specific frame
            elif key == ord('g'):
                try:
                    target = input(f"Go to frame (0-{self.total_frames-1}): ").strip()
                    if target.endswith('s'):  # Allow time in seconds
                        seconds = float(target[:-1])
                        frame_idx = int(seconds * self.fps)
                    else:
                        frame_idx = int(target)
                    frame_idx = max(0, min(frame_idx, self.total_frames - 1))
                    print(f"  Jumped to frame {frame_idx} ({frame_idx/self.fps:.1f}s)")
                except:
                    print("  Invalid input")
            # Markers
            elif key == ord('1'):  # Attack start
                self.attack_starts.append(frame_idx)
                print(f"  [ATTACK START] Frame {frame_idx} ({self._frame_to_ms(frame_idx):.1f}ms)")
            elif key == ord('2'):  # Damage
                self.damage_frames.append(frame_idx)
                print(f"  [DAMAGE] Frame {frame_idx} ({self._frame_to_ms(frame_idx):.1f}ms)")
            elif key == ord('3'):  # Projectile
                self.projectile_frames.append(frame_idx)
                print(f"  [PROJECTILE] Frame {frame_idx} ({self._frame_to_ms(frame_idx):.1f}ms)")
            elif key == ord('z'):  # Undo last marker
                self._undo_last_marker()
            elif key == 13:  # Enter - compute
                self._compute_results()
            elif key == ord('S'):  # Shift+S to save (capital S)
                self._save_results()
            elif key == ord('p'):  # Toggle pause
                paused = not paused
                print(f"  {'PAUSED' if paused else 'PLAYING'}")

        cv2.destroyAllWindows()
        self.cap.release()

    def _undo_last_marker(self):
        """Remove the most recently added marker."""
        # Find which list has the most recent marker
        last_attack = self.attack_starts[-1] if self.attack_starts else -1
        last_damage = self.damage_frames[-1] if self.damage_frames else -1
        last_proj = self.projectile_frames[-1] if self.projectile_frames else -1

        most_recent = max(last_attack, last_damage, last_proj)

        if most_recent == -1:
            print("  No markers to undo")
            return

        if most_recent == last_attack:
            removed = self.attack_starts.pop()
            print(f"  [UNDO] Removed ATTACK START at frame {removed}")
        elif most_recent == last_damage:
            removed = self.damage_frames.pop()
            print(f"  [UNDO] Removed DAMAGE at frame {removed}")
        else:
            removed = self.projectile_frames.pop()
            print(f"  [UNDO] Removed PROJECTILE at frame {removed}")

    def _frame_to_ms(self, frame: int) -> float:
        return (frame / self.fps) * 1000

    def _draw_ui(self, frame: np.ndarray, frame_idx: int) -> np.ndarray:
        display = frame.copy()
        h, w = display.shape[:2]

        # Scale font size based on display size
        font_scale = 0.7 * self.scale
        thickness = max(1, int(self.scale))

        # Semi-transparent overlay at bottom (bigger for scaled display)
        overlay_height = int(140 * self.scale)
        overlay = display.copy()
        cv2.rectangle(overlay, (0, h-overlay_height), (w, h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, display, 0.3, 0, display)

        # Progress bar
        progress = frame_idx / max(1, self.total_frames - 1)
        bar_y = h - overlay_height + int(10 * self.scale)
        bar_height = int(8 * self.scale)
        cv2.rectangle(display, (10, bar_y), (w-10, bar_y + bar_height), (60, 60, 60), -1)
        cv2.rectangle(display, (10, bar_y), (int(10 + (w-20) * progress), bar_y + bar_height), (0, 200, 0), -1)

        # Frame info
        time_sec = frame_idx / self.fps
        time_ms = self._frame_to_ms(frame_idx)
        y_offset = h - overlay_height + int(40 * self.scale)
        cv2.putText(display, f"Frame: {frame_idx}/{self.total_frames} | Time: {time_sec:.2f}s ({time_ms:.0f}ms)",
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, font_scale * 0.85, (255, 255, 255), thickness)

        # Marker counts
        y_offset += int(30 * self.scale)
        cv2.putText(display, f"Attacks: {len(self.attack_starts)} | Damage: {len(self.damage_frames)} | Projectiles: {len(self.projectile_frames)}",
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, font_scale * 0.85, (255, 255, 255), thickness)

        # Current frame markers
        markers = []
        if frame_idx in self.attack_starts:
            markers.append("ATTACK START")
        if frame_idx in self.damage_frames:
            markers.append("DAMAGE")
        if frame_idx in self.projectile_frames:
            markers.append("PROJECTILE")

        if markers:
            y_offset += int(30 * self.scale)
            cv2.putText(display, " | ".join(markers),
                       (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 255, 0), thickness + 1)

        # Top bar with controls hint
        top_overlay = display.copy()
        cv2.rectangle(top_overlay, (0, 0), (w, int(35 * self.scale)), (0, 0, 0), -1)
        cv2.addWeighted(top_overlay, 0.6, display, 0.4, 0, display)

        cv2.putText(display, f"{self.champion} | 1=Attack 2=Damage 3=Proj | WASD/Arrows=Navigate | ENTER=Results | Shift+S=Save | Q=Quit",
                   (10, int(25 * self.scale)), cv2.FONT_HERSHEY_SIMPLEX, font_scale * 0.6, (200, 200, 200), thickness)

        return display

    def _compute_results(self):
        print("\n" + "="*50)
        print("TIMING RESULTS")
        print("="*50)

        # Compute attack windup (attack start -> damage)
        windups = []
        for i, start in enumerate(self.attack_starts):
            # Find closest damage after this start
            damages_after = [d for d in self.damage_frames if d > start]
            if damages_after:
                damage = min(damages_after)
                windup_frames = damage - start
                windup_ms = self._frame_to_ms(windup_frames)
                windups.append(windup_frames)
                print(f"Attack {i+1}: Start={start} -> Damage={damage} = {windup_frames} frames ({windup_ms:.1f}ms)")

        if windups:
            avg_windup_frames = sum(windups) / len(windups)
            avg_windup_ms = self._frame_to_ms(avg_windup_frames)
            avg_windup_sec = avg_windup_frames / self.fps

            print(f"\n>>> AVERAGE ATTACK WINDUP: {avg_windup_frames:.1f} frames = {avg_windup_ms:.1f}ms = {avg_windup_sec:.3f}s")

        # Compute projectile travel time (projectile spawn -> damage)
        if self.projectile_frames and self.damage_frames:
            travel_times = []
            for proj in self.projectile_frames:
                damages_after = [d for d in self.damage_frames if d > proj]
                if damages_after:
                    damage = min(damages_after)
                    travel = damage - proj
                    travel_times.append(travel)

            if travel_times:
                avg_travel = sum(travel_times) / len(travel_times)
                print(f">>> AVERAGE PROJECTILE TRAVEL: {avg_travel:.1f} frames = {self._frame_to_ms(avg_travel):.1f}ms")

        print("="*50 + "\n")

        return {
            'windups_frames': windups,
            'avg_windup_frames': avg_windup_frames if windups else None,
            'avg_windup_seconds': avg_windup_frames / self.fps if windups else None,
        }

    def _save_results(self):
        results = self._compute_results()

        output = {
            'champion': self.champion,
            'video': self.video_path,
            'video_fps': self.fps,
            'measured_at': datetime.now().isoformat(),
            'markers': {
                'attack_starts': self.attack_starts,
                'damage_frames': self.damage_frames,
                'projectile_frames': self.projectile_frames,
            },
            'timing': {
                'attack_windup_frames': results.get('avg_windup_frames'),
                'attack_windup_seconds': results.get('avg_windup_seconds'),
                'individual_windups_frames': results.get('windups_frames', []),
                'source': 'measured',
                'confidence': 'high' if len(results.get('windups_frames', [])) >= 3 else 'medium',
            }
        }

        # Save to file
        output_dir = Path(__file__).parent / "measurements"
        output_dir.mkdir(exist_ok=True)

        filename = f"{self.champion.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        output_path = output_dir / filename

        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"\nSaved to: {output_path}")

        # Also print update command
        print(f"\nTo update timing_constants.json:")
        print(f"  API name: TFT16_{self.champion.replace(' ', '')}")
        print(f"  attack_windup_seconds: {results.get('avg_windup_seconds', 'N/A')}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python quick_measure.py <video_file> [--champion <name>]")
        print("\nExample:")
        print("  python quick_measure.py caitlyn_fight.mp4 --champion Caitlyn")
        sys.exit(1)

    video_path = sys.argv[1]
    champion = "Unknown"

    if "--champion" in sys.argv:
        idx = sys.argv.index("--champion")
        if idx + 1 < len(sys.argv):
            champion = sys.argv[idx + 1]

    measurer = QuickMeasure(video_path, champion)
    measurer.run()


if __name__ == "__main__":
    main()
