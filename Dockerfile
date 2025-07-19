FROM ollama/ollama:latest

# Install scikit-learn specific dependencies and Python
RUN apt-get update && apt-get install -y \
    python3 python3-pip \
    libgomp1 libstdc++6 build-essential \
    curl \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /algorithm

# Copy the algorithm code (with the same depth)
COPY template/algorithm/requirements.txt /algorithm/requirements.txt

# Install the dependencies from the requirements.txt file
RUN pip install --no-cache-dir --break-system-packages -r /algorithm/requirements.txt

COPY template/algorithm/src /algorithm/src
COPY template/algorithm/tests /algorithm/tests

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Expose Ollama’s port
EXPOSE 11434

COPY entrypoint.sh /algorithm/entrypoint.sh
# Check if running dev & tests
ENTRYPOINT ["/bin/sh", "/algorithm/entrypoint.sh"]
CMD ["sh", "export OLLAMA_CONTEXT_LENGTH=2048"]
# Bottom due to cache
ENV VERSION_TAG="0.0.1"