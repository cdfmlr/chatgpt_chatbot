# Build phase
FROM python:3.10.10-slim-bullseye AS builder

# Set the working directory
WORKDIR /app

# Install build dependencies
RUN sed -i 's#http://deb.debian.org#https://mirrors.tuna.tsinghua.edu.cn#g' /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y build-essential

ENV PIP_DEFAULT_TIMEOUT=1000 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 

RUN pip install poetry -i https://pypi.tuna.tsinghua.edu.cn/simple

# Copy and install the dependencies
COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.create false && \
    poetry install --no-dev --no-interaction --no-ansi --no-root


# Arm64 wheel contains a debug / non stripped version of the .so library
# - https://github.com/grpc/grpc/issues/29935
# - https://command-not-found.com/strip
RUN if [ "$(uname -m)" = 'aarch64' ]; then \
	  apt-get install -y binutils && \
	  strip -s -g -S -d --strip-debug /usr/local/lib/python3.10/site-packages/grpc/_cython/cygrpc.cpython-310-aarch64-linux-gnu.so \
    ; fi

# Copy the source code
COPY . .

# Build the server
#RUN poetry build -f wheel && \
#    pip install dist/*.whl

# Runtime phase
FROM python:3.10.10-slim-bullseye

# Set the working directory
WORKDIR /app

# Copy the server binary and its dependencies from the builder image
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /app /app

# Expose the port that the server will listen on
# EXPOSE 50051

# Start the server
CMD cd /app && \
	GRPC_REFLECTION=True \
	CHATGPT_V3_COOLDOWN=10 \
	python chatgpt --grpc 0.0.0.0:50052

