FROM ubuntu:23.10
LABEL name="gpt4all-box"
LABEL description="A gpt4all agent running as a RESTful API service."
LABEL maintainer="Anthony Waldsmith <awaldsmith@protonmail.com>"

# Install dependencies (libnvidia-gl-525-server)
RUN apt-get update -yq && apt-get install --no-install-recommends -yq git gcc g++ make cmake openssl curl zlib1g-dev python3-pip libvulkan-dev libvulkan1 vulkan-tools mesa-vulkan-drivers

# Install vulkan-sdk
RUN cd /tmp \
	&& curl -so - https://packages.lunarg.com/lunarg-signing-key-pub.asc | tee /etc/apt/trusted.gpg.d/lunarg.asc \
	&& curl -so /etc/apt/sources.list.d/lunarg-vulkan-jammy.list https://packages.lunarg.com/vulkan/lunarg-vulkan-jammy.list \
	&& apt update -yq \
	&& apt install -yq vulkan-sdk

ADD requirements.txt .
RUN pip install -r requirements.txt --break-system-packages

# Create user
RUN useradd -m gpt4all

WORKDIR /home/gpt4all

# Switch to user-mode
USER gpt4all

# Build pip dependences and install gpt4all for python
RUN echo "export PATH='${PATH}:~/.local/bin'" >> ~/.profile \
	&& . ~/.profile
RUN git clone --recurse-submodules https://github.com/nomic-ai/gpt4all \
	&& cd gpt4all/gpt4all-backend/ \
	&& mkdir build \
	&& cd build \
	&& cmake .. \
	&& cmake --build . --parallel --config Release \
	&& cd ../../gpt4all-bindings/python \
	&& pip install -e . --break-system-packages \
	&& cd ~/ \
	&& rm -rf gpt4all/

CMD python3 src/g4ab.py
