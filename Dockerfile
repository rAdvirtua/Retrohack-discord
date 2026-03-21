# 1. Use a stable, lightweight Python base
FROM python:3.11-slim

# 2. Prevent Python from writing .pyc files and enable real-time logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Set the working directory in the container
WORKDIR /app

# 4. Copy requirements and install them
# We do this before copying the rest of the code to take advantage of Docker's cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of your project files
COPY . .

# 6. Hugging Face Security: Create and switch to a non-root user (UID 1000)
# This is required for Docker spaces to run successfully.
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:${PATH}"

# 7. Expose the mandatory Hugging Face port
EXPOSE 7860

# 8. The command to launch your "Hunter" bot
# This will execute bot.py, which in turn triggers keep_alive.py
CMD ["python", "bot.py"]
