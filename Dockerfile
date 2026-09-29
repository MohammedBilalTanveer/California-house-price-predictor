# Container image for hosting: Hugging Face Spaces, Render, Koyeb, Google Cloud Run, ...
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Run as a non-root user with uid 1000 (what Hugging Face Spaces expects).
RUN useradd --create-home --uid 1000 user \
    && mkdir /home/user/app && chown user:user /home/user/app
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install --user -r requirements.txt

COPY --chown=user . .
# Train at build time (same recipe and random_state as the notebook) so the server starts fast.
RUN python train.py

# Hosts pass the port in $PORT; 7860 is the Hugging Face Spaces default.
ENV PORT=7860
EXPOSE 7860
CMD ["sh", "-c", "exec uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
