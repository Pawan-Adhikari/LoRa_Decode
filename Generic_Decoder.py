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
from gnuradio import soapy


class Generic_Decoder(gr.top_block, Qt.QWidget):
    def __init__(self, sdr_dev_string="", samp_rate=1024000.000000, center_freq=412e6, gain=20):
        gr.top_block.__init__(self, "Not titled yet", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Not titled yet")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except BaseException as exc:
            print(f"Qt GUI: Could not set Icon: {str(exc)}", file=sys.stderr)
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("gnuradio/flowgraphs", "Generic_Decoder")

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

        self.soapy_custom_source_0.set_sample_rate(0, self.samp_rate)
        self.soapy_custom_source_0.set_frequency(0, self.center_freq)
        self.soapy_custom_source_0.set_frequency_correction(0, 0) 
        self.soapy_custom_source_0.set_iq_balance(0, 0)

        try:
            self.soapy_custom_source_0.set_dc_offset_mode(0, False) 
        except ValueError as e:
            print(f"[WARN] SDR does not support automatic DC offset mode: {e}. Keeping it off.", file=sys.stderr)
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
        self.settings = Qt.QSettings("gnuradio/flowgraphs", "Generic_Decoder")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()
        event.accept()


def main(top_block_cls=Generic_Decoder):
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
