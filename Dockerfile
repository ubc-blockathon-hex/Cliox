FROM ollama/ollama:latest

# Install scikit-learn specific dependencies and Python
RUN apt-get update && apt-get install -y \
    python3 python3-pip \
    libgomp1 libstdc++6 build-essential \
    curl \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /algorithm

# Copy the algorithm code (with the same depth)
COPY template/algorithm/src /algorithm/src
COPY template/algorithm/tests /algorithm/tests
COPY template/algorithm/requirements.txt /algorithm/requirements.txt
COPY entrypoint.sh /algorithm/entrypoint.sh

# Install the dependencies from the requirements.txt file
RUN pip install --no-cache-dir --break-system-packages -r /algorithm/requirements.txt

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Expose Ollama’s port
EXPOSE 11434

# Check if running dev & tests
# CMD ["sh", "/entrypoint.sh"]

# Bottom due to cache
ENV VERSION_TAG="0.0.0"