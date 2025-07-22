import subprocess
import sys
import os
import json
import time

# In Docker, we expect SoapySDR and gnuradio.soapy to be correctly installed
# and discoverable via PYTHONPATH set in the Dockerfile.
try:
    import SoapySDR
    from SoapySDR import *
    print("[INFO] SoapySDR Python binding found in Docker environment for detection.")
except ImportError:
    print("[ERROR] SoapySDR Python binding not found in Docker environment. This is critical.", file=sys.stderr)
    print("Please check your Dockerfile for SoapySDR Python binding installation/path setup.", file=sys.stderr)
    sys.exit(1) # Critical error, cannot proceed without SoapySDR

try:
    import gnuradio.soapy # Ensure gnuradio.soapy is also importable
    print("[INFO] gnuradio.soapy module found in Docker environment.")
except ImportError:
    print("[ERROR] gnuradio.soapy module not found in Docker environment. This is critical.", file=sys.stderr)
    print("Please check your Dockerfile for gnuradio and gr-soapy installation/path setup.", file=sys.stderr)
    sys.exit(1) # Critical error, cannot proceed without gnuradio.soapy

class SDRManager:
    def __init__(self):
        # No more venv management or system-level installations in Docker
        print("SDRManager initialized for Docker environment.")

    def _run_command(self, command, check_output=False, shell=False, env=None):
        """Helper to run shell commands within the Docker context."""
        # For internal calls, we still want to print to stdout/stderr
        # For calls that need to return output, use check_output=True
        print(f"Executing internal command: {' '.join(command)}")
        try:
            if check_output:
                result = subprocess.run(command, check=True, capture_output=True, text=True, shell=shell, env=env)
                print(f"Internal command output:\n{result.stdout.strip()}")
                if result.stderr:
                    print(f"Internal command errors (stderr):\n{result.stderr.strip()}", file=sys.stderr)
                return result.stdout.strip()
            else:
                subprocess.run(command, check=True, shell=shell, env=env)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Internal command failed with error code {e.returncode}: {e}", file=sys.stderr)
            if e.stdout: print(f"Stdout: {e.stdout.strip()}", file=sys.stderr)
            if e.stderr: print(f"Stderr: {e.stderr.strip()}", file=sys.stderr)
            return False
        except FileNotFoundError:
            print(f"Internal command not found: {command[0]}. Is it installed and in PATH within Docker?", file=sys.stderr)
            return False
        except Exception as e:
            print(f"An unexpected error occurred during internal command: {e}", file=sys.stderr)
            return False

    def check_soapy_sdr_util(self):
        """Checks if SoapySDRUtil is available and working within Docker."""
        print("Checking if SoapySDRUtil is installed and working...")
        try:
            output = self._run_command(["SoapySDRUtil", "--info"], check_output=True)
            if "Lib Version: v" in output and "Available factories" in output:
                print("SoapySDRUtil is installed and working.")
                return True
            else:
                print("SoapySDRUtil output is incomplete or unexpected. SoapySDR might not be fully configured.", file=sys.stderr)
                return False
        except Exception as e:
            print(f"SoapySDRUtil command failed: {e}. SoapySDR might not be installed or in PATH within Docker.", file=sys.stderr)
            return False

    def check_gr_lora_sdr_import(self):
        """Checks if gr-lora_sdr can be imported within Docker."""
        print("Checking if gr-lora_sdr can be imported...")
        try:
            check_script = "import gnuradio.lora_sdr; print('gr-lora_sdr import successful')"
            output = self._run_command(["python3", "-c", check_script], check_output=True)
            if "gr-lora_sdr import successful" in output:
                print("gr-lora_sdr is importable.")
                return True
            else:
                print("gr-lora_sdr import failed. See error above.", file=sys.stderr)
                return False
        except Exception as e:
            print(f"Error checking gr-lora_sdr import: {e}", file=sys.stderr)
            return False

    def detect_and_select_sdr(self):
        print("\n--- Detecting Connected SDR Devices via SoapySDR ---")
        
        try:
            results = SoapySDR.Device.enumerate()

            if not results:
                print("No SDR devices found via SoapySDR. Please ensure your SDR is connected and powered on.", file=sys.stderr)
                print("NO_SDR_DEVICES_FOUND") # <--- Signal to Orchestrator
                return None

            print("Found the following SDR devices:")
            device_options = []
            for i, device_info in enumerate(results):
                driver = device_info['driver'] if 'driver' in device_info else "N/A"
                label = device_info['label'] if 'label' in device_info else f"Unknown SDR {i}"
                serial = device_info['serial'] if 'serial' in device_info else ""
                addr = device_info['addr'] if 'addr' in device_info else ""
                
                dev_args = f"driver={driver}"
                if serial:
                    dev_args += f",serial={serial}"
                elif addr:
                    dev_args += f",addr={addr}"
                
                device_options.append({
                    "index": i,
                    "label": label,
                    "driver_key": driver,
                    "device_args": dev_args
                })
                print(f"  [{i}] Label: {label}, Driver: {driver}, Device Args: '{dev_args}'")

        except Exception as e:
            # This catch-all is for the outer block where you call SoapySDR.Device.enumerate()
            print(f"ERROR_SDR_DETECTION: {e}", file=sys.stderr)
            print("Could not detect SDRs. Please ensure SoapySDR is installed and working within the Docker container.", file=sys.stderr)
            print("NO_SDR_DEVICES_FOUND") # <--- Signal to Orchestrator
            return None

        #selected_index = -1
        #while selected_index == -1 or selected_index <= len(device_options):
            #try:
                #user_input = input("Which device do you want to choose ?")
                #selected_index = int(user_input)
            #except ValueError:
                #print("Invalid input. Please enter an index from above.")
            #except KeyboardInterrupt:
                #print("\nUser interrupted. Exiting.")
                #sys.exit(0)
        selected_index = 0

        chosen_device = device_options[selected_index]
        print(f"\nSelected SDR: '{chosen_device['label']}' (Driver: {chosen_device['driver_key']})")
        
        print(f"SoapySDR driver module for '{chosen_device['driver_key']}' is assumed to be installed in Docker container.")
        
        print(f"SELECTED_SDR_DEVICE:{chosen_device['device_args']}") # Ensure this is always printed on success
        return chosen_device['device_args']

