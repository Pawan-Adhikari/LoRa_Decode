import subprocess
import os
import sys
import platform

def main():
    print("--- Starting LoRa SDR Setup and Run Process (Dockerized) ---")

    # Determine the Docker image name
    docker_image_name = "lora-sdr-demodulator"

    # 1. Build the Docker image
    print(f"\nStep 1: Building Docker image '{docker_image_name}'...")
    try:
        # Get the directory of the current script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Ensure Dockerfile exists
        dockerfile_path = os.path.join(script_dir, "Dockerfile")
        if not os.path.exists(dockerfile_path):
            print(f"Error: Dockerfile not found at {dockerfile_path}. Please create it.", file=sys.stderr)
            sys.exit(1)

        # Build the Docker image. The context is the script's directory.
        build_command = ["docker", "build", "-t", docker_image_name, script_dir]
        print(f"Executing: {' '.join(build_command)}")
        subprocess.run(build_command, check=True)
        print(f"Step 1: Docker image '{docker_image_name}' built successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Critical error: Failed to build Docker image. Error: {e}", file=sys.stderr)
        print("Please ensure Docker is installed and running on your system.", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: 'docker' command not found. Please install Docker Desktop.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred during Docker build: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. Run the SDR detection within the Docker container
    print("\nStep 2: Detecting SDR devices within the Docker container...")
    
    # Common device mounts for SDRs. Adjust based on your specific SDR.
    device_mounts = []
    if platform.system() == "Linux":
        device_mounts.append("--device=/dev/bus/usb") # Generic USB device access
        # Add more specific devices if known, e.g., --device=/dev/ttyUSB0
    elif platform.system() == "Darwin":
        print("[WARN] USB device passthrough on Docker Desktop for macOS can be complex.")
        print("[WARN] If SDR detection fails, you might need to manually configure USB passthrough or use a Linux VM.")
        device_mounts.append("--device=/dev/bus/usb") # Attempt generic USB passthrough
    elif platform.system() == "Windows":
        print("[WARN] USB device passthrough on Docker Desktop for Windows can be complex.")
        print("[WARN] If SDR detection fails, you might need to manually configure USB passthrough or use a Linux VM.")
        pass # No generic device mount for Windows in this context

    # Command to run sdr_manager.py's detection method inside the container
    run_detection_command = [
        "docker", "run", "--rm", "-it", "--network=host", "--privileged",
        *device_mounts,
        docker_image_name,
        "python3", "sdr_manager.py", "detect_sdr_only"
    ]
    
    selected_sdr_dev_string = None
    print(f"Executing SDR detection in Docker: {' '.join(run_detection_command)}")
    try:
        process = subprocess.Popen(run_detection_command, stdin=sys.stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout_lines = []
        stderr_lines = []

        # Read stdout and stderr line by line to process output
        while True:
            stdout_line = process.stdout.readline()
            stderr_line = process.stderr.readline()

            if stdout_line == '' and stderr_line == '' and process.poll() is not None:
                break
            if stdout_line:
                sys.stdout.write(stdout_line) # Print to host console
                stdout_lines.append(stdout_line.strip())
                if "SELECTED_SDR_DEVICE:" in stdout_line:
                    selected_sdr_dev_string = stdout_line.replace("SELECTED_SDR_DEVICE:", "").strip()
                elif "NO_SDR_DEVICES_FOUND" in stdout_line:
                    # If this is found, we know no devices were detected
                    # We can break early or let the loop finish and then check
                    pass # Let the loop finish to ensure all messages are printed

            if stderr_line:
                sys.stderr.write(stderr_line) # Print to host console
                stderr_lines.append(stderr_line.strip())
        
        # Wait for the process to terminate and get its return code
        process.wait()

        if process.returncode != 0:
            # If sdr_manager.py exited with an error (e.g., no devices found and it signaled an error)
            # or if there was a Docker error.
            # We already printed the output, just need to check for the specific message.
            if "NO_SDR_DEVICES_FOUND" in "\n".join(stdout_lines):
                 print("\n--- SDR Detection Failed: No devices found in Docker container ---", file=sys.stderr)
                 print("This usually indicates a problem with USB device passthrough from your host macOS to the Docker VM.", file=sys.stderr)
                 print("\nTroubleshooting Steps for macOS Docker USB Passthrough:", file=sys.stderr)
                 print("1. Verify your SDR is connected and recognized by macOS: Open 'System Information' (search in Spotlight), then go to 'USB' under 'Hardware'. Look for your SDR device.", file=sys.stderr)
                 print("2. Check Docker Desktop settings: Go to Docker Desktop -> Settings (or Preferences) -> Resources -> USB. Ensure your device is listed and enabled for sharing with containers. You might need to restart Docker Desktop after changes.", file=sys.stderr)
                 print("3. Try a different USB port or cable.", file=sys.stderr)
                 print("4. Some complex SDRs (e.g., USRPs) require specific drivers or firmware on the host before Docker can access them.", file=sys.stderr)
                 print("5. Consider running a dedicated Linux Virtual Machine (e.g., with VirtualBox, UTM, or Parallels) and installing GNU Radio and drivers directly in that VM, then running your scripts there. USB passthrough is often more reliable in full VMs.", file=sys.stderr)
                 print("6. For advanced users: Explore `usbip` if you have a Linux VM where you can forward USB devices to the Docker container.", file=sys.stderr)
                 sys.exit(1) # Exit with an error code
            else:
                print(f"Critical error: SDR detection failed in Docker with exit code {process.returncode}.", file=sys.stderr)
                print("Please review the output above for specific errors.", file=sys.stderr)
                sys.exit(1)

        if not selected_sdr_dev_string:
            # This case should ideally be caught by NO_SDR_DEVICES_FOUND or a direct selection.
            # If we reach here, it means no device was selected and no specific error was signaled.
            print("Error: SDR detection completed, but no device was selected or identified.", file=sys.stderr)
            sys.exit(1)

        print(f"Step 2: Selected SDR: '{selected_sdr_dev_string}'.")

    except Exception as e:
        print(f"An unexpected error occurred during SDR detection: {e}", file=sys.stderr)
        sys.exit(1)

    # 3. Run the LoRa demodulator flowgraph within the Docker container
    print("\nStep 3: Launching the LoRa demodulator within the Docker container...")
    
    run_demodulator_command = [
        'docker', 'run', '--rm', '-it',
        '--network=host',           # Allows container to reach host.docker.internal
        '--privileged',             # Still needed for some low-level access within container, though --device handles main USB
        '--device=/dev/bus/usb',    # Pass through the USB device
        '-e', 'GR_DISABLE_VM_ALLOCATOR=1', # NEW: For vmcircbuf error
        '-e', 'QT_QPA_PLATFORM=offscreen',  # Tell Qt/X applications where to display
        *device_mounts,
        docker_image_name,
        "python3", "Generic_Decoder.py",
        "--sdr-dev-string", selected_sdr_dev_string,
        "--sample-rate", "250e3",
        "--center-freq", "433e6",
        "--gain", "20"
    ]
    
    print(f"Executing LoRa demodulator in Docker: {' '.join(run_demodulator_command)}")
    try:
        # For the demodulator, we want full interactivity
        subprocess.run(run_demodulator_command, check=True, stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr)
    except subprocess.CalledProcessError as e:
        print(f"LoRa demodulator script failed in Docker with error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"An unexpected error occurred while launching demodulator in Docker: {e}", file=sys.stderr)
    
    print("\n--- LoRa SDR Process Finished ---")

if __name__ == "__main__":
    # This allows sdr_manager.py to be called directly from Orchestrator for specific tasks
    if len(sys.argv) > 1 and sys.argv[1] == "detect_sdr_only":
        # This branch is executed when Orchestrator runs sdr_manager.py inside Docker
        from sdr_manager import SDRManager
        sdr_manager = SDRManager()
        sdr_manager.detect_and_select_sdr()
        # sdr_manager.py already prints SELECTED_SDR_DEVICE or NO_SDR_DEVICES_FOUND
        sys.exit(0)
    else:
        main()
