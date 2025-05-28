import cv2
import numpy as np
import time
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import List, Tuple, Optional
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("package_inspection.log"), logging.StreamHandler()],
)


@dataclass
class PackageInspection:
    package_id: int
    timestamp: datetime
    has_label: bool
    label_centered: bool
    label_position: Optional[Tuple[int, int]]
    package_bbox: Tuple[int, int, int, int]
    confidence_score: float


class PackageInspector:
    def __init__(self, camera_index=0):
        self.cap = cv2.VideoCapture(camera_index)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        # Package detection parameters
        self.package_cascade = None  # Will be loaded if using Haar cascades
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2(
            detectShadows=True, varThreshold=50
        )

        # Tracking variables
        self.package_counter = 0
        self.inspection_results = []
        self.last_packages = []

        # Calibration parameters (adjust based on your setup)
        self.min_package_area = 5000
        self.max_package_area = 50000
        self.label_color_range = {
            "lower": np.array([0, 0, 200]),  # Adjust for your label color
            "upper": np.array([180, 30, 255]),
        }

        # Center tolerance (percentage of package width/height)
        self.center_tolerance = 0.15

    def preprocess_frame(self, frame):
        """Preprocess frame for better detection"""
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Enhance contrast
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(blurred)

        return enhanced

    def detect_packages(self, frame):
        """Detect packages on the conveyor belt"""
        # Method 1: Background subtraction for moving objects
        fg_mask = self.background_subtractor.apply(frame)

        # Clean up the mask
        kernel = np.ones((5, 5), np.uint8)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)

        # Find contours
        contours, _ = cv2.findContours(
            fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        packages = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if self.min_package_area < area < self.max_package_area:
                # Get bounding rectangle
                x, y, w, h = cv2.boundingRect(contour)

                # Filter by aspect ratio (assuming packages are roughly rectangular)
                aspect_ratio = w / h
                if 0.5 < aspect_ratio < 3.0:  # Adjust based on your package shape
                    packages.append((x, y, w, h, area))

        return packages

    def detect_label_on_package(self, frame, package_bbox):
        """Detect if a label exists on the package and check its position"""
        x, y, w, h = package_bbox

        # Extract package region
        package_roi = frame[y : y + h, x : x + w]

        if package_roi.size == 0:
            return False, False, None

        # Method 1: Color-based label detection
        hsv_roi = cv2.cvtColor(package_roi, cv2.COLOR_BGR2HSV)

        # Create mask for label color
        label_mask = cv2.inRange(
            hsv_roi, self.label_color_range["lower"], self.label_color_range["upper"]
        )

        # Find label contours
        label_contours, _ = cv2.findContours(
            label_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if not label_contours:
            return False, False, None

        # Find the largest label contour
        largest_label = max(label_contours, key=cv2.contourArea)
        label_area = cv2.contourArea(largest_label)

        # Check if label is significant enough
        package_area = w * h
        if label_area < package_area * 0.05:  # Label should be at least 5% of package
            return False, False, None

        # Get label center
        M = cv2.moments(largest_label)
        if M["m00"] != 0:
            label_cx = int(M["m10"] / M["m00"])
            label_cy = int(M["m01"] / M["m00"])
        else:
            return True, False, None

        # Check if label is centered
        package_center_x = w // 2
        package_center_y = h // 2

        tolerance_x = w * self.center_tolerance
        tolerance_y = h * self.center_tolerance

        is_centered = (
            abs(label_cx - package_center_x) < tolerance_x
            and abs(label_cy - package_center_y) < tolerance_y
        )

        # Convert to global coordinates
        global_label_pos = (x + label_cx, y + label_cy)

        return True, is_centered, global_label_pos

    def track_packages(self, current_packages):
        """Simple tracking to avoid duplicate counting"""
        # This is a simplified tracking algorithm
        # You might want to implement a more sophisticated tracker like SORT

        new_packages = []
        for pkg in current_packages:
            x, y, w, h, area = pkg
            center = (x + w // 2, y + h // 2)

            # Check if this package is new (not in previous frame)
            is_new = True
            for last_pkg in self.last_packages:
                last_center = (
                    last_pkg[0] + last_pkg[2] // 2,
                    last_pkg[1] + last_pkg[3] // 2,
                )
                distance = np.sqrt(
                    (center[0] - last_center[0]) ** 2
                    + (center[1] - last_center[1]) ** 2
                )

                if distance < 50:  # Threshold for same package
                    is_new = False
                    break

            if is_new:
                new_packages.append(pkg)

        self.last_packages = current_packages
        return new_packages

    def inspect_package(self, frame, package_bbox):
        """Perform complete inspection of a package"""
        has_label, is_centered, label_pos = self.detect_label_on_package(
            frame, package_bbox
        )

        self.package_counter += 1

        inspection = PackageInspection(
            package_id=self.package_counter,
            timestamp=datetime.now(),
            has_label=has_label,
            label_centered=is_centered,
            label_position=label_pos,
            package_bbox=package_bbox,
            confidence_score=0.8,  # You can implement a confidence calculation
        )

        self.inspection_results.append(inspection)

        # Log the result
        status = "PASS" if has_label and is_centered else "FAIL"
        issue = []
        if not has_label:
            issue.append("NO_LABEL")
        elif not is_centered:
            issue.append("LABEL_MISALIGNED")

        issue_str = ", ".join(issue) if issue else "NONE"

        logging.info(f"Package {inspection.package_id}: {status} - Issues: {issue_str}")

        return inspection

    def draw_annotations(self, frame, packages, inspections):
        """Draw bounding boxes and inspection results on frame"""
        for i, (package, inspection) in enumerate(zip(packages, inspections)):
            x, y, w, h, _ = package

            # Choose color based on inspection result
            if inspection.has_label and inspection.label_centered:
                color = (0, 255, 0)  # Green for good
                status = "PASS"
            elif inspection.has_label:
                color = (0, 255, 255)  # Yellow for misaligned
                status = "MISALIGNED"
            else:
                color = (0, 0, 255)  # Red for no label
                status = "NO LABEL"

            # Draw package bounding box
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)

            # Draw label position if detected
            if inspection.label_position:
                lx, ly = inspection.label_position
                cv2.circle(frame, (lx, ly), 5, (255, 0, 255), -1)
                cv2.line(frame, (x + w // 2, y + h // 2), (lx, ly), (255, 0, 255), 2)

            # Add text annotation
            cv2.putText(
                frame,
                f"ID:{inspection.package_id} {status}",
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2,
            )

        return frame

    def save_inspection_data(self, filename="inspection_results.json"):
        """Save inspection results to file"""
        data = []
        for inspection in self.inspection_results:
            data.append(
                {
                    "package_id": inspection.package_id,
                    "timestamp": inspection.timestamp.isoformat(),
                    "has_label": inspection.has_label,
                    "label_centered": inspection.label_centered,
                    "label_position": inspection.label_position,
                    "package_bbox": inspection.package_bbox,
                    "confidence_score": inspection.confidence_score,
                }
            )

        with open(filename, "w") as f:
            json.dump(data, f, indent=2)

    def run(self):
        """Main inspection loop"""
        logging.info("Starting package inspection system...")

        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    logging.error("Failed to read frame from camera")
                    break

                # Detect packages
                packages = self.detect_packages(frame)

                # Track new packages to avoid duplicate processing
                new_packages = self.track_packages(packages)

                # Inspect each new package
                inspections = []
                for package in new_packages:
                    inspection = self.inspect_package(frame, package[:4])  # Remove area
                    inspections.append(inspection)

                # Draw annotations
                annotated_frame = self.draw_annotations(
                    frame, new_packages, inspections
                )

                # Add system info
                cv2.putText(
                    annotated_frame,
                    f"Packages Processed: {self.package_counter}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2,
                )

                pass_rate = 0
                if self.package_counter > 0:
                    passed = sum(
                        1
                        for r in self.inspection_results[-50:]
                        if r.has_label and r.label_centered
                    )
                    pass_rate = (passed / min(len(self.inspection_results), 50)) * 100

                cv2.putText(
                    annotated_frame,
                    f"Pass Rate: {pass_rate:.1f}%",
                    (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2,
                )

                # Display the frame
                cv2.imshow("Package Inspection", annotated_frame)

                # Check for exit condition
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                elif key == ord("s"):
                    # Save current results
                    self.save_inspection_data()
                    logging.info("Inspection data saved")

                # Small delay to prevent excessive CPU usage
                time.sleep(0.01)

        except KeyboardInterrupt:
            logging.info("Inspection stopped by user")

        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        self.save_inspection_data()
        self.cap.release()
        cv2.destroyAllWindows()
        logging.info("Package inspection system stopped")


# Configuration function for easy customization
def configure_inspector():
    """Configure the inspector based on your specific setup"""
    inspector = PackageInspector(camera_index=0)  # Change camera index if needed

    # Adjust these parameters based on your setup:

    # Package size constraints (in pixels)
    inspector.min_package_area = 5000
    inspector.max_package_area = 50000

    # Label color range (HSV format)
    # You may need to calibrate this for your specific label colors
    inspector.label_color_range = {
        "lower": np.array([0, 0, 200]),  # Adjust for your label color
        "upper": np.array([180, 30, 255]),
    }

    # Center tolerance (15% of package dimensions)
    inspector.center_tolerance = 0.15

    return inspector


if __name__ == "__main__":
    # Create and configure the inspector
    inspector = configure_inspector()

    # Run the inspection system
    inspector.run()