def ensure_avahi_daemon_running():
    """
    Checks if D-Bus and Avahi daemons are running and starts them if they're not.
    This function assumes avahi-daemon and dbus are already installed in the container.
    """
    print("Checking if D-Bus daemon is running...")
    try:
        subprocess.run(["pgrep", "dbus-daemon"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("D-Bus daemon already running.")
    except subprocess.CalledProcessError:
        print("D-Bus daemon not found running. Attempting to start...")
        # Create the run directory for D-Bus socket if it doesn't exist
        os.makedirs("/var/run/dbus", exist_ok=True)
        os.chmod("/var/run/dbus", 0o755) # Ensure correct permissions

        # Start D-Bus daemon in the background
        dbus_start_cmd = "/usr/bin/dbus-daemon --system --nopidfile --print-address &"
        dbus_result = os.system(dbus_start_cmd)
        if dbus_result != 0:
            print(f"ERROR: Failed to start dbus-daemon (os.system exit code: {dbus_result}).", file=sys.stderr)
            return False
        print("D-Bus daemon command sent. Giving it a moment to initialize...")
        time.sleep(1) # Give D-Bus a moment to create its socket
        
        # Optional: Verify D-Bus is actually running
        try:
            subprocess.run(["pgrep", "dbus-daemon"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print("D-Bus daemon successfully started.")
        except subprocess.CalledProcessError:
            print("WARNING: D-Bus daemon did not appear to start after delay.", file=sys.stderr)
            # Proceed, but this might indicate a deeper issue or a very slow start
            

    print("Checking if Avahi daemon is running...")
    try:
        # Check if avahi-daemon process is already running
        subprocess.run(["pgrep", "avahi-daemon"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("Avahi daemon is already running.")
        return True
    except subprocess.CalledProcessError:
        print("Avahi daemon not found running. Attempting to start...")
        
        # Start Avahi daemon in the background
        start_cmd = "/usr/sbin/avahi-daemon --no-drop-root &"
        result = os.system(start_cmd)

        if result != 0:
            print(f"ERROR: Failed to start avahi-daemon (os.system exit code: {result}).", file=sys.stderr)
            print("Ensure /usr/sbin/avahi-daemon exists and has execute permissions.", file=sys.stderr)
            return False
        else:
            print("Avahi daemon command sent. Giving it a moment to initialize...")
            time.sleep(3) # Give Avahi a bit more time to get up and running
            
            # Optional: Verify it's actually running after sleep
            try:
                subprocess.run(["pgrep", "avahi-daemon"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                print("Avahi daemon successfully started and verified.")
                return True
            except subprocess.CalledProcessError:
                print("WARNING: Avahi daemon did not appear to start after delay.", file=sys.stderr)
                return False

# --- Command Line Argument Handling for Docker Entrypoint ---
if __name__ == "__main__":
    if not ensure_avahi_daemon_running():
        print("Avahi daemon could not be started or verified. SDR discovery may fail.", file=sys.stderr)
        # You might want to exit here if Avahi is absolutely critical
        # sys.exit(1)
    if len(sys.argv) > 1 and sys.argv[1] == "detect_sdr_only":
        sdr_manager = SDRManager()
        sdr_manager.detect_and_select_sdr()
        # The detect_and_select_sdr method already prints the necessary output (SELECTED_SDR_DEVICE or NO_SDR_DEVICES_FOUND)
        sys.exit(0)
    else:
        print("SDRManager script can be run with 'detect_sdr_only' argument for SDR detection.")
        print("Example: python3 sdr_manager.py detect_sdr_only")
        sys.exit(1) # Indicate an error if not called correctly
