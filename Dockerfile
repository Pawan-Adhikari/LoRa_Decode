# Use an Ubuntu base image
FROM ubuntu:22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV HOME=/root
ENV GR_DISABLE_VM_ALLOCATOR=1
ENV PYTHONPATH=/usr/lib/python3/dist-packages:/usr/local/lib/python3/dist-packages:$PYTHONPATH

# Install system dependencies and SDR-related tools
RUN apt-get update && apt-get install -y \
    avahi-daemon \
    libnss-mdns \
    build-essential \
    cmake \
    git \
    python3 \
    python3-pip \
    python3-numpy \
    python3-scipy \
    python3-pyqt5 \
    libusb-1.0-0-dev \
    pkg-config \
    gnuradio \
    gnuradio-dev \
    libsoapysdr-dev \
    soapysdr-tools \
    soapysdr-module-rtlsdr \
    soapysdr-module-uhd \
    soapysdr-module-hackrf \
    soapysdr-module-lms7 \
    rtl-sdr \
    uhd-host \
    hackrf \
    limesuite \
    libiio-utils \
    libiio-dev \
    libad9361-dev \
    && rm -rf /var/lib/apt/lists/*

# --- Fix GNU Radio buffer allocation bug ---
RUN mkdir -p /root/.gnuradio/prefs && \
    echo "[gr]" > /root/.gnuradio/prefs/vmcircbuf_default_factory && \
    echo "default = gr::vmcircbuf_malloc" >> /root/.gnuradio/prefs/vmcircbuf_default_factory

# Build gr-lora_sdr from source
WORKDIR /root/gr-lora_sdr
RUN git clone https://github.com/tapparelj/gr-lora_sdr.git . && \
    mkdir build && cd build && \
    cmake .. && \
    make -j$(nproc) && \
    make install && \
    ldconfig

# Create necessary runtime directories
RUN mkdir -p /var/run/dbus && chmod 755 /var/run/dbus && \
    rm -f /var/run/avahi-daemon/pid

# Optional: Build SoapyPlutoSDR from source
WORKDIR /root/SoapyPlutoSDR
RUN git clone https://github.com/pothosware/SoapyPlutoSDR.git . && \
    mkdir build && cd build && \
    cmake .. && \
    make -j$(nproc) && \
    make install && \
    ldconfig

RUN /usr/lib/uhd/utils/uhd_images_downloader.py

# Set working directory for your LoRa decoding scripts
WORKDIR /app
COPY Generic_Decoder.py ./
COPY sdr_manager.py ./
COPY Orchestrator.py ./

# Default command
CMD ["python3", "Orchestrator.py"]
