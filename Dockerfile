FROM python:alpine
LABEL name="gpt4all-box"
LABEL description="A gpt4all agent running as a RESTful API service."
LABEL maintainer="Anthony Waldsmith <awaldsmith@protonmail.com>"

# Install dependencies
RUN apk --update add git musl-dev libgcc openssl-dev curl zlib-dev py3-pip gcc g++ make cmake

WORKDIR /tmp

ADD requirements.txt .

RUN cd /tmp && pip install -r requirements.txt

RUN git clone --recurse-submodules https://github.com/nomic-ai/gpt4all \
	&& cd gpt4all/gpt4all-backend/ \
	&& mkdir build \
	&& cd build \
	&& cmake .. \
	&& cmake --build . --parallel \
	&& cd ../../gpt4all-bindings/python \
	&& pip install -e . \
	&& mkdir -p ~/.cache/gpt4all/

WORKDIR /mnt

CMD python3 src/g4ab.py
