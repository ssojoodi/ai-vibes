import cv2
import numpy as np
import time
import json
import os
from datetime import datetime


class LawnGuardian:
    def __init__(self):
        self.cap = None
        self.detection_zone = []
        self.zone_mask = None
        self.last_detection_time = 0
        self.detection_cooldown = 1.0  # 1 second between samples
        self.min_contour_area = 500  # Minimum size for detection
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2(
            detectShadows=True
        )
        self.zone_file = "detection_zone.json"

    def load_zone(self):
        """Load previously saved detection zone"""
        if os.path.exists(self.zone_file):
            with open(self.zone_file, "r") as f:
                self.detection_zone = json.load(f)
            print("Loaded existing detection zone")

    def save_zone(self):
        """Save detection zone to file"""
        with open(self.zone_file, "w") as f:
            json.dump(self.detection_zone, f)
        print("Detection zone saved")

    def mouse_callback(self, event, x, y, flags, param):
        """Handle mouse clicks for zone definition"""
        if event == cv2.EVENT_LBUTTONDOWN:
            self.detection_zone.append([x, y])
            print(f"Point added: ({x}, {y})")
        elif event == cv2.EVENT_RBUTTONDOWN:
            if len(self.detection_zone) > 0:
                self.detection_zone.pop()
                print("Last point removed")

    def create_zone_mask(self, frame_shape):
        """Create mask from detection zone points"""
        if len(self.detection_zone) < 3:
            return None

        mask = np.zeros(frame_shape[:2], dtype=np.uint8)
        points = np.array(self.detection_zone, dtype=np.int32)
        cv2.fillPoly(mask, [points], 255)
        return mask

    def setup_zone_editor(self):
        """Interactive zone editor"""
        print("\n=== ZONE SETUP MODE ===")
        print("Instructions:")
        print("- Left click to add points for your detection zone")
        print("- Right click to remove the last point")
        print("- Press 's' to save zone")
        print("- Press 'c' to clear all points")
        print("- Press 'q' to finish setup")
        print("- You need at least 3 points to create a zone")

        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            print("Error: Could not open webcam")
            return False

        cv2.namedWindow("Zone Editor")
        cv2.setMouseCallback("Zone Editor", self.mouse_callback)

        self.load_zone()

        while True:
            ret, frame = self.cap.read()
            if not ret:
                break

            # Draw existing zone
            if len(self.detection_zone) > 0:
                for i, point in enumerate(self.detection_zone):
                    cv2.circle(frame, tuple(point), 5, (0, 255, 0), -1)
                    cv2.putText(
                        frame,
                        str(i + 1),
                        (point[0] + 10, point[1]),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (0, 255, 0),
                        1,
                    )

                # Draw lines between points
                if len(self.detection_zone) > 1:
                    points = np.array(self.detection_zone, dtype=np.int32)
                    cv2.polylines(frame, [points], False, (0, 255, 0), 2)

                    # Close the polygon if we have 3+ points
                    if len(self.detection_zone) >= 3:
                        cv2.polylines(frame, [points], True, (0, 255, 0), 2)
                        # Show filled zone with transparency
                        overlay = frame.copy()
                        cv2.fillPoly(overlay, [points], (0, 255, 0))
                        frame = cv2.addWeighted(frame, 0.8, overlay, 0.2, 0)

            # Add instructions on frame
            cv2.putText(
                frame,
                f"Points: {len(self.detection_zone)}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2,
            )
            cv2.putText(
                frame,
                "Left click: Add point | Right click: Remove point",
                (10, frame.shape[0] - 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
            )
            cv2.putText(
                frame,
                "Press 's' to save, 'c' to clear, 'q' to finish",
                (10, frame.shape[0] - 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
            )

            cv2.imshow("Zone Editor", frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("s"):
                if len(self.detection_zone) >= 3:
                    self.save_zone()
                else:
                    print("Need at least 3 points to save zone")
            elif key == ord("c"):
                self.detection_zone = []
                print("Zone cleared")

        self.cap.release()
        cv2.destroyAllWindows()

        return len(self.detection_zone) >= 3

    def detect_motion_in_zone(self, frame):
        """Detect motion within the defined zone"""
        if self.zone_mask is None:
            return False, None

        # Apply background subtraction
        fg_mask = self.background_subtractor.apply(frame)

        # Apply morphological operations to clean up the mask
        kernel = np.ones((5, 5), np.uint8)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)

        # Apply zone mask
        zone_motion = cv2.bitwise_and(fg_mask, self.zone_mask)

        # Find contours
        contours, _ = cv2.findContours(
            zone_motion, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        # Check if any contour is large enough
        detected = False
        largest_area = 0
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > self.min_contour_area:
                detected = True
                largest_area = max(largest_area, area)

        return detected, largest_area

    def run_detection(self):
        """Main detection loop"""
        print("\n=== DETECTION MODE ===")
        print(
            f"Monitoring lawn area (sampling every {self.detection_cooldown} seconds)"
        )
        print(f"Minimum detection size: {self.min_contour_area} pixels")
        print("Press 'q' to quit")

        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            print("Error: Could not open webcam")
            return

        # Create zone mask
        ret, frame = self.cap.read()
        if ret:
            self.zone_mask = self.create_zone_mask(frame.shape)

        if self.zone_mask is None:
            print("Error: No valid detection zone defined")
            return

        detection_active = False

        while True:
            ret, frame = self.cap.read()
            if not ret:
                break

            current_time = time.time()

            # Sample at defined interval
            if current_time - self.last_detection_time >= self.detection_cooldown:
                self.last_detection_time = current_time

                detected, area = self.detect_motion_in_zone(frame)

                if detected and not detection_active:
                    detection_active = True
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(
                        f"🚨 ANIMAL DETECTED on lawn! [{timestamp}] Area: {area} pixels"
                    )

                elif not detected and detection_active:
                    detection_active = False
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"✅ Area clear [{timestamp}]")

            # Visualize (optional - comment out for headless operation)
            self.draw_detection_overlay(frame, detection_active)
            cv2.imshow("Lawn Guardian", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

        self.cap.release()
        cv2.destroyAllWindows()

    def draw_detection_overlay(self, frame, detection_active):
        """Draw detection zone and status on frame"""
        # Draw detection zone
        if len(self.detection_zone) >= 3:
            points = np.array(self.detection_zone, dtype=np.int32)
            color = (0, 0, 255) if detection_active else (0, 255, 0)
            cv2.polylines(frame, [points], True, color, 2)

        # Status text
        status = "ANIMAL DETECTED!" if detection_active else "Monitoring..."
        color = (0, 0, 255) if detection_active else (0, 255, 0)
        cv2.putText(frame, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

        # Timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        cv2.putText(
            frame,
            timestamp,
            (10, frame.shape[0] - 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
        )


def main():
    guardian = LawnGuardian()

    print("🐕 Lawn Guardian - Animal Detection System")
    print("=========================================")

    # Setup detection zone
    if guardian.setup_zone_editor():
        print("✅ Detection zone configured successfully!")

        # Ask for sensitivity settings
        try:
            min_size = input(
                f"Enter minimum detection size in pixels (default {guardian.min_contour_area}): "
            )
            if min_size.strip():
                guardian.min_contour_area = int(min_size)
        except ValueError:
            print("Using default minimum size")

        # Start detection
        guardian.run_detection()
    else:
        print("❌ No detection zone configured. Exiting.")


if __name__ == "__main__":
    main()
