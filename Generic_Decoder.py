#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Generic LoRa Decoder
# GNU Radio version: 3.10.12.0

from PyQt5 import Qt, QtCore, QtWidgets
from gnuradio import qtgui
from gnuradio import blocks, gr
from gnuradio import gr
from gnuradio.filter import firdes
from gnuradio.fft import window
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
import gnuradio.lora_sdr as lora_sdr
import threading
import os

# Import soapy block specifically, as it might not be in gr namespace by default
try:
    from gnuradio import soapy
except ImportError:
    print("Error: gnuradio.soapy module not found. Please ensure gr-soapy is installed.", file=sys.stderr)
    sys.exit(1)

class LoRaDemodulatorFlowgraph(gr.top_block, Qt.QWidget):
    def __init__(self, sdr_dev_string="", samp_rate=125e3, center_freq=412e6, gain=20):
         # ADD THESE TWO DEBUG PRINT LINES HERE:
        print(f"DEBUG (Inside Container): GR_VMCIRCBUF_DEFAULT_FACTORY={os.getenv('GR_VMCIRCBUF_DEFAULT_FACTORY')}", file=sys.stderr)
        # This next line attempts to get the factory GNU Radio actually picked. It might also error if vmcircbuf is totally broken, but worth a try.
        try:
            print(f"DEBUG (Inside Container): gr.vmcircbuf_default_factory_get()={gr.vmcircbuf_default_factory_get()}", file=sys.stderr)
        except AttributeError:
            print("DEBUG (Inside Container): gr.vmcircbuf_default_factory_get() not available or failed.", file=sys.stderr)
        except Exception as e:
            print(f"DEBUG (Inside Container): Error calling gr.vmcircbuf_default_factory_get(): {e}", file=sys.stderr)
        # --- END OF DEBUG PRINT LINES ---
        gr.top_block.__init__(self, "Generic LoRa Decoder", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Generic LoRa Decoder")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except BaseException as exc:
            print(f"Qt GUI: Could not set Icon: {str(exc)}", file=sys.stderr)
        self.top_scroll_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = QtWidgets.QScrollArea()
        self.top_scroll.setFrameStyle(QtWidgets.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = QtWidgets.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = QtWidgets.QVBoxLayout(self.top_widget)
        self.top_grid_layout = QtWidgets.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "lora_demod_generic")

        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Parameters (Passed as arguments or fixed for LoRa)
        ##################################################
        self.samp_rate = samp_rate
        self.center_freq = center_freq
        self.gain = gain
        self.sdr_dev_string = sdr_dev_string

        # LoRa specific parameters (fixed for this decoder)
        self.lora_bw = 125000
        self.lora_sf = 7
        self.lora_cr = 1
        self.lora_sync_word = 0x12

        ##################################################
        # Blocks
        ##################################################

        # Soapy Custom Source block - uses the dynamically passed sdr_dev_string
        stream_args = 'bufflen=16384' # Common stream arg, can be made dynamic too
        tune_args = ['']
        settings = ['']

        print(f"Attempting to open SDR with device string: '{self.sdr_dev_string}'")
        self.soapy_custom_source_0 = soapy.source(self.sdr_dev_string, "fc32", 1, '',
                                  stream_args, tune_args, settings)

        # Configure SDR RF parameters
        self.soapy_custom_source_0.set_sample_rate(0, self.samp_rate)
        self.soapy_custom_source_0.set_frequency(0, self.center_freq)
        self.soapy_custom_source_0.set_frequency_correction(0, 0) # PPM correction

        # Try to set DC offset mode; catch error if not supported (common for RTL-SDR)
        try:
            self.soapy_custom_source_0.set_dc_offset_mode(0, False) # Set to False (manual/off)
        except ValueError as e:
            print(f"[WARN] SDR does not support automatic DC offset mode: {e}. Keeping it off.", file=sys.stderr)
        
        # Set bias tee (default to False)
        # Set bias tee (default to False)
        biastee_supported = False
        try:
            # get_setting_info() returns a list of objects, each with a 'key' attribute
            for setting_info in self.soapy_custom_source_0.get_setting_info():
                if setting_info.key == 'biastee': # Check the 'key' attribute of each setting
                    biastee_supported = True
                    break # Found it, no need to check further
        except Exception as e:
            # This handles cases where get_setting_info() might fail or not exist in a very old binding
            print(f"[WARN] Could not retrieve setting info for bias tee check: {e}", file=sys.stderr)
            # If an error occurs here, biastee_supported remains False, and we skip setting it.

        if biastee_supported:
            try:
                self.soapy_custom_source_0.write_setting('biastee', 'false')
            except Exception as e:
                print(f"[WARN] Could not set bias tee to false: {e}", file=sys.stderr)
        else:
            print("[INFO] Bias tee setting not supported by this SDR (checked via get_setting_info).", file=sys.stderr)


        # Set gain
        try:
            self.soapy_custom_source_0.set_gain(0, self.gain)
        except Exception as e:
            print(f"[WARN] Could not set gain to {self.gain} dB: {e}", file=sys.stderr)


        # LoRa RX block
        self.lora_rx_0 = lora_sdr.lora_sdr_lora_rx(
            bw=self.lora_bw,
            cr=self.lora_cr,
            has_crc=True,
            impl_head=False,
            pay_len=255,
            samp_rate=int(self.samp_rate),
            sf=self.lora_sf,
            sync_word=[self.lora_sync_word],
            soft_decoding=True,
            ldro_mode=2,
            print_rx=[True,True]
        )
        self.blocks_message_debug_0 = blocks.message_debug(True)


        ##################################################
        # Connections
        ##################################################
        self.msg_connect((self.lora_rx_0, 'out'), (self.blocks_message_debug_0, 'print'))
        self.connect((self.soapy_custom_source_0, 0), (self.lora_rx_0, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "lora_demod_generic")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()
        event.accept()


def main(top_block_cls=LoRaDemodulatorFlowgraph):
    parser = ArgumentParser(description="Generic LoRa Demodulator using SoapySDR")
    parser.add_argument("--sdr-dev-string", type=str, required=True,
                        help="SoapySDR device string (e.g., 'driver=rtlsdr', 'driver=uhd,serial=XXXX')")
    parser.add_argument("--sample-rate", type=eng_float, default=125e3,
                        help="SDR Sample Rate in Hz (default: 125e3)")
    parser.add_argument("--center-freq", type=eng_float, default=412e6,
                        help="SDR Center Frequency in Hz (default: 412e6)")
    parser.add_argument("--gain", type=eng_float, default=20,
                        help="SDR Gain in dB (default: 20)")
    args = parser.parse_args()

    qapp = QtWidgets.QApplication(sys.argv)

    tb = top_block_cls(
        sdr_dev_string=args.sdr_dev_string,
        samp_rate=args.sample_rate,
        center_freq=args.center_freq,
        gain=args.gain
    )

    tb.start()
    tb.flowgraph_started.set()

    tb.show()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()
        QtWidgets.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = QtCore.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    qapp.exec_()

if __name__ == '__main__':
    main()
