FROM python:3.11

# 1. Install system tools (excluding the resolv.conf edit)
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    dnsutils \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# 2. Install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 3. Copy project files
COPY . .

# 4. Hugging Face Security Compliance
# We still need this to ensure the app runs with the correct permissions
RUN useradd -m -u 1000 user && \
    chown -R user:user /app
USER user
ENV PATH="/home/user/.local/bin:${PATH}"

EXPOSE 7860
CMD ["python", "bot.py"]
